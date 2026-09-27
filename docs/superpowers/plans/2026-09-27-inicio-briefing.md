# Subproyecto 1 — Nueva estructura + Inicio briefing · Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganizar el dashboard alrededor de preguntas del usuario (Inicio, Actividad, Gasto y ROI, Proyectos, Configuración) con un Inicio tipo briefing alimentado por un nuevo `GET /api/briefing`, y alinear la identidad visual con jrueda.dev.

**Architecture:** `briefing.py` (raíz, stdlib) lee `history.db` en una capa SQLite delgada y construye el briefing con funciones puras (ventanas, cobertura, KPIs, suscripción, top de proyectos y reglas `rule(ctx) -> Signal | None`). `server.py` solo expone la ruta. En el frontend la fuente deja de ser una ruta y pasa a ser el parámetro global `?fuente=`; cada vista vive en `src/views/` y el Inicio en `src/components/home/`.

**Tech Stack:** Python 3 stdlib (`sqlite3`, `unittest`), React 19 + TypeScript + Vite + Tailwind v4 + shadcn (base-ui) + react-router 7, vitest, Playwright (E2E temporal).

**Spec:** `docs/superpowers/specs/2026-09-27-inicio-briefing-design.md`

## Global Constraints

- Backend solo stdlib: `briefing.py`, `server.py`, `main.py` no agregan dependencias.
- OpenRouter nunca se suma a "Todas" (`source=all` excluye `daily_model`).
- `history.db`: `briefing.py` solo lee (abre en `mode=ro`); nunca poda ni escribe.
- Ningún archivo contiene rutas propias de la máquina del autor (`/home/jruedadev`, `~/DEV/JRDV`). En tests usa rutas genéricas como `/home/u/DEV/ACME/app`.
- Toda la interfaz y los textos que arma el backend están en español, con tildes correctas.
- Formato es-CO en ambos lados: dinero `$ 1.234,56` (negativo `-$ 3,00`), enteros `1.234.567`, decimales con coma (`7,9`), fechas cortas `27 sept` (abreviaturas: ene, feb, mar, abr, may, jun, jul, ago, sept, oct, nov, dic).
- "Hoy" es `date.today()` del servidor; todas las funciones puras reciben `today` como parámetro para poder testearlas.
- Correcciones medidas al §4.4 del spec (el spec permite corregir cualquier FAIL de contraste): en tema claro `--primary-foreground` es `#020817` (no `#f8fafc`, que da 2,46:1 sobre `#00b1cc`); el texto o enlace cyan usa un token aparte `--link` (`#0e7490` en claro = 5,36:1; `#00ddff` en oscuro); el cyan nunca va en marcas de datos (ΔE 12 contra el aqua de OpenCode); las variables `--viz-*` no cambian.
- Commits en español con prefijo convencional (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`), **sin** líneas `Co-Authored-By` ni `Claude-Session`. Rama de trabajo: `dev`.
- Comandos: backend `python3 -m unittest discover -s tests -v`; frontend (en `frontend/`) `npm test`, `npm run build`, `npm run lint`.

## Review Focus

1. **`?comparar=` que dejó de ser válido** (enlace viejo o mes sin datos para la fuente elegida): el backend responde 400 y el Inicio debe volver solo al mes por defecto en vez de quedarse en error. → test de `HttpError` en Task 6 y efecto en `HomeView` (Task 7).
2. **URL con codificación rota** (`/proyectos/%E0%A4%A`): no debe tumbar la app; se trata como ruta desconocida y lleva a `/`. → test en `routes.test.ts` (Task 9).
3. **Cruce de año y meses cortos**: el 31 de enero compara contra diciembre del año anterior; el 30 de marzo compara contra el 28 de febrero. → tests en Task 1.
4. **Fecha de inicio de suscripción futura o a mitad de mes** (guardada como texto en una columna REAL): `api_equivalent` solo cuenta desde esa fecha y nunca es negativo. → tests en Task 1 y Task 3.
5. **Cambiar de fuente con `?comparar=`/`?dia=` puestos**: al cambiar la fuente se limpian ambos para no pedir un mes inelegible. → test de `searchForSource` en Task 9.

---

## File Structure

**Backend (raíz)**
- Create `briefing.py`: formato es-CO, ventanas y cobertura, KPIs, suscripción, top de proyectos, `client_of`, reglas de atención, capa SQLite y `format_briefing` para la CLI.
- Modify `server.py`: ruta `GET /api/briefing` y `_send_json(..., status=200)`.
- Modify `main.py`: flag `--briefing`.
- Create `tests/test_briefing.py`, `tests/fixtures/client_of_cases.json`.
- Modify `tests/test_server.py`, `tests/test_main.py`.
- Modify `CLAUDE.md`, `README.md`.

**Frontend (`frontend/src/`)**
- Modify `index.css` (tokens de marca, fuentes, glow, gradiente, `.card-interactive`), `package.json` (fuentes, cmdk).
- Modify `lib/api.ts` (`HttpError`, tipos y `fetchBriefing`), `lib/sources.ts` (`SOURCE_KEYS`, `SourceKey`), `lib/routes.ts` (modelo nuevo de rutas), `lib/sessions.ts`, `hooks/useDashboardRoute.ts`.
- Create `lib/briefing.ts` (+ test), `hooks/useBriefing.ts`, `lib/clients.test.ts`, `lib/projects.ts` (+ test), `lib/settings.ts` (+ test), `lib/commands.ts` (+ test).
- Create `components/home/{HomeView,BriefingHeader,BriefingKpis,AttentionList,TopProjects,DailySpark}.tsx`.
- Create `components/SettingsForm.tsx`, `components/TopBar.tsx`, `components/SourceFilter.tsx`, `components/CommandPalette.tsx`, `components/ui/command.tsx` (vía shadcn CLI).
- Create `views/{ActivityView,SpendView,ProjectsView,SettingsView}.tsx`.
- Modify `App.tsx`, `components/Sidebar.tsx`, `components/RoiView.tsx`, `components/TrendChart.tsx`, `components/SessionDetail.tsx`, `components/ProjectDetailSheet.tsx`.

---

### Task 1: `briefing.py` — núcleo (formato, ventanas, cobertura, KPIs, suscripción, top, `client_of`)

**Files:**
- Create: `briefing.py`
- Create: `tests/test_briefing.py`
- Create: `tests/fixtures/client_of_cases.json`

**Interfaces:**
- Produces (usadas por Tasks 2–4): `BriefingError(ValueError)`; constantes `PROJECT_SOURCES`, `VALID_SOURCES`, `SUBSCRIPTION_KEYS`, `SOURCE_LABELS`, `SOURCE_SLUGS`; `format_usd(float) -> str`, `format_int(int) -> str`, `format_day(iso) -> str`, `format_ratio(float) -> str`; `month_of(date) -> "YYYY-MM"`, `previous_month(str) -> str`, `month_window(month, day) -> (from, to)`, `month_coverage(month, start) -> (coverage, since) | None`, `eligible_months(start, current_month) -> list[dict]`; `rows_for_source(source, project_rows, model_rows) -> list[row]`, `in_range(rows, start, end)`, `sum_cost(rows)`, `sum_tokens(rows)`, `active_dates(rows) -> list[str]`, `delta_pct(current, previous) -> float | None`, `compare_costs(api, sub) -> (winner, savings)`, `subscription_summary(source, project_rows, settings, window) -> dict`, `top_projects(rows, limit=3) -> list[dict]`, `client_of(path) -> str`, `evaluate_rules(ctx) -> list[dict]`, `build_briefing(project_rows, model_rows, settings, today, source="all", compare=None, degraded=False) -> dict`.
- Una fila (`row`) es `{"date": "YYYY-MM-DD", "source": str, "project": str | None, "tokens": int, "cost": float | None}`. `settings` es el dict de `history.ROI_SETTINGS_KEYS` (valores `None` si faltan).

- [ ] **Step 1: Crear el fixture compartido de `client_of`**

`tests/fixtures/client_of_cases.json` (lo consumen `tests/test_briefing.py` y, en Task 6, `frontend/src/lib/clients.test.ts`):

```json
[
  {"path": "/home/u/DEV/JRDV/ai-monitor", "client": "JRDV"},
  {"path": "/home/u/dev/Acme/app", "client": "Acme"},
  {"path": "/home/u/Dev/Mixto/x", "client": "Mixto"},
  {"path": "/srv/DEV/A/DEV/B/app", "client": "A"},
  {"path": "/home/u/DEV", "client": "Otros"},
  {"path": "/home/u/projects/app", "client": "Otros"},
  {"path": "", "client": "Otros"}
]
```

- [ ] **Step 2: Escribir los tests que fallan**

`tests/test_briefing.py`:

```python
import json
import os
import unittest
from datetime import date

import briefing
import history

TODAY = date(2026, 9, 27)
APP = "/home/u/DEV/ACME/app"
NO_SETTINGS = {key: None for key in history.ROI_SETTINGS_KEYS}


def row(day, source="claude_code", project=APP, tokens=100, cost=1.0):
    return {"date": day, "source": source, "project": project, "tokens": tokens, "cost": cost}


def settings(**overrides):
    return {**NO_SETTINGS, **overrides}


def build(project_rows=(), model_rows=(), today=TODAY, source="all", compare=None, cfg=None):
    return briefing.build_briefing(
        list(project_rows), list(model_rows), cfg or NO_SETTINGS, today, source=source, compare=compare,
    )


class TestFormat(unittest.TestCase):
    def test_usd_matches_es_co(self):
        self.assertEqual(briefing.format_usd(1234.5), "$ 1.234,50")
        self.assertEqual(briefing.format_usd(-3), "-$ 3,00")
        self.assertEqual(briefing.format_usd(0.004), "$ 0,00")

    def test_int_ratio_and_day(self):
        self.assertEqual(briefing.format_int(953620952), "953.620.952")
        self.assertEqual(briefing.format_ratio(7.94), "7,9")
        self.assertEqual(briefing.format_day("2026-09-27"), "27 sept")
        self.assertEqual(briefing.format_day("2026-01-05"), "5 ene")


class TestWindows(unittest.TestCase):
    def test_month_window_clips_to_short_month(self):
        self.assertEqual(briefing.month_window("2026-02", 31), ("2026-02-01", "2026-02-28"))
        self.assertEqual(briefing.month_window("2028-02", 30), ("2028-02-01", "2028-02-29"))
        self.assertEqual(briefing.month_window("2026-09", 27), ("2026-09-01", "2026-09-27"))

    def test_previous_month_crosses_year(self):
        self.assertEqual(briefing.previous_month("2026-01"), "2025-12")
        self.assertEqual(briefing.previous_month("2026-10"), "2026-09")

    def test_month_coverage(self):
        self.assertEqual(briefing.month_coverage("2026-08", "2026-07-18"), ("full", None))
        self.assertEqual(briefing.month_coverage("2026-07", "2026-07-01"), ("full", None))
        self.assertEqual(briefing.month_coverage("2026-07", "2026-07-18"), ("partial", "2026-07-18"))
        self.assertIsNone(briefing.month_coverage("2026-06", "2026-07-18"))
        self.assertIsNone(briefing.month_coverage("2026-06", None))

    def test_eligible_months_descending_until_start(self):
        self.assertEqual(briefing.eligible_months("2026-07-18", "2026-09"), [
            {"month": "2026-08", "coverage": "full", "since": None},
            {"month": "2026-07", "coverage": "partial", "since": "2026-07-18"},
        ])
        self.assertEqual(briefing.eligible_months("2026-09-03", "2026-09"), [])
        self.assertEqual(briefing.eligible_months(None, "2026-09"), [])


class TestKpis(unittest.TestCase):
    def test_equivalent_window_against_previous_month(self):
        data = build([
            row("2026-08-27", cost=10, tokens=1000),
            row("2026-08-28", cost=99, tokens=9999),  # fuera del tramo equivalente
            row("2026-09-27", cost=5, tokens=500),
        ])
        self.assertEqual(data["window"], {"month": "2026-09", "from": "2026-09-01", "to": "2026-09-27"})
        self.assertEqual(data["compare"], {"month": "2026-08", "from": "2026-08-01", "to": "2026-08-27",
                                           "coverage": "full", "since": None})
        self.assertEqual(data["kpis"]["cost"], {"current": 5.0, "previous": 10.0, "delta_pct": -50.0})
        self.assertEqual(data["kpis"]["tokens"], {"current": 500, "previous": 1000, "delta_pct": -50.0})
        self.assertEqual(data["kpis"]["active_days"], {"current": 1, "previous": 1})
        self.assertFalse(data["kpis"]["cost_incomplete"])
        self.assertFalse(data["degraded"])

    def test_january_compares_against_december_of_previous_year(self):
        data = build([row("2025-12-31", cost=4), row("2026-01-31", cost=2)], today=date(2026, 1, 31))
        self.assertEqual(data["compare"]["month"], "2025-12")
        self.assertEqual(data["compare"]["to"], "2025-12-31")
        self.assertEqual(data["kpis"]["cost"]["previous"], 4.0)

    def test_march_30_compares_against_february_28(self):
        data = build([row("2026-02-10"), row("2026-03-30")], today=date(2026, 3, 30))
        self.assertEqual(data["compare"]["to"], "2026-02-28")

    def test_delta_is_null_when_previous_is_zero(self):
        data = build([row("2026-07-01", cost=3), row("2026-09-02", cost=2)])
        self.assertEqual(data["kpis"]["cost"]["previous"], 0.0)
        self.assertIsNone(data["kpis"]["cost"]["delta_pct"])

    def test_default_compare_without_data_is_coverage_none(self):
        data = build([row("2026-09-02")])
        self.assertEqual(data["compare"]["coverage"], "none")
        self.assertIsNone(data["compare"]["since"])
        self.assertIsNone(data["kpis"]["cost"]["previous"])
        self.assertIsNone(data["kpis"]["cost"]["delta_pct"])
        self.assertIsNone(data["kpis"]["active_days"]["previous"])
        self.assertEqual(data["eligible_months"], [])

    def test_explicit_compare_partial_month_is_marked(self):
        data = build([row("2026-07-18", cost=8), row("2026-09-02")], compare="2026-07")
        self.assertEqual(data["compare"]["coverage"], "partial")
        self.assertEqual(data["compare"]["since"], "2026-07-18")
        self.assertEqual(data["kpis"]["cost"]["previous"], 8.0)

    def test_invalid_parameters_raise_briefing_error(self):
        rows = [row("2026-07-18"), row("2026-09-02")]
        with self.assertRaises(briefing.BriefingError):
            build(rows, compare="2026-05")  # anterior al inicio de datos
        with self.assertRaises(briefing.BriefingError):
            build(rows, compare="2026-09")  # el mes actual no es comparable
        with self.assertRaises(briefing.BriefingError):
            build(rows, compare="2026-13")
        with self.assertRaises(briefing.BriefingError):
            build(rows, source="copilot")

    def test_null_cost_sums_zero_and_flags_incomplete(self):
        data = build([row("2026-09-01", cost=None), row("2026-09-02", cost=2)])
        self.assertEqual(data["kpis"]["cost"]["current"], 2.0)
        self.assertTrue(data["kpis"]["cost_incomplete"])

    def test_all_excludes_openrouter_and_openrouter_branch_uses_daily_model(self):
        model_rows = [{"date": "2026-09-03", "model": "__all__", "tokens": 70, "cost": 50.0},
                      {"date": "2026-09-03", "model": "gpt-x", "tokens": 1, "cost": 999.0}]
        all_data = build([row("2026-09-03", cost=1)], model_rows)
        self.assertEqual(all_data["kpis"]["cost"]["current"], 1.0)
        or_data = build([row("2026-09-03", cost=1)], model_rows, source="openrouter")
        self.assertEqual(or_data["kpis"]["cost"]["current"], 50.0)
        self.assertEqual(or_data["kpis"]["tokens"]["current"], 70)
        self.assertEqual(or_data["top_projects"], [])
        self.assertEqual(or_data["subscription"]["configured"], False)

    def test_single_source_filter(self):
        data = build([row("2026-09-03", cost=1), row("2026-09-03", source="codex", cost=7)], source="codex")
        self.assertEqual(data["source"], "codex")
        self.assertEqual(data["kpis"]["cost"]["current"], 7.0)


class TestSubscription(unittest.TestCase):
    def test_compare_costs_matches_roi_ts_rounding(self):
        self.assertEqual(briefing.compare_costs(657.10, 20.0), ("subscription", 637.1))
        self.assertEqual(briefing.compare_costs(5.0, 20.0), ("api", 15.0))
        self.assertEqual(briefing.compare_costs(20.004, 20.0), ("tie", 0.0))
        self.assertEqual(briefing.compare_costs(19.995, 20.0), ("tie", 0.0))  # Math.round(-0.5) = -0

    def test_not_configured_returns_nulls(self):
        data = build([row("2026-09-03")])
        self.assertEqual(data["subscription"], {"configured": False, "paid": None, "api_equivalent": None,
                                                "winner": None, "savings": None})

    def test_configured_subscription_wins(self):
        data = build([row("2026-09-03", cost=657.10)], cfg=settings(subscription_cost_claude=20.0))
        self.assertEqual(data["subscription"], {"configured": True, "paid": 20.0, "api_equivalent": 657.1,
                                                "winner": "subscription", "savings": 637.1})

    def test_only_configured_sources_count_toward_api_equivalent(self):
        rows = [row("2026-09-03", cost=30), row("2026-09-03", source="codex", cost=500)]
        data = build(rows, cfg=settings(subscription_cost_claude=20.0))
        self.assertEqual(data["subscription"]["api_equivalent"], 30.0)
        self.assertEqual(data["subscription"]["paid"], 20.0)

    def test_start_inside_month_counts_from_start(self):
        rows = [row("2026-09-10", cost=100), row("2026-09-20", cost=30)]
        data = build(rows, cfg=settings(subscription_cost_claude=20.0, subscription_start_claude="2026-09-15"))
        self.assertEqual(data["subscription"]["api_equivalent"], 30.0)

    def test_future_start_counts_nothing_and_never_negative(self):
        data = build([row("2026-09-10", cost=100)],
                     cfg=settings(subscription_cost_claude=20.0, subscription_start_claude="2026-10-05"))
        self.assertEqual(data["subscription"]["api_equivalent"], 0.0)
        self.assertEqual(data["subscription"]["winner"], "api")
        self.assertEqual(data["subscription"]["savings"], 20.0)

    def test_source_without_possible_subscription(self):
        data = build([row("2026-09-03", source="opencode")], source="opencode",
                     cfg=settings(subscription_cost_claude=20.0))
        self.assertFalse(data["subscription"]["configured"])


class TestTopProjects(unittest.TestCase):
    def test_top_three_by_cost_with_share_and_client(self):
        rows = [
            row("2026-09-03", project="/home/u/DEV/ACME/a", cost=50),
            row("2026-09-04", project="/home/u/DEV/ACME/a", cost=10),
            row("2026-09-03", project="/home/u/DEV/BETA/b", cost=30),
            row("2026-09-03", project="/home/u/tmp/c", cost=15),
            row("2026-09-03", project="/home/u/DEV/BETA/d", cost=5),
        ]
        top = build(rows)["top_projects"]
        self.assertEqual([p["project"] for p in top], ["/home/u/DEV/ACME/a", "/home/u/DEV/BETA/b", "/home/u/tmp/c"])
        self.assertEqual(top[0], {"project": "/home/u/DEV/ACME/a", "client": "ACME", "cost": 60.0, "share": 0.6})
        self.assertEqual(top[2]["client"], "Otros")


class TestClientOfParity(unittest.TestCase):
    def test_same_cases_as_clients_ts(self):
        path = os.path.join(os.path.dirname(__file__), "fixtures", "client_of_cases.json")
        with open(path) as f:
            cases = json.load(f)
        for case in cases:
            with self.subTest(path=case["path"]):
                self.assertEqual(briefing.client_of(case["path"]), case["client"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Verificar que fallan**

Run: `python3 -m unittest tests.test_briefing -v`
Expected: FAIL/ERROR con `ModuleNotFoundError: No module named 'briefing'`.

- [ ] **Step 4: Implementar el núcleo**

`briefing.py` (en Task 2 se agregan las reglas debajo de `evaluate_rules`; aquí `RULES` queda vacío):

```python
"""Briefing del Inicio: el mes en curso contra un mes comparable y las señales
de "Atención ahora". No es un collector: solo lee history.db y nunca toca a los
proveedores. Lógica en funciones puras sobre filas; SQLite en una capa delgada.
Spec: docs/superpowers/specs/2026-09-27-inicio-briefing-design.md
"""
import calendar
import math
import re
from datetime import date, timedelta
from urllib.parse import quote

PROJECT_SOURCES = ("claude_code", "codex", "opencode", "hermes")
VALID_SOURCES = ("all",) + PROJECT_SOURCES + ("openrouter",)
# Fuentes con suscripción posible → (clave de costo, clave de fecha de inicio) en roi_settings.
SUBSCRIPTION_KEYS = {
    "claude_code": ("subscription_cost_claude", "subscription_start_claude"),
    "codex": ("subscription_cost_codex", "subscription_start_codex"),
}
SOURCE_LABELS = {"claude_code": "Claude Code", "codex": "Codex", "opencode": "OpenCode",
                 "hermes": "Hermes", "openrouter": "OpenRouter"}
SOURCE_SLUGS = {"claude_code": "claude-code", "codex": "codex", "opencode": "opencode",
                "hermes": "hermes", "openrouter": "openrouter"}

_MONTHS_SHORT = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic")
_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


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

def rows_for_source(source, project_rows, model_rows):
    if source == "openrouter":
        return [{"date": r["date"][:10], "source": "openrouter", "project": None,
                 "tokens": r["tokens"] or 0, "cost": r["cost"]}
                for r in model_rows if r["model"] == "__all__"]
    if source == "all":
        return [r for r in project_rows if r["source"] in PROJECT_SOURCES]
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


def _subscription_candidates(source):
    if source == "all":
        return list(SUBSCRIPTION_KEYS)
    return [source] if source in SUBSCRIPTION_KEYS else []


def subscription_summary(source, project_rows, settings, window):
    configured = [s for s in _subscription_candidates(source)
                  if settings.get(SUBSCRIPTION_KEYS[s][0]) is not None]
    if not configured:
        return {"configured": False, "paid": None, "api_equivalent": None, "winner": None, "savings": None}
    paid = sum(float(settings[SUBSCRIPTION_KEYS[s][0]]) for s in configured)
    api = 0.0
    for s in configured:
        start = settings.get(SUBSCRIPTION_KEYS[s][1])
        lower = max(window[0], str(start)[:10]) if start else window[0]
        api += sum_cost(in_range([r for r in project_rows if r["source"] == s], lower, window[1]))
    winner, savings = compare_costs(api, paid)
    return {"configured": True, "paid": round(paid, 2), "api_equivalent": round(api, 2),
            "winner": winner, "savings": round(savings, 2)}


# --- Proyectos -----------------------------------------------------------------

def client_of(path):
    """Port de clientOf (frontend/src/lib/clients.ts): segmento tras "DEV" o "Otros"."""
    segments = path.split("/")
    for idx, segment in enumerate(segments):
        if segment.upper() == "DEV":
            return segments[idx + 1] if idx + 1 < len(segments) else "Otros"
    return "Otros"


def _project_costs(rows):
    costs = {}
    for r in rows:
        if r["project"] is not None:
            costs[r["project"]] = costs.get(r["project"], 0.0) + (r["cost"] or 0)
    return costs


def top_projects(rows, limit=3):
    costs = _project_costs(rows)
    total = sum(costs.values())
    ranked = sorted(costs.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    return [{"project": p, "client": client_of(p), "cost": round(c, 2),
             "share": round(c / total, 3) if total > 0 else 0.0} for p, c in ranked]


# --- Reglas de "Atención ahora" (Task 2) ---------------------------------------

RULES = ()
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

def build_briefing(project_rows, model_rows, settings, today, source="all", compare=None, degraded=False):
    if source not in VALID_SOURCES:
        raise BriefingError(f"Fuente desconocida: {source}")
    if compare is not None and not _MONTH_RE.match(compare):
        raise BriefingError("El parámetro compare debe tener el formato YYYY-MM")

    current = month_of(today)
    rows = rows_for_source(source, project_rows, model_rows)
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

    window = month_window(current, today.day)
    compare_window = month_window(compare_month, today.day)
    window_rows = in_range(rows, *window)
    compare_rows = in_range(rows, *compare_window) if entry else []

    cost_now, cost_prev = sum_cost(window_rows), (sum_cost(compare_rows) if entry else None)
    tokens_now, tokens_prev = sum_tokens(window_rows), (sum_tokens(compare_rows) if entry else None)

    ctx = {"source": source, "today": today, "window": window, "rows": rows, "window_rows": window_rows,
           "project_rows": project_rows, "model_rows": model_rows, "settings": settings}

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
        "subscription": (subscription_summary(source, project_rows, settings, window)
                         if source != "openrouter" else subscription_summary("openrouter", [], settings, window)),
        "top_projects": top_projects(window_rows),
        "attention": evaluate_rules(ctx),
        "degraded": degraded,
    }
```

Nota: `quote` y `timedelta` se importan ya porque Task 2 los usa; si `python3 -m pyflakes` no está disponible, no importa, pero no los quites.

- [ ] **Step 5: Verificar que pasan**

Run: `python3 -m unittest tests.test_briefing -v`
Expected: todos PASS.

- [ ] **Step 6: Suite completa y commit**

Run: `python3 -m unittest discover -s tests -v` → todo PASS.

```bash
git add briefing.py tests/test_briefing.py tests/fixtures/client_of_cases.json
git commit -m "feat(briefing): núcleo del briefing con ventanas, cobertura, KPIs, suscripción y top de proyectos"
```

---

### Task 2: `briefing.py` — reglas de "Atención ahora"

**Files:**
- Modify: `briefing.py` (sección "Reglas")
- Test: `tests/test_briefing.py` (nueva clase `TestRules`)

**Interfaces:**
- Consumes: todo lo de Task 1 (`ctx` con claves `source, today, window, rows, window_rows, project_rows, model_rows, settings`).
- Produces: `rule_spike_day`, `rule_project_concentration`, `rule_cost_incomplete`, `rule_subscription_missing`, `rule_habitual_source_silent` (`ctx -> dict | None`), y `RULES` con ese orden. Cada señal es `{"id", "severity": "warning"|"info", "title", "evidence": [str], "link"}`.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `tests/test_briefing.py` (antes del `if __name__`):

```python
def ids(data):
    return [signal["id"] for signal in data["attention"]]


def daily(first, last, **kwargs):
    """Una fila por día entre dos fechas ISO, ambas inclusive."""
    from datetime import timedelta
    start, end = date.fromisoformat(first), date.fromisoformat(last)
    out = []
    while start <= end:
        out.append(row(start.isoformat(), **kwargs))
        start += timedelta(days=1)
    return out


class TestRules(unittest.TestCase):
    def test_spike_day_fires_against_active_day_average(self):
        rows = daily("2026-09-01", "2026-09-04", cost=10) + [row("2026-09-27", cost=100)]
        data = build(rows, cfg=settings(subscription_cost_claude=20.0))
        spike = data["attention"][0]
        self.assertEqual(spike["id"], "spike_day")
        self.assertEqual(spike["severity"], "warning")
        self.assertEqual(spike["title"], "Hoy llevas $ 100,00 — 3,6× tu promedio diario")
        self.assertEqual(spike["evidence"], ["2026-09-27: $ 100,00", "Promedio de días activos del mes: $ 28,00"])
        self.assertEqual(spike["link"], "/actividad?dia=2026-09-27")

    def test_spike_day_on_a_past_day_names_the_day(self):
        rows = daily("2026-09-01", "2026-09-04", cost=10) + [row("2026-09-12", cost=100)]
        spike = build(rows)["attention"][0]
        self.assertTrue(spike["title"].startswith("El 12 sept gastaste $ 100,00"))

    def test_spike_day_needs_five_active_days(self):
        rows = daily("2026-09-01", "2026-09-03", cost=10) + [row("2026-09-27", cost=100)]
        self.assertNotIn("spike_day", ids(build(rows)))

    def test_spike_day_is_measured_within_the_source_filter(self):
        rows = (daily("2026-09-01", "2026-09-06", source="codex", project="/home/u/DEV/X/c", cost=5)
                + daily("2026-09-01", "2026-09-04", cost=10) + [row("2026-09-27", cost=500)])
        self.assertNotIn("spike_day", ids(build(rows, source="codex")))
        self.assertIn("spike_day", ids(build(rows, source="claude_code")))

    def test_project_concentration(self):
        rows = [row("2026-09-02", project="/home/u/DEV/ACME/app", cost=60),
                row("2026-09-02", project="/home/u/DEV/ACME/web", cost=40)]
        data = build(rows, cfg=settings(subscription_cost_claude=20.0))
        signal = next(s for s in data["attention"] if s["id"] == "project_concentration")
        self.assertEqual(signal["severity"], "info")
        self.assertEqual(signal["title"], "app concentra el 60 % del gasto del mes")
        self.assertEqual(signal["evidence"], ["/home/u/DEV/ACME/app: $ 60,00 de $ 100,00"])
        self.assertEqual(signal["link"], "/proyectos/ACME?proyecto=%2Fhome%2Fu%2FDEV%2FACME%2Fapp")

    def test_project_concentration_needs_more_than_half(self):
        rows = [row("2026-09-02", project="/home/u/DEV/ACME/app", cost=50),
                row("2026-09-02", project="/home/u/DEV/ACME/web", cost=50)]
        self.assertNotIn("project_concentration", ids(build(rows)))

    def test_cost_incomplete_signal(self):
        data = build([row("2026-09-02", cost=None), row("2026-09-03", project="/home/u/DEV/B/x", cost=1),
                      row("2026-09-03", project="/home/u/DEV/C/y", cost=1)])
        signal = next(s for s in data["attention"] if s["id"] == "cost_incomplete")
        self.assertEqual(signal["evidence"][0], "Días afectados: 2 sept")
        self.assertEqual(signal["link"], "/gasto")

    def test_subscription_missing_after_three_active_days(self):
        self.assertIn("subscription_missing", ids(build(daily("2026-09-01", "2026-09-03"))))
        self.assertNotIn("subscription_missing", ids(build(daily("2026-09-01", "2026-09-02"))))
        self.assertNotIn("subscription_missing",
                         ids(build(daily("2026-09-01", "2026-09-03"), cfg=settings(subscription_cost_claude=20.0))))
        self.assertNotIn("subscription_missing", ids(build(
            daily("2026-09-01", "2026-09-03", source="hermes"), source="hermes")))

    def test_habitual_source_silent_fires(self):
        rows = daily("2026-08-20", "2026-09-18")  # 30 días seguidos, luego 9 días sin datos
        data = build(rows, cfg=settings(subscription_cost_claude=20.0))
        signal = next(s for s in data["attention"] if s["id"] == "habitual_source_silent")
        self.assertEqual(signal["severity"], "warning")
        self.assertEqual(signal["title"], "Claude Code lleva 9 días sin datos")
        self.assertEqual(signal["link"], "/gasto?fuente=claude-code")

    def test_sporadic_source_never_fires_silent(self):
        rows = daily("2026-08-20", "2026-09-27") + [row("2026-09-12", source="codex", project="/home/u/DEV/X/c")]
        self.assertNotIn("habitual_source_silent", ids(build(rows, cfg=settings(subscription_cost_claude=20.0))))

    def test_silence_threshold_scales_with_typical_interval(self):
        every_other = [r for i, r in enumerate(daily("2026-08-22", "2026-09-20")) if i % 2 == 0]  # 15 días, intervalo 2
        # último día activo 2026-09-19; umbral max(3, 3×2) = 6
        not_yet = build(every_other, today=date(2026, 9, 25), cfg=settings(subscription_cost_claude=20.0))
        self.assertNotIn("habitual_source_silent", ids(not_yet))
        silent = build(every_other, today=date(2026, 9, 26), cfg=settings(subscription_cost_claude=20.0))
        self.assertIn("habitual_source_silent", ids(silent))

    def test_ordering_by_severity_and_max_three(self):
        rows = (daily("2026-08-10", "2026-09-08", cost=1)  # Claude habitual, en silencio desde el 8
                + [row("2026-09-05", project="/home/u/DEV/ACME/otro", cost=None),
                   row("2026-09-20", source="codex", project="/home/u/DEV/BIG/app", cost=100)])
        data = build(rows)
        self.assertEqual(ids(data), ["spike_day", "habitual_source_silent", "project_concentration"])

    def test_no_rows_no_signals(self):
        self.assertEqual(build([])["attention"], [])
```

- [ ] **Step 2: Verificar que fallan**

Run: `python3 -m unittest tests.test_briefing.TestRules -v`
Expected: FAIL (listas `attention` vacías, `StopIteration`).

- [ ] **Step 3: Implementar las reglas**

En `briefing.py`, reemplazar el bloque `RULES = ()` de la sección "Reglas" por:

```python
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
        "link": f"/proyectos/{quote(client_of(project), safe='')}?proyecto={quote(project, safe='')}",
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
    for source in _subscription_candidates(ctx["source"]):
        if ctx["settings"].get(SUBSCRIPTION_KEYS[source][0]) is not None:
            continue
        rows = in_range([r for r in ctx["project_rows"] if r["source"] == source], *ctx["window"])
        days = len(active_dates(rows))
        if days >= SUBSCRIPTION_MIN_ACTIVE_DAYS:
            missing.append((source, days))
    if not missing:
        return None
    labels = " y ".join(SOURCE_LABELS[source] for source, _ in missing)
    return {
        "id": "subscription_missing", "severity": "info",
        "title": f"Configura tu plan de {labels} para comparar suscripción y API",
        "evidence": [f"{SOURCE_LABELS[source]}: {days} días activos este mes, sin plan configurado"
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
            "title": f"{SOURCE_LABELS[source]} lleva {silent} días sin datos",
            "evidence": [f"Último día con actividad: {format_day(last.isoformat())}",
                         f"Activa {active} de los {HABITUAL_WINDOW_DAYS} días previos; "
                         f"se avisa después de {threshold} días sin datos"],
            "link": f"/gasto?fuente={SOURCE_SLUGS[source]}",
        }
    return None


RULES = (rule_spike_day, rule_project_concentration, rule_cost_incomplete,
         rule_subscription_missing, rule_habitual_source_silent)
```

Dejar `MAX_SIGNALS`, `_SEVERITY_ORDER` y `evaluate_rules` como están (debajo de `RULES`).

- [ ] **Step 4: Verificar que pasan**

Run: `python3 -m unittest tests.test_briefing -v`
Expected: todo PASS. Si `test_ordering_by_severity_and_max_three` falla, imprime `data["attention"]` y revisa la cuenta (promedio = 108/9 = 12; 100 > 30 dispara el pico).

- [ ] **Step 5: Commit**

```bash
git add briefing.py tests/test_briefing.py
git commit -m "feat(briefing): reglas de Atención ahora con línea base por fuente"
```

---

### Task 3: `briefing.py` — capa SQLite y degradación

**Files:**
- Modify: `briefing.py` (agregar imports `logging`, `os`, `sqlite3`, `pathlib.Path`, `history`; funciones `load` y `get_briefing`)
- Test: `tests/test_briefing.py` (clase `TestSqlite`)

**Interfaces:**
- Consumes: `build_briefing`, `BriefingError`, `VALID_SOURCES`; `history.ROI_SETTINGS_KEYS`, `history.DB_PATH_DEFAULT`, `history.ensure_schema`, `history.save_roi_settings`.
- Produces: `load(db_path) -> (project_rows, model_rows, settings)` (deja pasar `sqlite3.Error`); `get_briefing(db_path=None, source="all", compare=None, today=None) -> dict` (nunca lanza por errores de SQLite; sí lanza `BriefingError`).

- [ ] **Step 1: Tests que fallan**

Agregar a `tests/test_briefing.py` (imports arriba: `import sqlite3`, `import tempfile`):

```python
class TestSqlite(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = os.path.join(self.dir, "history.db")

    def _insert(self, project_rows=(), model_rows=()):
        history.ensure_schema(self.db)
        con = sqlite3.connect(self.db)
        con.executemany("INSERT INTO daily_project (date, source, project, tokens, cost) VALUES (?, ?, ?, ?, ?)",
                        project_rows)
        con.executemany("INSERT INTO daily_model (date, model, tokens, cost) VALUES (?, ?, ?, ?)", model_rows)
        con.commit()
        con.close()

    def test_missing_db_returns_empty_response_without_creating_file(self):
        data = briefing.get_briefing(db_path=self.db, today=TODAY)
        self.assertFalse(os.path.exists(self.db))
        self.assertFalse(data["degraded"])
        self.assertEqual(data["kpis"]["cost"], {"current": 0, "previous": None, "delta_pct": None})
        self.assertEqual(data["eligible_months"], [])
        self.assertEqual(data["attention"], [])
        self.assertFalse(data["subscription"]["configured"])

    def test_file_without_tables_is_empty_not_degraded(self):
        open(self.db, "w").close()
        data = briefing.get_briefing(db_path=self.db, today=TODAY)
        self.assertFalse(data["degraded"])
        self.assertEqual(data["attention"], [])

    def test_empty_schema_keeps_configured_subscription(self):
        history.ensure_schema(self.db)
        history.save_roi_settings({"subscription_cost_claude": 20.0}, db_path=self.db)
        data = briefing.get_briefing(db_path=self.db, today=TODAY)
        self.assertTrue(data["subscription"]["configured"])
        self.assertEqual(data["subscription"]["api_equivalent"], 0.0)

    def test_corrupt_db_is_degraded(self):
        with open(self.db, "wb") as f:
            f.write(b"esto no es una base sqlite" * 200)
        data = briefing.get_briefing(db_path=self.db, today=TODAY, compare="2026-08")
        self.assertTrue(data["degraded"])
        self.assertEqual(data["attention"], [])
        self.assertEqual(data["kpis"]["cost"]["current"], 0)

    def test_reads_rows_models_and_text_start_date(self):
        self._insert(
            [("2026-08-27", "claude_code", APP, 10, 4.0), ("2026-09-20", "claude_code", APP, 10, 6.0),
             ("2026-09-10", "claude_code", APP, 10, 100.0)],
            [("2026-09-03", "__all__", 70, 50.0)],
        )
        history.save_roi_settings({"subscription_cost_claude": 20.0, "subscription_start_claude": "2026-09-15"},
                                  db_path=self.db)
        data = briefing.get_briefing(db_path=self.db, today=TODAY)
        self.assertEqual(data["kpis"]["cost"]["current"], 106.0)
        self.assertEqual(data["kpis"]["cost"]["previous"], 4.0)
        self.assertEqual(data["subscription"]["api_equivalent"], 6.0)
        self.assertEqual(briefing.get_briefing(db_path=self.db, today=TODAY, source="openrouter")
                         ["kpis"]["cost"]["current"], 50.0)

    def test_invalid_source_raises_even_without_db(self):
        with self.assertRaises(briefing.BriefingError):
            briefing.get_briefing(db_path=self.db, source="nope", today=TODAY)

    def test_format_briefing_for_cli(self):
        self._insert([("2026-08-27", "claude_code", APP, 1000, 10.0), ("2026-09-27", "claude_code", APP, 500, 5.0)])
        text = briefing.format_briefing(briefing.get_briefing(db_path=self.db, today=TODAY))
        self.assertIn("Gasto equivalente API: $ 5,00 (-50,0 %)", text)
        self.assertIn("Tokens: 500 (-50,0 %)", text)
        self.assertIn("Días activos: 1 (antes: 1)", text)
        self.assertIn("Atención ahora", text)
```

- [ ] **Step 2: Verificar que fallan**

Run: `python3 -m unittest tests.test_briefing.TestSqlite -v`
Expected: ERROR `AttributeError: module 'briefing' has no attribute 'get_briefing'`.

- [ ] **Step 3: Implementar**

Imports al inicio de `briefing.py` (junto a los existentes):

```python
import logging
import os
import sqlite3
from pathlib import Path

import history

log = logging.getLogger(__name__)
```

Al final del archivo:

```python
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
    con = sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)
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


def get_briefing(db_path=None, source="all", compare=None, today=None):
    db_path = db_path or history.DB_PATH_DEFAULT
    today = today or date.today()
    if source not in VALID_SOURCES:
        raise BriefingError(f"Fuente desconocida: {source}")
    try:
        project_rows, model_rows, settings = load(db_path)
        degraded = False
    except sqlite3.Error as exc:
        log.warning("briefing: no se pudo leer %s: %s", db_path, exc)
        project_rows, model_rows, settings = [], [], _empty_settings()
        degraded = True
    return build_briefing(project_rows, model_rows, settings, today,
                          source=source, compare=compare, degraded=degraded)


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
```

- [ ] **Step 4: Verificar que pasan**

Run: `python3 -m unittest tests.test_briefing -v` → todo PASS.

- [ ] **Step 5: Commit**

```bash
git add briefing.py tests/test_briefing.py
git commit -m "feat(briefing): lectura de history.db en solo lectura con degradación y formato para CLI"
```

---

### Task 4: `GET /api/briefing` y `main.py --briefing`

**Files:**
- Modify: `server.py` (import `briefing`, ruta, `_send_json(body, status=200)`)
- Modify: `main.py` (flag `--briefing`)
- Modify: `tests/test_server.py`, `tests/test_main.py`
- Modify: `CLAUDE.md` (bullet de `briefing.py` en Architecture y comando en Commands), `README.md` (sección corta "Briefing")

**Interfaces:**
- Consumes: `briefing.get_briefing(db_path, source, compare)`, `briefing.BriefingError`, `briefing.format_briefing(data)`.
- Produces: `GET /api/briefing?source=&compare=` → 200 con el JSON del spec §3.2 más `degraded: bool`; 400 con `{"error": "<mensaje>"}` si `source` o `compare` son inválidos.

- [ ] **Step 1: Tests que fallan**

En `tests/test_server.py`, dentro de `TestServerAPI` (agregar `import urllib.error` si falta; ya está):

```python
    def test_api_briefing_returns_empty_briefing_without_history(self):
        status, body = self._get("/api/briefing")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["source"], "all")
        self.assertEqual(data["attention"], [])
        self.assertEqual(data["eligible_months"], [])
        self.assertIn("kpis", data)
        self.assertFalse(data["degraded"])

    def test_api_briefing_openrouter_source(self):
        status, body = self._get("/api/briefing?source=openrouter")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["source"], "openrouter")

    def test_api_briefing_invalid_compare_is_400_with_message(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._get("/api/briefing?compare=1999-01")
        self.assertEqual(ctx.exception.code, 400)
        self.assertIn("1999-01", json.loads(ctx.exception.read())["error"])

    def test_api_briefing_invalid_source_is_400(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._get("/api/briefing?source=copilot")
        self.assertEqual(ctx.exception.code, 400)
```

En `tests/test_main.py` (nueva clase; `import io` y `from contextlib import redirect_stdout` arriba):

```python
class TestBriefingFlag(unittest.TestCase):
    def test_briefing_flag_collects_then_prints_summary(self):
        fake = {"claude_code": {}, "codex": {}, "opencode": {}, "hermes": {},
                "openrouter": {"unavailable": True, "reason": "x"}}
        out = io.StringIO()
        with patch("sys.argv", ["main.py", "--briefing"]), \
             patch("main.collect_all", return_value=fake) as collect, \
             patch("main.briefing.get_briefing", return_value={"stub": True}) as get, \
             patch("main.briefing.format_briefing", return_value="RESUMEN") as fmt, \
             redirect_stdout(out):
            import main as main_module
            main_module.main()
        collect.assert_called_once()
        get.assert_called_once_with()
        fmt.assert_called_once_with({"stub": True})
        self.assertEqual(out.getvalue().strip(), "RESUMEN")
```

- [ ] **Step 2: Verificar que fallan**

Run: `python3 -m unittest tests.test_server tests.test_main -v`
Expected: los nuevos tests fallan (la ruta cae en estáticos y devuelve el `index.html` de fallback; `main.briefing` no existe).

- [ ] **Step 3: Implementar**

`server.py`: agregar `import briefing` junto a `import history` y, en `do_GET`, antes del `elif parsed.path == "/api/roi-settings":`:

```python
            elif parsed.path == "/api/briefing":
                qs = parse_qs(parsed.query)
                try:
                    data = briefing.get_briefing(
                        db_path=db_path,
                        source=qs.get("source", ["all"])[0],
                        compare=qs.get("compare", [None])[0],
                    )
                except briefing.BriefingError as exc:
                    self._send_json(json.dumps({"error": str(exc)}), status=400)
                    return
                self._send_json(json.dumps(data))
```

Y cambiar `_send_json`:

```python
        def _send_json(self, body, status=200):
            encoded = body.encode("utf-8")
            self.send_response(status)
```

(el resto del método igual).

`main.py`: `import briefing` junto a `import history`; en el docstring agregar `  main.py --briefing   -> briefing del mes (KPIs, comparación y señales)`; en `main()`:

```python
    ap.add_argument("--briefing", action="store_true")
    args = ap.parse_args()

    sources = collect_all()
    if args.briefing:
        print(briefing.format_briefing(briefing.get_briefing()))
        return
    combined = combine_projects(...)  # línea existente, sin cambios
```

`CLAUDE.md`: en Commands agregar `python3 main.py --briefing          # briefing del mes: KPIs vs mes comparable y señales de atención`; en Architecture, después del bullet de `history.py`:

```markdown
- **`briefing.py`** alimenta el Inicio (`GET /api/briefing`) y `main.py --briefing`. No es un collector: abre `history.db` en solo lectura (`mode=ro`), nunca lo crea ni lo modifica, y construye todo con funciones puras sobre filas (ventana equivalente del mes contra un mes comparable, cobertura `full`/`partial`, suscripción frente a API con el mismo redondeo que `compareCosts` en `frontend/src/lib/roi.ts`, `client_of` portado de `lib/clients.ts` con casos compartidos en `tests/fixtures/client_of_cases.json`). Las señales de "Atención ahora" son funciones `rule(ctx) -> dict | None` en `RULES`, medidas siempre contra la línea base de la propia fuente; son la semilla del futuro motor de recomendaciones. Un `sqlite3.Error` devuelve una respuesta vacía con `degraded: true`, nunca un 500.
```

`README.md`: agregar debajo de la sección de uso de la CLI:

```markdown
### Briefing

`python3 main.py --briefing` imprime el resumen del mes: gasto equivalente API, tokens y días activos comparados con el mismo tramo del mes anterior, suscripción frente a API y las señales de "Atención ahora". Es lo mismo que muestra el Inicio del dashboard (`GET /api/briefing?source=<fuente>&compare=YYYY-MM`).
```

- [ ] **Step 4: Verificar**

Run: `python3 -m unittest discover -s tests -v` → todo PASS.
Run: `python3 main.py --briefing` → imprime un resumen legible con los datos reales (sin traceback).

- [ ] **Step 5: Commit**

```bash
git add server.py main.py tests/test_server.py tests/test_main.py CLAUDE.md README.md
git commit -m "feat: endpoint /api/briefing y main.py --briefing"
```

---

### Task 5: Identidad visual de jrueda.dev (tokens, fuentes, glow, gradiente)

**Files:**
- Modify: `frontend/src/index.css`
- Modify: `frontend/package.json`, `frontend/package-lock.json` (`npm install @fontsource/inter @fontsource/jetbrains-mono`; `npm uninstall @fontsource-variable/geist` solo si `grep -rn geist frontend/src frontend/index.html` no devuelve nada)
- Modify: `frontend/src/main.tsx` (imports de fuentes)

**Interfaces:**
- Produces (clases Tailwind que usan Tasks 7–10): `text-link`, `bg-link`, `shadow-glow`, `bg-[image:var(--gradient-brand)]`, `font-mono` (JetBrains Mono), `font-sans` (Inter), `.card-interactive`, radios `rounded-lg/md/sm/xl` derivados de `--radius: 0.75rem`.

- [ ] **Step 1: Instalar fuentes e importarlas**

Run (en `frontend/`): `npm install @fontsource/inter @fontsource/jetbrains-mono`

`frontend/src/main.tsx`, antes de `import './index.css'`:

```ts
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "@fontsource/inter/800.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";
```

- [ ] **Step 2: Reemplazar los tokens shadcn de `:root` y `.dark`**

En `index.css`, sustituir las líneas desde `--background` hasta `--sidebar-ring` de `:root` por:

```css
  --background: #ffffff;
  --foreground: #020817;
  --card: #ffffff;
  --card-foreground: #020817;
  --popover: #ffffff;
  --popover-foreground: #020817;
  --muted: #f1f5f9;
  --muted-foreground: #64748b;
  --accent: #f1f5f9;
  --accent-foreground: #020817;
  --destructive: #ef4444;
  --destructive-foreground: #ffffff;
  --border: #e2e8f0;
  --input: #e2e8f0;
  --primary: #00b1cc;
  /* #f8fafc sobre #00b1cc da 2,46:1; #020817 da 7,77:1 (corrección medida al spec §4.4). */
  --primary-foreground: #020817;
  --secondary: #f1f5f9;
  --secondary-foreground: #020817;
  --ring: #00b1cc;
  /* Cyan legible como texto o enlace sobre blanco (5,36:1); --primary solo pasa como superficie. */
  --link: #0e7490;
  --glow: 0 0 40px rgb(0 177 204 / 0.15);
  --gradient-brand: linear-gradient(135deg, #00b1cc, #29bc86);
  --radius: 0.75rem;

  --sidebar: var(--background);
  --sidebar-foreground: var(--foreground);
  --sidebar-primary: var(--primary);
  --sidebar-primary-foreground: var(--primary-foreground);
  --sidebar-accent: var(--muted);
  --sidebar-accent-foreground: var(--foreground);
  --sidebar-border: var(--border);
  --sidebar-ring: var(--ring);
```

y las de `.dark` por:

```css
  --background: #09090b;
  --foreground: #f8fafc;
  --card: #101013;
  --card-foreground: #f8fafc;
  --popover: #101013;
  --popover-foreground: #f8fafc;
  --muted: #242428;
  --muted-foreground: #94a3b8;
  --accent: #242428;
  --accent-foreground: #f8fafc;
  --destructive: #ef4444;
  --destructive-foreground: #09090b;
  --border: #303036;
  --input: #303036;
  --primary: #00ddff;
  --primary-foreground: #09090b;
  --secondary: #242428;
  --secondary-foreground: #f8fafc;
  --ring: #00ddff;
  --link: #00ddff;
  --glow: 0 0 40px rgb(0 221 255 / 0.2);
  --gradient-brand: linear-gradient(135deg, #00ddff, #36d399);

  --sidebar: var(--background);
  --sidebar-foreground: var(--foreground);
  --sidebar-primary: var(--primary);
  --sidebar-primary-foreground: var(--primary-foreground);
  --sidebar-accent: var(--muted);
  --sidebar-accent-foreground: var(--foreground);
  --sidebar-border: var(--border);
  --sidebar-ring: var(--ring);
```

Las variables `--tremor-*` y `--viz-*` **no se tocan**.

- [ ] **Step 3: Exponer los tokens nuevos en `@theme inline`**

Dentro de `@theme inline { ... }`, después de `--color-sidebar-ring`:

```css
  --color-link: var(--link);
  --shadow-glow: var(--glow);
  --radius-sm: calc(var(--radius) - 4px);
  --radius-md: calc(var(--radius) - 2px);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) + 4px);
  --font-sans: "Inter", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, SFMono-Regular, monospace;
```

Y al final del archivo:

```css
/* Tarjeta interactiva (patrón card-active de jrueda.dev): borde cyan + glow al hover/foco. */
.card-interactive {
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
}
.card-interactive:hover,
.card-interactive:focus-visible {
  border-color: var(--primary);
  box-shadow: var(--glow);
}
@media (prefers-reduced-motion: reduce) {
  .card-interactive {
    transition: none;
  }
}
```

- [ ] **Step 4: Validar la paleta**

Invoca la skill `dataviz` y ejecuta su validador de paleta (está referenciado en la skill, `references/palette.md` y el script que menciona) con, para **cada tema**: el cyan de interfaz (`#00b1cc` claro, `#00ddff` oscuro) más las cinco `--viz-*` de ese tema, sobre el fondo del tema (`#ffffff` / `#09090b`). Además comprueba contraste WCAG de texto: `--link` sobre `--background` y `--card` ≥ 4,5:1; `--primary-foreground` sobre `--primary` ≥ 4,5:1; `--muted-foreground` sobre `--background` ≥ 4,5:1, en ambos temas. Si el validador de la skill no cubre contraste, calcula la razón WCAG con un script Node de una sola vez en el scratchpad (no en el repo).

Expected: sin FAIL de contraste de texto. Un FAIL de ΔE entre el cyan y una `--viz-*` es aceptable **solo** porque el cyan nunca va en marcas de datos (anótalo en el reporte). Cualquier FAIL de contraste de texto se corrige ajustando el token (no las `--viz-*`) antes del commit.

- [ ] **Step 5: Build, tests y commit**

Run (en `frontend/`): `npm run build && npm test && npm run lint` → OK.

```bash
git add frontend/src/index.css frontend/src/main.tsx frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): identidad visual de jrueda.dev con cyan como acento, Inter y JetBrains Mono"
```

---

### Task 6: Frontend — contrato del briefing, `lib/briefing.ts`, `useBriefing` y paridad de `clientOf`

**Files:**
- Modify: `frontend/src/lib/api.ts`, `frontend/src/lib/sources.ts`, `frontend/src/lib/routes.ts` (solo agregar helpers), `frontend/tsconfig.app.json` (`"resolveJsonModule": true`)
- Create: `frontend/src/lib/briefing.ts`, `frontend/src/lib/briefing.test.ts`, `frontend/src/hooks/useBriefing.ts`, `frontend/src/lib/clients.test.ts`, `frontend/src/lib/api.test.ts`
- Modify: `frontend/src/lib/routes.test.ts`

**Interfaces:**
- Produces:
  - `lib/sources.ts`: `SOURCE_KEYS = ["all","claude_code","codex","opencode","hermes","openrouter"] as const`, `type SourceKey`.
  - `lib/api.ts`: `class HttpError extends Error { status: number }`; tipos `Coverage`, `MonthCoverage`, `BriefingKpi`, `BriefingSignal`, `BriefingSubscription`, `BriefingProject`, `BriefingResponse`; `fetchBriefing(source: SourceKey, compare: string | null): Promise<BriefingResponse>`.
  - `lib/routes.ts` (aditivo): `SOURCE_PARAM = "fuente"`, `COMPARE_PARAM = "comparar"`, `withQuery(path: string, params: URLSearchParams): string`, `withSource(target: string, search: string): string`.
  - `lib/briefing.ts`: `formatDeltaPct(number|null): string`, `coverageLabel(since: string): string`, `windowLabel(b): string`, `subscriptionLine(s): string|null`, `subscriptionHeadline(s): string`, `isEmptyBriefing(b): boolean`, `dailyCostSeries(data: HistoryResponse, source: SourceKey, from: string, to: string): {date: string; cost: number}[]`.
  - `hooks/useBriefing.ts`: `useBriefing(source, compare, refreshKey: unknown): BriefingState & { retry(): void }`, con `BriefingState = {status:"loading"} | {status:"error"; message: string; httpStatus: number|null} | {status:"ready"; data: BriefingResponse}`.

- [ ] **Step 1: Tests que fallan**

`frontend/src/lib/clients.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import cases from "../../../tests/fixtures/client_of_cases.json";
import { clientOf } from "@/lib/clients";

describe("clientOf: paridad con briefing.client_of (fixture compartido)", () => {
  it.each(cases)("$path → $client", ({ path, client }) => {
    expect(clientOf(path)).toBe(client);
  });
});
```

`frontend/src/lib/api.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { HttpError, fetchBriefing } from "@/lib/api";

afterEach(() => vi.unstubAllGlobals());

describe("fetchBriefing", () => {
  it("arma la query con source y compare", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await fetchBriefing("claude_code", "2026-08");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/briefing?source=claude_code&compare=2026-08");
  });

  it("un 400 llega como HttpError con status y el mensaje del backend", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: "No hay datos para comparar con 1999-01" }), { status: 400 }),
    ));
    const err = await fetchBriefing("all", "1999-01").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(HttpError);
    expect((err as HttpError).status).toBe(400);
    expect((err as HttpError).message).toContain("No hay datos para comparar con 1999-01");
  });
});
```

`frontend/src/lib/briefing.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { BriefingResponse, HistoryResponse } from "@/lib/api";
import {
  coverageLabel, dailyCostSeries, formatDeltaPct, isEmptyBriefing, subscriptionHeadline, subscriptionLine, windowLabel,
} from "@/lib/briefing";

function briefing(overrides: Partial<BriefingResponse> = {}): BriefingResponse {
  return {
    source: "all",
    window: { month: "2026-09", from: "2026-09-01", to: "2026-09-27" },
    compare: { month: "2026-08", from: "2026-08-01", to: "2026-08-27", coverage: "full", since: null },
    eligible_months: [{ month: "2026-08", coverage: "full", since: null }],
    kpis: {
      cost: { current: 10, previous: 20, delta_pct: -50 },
      tokens: { current: 100, previous: 50, delta_pct: 100 },
      active_days: { current: 3, previous: 2 },
      cost_incomplete: false,
    },
    subscription: { configured: false, paid: null, api_equivalent: null, winner: null, savings: null },
    top_projects: [],
    attention: [],
    degraded: false,
    ...overrides,
  };
}

describe("formatDeltaPct", () => {
  it("signo explícito, coma decimal y guion para null", () => {
    expect(formatDeltaPct(12.34)).toBe("+12,3 %");
    expect(formatDeltaPct(-17.8)).toBe("−17,8 %");
    expect(formatDeltaPct(0)).toBe("0,0 %");
    expect(formatDeltaPct(null)).toBe("—");
  });
});

describe("etiquetas de ventana y cobertura", () => {
  it("ventana comparada", () => {
    expect(windowLabel(briefing())).toBe("1–27 sept · comparado con 1–27 ago");
  });
  it("sin mes comparable", () => {
    const b = briefing({ compare: { month: "2026-08", from: "2026-08-01", to: "2026-08-27", coverage: "none", since: null } });
    expect(windowLabel(b)).toBe("1–27 sept · sin mes con datos para comparar");
  });
  it("cobertura parcial", () => {
    expect(coverageLabel("2026-07-18")).toBe("cobertura parcial desde 18 jul");
  });
});

describe("suscripción", () => {
  const base = { configured: true, paid: 20, api_equivalent: 657.1 } as const;
  it("gana la suscripción", () => {
    const s = { ...base, winner: "subscription", savings: 637.1 } as const;
    expect(subscriptionLine(s)).toBe("Pagas $ 20,00 · equivale a $ 657,10 · ahorras $ 637,10");
    expect(subscriptionHeadline(s)).toBe("Ahorras $ 637,10");
  });
  it("gana la API", () => {
    const s = { ...base, api_equivalent: 5, winner: "api", savings: 15 } as const;
    expect(subscriptionLine(s)).toBe("Pagas $ 20,00 · equivale a $ 5,00 · la API saldría $ 15,00 más barata");
    expect(subscriptionHeadline(s)).toBe("API más barata por $ 15,00");
  });
  it("empate y sin plan", () => {
    expect(subscriptionHeadline({ ...base, winner: "tie", savings: 0 })).toBe("Empate");
    const none = { configured: false, paid: null, api_equivalent: null, winner: null, savings: null };
    expect(subscriptionLine(none)).toBeNull();
    expect(subscriptionHeadline(none)).toBe("Sin plan configurado");
  });
});

describe("isEmptyBriefing", () => {
  it("vacío solo sin meses elegibles ni actividad", () => {
    const empty = briefing({ eligible_months: [], kpis: { ...briefing().kpis, active_days: { current: 0, previous: null } } });
    expect(isEmptyBriefing(empty)).toBe(true);
    expect(isEmptyBriefing(briefing())).toBe(false);
  });
});

describe("dailyCostSeries", () => {
  const data: HistoryResponse = {
    daily_project: [
      { date: "2026-09-01", source: "claude_code", project: "/p", tokens: 1, cost: 2 },
      { date: "2026-09-01", source: "codex", project: "/p", tokens: 1, cost: 3 },
      { date: "2026-09-03", source: "claude_code", project: "/q", tokens: 1, cost: null },
      { date: "2026-08-31", source: "claude_code", project: "/p", tokens: 1, cost: 9 },
    ],
    daily_model: [{ date: "2026-09-02", model: "__all__", tokens: 1, cost: 7 }],
  };
  it("rellena días sin datos con 0 y suma todas las fuentes de proyecto", () => {
    expect(dailyCostSeries(data, "all", "2026-09-01", "2026-09-03")).toEqual([
      { date: "2026-09-01", cost: 5 }, { date: "2026-09-02", cost: 0 }, { date: "2026-09-03", cost: 0 },
    ]);
  });
  it("filtra por fuente y usa daily_model para OpenRouter", () => {
    expect(dailyCostSeries(data, "codex", "2026-09-01", "2026-09-01")).toEqual([{ date: "2026-09-01", cost: 3 }]);
    expect(dailyCostSeries(data, "openrouter", "2026-09-02", "2026-09-02")).toEqual([{ date: "2026-09-02", cost: 7 }]);
  });
});
```

Agregar a `frontend/src/lib/routes.test.ts`:

```ts
import { withSource } from "@/lib/routes";

describe("withSource", () => {
  it("conserva ?fuente= de la URL actual y no pisa uno explícito", () => {
    expect(withSource("/actividad?dia=2026-09-27", "?fuente=codex&dia=2026-01-01")).toBe("/actividad?dia=2026-09-27&fuente=codex");
    expect(withSource("/gasto?fuente=claude-code", "?fuente=codex")).toBe("/gasto?fuente=claude-code");
    expect(withSource("/configuracion", "")).toBe("/configuracion");
  });
});
```

- [ ] **Step 2: Verificar que fallan**

Run (en `frontend/`): `npm test`
Expected: FAIL (módulos y exports inexistentes).

- [ ] **Step 3: Implementar**

`tsconfig.app.json`: agregar `"resolveJsonModule": true,` bajo "Bundler mode".

`lib/sources.ts`, al final:

```ts
/** Filtro global de fuente (?fuente=). "all" suma las cuatro fuentes por proyecto; nunca OpenRouter. */
export const SOURCE_KEYS = ["all", "claude_code", "codex", "opencode", "hermes", "openrouter"] as const;
export type SourceKey = (typeof SOURCE_KEYS)[number];
```

`lib/api.ts`: reemplazar `getJson` y agregar tipos/función:

```ts
import type { SourceKey } from "@/lib/sources";
import type { CostWinner } from "@/lib/roi";

/** Error HTTP con el status, para que la UI distinga un 400 (parámetro inválido) de una caída. */
export class HttpError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "HttpError";
    this.status = status;
  }
}

async function getJson<T>(input: string, init?: RequestInit): Promise<T> {
  const res = await fetch(input, init);
  if (!res.ok) {
    let detail = "";
    try {
      const body = (await res.json()) as { error?: string };
      if (body?.error) detail = `: ${body.error}`;
    } catch {
      // cuerpo no JSON: basta con el status
    }
    throw new HttpError(`${init?.method ?? "GET"} ${input} → HTTP ${res.status}${detail}`, res.status);
  }
  return res.json() as Promise<T>;
}

export type Coverage = "full" | "partial" | "none";

export interface MonthCoverage {
  month: string;
  coverage: Exclude<Coverage, "none">;
  since: string | null;
}

export interface BriefingKpi {
  current: number;
  previous: number | null;
  delta_pct: number | null;
}

export interface BriefingSignal {
  id: string;
  severity: "warning" | "info";
  title: string;
  evidence: string[];
  link: string;
}

export interface BriefingSubscription {
  configured: boolean;
  paid: number | null;
  api_equivalent: number | null;
  winner: CostWinner | null;
  savings: number | null;
}

export interface BriefingProject {
  project: string;
  client: string;
  cost: number;
  share: number;
}

export interface BriefingResponse {
  source: SourceKey;
  window: { month: string; from: string; to: string };
  compare: { month: string; from: string; to: string; coverage: Coverage; since: string | null };
  eligible_months: MonthCoverage[];
  kpis: {
    cost: BriefingKpi;
    tokens: BriefingKpi;
    active_days: { current: number; previous: number | null };
    cost_incomplete: boolean;
  };
  subscription: BriefingSubscription;
  top_projects: BriefingProject[];
  attention: BriefingSignal[];
  degraded: boolean;
}

export function fetchBriefing(source: SourceKey, compare: string | null): Promise<BriefingResponse> {
  const params = new URLSearchParams({ source });
  if (compare) params.set("compare", compare);
  return getJson(`/api/briefing?${params}`);
}
```

Si `lib/roi.ts` importa de `lib/api.ts` y el import de `CostWinner` crea un ciclo que molesta a oxlint, declara en `api.ts` `export type CostWinner = "subscription" | "api" | "tie";` y haz que `roi.ts` lo reexporte desde `api.ts`.

`lib/routes.ts`, al final (aditivo; Task 9 reescribe el resto del archivo y conserva esto):

```ts
export const SOURCE_PARAM = "fuente";
export const COMPARE_PARAM = "comparar";

export function withQuery(path: string, params: URLSearchParams): string {
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

/** Enlace interno que conserva el filtro global ?fuente= de la URL actual. */
export function withSource(target: string, search: string): string {
  const current = new URLSearchParams(search).get(SOURCE_PARAM);
  const [path, query = ""] = target.split("?");
  const params = new URLSearchParams(query);
  if (current && !params.has(SOURCE_PARAM)) params.set(SOURCE_PARAM, current);
  return withQuery(path, params);
}
```

`lib/briefing.ts`:

```ts
/**
 * Formato de presentación del briefing (/api/briefing). El backend ya decide
 * qué señales mostrar y arma sus textos; aquí solo se da forma a números y etiquetas.
 */
import type { BriefingResponse, BriefingSubscription, HistoryResponse } from "@/lib/api";
import { formatDayShort, formatDecimal, formatUsd } from "@/lib/format";
import type { SourceKey } from "@/lib/sources";

export function formatDeltaPct(delta: number | null): string {
  if (delta === null) return "—";
  const sign = delta > 0 ? "+" : delta < 0 ? "−" : "";
  return `${sign}${formatDecimal(Math.abs(delta))} %`;
}

export function coverageLabel(since: string): string {
  return `cobertura parcial desde ${formatDayShort(since)}`;
}

function dayRange(from: string, to: string): string {
  return `${Number(from.slice(8, 10))}–${formatDayShort(to)}`;
}

export function windowLabel(b: BriefingResponse): string {
  const current = dayRange(b.window.from, b.window.to);
  if (b.compare.coverage === "none") return `${current} · sin mes con datos para comparar`;
  return `${current} · comparado con ${dayRange(b.compare.from, b.compare.to)}`;
}

export function subscriptionLine(s: BriefingSubscription): string | null {
  if (!s.configured || s.paid === null || s.api_equivalent === null || s.savings === null) return null;
  const base = `Pagas ${formatUsd(s.paid)} · equivale a ${formatUsd(s.api_equivalent)}`;
  if (s.winner === "subscription") return `${base} · ahorras ${formatUsd(s.savings)}`;
  if (s.winner === "api") return `${base} · la API saldría ${formatUsd(s.savings)} más barata`;
  return `${base} · empate`;
}

export function subscriptionHeadline(s: BriefingSubscription): string {
  if (!s.configured || s.savings === null) return "Sin plan configurado";
  if (s.winner === "subscription") return `Ahorras ${formatUsd(s.savings)}`;
  if (s.winner === "api") return `API más barata por ${formatUsd(s.savings)}`;
  return "Empate";
}

export function isEmptyBriefing(b: BriefingResponse): boolean {
  return b.eligible_months.length === 0 && b.kpis.active_days.current === 0;
}

const PROJECT_SOURCES = new Set(["claude_code", "codex", "opencode", "hermes"]);

/** Costo por día entre `from` y `to` (inclusive), con 0 en los días sin filas. */
export function dailyCostSeries(
  data: HistoryResponse, source: SourceKey, from: string, to: string,
): { date: string; cost: number }[] {
  const byDate: Record<string, number> = {};
  if (source === "openrouter") {
    for (const row of data.daily_model) {
      if (row.model === "__all__") byDate[row.date.slice(0, 10)] = (byDate[row.date.slice(0, 10)] ?? 0) + (row.cost ?? 0);
    }
  } else {
    for (const row of data.daily_project) {
      if (source === "all" ? !PROJECT_SOURCES.has(row.source) : row.source !== source) continue;
      const date = row.date.slice(0, 10);
      byDate[date] = (byDate[date] ?? 0) + (row.cost ?? 0);
    }
  }
  const points: { date: string; cost: number }[] = [];
  // Cursor en UTC para no saltar ni duplicar días por la zona horaria.
  const cursor = new Date(`${from}T00:00:00Z`);
  const end = new Date(`${to}T00:00:00Z`);
  while (cursor <= end) {
    const date = cursor.toISOString().slice(0, 10);
    points.push({ date, cost: byDate[date] ?? 0 });
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return points;
}
```

`hooks/useBriefing.ts`:

```ts
import { useCallback, useEffect, useState } from "react";
import { HttpError, fetchBriefing, type BriefingResponse } from "@/lib/api";
import type { SourceKey } from "@/lib/sources";

/** Caché por (fuente, mes comparado): volver al Inicio o a un filtro ya visto pinta
 * de inmediato, sin skeleton, mientras se revalida en segundo plano. */
const cache = new Map<string, BriefingResponse>();

export type BriefingState =
  | { status: "loading" }
  | { status: "error"; message: string; httpStatus: number | null }
  | { status: "ready"; data: BriefingResponse };

/** `refreshKey` cambia con cada snapshot SSE nuevo: dispara una revalidación silenciosa. */
export function useBriefing(
  source: SourceKey, compare: string | null, refreshKey: unknown,
): BriefingState & { retry: () => void } {
  const key = `${source}|${compare ?? ""}`;
  const [state, setState] = useState<BriefingState>(() => {
    const data = cache.get(key);
    return data ? { status: "ready", data } : { status: "loading" };
  });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const cached = cache.get(key);
    setState(cached ? { status: "ready", data: cached } : { status: "loading" });
    fetchBriefing(source, compare)
      .then((data) => {
        cache.set(key, data);
        if (!cancelled) setState({ status: "ready", data });
      })
      .catch((err: Error) => {
        // Con datos en pantalla, un fallo de revalidación no los reemplaza por un error.
        if (cancelled || cached) return;
        setState({ status: "error", message: err.message, httpStatus: err instanceof HttpError ? err.status : null });
      });
    return () => {
      cancelled = true;
    };
  }, [key, source, compare, refreshKey, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { ...state, retry };
}
```

- [ ] **Step 4: Verificar**

Run (en `frontend/`): `npm test && npm run build && npm run lint` → OK.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib frontend/src/hooks/useBriefing.ts frontend/tsconfig.app.json
git commit -m "feat(frontend): contrato de /api/briefing, formato del briefing y paridad de clientOf"
```

---

### Task 7: Inicio (variante A · briefing vertical)

**Files:**
- Create: `frontend/src/components/home/HomeView.tsx`, `BriefingHeader.tsx`, `BriefingKpis.tsx`, `AttentionList.tsx`, `TopProjects.tsx`, `DailySpark.tsx`

**Interfaces:**
- Consumes: `useBriefing`, `useHistory`, todo `lib/briefing.ts`, `withSource`, `SOURCE_META`, `SourceKey`, `formatUsd/formatInt/formatCompact/formatMonth/formatDayShort`, `basename` de `lib/tree.ts`, `Skeleton`.
- Produces: `HomeView({ source: SourceKey; compare: string | null; onCompareChange: (month: string | null) => void; refreshKey: unknown })`. Se monta en `/` en Task 9. Encabezado `<h1>` = mes actual (p. ej. "Septiembre de 2026").

No hay tests de componentes en este repo (vitest cubre `lib/`); la lógica ya está probada en Task 6. La verificación visual es la de Task 11.

- [ ] **Step 1: `BriefingHeader.tsx`**

```tsx
import { useId } from "react";
import type { BriefingResponse } from "@/lib/api";
import { coverageLabel, windowLabel } from "@/lib/briefing";
import { formatMonth } from "@/lib/format";

interface BriefingHeaderProps {
  briefing: BriefingResponse;
  onCompareChange: (month: string | null) => void;
}

export function BriefingHeader({ briefing, onCompareChange }: BriefingHeaderProps) {
  const selectId = useId();
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-bold tracking-tight">{formatMonth(briefing.window.month)}</h1>
        <p className="text-sm text-muted-foreground">{windowLabel(briefing)}</p>
      </div>
      {briefing.eligible_months.length > 0 && (
        <div className="flex items-center gap-2 text-sm">
          <label htmlFor={selectId} className="text-muted-foreground">Comparar con</label>
          <select
            id={selectId}
            value={briefing.compare.month}
            onChange={(e) => onCompareChange(e.target.value)}
            className="max-w-[16rem] rounded-lg border bg-background px-3 py-1.5 text-sm"
          >
            {briefing.eligible_months.map((m) => (
              <option key={m.month} value={m.month}>
                {formatMonth(m.month)}
                {m.coverage === "partial" && m.since ? ` · ${coverageLabel(m.since)}` : ""}
              </option>
            ))}
          </select>
        </div>
      )}
    </header>
  );
}
```

- [ ] **Step 2: `BriefingKpis.tsx`**

```tsx
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { BriefingResponse } from "@/lib/api";
import { coverageLabel, formatDeltaPct, subscriptionHeadline, subscriptionLine } from "@/lib/briefing";
import { formatCompact, formatInt, formatUsd } from "@/lib/format";
import { withSource } from "@/lib/routes";

function Delta({ value, label }: { value: number | null; label: string }) {
  if (value === null) {
    return (
      <span title="sin datos para comparar" className="text-muted-foreground">
        <span aria-hidden>—</span>
        <span className="sr-only">{label}: sin datos para comparar</span>
      </span>
    );
  }
  return (
    <span className="font-medium tabular-nums">
      <span className="sr-only">{label}: </span>
      {formatDeltaPct(value)}
    </span>
  );
}

function Kpi({ label, value, children }: { label: string; value: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border bg-card p-5">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-bold tracking-tight tabular-nums">{value}</p>
      <div className="mt-2 space-y-1 text-sm text-muted-foreground">{children}</div>
    </div>
  );
}

export function BriefingKpis({ briefing, search }: { briefing: BriefingResponse; search: string }) {
  const { kpis, subscription, compare } = briefing;
  const partial = compare.coverage === "partial" && compare.since ? coverageLabel(compare.since) : null;
  const line = subscriptionLine(subscription);

  return (
    <section aria-label="Indicadores del mes" className="grid grid-cols-1 gap-4 md:grid-cols-3">
      <Kpi label="Gasto equivalente API" value={formatUsd(kpis.cost.current)}>
        <p>
          <Delta value={kpis.cost.delta_pct} label="Variación del gasto" /> frente al mes comparado
        </p>
        {partial && <p className="text-xs">{partial}</p>}
        {kpis.cost_incomplete && <p className="text-xs">Incluye consumo sin costo calculado</p>}
      </Kpi>
      <Kpi label="Suscripción vs API" value={subscriptionHeadline(subscription)}>
        {line ? (
          <p>{line}</p>
        ) : (
          <Link to={withSource("/configuracion", search)} className="text-link underline-offset-4 hover:underline">
            Configura tu plan para comparar
          </Link>
        )}
      </Kpi>
      <Kpi label="Días activos" value={formatInt(kpis.active_days.current)}>
        <p>
          {formatCompact(kpis.tokens.current)} tokens · <Delta value={kpis.tokens.delta_pct} label="Variación de tokens" />
        </p>
        {kpis.active_days.previous !== null && <p className="text-xs">Antes: {formatInt(kpis.active_days.previous)} días</p>}
      </Kpi>
    </section>
  );
}
```

- [ ] **Step 3: `AttentionList.tsx`**

```tsx
import { Link } from "react-router-dom";
import { AlertTriangle, Info } from "lucide-react";
import type { BriefingSignal } from "@/lib/api";
import { withSource } from "@/lib/routes";

// El color nunca es el único indicador: punto + ícono + texto accesible.
const SEVERITY = {
  warning: { icon: AlertTriangle, label: "Advertencia", dot: "bg-amber-500", text: "text-amber-700 dark:text-amber-400" },
  info: { icon: Info, label: "Información", dot: "bg-link", text: "text-link" },
} as const;

export function AttentionList({ signals, search }: { signals: BriefingSignal[]; search: string }) {
  return (
    <section aria-labelledby="attention-title" className="rounded-xl border bg-card p-5">
      <h2 id="attention-title" className="text-sm font-medium">Atención ahora</h2>
      {signals.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">Nada requiere tu atención ahora</p>
      ) : (
        <ul className="mt-3 divide-y">
          {signals.map((signal) => {
            const meta = SEVERITY[signal.severity];
            return (
              <li key={signal.id} className="flex gap-3 py-3 first:pt-0 last:pb-0">
                <span className={`mt-0.5 inline-flex shrink-0 items-center gap-1.5 ${meta.text}`}>
                  <span aria-hidden className={`h-2 w-2 rounded-full ${meta.dot}`} />
                  <meta.icon className="h-4 w-4" aria-hidden />
                  <span className="sr-only">{meta.label}:</span>
                </span>
                <div className="min-w-0 flex-1 space-y-1">
                  <p className="text-sm font-medium">{signal.title}</p>
                  <ul className="space-y-0.5 text-xs text-muted-foreground">
                    {signal.evidence.map((item) => (
                      <li key={item} className="break-words">{item}</li>
                    ))}
                  </ul>
                </div>
                <Link
                  to={withSource(signal.link, search)}
                  className="shrink-0 self-center text-sm text-link underline-offset-4 hover:underline"
                >
                  Ver<span className="sr-only">: {signal.title}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
```

- [ ] **Step 4: `TopProjects.tsx`**

```tsx
import { Link } from "react-router-dom";
import type { BriefingProject } from "@/lib/api";
import { formatUsd } from "@/lib/format";
import { withSource } from "@/lib/routes";
import { basename } from "@/lib/tree";

export function TopProjects({ projects, search }: { projects: BriefingProject[]; search: string }) {
  return (
    <section aria-labelledby="top-projects-title" className="rounded-xl border bg-card p-5">
      <h2 id="top-projects-title" className="text-sm font-medium">Proyectos con más gasto</h2>
      {projects.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">Sin gasto por proyecto en este periodo</p>
      ) : (
        <ol className="mt-4 space-y-3">
          {projects.map((p) => {
            const pct = Math.round(p.share * 100);
            const href = `/proyectos/${encodeURIComponent(p.client)}?proyecto=${encodeURIComponent(p.project)}`;
            return (
              <li key={p.project}>
                <Link to={withSource(href, search)} className="-m-2 block rounded-lg p-2 hover:bg-muted">
                  <div className="flex items-baseline justify-between gap-3 text-sm">
                    <span className="truncate font-medium" title={p.project}>{basename(p.project)}</span>
                    <span className="shrink-0 tabular-nums">{formatUsd(p.cost)}</span>
                  </div>
                  <div className="mt-1.5 flex items-center gap-2">
                    <div className="h-1.5 flex-1 rounded-full bg-muted" aria-hidden>
                      <div className="h-full rounded-full bg-muted-foreground/70" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="w-10 text-right text-xs tabular-nums text-muted-foreground">{pct} %</span>
                  </div>
                  <p className="mt-0.5 font-mono text-xs text-muted-foreground">{p.client}</p>
                </Link>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
```

- [ ] **Step 5: `DailySpark.tsx`**

```tsx
import { Link } from "react-router-dom";
import { Skeleton } from "@/components/ui/skeleton";
import { useHistory } from "@/hooks/useHistory";
import { dailyCostSeries } from "@/lib/briefing";
import { formatDayShort, formatUsd } from "@/lib/format";
import { withSource } from "@/lib/routes";
import { SOURCE_META, type SourceKey } from "@/lib/sources";

const HISTORY_DAYS = 62;

interface DailySparkProps {
  source: SourceKey;
  from: string;
  to: string;
  search: string;
}

export function DailySpark({ source, from, to, search }: DailySparkProps) {
  const history = useHistory(HISTORY_DAYS);
  const points = history.status === "ready" ? dailyCostSeries(history.data, source, from, to) : [];
  const max = points.reduce((m, p) => Math.max(m, p.cost), 0);
  // Identidad de la fuente filtrada; tinta neutra en "Todas" (el cyan nunca va en datos).
  const color = source === "all" ? "var(--muted-foreground)" : SOURCE_META[source].color;

  return (
    <section aria-labelledby="spark-title" className="rounded-xl border bg-card p-5">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="spark-title" className="text-sm font-medium">Gasto diario del mes</h2>
        <Link to={withSource("/actividad", search)} className="text-sm text-link underline-offset-4 hover:underline">
          Ver actividad
        </Link>
      </div>
      {history.status === "loading" && <Skeleton className="mt-4 h-32 w-full" />}
      {history.status === "error" && (
        <p role="alert" className="mt-4 text-sm text-muted-foreground">No se pudo cargar el historial ({history.message}).</p>
      )}
      {history.status === "ready" && (
        <svg
          viewBox={`0 0 ${Math.max(points.length, 1) * 10} 100`}
          preserveAspectRatio="none"
          className="mt-4 h-32 w-full"
          role="img"
          aria-label={`Gasto diario del ${formatDayShort(from)} al ${formatDayShort(to)}; máximo ${formatUsd(max)}`}
        >
          {points.map((p, i) => {
            const height = max > 0 ? (p.cost / max) * 96 : 0;
            return (
              <rect key={p.date} x={i * 10 + 1} y={100 - height} width={8} height={height} rx={1.5} fill={color}>
                <title>{`${formatDayShort(p.date)}: ${formatUsd(p.cost)}`}</title>
              </rect>
            );
          })}
        </svg>
      )}
    </section>
  );
}
```

- [ ] **Step 6: `HomeView.tsx`**

```tsx
import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { AlertCircle, RotateCw } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { useBriefing } from "@/hooks/useBriefing";
import { isEmptyBriefing } from "@/lib/briefing";
import { withSource } from "@/lib/routes";
import type { SourceKey } from "@/lib/sources";
import { AttentionList } from "./AttentionList";
import { BriefingHeader } from "./BriefingHeader";
import { BriefingKpis } from "./BriefingKpis";
import { DailySpark } from "./DailySpark";
import { TopProjects } from "./TopProjects";

interface HomeViewProps {
  source: SourceKey;
  compare: string | null;
  onCompareChange: (month: string | null) => void;
  refreshKey: unknown;
}

/** Mismas alturas que el contenido final para que no salte el layout. */
function HomeSkeleton() {
  return (
    <div aria-busy="true" aria-label="Cargando briefing" className="space-y-6">
      <div className="space-y-2"><Skeleton className="h-8 w-56" /><Skeleton className="h-4 w-72" /></div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {[0, 1, 2].map((i) => <Skeleton key={i} className="h-36 w-full rounded-xl" />)}
      </div>
      <Skeleton className="h-44 w-full rounded-xl" />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Skeleton className="h-60 w-full rounded-xl" /><Skeleton className="h-60 w-full rounded-xl" />
      </div>
    </div>
  );
}

export function HomeView({ source, compare, onCompareChange, refreshKey }: HomeViewProps) {
  const briefing = useBriefing(source, compare, refreshKey);
  const { search } = useLocation();

  // Un ?comparar= que ya no es elegible (enlace viejo u otra fuente) vuelve al mes por defecto.
  const invalidCompare = briefing.status === "error" && briefing.httpStatus === 400 && compare !== null;
  useEffect(() => {
    if (invalidCompare) onCompareChange(null);
  }, [invalidCompare, onCompareChange]);

  if (briefing.status === "loading" || invalidCompare) return <HomeSkeleton />;

  if (briefing.status === "error") {
    return (
      <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl border bg-card p-5 text-sm">
        <AlertCircle className="h-4 w-4 shrink-0 text-destructive" aria-hidden />
        <span className="min-w-0 flex-1 break-words">No se pudo cargar el briefing ({briefing.message}).</span>
        <button
          type="button"
          onClick={briefing.retry}
          className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 font-medium hover:bg-muted"
        >
          <RotateCw className="h-4 w-4" aria-hidden />
          Reintentar
        </button>
      </div>
    );
  }

  const b = briefing.data;
  const degraded = b.degraded && (
    <p role="status" className="rounded-lg border bg-muted px-3 py-2 text-sm text-muted-foreground">
      Historial no disponible temporalmente
    </p>
  );

  if (isEmptyBriefing(b)) {
    return (
      <div className="space-y-4">
        {degraded}
        <div className="space-y-3 rounded-xl border bg-card p-8 text-center">
          <h1 className="text-lg font-semibold">Aún no hay historial</h1>
          <p className="mx-auto max-w-prose text-sm text-muted-foreground">
            ai-monitor registra un resumen diario cada vez que recolecta; vuelve después de tu primera sesión.
          </p>
          <Link to={withSource("/configuracion", search)} className="text-sm text-link underline-offset-4 hover:underline">
            Ir a Configuración
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {degraded}
      <BriefingHeader briefing={b} onCompareChange={onCompareChange} />
      <BriefingKpis briefing={b} search={search} />
      <AttentionList signals={b.attention} search={search} />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <TopProjects projects={b.top_projects} search={search} />
        <DailySpark source={source} from={b.window.from} to={b.window.to} search={search} />
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Verificar y commit**

Run (en `frontend/`): `npm run build && npm run lint && npm test` → OK (el componente aún no está montado; `tsc -b` lo compila igual).

```bash
git add frontend/src/components/home
git commit -m "feat(frontend): Inicio tipo briefing con KPIs, atención ahora, top de proyectos y gasto diario"
```

---

### Task 8: Configuración (formulario de plan movido desde ROI + estado por fuente)

**Files:**
- Create: `frontend/src/components/SettingsForm.tsx`, `frontend/src/views/SettingsView.tsx`, `frontend/src/lib/settings.ts`, `frontend/src/lib/settings.test.ts`
- Modify: `frontend/src/components/RoiView.tsx` (quitar inputs, borrador y guardado; conservar "Acotar a" y las tarjetas; enlace a Configuración)

**Interfaces:**
- Consumes: `fetchRoiSettings`, `saveRoiSettings`, `RoiSettings`, `UsageSnapshot`, `SOURCE_META`, `SourceKey`, `withSource`.
- Produces: `SettingsView({ sources: UsageSnapshot["sources"] | null })` con `<h1>Configuración</h1>` (se monta en `/configuracion` en Task 9); `sourceStatuses(sources) -> SourceStatus[]` con `SourceStatus = { key: Exclude<SourceKey,"all">; label: string; state: "data" | "empty" | "unavailable"; detail: string }`.

- [ ] **Step 1: Test que falla**

`frontend/src/lib/settings.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { UsageSnapshot } from "@/lib/api";
import { sourceStatuses } from "@/lib/settings";

const usage = { total_tokens: 1 } as UsageSnapshot["sources"]["claude_code"][string];

describe("sourceStatuses", () => {
  it("sin snapshot → lista vacía", () => {
    expect(sourceStatuses(null)).toEqual([]);
  });

  it("con datos, sin datos y OpenRouter sin clave", () => {
    const sources = {
      claude_code: { "/a": usage, "/b": usage }, codex: {}, opencode: {}, hermes: {},
      openrouter: { unavailable: true, reason: "OPENROUTER_API_KEY no configurada" },
    } as UsageSnapshot["sources"];
    const byKey = Object.fromEntries(sourceStatuses(sources).map((s) => [s.key, s]));
    expect(byKey.claude_code).toMatchObject({ state: "data", detail: "2 proyectos" });
    expect(byKey.codex).toMatchObject({ state: "empty", detail: "Sin datos (no instalado o sin uso)" });
    expect(byKey.openrouter).toMatchObject({ state: "unavailable", detail: "OPENROUTER_API_KEY no configurada" });
  });

  it("OpenRouter disponible cuenta modelos", () => {
    const sources = {
      claude_code: {}, codex: {}, opencode: {}, hermes: {},
      openrouter: { unavailable: false, models: { a: { tokens: 1, cost: 1, requests: 1 } } },
    } as UsageSnapshot["sources"];
    expect(sourceStatuses(sources).find((s) => s.key === "openrouter")).toMatchObject({ state: "data", detail: "1 modelo" });
  });
});
```

Run: `npm test` → FAIL (módulo inexistente).

- [ ] **Step 2: `lib/settings.ts`**

```ts
import type { UsageSnapshot } from "@/lib/api";
import { SOURCE_META, type SourceKey } from "@/lib/sources";

export interface SourceStatus {
  key: Exclude<SourceKey, "all">;
  label: string;
  state: "data" | "empty" | "unavailable";
  detail: string;
}

const PROJECT_SOURCES = ["claude_code", "codex", "opencode", "hermes"] as const;
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** Estado por fuente a partir del snapshot en memoria. No distingue "no instalado" de
 * "falla de lectura": los collectors aún no reportan su estado (fuera de alcance v1). */
export function sourceStatuses(sources: UsageSnapshot["sources"] | null): SourceStatus[] {
  if (!sources) return [];
  const rows: SourceStatus[] = PROJECT_SOURCES.map((key) => {
    const count = Object.keys(sources[key] ?? {}).length;
    return {
      key,
      label: SOURCE_META[key].label,
      state: count > 0 ? "data" : "empty",
      detail: count > 0 ? plural(count, "proyecto", "proyectos") : "Sin datos (no instalado o sin uso)",
    };
  });
  const or = sources.openrouter;
  rows.push(
    or?.unavailable
      ? { key: "openrouter", label: SOURCE_META.openrouter.label, state: "unavailable", detail: or.reason ?? "No disponible" }
      : {
          key: "openrouter",
          label: SOURCE_META.openrouter.label,
          state: "data",
          detail: plural(Object.keys(or?.models ?? {}).length, "modelo", "modelos"),
        },
  );
  return rows;
}
```

- [ ] **Step 3: `components/SettingsForm.tsx`** (código movido de `RoiView`)

```tsx
import { useEffect, useState } from "react";
import { AlertCircle, Check, Save } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchRoiSettings, saveRoiSettings, type RoiSettings } from "@/lib/api";

type Draft = Record<keyof RoiSettings, string>;

function toDraft(s: RoiSettings): Draft {
  return {
    subscription_cost_claude: s.subscription_cost_claude?.toString() ?? "",
    subscription_cost_codex: s.subscription_cost_codex?.toString() ?? "",
    hourly_rate: s.hourly_rate?.toString() ?? "",
    subscription_start_claude: s.subscription_start_claude ?? "",
    subscription_start_codex: s.subscription_start_codex ?? "",
  };
}

export function SettingsForm() {
  const [draft, setDraft] = useState<Draft | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");

  useEffect(() => {
    fetchRoiSettings().then((s) => setDraft(toDraft(s))).catch((err: Error) => setLoadError(err.message));
  }, []);

  // Cualquier edición posterior invalida el "Cambios guardados" / error anterior.
  useEffect(() => setSaveStatus("idle"), [draft]);

  if (loadError) {
    return (
      <div role="alert" className="flex items-center gap-2 rounded-xl border bg-card p-5 text-sm">
        <AlertCircle className="h-4 w-4 shrink-0 text-destructive" aria-hidden />
        No se pudo cargar la configuración ({loadError}).
      </div>
    );
  }
  if (!draft) return <Skeleton className="h-72 w-full rounded-xl" />;

  const update = (key: keyof RoiSettings) => (value: string) => setDraft((d) => (d ? { ...d, [key]: value } : d));

  const handleSave = async () => {
    setSaveStatus("saving");
    const payload: Partial<RoiSettings> = {
      subscription_cost_claude: draft.subscription_cost_claude ? Number(draft.subscription_cost_claude) : null,
      subscription_cost_codex: draft.subscription_cost_codex ? Number(draft.subscription_cost_codex) : null,
      hourly_rate: draft.hourly_rate ? Number(draft.hourly_rate) : null,
      subscription_start_claude: draft.subscription_start_claude || null,
      subscription_start_codex: draft.subscription_start_codex || null,
    };
    try {
      setDraft(toDraft(await saveRoiSettings(payload)));
      setSaveStatus("saved");
    } catch (err) {
      console.error("Error al guardar /api/roi-settings:", err);
      setSaveStatus("error");
    }
  };

  return (
    <section aria-labelledby="plan-title" className="space-y-4 rounded-xl border bg-card p-5">
      <div>
        <h2 id="plan-title" className="text-sm font-medium">Tu plan</h2>
        <p className="text-sm text-muted-foreground">
          Con el costo mensual el Inicio y ROI comparan tu suscripción contra el precio de la API; la tarifa por hora estima el valor generado.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Field label="Suscripción Claude ($/mes)" value={draft.subscription_cost_claude} onChange={update("subscription_cost_claude")} />
        <Field label="Suscripción Codex ($/mes)" value={draft.subscription_cost_codex} onChange={update("subscription_cost_codex")} />
        <Field label="Tarifa por hora ($)" value={draft.hourly_rate} onChange={update("hourly_rate")} />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field type="date" label="Inicio suscripción Claude" value={draft.subscription_start_claude} onChange={update("subscription_start_claude")} />
        <Field type="date" label="Inicio suscripción Codex" value={draft.subscription_start_codex} onChange={update("subscription_start_codex")} />
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={saveStatus === "saving"}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        >
          <Save className="h-4 w-4" aria-hidden />
          {saveStatus === "saving" ? "Guardando…" : "Guardar"}
        </button>
        <span role="status" aria-live="polite" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
          {saveStatus === "saved" && (<><Check className="h-4 w-4" aria-hidden />Cambios guardados</>)}
          {saveStatus === "error" && (
            <><AlertCircle className="h-4 w-4 text-destructive" aria-hidden />No se pudo guardar. Revisa que el servidor siga activo e inténtalo de nuevo.</>
          )}
        </span>
      </div>
    </section>
  );
}

function Field({ label, value, onChange, type = "number" }: {
  label: string; value: string; onChange: (v: string) => void; type?: "number" | "date";
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <input
        type={type}
        {...(type === "number" ? { min: "0", step: "0.01", placeholder: "—" } : {})}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
      />
    </label>
  );
}
```

- [ ] **Step 4: `views/SettingsView.tsx`**

```tsx
import { SettingsForm } from "@/components/SettingsForm";
import { Skeleton } from "@/components/ui/skeleton";
import type { UsageSnapshot } from "@/lib/api";
import { sourceStatuses } from "@/lib/settings";
import { SOURCE_META } from "@/lib/sources";

const STATE_LABEL = { data: "Con datos", empty: "Sin datos", unavailable: "No disponible" } as const;

export function SettingsView({ sources }: { sources: UsageSnapshot["sources"] | null }) {
  const statuses = sourceStatuses(sources);
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Configuración</h1>
      <SettingsForm />
      <section aria-labelledby="sources-title" className="rounded-xl border bg-card p-5">
        <h2 id="sources-title" className="text-sm font-medium">Fuentes</h2>
        {statuses.length === 0 ? (
          <Skeleton className="mt-3 h-40 w-full" />
        ) : (
          <ul className="mt-3 divide-y">
            {statuses.map((s) => {
              const Icon = SOURCE_META[s.key].icon;
              return (
                <li key={s.key} className="flex items-center gap-3 py-2.5">
                  <Icon className="h-4 w-4 shrink-0" style={{ color: SOURCE_META[s.key].color }} aria-hidden />
                  <span className="text-sm font-medium">{s.label}</span>
                  <span className="min-w-0 flex-1 truncate text-sm text-muted-foreground" title={s.detail}>{s.detail}</span>
                  <span className="shrink-0 rounded-full border px-2 py-0.5 text-xs">{STATE_LABEL[s.state]}</span>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
```

- [ ] **Step 5: Quitar el formulario de `RoiView.tsx`**

En `RoiView`: eliminar el estado `draft`, `saveStatus`, el `useEffect` que resetea `saveStatus`, `handleSave`, los componentes `Field`/`DateField`, los inputs de montos y fechas y el bloque del botón Guardar, y los imports que queden sin uso (`Check`, `Save`, `saveRoiSettings`). `fetchRoiSettings().then(setSettings)` se mantiene. El bloque "Parametrización" queda solo con el `select` "Acotar a", y debajo del título agrega:

```tsx
        <p className="text-sm text-muted-foreground">
          Los montos de tu plan y la tarifa por hora se editan en{" "}
          <Link to={withSource("/configuracion", search)} className="text-link underline-offset-4 hover:underline">Configuración</Link>.
        </p>
```

con `import { Link, useLocation } from "react-router-dom";`, `import { withSource } from "@/lib/routes";` y `const { search } = useLocation();` al inicio del componente. Si `settings` tiene ambos costos en `null`, las tarjetas ya muestran su estado sin plan; no cambies la lógica de cálculo (`computeSourceRoi`).

- [ ] **Step 6: Verificar y commit**

Run (en `frontend/`): `npm test && npm run build && npm run lint` → OK.

```bash
git add frontend/src/components/SettingsForm.tsx frontend/src/views/SettingsView.tsx frontend/src/lib/settings.ts frontend/src/lib/settings.test.ts frontend/src/components/RoiView.tsx
git commit -m "feat(frontend): vista de Configuración con el plan y el estado por fuente"
```

---

### Task 9: Rutas nuevas, fuente como parámetro global y shell (sidebar + vistas)

**Files:**
- Modify (reescritura): `frontend/src/lib/routes.ts`, `frontend/src/lib/routes.test.ts`, `frontend/src/hooks/useDashboardRoute.ts`, `frontend/src/App.tsx`, `frontend/src/components/Sidebar.tsx`
- Create: `frontend/src/lib/projects.ts`, `frontend/src/lib/projects.test.ts`, `frontend/src/views/ActivityView.tsx`, `frontend/src/views/SpendView.tsx`, `frontend/src/views/ProjectsView.tsx`
- Modify (tipos): `frontend/src/lib/sessions.ts`, `frontend/src/components/TrendChart.tsx`, `frontend/src/components/SessionDetail.tsx`, `frontend/src/components/ProjectDetailSheet.tsx` — cambiar `SectionKey` por `SourceKey` (de `@/lib/sources`) y borrar las ramas `"roi"`.

**Interfaces:**
- Consumes: `SOURCE_KEYS`, `SourceKey`, `SOURCE_PARAM`, `COMPARE_PARAM`, `withQuery`, `withSource` (Task 6), `HomeView` (Task 7), `SettingsView` (Task 8).
- Produces:
  - `lib/routes.ts`: `VIEW_KEYS`, `ViewKey = "home"|"activity"|"spend"|"roi"|"projects"|"settings"`, `DAY_PARAM`, `PROJECT_PARAM`, `DashboardLocation { view; client }`, `parsePath(pathname) -> DashboardLocation | null`, `viewPath(view, client?) -> string`, `parseSource(slug|null) -> SourceKey`, `sourceSlug(SourceKey) -> string|null`, `legacyRedirect(pathname, search) -> string|null`, `searchForSource(search, source) -> string` (sin `?`), `promptPath(pathname) -> string`, más lo de Task 6.
  - `hooks/useDashboardRoute.ts`: `{ view, client, valid, redirect, source, compare, selectedDate, selectedProject, setSelectedDate, setSelectedProject, setSource, setCompare }`.
  - `lib/projects.ts`: `projectsFor(sources, combined, source: SourceKey, client: string | null): Record<string, ProjectUsage>`.
  - Cada vista renderiza su propio `<h1>`: "Actividad", "Gasto", "ROI", "Proyectos" (o el nombre del cliente), "Configuración"; el Inicio usa el mes.

- [ ] **Step 1: Reescribir `routes.test.ts` (falla)**

```ts
import { describe, expect, it } from "vitest";
import {
  VIEW_KEYS, legacyRedirect, parsePath, parseSource, promptPath, searchForSource, sourceSlug, viewPath, withSource,
} from "@/lib/routes";
import { SOURCE_KEYS } from "@/lib/sources";

describe("parsePath", () => {
  it("vistas nuevas", () => {
    expect(parsePath("/")).toEqual({ view: "home", client: null });
    expect(parsePath("/actividad")).toEqual({ view: "activity", client: null });
    expect(parsePath("/gasto")).toEqual({ view: "spend", client: null });
    expect(parsePath("/gasto/roi")).toEqual({ view: "roi", client: null });
    expect(parsePath("/proyectos")).toEqual({ view: "projects", client: null });
    expect(parsePath("/proyectos/Mi%20Cliente")).toEqual({ view: "projects", client: "Mi Cliente" });
    expect(parsePath("/configuracion")).toEqual({ view: "settings", client: null });
  });

  it("rutas desconocidas o mal codificadas → null", () => {
    expect(parsePath("/gasto/otra")).toBeNull();
    expect(parsePath("/proyectos/a/b")).toBeNull();
    expect(parsePath("/claude-code")).toBeNull();
    expect(parsePath("/proyectos/%E0%A4%A")).toBeNull();
  });

  it.each(VIEW_KEYS)("viewPath(%s) ida y vuelta", (view) => {
    expect(parsePath(viewPath(view))).toEqual({ view, client: null });
  });

  it("viewPath de cliente ida y vuelta", () => {
    expect(parsePath(viewPath("projects", "A/B & C"))).toEqual({ view: "projects", client: "A/B & C" });
  });
});

describe("fuente como parámetro", () => {
  it.each(SOURCE_KEYS)("parseSource(sourceSlug(%s)) ida y vuelta", (key) => {
    expect(parseSource(sourceSlug(key))).toBe(key);
  });
  it("slug desconocido o ausente → all", () => {
    expect(parseSource(null)).toBe("all");
    expect(parseSource("claude_code")).toBe("all");
  });
  it("cambiar la fuente limpia comparar y día, y conserva el resto", () => {
    expect(searchForSource("?comparar=2026-07&dia=2026-09-01&proyecto=%2Fa", "codex")).toBe("proyecto=%2Fa&fuente=codex");
    expect(searchForSource("?fuente=codex", "all")).toBe("");
  });
});

describe("redirecciones legadas", () => {
  it("fuentes → /gasto?fuente=", () => {
    expect(legacyRedirect("/claude-code", "")).toBe("/gasto?fuente=claude-code");
    expect(legacyRedirect("/openrouter", "?dia=2026-09-01")).toBe("/gasto?dia=2026-09-01&fuente=openrouter");
  });
  it("roi y cliente conservan la query", () => {
    expect(legacyRedirect("/roi", "?fuente=codex")).toBe("/gasto/roi?fuente=codex");
    expect(legacyRedirect("/cliente/Mi%20Cliente", "?proyecto=%2Fa")).toBe("/proyectos/Mi%20Cliente?proyecto=%2Fa");
  });
  it("rutas vigentes no redirigen", () => {
    expect(legacyRedirect("/gasto", "")).toBeNull();
    expect(legacyRedirect("/", "")).toBeNull();
  });
});

describe("withSource", () => {
  it("conserva ?fuente= de la URL actual y no pisa uno explícito", () => {
    expect(withSource("/actividad?dia=2026-09-27", "?fuente=codex&dia=2026-01-01")).toBe("/actividad?dia=2026-09-27&fuente=codex");
    expect(withSource("/gasto?fuente=claude-code", "?fuente=codex")).toBe("/gasto?fuente=claude-code");
    expect(withSource("/configuracion", "")).toBe("/configuracion");
  });
});

describe("promptPath", () => {
  it("ruta de la vista estilo shell", () => {
    expect(promptPath("/")).toBe("~");
    expect(promptPath("/gasto/roi")).toBe("~/gasto/roi");
    expect(promptPath("/proyectos/Mi%20Cliente")).toBe("~/proyectos/Mi Cliente");
  });
});
```

`frontend/src/lib/projects.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { ProjectUsage, UsageSnapshot } from "@/lib/api";
import { projectsFor } from "@/lib/projects";

const usage = (cost: number) => ({ total_tokens: 10, cost, messages: 1, session_count: 1 }) as UsageSnapshot["sources"]["codex"][string];
const combined: Record<string, ProjectUsage> = {
  "/home/u/DEV/A/x": { total_tokens: 20, cost: 3, messages: 2, session_count: 2, by_source: ["claude_code", "codex"] },
  "/home/u/DEV/B/y": { total_tokens: 5, cost: 1, messages: 1, session_count: 1, by_source: ["claude_code"] },
};
const sources = {
  claude_code: {}, codex: { "/home/u/DEV/A/x": usage(2) }, opencode: {}, hermes: {},
  openrouter: { unavailable: false, models: { "m-1": { tokens: 7, cost: 4, requests: 3 } } },
} as UsageSnapshot["sources"];

describe("projectsFor", () => {
  it("all usa la vista combinada y filtra por cliente", () => {
    expect(Object.keys(projectsFor(sources, combined, "all", null))).toHaveLength(2);
    expect(Object.keys(projectsFor(sources, combined, "all", "B"))).toEqual(["/home/u/DEV/B/y"]);
  });
  it("una fuente usa sus propios proyectos", () => {
    expect(projectsFor(sources, combined, "codex", null)["/home/u/DEV/A/x"]).toMatchObject({ cost: 2, by_source: ["codex"] });
  });
  it("OpenRouter agrupa por modelo y sin datos devuelve vacío", () => {
    expect(projectsFor(sources, combined, "openrouter", null)["m-1"]).toMatchObject({ total_tokens: 7, cost: 4, messages: 3 });
    expect(projectsFor(null, null, "all", null)).toEqual({});
  });
});
```

Run: `npm test` → FAIL.

- [ ] **Step 2: Reescribir `lib/routes.ts`**

```ts
/**
 * Estado de navegación ↔ URL. La URL es la única fuente de verdad: un enlace o una
 * recarga reproducen exactamente la misma vista.
 *
 *   /                        → Inicio (briefing)
 *   /actividad               → tendencia + sesiones del día
 *   /gasto, /gasto/roi       → Gasto y ROI
 *   /proyectos[/<cliente>]   → proyectos agrupados por cliente
 *   /configuracion           → plan y estado de fuentes
 *   ?fuente=<slug>           → filtro global de fuente (ausente = todas, sin OpenRouter)
 *   ?comparar=YYYY-MM        → mes comparado en el Inicio
 *   ?dia=YYYY-MM-DD          → día seleccionado en la tendencia / sesiones
 *   ?proyecto=<ruta>         → panel de detalle de proyecto abierto
 */
import type { SourceKey } from "@/lib/sources";

export const VIEW_KEYS = ["home", "activity", "spend", "roi", "projects", "settings"] as const;
export type ViewKey = (typeof VIEW_KEYS)[number];

export const SOURCE_PARAM = "fuente";
export const COMPARE_PARAM = "comparar";
export const DAY_PARAM = "dia";
export const PROJECT_PARAM = "proyecto";

const VIEW_PATH: Record<ViewKey, string> = {
  home: "/",
  activity: "/actividad",
  spend: "/gasto",
  roi: "/gasto/roi",
  projects: "/proyectos",
  settings: "/configuracion",
};

const SOURCE_SLUG: Record<Exclude<SourceKey, "all">, string> = {
  claude_code: "claude-code",
  codex: "codex",
  opencode: "opencode",
  hermes: "hermes",
  openrouter: "openrouter",
};

const SLUG_SOURCE = Object.fromEntries(
  Object.entries(SOURCE_SLUG).map(([key, slug]) => [slug, key as SourceKey]),
) as Record<string, SourceKey>;

export interface DashboardLocation {
  view: ViewKey;
  client: string | null;
}

/** Segmentos decodificados; null si la codificación está rota (%E0%A4%A). */
function segments(pathname: string): string[] | null {
  try {
    return pathname.split("/").filter(Boolean).map(decodeURIComponent);
  } catch {
    return null;
  }
}

/** null = ruta desconocida (el llamador redirige a "/"). */
export function parsePath(pathname: string): DashboardLocation | null {
  const parts = segments(pathname);
  if (!parts) return null;
  const [head, ...rest] = parts;
  if (parts.length === 0) return { view: "home", client: null };
  if (head === "actividad" && rest.length === 0) return { view: "activity", client: null };
  if (head === "gasto" && rest.length === 0) return { view: "spend", client: null };
  if (head === "gasto" && rest.length === 1 && rest[0] === "roi") return { view: "roi", client: null };
  if (head === "proyectos" && rest.length === 0) return { view: "projects", client: null };
  if (head === "proyectos" && rest.length === 1) return { view: "projects", client: rest[0] };
  if (head === "configuracion" && rest.length === 0) return { view: "settings", client: null };
  return null;
}

export function viewPath(view: ViewKey, client?: string | null): string {
  if (view === "projects" && client) return `/proyectos/${encodeURIComponent(client)}`;
  return VIEW_PATH[view];
}

export function parseSource(slug: string | null): SourceKey {
  return (slug && SLUG_SOURCE[slug]) || "all";
}

export function sourceSlug(source: SourceKey): string | null {
  return source === "all" ? null : SOURCE_SLUG[source];
}

export function withQuery(path: string, params: URLSearchParams): string {
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

/** Enlace interno que conserva el filtro global ?fuente= de la URL actual. */
export function withSource(target: string, search: string): string {
  const current = new URLSearchParams(search).get(SOURCE_PARAM);
  const [path, query = ""] = target.split("?");
  const params = new URLSearchParams(query);
  if (current && !params.has(SOURCE_PARAM)) params.set(SOURCE_PARAM, current);
  return withQuery(path, params);
}

/** Query tras cambiar de fuente: el mes comparado y el día dependen de la fuente, se limpian. */
export function searchForSource(search: string, source: SourceKey): string {
  const params = new URLSearchParams(search);
  params.delete(COMPARE_PARAM);
  params.delete(DAY_PARAM);
  params.delete(SOURCE_PARAM);
  const slug = sourceSlug(source);
  if (slug) params.set(SOURCE_PARAM, slug);
  return params.toString();
}

/** Rutas de la estructura anterior (una ruta por fuente, /roi, /cliente/<X>). */
export function legacyRedirect(pathname: string, search: string): string | null {
  const parts = segments(pathname);
  if (!parts) return null;
  const params = new URLSearchParams(search);
  if (parts.length === 1 && SLUG_SOURCE[parts[0]]) {
    params.set(SOURCE_PARAM, parts[0]);
    return withQuery("/gasto", params);
  }
  if (parts.length === 1 && parts[0] === "roi") return withQuery("/gasto/roi", params);
  if (parts.length === 2 && parts[0] === "cliente") return withQuery(viewPath("projects", parts[1]), params);
  return null;
}

/** "ai-monitor:<esto>$" en la barra superior. */
export function promptPath(pathname: string): string {
  const parts = segments(pathname) ?? [];
  return parts.length === 0 ? "~" : `~/${parts.join("/")}`;
}
```

- [ ] **Step 3: `lib/projects.ts`** (lógica movida de `App.projectsForSection`)

```ts
import type { ProjectUsage, UsageSnapshot } from "@/lib/api";
import { clientOf } from "@/lib/clients";
import type { SourceKey } from "@/lib/sources";

/** Proyectos (o modelos, en OpenRouter) para una fuente, opcionalmente acotados a un cliente. */
export function projectsFor(
  sources: UsageSnapshot["sources"] | null,
  combined: Record<string, ProjectUsage> | null,
  source: SourceKey,
  client: string | null,
): Record<string, ProjectUsage> {
  if (!sources || !combined) return {};

  let result: Record<string, ProjectUsage>;
  if (source === "all") {
    result = combined;
  } else if (source === "openrouter") {
    const or = sources.openrouter;
    if (!or || or.unavailable || !or.models) return {};
    return Object.fromEntries(
      Object.entries(or.models).map(([model, v]) => [
        model,
        { total_tokens: v.tokens, cost: v.cost, messages: v.requests, session_count: v.requests, by_source: ["openrouter"] },
      ]),
    );
  } else {
    result = Object.fromEntries(
      Object.entries(sources[source]).map(([name, v]) => [
        name,
        { total_tokens: v.total_tokens, cost: v.cost, messages: v.messages, session_count: v.session_count, by_source: [source] },
      ]),
    );
  }

  if (!client) return result;
  return Object.fromEntries(Object.entries(result).filter(([path]) => clientOf(path) === client));
}
```

- [ ] **Step 4: `hooks/useDashboardRoute.ts`**

```ts
import { useCallback } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import {
  COMPARE_PARAM, DAY_PARAM, PROJECT_PARAM, SOURCE_PARAM, legacyRedirect, parsePath, parseSource, searchForSource,
  type DashboardLocation,
} from "@/lib/routes";
import type { SourceKey } from "@/lib/sources";

export interface DashboardRoute extends DashboardLocation {
  /** false si la ruta no existe; App redirige a "/". */
  valid: boolean;
  /** Destino de una ruta de la estructura anterior, o null. */
  redirect: string | null;
  source: SourceKey;
  compare: string | null;
  selectedDate: string | null;
  selectedProject: string | null;
  setSelectedDate: (date: string | null) => void;
  setSelectedProject: (project: string | null) => void;
  setSource: (source: SourceKey) => void;
  setCompare: (month: string | null) => void;
}

export function useDashboardRoute(): DashboardRoute {
  const { pathname, search, state } = useLocation();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const parsed = parsePath(pathname);

  const setParam = useCallback(
    (key: string, value: string | null, replace: boolean, navState?: unknown) => {
      setParams((prev) => {
        const next = new URLSearchParams(prev);
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      }, { replace, state: navState });
    },
    [setParams],
  );

  // El día y el mes comparado reemplazan la entrada del historial (explorar no debe
  // llenar el botón "Atrás"); abrir un proyecto sí la empuja, de modo que "Atrás"
  // cierra el panel de detalle —lo esperable en móvil—.
  const setSelectedDate = useCallback((date: string | null) => setParam(DAY_PARAM, date, true), [setParam]);
  const setCompare = useCallback((month: string | null) => setParam(COMPARE_PARAM, month, true), [setParam]);
  const setSource = useCallback(
    (source: SourceKey) => setParams(new URLSearchParams(searchForSource(search, source)), { replace: true }),
    [search, setParams],
  );
  const setSelectedProject = useCallback(
    (project: string | null) => {
      if (project) {
        setParam(PROJECT_PARAM, project, false, { openedProject: true });
      } else if ((state as { openedProject?: boolean } | null)?.openedProject) {
        navigate(-1);
      } else {
        setParam(PROJECT_PARAM, null, true);
      }
    },
    [navigate, setParam, state],
  );

  return {
    view: parsed?.view ?? "home",
    client: parsed?.client ?? null,
    valid: parsed !== null,
    redirect: parsed ? null : legacyRedirect(pathname, search),
    source: parseSource(params.get(SOURCE_PARAM)),
    compare: params.get(COMPARE_PARAM),
    selectedDate: params.get(DAY_PARAM),
    selectedProject: params.get(PROJECT_PARAM),
    setSelectedDate,
    setSelectedProject,
    setSource,
    setCompare,
  };
}
```

- [ ] **Step 5: Cambiar `SectionKey` por `SourceKey` en componentes existentes**

- `lib/sessions.ts`: `import type { SourceKey } from "@/lib/sources";`, parámetro `section: SourceKey` y `const sourceKeys = section === "all" ? SESSION_SOURCES : section === "openrouter" ? [] : ([section] as const);`.
- `TrendChart.tsx`: `section: SourceKey`; borrar `if (section === "roi") return null;`; `buildSeries(..., section: SourceKey, ...)`.
- `SessionDetail.tsx`, `ProjectDetailSheet.tsx`: `section: SourceKey` (import desde `@/lib/sources`).

Run: `grep -rn "SectionKey\|sectionPath\|clientPath\|SECTION_KEYS" frontend/src` → solo deben quedar coincidencias en archivos que reescribes en los pasos 6–8 (App, Sidebar); al terminar el paso 8, ninguna.

- [ ] **Step 6: Vistas**

`views/ActivityView.tsx`:

```tsx
import { Suspense, lazy } from "react";
import { SessionDetail } from "@/components/SessionDetail";
import { SectionFallback } from "@/views/SectionFallback";
import type { UsageSnapshot } from "@/lib/api";
import type { SourceKey } from "@/lib/sources";

const TrendChart = lazy(() => import("@/components/TrendChart").then((m) => ({ default: m.TrendChart })));

interface ActivityViewProps {
  source: SourceKey;
  sources: UsageSnapshot["sources"] | null;
  selectedDate: string | null;
  onSelectDate: (date: string | null) => void;
  onSelectProject: (project: string | null) => void;
}

export function ActivityView({ source, sources, selectedDate, onSelectDate, onSelectProject }: ActivityViewProps) {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Actividad</h1>
      <Suspense fallback={<SectionFallback label="Cargando tendencia" />}>
        <TrendChart section={source} selectedDate={selectedDate} onSelectDate={onSelectDate} />
      </Suspense>
      <SessionDetail
        sources={sources}
        section={source}
        clientFilter={null}
        selectedDate={selectedDate}
        onSelectDate={onSelectDate}
        onSelectProject={onSelectProject}
      />
    </div>
  );
}
```

`views/SectionFallback.tsx` (movido desde `App.tsx`):

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export function SectionFallback({ label }: { label: string }) {
  return (
    <div aria-busy="true" aria-label={label} className="space-y-3 rounded-xl border bg-card p-5">
      <Skeleton className="h-5 w-56" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}
```

`views/SpendView.tsx`:

```tsx
import { Suspense, lazy } from "react";
import { Link, useLocation } from "react-router-dom";
import { KpiCards } from "@/components/KpiCards";
import { ProjectTable } from "@/components/ProjectTable";
import { SectionFallback } from "@/views/SectionFallback";
import type { ProjectUsage, UsageSnapshot } from "@/lib/api";
import { projectsFor } from "@/lib/projects";
import { withSource } from "@/lib/routes";
import type { SourceKey } from "@/lib/sources";
import { cn } from "@/lib/utils";

const TrendChart = lazy(() => import("@/components/TrendChart").then((m) => ({ default: m.TrendChart })));
const RoiView = lazy(() => import("@/components/RoiView").then((m) => ({ default: m.RoiView })));

const TABS = [
  { key: "spend", path: "/gasto", label: "Gasto" },
  { key: "roi", path: "/gasto/roi", label: "ROI" },
] as const;

interface SpendViewProps {
  tab: "spend" | "roi";
  source: SourceKey;
  sources: UsageSnapshot["sources"] | null;
  combined: Record<string, ProjectUsage> | null;
  selectedDate: string | null;
  onSelectDate: (date: string | null) => void;
  onSelectProject: (project: string | null) => void;
}

export function SpendView({ tab, source, sources, combined, selectedDate, onSelectDate, onSelectProject }: SpendViewProps) {
  const { search } = useLocation();
  const projects = projectsFor(sources, combined, source, null);
  const openRouterUnavailable = source === "openrouter" && sources?.openrouter?.unavailable;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">{tab === "roi" ? "ROI" : "Gasto"}</h1>
        <nav aria-label="Gasto y ROI" className="inline-flex rounded-lg border p-1">
          {TABS.map((t) => (
            <Link
              key={t.key}
              to={withSource(t.path, search)}
              aria-current={tab === t.key ? "page" : undefined}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm",
                tab === t.key ? "bg-muted font-medium shadow-[inset_0_-2px_0_var(--primary)]" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t.label}
            </Link>
          ))}
        </nav>
      </div>
      {tab === "roi" ? (
        <Suspense fallback={<SectionFallback label="Cargando ROI" />}>
          <RoiView sources={sources} />
        </Suspense>
      ) : (
        <>
          <Suspense fallback={<SectionFallback label="Cargando tendencia" />}>
            <TrendChart section={source} selectedDate={selectedDate} onSelectDate={onSelectDate} />
          </Suspense>
          {openRouterUnavailable ? (
            <div className="rounded-xl border bg-card p-6 text-sm text-muted-foreground">
              OpenRouter no disponible{sources?.openrouter?.reason ? `: ${sources.openrouter.reason}` : "."}
            </div>
          ) : (
            combined && (
              <>
                <KpiCards projects={projects} />
                <ProjectTable projects={projects} onSelectProject={source === "openrouter" ? undefined : onSelectProject} />
              </>
            )
          )}
        </>
      )}
    </div>
  );
}
```

`views/ProjectsView.tsx`:

```tsx
import { Link, useLocation } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { KpiCards } from "@/components/KpiCards";
import { ProjectTable } from "@/components/ProjectTable";
import { SectionFallback } from "@/views/SectionFallback";
import type { ProjectUsage, UsageSnapshot } from "@/lib/api";
import { groupProjectsByClient } from "@/lib/clients";
import { formatInt, formatUsd } from "@/lib/format";
import { projectsFor } from "@/lib/projects";
import { viewPath, withSource } from "@/lib/routes";
import type { SourceKey } from "@/lib/sources";

interface ProjectsViewProps {
  client: string | null;
  source: SourceKey;
  sources: UsageSnapshot["sources"] | null;
  combined: Record<string, ProjectUsage> | null;
  onSelectProject: (project: string | null) => void;
}

export function ProjectsView({ client, source, sources, combined, onSelectProject }: ProjectsViewProps) {
  const { search } = useLocation();

  if (source === "openrouter") {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold">Proyectos</h1>
        <p className="text-sm text-muted-foreground">
          OpenRouter agrupa el consumo por modelo, no por proyecto.{" "}
          <Link to={withSource("/gasto", search)} className="text-link underline-offset-4 hover:underline">Ver gasto por modelo</Link>
        </p>
      </div>
    );
  }
  if (!combined) return <SectionFallback label="Cargando proyectos" />;

  if (client) {
    const projects = projectsFor(sources, combined, source, client);
    return (
      <div className="space-y-6">
        <div className="space-y-1">
          <Link to={withSource(viewPath("projects"), search)} className="inline-flex items-center gap-1 text-sm text-link hover:underline">
            <ChevronLeft className="h-4 w-4" aria-hidden /> Proyectos
          </Link>
          <h1 className="text-xl font-semibold">{client}</h1>
        </div>
        <KpiCards projects={projects} />
        <ProjectTable projects={projects} onSelectProject={onSelectProject} />
      </div>
    );
  }

  const all = projectsFor(sources, combined, source, null);
  const clients = Object.entries(groupProjectsByClient(Object.keys(all)))
    .map(([name, paths]) => ({ name, count: paths.length, cost: paths.reduce((sum, p) => sum + all[p].cost, 0) }))
    .sort((a, b) => b.cost - a.cost);

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Proyectos</h1>
      {clients.length === 0 ? (
        <p className="text-sm text-muted-foreground">Sin proyectos para esta fuente.</p>
      ) : (
        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {clients.map((c) => (
            <li key={c.name}>
              <Link to={withSource(viewPath("projects", c.name), search)} className="card-interactive block rounded-xl border bg-card p-5">
                <p className="font-mono text-sm text-muted-foreground">{c.name}</p>
                <p className="mt-1 text-2xl font-bold tabular-nums">{formatUsd(c.cost)}</p>
                <p className="text-sm text-muted-foreground">{formatInt(c.count)} {c.count === 1 ? "proyecto" : "proyectos"}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 7: `components/Sidebar.tsx`**

```tsx
import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { Activity, FolderKanban, Home, Lightbulb, Settings, Wallet } from "lucide-react";
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupContent, SidebarHeader, SidebarMenu,
  SidebarMenuBadge, SidebarMenuButton, SidebarMenuItem, SidebarMenuSub, SidebarMenuSubButton, SidebarMenuSubItem, useSidebar,
} from "@/components/ui/sidebar";
import { viewPath, withSource, type ViewKey } from "@/lib/routes";

// Activo = borde interno cyan de 2px + superficie soft (spec §4.2).
const ACTIVE = "data-active:shadow-[inset_2px_0_0_var(--primary)]";

const NAV: { views: ViewKey[]; to: ViewKey; label: string; icon: typeof Home }[] = [
  { views: ["home"], to: "home", label: "Inicio", icon: Home },
  { views: ["activity"], to: "activity", label: "Actividad", icon: Activity },
  { views: ["spend", "roi"], to: "spend", label: "Gasto y ROI", icon: Wallet },
  { views: ["projects"], to: "projects", label: "Proyectos", icon: FolderKanban },
];

interface AppSidebarProps {
  view: ViewKey;
  activeClient: string | null;
  clients: string[];
}

export function AppSidebar({ view, activeClient, clients }: AppSidebarProps) {
  const location = useLocation();
  const { isMobile, setOpenMobile } = useSidebar();
  const href = (to: string) => withSource(to, location.search);

  // En móvil el sidebar es un Sheet: navegar lo cierra para mostrar el contenido.
  useEffect(() => {
    if (isMobile) setOpenMobile(false);
  }, [location.pathname, location.search, isMobile, setOpenMobile]);

  return (
    <Sidebar>
      <SidebarHeader className="h-16 flex-row items-center gap-2 border-b px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[image:var(--gradient-brand)] text-primary-foreground">
          <Activity className="h-4 w-4" aria-hidden />
        </div>
        <span className="bg-[image:var(--gradient-brand)] bg-clip-text font-extrabold tracking-tight text-transparent">ai-monitor</span>
      </SidebarHeader>

      <SidebarContent>
        <nav aria-label="Navegación principal" className="contents">
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                {NAV.map((item) => {
                  const isActive = item.views.includes(view) && !(item.to === "projects" && activeClient);
                  return (
                    <SidebarMenuItem key={item.to}>
                      <SidebarMenuButton
                        isActive={item.views.includes(view)}
                        className={ACTIVE}
                        render={<Link to={href(viewPath(item.to))} aria-current={isActive ? "page" : undefined} />}
                      >
                        <item.icon aria-hidden />
                        <span>{item.label}</span>
                      </SidebarMenuButton>
                      {item.to === "projects" && clients.length > 0 && (
                        <SidebarMenuSub>
                          {clients.map((client) => (
                            <SidebarMenuSubItem key={client}>
                              <SidebarMenuSubButton
                                size="sm"
                                isActive={activeClient === client}
                                render={
                                  <Link
                                    to={href(viewPath("projects", client))}
                                    aria-current={activeClient === client ? "page" : undefined}
                                  />
                                }
                              >
                                <span>{client}</span>
                              </SidebarMenuSubButton>
                            </SidebarMenuSubItem>
                          ))}
                        </SidebarMenuSub>
                      )}
                    </SidebarMenuItem>
                  );
                })}
                <SidebarMenuItem>
                  <SidebarMenuButton disabled aria-disabled="true">
                    <Lightbulb aria-hidden />
                    <span>Recomendaciones</span>
                  </SidebarMenuButton>
                  <SidebarMenuBadge>pronto</SidebarMenuBadge>
                </SidebarMenuItem>
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </nav>
      </SidebarContent>

      <SidebarFooter className="border-t">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              isActive={view === "settings"}
              className={ACTIVE}
              render={<Link to={href(viewPath("settings"))} aria-current={view === "settings" ? "page" : undefined} />}
            >
              <Settings aria-hidden />
              <span>Configuración</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
```

Nota: `SidebarMenuBadge` usa `[&>span:last-child]:truncate`; si "pronto" se corta, ajusta con `className="text-muted-foreground"` y verifica en la captura de Task 11. Si `SidebarMenuButton` no reenvía `disabled` al botón, usa solo `aria-disabled="true"` (la clase `aria-disabled:pointer-events-none` ya lo bloquea).

- [ ] **Step 8: `App.tsx`**

```tsx
import { Navigate } from "react-router-dom";
import { useUsageStream } from "@/hooks/useUsageStream";
import { useDashboardRoute } from "@/hooks/useDashboardRoute";
import { AppSidebar } from "@/components/Sidebar";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { ProjectDetailSheet } from "@/components/ProjectDetailSheet";
import { ThemeToggle } from "@/components/ThemeToggle";
import { HomeView } from "@/components/home/HomeView";
import { ActivityView } from "@/views/ActivityView";
import { SpendView } from "@/views/SpendView";
import { ProjectsView } from "@/views/ProjectsView";
import { SettingsView } from "@/views/SettingsView";
import { groupProjectsByClient } from "@/lib/clients";

export default function App() {
  const route = useDashboardRoute();
  const { sources, combined, connected } = useUsageStream();

  if (route.redirect) return <Navigate to={route.redirect} replace />;
  if (!route.valid) return <Navigate to="/" replace />;

  const clients = Object.keys(groupProjectsByClient(Object.keys(combined ?? {}))).sort();

  return (
    <SidebarProvider className="bg-background text-foreground">
      <AppSidebar view={route.view} activeClient={route.client} clients={clients} />
      <SidebarInset className="min-w-0">
        <header className="sticky top-0 z-10 flex h-16 items-center justify-between gap-3 border-b bg-background/80 px-4 backdrop-blur md:px-6">
          <SidebarTrigger className="-ml-1" />
          <div className="flex shrink-0 items-center gap-3">
            <span
              role="status"
              aria-live="polite"
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
                connected ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "bg-muted text-muted-foreground"
              }`}
            >
              <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-emerald-500 animate-pulse" : "bg-muted-foreground"}`} />
              {connected ? "En vivo" : "Conectando…"}
            </span>
            <ThemeToggle />
          </div>
        </header>
        {/* SidebarInset ya es el <main>; aquí un div para no anidar landmarks. */}
        <div key={route.view} className="dashboard-section w-full min-w-0 max-w-[1400px] flex-1 p-4 md:p-6">
          {route.view === "home" && (
            <HomeView source={route.source} compare={route.compare} onCompareChange={route.setCompare} refreshKey={sources} />
          )}
          {route.view === "activity" && (
            <ActivityView
              source={route.source}
              sources={sources}
              selectedDate={route.selectedDate}
              onSelectDate={route.setSelectedDate}
              onSelectProject={route.setSelectedProject}
            />
          )}
          {(route.view === "spend" || route.view === "roi") && (
            <SpendView
              tab={route.view}
              source={route.source}
              sources={sources}
              combined={combined}
              selectedDate={route.selectedDate}
              onSelectDate={route.setSelectedDate}
              onSelectProject={route.setSelectedProject}
            />
          )}
          {route.view === "projects" && (
            <ProjectsView
              client={route.client}
              source={route.source}
              sources={sources}
              combined={combined}
              onSelectProject={route.setSelectedProject}
            />
          )}
          {route.view === "settings" && <SettingsView sources={sources} />}
        </div>
      </SidebarInset>
      <ProjectDetailSheet
        sources={sources}
        section={route.source === "openrouter" ? "all" : route.source}
        project={route.selectedProject}
        onClose={() => route.setSelectedProject(null)}
      />
    </SidebarProvider>
  );
}
```

- [ ] **Step 9: Verificar y commit**

Run (en `frontend/`): `npm test && npm run build && npm run lint` → OK. Run: `grep -rn "SectionKey\|sectionPath\|clientPath" frontend/src` → sin resultados.

Prueba rápida manual con el servidor de desarrollo (`npm run dev` con `server.py` corriendo en 8420, o `npm run build` + `python3 server.py`): `/`, `/actividad`, `/gasto?fuente=codex`, `/claude-code` (debe terminar en `/gasto?fuente=claude-code`). La verificación completa es Task 11.

```bash
git add frontend/src
git commit -m "feat(frontend): rutas por pregunta con ?fuente= global, redirecciones legadas y nuevo sidebar"
```

---

### Task 10: Barra superior (prompt, chips de fuente, ⌘K, En vivo, tema)

**Files:**
- Create: `frontend/src/components/ui/command.tsx` (shadcn CLI), `frontend/src/components/TopBar.tsx`, `frontend/src/components/SourceFilter.tsx`, `frontend/src/components/CommandPalette.tsx`, `frontend/src/lib/commands.ts`, `frontend/src/lib/commands.test.ts`
- Modify: `frontend/src/App.tsx` (reemplazar el `<header>` por `<TopBar>`), `frontend/package.json`/lock (`cmdk`)

**Interfaces:**
- Consumes: `promptPath`, `withSource`, `viewPath`, `SOURCE_KEYS`, `SOURCE_META`, `collectSessions`, `groupProjectsByClient`, `clientOf`, `basename`, `formatDate`.
- Produces: `TopBar({ connected, source, onSourceChange, sources, combined })`; `buildCommandEntries(sources, combined): CommandEntry[]` con `CommandEntry = { id: string; group: "Vistas"|"Clientes"|"Proyectos"|"Sesiones"; label: string; hint?: string; to: string; keywords: string[] }`.

- [ ] **Step 1: Test que falla**

`frontend/src/lib/commands.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { ProjectUsage, UsageSnapshot } from "@/lib/api";
import { buildCommandEntries } from "@/lib/commands";

const combined: Record<string, ProjectUsage> = {
  "/home/u/DEV/ACME/app": { total_tokens: 1, cost: 1, messages: 1, session_count: 1, by_source: ["claude_code"] },
};
const sources = {
  claude_code: {
    "/home/u/DEV/ACME/app": {
      sessions_detail: [
        { session_id: "s1", tokens: 1, cost: 1, title: "Arreglar login", first_ts: null, last_ts: null, cwd: null, date: "2026-09-20" },
        { session_id: "s2", tokens: 1, cost: 1, title: null, first_ts: null, last_ts: null, cwd: null, date: "2026-09-21" },
      ],
    },
  },
  codex: {}, opencode: {}, hermes: {}, openrouter: { unavailable: true },
} as unknown as UsageSnapshot["sources"];

describe("buildCommandEntries", () => {
  const entries = buildCommandEntries(sources, combined);
  const byGroup = (g: string) => entries.filter((e) => e.group === g);

  it("incluye las seis vistas", () => {
    expect(byGroup("Vistas").map((e) => e.to)).toEqual(["/", "/actividad", "/gasto", "/gasto/roi", "/proyectos", "/configuracion"]);
  });
  it("clientes y proyectos enlazan a /proyectos", () => {
    expect(byGroup("Clientes")[0]).toMatchObject({ label: "ACME", to: "/proyectos/ACME" });
    expect(byGroup("Proyectos")[0]).toMatchObject({
      label: "app", hint: "/home/u/DEV/ACME/app", to: "/proyectos/ACME?proyecto=%2Fhome%2Fu%2FDEV%2FACME%2Fapp",
    });
  });
  it("solo sesiones con título, enlazadas a su día", () => {
    expect(byGroup("Sesiones")).toHaveLength(1);
    expect(byGroup("Sesiones")[0]).toMatchObject({ label: "Arreglar login", to: "/actividad?dia=2026-09-20" });
  });
  it("sin snapshot solo quedan las vistas", () => {
    expect(buildCommandEntries(null, null).every((e) => e.group === "Vistas")).toBe(true);
  });
  it("ids únicos", () => {
    expect(new Set(entries.map((e) => e.id)).size).toBe(entries.length);
  });
});
```

Run: `npm test` → FAIL.

- [ ] **Step 2: `lib/commands.ts`**

```ts
import type { ProjectUsage, UsageSnapshot } from "@/lib/api";
import { clientOf, groupProjectsByClient } from "@/lib/clients";
import { formatDate } from "@/lib/format";
import { viewPath, type ViewKey } from "@/lib/routes";
import { collectSessions } from "@/lib/sessions";
import { SOURCE_META } from "@/lib/sources";
import { basename } from "@/lib/tree";

export const COMMAND_GROUPS = ["Vistas", "Clientes", "Proyectos", "Sesiones"] as const;

export interface CommandEntry {
  id: string;
  group: (typeof COMMAND_GROUPS)[number];
  label: string;
  hint?: string;
  to: string;
  keywords: string[];
}

const VIEWS: { view: ViewKey; label: string; keywords: string[] }[] = [
  { view: "home", label: "Inicio", keywords: ["briefing", "resumen"] },
  { view: "activity", label: "Actividad", keywords: ["tendencia", "sesiones", "días"] },
  { view: "spend", label: "Gasto", keywords: ["costo", "kpi"] },
  { view: "roi", label: "ROI", keywords: ["suscripción", "ahorro"] },
  { view: "projects", label: "Proyectos", keywords: ["clientes"] },
  { view: "settings", label: "Configuración", keywords: ["plan", "tarifa", "fuentes"] },
];

const MAX_SESSIONS = 500;

/** Índice del ⌘K sobre el snapshot en memoria (sin backend). */
export function buildCommandEntries(
  sources: UsageSnapshot["sources"] | null,
  combined: Record<string, ProjectUsage> | null,
): CommandEntry[] {
  const entries: CommandEntry[] = VIEWS.map((v) => ({
    id: `view:${v.view}`, group: "Vistas", label: v.label, to: viewPath(v.view), keywords: v.keywords,
  }));

  const paths = Object.keys(combined ?? {}).sort();
  for (const client of Object.keys(groupProjectsByClient(paths)).sort()) {
    entries.push({ id: `client:${client}`, group: "Clientes", label: client, to: viewPath("projects", client), keywords: [] });
  }
  for (const path of paths) {
    entries.push({
      id: `project:${path}`,
      group: "Proyectos",
      label: basename(path),
      hint: path,
      to: `${viewPath("projects", clientOf(path))}?proyecto=${encodeURIComponent(path)}`,
      keywords: [path, clientOf(path)],
    });
  }

  const sessions = collectSessions(sources, "all")
    .filter((s) => s.title && s.date)
    .sort((a, b) => (b.date ?? "").localeCompare(a.date ?? ""))
    .slice(0, MAX_SESSIONS);
  for (const s of sessions) {
    entries.push({
      id: `session:${s.source}:${s.session_id}`,
      group: "Sesiones",
      label: s.title as string,
      hint: `${SOURCE_META[s.source].label} · ${formatDate(s.date as string)}`,
      to: `/actividad?dia=${s.date}`,
      keywords: [s.project],
    });
  }
  return entries;
}
```

Run: `npm test` → PASS.

- [ ] **Step 3: Componente `Command` de shadcn**

Run (en `frontend/`): `npx shadcn@latest add command`. Debe crear `src/components/ui/command.tsx` (y `dialog.tsx` si hace falta) e instalar `cmdk`. Revisa el archivo generado: exporta `CommandDialog`, `CommandInput`, `CommandList`, `CommandEmpty`, `CommandGroup`, `CommandItem`. Si el CLI falla (sin red o conflicto de estilo con base-ui), instala `cmdk` con `npm install cmdk` y crea `components/ui/command.tsx` como envoltura mínima de `cmdk` (`Command`, `Command.Input`, `Command.List`, `Command.Empty`, `Command.Group`, `Command.Item`) dentro de un `Dialog` construido con `@base-ui/react` (mismo patrón que `ui/sheet.tsx`), con clases de los tokens (`bg-popover`, `border`, `rounded-xl`, `shadow-glow`).

- [ ] **Step 4: `CommandPalette.tsx`**

```tsx
import { useMemo } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList,
} from "@/components/ui/command";
import type { ProjectUsage, UsageSnapshot } from "@/lib/api";
import { COMMAND_GROUPS, buildCommandEntries } from "@/lib/commands";
import { withSource } from "@/lib/routes";

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sources: UsageSnapshot["sources"] | null;
  combined: Record<string, ProjectUsage> | null;
}

export function CommandPalette({ open, onOpenChange, sources, combined }: CommandPaletteProps) {
  const navigate = useNavigate();
  const { search } = useLocation();
  const entries = useMemo(() => buildCommandEntries(sources, combined), [sources, combined]);

  const go = (to: string) => {
    onOpenChange(false);
    navigate(withSource(to, search));
  };

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange} title="Buscar" description="Vistas, clientes, proyectos y sesiones">
      <CommandInput placeholder="Buscar vistas, clientes, proyectos o sesiones…" />
      <CommandList>
        <CommandEmpty>Sin resultados.</CommandEmpty>
        {COMMAND_GROUPS.map((group) => {
          const items = entries.filter((e) => e.group === group);
          if (items.length === 0) return null;
          return (
            <CommandGroup key={group} heading={group}>
              {items.map((e) => (
                <CommandItem key={e.id} value={`${e.label} ${e.keywords.join(" ")} ${e.id}`} onSelect={() => go(e.to)}>
                  <span className="truncate">{e.label}</span>
                  {e.hint && <span className="ml-auto truncate pl-3 font-mono text-xs text-muted-foreground">{e.hint}</span>}
                </CommandItem>
              ))}
            </CommandGroup>
          );
        })}
      </CommandList>
    </CommandDialog>
  );
}
```

Si el `CommandDialog` generado no acepta `title`/`description`, pásalos como su API lo requiera (el diálogo debe tener nombre accesible "Buscar").

- [ ] **Step 5: `SourceFilter.tsx`**

```tsx
import { SOURCE_KEYS, SOURCE_META, type SourceKey } from "@/lib/sources";
import { cn } from "@/lib/utils";

const OPTIONS = SOURCE_KEYS.map((key) => ({ key, label: key === "all" ? "Todas" : SOURCE_META[key].label }));

interface SourceFilterProps {
  value: SourceKey;
  onChange: (source: SourceKey) => void;
}

/** Chips en escritorio; select compacto en pantallas angostas (spec §4.5). */
export function SourceFilter({ value, onChange }: SourceFilterProps) {
  return (
    <>
      <div role="group" aria-label="Filtrar por fuente" className="hidden items-center gap-1 xl:flex">
        {OPTIONS.map((o) => (
          <button
            key={o.key}
            type="button"
            aria-pressed={value === o.key}
            onClick={() => onChange(o.key)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors",
              value === o.key ? "border-primary bg-primary/10 font-medium text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {o.key !== "all" && <span aria-hidden className="h-2 w-2 rounded-full" style={{ background: SOURCE_META[o.key].color }} />}
            {o.label}
          </button>
        ))}
      </div>
      <label className="xl:hidden">
        <span className="sr-only">Filtrar por fuente</span>
        <select
          value={value}
          onChange={(e) => onChange(e.target.value as SourceKey)}
          className="max-w-[9.5rem] rounded-lg border bg-background px-2 py-1.5 text-sm"
        >
          {OPTIONS.map((o) => (
            <option key={o.key} value={o.key}>{o.label}</option>
          ))}
        </select>
      </label>
    </>
  );
}
```

- [ ] **Step 6: `TopBar.tsx`**

```tsx
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { Search } from "lucide-react";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { ThemeToggle } from "@/components/ThemeToggle";
import { CommandPalette } from "@/components/CommandPalette";
import { SourceFilter } from "@/components/SourceFilter";
import type { ProjectUsage, UsageSnapshot } from "@/lib/api";
import { promptPath } from "@/lib/routes";
import type { SourceKey } from "@/lib/sources";

interface TopBarProps {
  connected: boolean;
  source: SourceKey;
  onSourceChange: (source: SourceKey) => void;
  sources: UsageSnapshot["sources"] | null;
  combined: Record<string, ProjectUsage> | null;
}

export function TopBar({ connected, source, onSourceChange, sources, combined }: TopBarProps) {
  const { pathname } = useLocation();
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <header className="sticky top-0 z-10 flex h-16 items-center gap-2 border-b bg-background/80 px-4 backdrop-blur md:gap-3 md:px-6">
      <SidebarTrigger className="-ml-1" />
      <p className="hidden min-w-0 truncate font-mono text-sm text-muted-foreground sm:block">
        <span className="text-link">ai-monitor</span>:{promptPath(pathname)}$
      </p>
      <div className="ml-auto flex shrink-0 items-center gap-2">
        <SourceFilter value={source} onChange={onSourceChange} />
        <button
          type="button"
          onClick={() => setPaletteOpen(true)}
          aria-label="Buscar"
          aria-keyshortcuts="Meta+K Control+K"
          className="inline-flex h-8 items-center gap-2 rounded-lg border px-2 text-sm text-muted-foreground hover:text-foreground md:px-3"
        >
          <Search className="h-4 w-4" aria-hidden />
          <span className="hidden md:inline">Buscar</span>
          <kbd className="hidden rounded border bg-muted px-1.5 font-mono text-[10px] md:inline">⌘K</kbd>
        </button>
        <span
          role="status"
          aria-live="polite"
          className={`inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium ${
            connected ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "bg-muted text-muted-foreground"
          }`}
        >
          <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-emerald-500 animate-pulse" : "bg-muted-foreground"}`} />
          <span className="sr-only md:not-sr-only">{connected ? "En vivo" : "Conectando…"}</span>
        </span>
        <ThemeToggle />
      </div>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} sources={sources} combined={combined} />
    </header>
  );
}
```

- [ ] **Step 7: Usar `TopBar` en `App.tsx`**

Reemplazar el `<header>…</header>` completo por:

```tsx
        <TopBar
          connected={connected}
          source={route.source}
          onSourceChange={route.setSource}
          sources={sources}
          combined={combined}
        />
```

con `import { TopBar } from "@/components/TopBar";` y quitando los imports que queden sin uso (`SidebarTrigger`, `ThemeToggle`).

- [ ] **Step 8: Verificar y commit**

Run (en `frontend/`): `npm test && npm run build && npm run lint` → OK.

```bash
git add frontend/src frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): barra superior con prompt, filtro global de fuente y búsqueda ⌘K"
```

---

### Task 11: Verificación final (E2E, paleta, portabilidad, documentación)

**Files:**
- Create (temporal, fuera del repo): `<scratchpad>/e2e-briefing.mjs`
- Modify: `README.md` (sección del dashboard: rutas nuevas y dónde configurar el plan)

**Interfaces:**
- Consumes: todo lo anterior; servidor real en un puerto de prueba.

- [ ] **Step 1: Suites completas**

Run: `python3 -m unittest discover -s tests -v` → todo PASS.
Run (en `frontend/`): `npm test && npm run build && npm run lint` → OK.

- [ ] **Step 2: Levantar el servidor de prueba**

Run (en segundo plano, desde la raíz): `AI_MONITOR_PORT=8431 python3 server.py`. Espera a que `curl -s http://127.0.0.1:8431/api/briefing | head -c 300` devuelva JSON.

- [ ] **Step 3: Script E2E con Playwright (en el scratchpad, no en el repo)**

Usa el paquete `playwright` ya instalado en `frontend/node_modules` (ejecuta el script con `node` desde `frontend/` o con `NODE_PATH=frontend/node_modules`). Nunca uses `claude-in-chrome`. El script debe:

```js
import { chromium } from "playwright";

const BASE = "http://127.0.0.1:8431";
const browser = await chromium.launch();
const failures = [];
const check = (cond, msg) => { if (!cond) failures.push(msg); };

for (const scheme of ["light", "dark"]) {
  for (const width of [1440, 375]) {
    const page = await browser.newPage({ colorScheme: scheme, viewport: { width, height: 900 } });
    const errors = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    page.on("pageerror", (e) => errors.push(e.message));
    // El tema de la app se controla con la clase .dark (useTheme); fuerza el esquema elegido.
    await page.addInitScript((s) => localStorage.setItem("theme", s), scheme);

    const views = [["/", /de 20\d\d|Aún no hay historial/], ["/actividad", /Actividad/], ["/gasto", /Gasto/],
                   ["/gasto/roi", /ROI/], ["/proyectos", /Proyectos/], ["/configuracion", /Configuración/]];
    for (const [path, heading] of views) {
      await page.goto(BASE + path);
      await page.locator("h1").first().waitFor();
      check(heading.test(await page.locator("h1").first().innerText()), `${scheme}/${width} ${path}: h1 inesperado`);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
      check(!overflow, `${scheme}/${width} ${path}: scroll horizontal`);
      await page.screenshot({ path: `${process.env.SHOTS}/${scheme}-${width}${path.replaceAll("/", "_") || "_home"}.png`, fullPage: true });
    }

    for (const [from, to] of [["/claude-code", "/gasto?fuente=claude-code"], ["/roi", "/gasto/roi"],
                              ["/cliente/ACME", "/proyectos/ACME"], ["/no-existe", "/"]]) {
      await page.goto(BASE + from);
      await page.waitForURL((u) => u.pathname + u.search === to);
    }

    // Filtro persistente al navegar desde el sidebar / enlaces.
    await page.goto(BASE + "/gasto?fuente=codex");
    await page.goto(BASE + "/gasto?fuente=codex");
    if (width >= 1280) {
      await page.getByRole("link", { name: "Actividad" }).first().click();
      check(new URL(page.url()).searchParams.get("fuente") === "codex", `${scheme}/${width}: ?fuente= no persiste`);
    }

    // ⌘K
    await page.keyboard.press("Control+k");
    await page.getByPlaceholder(/Buscar vistas/).fill("Configuración");
    await page.keyboard.press("Enter");
    await page.waitForURL((u) => u.pathname === "/configuracion");

    check(errors.length === 0, `${scheme}/${width}: errores de consola: ${errors.join(" | ")}`);
    await page.close();
  }
}
await browser.close();
console.log(failures.length ? `FALLOS:\n${failures.join("\n")}` : "E2E OK");
process.exit(failures.length ? 1 : 0);
```

Ajusta la clave de `localStorage` a la que use `hooks/useTheme.ts` (léelo antes). A 375px el sidebar es un Sheet: la comprobación de persistencia de `?fuente=` desde el sidebar se hace solo en escritorio; en móvil verifica que el `select` de fuente existe (`page.getByLabel("Filtrar por fuente")`). Guarda las capturas en el scratchpad (`SHOTS`).

Run: `SHOTS=<scratchpad>/shots node <scratchpad>/e2e-briefing.mjs`
Expected: `E2E OK`. Revisa visualmente al menos las capturas de `/` en claro/oscuro a 1440 y 375 (Read de los PNG): cyan solo en interfaz, logotipo con gradiente, KPIs en una columna a 375px, "Atención ahora" con punto + ícono.

- [ ] **Step 4: Paleta**

Repite el validador de Task 5 Step 4 sobre los valores finales de `index.css` en ambos temas. Expected: sin FAIL de contraste de texto.

- [ ] **Step 5: Portabilidad**

Run: `git diff --name-only main...HEAD | xargs grep -nE "/home/jruedadev|DEV/JRDV" -- 2>/dev/null`
Expected: sin coincidencias (el spec y este plan pueden mencionar el nombre del repo, pero no rutas absolutas de la máquina; si aparecen en código o tests, corrígelas).

- [ ] **Step 6: README**

En la sección del dashboard interactivo del `README.md`, documentar la estructura nueva:

```markdown
### Estructura del dashboard

| Ruta | Qué responde |
|---|---|
| `/` Inicio | ¿Cómo voy este mes y qué debo mirar? KPIs contra el mismo tramo de un mes comparable (selector "Comparar con") y señales de "Atención ahora" |
| `/actividad` | ¿Qué pasó? Tendencia diaria y sesiones del día (`?dia=`) |
| `/gasto`, `/gasto/roi` | ¿Cuánto me cuesta? Gasto por proyecto (o por modelo en OpenRouter) y suscripción frente a API |
| `/proyectos` | ¿En qué proyectos? Agrupados por cliente (`~/DEV/<CLIENTE>/<proyecto>`) |
| `/configuracion` | Tu plan (costo mensual y fecha de inicio de la suscripción, tarifa por hora) y el estado de cada fuente |

El filtro de fuente es global (`?fuente=claude-code|codex|opencode|hermes|openrouter`) y se conserva al navegar; ⌘K / Ctrl+K busca vistas, clientes, proyectos y sesiones. Las rutas antiguas (`/claude-code`, `/roi`, `/cliente/<X>`…) redirigen a las nuevas.
```

- [ ] **Step 7: Detener el servidor de prueba y commit**

Detén el proceso de `server.py` en 8431.

```bash
git add README.md
git commit -m "docs: estructura del dashboard por preguntas y dónde configurar el plan"
```

No reinicies el servicio systemd `ai-monitor-server` sin preguntar al usuario.
