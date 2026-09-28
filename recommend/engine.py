"""Orquesta una corrida del motor (spec §3 y §5): lock → prompts (30 días) →
redacción → candidatos → LLM o solo léxico → heurística → señales de costo
→ store.apply_run en una transacción → registro de la corrida → liberar lock."""
import os
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone

import briefing
import history
from recommend import cluster as clustering
from recommend import cost, heuristics, llm, store
from recommend.prompts import ENGINE_DIR, read_all
from recommend.redact import redact

LOCK_PATH = os.path.expanduser("~/.local/share/ai-monitor/recommend.lock")
WINDOW_DAYS = 30
IMPACT_HIGH = 0.10
IMPACT_MEDIUM = 0.03
FRESH_LOCK_SECONDS = 10


class EngineBusy(Exception):
    """Ya hay una corrida viva (lock con un PID vivo)."""


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, OverflowError):
        return False
    return True


def lock_is_live(lock_path):
    try:
        with open(lock_path) as fh:
            content = fh.read().strip()
        age = time.time() - os.path.getmtime(lock_path)
    except OSError:
        return False  # desapareció entre medias: se reintenta
    if not content.isdigit():
        # Otro proceso acaba de crearlo y aún no escribió su PID.
        return age < FRESH_LOCK_SECONDS
    return _pid_alive(int(content))


def acquire_lock(lock_path=LOCK_PATH):
    os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
    for _ in range(3):
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            if lock_is_live(lock_path):
                raise EngineBusy() from None
            try:
                os.unlink(lock_path)
            except FileNotFoundError:
                pass
            continue
        with os.fdopen(fd, "w") as fh:
            fh.write(str(os.getpid()))
        return
    raise EngineBusy()


def release_lock(lock_path=LOCK_PATH):
    try:
        with open(lock_path) as fh:
            if fh.read().strip() != str(os.getpid()):
                return
        os.unlink(lock_path)
    except OSError:
        pass


def impact_for(tokens, total):
    share = tokens / total if total > 0 else 0
    if share >= IMPACT_HIGH:
        return "alto"
    if share >= IMPACT_MEDIUM:
        return "medio"
    return "bajo"


def load_session_tokens(db_path=None):
    """Tokens por sesión según los collectors, la misma fuente de verdad que el
    dashboard. Los collectors ya degradan solos si falta su archivo."""
    from collectors import claude_code, codex, hermes, opencode

    sources = {"claude_code": claude_code.collect(db_path=db_path), "codex": codex.collect(db_path=db_path),
               "opencode": opencode.collect(), "hermes": hermes.collect()}
    out = {}
    for source, projects in sources.items():
        for data in projects.values():
            for session in data.get("sessions_detail") or []:
                sid = session.get("session_id")
                if sid is None:
                    continue
                key = (source, str(sid))
                out[key] = out.get(key, 0) + int(session.get("tokens") or 0)
    return out


def _source_totals(project_rows, since, until):
    totals = {}
    for row in project_rows:
        if since <= row["date"] <= until:
            totals[row["source"]] = totals.get(row["source"], 0) + (row["tokens"] or 0)
    return totals


def _pattern_rec(c, texts, model, totals):
    generator = model if texts else "reglas"
    texts = texts or heuristics.recommend(c)
    total = sum(totals.get(source, 0) for source in c.sources)
    return {"tool": c.tool, "tokens": c.tokens, "pattern": texts["pattern"], "kind": texts["kind"],
            "description": texts["description"], "impact": impact_for(c.tokens, total),
            "evidence": c.evidence(), "draft": texts["draft"], "signature": sorted(c.signature),
            "generator": generator}


def _analyze(settings, db_path, today, prompt_overrides, session_tokens, runner, engine_dir):
    os.makedirs(engine_dir, exist_ok=True)
    since = (today - timedelta(days=WINDOW_DAYS - 1)).isoformat()
    raw, errors = read_all(since, prompt_overrides, engine_dir)
    prompts = [p._replace(text=redact(p.text)) for p in raw]
    if session_tokens is None:
        session_tokens = load_session_tokens(db_path)
    try:
        project_rows, model_rows, roi = briefing.load(db_path or history.DB_PATH_DEFAULT)
    except sqlite3.Error as exc:
        project_rows, model_rows, roi = [], [], {}
        errors.append(f"history: {exc}")

    fields = {"model": None, "attempts": 0, "llm_tokens": 0, "llm_cost": 0.0}
    texts, degraded = {}, False
    if settings["backend"] == "none":
        groups, degraded = clustering.lexical_clusters(prompts, session_tokens), True
    else:
        cands = clustering.candidates(prompts, session_tokens)
        groups = []
        if cands:
            result = llm.run_llm(cands, settings["backend"], settings["llm_chain"], runner=runner, cwd=engine_dir)
            fields.update(attempts=result["attempts"], llm_tokens=result["llm_tokens"], llm_cost=result["llm_cost"])
            errors.extend(result["errors"])
            if result["ok"]:
                fields["model"] = result["model"]
                by_id = {c.cluster_id: c for c in cands}
                grouped = llm.validate_groups(result["data"], list(by_id))
                merged = [clustering.merge([by_id[m] for m in members], gid) for gid, members in grouped.items()]
                groups = clustering.rank_final(merged)
                texts = llm.validate_recommendations(result["data"], set(grouped))
            else:
                groups, degraded = clustering.lexical_clusters(prompts, session_tokens), True

    totals = _source_totals(project_rows, since, today.isoformat())
    pattern_recs = [_pattern_rec(c, texts.get(c.cluster_id), fields["model"], totals) for c in groups]
    cost_recs = cost.cost_recommendations(project_rows, model_rows, roi, today)
    counts = store.apply_run(db_path, pattern_recs, cost_recs, now_iso())
    return {"status": "degraded" if degraded else "ok", **fields, "prompts": len(prompts),
            "clusters": len(groups), **counts, "error": "; ".join(errors)[:1000] or None}


def start(trigger, db_path=None, lock_path=LOCK_PATH):
    acquire_lock(lock_path)
    try:
        settings = store.get_engine_settings(db_path)
        run_id = store.start_run(db_path, trigger, settings["backend"], now_iso())
    except BaseException:
        release_lock(lock_path)
        raise
    return run_id, settings


def execute(run_id, settings, db_path=None, lock_path=LOCK_PATH, today=None, prompt_overrides=None,
            session_tokens=None, runner=llm.subprocess_runner, engine_dir=ENGINE_DIR):
    try:
        result = _analyze(settings, db_path, today or date.today(), prompt_overrides, session_tokens,
                          runner, engine_dir)
        status = result.pop("status")
        store.finish_run(db_path, run_id, status, now_iso(), **result)
        return status
    except Exception as exc:  # noqa: BLE001 — la corrida queda en error, nunca colgada en "corriendo"
        try:
            store.finish_run(db_path, run_id, "error", now_iso(), error=f"{type(exc).__name__}: {exc}"[:1000])
        except sqlite3.Error:
            pass
        return "error"
    finally:
        release_lock(lock_path)


def run(trigger, db_path=None, lock_path=LOCK_PATH, **kw):
    run_id, settings = start(trigger, db_path, lock_path)
    return run_id, execute(run_id, settings, db_path, lock_path, **kw)
