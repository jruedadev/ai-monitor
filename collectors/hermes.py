"""Collector de uso de Hermes Agent, leyendo ~/.hermes/state.db (tabla `sessions`).
El costo lo reporta Hermes directamente (actual_cost_usd si existe, si no
estimated_cost_usd), no se re-estima con pricing.py.
"""
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone


_WANTED_COLUMNS = (
    "id", "cwd", "model", "input_tokens", "output_tokens",
    "cache_read_tokens", "cache_write_tokens", "estimated_cost_usd",
    "actual_cost_usd", "message_count", "started_at",
    "source", "chat_type", "title",
)


def _get(row, name, default=None):
    return row[name] if name in row.keys() else default


def _project_for(cwd, source, chat_type):
    if cwd:
        return cwd
    if source:
        return f"{source}:{chat_type}" if chat_type else source
    return "unknown"


def collect(db_path=None):
    if db_path is None:
        db_path = os.path.expanduser("~/.hermes/state.db")

    if not os.path.isfile(db_path):
        return {}

    try:
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        existing = {r[1] for r in cur.execute("PRAGMA table_info(sessions)").fetchall()}
        if "id" not in existing:
            con.close()
            return {}
        columns = [c for c in _WANTED_COLUMNS if c in existing]
        cur.execute(f"SELECT {', '.join(columns)} FROM sessions")
        rows = cur.fetchall()
        con.close()
    except sqlite3.Error:
        return {}

    projects = defaultdict(lambda: {
        "input": 0, "output": 0, "cache_read": 0, "cache_write": 0,
        "cost": 0.0, "messages": 0, "session_count": 0,
        "by_day": defaultdict(lambda: {"tokens": 0, "cost": 0.0}),
        "sessions_detail": [],
    })

    for row in rows:
        try:
            cwd = _get(row, "cwd")
            model = _get(row, "model")
            project = _project_for(cwd, _get(row, "source"), _get(row, "chat_type"))
            inp = row["input_tokens"] or 0
            out = row["output_tokens"] or 0
            cr = row["cache_read_tokens"] or 0
            cw = row["cache_write_tokens"] or 0
            actual = row["actual_cost_usd"]
            cost = actual if actual is not None else (row["estimated_cost_usd"] or 0.0)

            p = projects[project]
            p["input"] += inp
            p["output"] += out
            p["cache_read"] += cr
            p["cache_write"] += cw
            p["cost"] += cost
            p["messages"] += row["message_count"] or 0
            p["session_count"] += 1

            started_at = row["started_at"]
            day = None
            if started_at is not None:
                day = datetime.fromtimestamp(started_at, tz=timezone.utc).strftime("%Y-%m-%d")
                p["by_day"][day]["tokens"] += inp + out + cr + cw
                p["by_day"][day]["cost"] += cost

            p["sessions_detail"].append({
                "session_id": row["id"],
                "tokens": inp + out + cr + cw,
                "cost": round(cost, 4),
                "title": _get(row, "title") or model,
                "last_ts": started_at,
                "cwd": cwd,
                "date": day,
            })
        except (KeyError, TypeError, ValueError, OSError):
            # Skip rows with unexpected data types or missing fields
            # OSError can occur when datetime.fromtimestamp() receives out-of-range timestamps
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
            "by_day": {k: {"tokens": v["tokens"], "cost": round(v["cost"], 4)} for k, v in p["by_day"].items()},
            "sessions_detail": p["sessions_detail"],
        }
    return out
