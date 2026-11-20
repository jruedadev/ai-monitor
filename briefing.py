"""Briefing del Inicio: el mes en curso contra un mes comparable y las señales
de "Atención ahora". No es un collector: solo lee history.db y nunca toca a los
proveedores. Lógica en funciones puras sobre filas; SQLite en una capa delgada.
Spec: docs/superpowers/specs/2026-09-27-inicio-briefing-design.md
"""
import calendar
import json
import logging
import math
import os
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import accounts as accounts_mod
import clients
import history

log = logging.getLogger(__name__)

PROJECT_SOURCES = ("claude_code", "codex", "opencode", "hermes")
# Codex todavía no tiene cuentas (spec multi-suscripción §8): su plan sigue en roi_settings.
CODEX_KEYS = ("subscription_cost_codex", "subscription_start_codex")
SOURCE_LABELS = {"claude_code": "Claude Code", "codex": "Codex", "opencode": "OpenCode",
                 "hermes": "Hermes", "openrouter": "OpenRouter"}
SOURCE_SLUGS = {"claude_code": "claude-code", "codex": "codex", "opencode": "opencode",
                "hermes": "hermes", "openrouter": "openrouter"}

_MONTHS_SHORT = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic")
_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class BriefingError(ValueError):
    """Parámetro inválido; server.py lo traduce a HTTP 400."""


# --- Formato: mismo resultado que frontend/src/lib/format.ts (es-CO) ---------

def format_usd(value):
    text = f"{abs(value):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    sign = "-" if value < 0 and text != "0,00" else ""
    return f"{sign}$ {text}"


def format_int(value):
    return f"{int(value):,}".replace(",", ".")


def format_ratio(value):
    return f"{value:.1f}".replace(".", ",")


def format_day(iso):
    _, month, day = (int(part) for part in iso[:10].split("-"))
    return f"{day} {_MONTHS_SHORT[month - 1]}"


# --- Ventanas y cobertura ----------------------------------------------------

def month_of(day):
    return f"{day.year:04d}-{day.month:02d}"


def previous_month(month):
    year, mon = (int(part) for part in month.split("-"))
    return f"{year - 1:04d}-12" if mon == 1 else f"{year:04d}-{mon - 1:02d}"


def month_window(month, day):
    """Del día 1 al `day` del mes; si el mes es más corto, se recorta a su último día."""
    year, mon = (int(part) for part in month.split("-"))
    last = calendar.monthrange(year, mon)[1]
    return f"{month}-01", f"{month}-{min(day, last):02d}"


def month_coverage(month, start):
    """("full", None), ("partial", since) o None si el mes es anterior al inicio de datos."""
    if start is None:
        return None
    if start <= f"{month}-01":
        return ("full", None)
    if start[:7] == month:
        return ("partial", start)
    return None


def eligible_months(start, current_month):
    if start is None:
        return []
    months = []
    month = previous_month(current_month)
    while month >= start[:7]:
        coverage, since = month_coverage(month, start)
        months.append({"month": month, "coverage": coverage, "since": since})
        month = previous_month(month)
    return months


# --- Filas -------------------------------------------------------------------

def valid_sources(accounts):
    """Fuentes aceptadas: las fijas más el source de cada cuenta configurada."""
    return (("all", "codex", "opencode", "hermes", "openrouter")
            + tuple(accounts_mod.source_name(a) for a in accounts))


VALID_SOURCES = valid_sources(accounts_mod.legacy_accounts({}))


def subscription_accounts(accounts, settings):
    """Cuentas con plan: las de Claude Code más Codex, que sigue leyéndose de roi_settings."""
    cost_key, start_key = CODEX_KEYS
    codex = {"id": "codex", "provider": "codex", "label": "Codex", "location": "", "default": True,
             "monthly_cost": settings.get(cost_key), "start_date": settings.get(start_key)}
    return list(accounts) + [codex]


def source_label(source, accounts=()):
    if source in SOURCE_LABELS:
        return SOURCE_LABELS[source]
    for account in accounts:
        if accounts_mod.source_name(account) == source:
            return f"{account['label']} (Claude Code)"
    return source


def source_slug(source):
    return SOURCE_SLUGS.get(source) or source.replace("claude_code", "claude-code", 1)


def rows_for_source(source, project_rows, model_rows):
    if source == "openrouter":
        return [{"date": r["date"][:10], "source": "openrouter", "project": None,
                 "tokens": r["tokens"] or 0, "cost": r["cost"]}
                for r in model_rows if r["model"] == "__all__"]
    if source == "all":
        return [r for r in project_rows
                if r["source"] in PROJECT_SOURCES or accounts_mod.is_claude_source(r["source"])]
    if source == "claude_code":  # todas las cuentas de Claude Code (spec §5.2)
        return [r for r in project_rows if accounts_mod.is_claude_source(r["source"])]
    return [r for r in project_rows if r["source"] == source]


def in_range(rows, start, end):
    return [r for r in rows if start <= r["date"] <= end]


def sum_cost(rows):
    return sum(r["cost"] or 0 for r in rows)


def sum_tokens(rows):
    return sum(r["tokens"] or 0 for r in rows)


def active_dates(rows):
    return sorted({r["date"] for r in rows if (r["tokens"] or 0) > 0 or (r["cost"] or 0) > 0})


def delta_pct(current, previous):
    if previous is None or previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


# --- Suscripción frente a API -------------------------------------------------

def compare_costs(api_cost, subscription_cost):
    """Misma regla que compareCosts en frontend/src/lib/roi.ts (Math.round a centavos)."""
    diff = api_cost - subscription_cost
    cents = math.floor(diff * 100 + 0.5)
    if cents == 0:
        return "tie", 0.0
    return ("subscription" if cents > 0 else "api"), abs(diff)


def _subscription_candidates(source, accounts):
    """Cuentas que entran en el veredicto de `source`: todas en "all", todas las del proveedor
    si `source` es el nombre del proveedor, o solo la cuenta cuyo source coincide."""
    if source == "all":
        return list(accounts)
    by_provider = [a for a in accounts if a["provider"] == source]
    if by_provider:
        return by_provider
    return [a for a in accounts if accounts_mod.source_name(a) == source]


def _parse_cost_setting(value):
    """float(value) o None si el dato guardado está corrupto — nunca debe romper el briefing."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_start_setting(value):
    """Fecha YYYY-MM-DD válida, o None (dato ausente o corrupto, p.ej. un número guardado
    por error)."""
    if value is None:
        return None
    text = str(value)[:10]
    return text if _DATE_RE.match(text) else None


def _verdict(candidates, project_rows, window):
    configured = []
    for account in candidates:
        cost = _parse_cost_setting(account.get("monthly_cost"))
        if cost is None:
            continue
        start = _parse_start_setting(account.get("start_date"))
        if start is not None and start > window[1]:
            # La suscripción todavía no empieza dentro de esta ventana: se trata como
            # no configurada para este mes, no como "paid $X, api $0".
            continue
        configured.append((accounts_mod.source_name(account), cost, start))
    if not configured:
        return {"configured": False, "paid": None, "api_equivalent": None, "winner": None, "savings": None}
    paid = sum(cost for _, cost, _ in configured)
    api = 0.0
    for s, _, start in configured:
        lower = max(window[0], start) if start else window[0]
        api += sum_cost(in_range([r for r in project_rows if r["source"] == s], lower, window[1]))
    winner, savings = compare_costs(api, paid)
    return {"configured": True, "paid": round(paid, 2), "api_equivalent": round(api, 2),
            "winner": winner, "savings": round(savings, 2)}


def subscription_summary(source, project_rows, accounts, window):
    return _verdict(_subscription_candidates(source, accounts), project_rows, window)


def accounts_summary(accounts, project_rows, window):
    """Un veredicto por cuenta; una cuenta sin filas queda en 0.0 ("sin datos"), no en error."""
    return [{"id": a["id"], "label": a["label"], "source": accounts_mod.source_name(a),
             **_verdict([a], project_rows, window)} for a in accounts]


# --- Proyectos -----------------------------------------------------------------

def client_of(path, roots=None):
    """Cliente del proyecto según las raíces configuradas (clients.client_of)."""
    return clients.client_of(path, roots if roots is not None else clients.default_roots())


def _project_costs(rows):
    costs = {}
    for r in rows:
        if r["project"] is not None:
            costs[r["project"]] = costs.get(r["project"], 0.0) + (r["cost"] or 0)
    return costs


def top_projects(rows, roots, limit=3):
    costs = _project_costs(rows)
    total = sum(costs.values())
    ranked = sorted(costs.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    return [{"project": p, "client": client_of(p, roots), "cost": round(c, 2),
             "share": round(c / total, 3) if total > 0 else 0.0} for p, c in ranked]


# --- Reglas de "Atención ahora" (Task 2) ---------------------------------------

# Umbrales (spec §3.4). La línea base siempre es la propia de la fuente filtrada.
SPIKE_FACTOR = 2.5
SPIKE_MIN_ACTIVE_DAYS = 5
CONCENTRATION_SHARE = 0.5
SUBSCRIPTION_MIN_ACTIVE_DAYS = 3
HABITUAL_WINDOW_DAYS = 30
HABITUAL_MIN_SHARE = 0.4
SILENT_MIN_DAYS = 3
SILENT_GAP_FACTOR = 3


def rule_spike_day(ctx):
    per_day = {}
    for r in ctx["window_rows"]:
        per_day[r["date"]] = per_day.get(r["date"], 0.0) + (r["cost"] or 0)
    active = {day: cost for day, cost in per_day.items() if cost > 0}
    if len(active) < SPIKE_MIN_ACTIVE_DAYS:
        return None
    average = sum(active.values()) / len(active)
    day, cost = max(active.items(), key=lambda kv: (kv[1], kv[0]))
    if cost <= SPIKE_FACTOR * average:
        return None
    when = "Hoy llevas" if day == ctx["today"].isoformat() else f"El {format_day(day)} gastaste"
    return {
        "id": "spike_day", "severity": "warning",
        "title": f"{when} {format_usd(cost)} — {format_ratio(cost / average)}× tu promedio diario",
        "evidence": [f"{day}: {format_usd(cost)}", f"Promedio de días activos del mes: {format_usd(average)}"],
        "link": f"/actividad?dia={day}",
    }


def rule_project_concentration(ctx):
    if ctx["source"] == "openrouter":
        return None
    costs = _project_costs(ctx["window_rows"])
    total = sum(costs.values())
    if total <= 0:
        return None
    project, cost = max(costs.items(), key=lambda kv: (kv[1], kv[0]))
    share = cost / total
    if share <= CONCENTRATION_SHARE:
        return None
    name = project.rstrip("/").split("/")[-1] or project
    return {
        "id": "project_concentration", "severity": "info",
        "title": f"{name} concentra el {round(share * 100)} % del gasto del mes",
        "evidence": [f"{project}: {format_usd(cost)} de {format_usd(total)}"],
        "link": f"/proyectos/{quote(client_of(project, ctx.get('roots')), safe='')}?proyecto={quote(project, safe='')}",
    }


def rule_cost_incomplete(ctx):
    days = sorted({r["date"] for r in ctx["window_rows"] if r["cost"] is None})
    if not days:
        return None
    shown = ", ".join(format_day(day) for day in days[:3]) + ("…" if len(days) > 3 else "")
    return {
        "id": "cost_incomplete", "severity": "info",
        "title": "Hay consumo sin costo calculado este mes",
        "evidence": [f"Días afectados: {shown}", "Esos consumos suman $ 0,00, así que el gasto real es mayor"],
        "link": "/gasto",
    }


def rule_subscription_missing(ctx):
    missing = []
    for account in _subscription_candidates(ctx["source"], ctx["accounts"]):
        if account.get("monthly_cost") is not None:
            continue
        source = accounts_mod.source_name(account)
        rows = in_range([r for r in ctx["project_rows"] if r["source"] == source], *ctx["window"])
        days = len(active_dates(rows))
        if days >= SUBSCRIPTION_MIN_ACTIVE_DAYS:
            missing.append((source, days))
    if not missing:
        return None
    label = lambda source: source_label(source, ctx["accounts"])
    labels = " y ".join(label(source) for source, _ in missing)
    return {
        "id": "subscription_missing", "severity": "info",
        "title": f"Configura tu plan de {labels} para comparar suscripción y API",
        "evidence": [f"{label(source)}: {days} días activos este mes, sin plan configurado"
                     for source, days in missing],
        "link": "/configuracion",
    }


def _silence(dates, today):
    """(días en silencio, días activos en los 30 previos, umbral, último día) si la
    fuente es habitual; None si es esporádica o no tiene datos."""
    if not dates:
        return None
    last = date.fromisoformat(dates[-1])
    since = last - timedelta(days=HABITUAL_WINDOW_DAYS - 1)
    recent = [d for d in (date.fromisoformat(x) for x in dates) if d >= since]
    if len(recent) / HABITUAL_WINDOW_DAYS < HABITUAL_MIN_SHARE:
        return None
    gaps = sorted((b - a).days for a, b in zip(recent, recent[1:]))
    typical = gaps[len(gaps) // 2] if gaps else 1
    threshold = max(SILENT_MIN_DAYS, SILENT_GAP_FACTOR * typical)
    return (today - last).days, len(recent), threshold, last


def rule_habitual_source_silent(ctx):
    candidates = PROJECT_SOURCES if ctx["source"] == "all" else (ctx["source"],)
    for source in candidates:
        rows = rows_for_source(source, ctx["project_rows"], ctx["model_rows"])
        info = _silence(active_dates(rows), ctx["today"])
        if info is None:
            continue
        silent, active, threshold, last = info
        if silent <= threshold:
            continue
        return {
            "id": "habitual_source_silent", "severity": "warning",
            "title": f"{source_label(source, ctx['accounts'])} lleva {silent} días sin datos",
            "evidence": [f"Último día con actividad: {format_day(last.isoformat())}",
                         f"Activa {active} de los {HABITUAL_WINDOW_DAYS} días previos; "
                         f"se avisa después de {threshold} días sin datos"],
            "link": f"/gasto?fuente={source_slug(source)}",
        }
    return None


RULES = (rule_spike_day, rule_project_concentration, rule_cost_incomplete,
         rule_subscription_missing, rule_habitual_source_silent)
MAX_SIGNALS = 3
_SEVERITY_ORDER = {"warning": 0, "info": 1}


def evaluate_rules(ctx):
    fired = []
    for index, rule in enumerate(RULES):
        signal = rule(ctx)
        if signal is not None:
            fired.append((index, signal))
    fired.sort(key=lambda item: (_SEVERITY_ORDER[item[1]["severity"]], item[0]))
    return [signal for _, signal in fired[:MAX_SIGNALS]]


# --- Ensamblado ----------------------------------------------------------------

def build_context(project_rows, model_rows, settings, today, source="all", roots=None, accounts=None):
    """Contexto que consumen las RULES: lo usan el briefing y el motor de
    recomendaciones (recommend/cost.py), que lo evalúa por fuente."""
    rows = rows_for_source(source, project_rows, model_rows)
    if accounts is None:
        accounts = accounts_mod.legacy_accounts(settings)
    window = month_window(month_of(today), today.day)
    return {"source": source, "today": today, "window": window, "rows": rows,
            "window_rows": in_range(rows, *window), "project_rows": project_rows,
            "model_rows": model_rows, "settings": settings,
            "roots": roots if roots is not None else clients.default_roots(),
            "accounts": subscription_accounts(accounts, settings)}


def build_briefing(project_rows, model_rows, settings, today, source="all", compare=None, degraded=False,
                   roots=None, accounts=None):
    if accounts is None:
        accounts = accounts_mod.legacy_accounts(settings)
    if source not in valid_sources(accounts):
        raise BriefingError(f"Fuente desconocida: {source}")
    if compare is not None and not _MONTH_RE.match(compare):
        raise BriefingError("El parámetro compare debe tener el formato YYYY-MM")

    current = month_of(today)
    ctx = build_context(project_rows, model_rows, settings, today, source, roots, accounts)
    rows = ctx["rows"]
    start = min((r["date"] for r in rows), default=None)
    eligible = eligible_months(start, current)
    by_month = {entry["month"]: entry for entry in eligible}

    if compare is None:
        compare_month = previous_month(current)
    elif compare in by_month or degraded:
        compare_month = compare
    else:
        raise BriefingError(f"No hay datos para comparar con {compare}")
    entry = by_month.get(compare_month)

    window, window_rows = ctx["window"], ctx["window_rows"]
    compare_window = month_window(compare_month, today.day)
    compare_rows = in_range(rows, *compare_window) if entry else []

    cost_now, cost_prev = sum_cost(window_rows), (sum_cost(compare_rows) if entry else None)
    tokens_now, tokens_prev = sum_tokens(window_rows), (sum_tokens(compare_rows) if entry else None)

    return {
        "source": source,
        "window": {"month": current, "from": window[0], "to": window[1]},
        "compare": {"month": compare_month, "from": compare_window[0], "to": compare_window[1],
                    "coverage": entry["coverage"] if entry else "none",
                    "since": entry["since"] if entry else None},
        "eligible_months": eligible,
        "kpis": {
            "cost": {"current": round(cost_now, 2),
                     "previous": round(cost_prev, 2) if cost_prev is not None else None,
                     "delta_pct": delta_pct(cost_now, cost_prev)},
            "tokens": {"current": tokens_now, "previous": tokens_prev,
                       "delta_pct": delta_pct(tokens_now, tokens_prev)},
            "active_days": {"current": len(active_dates(window_rows)),
                            "previous": len(active_dates(compare_rows)) if entry else None},
            "cost_incomplete": any(r["cost"] is None for r in window_rows),
        },
        "subscription": subscription_summary(source, project_rows, ctx["accounts"], window),
        "accounts": accounts_summary(accounts, project_rows, window),
        "top_projects": top_projects(window_rows, ctx["roots"]),
        "attention": evaluate_rules(ctx),
        "degraded": degraded,
    }


# --- Capa SQLite ---------------------------------------------------------------

def _empty_settings():
    return {key: None for key in history.ROI_SETTINGS_KEYS}


def load(db_path):
    """(project_rows, model_rows, settings). Sin base o sin tablas → vacío.
    Abre en solo lectura: el briefing nunca crea ni modifica history.db.
    Los sqlite3.Error se propagan para que get_briefing los marque como degradados."""
    settings = _empty_settings()
    if not os.path.exists(db_path):
        return [], [], settings
    # timeout = busy_timeout: espera si el escritor (el servidor) tiene la base bloqueada.
    con = sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    try:
        tables = {name for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        project_rows = []
        if "daily_project" in tables:
            project_rows = [
                {"date": d[:10], "source": s, "project": p, "tokens": t or 0, "cost": c}
                for d, s, p, t, c in con.execute("SELECT date, source, project, tokens, cost FROM daily_project")
            ]
        model_rows = []
        if "daily_model" in tables:
            model_rows = [
                {"date": d[:10], "model": m, "tokens": t or 0, "cost": c}
                for d, m, t, c in con.execute("SELECT date, model, tokens, cost FROM daily_model")
            ]
        if "roi_settings" in tables:
            for key, value in con.execute("SELECT key, value FROM roi_settings"):
                if key in settings:
                    settings[key] = value
    finally:
        con.close()
    return project_rows, model_rows, settings


def load_client_roots(db_path):
    """Raíces de cliente en solo lectura. Sin archivo, tabla o clave → por defecto.
    Los sqlite3.Error se propagan para que get_briefing los marque como degradados."""
    if not os.path.exists(db_path):
        return clients.default_roots()
    # timeout = busy_timeout: espera si el escritor (el servidor) tiene la base bloqueada.
    con = sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    try:
        tables = {name for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "app_settings" not in tables:
            return clients.default_roots()
        row = con.execute("SELECT value FROM app_settings WHERE key = 'client_roots'").fetchone()
    finally:
        con.close()
    return clients.parse_stored_roots(row[0] if row else None)


def load_accounts(db_path, settings):
    """Cuentas guardadas en solo lectura (el briefing nunca crea ni migra history.db).
    Sin archivo, tabla, clave o con valor inválido → cuentas legacy desde `settings`.
    Los sqlite3.Error se propagan para que get_briefing los marque como degradados."""
    if os.path.exists(db_path):
        con = sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
        try:
            tables = {name for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            row = (con.execute("SELECT value FROM app_settings WHERE key = 'accounts'").fetchone()
                   if "app_settings" in tables else None)
        finally:
            con.close()
        if row and row[0] is not None:
            try:
                return accounts_mod.normalize_accounts(json.loads(row[0]))
            except ValueError:  # JSON corrupto o AccountsError (subclase de ValueError)
                pass
    return accounts_mod.legacy_accounts(settings)


def get_briefing(db_path=None, source="all", compare=None, today=None):
    db_path = db_path or history.DB_PATH_DEFAULT
    today = today or datetime.now(timezone.utc).date()
    try:
        project_rows, model_rows, settings = load(db_path)
        roots = load_client_roots(db_path)
        accounts = load_accounts(db_path, settings)
        degraded = False
    except sqlite3.Error as exc:
        log.warning("briefing: no se pudo leer %s: %s", db_path, exc)
        project_rows, model_rows, settings = [], [], _empty_settings()
        roots = clients.default_roots()
        accounts = accounts_mod.legacy_accounts(settings)
        degraded = True
    return build_briefing(project_rows, model_rows, settings, today, source=source, compare=compare,
                          degraded=degraded, roots=roots, accounts=accounts)


# --- CLI -------------------------------------------------------------------------

def _delta_text(value):
    return "sin datos para comparar" if value is None else f"{value:+.1f} %".replace(".", ",")


def format_briefing(data):
    window, compare, kpis, sub = data["window"], data["compare"], data["kpis"], data["subscription"]
    lines = [f"Briefing {window['month']} ({format_day(window['from'])}–{format_day(window['to'])})"]
    if compare["coverage"] == "none":
        lines.append("Sin mes con datos para comparar")
    else:
        partial = f", cobertura parcial desde {format_day(compare['since'])}" if compare["since"] else ""
        lines.append(f"Comparado con {format_day(compare['from'])}–{format_day(compare['to'])}{partial}")
    if data.get("degraded"):
        lines.append("Historial no disponible temporalmente")
    lines += [
        "",
        f"Gasto equivalente API: {format_usd(kpis['cost']['current'])} ({_delta_text(kpis['cost']['delta_pct'])})",
        f"Tokens: {format_int(kpis['tokens']['current'])} ({_delta_text(kpis['tokens']['delta_pct'])})",
        f"Días activos: {kpis['active_days']['current']}"
        + (f" (antes: {kpis['active_days']['previous']})" if kpis["active_days"]["previous"] is not None else ""),
    ]
    if sub["configured"]:
        verdict = {"subscription": f"ahorras {format_usd(sub['savings'])}",
                   "api": f"la API saldría {format_usd(sub['savings'])} más barata",
                   "tie": "empate"}[sub["winner"]]
        lines.append(f"Suscripción: pagas {format_usd(sub['paid'])} · equivale a "
                     f"{format_usd(sub['api_equivalent'])} · {verdict}")
    else:
        lines.append("Suscripción: sin plan configurado")
    if data["top_projects"]:
        lines += ["", "Top proyectos:"]
        for i, p in enumerate(data["top_projects"], 1):
            lines.append(f"  {i}. {p['project']} ({p['client']}) {format_usd(p['cost'])} · {round(p['share'] * 100)} %")
    lines += ["", "Atención ahora:"]
    if not data["attention"]:
        lines.append("  Nada requiere tu atención ahora")
    for signal in data["attention"]:
        marker = "!" if signal["severity"] == "warning" else "i"
        lines.append(f"  [{marker}] {signal['title']}")
        lines += [f"      - {item}" for item in signal["evidence"]]
    return "\n".join(lines)
