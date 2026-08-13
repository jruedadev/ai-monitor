"""Persistencia local de rollups diarios (ver spec: preserva histórico más
allá de la ventana de retención de cada proveedor). SQLite, stdlib only.
"""
import os
import sqlite3
from datetime import datetime, timedelta, timezone

DB_PATH_DEFAULT = os.path.expanduser("~/.local/share/ai-monitor/history.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_project (
    date TEXT NOT NULL, source TEXT NOT NULL, project TEXT NOT NULL,
    tokens INTEGER NOT NULL, cost REAL,
    PRIMARY KEY (date, source, project)
);
CREATE TABLE IF NOT EXISTS daily_model (
    date TEXT NOT NULL, model TEXT NOT NULL,
    tokens INTEGER NOT NULL, cost REAL,
    PRIMARY KEY (date, model)
);
CREATE TABLE IF NOT EXISTS pricing (
    model TEXT PRIMARY KEY,
    input REAL, output REAL, cache_read REAL, cache_write REAL,
    updated_at TEXT NOT NULL
);
"""


def ensure_schema(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript(_SCHEMA)
    con.commit()
    con.close()


def record_snapshot(sources, db_path=None):
    if db_path is None:
        db_path = DB_PATH_DEFAULT
    ensure_schema(db_path)

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    for source_name in ("claude_code", "codex", "opencode"):
        for project, v in sources.get(source_name, {}).items():
            for date, day in (v.get("by_day") or {}).items():
                cur.execute(
                    "INSERT OR REPLACE INTO daily_project (date, source, project, tokens, cost) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (date, source_name, project, day.get("tokens", 0), day.get("cost")),
                )

    orr = sources.get("openrouter") or {}
    if not orr.get("unavailable", True):
        for date, day in (orr.get("by_day") or {}).items():
            cur.execute(
                "INSERT OR REPLACE INTO daily_model (date, model, tokens, cost) VALUES (?, ?, ?, ?)",
                (date, "__all__", day.get("tokens", 0), day.get("cost")),
            )

    con.commit()
    con.close()


def query_history(days, db_path=None):
    if db_path is None:
        db_path = DB_PATH_DEFAULT
    ensure_schema(db_path)

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute(
        "SELECT date, source, project, tokens, cost FROM daily_project "
        "WHERE date >= ? ORDER BY date ASC", (cutoff,)
    )
    daily_project = [dict(r) for r in cur.fetchall()]

    cur.execute(
        "SELECT date, model, tokens, cost FROM daily_model "
        "WHERE date >= ? ORDER BY date ASC", (cutoff,)
    )
    daily_model = [dict(r) for r in cur.fetchall()]

    con.close()
    return {"daily_project": daily_project, "daily_model": daily_model}
