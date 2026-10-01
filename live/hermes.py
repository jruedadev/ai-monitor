"""Lector en vivo de Hermes (~/.hermes/state.db, solo lectura). Fechas en epoch segundos.
Nunca selecciona content, api_content, reasoning* ni display_*."""
import json
import os
import sqlite3

from live.model import OFFICE_WINDOW_S, SessionFacts, SourceUnavailable

BATCH = 500


def _chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _calls(raw):
    """[(id, nombre)] de un JSON de tool_calls; lo que no encaje se ignora."""
    try:
        data = json.loads(raw) if raw else None
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    out = []
    for call in data:
        if not isinstance(call, dict):
            continue
        fn = call.get("function")
        name = fn.get("name") if isinstance(fn, dict) else call.get("name")
        if isinstance(call.get("id"), str) and isinstance(name, str):
            out.append((call["id"], name))
    return out


def read(now, db_path=None):
    path = db_path or os.path.expanduser("~/.hermes/state.db")
    if not os.path.isfile(path):
        raise SourceUnavailable(path)
    since = now - OFFICE_WINDOW_S
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            sessions = con.execute(
                "SELECT id, cwd, last_activity_at, ended_at FROM sessions WHERE last_activity_at >= ?",
                (since,),
            ).fetchall()
            con.execute("SELECT 1 FROM messages LIMIT 1")  # sin tabla `messages` la fuente no es válida
            messages = []
            for chunk in _chunks([row[0] for row in sessions], BATCH):
                marks = ",".join("?" * len(chunk))
                messages.extend(con.execute(
                    "SELECT session_id, role, tool_calls, tool_call_id, timestamp FROM messages "
                    f"WHERE session_id IN ({marks}) AND timestamp >= ? ORDER BY timestamp",
                    (*chunk, since),
                ).fetchall())
        finally:
            con.close()
    except sqlite3.Error as exc:
        raise SourceUnavailable(str(exc)) from exc

    state = {}
    for sid, role, tool_calls, tool_call_id, ts in messages:
        entry = state.setdefault(sid, {"last": None, "pending": {}})
        if role in ("user", "assistant", "tool") and ts is not None:
            entry["last"] = ts if entry["last"] is None else max(entry["last"], ts)
        if role == "assistant":
            for call_id, name in _calls(tool_calls):
                entry["pending"][call_id] = (name, ts)
        elif role == "tool":
            entry["pending"].pop(tool_call_id, None)

    facts = []
    for sid, cwd, activity, ended_at in sessions:
        entry = state.get(sid, {"last": None, "pending": {}})
        stamps = [t for t in (activity, entry["last"]) if t is not None]
        tool, tool_since = None, None
        for name, ts in entry["pending"].values():
            if ts is not None and (tool_since is None or ts >= tool_since):
                tool, tool_since = name, ts
        facts.append(SessionFacts("hermes", sid, cwd or "unknown", max(stamps) if stamps else None,
                                  tool, tool_since, ended=ended_at is not None))
    return facts
