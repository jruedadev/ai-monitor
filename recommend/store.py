"""Persistencia del motor en history.db (spec §4). Nunca borra filas: las
recomendaciones solo cambian de estado. Todas las escrituras de una corrida
van en una transacción; si algo falla, rollback y las filas previas quedan."""
import hashlib
import json
import sqlite3

import history
from recommend.cluster import jaccard
from recommend.settings import BACKENDS, DEFAULT_BACKEND, DEFAULT_CHAIN, parse_entry

SCHEMA = """
CREATE TABLE IF NOT EXISTS recommendations (
  id TEXT PRIMARY KEY, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, tool TEXT NOT NULL,
  tokens INTEGER NOT NULL, pattern TEXT NOT NULL, kind TEXT NOT NULL, description TEXT NOT NULL,
  impact TEXT NOT NULL, evidence TEXT NOT NULL, draft TEXT NOT NULL, signature TEXT NOT NULL,
  status TEXT NOT NULL, status_at TEXT NOT NULL, generator TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS recommendation_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, finished_at TEXT,
  trigger TEXT NOT NULL, backend TEXT NOT NULL, model TEXT, attempts INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL, prompts INTEGER, clusters INTEGER, created INTEGER, updated INTEGER,
  resolved INTEGER, error TEXT, llm_tokens INTEGER, llm_cost REAL
);
CREATE TABLE IF NOT EXISTS engine_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

STATUSES = ("nueva", "aplicada", "saltada", "resuelta")
USER_STATUSES = ("nueva", "aplicada", "saltada")
SAME_PATTERN_THRESHOLD = 0.5
_RUN_FIELDS = ("model", "attempts", "prompts", "clusters", "created", "updated", "resolved",
               "error", "llm_tokens", "llm_cost")
_IMPACT_ORDER = "CASE impact WHEN 'alto' THEN 0 WHEN 'medio' THEN 1 ELSE 2 END"
_NON_LLM = ("reglas", "costo")


def connect(db_path=None):
    db_path = db_path or history.DB_PATH_DEFAULT
    history.ensure_schema(db_path)
    con = sqlite3.connect(db_path, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout = 30000")
    con.executescript(SCHEMA)
    return con


# --- Configuración -------------------------------------------------------------

def _valid_chain(value):
    try:
        chain = json.loads(value)
        if not isinstance(chain, list) or not chain:
            return None
        for entry in chain:
            parse_entry(entry)
    except (TypeError, ValueError):
        return None
    return chain


def get_engine_settings(db_path=None):
    con = connect(db_path)
    try:
        rows = dict(con.execute("SELECT key, value FROM engine_settings").fetchall())
    finally:
        con.close()
    backend = rows.get("backend") if rows.get("backend") in BACKENDS else DEFAULT_BACKEND
    chain = _valid_chain(rows.get("llm_chain")) or list(DEFAULT_CHAIN)
    return {"backend": backend, "llm_chain": chain}


def save_engine_settings(settings, db_path=None):
    """Recibe un payload ya validado con settings.validate_engine_settings."""
    con = connect(db_path)
    try:
        with con:
            con.execute("INSERT OR REPLACE INTO engine_settings (key, value) VALUES ('backend', ?)",
                        (settings["backend"],))
            con.execute("INSERT OR REPLACE INTO engine_settings (key, value) VALUES ('llm_chain', ?)",
                        (json.dumps(settings["llm_chain"]),))
    finally:
        con.close()


# --- Corridas --------------------------------------------------------------------

def start_run(db_path, trigger, backend, now):
    con = connect(db_path)
    try:
        with con:
            cur = con.execute(
                "INSERT INTO recommendation_runs (started_at, trigger, backend, status) VALUES (?, ?, ?, 'corriendo')",
                (now, trigger, backend))
        return cur.lastrowid
    finally:
        con.close()


def finish_run(db_path, run_id, status, now, **fields):
    unknown = set(fields) - set(_RUN_FIELDS)
    if unknown:
        raise ValueError(f"Campos de corrida desconocidos: {sorted(unknown)}")
    columns = ["status = ?", "finished_at = ?"] + [f"{key} = ?" for key in fields]
    con = connect(db_path)
    try:
        with con:
            con.execute(f"UPDATE recommendation_runs SET {', '.join(columns)} WHERE id = ?",
                        (status, now, *fields.values(), run_id))
    finally:
        con.close()


def _one(db_path, sql, params=()):
    con = connect(db_path)
    try:
        row = con.execute(sql, params).fetchone()
    finally:
        con.close()
    return dict(row) if row else None


def get_run(db_path, run_id):
    return _one(db_path, "SELECT * FROM recommendation_runs WHERE id = ?", (run_id,))


def last_run(db_path):
    return _one(db_path, "SELECT * FROM recommendation_runs ORDER BY id DESC LIMIT 1")


def latest_finished_run_id(db_path):
    row = _one(db_path, "SELECT MAX(id) AS id FROM recommendation_runs WHERE finished_at IS NOT NULL")
    return row["id"] if row else None


# --- Recomendaciones ---------------------------------------------------------------

def _public(row):
    rec = dict(row)
    rec["evidence"] = json.loads(rec["evidence"])
    rec.pop("signature", None)
    return rec


def list_recommendations(db_path, status="nueva"):
    if status != "todas" and status not in STATUSES:
        raise ValueError(f"Estado desconocido: {status}")
    where, params = ("", ()) if status == "todas" else ("WHERE status = ?", (status,))
    con = connect(db_path)
    try:
        rows = con.execute(f"SELECT * FROM recommendations {where} "
                           f"ORDER BY {_IMPACT_ORDER}, tokens DESC, last_seen DESC, id", params).fetchall()
    finally:
        con.close()
    return [_public(r) for r in rows]


def set_status(db_path, rec_id, status, now):
    if status not in USER_STATUSES:
        raise ValueError(f"Estado inválido: {status}")
    con = connect(db_path)
    try:
        with con:
            cur = con.execute("UPDATE recommendations SET status = ?, status_at = ? WHERE id = ?",
                              (status, now, rec_id))
        if cur.rowcount == 0:
            return None
        return _public(con.execute("SELECT * FROM recommendations WHERE id = ?", (rec_id,)).fetchone())
    finally:
        con.close()


def _canon(signature):
    return json.dumps(signature, sort_keys=True, ensure_ascii=False)


def _new_id(rec, used):
    base = rec["kind"] + _canon(rec["signature"])
    rec_id, n = hashlib.sha1(base.encode()).hexdigest()[:16], 0
    while rec_id in used:
        n += 1
        rec_id = hashlib.sha1(f"{base}#{n}".encode()).hexdigest()[:16]
    used.add(rec_id)
    return rec_id


def _insert(con, rec, now, used):
    con.execute(
        "INSERT INTO recommendations (id, first_seen, last_seen, tool, tokens, pattern, kind, description, impact, "
        "evidence, draft, signature, status, status_at, generator) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'nueva', ?, ?)",
        (_new_id(rec, used), now, now, rec["tool"], rec["tokens"], rec["pattern"], rec["kind"],
         rec["description"], rec["impact"], json.dumps(rec["evidence"], ensure_ascii=False), rec["draft"],
         _canon(rec["signature"]), now, rec["generator"]))


def _update(con, row, rec, now, is_cost):
    if row["status"] == "saltada":
        con.execute("UPDATE recommendations SET last_seen = ? WHERE id = ?", (now, row["id"]))
        return
    sets = {"last_seen": now, "tokens": rec["tokens"], "impact": rec["impact"],
            "evidence": json.dumps(rec["evidence"], ensure_ascii=False)}
    if is_cost:
        sets.update(pattern=rec["pattern"], description=rec["description"], draft=rec["draft"], tool=rec["tool"])
        if row["status"] == "resuelta":
            sets.update(status="nueva", status_at=now)
    elif row["generator"] == "reglas" and rec["generator"] not in _NON_LLM:
        sets.update(description=rec["description"], draft=rec["draft"], generator=rec["generator"], kind=rec["kind"])
    assignments = ", ".join(f"{key} = ?" for key in sets)
    con.execute(f"UPDATE recommendations SET {assignments} WHERE id = ?", (*sets.values(), row["id"]))


def apply_run(db_path, pattern_recs, cost_recs, now):
    counts = {"created": 0, "updated": 0, "resolved": 0}
    con = connect(db_path)
    try:
        with con:
            rows = [dict(r) for r in con.execute("SELECT * FROM recommendations")]
            used = {r["id"] for r in rows}

            patterns = [r for r in rows if r["kind"] != "costo"]
            matched = set()
            for rec in pattern_recs:
                signature = set(rec["signature"])
                best, best_score = None, SAME_PATTERN_THRESHOLD
                for row in patterns:
                    if row["id"] in matched:
                        continue
                    score = jaccard(signature, set(json.loads(row["signature"])))
                    if score >= best_score and (best is None or score > best_score):
                        best, best_score = row, score
                if best is None:
                    _insert(con, rec, now, used)
                    counts["created"] += 1
                else:
                    matched.add(best["id"])
                    _update(con, best, rec, now, is_cost=False)
                    counts["updated"] += 1

            costs = {r["signature"]: r for r in rows if r["kind"] == "costo"}
            fired = set()
            for rec in cost_recs:
                key = _canon(rec["signature"])
                fired.add(key)
                if key in costs:
                    _update(con, costs[key], rec, now, is_cost=True)
                    counts["updated"] += 1
                else:
                    _insert(con, rec, now, used)
                    counts["created"] += 1
            for key, row in costs.items():
                if key not in fired and row["status"] == "nueva":
                    con.execute("UPDATE recommendations SET status = 'resuelta', status_at = ? WHERE id = ?",
                                (now, row["id"]))
                    counts["resolved"] += 1
    finally:
        con.close()
    return counts
