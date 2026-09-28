"""Persistencia local de rollups diarios (ver spec: preserva histórico más
allá de la ventana de retención de cada proveedor). SQLite, stdlib only.
"""
import os
import re
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
CREATE TABLE IF NOT EXISTS roi_settings (
    key TEXT PRIMARY KEY,
    value REAL,
    updated_at TEXT NOT NULL
);
"""

ROI_SETTINGS_KEYS = (
    "subscription_cost_claude",
    "subscription_cost_codex",
    "hourly_rate",
    "subscription_start_claude",
    "subscription_start_codex",
)


def ensure_schema(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript(_SCHEMA)
    _migrate_legacy_dates(con)
    con.commit()
    con.close()


def _normalize_date(value):
    return str(value)[:10]


def _migrate_legacy_dates(con):
    for table, group_cols in (
        ("daily_project", ("source", "project")),
        ("daily_model", ("model",)),
    ):
        rows = con.execute(
            f"SELECT date, {', '.join(group_cols)}, tokens, cost FROM {table}"
        ).fetchall()
        if not any(" " in (row[0] or "") for row in rows):
            continue
        cols = len(group_cols)
        chosen = {}
        for row in rows:
            date = row[0]
            key = (date[:10],) + tuple(row[1 : 1 + cols])
            if " " in (date or ""):
                chosen.setdefault(key, (date[:10],) + row[1:])
            else:
                chosen[key] = row
        con.execute(f"DELETE FROM {table}")
        placeholders = ", ".join(["?"] * (cols + 3))
        con.executemany(
            f"INSERT INTO {table} (date, {', '.join(group_cols)}, tokens, cost) "
            f"VALUES ({placeholders})",
            list(chosen.values()),
        )


def record_snapshot(sources, db_path=None):
    if db_path is None:
        db_path = DB_PATH_DEFAULT
    ensure_schema(db_path)

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    for source_name in ("claude_code", "codex", "opencode", "hermes"):
        for project, v in sources.get(source_name, {}).items():
            for date, day in (v.get("by_day") or {}).items():
                cur.execute(
                    "INSERT OR REPLACE INTO daily_project (date, source, project, tokens, cost) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (_normalize_date(date), source_name, project, day.get("tokens", 0), day.get("cost")),
                )

    orr = sources.get("openrouter") or {}
    if not orr.get("unavailable", True):
        for date, day in (orr.get("by_day") or {}).items():
            cur.execute(
                "INSERT OR REPLACE INTO daily_model (date, model, tokens, cost) VALUES (?, ?, ?, ?)",
                (_normalize_date(date), "__all__", day.get("tokens", 0), day.get("cost")),
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


def get_roi_settings(db_path=None):
    if db_path is None:
        db_path = DB_PATH_DEFAULT
    ensure_schema(db_path)

    con = sqlite3.connect(db_path)
    rows = dict(con.execute("SELECT key, value FROM roi_settings").fetchall())
    con.close()

    return {key: rows.get(key) for key in ROI_SETTINGS_KEYS}


class RoiSettingsError(ValueError):
    """Payload inválido para /api/roi-settings; server.py lo traduce a HTTP 400."""


_ROI_NUMBER_KEYS = ("subscription_cost_claude", "subscription_cost_codex", "hourly_rate")
_ROI_DATE_KEYS = ("subscription_start_claude", "subscription_start_codex")
_ROI_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_roi_settings(settings):
    """Valida el payload de /api/roi-settings contra el allowlist de ROI_SETTINGS_KEYS.
    No escribe nada; lanza RoiSettingsError con el primer problema encontrado."""
    if not isinstance(settings, dict):
        raise RoiSettingsError("El cuerpo debe ser un objeto JSON")
    for key, value in settings.items():
        if key not in ROI_SETTINGS_KEYS:
            raise RoiSettingsError(f"Clave desconocida: {key}")
        if key in _ROI_NUMBER_KEYS:
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise RoiSettingsError(f"{key} debe ser numérico o null")
        elif key in _ROI_DATE_KEYS:
            if value is None:
                continue
            if not isinstance(value, str) or not _ROI_DATE_RE.match(value):
                raise RoiSettingsError(f"{key} debe tener formato YYYY-MM-DD o null")


def save_roi_settings(settings, db_path=None):
    if db_path is None:
        db_path = DB_PATH_DEFAULT
    ensure_schema(db_path)

    now = datetime.now(timezone.utc).isoformat()
    con = sqlite3.connect(db_path)
    for key, value in settings.items():
        if key not in ROI_SETTINGS_KEYS:
            continue
        con.execute(
            "INSERT OR REPLACE INTO roi_settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, now),
        )
    con.commit()
    con.close()
