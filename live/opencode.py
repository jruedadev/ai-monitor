"""Lector en vivo de OpenCode (~/.local/share/opencode/opencode.db, solo lectura).
`time_*` está en milisegundos. Del JSON de `part.data` solo se extraen tipo, herramienta y estado."""
import os
import sqlite3

from live.model import OFFICE_WINDOW_S, SessionFacts, SourceUnavailable

BATCH = 500  # por debajo del límite de variables de SQLite


def _chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def read(now, db_path=None):
    path = db_path or os.path.expanduser("~/.local/share/opencode/opencode.db")
    if not os.path.isfile(path):
        raise SourceUnavailable(path)
    since_ms = (now - OFFICE_WINDOW_S) * 1000
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            sessions = con.execute(
                "SELECT id, directory, time_updated, time_archived FROM session WHERE time_updated >= ?",
                (since_ms,),
            ).fetchall()
            con.execute("SELECT 1 FROM part LIMIT 1")  # sin tabla `part` la fuente no es válida aunque no haya sesiones
            parts = []
            ids = [row[0] for row in sessions]
            for chunk in _chunks(ids, BATCH):
                marks = ",".join("?" * len(chunk))
                parts.extend(con.execute(
                    "SELECT session_id, time_created, time_updated, json_extract(data,'$.type'), "
                    "json_extract(data,'$.tool'), json_extract(data,'$.state.status') "
                    f"FROM part WHERE json_valid(data) AND session_id IN ({marks}) AND time_updated >= ?",
                    (*chunk, since_ms),
                ).fetchall())
        finally:
            con.close()
    except sqlite3.Error as exc:
        raise SourceUnavailable(str(exc)) from exc

    by_session = {}
    for sid, created, updated, ptype, tool, status in parts:
        entry = by_session.setdefault(sid, {"last": None, "tool": None, "since": None})
        if updated is not None:
            entry["last"] = updated if entry["last"] is None else max(entry["last"], updated)
        if ptype == "tool" and status in ("pending", "running") and isinstance(tool, str) and created is not None:
            if entry["since"] is None or created >= entry["since"]:
                entry["tool"], entry["since"] = tool, created

    facts = []
    for sid, directory, updated, archived in sessions:
        entry = by_session.get(sid, {"last": None, "tool": None, "since": None})
        stamps = [t for t in (updated, entry["last"]) if t is not None]
        facts.append(SessionFacts(
            "opencode", sid, directory or "unknown",
            max(stamps) / 1000 if stamps else None,
            entry["tool"], entry["since"] / 1000 if entry["since"] is not None else None,
            ended=archived is not None,
        ))
    return facts
