"""Collector de uso de OpenCode, leyendo ~/.local/share/opencode/opencode.db
(tabla `session`). El costo lo reporta OpenCode directamente, no se re-estima.
"""
import os
import sqlite3
from collections import defaultdict


def collect(db_path=None):
    if db_path is None:
        db_path = os.path.expanduser("~/.local/share/opencode/opencode.db")

    if not os.path.isfile(db_path):
        return {}

    try:
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            "SELECT id, directory, model, title, cost, tokens_input, tokens_output, "
            "tokens_cache_read, tokens_cache_write, time_created FROM session"
        )
        rows = cur.fetchall()
        con.close()
    except sqlite3.Error:
        return {}

    projects = defaultdict(lambda: {
        "input": 0, "output": 0, "cache_read": 0, "cache_write": 0,
        "cost": 0.0, "messages": 0, "session_count": 0, "sessions_detail": [],
    })

    for row in rows:
        try:
            directory = row["directory"] or "unknown"
            inp = row["tokens_input"] or 0
            out = row["tokens_output"] or 0
            cr = row["tokens_cache_read"] or 0
            cw = row["tokens_cache_write"] or 0
            cost = row["cost"] or 0.0

            p = projects[directory]
            p["input"] += inp
            p["output"] += out
            p["cache_read"] += cr
            p["cache_write"] += cw
            p["cost"] += cost
            p["messages"] += 1
            p["session_count"] += 1
            p["sessions_detail"].append({
                "session_id": row["id"],
                "tokens": inp + out + cr + cw,
                "cost": round(cost, 4),
                "title": row["title"],
                "last_ts": row["time_created"],
                "cwd": directory,
            })
        except (KeyError, TypeError, ValueError):
            # Skip rows with unexpected data types or missing fields
            continue

    out = {}
    for name, p in projects.items():
        out[name] = {
            "input": p["input"], "output": p["output"],
            "cache_read": p["cache_read"], "cache_write": p["cache_write"],
            "total_tokens": p["input"] + p["output"] + p["cache_read"] + p["cache_write"],
            "cost": round(p["cost"], 4),
            "messages": p["messages"],
            "session_count": p["session_count"],
            "sessions_detail": p["sessions_detail"],
        }
    return out
