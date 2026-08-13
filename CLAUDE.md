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

- **Per-project collectors** (`claude_code.py`, `codex.py`, `opencode.py`): `collect(...) -> dict[str, dict]` — the optional override parameter's name varies by collector (`projects_dir`, `state_db_path`, `db_path`), keyed by the real project directory (never the encoded/ambiguous directory name Claude Code uses on disk). Each returns the same shape: `{input, output, cache_read, cache_write, total_tokens, cost, messages, session_count, sessions_detail}`. This uniform shape is what lets `main.combine_projects()` sum across sources without source-specific logic.
- **`openrouter.py`** breaks that pattern deliberately: OpenRouter has no notion of a project directory, so it aggregates by model instead, and returns `{"unavailable": True, "reason": ...}` when `OPENROUTER_API_KEY` isn't set or the request fails — every consumer of this collector must check `unavailable` before touching `models`/`by_day`. **`OPENROUTER_API_KEY` must be a management key** (see README's "OpenRouter" section): only management keys can fetch `/api/v1/activity`; a regular key returns `403 "Only management keys can fetch activity for an account"` and a revoked key returns `401 "User not found"`. The key is resolved from `OPENROUTER_API_KEY` first, then from `~/.config/ai-monitor/env` (written by `install.sh` with `chmod 600` and consumed by the systemd unit via `EnvironmentFile`) — never from other tools' config files, whose keys may be revoked or the wrong type. If you ever write a key source in here, it must follow that same `$OPENROUTER_API_KEY` → `~/.config/ai-monitor/env` chain.
- **`pricing.py`** is the only shared estimation logic, used by `claude_code.py` and `codex.py`. `opencode.py` deliberately does NOT use it — OpenCode's SQLite `session.cost` is already computed by OpenCode itself with the real provider price, so re-estimating it would be both redundant and less accurate. If you're tempted to route OpenCode through `pricing.cost_of`, don't — that's a known anti-pattern here. Prices themselves are **not** a hardcoded Python dict anymore: SQLite (`history.db`'s `pricing` table) is the source of truth, bootstrapped from `pricing.py`'s `_DEFAULT_SNAPSHOT` on first use. `pricing.py` only reads (with an in-process cache keyed by `db_path`, invalidated via `reset_cache()`); `collectors/sync_pricing.py` is the only supported writer (`--write`/`--check`). Don't edit the `pricing` table directly, and don't reintroduce a Python dict as the live source of prices.
- **Graceful degradation is load-bearing**: every collector must return an empty/unavailable result on a missing file, missing table, or any `sqlite3.Error`/network error — never let one absent platform take down the whole dashboard. `main.py` and `dashboard/template.py` both assume collectors already sanitized their own failures; they don't wrap collector calls in additional try/except.
- **`dashboard/template.py`** renders a single self-contained HTML string (no CDN, inline CSS/JS, `prefers-color-scheme` dark mode) with a JS-side tab switcher over pre-serialized JSON (`sources`, `combined`) — there's no server, the "interactivity" is just show/hide over data baked into the page at generation time.
- **`server.py`** is the live counterpart to `main.py --html`: it reuses `main.collect_all()`/`main.combine_projects()` unchanged, adds a background thread that re-collects every N seconds and diffs the JSON before publishing to `sse.SSEBroker`, and serves `frontend/dist/` as static files with SPA fallback. `sse.py` is deliberately socket-free (pure formatting + an in-memory pub/sub broker) so it's unit-testable without spinning up real connections — `server.py` is the only place that wires it to actual sockets.
- **`history.py`** is additive persistence, not a collector: `main.collect_all()` calls `history.record_snapshot()` after every collection (whether triggered by the CLI, the timer, or `server.py`'s background loop), writing daily rollups to `~/.local/share/ai-monitor/history.db` via `INSERT OR REPLACE`. The replace-not-delete semantics are load-bearing: a date that stops appearing in a collector's `by_day` output (because the provider rotated it out) is deliberately left untouched in `history.db` — that's the entire point of the table. Don't add a "prune stale rows" step; absence upstream is what preserves history here, not a signal to delete.
- **`frontend/`** is a separate Node/npm project (Vite + React + TypeScript + shadcn/ui + Tremor) with its own dependencies — this does not violate the backend's stdlib-only rule, which applies to `server.py`/`collectors/`/`history.py` only. The frontend talks to `server.py` exclusively through `/api/usage`, `/api/stream` (SSE), and `/api/history` — it has no other way to reach collector data.
- **The "Todo" combined view never includes OpenRouter.** This is intentional (see README's "OpenCode + OpenRouter" note) — OpenCode sessions routed through OpenRouter's `providerID` can double-report the same consumption in both sources, and there's no reliable shared ID to deduplicate them. Don't "fix" this by adding OpenRouter into `combine_projects()`.

## Portability constraints

No file in this repo may contain a path specific to the original author's machine (no `/home/jruedadev`, no `~/DEV/JRDV/...`). `shell/aliases.sh` resolves its own location via `${BASH_SOURCE[0]}`; `install.sh` resolves the repo location via `dirname "$0"`. Keep it that way — this repo is meant to be cloned and used by other people as-is.
