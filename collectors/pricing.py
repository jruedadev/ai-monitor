"""Tabla de precios de lista (USD por millón de tokens) y cálculo de costo.
Compartida por los collectors que estiman costo (claude_code, codex).
OpenCode no usa este módulo porque ya reporta su propio costo calculado.

Los precios viven en la tabla `pricing` de history.db (ver history.py's
_SCHEMA, Task 13). `_DEFAULT_SNAPSHOT` es solo el snapshot de bootstrap:
si la tabla está vacía en el primer uso, se inserta este snapshot y a
partir de ahí la base de datos es la fuente de verdad. Para actualizar
precios en producción, usar `collectors/sync_pricing.py`, no editar este
dict (salvo para cambiar el propio valor de bootstrap).
"""
import datetime
import sqlite3

import history

_DEFAULT_SNAPSHOT = {
    "claude-opus-5":             {"input": 15.0, "output": 75.0, "cache_read": 1.5, "cache_write": 18.75},
    "claude-sonnet-5":           {"input": 3.0,  "output": 15.0, "cache_read": 0.3, "cache_write": 3.75},
    "claude-haiku-4-5-20251001": {"input": 1.0,  "output": 5.0,  "cache_read": 0.1, "cache_write": 1.25},
    "claude-fable-5":            {"input": 3.0,  "output": 15.0, "cache_read": 0.3, "cache_write": 3.75},
    # Modelos OpenAI vistos en Codex (precios de lista aproximados, ajustar si cambian)
    "gpt-5.5":                   {"input": 2.5,  "output": 10.0, "cache_read": 0.25, "cache_write": 2.5},
    "gpt-5.5-fast":              {"input": 2.5,  "output": 10.0, "cache_read": 0.25, "cache_write": 2.5},
    "gpt-5.5-mini":              {"input": 0.5,  "output": 2.0,  "cache_read": 0.05, "cache_write": 0.5},
}
DEFAULT_PRICE = None  # sin default silencioso: modelo desconocido -> costo None

# Cache en memoria de la tabla pricing, por db_path. cost_of() se llama una vez
# por mensaje en el loop de recolección (claude_code.py/codex.py), así que abrir
# una conexión SQLite nueva por llamada es una regresión de performance medible
# (~1.7s de 2.3s totales sobre 12,405 mensajes). El cache solo se invalida
# explícitamente vía reset_cache() (p.ej. entre corridas de test).
_PRICING_CACHE = {}


def reset_cache():
    """Limpia el cache de pricing en memoria. Usar en tests para aislar estado
    entre corridas; un proceso de servidor de larga duración recarga solo al
    reiniciar, que es el comportamiento esperado."""
    _PRICING_CACHE.clear()


def _load_pricing(db_path):
    if db_path is None:
        db_path = history.DB_PATH_DEFAULT

    if db_path in _PRICING_CACHE:
        return _PRICING_CACHE[db_path]

    history.ensure_schema(db_path)

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM pricing")
    if cur.fetchone()["n"] == 0:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        for model, rates in _DEFAULT_SNAPSHOT.items():
            cur.execute(
                "INSERT OR REPLACE INTO pricing (model, input, output, cache_read, cache_write, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (model, rates["input"], rates["output"], rates["cache_read"], rates["cache_write"], now),
            )
        con.commit()

    cur.execute("SELECT model, input, output, cache_read, cache_write FROM pricing")
    result = {
        row["model"]: {"input": row["input"], "output": row["output"],
                        "cache_read": row["cache_read"], "cache_write": row["cache_write"]}
        for row in cur.fetchall()
    }
    con.close()
    _PRICING_CACHE[db_path] = result
    return result


def price_for(model, db_path=None):
    if not model:
        return None
    rates = _load_pricing(db_path)
    for key, p in rates.items():
        if key in model:
            return p
    return None


def cost_of(input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, model, db_path=None):
    p = price_for(model, db_path=db_path)
    if p is None:
        return None
    return (
        (input_tokens or 0) * p["input"]
        + (output_tokens or 0) * p["output"]
        + (cache_read_tokens or 0) * p["cache_read"]
        + (cache_write_tokens or 0) * p["cache_write"]
    ) / 1_000_000
