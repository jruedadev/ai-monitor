# Dashboard Multiplataforma (Claude Code, Codex, OpenCode, OpenRouter) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `ai-monitor` from a single Claude-Code-only script into a modular multi-source dashboard covering Claude Code, Codex, OpenCode, and OpenRouter, with a "Todo" combined view, without any hardcoded user/path assumptions.

**Architecture:** One collector module per source under `collectors/`, all returning the same shape for the three per-project sources (`claude_code`, `codex`, `opencode`); `openrouter` returns a per-model shape. `main.py` orchestrates: calls every collector (each fails in isolation), combines the per-project ones, and renders a tabbed HTML dashboard from `dashboard/template.py`. Portability (alias + systemd) is handled by `shell/aliases.sh` (self-locating via `BASH_SOURCE`) and `install.sh` (self-locating via `dirname "$0"`).

**Tech Stack:** Python 3 standard library only (`sqlite3`, `json`, `urllib.request`, `argparse`, `unittest`) — no pip dependencies, so the public repo has zero install friction.

## Global Constraints

- No external Python dependencies (stdlib only) — this is documented in the current README and must stay true.
- No hardcoded paths to `/home/jruedadev` or `~/DEV/JRDV/...` anywhere in versioned files — everything resolves relative to `~` of the executing user, or relative to the repo's own location for shell/systemd config.
- Every collector must degrade gracefully: missing file/DB/env var → `{"unavailable": True, "reason": "..."}` for that source, never an unhandled exception that kills the whole run.
- Costs: OpenCode's `cost` field is used as-is (never re-estimated). Claude Code and Codex costs are estimated from a price table; if a model isn't in the table, cost is `None` (not a silently wrong default).
- The "Todo" combined view sums only Claude Code + Codex + OpenCode. OpenRouter is never included in that sum (documented double-counting risk with OpenCode's `openrouter` provider sessions).

---

## File Structure

```
ai-monitor/
  main.py
  collectors/
    __init__.py
    pricing.py         # shared price table + cost_of() used by claude_code.py and codex.py
    claude_code.py
    codex.py
    opencode.py
    openrouter.py
  dashboard/
    __init__.py
    template.py         # HTML_TEMPLATE with tabs, render(data) -> str
  tests/
    __init__.py
    test_pricing.py
    test_claude_code.py
    test_codex.py
    test_opencode.py
    test_openrouter.py
  shell/
    aliases.sh
  systemd/
    ai-monitor.service.template
    ai-monitor.timer
  install.sh
  claude_usage.py        # DELETED at the end (Task 8), replaced by main.py + collectors/
  README.md
  CLAUDE.md
```

---

### Task 1: Shared pricing module

**Files:**
- Create: `collectors/__init__.py` (empty)
- Create: `collectors/pricing.py`
- Test: `tests/__init__.py` (empty)
- Test: `tests/test_pricing.py`

**Interfaces:**
- Produces: `PRICING: dict[str, dict]`, `DEFAULT_PRICE: dict`, `price_for(model: str | None) -> dict`, `cost_of(input_tokens: int, output_tokens: int, cache_read_tokens: int, cache_write_tokens: int, model: str | None) -> float | None`.
  - `cost_of` returns `None` if `model` is `None` or doesn't match any key in `PRICING` (no silent default — this is stricter than the current `claude_usage.py`, which used `DEFAULT_PRICE` as a fallback; the new behavior matches the spec's "no inventar un precio" rule).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pricing.py
import unittest
from collectors import pricing


class TestPricing(unittest.TestCase):
    def test_known_model_computes_cost(self):
        cost = pricing.cost_of(
            input_tokens=1_000_000, output_tokens=1_000_000,
            cache_read_tokens=0, cache_write_tokens=0,
            model="claude-sonnet-5",
        )
        self.assertAlmostEqual(cost, 3.0 + 15.0)

    def test_unknown_model_returns_none(self):
        cost = pricing.cost_of(
            input_tokens=1000, output_tokens=1000,
            cache_read_tokens=0, cache_write_tokens=0,
            model="some-brand-new-model-nobody-mapped-yet",
        )
        self.assertIsNone(cost)

    def test_none_model_returns_none(self):
        cost = pricing.cost_of(
            input_tokens=1000, output_tokens=1000,
            cache_read_tokens=0, cache_write_tokens=0,
            model=None,
        )
        self.assertIsNone(cost)

    def test_partial_model_name_match(self):
        # Codex/OpenAI model ids often carry suffixes; substring match must work
        cost = pricing.cost_of(
            input_tokens=1_000_000, output_tokens=0,
            cache_read_tokens=0, cache_write_tokens=0,
            model="gpt-5.5-fast",
        )
        self.assertIsNotNone(cost)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ai-monitor && python3 -m unittest tests.test_pricing -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collectors'` (package doesn't exist yet)

- [ ] **Step 3: Write minimal implementation**

```python
# collectors/pricing.py
"""Tabla de precios de lista (USD por millón de tokens) y cálculo de costo.
Compartida por los collectors que estiman costo (claude_code, codex).
OpenCode no usa este módulo porque ya reporta su propio costo calculado.
"""

PRICING = {
    "claude-opus-5":             {"in": 15.0, "out": 75.0, "cache_r": 1.5, "cache_w": 18.75},
    "claude-sonnet-5":           {"in": 3.0,  "out": 15.0, "cache_r": 0.3, "cache_w": 3.75},
    "claude-haiku-4-5-20251001": {"in": 1.0,  "out": 5.0,  "cache_r": 0.1, "cache_w": 1.25},
    "claude-fable-5":            {"in": 3.0,  "out": 15.0, "cache_r": 0.3, "cache_w": 3.75},
    # Modelos OpenAI vistos en Codex (precios de lista aproximados, ajustar si cambian)
    "gpt-5.5":                   {"in": 2.5,  "out": 10.0, "cache_r": 0.25, "cache_w": 2.5},
    "gpt-5.5-fast":              {"in": 2.5,  "out": 10.0, "cache_r": 0.25, "cache_w": 2.5},
    "gpt-5.5-mini":              {"in": 0.5,  "out": 2.0,  "cache_r": 0.05, "cache_w": 0.5},
}
DEFAULT_PRICE = None  # sin default silencioso: modelo desconocido -> costo None


def price_for(model):
    if not model:
        return None
    for key, p in PRICING.items():
        if key in model:
            return p
    return None


def cost_of(input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, model):
    p = price_for(model)
    if p is None:
        return None
    return (
        (input_tokens or 0) * p["in"]
        + (output_tokens or 0) * p["out"]
        + (cache_read_tokens or 0) * p["cache_r"]
        + (cache_write_tokens or 0) * p["cache_w"]
    ) / 1_000_000
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ai-monitor && python3 -m unittest tests.test_pricing -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
cd ai-monitor
git add collectors/__init__.py collectors/pricing.py tests/__init__.py tests/test_pricing.py
git commit -m "feat: agregar módulo de precios compartido con costo None para modelos desconocidos"
```

---

### Task 2: Claude Code collector (migrar lógica existente)

**Files:**
- Create: `collectors/claude_code.py`
- Test: `tests/test_claude_code.py`

**Interfaces:**
- Consumes: `collectors.pricing.cost_of(input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, model) -> float | None`
- Produces: `collect(projects_dir: str | None = None) -> dict[str, dict]`. Each value has shape:
  ```python
  {
      "input": int, "output": int, "cache_read": int, "cache_write": int,
      "total_tokens": int, "cost": float, "messages": int, "session_count": int,
      "sessions_detail": [
          {"session_id": str, "tokens": int, "cost": float, "title": str | None,
           "last_ts": str | None, "cwd": str | None}
      ],
  }
  ```
  `projects_dir` defaults to `os.path.expanduser("~/.claude/projects")` when `None` — the override exists purely so tests can point at a temp directory instead of the real one.
  Sessions/costs where `pricing.cost_of` returns `None` contribute `0.0` to the aggregated `cost` (a per-project total can't be partially "None"; it's a sum, so unknown-cost messages simply don't add to it — this matches today's behavior for known Claude models, which are all mapped).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_claude_code.py
import json
import os
import shutil
import tempfile
import unittest

from collectors import claude_code


class TestClaudeCodeCollector(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.proj_dir = os.path.join(self.tmp, "-home-user-DEV-demo")
        os.makedirs(self.proj_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _write_session(self, filename, lines):
        path = os.path.join(self.proj_dir, filename)
        with open(path, "w") as f:
            for rec in lines:
                f.write(json.dumps(rec) + "\n")

    def test_resolves_project_by_real_cwd_not_encoded_dirname(self):
        self._write_session("sess1.jsonl", [
            {"type": "ai-title", "aiTitle": "Mi tarea", "sessionId": "sess1"},
            {
                "type": "assistant", "cwd": "/home/user/DEV/demo",
                "timestamp": "2026-08-01T10:00:00Z",
                "message": {
                    "model": "claude-sonnet-5",
                    "usage": {
                        "input_tokens": 100, "output_tokens": 50,
                        "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
                    },
                },
            },
        ])

        data = claude_code.collect(projects_dir=self.tmp)

        self.assertIn("/home/user/DEV/demo", data)
        self.assertNotIn("-home-user-DEV-demo", data)
        proj = data["/home/user/DEV/demo"]
        self.assertEqual(proj["input"], 100)
        self.assertEqual(proj["output"], 50)
        self.assertEqual(proj["messages"], 1)
        self.assertEqual(proj["session_count"], 1)
        self.assertEqual(proj["sessions_detail"][0]["title"], "Mi tarea")

    def test_missing_projects_dir_returns_empty_dict(self):
        data = claude_code.collect(projects_dir=os.path.join(self.tmp, "does-not-exist"))
        self.assertEqual(data, {})

    def test_non_assistant_records_are_ignored(self):
        self._write_session("sess2.jsonl", [
            {"type": "queue-operation", "content": "irrelevant"},
        ])
        data = claude_code.collect(projects_dir=self.tmp)
        self.assertEqual(data, {})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ai-monitor && python3 -m unittest tests.test_claude_code -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collectors.claude_code'`

- [ ] **Step 3: Write minimal implementation**

```python
# collectors/claude_code.py
"""Collector de uso de Claude Code, leyendo transcripts locales en
~/.claude/projects/*/*.jsonl.
"""
import glob
import json
import os
from collections import defaultdict

from collectors.pricing import cost_of


def collect(projects_dir=None):
    if projects_dir is None:
        projects_dir = os.path.expanduser("~/.claude/projects")

    if not os.path.isdir(projects_dir):
        return {}

    projects = defaultdict(lambda: {
        "input": 0, "output": 0, "cache_read": 0, "cache_write": 0,
        "cost": 0.0, "messages": 0, "sessions": set(),
        "sessions_detail": defaultdict(lambda: {
            "tokens": 0, "cost": 0.0, "title": None, "last_ts": None, "cwd": None
        }),
    })

    for d in sorted(glob.glob(os.path.join(projects_dir, "*"))):
        if not os.path.isdir(d):
            continue
        dname = os.path.basename(d)
        for jf in glob.glob(os.path.join(d, "*.jsonl")):
            session_id = os.path.basename(jf).replace(".jsonl", "")
            with open(jf, "r", errors="ignore") as fh:
                lines = fh.readlines()

            resolved_name = dname
            title_for_session = None
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("type") == "ai-title" and rec.get("aiTitle"):
                    title_for_session = rec["aiTitle"]
                if rec.get("cwd"):
                    resolved_name = rec["cwd"]
                    break

            if title_for_session:
                projects[resolved_name]["sessions_detail"][session_id]["title"] = title_for_session

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if rec.get("type") != "assistant":
                    continue

                msg = rec.get("message") or {}
                usage = msg.get("usage")
                if not usage:
                    continue

                model = msg.get("model")
                ts = rec.get("timestamp")
                cwd = rec.get("cwd")

                inp = usage.get("input_tokens", 0) or 0
                out = usage.get("output_tokens", 0) or 0
                cr = usage.get("cache_read_input_tokens", 0) or 0
                cw = usage.get("cache_creation_input_tokens", 0) or 0
                c = cost_of(inp, out, cr, cw, model) or 0.0

                p = projects[resolved_name]
                p["input"] += inp
                p["output"] += out
                p["cache_read"] += cr
                p["cache_write"] += cw
                p["cost"] += c
                p["messages"] += 1
                p["sessions"].add(session_id)

                sd = p["sessions_detail"][session_id]
                sd["tokens"] += inp + out + cr + cw
                sd["cost"] += c
                sd["cwd"] = cwd or sd["cwd"]
                if ts and (sd["last_ts"] is None or ts > sd["last_ts"]):
                    sd["last_ts"] = ts

    out = {}
    for name, p in projects.items():
        out[name] = {
            "input": p["input"], "output": p["output"],
            "cache_read": p["cache_read"], "cache_write": p["cache_write"],
            "total_tokens": p["input"] + p["output"] + p["cache_read"] + p["cache_write"],
            "cost": round(p["cost"], 4),
            "messages": p["messages"],
            "session_count": len(p["sessions"]),
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
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd ai-monitor
git add collectors/claude_code.py tests/test_claude_code.py
git commit -m "feat: extraer collector de Claude Code como módulo independiente"
```

---

### Task 3: Codex collector

**Files:**
- Create: `collectors/codex.py`
- Test: `tests/test_codex.py`

**Interfaces:**
- Consumes: `collectors.pricing.cost_of(...)`
- Produces: `collect(state_db_path: str | None = None) -> dict[str, dict]` — same per-project shape as `claude_code.collect()`. Each Codex thread becomes one `sessions_detail` entry (Codex threads don't have a message-level breakdown, only a per-thread `tokens_used` total, so `messages` counts threads, not individual assistant turns).
  `state_db_path` defaults to `os.path.expanduser("~/.codex/state_5.sqlite")`.
  If the DB file doesn't exist, or the `threads` table is missing/unreadable, returns `{}` (no exception).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_codex.py
import os
import sqlite3
import tempfile
import unittest

from collectors import codex


SCHEMA = """
CREATE TABLE threads (
    id TEXT, cwd TEXT, model TEXT, tokens_used INTEGER,
    created_at INTEGER, title TEXT
);
"""


class TestCodexCollector(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        self.tmp.close()
        con = sqlite3.connect(self.tmp.name)
        con.execute(SCHEMA)
        con.execute(
            "INSERT INTO threads (id, cwd, model, tokens_used, created_at, title) VALUES (?,?,?,?,?,?)",
            ("t1", "/home/user/DEV/demo", "gpt-5.5", 26392, 1781898850, "Prueba de comunicación"),
        )
        con.commit()
        con.close()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_collects_thread_into_project(self):
        data = codex.collect(state_db_path=self.tmp.name)

        self.assertIn("/home/user/DEV/demo", data)
        proj = data["/home/user/DEV/demo"]
        self.assertEqual(proj["total_tokens"], 26392)
        self.assertEqual(proj["session_count"], 1)
        self.assertEqual(proj["sessions_detail"][0]["title"], "Prueba de comunicación")
        self.assertGreater(proj["cost"], 0)

    def test_missing_db_file_returns_empty_dict(self):
        data = codex.collect(state_db_path="/nonexistent/path/state_5.sqlite")
        self.assertEqual(data, {})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ai-monitor && python3 -m unittest tests.test_codex -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collectors.codex'`

- [ ] **Step 3: Write minimal implementation**

```python
# collectors/codex.py
"""Collector de uso de Codex, leyendo ~/.codex/state_5.sqlite (tabla `threads`)."""
import os
import sqlite3
from collections import defaultdict

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
        "cost": 0.0, "messages": 0, "session_count": 0, "sessions_detail": [],
    })

    for row in rows:
        cwd = row["cwd"] or "unknown"
        tokens_used = row["tokens_used"] or 0
        model = row["model"]
        # No hay desglose input/output en Codex: se trata todo como "input"
        # para que el total_tokens sea correcto; el costo usa el mismo total
        # como input puro (aproximación documentada en el README).
        cost = cost_of(tokens_used, 0, 0, 0, model) or 0.0

        p = projects[cwd]
        p["input"] += tokens_used
        p["cost"] += cost
        p["messages"] += 1
        p["session_count"] += 1
        p["sessions_detail"].append({
            "session_id": row["id"],
            "tokens": tokens_used,
            "cost": round(cost, 4),
            "title": row["title"],
            "last_ts": row["created_at"],
            "cwd": cwd,
        })

    out = {}
    for name, p in projects.items():
        out[name] = {
            "input": p["input"], "output": 0, "cache_read": 0, "cache_write": 0,
            "total_tokens": p["input"],
            "cost": round(p["cost"], 4),
            "messages": p["messages"],
            "session_count": p["session_count"],
            "sessions_detail": p["sessions_detail"],
        }
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ai-monitor && python3 -m unittest tests.test_codex -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
cd ai-monitor
git add collectors/codex.py tests/test_codex.py
git commit -m "feat: agregar collector de Codex (state_5.sqlite)"
```

---

### Task 4: OpenCode collector

**Files:**
- Create: `collectors/opencode.py`
- Test: `tests/test_opencode.py`

**Interfaces:**
- Produces: `collect(db_path: str | None = None) -> dict[str, dict]` — same per-project shape. Uses `session.cost` verbatim (no call to `pricing.cost_of`). `db_path` defaults to `os.path.expanduser("~/.local/share/opencode/opencode.db")`.
  A session with `directory IS NULL` is grouped under the key `"unknown"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_opencode.py
import os
import sqlite3
import tempfile
import unittest

from collectors import opencode


SCHEMA = """
CREATE TABLE session (
    id TEXT, directory TEXT, model TEXT, title TEXT, cost REAL,
    tokens_input INTEGER, tokens_output INTEGER,
    tokens_cache_read INTEGER, tokens_cache_write INTEGER,
    time_created INTEGER
);
"""


class TestOpenCodeCollector(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        con = sqlite3.connect(self.tmp.name)
        con.execute(SCHEMA)
        con.execute(
            "INSERT INTO session (id, directory, model, title, cost, tokens_input, "
            "tokens_output, tokens_cache_read, tokens_cache_write, time_created) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("s1", "/home/user/DEV/demo", '{"id":"gpt-5.5","providerID":"openai"}',
             "Sesión demo", 0.22, 1000, 200, 500, 100, 1777996210131),
        )
        con.commit()
        con.close()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_collects_session_using_reported_cost(self):
        data = opencode.collect(db_path=self.tmp.name)

        self.assertIn("/home/user/DEV/demo", data)
        proj = data["/home/user/DEV/demo"]
        self.assertEqual(proj["input"], 1000)
        self.assertEqual(proj["output"], 200)
        self.assertEqual(proj["cache_read"], 500)
        self.assertEqual(proj["cache_write"], 100)
        self.assertAlmostEqual(proj["cost"], 0.22)
        self.assertEqual(proj["session_count"], 1)

    def test_missing_db_returns_empty_dict(self):
        data = opencode.collect(db_path="/nonexistent/opencode.db")
        self.assertEqual(data, {})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ai-monitor && python3 -m unittest tests.test_opencode -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collectors.opencode'`

- [ ] **Step 3: Write minimal implementation**

```python
# collectors/opencode.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ai-monitor && python3 -m unittest tests.test_opencode -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
cd ai-monitor
git add collectors/opencode.py tests/test_opencode.py
git commit -m "feat: agregar collector de OpenCode (opencode.db, costo reportado directo)"
```

---

### Task 5: OpenRouter collector

**Files:**
- Create: `collectors/openrouter.py`
- Test: `tests/test_openrouter.py`

**Interfaces:**
- Produces: `collect(api_key: str | None = None, fetch=None) -> dict`.
  - If `api_key` is `None`, reads `os.environ.get("OPENROUTER_API_KEY")`; if still `None`, returns `{"unavailable": True, "reason": "OPENROUTER_API_KEY no está definida"}`.
  - `fetch` is an injected callable `(url: str, api_key: str) -> dict` used only by tests (defaults to a real `urllib.request`-based function `_http_get_json`), so tests never hit the network.
  - On success returns `{"unavailable": False, "models": {model_id: {"tokens": int, "cost": float, "requests": int}}, "by_day": {date: {"tokens": int, "cost": float}}}`, built by walking the `/api/v1/activity` response (list of daily rows, each with `model`, `date`, `usage` in USD, `tokens` or `prompt_tokens`/`completion_tokens` — the exact field names below are asserted by the test to lock the parsing contract).
  - On any request error (network, non-200, JSON decode) returns `{"unavailable": True, "reason": "<mensaje corto>"}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_openrouter.py
import unittest

from collectors import openrouter


class TestOpenRouterCollector(unittest.TestCase):
    def test_missing_api_key_marks_unavailable(self):
        data = openrouter.collect(api_key=None, fetch=lambda url, key: {})
        self.assertTrue(data["unavailable"])
        self.assertIn("OPENROUTER_API_KEY", data["reason"])

    def test_successful_fetch_aggregates_by_model_and_day(self):
        fake_response = {
            "data": [
                {"model": "openai/gpt-5.5", "date": "2026-08-10",
                 "usage": 0.5, "prompt_tokens": 1000, "completion_tokens": 200},
                {"model": "openai/gpt-5.5", "date": "2026-08-11",
                 "usage": 0.25, "prompt_tokens": 500, "completion_tokens": 100},
                {"model": "anthropic/claude-sonnet-5", "date": "2026-08-11",
                 "usage": 1.0, "prompt_tokens": 2000, "completion_tokens": 300},
            ]
        }

        data = openrouter.collect(api_key="fake-key", fetch=lambda url, key: fake_response)

        self.assertFalse(data["unavailable"])
        self.assertEqual(data["models"]["openai/gpt-5.5"]["tokens"], 1000 + 200 + 500 + 100)
        self.assertAlmostEqual(data["models"]["openai/gpt-5.5"]["cost"], 0.75)
        self.assertEqual(data["models"]["openai/gpt-5.5"]["requests"], 2)
        self.assertIn("anthropic/claude-sonnet-5", data["models"])
        self.assertAlmostEqual(data["by_day"]["2026-08-11"]["cost"], 1.25)

    def test_fetch_error_marks_unavailable_with_reason(self):
        def failing_fetch(url, key):
            raise RuntimeError("HTTP 401")

        data = openrouter.collect(api_key="bad-key", fetch=failing_fetch)
        self.assertTrue(data["unavailable"])
        self.assertIn("401", data["reason"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ai-monitor && python3 -m unittest tests.test_openrouter -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collectors.openrouter'`

- [ ] **Step 3: Write minimal implementation**

```python
# collectors/openrouter.py
"""Collector de uso de OpenRouter vía su API REST (/api/v1/activity).
No lee la key de ningún archivo de otra herramienta (ver spec: el token de
OpenCode no es una API key válida) — solo de OPENROUTER_API_KEY.
"""
import json
import os
import urllib.request
from collections import defaultdict

ACTIVITY_URL = "https://openrouter.ai/api/v1/activity"


def _http_get_json(url, api_key):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def collect(api_key=None, fetch=None):
    if api_key is None:
        api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {"unavailable": True, "reason": "OPENROUTER_API_KEY no está definida"}

    if fetch is None:
        fetch = _http_get_json

    try:
        response = fetch(ACTIVITY_URL, api_key)
    except Exception as e:
        return {"unavailable": True, "reason": str(e)}

    models = defaultdict(lambda: {"tokens": 0, "cost": 0.0, "requests": 0})
    by_day = defaultdict(lambda: {"tokens": 0, "cost": 0.0})

    for row in response.get("data", []):
        model = row.get("model", "unknown")
        date = row.get("date", "unknown")
        cost = row.get("usage", 0.0) or 0.0
        tokens = (row.get("prompt_tokens", 0) or 0) + (row.get("completion_tokens", 0) or 0)

        models[model]["tokens"] += tokens
        models[model]["cost"] += cost
        models[model]["requests"] += 1

        by_day[date]["tokens"] += tokens
        by_day[date]["cost"] += cost

    return {
        "unavailable": False,
        "models": {k: {"tokens": v["tokens"], "cost": round(v["cost"], 4), "requests": v["requests"]}
                   for k, v in models.items()},
        "by_day": {k: {"tokens": v["tokens"], "cost": round(v["cost"], 4)} for k, v in by_day.items()},
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ai-monitor && python3 -m unittest tests.test_openrouter -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd ai-monitor
git add collectors/openrouter.py tests/test_openrouter.py
git commit -m "feat: agregar collector de OpenRouter vía API /activity, degrada sin API key"
```

---

### Task 6: Dashboard template con pestañas

**Files:**
- Create: `dashboard/__init__.py` (empty)
- Create: `dashboard/template.py`
- Test: `tests/test_template.py`

**Interfaces:**
- Consumes: nothing from other collectors directly — takes plain dicts matching the shapes from Tasks 2-5.
- Produces: `render(sources: dict[str, dict], combined: dict[str, dict], generated_at: str) -> str`.
  - `sources` = `{"claude_code": <dict from claude_code.collect()>, "codex": <...>, "opencode": <...>, "openrouter": <dict from openrouter.collect()>}`.
  - `combined` = pre-summed per-project dict (Claude Code + Codex + OpenCode only) with an added `"by_source"` list per project entry — this combining logic lives in `main.py` (Task 7), `template.py` only renders whatever it's given.
  - Returns a complete self-contained HTML document (string) — no CDN, inline CSS/JS, `prefers-color-scheme` dark mode, same visual language as the current dashboard.

Because HTML output isn't meaningfully unit-tested line-by-line, the test only locks the **contract**: given input data, the returned string contains expected markers (tab labels, a project name, an "unavailable" message for a missing source). This is a smoke test, not a full snapshot test — deliberate, since the visual design will keep evolving without needing to update a brittle full-HTML assertion.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_template.py
import unittest

from dashboard import template


class TestDashboardTemplate(unittest.TestCase):
    def test_renders_project_and_all_tabs(self):
        sources = {
            "claude_code": {"/home/user/demo": {
                "input": 100, "output": 50, "cache_read": 0, "cache_write": 0,
                "total_tokens": 150, "cost": 0.01, "messages": 1, "session_count": 1,
                "sessions_detail": [],
            }},
            "codex": {},
            "opencode": {},
            "openrouter": {"unavailable": True, "reason": "OPENROUTER_API_KEY no está definida"},
        }
        combined = {"/home/user/demo": {
            "total_tokens": 150, "cost": 0.01, "messages": 1, "session_count": 1,
            "by_source": ["claude_code"],
        }}

        html = template.render(sources, combined, generated_at="2026-08-11 12:00")

        self.assertIn("<!doctype html>", html.lower())
        self.assertIn("Claude Code", html)
        self.assertIn("Codex", html)
        self.assertIn("OpenCode", html)
        self.assertIn("OpenRouter", html)
        self.assertIn("/home/user/demo", html)
        self.assertIn("OPENROUTER_API_KEY", html)  # unavailable reason surfaced


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ai-monitor && python3 -m unittest tests.test_template -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dashboard'`

- [ ] **Step 3: Write minimal implementation**

```python
# dashboard/template.py
"""Dashboard HTML autocontenido, con pestañas por fuente + una vista 'Todo'."""
import json

_HTML = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Uso de IA por proyecto</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{
  --bg:#0b0e14; --panel:#12161f; --panel2:#171c27; --text:#e6e9ef; --muted:#8b95a7;
  --accent:#7c9eff; --border:#232938;
}
@media (prefers-color-scheme: light){
  :root{ --bg:#f5f6f8; --panel:#ffffff; --panel2:#f0f1f4; --text:#1a1d24; --muted:#5a6272; --border:#e2e4ea; }
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding:24px;}
h1{font-size:1.4rem;margin:0 0 4px}
.sub{color:var(--muted);font-size:.85rem;margin-bottom:20px}
.tabs{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}
.tab{padding:8px 14px;border-radius:8px;border:1px solid var(--border);background:var(--panel);cursor:pointer;font-size:.85rem}
.tab.active{background:var(--accent);color:#0b0e14;border-color:var(--accent)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:24px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px}
.card .label{color:var(--muted);font-size:.75rem;text-transform:uppercase;letter-spacing:.05em}
.card .value{font-size:1.5rem;font-weight:600;margin-top:4px}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--border);border-radius:10px;overflow:hidden}
th,td{padding:10px 12px;text-align:left;font-size:.85rem;border-bottom:1px solid var(--border)}
th{color:var(--muted);font-weight:600}
tr:last-child td{border-bottom:none}
tr:hover td{background:var(--panel2)}
.num{text-align:right;font-variant-numeric:tabular-nums}
.pname{max-width:340px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.panel{display:none}
.panel.active{display:block}
.notice{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:16px;color:var(--muted)}
</style>
</head>
<body>
<h1>Uso de IA por proyecto</h1>
<div class="sub">Generado __GENERATED_AT__ · Claude Code · Codex · OpenCode · OpenRouter</div>

<div class="tabs" id="tabs"></div>
<div id="panels"></div>

<script>
const sources = __SOURCES__;
const combined = __COMBINED__;

const TAB_LABELS = {
  all: "Todo", claude_code: "Claude Code", codex: "Codex",
  opencode: "OpenCode", openrouter: "OpenRouter",
};

function fmtNum(n) { return (n || 0).toLocaleString(); }
function fmtCost(n) { return n == null ? "—" : "$" + n.toFixed(2); }

function renderProjectTable(data) {
  const rows = Object.entries(data).sort((a, b) => (b[1].total_tokens||0) - (a[1].total_tokens||0));
  const totalTokens = rows.reduce((s, [, v]) => s + (v.total_tokens || 0), 0);
  const totalCost = rows.reduce((s, [, v]) => s + (v.cost || 0), 0);
  let html = `<div class="grid">
    <div class="card"><div class="label">Proyectos</div><div class="value">${rows.length}</div></div>
    <div class="card"><div class="label">Tokens</div><div class="value">${fmtNum(totalTokens)}</div></div>
    <div class="card"><div class="label">Costo est.</div><div class="value">${fmtCost(totalCost)}</div></div>
  </div>`;
  html += `<table><thead><tr><th>Proyecto</th><th class="num">Tokens</th><th class="num">Costo</th>
    <th class="num">Msgs</th><th class="num">Sesiones</th></tr></thead><tbody>`;
  for (const [name, v] of rows) {
    html += `<tr><td class="pname" title="${name}">${name}</td>
      <td class="num">${fmtNum(v.total_tokens)}</td><td class="num">${fmtCost(v.cost)}</td>
      <td class="num">${v.messages || 0}</td><td class="num">${v.session_count || 0}</td></tr>`;
  }
  html += `</tbody></table>`;
  return html;
}

function renderOpenRouter(data) {
  if (data.unavailable) {
    return `<div class="notice">OpenRouter no disponible: ${data.reason}</div>`;
  }
  const rows = Object.entries(data.models || {}).sort((a, b) => b[1].tokens - a[1].tokens);
  let html = `<table><thead><tr><th>Modelo</th><th class="num">Tokens</th>
    <th class="num">Costo</th><th class="num">Requests</th></tr></thead><tbody>`;
  for (const [model, v] of rows) {
    html += `<tr><td class="pname" title="${model}">${model}</td>
      <td class="num">${fmtNum(v.tokens)}</td><td class="num">${fmtCost(v.cost)}</td>
      <td class="num">${v.requests}</td></tr>`;
  }
  html += `</tbody></table>`;
  return html;
}

const tabsEl = document.getElementById('tabs');
const panelsEl = document.getElementById('panels');
const tabKeys = ['all', 'claude_code', 'codex', 'opencode', 'openrouter'];

tabKeys.forEach((key, i) => {
  const btn = document.createElement('button');
  btn.className = 'tab' + (i === 0 ? ' active' : '');
  btn.textContent = TAB_LABELS[key];
  btn.onclick = () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('panel-' + key).classList.add('active');
  };
  tabsEl.appendChild(btn);

  const panel = document.createElement('div');
  panel.className = 'panel' + (i === 0 ? ' active' : '');
  panel.id = 'panel-' + key;
  if (key === 'all') panel.innerHTML = renderProjectTable(combined);
  else if (key === 'openrouter') panel.innerHTML = renderOpenRouter(sources.openrouter || {unavailable: true, reason: 'sin datos'});
  else panel.innerHTML = renderProjectTable(sources[key] || {});
  panelsEl.appendChild(panel);
});
</script>
</body>
</html>
"""


def render(sources, combined, generated_at):
    html = _HTML.replace("__GENERATED_AT__", generated_at)
    html = html.replace("__SOURCES__", json.dumps(sources))
    html = html.replace("__COMBINED__", json.dumps(combined))
    return html
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ai-monitor && python3 -m unittest tests.test_template -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
cd ai-monitor
git add dashboard/__init__.py dashboard/template.py tests/test_template.py
git commit -m "feat: agregar dashboard HTML con pestañas por fuente"
```

---

### Task 7: `main.py` orchestrator

**Files:**
- Create: `main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `collectors.claude_code.collect()`, `collectors.codex.collect()`, `collectors.opencode.collect()`, `collectors.openrouter.collect()`, `dashboard.template.render(sources, combined, generated_at)`.
- Produces: `combine_projects(claude_data: dict, codex_data: dict, opencode_data: dict) -> dict` — the pure merging function tested directly (sums `total_tokens`/`cost`/`messages`/`session_count` across sources for the same project key, tracks `by_source: list[str]`). `main()` is the CLI entry point (`--json`, `--html PATH`, default table), not unit tested (it's argument parsing + I/O glue, covered by the manual smoke test in Step 5 below).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_main.py
import unittest

from main import combine_projects


class TestCombineProjects(unittest.TestCase):
    def test_sums_matching_projects_across_sources(self):
        claude = {"/home/user/demo": {"total_tokens": 100, "cost": 0.1, "messages": 2, "session_count": 1}}
        codex = {"/home/user/demo": {"total_tokens": 50, "cost": 0.05, "messages": 1, "session_count": 1}}
        opencode = {"/home/user/other": {"total_tokens": 30, "cost": 0.02, "messages": 1, "session_count": 1}}

        combined = combine_projects(claude, codex, opencode)

        self.assertEqual(combined["/home/user/demo"]["total_tokens"], 150)
        self.assertAlmostEqual(combined["/home/user/demo"]["cost"], 0.15)
        self.assertEqual(sorted(combined["/home/user/demo"]["by_source"]), ["claude_code", "codex"])
        self.assertEqual(combined["/home/user/other"]["total_tokens"], 30)
        self.assertEqual(combined["/home/user/other"]["by_source"], ["opencode"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ai-monitor && python3 -m unittest tests.test_main -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
"""Dashboard multiplataforma de uso de IA: Claude Code, Codex, OpenCode, OpenRouter.

Uso:
  main.py               -> resumen en terminal (tabla, vista combinada)
  main.py --json         -> vuelca todas las fuentes crudas en JSON (stdout)
  main.py --html out.html -> genera dashboard HTML con pestañas por fuente
"""
import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone

from collectors import claude_code, codex, opencode, openrouter
from dashboard import template


def combine_projects(claude_data, codex_data, opencode_data):
    combined = defaultdict(lambda: {"total_tokens": 0, "cost": 0.0, "messages": 0,
                                     "session_count": 0, "by_source": []})
    for source_name, data in (("claude_code", claude_data), ("codex", codex_data),
                               ("opencode", opencode_data)):
        for project, v in data.items():
            c = combined[project]
            c["total_tokens"] += v.get("total_tokens", 0)
            c["cost"] += v.get("cost", 0) or 0
            c["messages"] += v.get("messages", 0)
            c["session_count"] += v.get("session_count", 0)
            c["by_source"].append(source_name)

    return {k: {**v, "cost": round(v["cost"], 4)} for k, v in combined.items()}


def collect_all():
    return {
        "claude_code": claude_code.collect(),
        "codex": codex.collect(),
        "opencode": opencode.collect(),
        "openrouter": openrouter.collect(),
    }


def print_table(sources, combined):
    rows = sorted(combined.items(), key=lambda kv: kv[1]["total_tokens"], reverse=True)
    total_tokens = sum(v["total_tokens"] for _, v in rows)
    total_cost = sum(v["cost"] for _, v in rows)
    name_w = max([len(k) for k, _ in rows] + [7])

    header = f"{'PROYECTO':<{name_w}}  {'TOKENS':>12}  {'COSTO $':>10}  {'FUENTES':>20}"
    print(header)
    print("-" * len(header))
    for name, v in rows:
        print(f"{name:<{name_w}}  {v['total_tokens']:>12,}  {v['cost']:>10.2f}  {','.join(v['by_source']):>20}")
    print("-" * len(header))
    print(f"{'TOTAL':<{name_w}}  {total_tokens:>12,}  {total_cost:>10.2f}")
    print("\n(Vista combinada: Claude Code + Codex + OpenCode. OpenRouter no se suma aquí — ver --html.)")

    orr = sources.get("openrouter", {})
    if orr.get("unavailable"):
        print(f"\nOpenRouter no disponible: {orr.get('reason')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--html", metavar="OUT")
    args = ap.parse_args()

    sources = collect_all()
    combined = combine_projects(sources["claude_code"], sources["codex"], sources["opencode"])

    if args.html:
        generated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
        html = template.render(sources, combined, generated_at)
        with open(args.html, "w") as f:
            f.write(html)
        print(f"Dashboard generado en: {args.html}")
    elif args.json:
        print(json.dumps({"sources": sources, "combined": combined}, indent=2))
    else:
        print_table(sources, combined)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ai-monitor && python3 -m unittest tests.test_main -v`
Expected: PASS (1 test)

- [ ] **Step 5: Manual smoke test (not automated — exercises real local data)**

```bash
cd ai-monitor
python3 main.py                              # tabla combinada en terminal
python3 main.py --html /tmp/ai-monitor-smoke.html
python3 -c "import webbrowser,os; print(os.path.getsize('/tmp/ai-monitor-smoke.html'), 'bytes')"
```
Expected: tabla imprime sin excepciones (con o sin OpenRouter disponible), el HTML se genera y pesa más de unos pocos KB.

- [ ] **Step 6: Commit**

```bash
cd ai-monitor
git add main.py tests/test_main.py
git commit -m "feat: agregar main.py orquestando los 4 collectors con vista combinada"
```

---

### Task 8: Retirar `claude_usage.py` y actualizar documentación

**Files:**
- Delete: `claude_usage.py`
- Modify: `README.md`
- Modify: `CLAUDE.md`

**Interfaces:** ninguna — solo documentación y limpieza, sin lógica nueva.

- [ ] **Step 1: Eliminar el script legado**

```bash
cd ai-monitor
git rm claude_usage.py
```

- [ ] **Step 2: Reescribir README.md**

Reemplazar el contenido completo por (mantiene la sección de portabilidad ya escrita, actualiza comandos a `main.py` y agrega las 4 fuentes):

```markdown
# ai-monitor

Dashboard local de uso de IA: agrega tokens y costo por proyecto a partir de los datos que **Claude Code**, **Codex** y **OpenCode** guardan localmente, más el consumo reportado por **OpenRouter** vía su API. Sin dependencias externas — solo librería estándar de Python.

## Fuentes soportadas

| Fuente | De dónde lee | Agrupa por |
|---|---|---|
| Claude Code | `~/.claude/projects/*/*.jsonl` | proyecto (cwd real) |
| Codex | `~/.codex/state_5.sqlite` | proyecto (cwd) |
| OpenCode | `~/.local/share/opencode/opencode.db` | proyecto (directory) |
| OpenRouter | API `openrouter.ai/api/v1/activity` (requiere `OPENROUTER_API_KEY`) | modelo |

Cada fuente que no esté instalada, o cuya key no esté configurada, se omite con un aviso — el resto del dashboard sigue funcionando.

## Uso

```bash
python3 main.py                     # tabla combinada en terminal (Claude+Codex+OpenCode)
python3 main.py --json              # todas las fuentes crudas + vista combinada, en JSON
python3 main.py --html out.html     # dashboard HTML con pestañas por fuente
```

## OpenRouter

Genera una API key en https://openrouter.ai/keys y expórtala:

```bash
export OPENROUTER_API_KEY="sk-or-..."
```

Sin esta variable, la pestaña de OpenRouter muestra un aviso en vez de datos; el resto del dashboard no se ve afectado.

## Instalación (alias + actualización automática)

1. Clona el repo donde prefieras.
2. Agrega una línea a tu `~/.bashrc` (o `~/.zshrc`) apuntando a donde lo clonaste:

   ```bash
   source "/ruta/donde/clonaste/ai-monitor/shell/aliases.sh"
   ```

3. Recarga la shell (`source ~/.bashrc`). Quedan disponibles:
   - `claude-usage` → regenera `~/claude-usage.html` y lo abre en el navegador.
   - `claude-usage-table` → imprime la tabla combinada en la terminal.

4. (Opcional) Para que el dashboard se mantenga fresco solo, corre:

   ```bash
   ./install.sh
   ```

   Detecta automáticamente dónde quedó el repo y genera una unidad `systemd --user` que regenera el HTML cada 15 minutos. El script imprime el comando final (`systemctl --user enable --now ai-monitor.timer`) sin ejecutarlo — lo corres tú cuando quieras activarlo.

## Sobre el costo estimado

- Claude Code y Codex: costo **estimado** con una tabla de precios de lista por modelo (`collectors/pricing.py`). Si el modelo no está mapeado, el costo de esa sesión no se estima (no se usa un precio por defecto que podría ser incorrecto).
- OpenCode: usa el costo que **OpenCode ya calculó** para cada sesión — no se re-estima.
- OpenRouter: costo real reportado por su API.

Ninguno de estos números refleja lo que realmente pagas si usas un plan de suscripción (Pro/Max) en vez de facturación por API — son un proxy relativo para comparar qué tan pesado es un proyecto o tarea frente a otro.

**Nota sobre OpenCode + OpenRouter**: cuando OpenCode enruta un modelo a través de OpenRouter, ese consumo puede aparecer en ambas pestañas. La vista "Todo" combinada solo suma Claude Code + Codex + OpenCode (nunca OpenRouter) para evitar doble conteo.

## Arquitectura

```
main.py                # CLI: --json / --html / tabla por defecto
collectors/
  pricing.py            # tabla de precios compartida
  claude_code.py         # ~/.claude/projects/*.jsonl
  codex.py                # ~/.codex/state_5.sqlite
  opencode.py              # ~/.local/share/opencode/opencode.db
  openrouter.py             # API REST openrouter.ai
dashboard/
  template.py               # HTML con pestañas, self-contained
shell/aliases.sh              # alias portables (BASH_SOURCE-relativo)
install.sh                     # genera unidad systemd --user
```

Cada collector expone `collect(...)` con un parámetro opcional para inyectar la ruta/fuente en tests, y se degrada a `{}` (o `{"unavailable": True, "reason": ...}` en OpenRouter) si la plataforma no está instalada — nunca lanza una excepción que tumbe el resto del dashboard.

## Tests

```bash
python3 -m unittest discover -s tests -v
```
```

- [ ] **Step 3: Reescribir CLAUDE.md**

Reemplazar el contenido completo por:

```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A dependency-free Python dashboard that aggregates local AI usage (tokens, cost) across Claude Code, Codex, and OpenCode, plus OpenRouter via its REST API, grouped by project directory (or by model for OpenRouter).

## Commands

```bash
python3 main.py                     # combined terminal table (Claude Code + Codex + OpenCode)
python3 main.py --json              # all raw per-source data + combined view, as JSON
python3 main.py --html out.html     # tabbed self-contained HTML dashboard
python3 -m unittest discover -s tests -v   # run the test suite
```

No build step, no external dependencies (stdlib only — `sqlite3`, `json`, `urllib.request`, `argparse`, `unittest`).

## Architecture

Each data source is an isolated collector module under `collectors/`, all sharing one contract:

- **Per-project collectors** (`claude_code.py`, `codex.py`, `opencode.py`): `collect(source_override=None) -> dict[str, dict]`, keyed by the real project directory (never the encoded/ambiguous directory name Claude Code uses on disk). Each returns the same shape: `{input, output, cache_read, cache_write, total_tokens, cost, messages, session_count, sessions_detail}`. This uniform shape is what lets `main.combine_projects()` sum across sources without source-specific logic.
- **`openrouter.py`** breaks that pattern deliberately: OpenRouter has no notion of a project directory, so it aggregates by model instead, and returns `{"unavailable": True, "reason": ...}` when `OPENROUTER_API_KEY` isn't set or the request fails — every consumer of this collector must check `unavailable` before touching `models`/`by_day`.
- **`pricing.py`** is the only shared estimation logic, used by `claude_code.py` and `codex.py`. `opencode.py` deliberately does NOT use it — OpenCode's SQLite `session.cost` is already computed by OpenCode itself with the real provider price, so re-estimating it would be both redundant and less accurate. If you're tempted to route OpenCode through `pricing.cost_of`, don't — that's a known anti-pattern here.
- **Graceful degradation is load-bearing**: every collector must return an empty/unavailable result on a missing file, missing table, or any `sqlite3.Error`/network error — never let one absent platform take down the whole dashboard. `main.py` and `dashboard/template.py` both assume collectors already sanitized their own failures; they don't wrap collector calls in additional try/except.
- **`dashboard/template.py`** renders a single self-contained HTML string (no CDN, inline CSS/JS, `prefers-color-scheme` dark mode) with a JS-side tab switcher over pre-serialized JSON (`sources`, `combined`) — there's no server, the "interactivity" is just show/hide over data baked into the page at generation time.
- **The "Todo" combined view never includes OpenRouter.** This is intentional (see README's "OpenCode + OpenRouter" note) — OpenCode sessions routed through OpenRouter's `providerID` can double-report the same consumption in both sources, and there's no reliable shared ID to deduplicate them. Don't "fix" this by adding OpenRouter into `combine_projects()`.

## Portability constraints

No file in this repo may contain a path specific to the original author's machine (no `/home/jruedadev`, no `~/DEV/JRDV/...`). `shell/aliases.sh` resolves its own location via `${BASH_SOURCE[0]}`; `install.sh` resolves the repo location via `dirname "$0"`. Keep it that way — this repo is meant to be cloned and used by other people as-is.
```

- [ ] **Step 4: Verificar que la suite completa sigue pasando y correr un smoke test final**

```bash
cd ai-monitor
python3 -m unittest discover -s tests -v
python3 main.py
```
Expected: todos los tests PASS, la tabla combinada imprime sin errores.

- [ ] **Step 5: Commit**

```bash
cd ai-monitor
git add -A
git commit -m "docs: actualizar README y CLAUDE.md para el dashboard multiplataforma; retirar claude_usage.py"
```

---

### Task 9: Portabilidad — `shell/aliases.sh`, `install.sh`, unidades systemd

**Files:**
- Create: `shell/aliases.sh`
- Create: `systemd/ai-monitor.service.template`
- Create: `systemd/ai-monitor.timer`
- Create: `install.sh`

**Interfaces:** ninguna en Python — son scripts de shell, verificados manualmente (no hay framework de test de shell en este repo y no se justifica añadir uno para 4 archivos de configuración).

- [ ] **Step 1: Crear `shell/aliases.sh`**

```bash
# shell/aliases.sh
# Alias portables para ai-monitor. Agregar a ~/.bashrc:
#   source "/ruta/donde/clonaste/ai-monitor/shell/aliases.sh"

_AI_MONITOR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

claude-usage() {
    python3 "$_AI_MONITOR_DIR/main.py" --html "$HOME/claude-usage.html" \
        && xdg-open "$HOME/claude-usage.html" >/dev/null 2>&1 &
}

alias claude-usage-table="python3 \"$_AI_MONITOR_DIR/main.py\""
```

- [ ] **Step 2: Crear `systemd/ai-monitor.service.template`**

```ini
[Unit]
Description=ai-monitor: regenerar dashboard de uso de IA

[Service]
Type=oneshot
ExecStart=__PYTHON__ __REPO_DIR__/main.py --html %h/claude-usage.html
```

- [ ] **Step 3: Crear `systemd/ai-monitor.timer`**

```ini
[Unit]
Description=Regenerar el dashboard de ai-monitor cada 15 minutos

[Timer]
OnBootSec=2min
OnUnitActiveSec=15min
Unit=ai-monitor.service

[Install]
WantedBy=timers.target
```

- [ ] **Step 4: Crear `install.sh`**

```bash
#!/usr/bin/env bash
# Genera la unidad systemd --user de ai-monitor con la ruta real del repo,
# sin hardcodear ninguna ruta de usuario en el código versionado.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="$(command -v python3)"
UNITS_DIR="$HOME/.config/systemd/user"

mkdir -p "$UNITS_DIR"

sed \
  -e "s#__REPO_DIR__#${REPO_DIR}#g" \
  -e "s#__PYTHON__#${PYTHON_BIN}#g" \
  "$REPO_DIR/systemd/ai-monitor.service.template" > "$UNITS_DIR/ai-monitor.service"

cp "$REPO_DIR/systemd/ai-monitor.timer" "$UNITS_DIR/ai-monitor.timer"

echo "Unidades instaladas en $UNITS_DIR"
echo ""
echo "Para activarlas, corre:"
echo "  systemctl --user daemon-reload"
echo "  systemctl --user enable --now ai-monitor.timer"
```

- [ ] **Step 5: Dar permisos de ejecución**

```bash
cd ai-monitor
chmod +x install.sh
```

- [ ] **Step 6: Verificación manual (no automatizada)**

```bash
cd ai-monitor
./install.sh
cat ~/.config/systemd/user/ai-monitor.service   # confirmar que __REPO_DIR__/__PYTHON__ quedaron resueltos, sin placeholders
```
Expected: el `.service` generado no contiene `__REPO_DIR__` ni `__PYTHON__` — ambos placeholders quedaron sustituidos por rutas reales de esta máquina, y el script no ejecutó `systemctl enable` por sí solo (confirmar con `systemctl --user is-enabled ai-monitor.timer` devolviendo "disabled" o error de "not found" hasta que el usuario lo active manualmente).

- [ ] **Step 7: Commit**

```bash
cd ai-monitor
git add shell/aliases.sh systemd/ install.sh
git commit -m "feat: agregar alias portables y generador de unidad systemd --user"
```

---

## Self-Review Notes

- **Spec coverage**: pricing/costo (Task 1), Claude Code migrado (Task 2), Codex (Task 3), OpenCode (Task 4), OpenRouter con degradación (Task 5), dashboard con pestañas + vista "Todo" sin OpenRouter (Task 6, Task 7's `combine_projects`), retiro de `claude_usage.py` + docs (Task 8), portabilidad de alias/systemd (Task 9). Todo lo del spec de 2026-08-11 está cubierto.
- **Placeholder scan**: sin TBD/TODO; los únicos `__REPO_DIR__`/`__PYTHON__` son placeholders *intencionales* del `.service.template`, sustituidos en tiempo de instalación por `install.sh` (Task 9, Step 4) — no son placeholders de este plan.
- **Type/name consistency**: `collect()` en los 4 collectors, `cost_of(input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, model)` en `pricing.py` usado igual en Tasks 2 y 3, `combine_projects(claude_data, codex_data, opencode_data)` y `template.render(sources, combined, generated_at)` usados con la misma firma entre Task 6 y Task 7.
