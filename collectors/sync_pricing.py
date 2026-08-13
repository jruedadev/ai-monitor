# collectors/sync_pricing.py
"""CLI para sincronizar precios hacia la tabla `pricing` de history.db.
Uso:
  python3 -m collectors.sync_pricing             # dry-run: muestra diff
  python3 -m collectors.sync_pricing --write      # aplica SNAPSHOT a la tabla
  python3 -m collectors.sync_pricing --check      # exit 1 si hay diferencias (CI)
"""
import argparse
import datetime
import sqlite3
import sys

import history
from collectors.pricing import _DEFAULT_SNAPSHOT as SNAPSHOT

# Editar el snapshot de bootstrap en collectors/pricing.py (_DEFAULT_SNAPSHOT)
# cuando un proveedor cambie precios, luego correr --write.


def _current_rows(db_path):
    if db_path is None:
        db_path = history.DB_PATH_DEFAULT
    history.ensure_schema(db_path)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT model, input, output, cache_read, cache_write FROM pricing")
    rows = {r["model"]: dict(r) for r in cur.fetchall()}
    con.close()
    return rows


def _diff(db_path):
    current = _current_rows(db_path)
    added, changed = [], []
    for model, rates in SNAPSHOT.items():
        if model not in current:
            added.append(model)
        elif {k: current[model][k] for k in ("input", "output", "cache_read", "cache_write")} != rates:
            changed.append(model)
    return added, changed


def write(db_path=None):
    if db_path is None:
        db_path = history.DB_PATH_DEFAULT
    history.ensure_schema(db_path)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    for model, rates in SNAPSHOT.items():
        cur.execute(
            "INSERT OR REPLACE INTO pricing (model, input, output, cache_read, cache_write, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (model, rates["input"], rates["output"], rates["cache_read"], rates["cache_write"], now),
        )
    con.commit()
    con.close()

    from collectors import pricing
    pricing.reset_cache()


def check(db_path=None):
    if db_path is None:
        db_path = history.DB_PATH_DEFAULT
    added, changed = _diff(db_path)
    return not added and not changed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.check:
        sys.exit(0 if check() else 1)

    added, changed = _diff(None)
    for m in added:
        print(f"+ {m} (nuevo)")
    for m in changed:
        print(f"~ {m} (precio distinto)")
    if not added and not changed:
        print("Sin cambios.")

    if args.write:
        write()
        print("Aplicado a la tabla pricing.")


if __name__ == "__main__":
    main()
