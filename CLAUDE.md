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
