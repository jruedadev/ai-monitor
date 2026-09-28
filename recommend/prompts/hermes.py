"""Prompts de Hermes: state.db, messages role=user (+ sessions para el proyecto)."""
import os
import sqlite3
from pathlib import Path

from collectors.hermes import _project_for
from recommend.prompts import Prompt, clean_text, day_from_epoch

_SESSION_COLUMNS = ("cwd", "source", "chat_type")


def read_prompts(since, override=None):
    path = override or os.path.expanduser("~/.hermes/state.db")
    if not os.path.isfile(path):
        return []
    con = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        tables = {name for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "messages" not in tables:
            return []
        existing = set()
        if "sessions" in tables:
            existing = {r[1] for r in con.execute("PRAGMA table_info(sessions)")}
        cols = [c for c in _SESSION_COLUMNS if c in existing]
        select = ", ".join([f"s.{c}" for c in cols]) or "NULL"
        join = "LEFT JOIN sessions s ON s.id = m.session_id" if "sessions" in tables else ""
        rows = con.execute(
            f"SELECT m.session_id, m.timestamp, m.content, {select} FROM messages m {join} "
            "WHERE m.role = 'user' ORDER BY m.timestamp").fetchall()
    finally:
        con.close()

    out = []
    for row in rows:
        session_id, timestamp, content = row[0], row[1], row[2]
        info = dict(zip(cols, row[3:]))
        day = day_from_epoch(timestamp)
        text = clean_text(content)
        if not text or day is None or day < since:
            continue
        project = _project_for(info.get("cwd"), info.get("source"), info.get("chat_type"))
        out.append(Prompt("hermes", project, str(session_id), day, text))
    return out
