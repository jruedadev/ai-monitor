# Interactive Microfrontend Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a live, interactive dashboard (React frontend + Python stdlib backend with SSE) on top of the existing collectors, plus a local SQLite history so trend data survives provider log rotation — without touching the existing CLI (`main.py`), static HTML (`dashboard/template.py`), or the `ai-monitor.timer` unit.

**Architecture:** Four `by_day` extensions to the existing collectors feed both the new `history.py` persistence layer and the frontend's trend chart. A new `server.py` (stdlib `http.server` only) exposes `/api/usage` (snapshot), `/api/stream` (SSE push), `/api/history` (long-term trend from SQLite), and serves the built frontend as static files with SPA fallback. The frontend is a separate Vite/React/TypeScript project (`frontend/`) using shadcn/ui + Tremor, consuming those three endpoints — it has its own dependencies (Node/npm), which is normal for frontend and does not affect the backend's "stdlib only" guarantee.

**Tech Stack:** Backend: Python 3 stdlib only (`http.server`, `threading`, `queue`, `sqlite3`, `json`). Frontend: Vite, React, TypeScript, shadcn/ui, Tremor.

## Global Constraints

- Backend stays stdlib-only Python — no Flask/FastAPI/requests in `server.py` or `history.py`.
- No hardcoded paths to a specific user's home directory anywhere in versioned files — `history.py`'s DB path and `server.py`'s config all resolve via `os.path.expanduser`/env vars, same pattern as existing collectors.
- Nothing in this plan modifies `main.py`'s existing CLI behavior (`--json`/`--html`/table output must be byte-for-byte the same as before, except for the one intentional addition: `collect_all()` now also calls `history.record_snapshot()` as a side effect — see Task 5).
- The 4 collectors' existing output keys (`input`, `output`, `cache_read`, `cache_write`, `total_tokens`, `cost`, `cost_incomplete`, `messages`, `session_count`, `sessions_detail`) must not change shape or meaning — `by_day` is purely additive.
- `history.py`'s `record_snapshot()` must use `INSERT OR REPLACE` keyed by `(date, source, project)` / `(date, model)` — never accumulate/add to existing rows, and never delete a row for a date that's absent from the current snapshot (see spec: absence is what preserves history past provider retention).
- The "Todo" combined view (`main.combine_projects()`) still never includes OpenRouter — this plan does not touch that function's exclusion logic.

---

## File Structure

```
ai-monitor/
  collectors/
    claude_code.py    # MODIFY: add by_day
    codex.py           # MODIFY: add by_day
    opencode.py          # MODIFY: add by_day
    openrouter.py          # unchanged (already has by_day)
  history.py                # NEW: SQLite rollup persistence
  main.py                     # MODIFY: collect_all() calls history.record_snapshot()
  server.py                     # NEW: http.server app (usage/stream/history endpoints + static serving)
  sse.py                          # NEW: SSEBroker + event formatting (pure, unit-tested)
  tests/
    test_claude_code.py            # MODIFY: add by_day test
    test_codex.py                    # MODIFY: add by_day test
    test_opencode.py                   # MODIFY: add by_day test
    test_history.py                      # NEW
    test_sse.py                            # NEW
    test_server.py                           # NEW (integration, real ephemeral-port server)
  frontend/                                   # NEW: separate Vite/React/TS project
    package.json
    vite.config.ts
    tsconfig.json
    index.html
    src/
      main.tsx
      App.tsx
      hooks/useUsageStream.ts
      hooks/useTheme.ts
      lib/api.ts
      components/Sidebar.tsx
      components/KpiCards.tsx
      components/ProjectTable.tsx
      components/TrendChart.tsx
      components/ThemeToggle.tsx
  systemd/
    ai-monitor-server.service.template     # NEW
  install.sh                                 # MODIFY: optional server-unit install path
  README.md                                    # MODIFY
  CLAUDE.md                                      # MODIFY
```

---

### Task 1: `by_day` in `collectors/claude_code.py`

**Files:**
- Modify: `collectors/claude_code.py`
- Modify: `tests/test_claude_code.py`

**Interfaces:**
- Produces: each project dict in `collect()`'s return value gains a new key `"by_day": {"YYYY-MM-DD": {"tokens": int, "cost": float}}`, derived from each message's existing `ts` (ISO-8601 string, e.g. `"2026-08-01T10:00:00Z"`) by taking `ts[:10]`. Messages with no `ts` are skipped for `by_day` (but still counted in the existing totals, unchanged).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_claude_code.py` (new test method inside `TestClaudeCodeCollector`):

```python
    def test_by_day_aggregates_tokens_and_cost_per_date(self):
        self._write_session("sess1.jsonl", [
            {
                "type": "assistant", "cwd": "/home/user/DEV/demo",
                "timestamp": "2026-08-01T10:00:00Z",
                "message": {
                    "model": "claude-sonnet-5",
                    "usage": {
                        "input_tokens": 1_000_000, "output_tokens": 0,
                        "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
                    },
                },
            },
            {
                "type": "assistant", "cwd": "/home/user/DEV/demo",
                "timestamp": "2026-08-02T09:00:00Z",
                "message": {
                    "model": "claude-sonnet-5",
                    "usage": {
                        "input_tokens": 500_000, "output_tokens": 0,
                        "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
                    },
                },
            },
        ])

        data = claude_code.collect(projects_dir=self.tmp)

        by_day = data["/home/user/DEV/demo"]["by_day"]
        self.assertEqual(by_day["2026-08-01"]["tokens"], 1_000_000)
        self.assertAlmostEqual(by_day["2026-08-01"]["cost"], 3.0)
        self.assertEqual(by_day["2026-08-02"]["tokens"], 500_000)
        self.assertAlmostEqual(by_day["2026-08-02"]["cost"], 1.5)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ai-monitor && python3 -m unittest tests.test_claude_code -v`
Expected: FAIL with `KeyError: 'by_day'`

- [ ] **Step 3: Write minimal implementation**

In `collectors/claude_code.py`, add a `by_day` bucket to the `projects` defaultdict factory (line 19-25) and accumulate into it in the message loop (around line 83-92), then serialize it in the output dict (around line 101-116):

```python
    projects = defaultdict(lambda: {
        "input": 0, "output": 0, "cache_read": 0, "cache_write": 0,
        "cost": 0.0, "cost_incomplete": False, "messages": 0, "sessions": set(),
        "by_day": defaultdict(lambda: {"tokens": 0, "cost": 0.0}),
        "sessions_detail": defaultdict(lambda: {
            "tokens": 0, "cost": 0.0, "title": None, "last_ts": None, "cwd": None
        }),
    })
```

```python
                p = projects[resolved_name]
                if raw_cost is None:
                    p["cost_incomplete"] = True
                p["input"] += inp
                p["output"] += out
                p["cache_read"] += cr
                p["cache_write"] += cw
                p["cost"] += c
                p["messages"] += 1
                p["sessions"].add(session_id)

                if ts:
                    day = ts[:10]
                    p["by_day"][day]["tokens"] += inp + out + cr + cw
                    p["by_day"][day]["cost"] += c
```

```python
    out = {}
    for name, p in projects.items():
        out[name] = {
            "input": p["input"], "output": p["output"],
            "cache_read": p["cache_read"], "cache_write": p["cache_write"],
            "total_tokens": p["input"] + p["output"] + p["cache_read"] + p["cache_write"],
            "cost": round(p["cost"], 4),
            "cost_incomplete": p["cost_incomplete"],
            "messages": p["messages"],
            "session_count": len(p["sessions"]),
            "by_day": {k: {"tokens": v["tokens"], "cost": round(v["cost"], 4)} for k, v in p["by_day"].items()},
            "sessions_detail": [
                {"session_id": sid, "tokens": v["tokens"], "cost": round(v["cost"], 4),
                 "title": v["title"], "last_ts": v["last_ts"], "cwd": v["cwd"]}
                for sid, v in p["sessions_detail"].items()
            ],
        }
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ai-monitor && python3 -m unittest tests.test_claude_code -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
cd ai-monitor
git add collectors/claude_code.py tests/test_claude_code.py
git commit -m "feat: agregar by_day al collector de Claude Code"
```

---

### Task 2: `by_day` in `collectors/codex.py`

**Files:**
- Modify: `collectors/codex.py`
- Modify: `tests/test_codex.py`

**Interfaces:**
- Produces: same `by_day` addition. Codex's `created_at` is an epoch-seconds integer (see `state_5.sqlite`'s `threads.created_at`), so the date is derived with `datetime.fromtimestamp(created_at, tz=timezone.utc).strftime("%Y-%m-%d")`. Rows with `created_at` missing/`None`/non-numeric are skipped for `by_day` only (existing totals unaffected — this falls inside the row's existing try/except at line 32-59, so a bad `created_at` there already skips the whole row today; that's unchanged).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_codex.py` (new test method inside `TestCodexCollector`):

```python
    def test_by_day_derives_date_from_created_at_epoch(self):
        con = sqlite3.connect(self.tmp.name)
        con.execute(
            "INSERT INTO threads (id, cwd, model, tokens_used, created_at, title) VALUES (?,?,?,?,?,?)",
            ("t2", "/home/user/DEV/demo", "gpt-5.5", 1_000_000, 1754006400, "Segunda"),
        )  # 1754006400 == 2025-08-01T00:00:00Z
        con.commit()
        con.close()

        data = codex.collect(state_db_path=self.tmp.name)

        by_day = data["/home/user/DEV/demo"]["by_day"]
        self.assertIn("2025-08-01", by_day)
        self.assertEqual(by_day["2025-08-01"]["tokens"], 1_000_000)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ai-monitor && python3 -m unittest tests.test_codex -v`
Expected: FAIL with `KeyError: 'by_day'`

- [ ] **Step 3: Write minimal implementation**

In `collectors/codex.py`, add `from datetime import datetime, timezone` to imports, add `"by_day": defaultdict(lambda: {"tokens": 0, "cost": 0.0})` to the `projects` factory (line 26-29), accumulate inside the existing per-row `try` block (line 32-56), and serialize in the output (line 61-71):

```python
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone

from collectors.pricing import cost_of
```

```python
    projects = defaultdict(lambda: {
        "input": 0, "output": 0, "cache_read": 0, "cache_write": 0,
        "cost": 0.0, "cost_incomplete": False, "messages": 0, "session_count": 0,
        "by_day": defaultdict(lambda: {"tokens": 0, "cost": 0.0}),
        "sessions_detail": [],
    })
```

```python
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
```

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ai-monitor && python3 -m unittest tests.test_codex -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd ai-monitor
git add collectors/codex.py tests/test_codex.py
git commit -m "feat: agregar by_day al collector de Codex"
```

---

### Task 3: `by_day` in `collectors/opencode.py`

**Files:**
- Modify: `collectors/opencode.py`
- Modify: `tests/test_opencode.py`

**Interfaces:**
- Produces: same `by_day` addition. OpenCode's `time_created` is epoch **milliseconds** (see existing test fixture value `1777996210131`), so date is `datetime.fromtimestamp(time_created / 1000, tz=timezone.utc).strftime("%Y-%m-%d")`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_opencode.py` (new test method inside `TestOpenCodeCollector`):

```python
    def test_by_day_derives_date_from_time_created_ms(self):
        con = sqlite3.connect(self.tmp.name)
        con.execute(
            "INSERT INTO session (id, directory, model, title, cost, tokens_input, "
            "tokens_output, tokens_cache_read, tokens_cache_write, time_created) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("s2", "/home/user/DEV/demo", '{"id":"gpt-5.5"}', "Segunda", 0.10,
             300, 50, 0, 0, 1777996210131),  # == 2026-05-05T15:50:10Z
        )
        con.commit()
        con.close()

        data = opencode.collect(db_path=self.tmp.name)

        by_day = data["/home/user/DEV/demo"]["by_day"]
        self.assertIn("2026-05-05", by_day)
        self.assertEqual(by_day["2026-05-05"]["tokens"], 350)
        self.assertAlmostEqual(by_day["2026-05-05"]["cost"], 0.10)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ai-monitor && python3 -m unittest tests.test_opencode -v`
Expected: FAIL with `KeyError: 'by_day'`

- [ ] **Step 3: Write minimal implementation**

In `collectors/opencode.py`, add `from datetime import datetime, timezone` to imports, add `"by_day"` to the factory (line 29-32), accumulate inside the existing per-row `try` block (line 35-58), and serialize in output (line 63-73):

```python
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
```

```python
    projects = defaultdict(lambda: {
        "input": 0, "output": 0, "cache_read": 0, "cache_write": 0,
        "cost": 0.0, "messages": 0, "session_count": 0,
        "by_day": defaultdict(lambda: {"tokens": 0, "cost": 0.0}),
        "sessions_detail": [],
    })
```

```python
            p = projects[directory]
            p["input"] += inp
            p["output"] += out
            p["cache_read"] += cr
            p["cache_write"] += cw
            p["cost"] += cost
            p["messages"] += 1
            p["session_count"] += 1

            time_created = row["time_created"]
            if time_created:
                day = datetime.fromtimestamp(time_created / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                p["by_day"][day]["tokens"] += inp + out + cr + cw
                p["by_day"][day]["cost"] += cost

            p["sessions_detail"].append({
```

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ai-monitor && python3 -m unittest tests.test_opencode -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd ai-monitor
git add collectors/opencode.py tests/test_opencode.py
git commit -m "feat: agregar by_day al collector de OpenCode"
```

---

### Task 4: `history.py` persistence module

**Files:**
- Create: `history.py`
- Create: `tests/test_history.py`

**Interfaces:**
- Produces:
  - `DB_PATH_DEFAULT = os.path.expanduser("~/.local/share/ai-monitor/history.db")`
  - `ensure_schema(db_path) -> None` — creates the two tables (idempotent, `CREATE TABLE IF NOT EXISTS`) and the parent directory if missing.
  - `record_snapshot(sources: dict, db_path: str | None = None) -> None` — `db_path` defaults to `DB_PATH_DEFAULT` when `None` (override exists for tests). Reads `sources["claude_code"|"codex"|"opencode"]` (each `dict[project, {..., "by_day": {date: {tokens, cost}}}]`) and `sources["openrouter"]` (either `{"unavailable": True, ...}`, skipped entirely, or `{"unavailable": False, "by_day": {date: {tokens, cost}}}` — note: OpenRouter's `by_day` is NOT per-model despite the rest of its shape being per-model; it's a single combined `by_day` across all models, so it's recorded into `daily_model` under the synthetic key `model="__all__"`. This is a deliberate simplification: `/api/v1/activity`'s `by_day` aggregate doesn't retain per-model-per-day granularity in the collector's current output, and splitting it further is out of scope for this task.
  - `query_history(days: int, db_path: str | None = None) -> dict` — returns `{"daily_project": [{"date", "source", "project", "tokens", "cost"}], "daily_model": [{"date", "model", "tokens", "cost"}]}` for the last `days` days (by string comparison on `date`, since dates are `YYYY-MM-DD` and sort correctly as strings), ordered by date ascending.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_history.py
import os
import sqlite3
import tempfile
import unittest

import history


class TestHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name

    def tearDown(self):
        os.unlink(self.db_path)

    def test_record_snapshot_writes_project_and_model_rollups(self):
        sources = {
            "claude_code": {
                "/home/user/demo": {"by_day": {"2026-08-01": {"tokens": 100, "cost": 0.01}}},
            },
            "codex": {},
            "opencode": {},
            "openrouter": {
                "unavailable": False,
                "by_day": {"2026-08-01": {"tokens": 500, "cost": 0.05}},
            },
        }

        history.record_snapshot(sources, db_path=self.db_path)

        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute("SELECT date, source, project, tokens, cost FROM daily_project")
        self.assertEqual(
            cur.fetchall(),
            [("2026-08-01", "claude_code", "/home/user/demo", 100, 0.01)],
        )
        cur.execute("SELECT date, model, tokens, cost FROM daily_model")
        self.assertEqual(cur.fetchall(), [("2026-08-01", "__all__", 500, 0.05)])
        con.close()

    def test_record_snapshot_replaces_existing_day_not_deletes_absent_ones(self):
        sources_day1 = {
            "claude_code": {"/home/user/demo": {"by_day": {
                "2026-08-01": {"tokens": 100, "cost": 0.01},
                "2026-08-02": {"tokens": 200, "cost": 0.02},
            }}},
            "codex": {}, "opencode": {}, "openrouter": {"unavailable": True, "reason": "x"},
        }
        history.record_snapshot(sources_day1, db_path=self.db_path)

        # Second snapshot: 2026-08-01 has grown (as if more usage happened that
        # day before the provider's retention window moved past it), and
        # 2026-08-02 is no longer present (provider stopped returning it).
        sources_day2 = {
            "claude_code": {"/home/user/demo": {"by_day": {
                "2026-08-01": {"tokens": 150, "cost": 0.015},
            }}},
            "codex": {}, "opencode": {}, "openrouter": {"unavailable": True, "reason": "x"},
        }
        history.record_snapshot(sources_day2, db_path=self.db_path)

        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute("SELECT date, tokens FROM daily_project ORDER BY date")
        rows = cur.fetchall()
        con.close()

        self.assertEqual(rows, [("2026-08-01", 150), ("2026-08-02", 200)])

    def test_query_history_filters_by_days_and_orders_ascending(self):
        sources = {
            "claude_code": {"/home/user/demo": {"by_day": {
                "2026-01-01": {"tokens": 10, "cost": 0.001},
                "2026-08-01": {"tokens": 20, "cost": 0.002},
            }}},
            "codex": {}, "opencode": {}, "openrouter": {"unavailable": True, "reason": "x"},
        }
        history.record_snapshot(sources, db_path=self.db_path)

        result = history.query_history(days=30, db_path=self.db_path)

        dates = [row["date"] for row in result["daily_project"]]
        self.assertEqual(dates, ["2026-08-01"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ai-monitor && python3 -m unittest tests.test_history -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'history'`

- [ ] **Step 3: Write minimal implementation**

```python
# history.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ai-monitor && python3 -m unittest tests.test_history -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd ai-monitor
git add history.py tests/test_history.py
git commit -m "feat: agregar history.py (persistencia SQLite de rollups diarios)"
```

---

### Task 5: Wire `history.record_snapshot()` into `main.py`

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`

**Interfaces:**
- Consumes: `history.record_snapshot(sources, db_path=None)` from Task 4.
- Produces: `collect_all(db_path=None)` — gains an optional `db_path` parameter (default `None`, forwarded to `record_snapshot`) purely so tests can point persistence at a temp file instead of the real `~/.local/share/ai-monitor/history.db`. `main()`'s call site (`sources = collect_all()`) is unchanged — the new parameter is opt-in for tests only, production behavior (writing to the real path) is the default with no flag needed.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_main.py`:

```python
import os
import tempfile
import unittest
from unittest.mock import patch

from main import collect_all, combine_projects


class TestCollectAll(unittest.TestCase):
    def test_collect_all_persists_snapshot_to_history(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            fake_sources = {
                "claude_code": {"/home/user/demo": {"by_day": {"2026-08-01": {"tokens": 10, "cost": 0.01}}}},
                "codex": {}, "opencode": {}, "openrouter": {"unavailable": True, "reason": "x"},
            }
            with patch("main.claude_code.collect", return_value=fake_sources["claude_code"]), \
                 patch("main.codex.collect", return_value={}), \
                 patch("main.opencode.collect", return_value={}), \
                 patch("main.openrouter.collect", return_value={"unavailable": True, "reason": "x"}):
                collect_all(db_path=tmp.name)

            import sqlite3
            con = sqlite3.connect(tmp.name)
            cur = con.cursor()
            cur.execute("SELECT date, tokens FROM daily_project")
            rows = cur.fetchall()
            con.close()
            self.assertEqual(rows, [("2026-08-01", 10)])
        finally:
            os.unlink(tmp.name)
```

(Keep the existing `TestCombineProjects` class in the file as-is — this adds a new `TestCollectAll` class alongside it.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ai-monitor && python3 -m unittest tests.test_main -v`
Expected: FAIL with `TypeError: collect_all() got an unexpected keyword argument 'db_path'`

- [ ] **Step 3: Write minimal implementation**

In `main.py`, add the import and update `collect_all`:

```python
from collectors import claude_code, codex, opencode, openrouter
from dashboard import template
import history
```

```python
def collect_all(db_path=None):
    sources = {
        "claude_code": claude_code.collect(),
        "codex": codex.collect(),
        "opencode": opencode.collect(),
        "openrouter": openrouter.collect(),
    }
    history.record_snapshot(sources, db_path=db_path)
    return sources
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ai-monitor && python3 -m unittest discover -s tests -v`
Expected: PASS (all tests, including the new `TestCollectAll`)

- [ ] **Step 5: Manual smoke test**

```bash
cd ai-monitor
python3 main.py
ls -la ~/.local/share/ai-monitor/history.db
```
Expected: table prints as before, AND `history.db` now exists (created on first real run).

- [ ] **Step 6: Commit**

```bash
cd ai-monitor
git add main.py tests/test_main.py
git commit -m "feat: persistir snapshot en history.db en cada collect_all()"
```

---

### Task 6: `sse.py` — SSE broker (pure, unit-tested)

**Files:**
- Create: `sse.py`
- Create: `tests/test_sse.py`

**Interfaces:**
- Produces:
  - `format_sse_event(event_name: str, data: str) -> bytes` — formats a single SSE event per spec (`event: <name>\ndata: <line>\ndata: <line>...\n\n`, UTF-8 encoded). Multi-line `data` must be split into multiple `data:` lines (SSE requires this).
  - `class SSEBroker`: `subscribe() -> queue.Queue`, `unsubscribe(q: queue.Queue) -> None`, `publish(event_name: str, data: str) -> None` (puts the formatted bytes onto every currently-subscribed queue; thread-safe via an internal `threading.Lock`).

This is deliberately decoupled from sockets/HTTP so it's fully testable with `unittest` alone — `server.py` (Task 7) is the only place that touches actual connections.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sse.py
import queue
import unittest

from sse import SSEBroker, format_sse_event


class TestFormatSSEEvent(unittest.TestCase):
    def test_formats_single_line_event(self):
        out = format_sse_event("usage", '{"a": 1}')
        self.assertEqual(out, b'event: usage\ndata: {"a": 1}\n\n')

    def test_formats_multi_line_data(self):
        out = format_sse_event("usage", "line1\nline2")
        self.assertEqual(out, b"event: usage\ndata: line1\ndata: line2\n\n")


class TestSSEBroker(unittest.TestCase):
    def test_publish_delivers_to_all_subscribers(self):
        broker = SSEBroker()
        q1 = broker.subscribe()
        q2 = broker.subscribe()

        broker.publish("usage", '{"x": 1}')

        self.assertEqual(q1.get_nowait(), format_sse_event("usage", '{"x": 1}'))
        self.assertEqual(q2.get_nowait(), format_sse_event("usage", '{"x": 1}'))

    def test_unsubscribe_stops_delivery(self):
        broker = SSEBroker()
        q1 = broker.subscribe()
        broker.unsubscribe(q1)

        broker.publish("usage", "{}")

        with self.assertRaises(queue.Empty):
            q1.get_nowait()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ai-monitor && python3 -m unittest tests.test_sse -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sse'`

- [ ] **Step 3: Write minimal implementation**

```python
# sse.py
"""Server-Sent Events: formateo puro + un broker en memoria thread-safe.
Sin dependencia de sockets/HTTP — server.py conecta esto a las conexiones reales.
"""
import queue
import threading


def format_sse_event(event_name, data):
    lines = data.split("\n")
    body = "".join(f"data: {line}\n" for line in lines)
    return f"event: {event_name}\n{body}\n".encode("utf-8")


class SSEBroker:
    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers = []

    def subscribe(self):
        q = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def publish(self, event_name, data):
        payload = format_sse_event(event_name, data)
        with self._lock:
            subscribers = list(self._subscribers)
        for q in subscribers:
            q.put(payload)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ai-monitor && python3 -m unittest tests.test_sse -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
cd ai-monitor
git add sse.py tests/test_sse.py
git commit -m "feat: agregar SSEBroker y formateo de eventos SSE (puro, sin sockets)"
```

---

### Task 7: `server.py` — HTTP server with `/api/usage`, `/api/stream`, `/api/history`, static serving

**Files:**
- Create: `server.py`
- Create: `tests/test_server.py`

**Interfaces:**
- Consumes: `main.collect_all()`/`main.combine_projects()` (Task 5), `history.query_history()` (Task 4), `sse.SSEBroker`/`format_sse_event` (Task 6).
- Produces: `build_app(static_dir: str, poll_interval_seconds: int = 60) -> ThreadingHTTPServer` — constructs and returns a bound-but-not-yet-serving `http.server.ThreadingHTTPServer` instance listening on `("127.0.0.1", 0)` (ephemeral port; the real entry point in Step 5 reads `AI_MONITOR_PORT` and passes it explicitly — `build_app` itself always uses an ephemeral port so tests never fight over a fixed one). Also starts the background collection thread (daemon) that calls `collect_all()` + `combine_projects()` every `poll_interval_seconds`, and publishes to a shared `SSEBroker` when the JSON snapshot changes (compare via `json.dumps(..., sort_keys=True)` string equality — simplest correct diff, no need for a separate hash).

Routes (implemented in the request handler):
- `GET /api/usage` → 200, `application/json`, body = `json.dumps({"sources": ..., "combined": ...})` (the latest snapshot, computed once by the background thread and read from shared state — request handling never blocks on live collection).
- `GET /api/stream` → SSE. On connect: subscribe to the broker, immediately write the current snapshot as the first `usage` event, then loop writing whatever the broker delivers until the client disconnects (write raising `BrokenPipeError`/`ConnectionResetError` ends the loop and unsubscribes).
- `GET /api/history?days=N` → 200, `application/json`, body = `json.dumps(history.query_history(days=N))`; `N` defaults to `90` if the query param is missing or not a positive integer.
- Any other `GET` → serve from `static_dir` (the frontend build); if the requested file doesn't exist, serve `static_dir/index.html` (SPA fallback) with a 200, EXCEPT if `static_dir` itself doesn't exist, in which case respond 404 with a short plain-text message pointing at `frontend/README` build instructions (this covers the case where someone runs `server.py` before ever building the frontend).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server.py
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.request
from unittest.mock import patch

import server


class TestServerAPI(unittest.TestCase):
    def setUp(self):
        self.static_dir = tempfile.mkdtemp()
        with open(os.path.join(self.static_dir, "index.html"), "w") as f:
            f.write("<html>fallback</html>")

        self.fake_sources = {
            "claude_code": {"/home/user/demo": {
                "input": 10, "output": 5, "cache_read": 0, "cache_write": 0,
                "total_tokens": 15, "cost": 0.01, "cost_incomplete": False,
                "messages": 1, "session_count": 1, "by_day": {}, "sessions_detail": [],
            }},
            "codex": {}, "opencode": {}, "openrouter": {"unavailable": True, "reason": "x"},
        }

        patcher = patch("server.main.collect_all", return_value=self.fake_sources)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.httpd = server.build_app(self.static_dir, poll_interval_seconds=3600)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        # Give the background collection thread one tick to populate state.
        time.sleep(0.2)

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def _get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as resp:
            return resp.status, resp.read()

    def test_api_usage_returns_current_snapshot(self):
        status, body = self._get("/api/usage")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("/home/user/demo", data["combined"])

    def test_api_history_returns_json_with_default_days(self):
        status, body = self._get("/api/history")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("daily_project", data)
        self.assertIn("daily_model", data)

    def test_unknown_path_falls_back_to_index_html(self):
        status, body = self._get("/some/spa/route")
        self.assertEqual(status, 200)
        self.assertIn(b"fallback", body)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ai-monitor && python3 -m unittest tests.test_server -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server'`

- [ ] **Step 3: Write minimal implementation**

```python
# server.py
"""Servidor HTTP del dashboard interactivo: API en vivo (snapshot + SSE +
histórico) y estáticos del frontend. Solo stdlib (http.server), sin frameworks.
"""
import json
import mimetypes
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import history
import main
from sse import SSEBroker, format_sse_event

_state_lock = threading.Lock()
_state = {"sources": {}, "combined": {}}


def _recompute_and_maybe_publish(broker):
    sources = main.collect_all()
    combined = main.combine_projects(sources["claude_code"], sources["codex"], sources["opencode"])
    payload = json.dumps({"sources": sources, "combined": combined}, sort_keys=True)

    with _state_lock:
        changed = json.dumps(_state, sort_keys=True) != payload
        _state["sources"] = sources
        _state["combined"] = combined

    if changed:
        broker.publish("usage", payload)


def _background_loop(broker, poll_interval_seconds):
    while True:
        try:
            _recompute_and_maybe_publish(broker)
        except Exception:
            pass  # una falla de recolección no debe tumbar el hilo de fondo
        time.sleep(poll_interval_seconds)


def _current_snapshot_json():
    with _state_lock:
        return json.dumps({"sources": _state["sources"], "combined": _state["combined"]})


def make_handler(static_dir, broker):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # silencioso; evita ruido en stdout durante uso normal

        def do_GET(self):
            parsed = urlparse(self.path)

            if parsed.path == "/api/usage":
                self._send_json(_current_snapshot_json())
            elif parsed.path == "/api/history":
                qs = parse_qs(parsed.query)
                try:
                    days = int(qs.get("days", ["90"])[0])
                    if days <= 0:
                        days = 90
                except ValueError:
                    days = 90
                self._send_json(json.dumps(history.query_history(days=days)))
            elif parsed.path == "/api/stream":
                self._handle_sse()
            else:
                self._serve_static(parsed.path)

        def _send_json(self, body):
            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _handle_sse(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            q = broker.subscribe()
            try:
                self.wfile.write(format_sse_event("usage", _current_snapshot_json()))
                self.wfile.flush()
                while True:
                    payload = q.get()
                    self.wfile.write(payload)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                broker.unsubscribe(q)

        def _serve_static(self, url_path):
            if not os.path.isdir(static_dir):
                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Frontend no compilado. Corre 'npm install && npm run build' en frontend/.")
                return

            rel_path = url_path.lstrip("/") or "index.html"
            candidate = os.path.normpath(os.path.join(static_dir, rel_path))
            if not candidate.startswith(os.path.abspath(static_dir)):
                candidate = os.path.join(static_dir, "index.html")
            if not os.path.isfile(candidate):
                candidate = os.path.join(static_dir, "index.html")

            if not os.path.isfile(candidate):
                self.send_response(404)
                self.end_headers()
                return

            content_type, _ = mimetypes.guess_type(candidate)
            with open(candidate, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def build_app(static_dir, poll_interval_seconds=60):
    broker = SSEBroker()
    handler_cls = make_handler(static_dir, broker)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)

    thread = threading.Thread(
        target=_background_loop, args=(broker, poll_interval_seconds), daemon=True
    )
    thread.start()
    # Primer ciclo inmediato y síncrono para que /api/usage no responda vacío
    # justo después de arrancar.
    _recompute_and_maybe_publish(broker)

    return httpd


def main_entrypoint():
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(repo_dir, "frontend", "dist")
    port = int(os.environ.get("AI_MONITOR_PORT", "8420"))

    httpd = build_app(static_dir)
    httpd.server_close()  # cerramos el socket efímero de build_app...
    httpd.socket.close()
    # ...y re-bindeamos al puerto real configurado, reutilizando el mismo handler class.
    handler_cls = httpd.RequestHandlerClass
    httpd_real = ThreadingHTTPServer(("127.0.0.1", port), handler_cls)
    print(f"ai-monitor server escuchando en http://127.0.0.1:{port}")
    httpd_real.serve_forever()


if __name__ == "__main__":
    main_entrypoint()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ai-monitor && python3 -m unittest tests.test_server -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Fix the port-rebinding wart and re-verify**

The `main_entrypoint` above closes and rebinds sockets awkwardly to reconcile "`build_app` always uses an ephemeral port for testability" with "the real process needs a configurable fixed port." Replace it with a cleaner version: give `build_app` an optional `port` parameter (default `0`) instead of hardcoding ephemeral inside it.

Edit `server.py`:
```python
def build_app(static_dir, poll_interval_seconds=60, port=0):
    broker = SSEBroker()
    handler_cls = make_handler(static_dir, broker)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler_cls)

    thread = threading.Thread(
        target=_background_loop, args=(broker, poll_interval_seconds), daemon=True
    )
    thread.start()
    _recompute_and_maybe_publish(broker)

    return httpd


def main_entrypoint():
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(repo_dir, "frontend", "dist")
    port = int(os.environ.get("AI_MONITOR_PORT", "8420"))

    httpd = build_app(static_dir, port=port)
    print(f"ai-monitor server escuchando en http://127.0.0.1:{port}")
    httpd.serve_forever()
```

Re-run: `cd ai-monitor && python3 -m unittest tests.test_server -v` — the test's `build_app(self.static_dir, poll_interval_seconds=3600)` call still gets `port=0` by default (unchanged behavior for tests), so this refactor should not affect Step 4's PASS.
Expected: PASS (3 tests, same as Step 4)

- [ ] **Step 6: Manual smoke test**

```bash
cd ai-monitor
AI_MONITOR_PORT=8421 timeout 5 python3 server.py &
sleep 1
curl -s http://127.0.0.1:8421/api/usage | head -c 200
echo ""
curl -s http://127.0.0.1:8421/api/history | head -c 200
wait
```
Expected: both curls return JSON (no connection refused, no 500), server exits cleanly after the 5s timeout.

- [ ] **Step 7: Commit**

```bash
cd ai-monitor
git add server.py tests/test_server.py
git commit -m "feat: agregar server.py (API en vivo + SSE + estáticos del frontend)"
```

---

### Task 8: Frontend scaffold — Vite + React + TypeScript + Tailwind + shadcn/ui + Tremor

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/index.html`, `frontend/tailwind.config.js`, `frontend/postcss.config.js`
- Create: `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/index.css`
- Create: `frontend/.gitignore`

**Interfaces:** none consumed yet (this task only scaffolds a buildable, empty-shell app — later tasks fill in real components). Produces: a working `npm run dev` and `npm run build` in `frontend/`, with shadcn/ui and Tremor installed and Tailwind configured, and a proxy from `/api/*` to `http://127.0.0.1:8420` during development (matching `server.py`'s default port from Task 7).

This task has no Python unit tests (frontend tooling, not stdlib logic) — verification is the build succeeding and a manual browser check.

- [ ] **Step 1: Scaffold the Vite project**

```bash
cd ai-monitor
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

- [ ] **Step 2: Install Tailwind, shadcn/ui, Tremor, and routing**

```bash
cd ai-monitor/frontend
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
npm install @tremor/react react-router-dom
npx shadcn@latest init -d
npx shadcn@latest add sidebar table tabs card button
```

(`shadcn@latest init -d` accepts the tool's defaults non-interactively; if the installed version prompts anyway, choose: TypeScript yes, style "New York", base color "Neutral", CSS variables yes.)

- [ ] **Step 3: Configure Tailwind content paths**

Edit `frontend/tailwind.config.js` so `content` includes `./index.html` and `./src/**/*.{ts,tsx}` (the `shadcn init` step above may already have done this — verify, don't duplicate).

- [ ] **Step 4: Configure the dev-server API proxy**

Edit `frontend/vite.config.ts` to add a proxy so `npm run dev` can talk to `server.py` running separately on port 8420:

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8420",
    },
  },
});
```

- [ ] **Step 5: Minimal `App.tsx` shell**

```tsx
// frontend/src/App.tsx
export default function App() {
  return (
    <div className="min-h-screen bg-background text-foreground p-6">
      <h1 className="text-xl font-semibold">ai-monitor</h1>
      <p className="text-muted-foreground">Dashboard interactivo — en construcción.</p>
    </div>
  );
}
```

- [ ] **Step 6: Build verification**

```bash
cd ai-monitor/frontend
npm run build
ls dist/
```
Expected: build succeeds with no errors, `dist/index.html` and `dist/assets/` exist.

- [ ] **Step 7: Manual dev-server smoke test**

```bash
cd ai-monitor/frontend
npm run dev &
sleep 2
curl -s http://127.0.0.1:5173 | grep -o "<title>.*</title>"
kill %1
```
Expected: curl returns the page's `<title>` tag (Vite dev server responds on its default port, typically 5173).

- [ ] **Step 8: Commit**

```bash
cd ai-monitor
git add frontend/
git commit -m "feat: scaffold del frontend (Vite + React + TS + Tailwind + shadcn/ui + Tremor)"
```

---

### Task 9: Frontend — `useUsageStream` hook + Sidebar + KPI cards + project table

**Files:**
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/hooks/useUsageStream.ts`
- Create: `frontend/src/components/Sidebar.tsx`
- Create: `frontend/src/components/KpiCards.tsx`
- Create: `frontend/src/components/ProjectTable.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `GET /api/usage` (Task 7) — response shape `{"sources": {claude_code, codex, opencode, openrouter}, "combined": {project: {total_tokens, cost, messages, session_count, by_source}}}`, and `GET /api/stream` (SSE, same payload shape pushed as the `usage` event).
- Produces: `useUsageStream()` React hook returning `{sources, combined, connected: boolean}`, updated live from SSE (falls back to nothing/loading state until the first event arrives — the server always sends one immediately on connect per Task 7's `_handle_sse`).

- [ ] **Step 1: `lib/api.ts` — shared types**

```typescript
// frontend/src/lib/api.ts
export interface ProjectUsage {
  total_tokens: number;
  cost: number;
  messages: number;
  session_count: number;
  by_source: string[];
}

export interface SourceProjectUsage {
  input: number;
  output: number;
  cache_read: number;
  cache_write: number;
  total_tokens: number;
  cost: number;
  cost_incomplete: boolean;
  messages: number;
  session_count: number;
  by_day: Record<string, { tokens: number; cost: number }>;
  sessions_detail: unknown[];
}

export interface OpenRouterUsage {
  unavailable: boolean;
  reason?: string;
  models?: Record<string, { tokens: number; cost: number; requests: number }>;
  by_day?: Record<string, { tokens: number; cost: number }>;
}

export interface UsageSnapshot {
  sources: {
    claude_code: Record<string, SourceProjectUsage>;
    codex: Record<string, SourceProjectUsage>;
    opencode: Record<string, SourceProjectUsage>;
    openrouter: OpenRouterUsage;
  };
  combined: Record<string, ProjectUsage>;
}
```

- [ ] **Step 2: `useUsageStream` hook**

```typescript
// frontend/src/hooks/useUsageStream.ts
import { useEffect, useRef, useState } from "react";
import type { UsageSnapshot } from "@/lib/api";

export function useUsageStream() {
  const [snapshot, setSnapshot] = useState<UsageSnapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource("/api/stream");
    sourceRef.current = es;

    es.addEventListener("usage", (event) => {
      const data = JSON.parse((event as MessageEvent).data) as UsageSnapshot;
      setSnapshot(data);
      setConnected(true);
    });

    es.onerror = () => setConnected(false);

    return () => es.close();
  }, []);

  return {
    sources: snapshot?.sources ?? null,
    combined: snapshot?.combined ?? null,
    connected,
  };
}
```

- [ ] **Step 3: `Sidebar` component**

```tsx
// frontend/src/components/Sidebar.tsx
const SECTIONS = [
  { key: "all", label: "Todo" },
  { key: "claude_code", label: "Claude Code" },
  { key: "codex", label: "Codex" },
  { key: "opencode", label: "OpenCode" },
  { key: "openrouter", label: "OpenRouter" },
] as const;

export type SectionKey = (typeof SECTIONS)[number]["key"];

interface SidebarProps {
  active: SectionKey;
  onSelect: (key: SectionKey) => void;
}

export function Sidebar({ active, onSelect }: SidebarProps) {
  return (
    <nav className="w-48 shrink-0 border-r p-4 space-y-1">
      {SECTIONS.map((s) => (
        <button
          key={s.key}
          onClick={() => onSelect(s.key)}
          className={`block w-full text-left rounded px-3 py-2 text-sm ${
            active === s.key ? "bg-accent text-accent-foreground" : "hover:bg-muted"
          }`}
        >
          {s.label}
        </button>
      ))}
    </nav>
  );
}
```

- [ ] **Step 4: `KpiCards` component (Tremor)**

```tsx
// frontend/src/components/KpiCards.tsx
import { Card, Metric, Text } from "@tremor/react";
import type { ProjectUsage } from "@/lib/api";

interface KpiCardsProps {
  projects: Record<string, ProjectUsage>;
}

export function KpiCards({ projects }: KpiCardsProps) {
  const rows = Object.values(projects);
  const totalTokens = rows.reduce((s, r) => s + r.total_tokens, 0);
  const totalCost = rows.reduce((s, r) => s + r.cost, 0);
  const totalSessions = rows.reduce((s, r) => s + r.session_count, 0);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <Card>
        <Text>Proyectos</Text>
        <Metric>{rows.length}</Metric>
      </Card>
      <Card>
        <Text>Tokens totales</Text>
        <Metric>{totalTokens.toLocaleString()}</Metric>
      </Card>
      <Card>
        <Text>Costo estimado</Text>
        <Metric>${totalCost.toFixed(2)}</Metric>
      </Card>
      <Card>
        <Text>Sesiones</Text>
        <Metric>{totalSessions}</Metric>
      </Card>
    </div>
  );
}
```

- [ ] **Step 5: `ProjectTable` component (shadcn/ui)**

```tsx
// frontend/src/components/ProjectTable.tsx
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import type { ProjectUsage } from "@/lib/api";

interface ProjectTableProps {
  projects: Record<string, ProjectUsage>;
}

export function ProjectTable({ projects }: ProjectTableProps) {
  const rows = Object.entries(projects).sort((a, b) => b[1].total_tokens - a[1].total_tokens);

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Proyecto</TableHead>
          <TableHead className="text-right">Tokens</TableHead>
          <TableHead className="text-right">Costo</TableHead>
          <TableHead className="text-right">Sesiones</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map(([name, v]) => (
          <TableRow key={name}>
            <TableCell className="max-w-xs truncate" title={name}>{name}</TableCell>
            <TableCell className="text-right">{v.total_tokens.toLocaleString()}</TableCell>
            <TableCell className="text-right">${v.cost.toFixed(2)}</TableCell>
            <TableCell className="text-right">{v.session_count}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

- [ ] **Step 6: Wire it all into `App.tsx`**

```tsx
// frontend/src/App.tsx
import { useState } from "react";
import { useUsageStream } from "@/hooks/useUsageStream";
import { Sidebar, type SectionKey } from "@/components/Sidebar";
import { KpiCards } from "@/components/KpiCards";
import { ProjectTable } from "@/components/ProjectTable";

export default function App() {
  const [section, setSection] = useState<SectionKey>("all");
  const { sources, combined, connected } = useUsageStream();

  const projectsForSection = () => {
    if (!sources || !combined) return {};
    if (section === "all") return combined;
    if (section === "openrouter") return {};
    return Object.fromEntries(
      Object.entries(sources[section]).map(([name, v]) => [
        name,
        { total_tokens: v.total_tokens, cost: v.cost, messages: v.messages, session_count: v.session_count, by_source: [section] },
      ]),
    );
  };

  return (
    <div className="min-h-screen flex bg-background text-foreground">
      <Sidebar active={section} onSelect={setSection} />
      <main className="flex-1 p-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">ai-monitor</h1>
          <span className={`text-xs ${connected ? "text-green-500" : "text-muted-foreground"}`}>
            {connected ? "● en vivo" : "○ conectando..."}
          </span>
        </div>
        {combined && <KpiCards projects={projectsForSection()} />}
        {combined && <ProjectTable projects={projectsForSection()} />}
      </main>
    </div>
  );
}
```

- [ ] **Step 7: Build verification**

```bash
cd ai-monitor/frontend
npm run build
```
Expected: succeeds with no TypeScript errors.

- [ ] **Step 8: Manual end-to-end smoke test**

```bash
cd ai-monitor
AI_MONITOR_PORT=8420 python3 server.py &
sleep 1
cd frontend && npm run dev &
sleep 2
curl -s http://127.0.0.1:5173 > /dev/null && echo "frontend up"
kill %1 %2
```
Expected: both processes start without error; open `http://127.0.0.1:5173` in a browser manually to confirm the sidebar, KPI cards, and table render with real data and the "● en vivo" indicator turns green within a couple seconds.

- [ ] **Step 9: Commit**

```bash
cd ai-monitor
git add frontend/src
git commit -m "feat: sidebar, KPI cards, tabla de proyectos y SSE en vivo en el frontend"
```

---

### Task 10: Frontend — trend chart from `/api/history` + theme toggle

**Files:**
- Create: `frontend/src/components/TrendChart.tsx`
- Create: `frontend/src/components/ThemeToggle.tsx`
- Create: `frontend/src/hooks/useTheme.ts`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `GET /api/history?days=90` (Task 7) — `{"daily_project": [...], "daily_model": [...]}`.
- Produces: `TrendChart` renders a Tremor `LineChart` of tokens-per-day, aggregated across all projects/sources client-side from `daily_project`. `useTheme()` returns `{theme: "light"|"dark", toggle: () => void}`, persisted to `localStorage`, defaulting to `prefers-color-scheme`.

- [ ] **Step 1: `useTheme` hook**

```typescript
// frontend/src/hooks/useTheme.ts
import { useEffect, useState } from "react";

type Theme = "light" | "dark";

function initialTheme(): Theme {
  const stored = localStorage.getItem("ai-monitor-theme");
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem("ai-monitor-theme", theme);
  }, [theme]);

  const toggle = () => setTheme((t) => (t === "dark" ? "light" : "dark"));

  return { theme, toggle };
}
```

- [ ] **Step 2: `ThemeToggle` component**

```tsx
// frontend/src/components/ThemeToggle.tsx
import { Button } from "@/components/ui/button";
import { useTheme } from "@/hooks/useTheme";

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <Button variant="outline" size="sm" onClick={toggle}>
      {theme === "dark" ? "☀️ Claro" : "🌙 Oscuro"}
    </Button>
  );
}
```

- [ ] **Step 3: `TrendChart` component**

```tsx
// frontend/src/components/TrendChart.tsx
import { useEffect, useState } from "react";
import { Card, Title, LineChart } from "@tremor/react";

interface DailyProjectRow {
  date: string;
  source: string;
  project: string;
  tokens: number;
  cost: number;
}

export function TrendChart() {
  const [rows, setRows] = useState<DailyProjectRow[]>([]);

  useEffect(() => {
    fetch("/api/history?days=90")
      .then((r) => r.json())
      .then((data) => setRows(data.daily_project));
  }, []);

  const byDate: Record<string, number> = {};
  for (const row of rows) {
    byDate[row.date] = (byDate[row.date] ?? 0) + row.tokens;
  }
  const chartData = Object.entries(byDate)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, tokens]) => ({ date, Tokens: tokens }));

  return (
    <Card>
      <Title>Tendencia de tokens (90 días)</Title>
      <LineChart
        data={chartData}
        index="date"
        categories={["Tokens"]}
        colors={["blue"]}
        className="h-64 mt-4"
      />
    </Card>
  );
}
```

- [ ] **Step 4: Wire into `App.tsx`**

Add the imports and render both new components — the toggle in the header row, the chart above the KPI cards:

```tsx
import { TrendChart } from "@/components/TrendChart";
import { ThemeToggle } from "@/components/ThemeToggle";
```

```tsx
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">ai-monitor</h1>
          <div className="flex items-center gap-3">
            <span className={`text-xs ${connected ? "text-green-500" : "text-muted-foreground"}`}>
              {connected ? "● en vivo" : "○ conectando..."}
            </span>
            <ThemeToggle />
          </div>
        </div>
        <TrendChart />
        {combined && <KpiCards projects={projectsForSection()} />}
        {combined && <ProjectTable projects={projectsForSection()} />}
```

- [ ] **Step 5: Build verification**

```bash
cd ai-monitor/frontend
npm run build
```
Expected: succeeds with no TypeScript errors.

- [ ] **Step 6: Manual smoke test**

Same as Task 9 Step 8 (start `server.py` + `npm run dev`), open the browser: confirm the trend chart renders (even if empty/flat on a fresh `history.db`), and the theme toggle switches light/dark and persists across a page reload.

- [ ] **Step 7: Commit**

```bash
cd ai-monitor
git add frontend/src
git commit -m "feat: gráfico de tendencia (history.db) y toggle de tema en el frontend"
```

---

### Task 11: systemd unit + `install.sh` for the interactive server

**Files:**
- Create: `systemd/ai-monitor-server.service.template`
- Modify: `install.sh`

**Interfaces:** none (shell/config only, verified manually — same pattern as the plan's precedent for `install.sh`/systemd tasks).

- [ ] **Step 1: Create the service template**

```ini
# systemd/ai-monitor-server.service.template
[Unit]
Description=ai-monitor: servidor del dashboard interactivo

[Service]
Type=simple
EnvironmentFile=-__ENV_FILE__
ExecStart=__PYTHON__ __REPO_DIR__/server.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

(The leading `-` in `EnvironmentFile=-__ENV_FILE__` matches systemd's own syntax for "load if present, don't fail if missing" — the OpenRouter env file from the earlier `install.sh` work may or may not exist depending on whether the user configured OpenRouter.)

- [ ] **Step 2: Extend `install.sh`**

Add, after the existing timer installation block (the `cp "$REPO_DIR/systemd/ai-monitor.timer" ...` line and the env-file block that follow it), a new optional section:

```bash
echo ""
read -r -p "¿Instalar también el servicio del dashboard interactivo (server.py)? [y/N] " REPLY
if [[ "$REPLY" =~ ^[Yy]$ ]]; then
  if [ ! -d "$REPO_DIR/frontend/dist" ]; then
    echo ""
    echo "ADVERTENCIA: no se encontró $REPO_DIR/frontend/dist"
    echo "El frontend no está compilado. Antes de activar el servicio, corre:"
    echo "  cd $REPO_DIR/frontend && npm install && npm run build"
    echo ""
  fi

  sed \
    -e "s#__REPO_DIR__#${REPO_DIR}#g" \
    -e "s#__PYTHON__#${PYTHON_BIN}#g" \
    -e "s#__ENV_FILE__#${ENV_FILE}#g" \
    "$REPO_DIR/systemd/ai-monitor-server.service.template" > "$UNITS_DIR/ai-monitor-server.service"

  echo "Unidad ai-monitor-server.service instalada en $UNITS_DIR"
  echo "Para activarla:"
  echo "  systemctl --user daemon-reload"
  echo "  systemctl --user enable --now ai-monitor-server.service"
fi
```

This must go before the final `echo` block that already prints the timer-activation instructions, so the server-related prompt/output appears as its own section, not interleaved.

- [ ] **Step 3: Manual verification**

```bash
cd ai-monitor
echo "n" | ./install.sh   # responde "no" al nuevo prompt
ls ~/.config/systemd/user/ai-monitor-server.service 2>&1   # debe fallar (no se creó)

echo "y" | ./install.sh   # responde "sí"
cat ~/.config/systemd/user/ai-monitor-server.service       # confirmar placeholders resueltos, sin __REPO_DIR__/__PYTHON__/__ENV_FILE__ literales

# limpieza: no dejar la unidad instalada tras la verificación si no se va a usar de verdad
rm -f ~/.config/systemd/user/ai-monitor-server.service
systemctl --user daemon-reload
```
Expected: con "n" no se crea el archivo; con "y" se crea con las rutas reales sustituidas; ningún `systemctl enable` se ejecuta automáticamente en ningún caso.

- [ ] **Step 4: Commit**

```bash
cd ai-monitor
git add systemd/ai-monitor-server.service.template install.sh
git commit -m "feat: agregar unidad systemd opcional para el servidor del dashboard interactivo"
```

---

### Task 12: Documentation — README and CLAUDE.md

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

**Interfaces:** none — documentation only.

- [ ] **Step 1: Update README.md**

Add a new section after the existing "Instalación" section, before "Sobre el costo estimado":

```markdown
## Dashboard interactivo (opcional)

Además del HTML estático y la tabla en terminal, hay un dashboard web en vivo (React + Server-Sent Events), servido por `server.py` — sin frameworks del lado del backend, solo `http.server` de la librería estándar.

**Requiere Node.js/npm** (a diferencia del resto del proyecto, que solo necesita Python) para compilar el frontend.

```bash
# 1. Compilar el frontend una vez (o cada vez que cambie)
cd frontend
npm install
npm run build
cd ..

# 2. Correr el servidor
python3 server.py
# abre http://127.0.0.1:8420
```

El puerto es configurable con `AI_MONITOR_PORT` (default `8420`). El servidor recolecta datos de las 4 fuentes cada 60 segundos y los empuja al navegador vía SSE — no hace falta recargar la página.

**Como servicio de systemd**: `./install.sh` pregunta si quieres instalar también `ai-monitor-server.service` (servicio de larga duración, separado del `ai-monitor.timer` existente que solo regenera el HTML estático).

### Histórico más allá de la retención de cada proveedor

`server.py` (y también `main.py`, en cada ejecución) guarda un rollup diario por proyecto/modelo en `~/.local/share/ai-monitor/history.db` (SQLite). Si Claude Code, Codex u OpenCode eventualmente rotan o truncan sesiones viejas, ese histórico local no se pierde — el gráfico de tendencia del dashboard interactivo (`GET /api/history`) lee de ahí, no de los datos en vivo.
```

- [ ] **Step 2: Update `CLAUDE.md`**

Add a new bullet to the "Architecture" list, after the `dashboard/template.py` bullet:

```markdown
- **`server.py`** is the live counterpart to `main.py --html`: it reuses `main.collect_all()`/`main.combine_projects()` unchanged, adds a background thread that re-collects every N seconds and diffs the JSON before publishing to `sse.SSEBroker`, and serves `frontend/dist/` as static files with SPA fallback. `sse.py` is deliberately socket-free (pure formatting + an in-memory pub/sub broker) so it's unit-testable without spinning up real connections — `server.py` is the only place that wires it to actual sockets.
- **`history.py`** is additive persistence, not a collector: `main.collect_all()` calls `history.record_snapshot()` after every collection (whether triggered by the CLI, the timer, or `server.py`'s background loop), writing daily rollups to `~/.local/share/ai-monitor/history.db` via `INSERT OR REPLACE`. The replace-not-delete semantics are load-bearing: a date that stops appearing in a collector's `by_day` output (because the provider rotated it out) is deliberately left untouched in `history.db` — that's the entire point of the table. Don't add a "prune stale rows" step; absence upstream is what preserves history here, not a signal to delete.
- **`frontend/`** is a separate Node/npm project (Vite + React + TypeScript + shadcn/ui + Tremor) with its own dependencies — this does not violate the backend's stdlib-only rule, which applies to `server.py`/`collectors/`/`history.py` only. The frontend talks to `server.py` exclusively through `/api/usage`, `/api/stream` (SSE), and `/api/history` — it has no other way to reach collector data.
```

- [ ] **Step 3: Run full suite one more time**

```bash
cd ai-monitor
python3 -m unittest discover -s tests -v
```
Expected: all tests pass (backend tests only — no test runner is being added for the frontend in this plan).

- [ ] **Step 4: Commit**

```bash
cd ai-monitor
git add README.md CLAUDE.md
git commit -m "docs: documentar el dashboard interactivo, server.py y history.db"
```

---

## Self-Review Notes

- **Spec coverage**: `by_day` extension to all 4 collectors (Tasks 1-3; OpenRouter already had it), `history.py` persistence with replace-not-delete semantics (Task 4), wiring into `collect_all()` (Task 5), SSE broker (Task 6), `server.py` with `/api/usage`/`/api/stream`/`/api/history`/static serving (Task 7), frontend scaffold + shadcn/ui + Tremor (Task 8), live data + sidebar + KPI cards + table (Task 9), trend chart from `/api/history` + theme toggle (Task 10), systemd + install.sh (Task 11), docs (Task 12). Every section of the 2026-08-11 spec (including its 2026-08-12 persistence addendum) has a corresponding task.
- **Placeholder scan**: no TBD/TODO. The `__ENV_FILE__`/`__REPO_DIR__`/`__PYTHON__` tokens in Task 11's service template are intentional install-time placeholders (same pattern as the existing `ai-monitor.service.template`), substituted by `install.sh`, not plan placeholders.
- **Type/name consistency**: `collect_all(db_path=None)` (Task 5) matches what `server.py` calls in Task 7 (`main.collect_all()`, no args — uses the real default path in production, exactly as intended). `history.record_snapshot(sources, db_path=None)` (Task 4) signature matches its two call sites (Task 5's `main.py`, implicitly via `collect_all`). `SSEBroker.subscribe()/unsubscribe()/publish()` (Task 6) match their usage in `server.py`'s `_handle_sse` (Task 7). `build_app(static_dir, poll_interval_seconds=60, port=0)`'s final signature (Task 7 Step 5) is what Task 7's own test (Step 1, written before the Step 5 refactor) calls with `poll_interval_seconds=3600` and no `port` — confirmed compatible since `port` has a default.
