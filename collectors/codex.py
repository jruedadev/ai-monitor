"""Collector de uso de Codex, leyendo ~/.codex/state_5.sqlite (tabla `threads`)."""
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone

from collectors.pricing import cost_of


def collect(state_db_path=None):
    if state_db_path is None:
        state_db_path = os.path.expanduser("~/.codex/state_5.sqlite")

    if not os.path.isfile(state_db_path):
        return {}

    try:
        con = sqlite3.connect(state_db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("SELECT id, cwd, model, tokens_used, created_at, title FROM threads")
        rows = cur.fetchall()
        con.close()
    except sqlite3.Error:
        return {}

    projects = defaultdict(lambda: {
        "input": 0, "output": 0, "cache_read": 0, "cache_write": 0,
        "cost": 0.0, "cost_incomplete": False, "messages": 0, "session_count": 0,
        "by_day": defaultdict(lambda: {"tokens": 0, "cost": 0.0}),
        "sessions_detail": [],
    })

    for row in rows:
        try:
            cwd = row["cwd"] or "unknown"
            tokens_used = row["tokens_used"] or 0
            model = row["model"]
            # No hay desglose input/output en Codex: se trata todo como "input"
            # para que el total_tokens sea correcto; el costo usa el mismo total
            # como input puro (aproximación documentada en el README).
            raw_cost = cost_of(tokens_used, 0, 0, 0, model)
            cost = raw_cost or 0.0

            p = projects[cwd]
            if raw_cost is None:
                p["cost_incomplete"] = True
            p["input"] += tokens_used
            p["cost"] += cost
            p["messages"] += 1
            p["session_count"] += 1

            created_at = row["created_at"]
            if created_at:
                day = datetime.fromtimestamp(created_at, tz=timezone.utc).strftime("%Y-%m-%d")
                p["by_day"][day]["tokens"] += tokens_used
                p["by_day"][day]["cost"] += cost

            p["sessions_detail"].append({
                "session_id": row["id"],
                "tokens": tokens_used,
                "cost": round(cost, 4),
                "title": row["title"],
                "last_ts": row["created_at"],
                "cwd": cwd,
            })
        except (KeyError, TypeError, ValueError):
            # Skip rows with unexpected data types or missing fields
            continue

    out = {}
    for name, p in projects.items():
        out[name] = {
            "input": p["input"], "output": 0, "cache_read": 0, "cache_write": 0,
            "total_tokens": p["input"],
            "cost": round(p["cost"], 4),
            "cost_incomplete": p["cost_incomplete"],
            "messages": p["messages"],
            "session_count": p["session_count"],
            "by_day": {k: {"tokens": v["tokens"], "cost": round(v["cost"], 4)} for k, v in p["by_day"].items()},
            "sessions_detail": p["sessions_detail"],
        }
    return out
