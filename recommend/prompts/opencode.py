"""Prompts de OpenCode: opencode.db, message(role=user) + part(type=text)."""
import json
import os
import sqlite3
from pathlib import Path

from recommend.prompts import Prompt, clean_text, day_from_epoch

_SQL = """
SELECT s.id, s.directory, m.id, m.time_created, m.data, p.data
FROM message m JOIN session s ON s.id = m.session_id JOIN part p ON p.message_id = m.id
ORDER BY m.time_created, m.id, p.id
"""


def _json(value):
    try:
        data = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def read_prompts(since, override=None):
    path = override or os.path.expanduser("~/.local/share/opencode/opencode.db")
    if not os.path.isfile(path):
        return []
    con = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        tables = {name for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if not {"session", "message", "part"} <= tables:
            return []
        rows = con.execute(_SQL).fetchall()
    finally:
        con.close()

    messages = {}  # message_id -> [session_id, directory, day, [textos]]
    for session_id, directory, message_id, created, message_data, part_data in rows:
        if _json(message_data).get("role") != "user":
            continue
        part = _json(part_data)
        if part.get("type") != "text" or part.get("synthetic") or not isinstance(part.get("text"), str):
            continue
        entry = messages.setdefault(message_id, [session_id, directory, day_from_epoch((created or 0) / 1000), []])
        entry[3].append(part["text"])

    out = []
    for session_id, directory, day, texts in messages.values():
        text = clean_text("\n".join(texts))
        if text and day and day >= since:
            out.append(Prompt("opencode", directory or "unknown", str(session_id), day, text))
    return out
