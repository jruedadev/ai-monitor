# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-file Python script (`claude_usage.py`) that parses local Claude Code session transcripts (`~/.claude/projects/*/*.jsonl`) to report token usage, estimated cost, and the heaviest sessions/tasks per project. No external dependencies — standard library only.

## Commands

```bash
# Terminal table summary
python3 claude_usage.py

# Full aggregated data as JSON
python3 claude_usage.py --json

# Self-contained HTML dashboard
python3 claude_usage.py --html dashboard.html
```

There is no build step, test suite, or linter configured in this repo.

## Architecture

The script has three stages, all in `claude_usage.py`:

1. **`collect()`** — walks every `~/.claude/projects/<encoded-dir>/*.jsonl` file. For each session file it does a pre-pass to resolve the *real* project path from the `cwd` field on any record (this is preferred over the directory name, since Claude Code encodes `/` as `-` in an irreversible way when a path itself contains dashes) and to grab the session's `ai-title` if present. It then does a second pass collecting only `type: "assistant"` records that carry a `usage` block, accumulating input/output/cache tokens, per-day totals, and per-session totals into a `defaultdict`-based structure keyed by the resolved project path.
2. **`cost_of()` / `price_for()` / `PRICING`** — a hardcoded per-model price table (USD per million tokens) used to estimate cost from token counts. This is a list-price estimate, not a real bill — it does not account for subscription plans (Pro/Max). When Anthropic changes pricing or ships new model names, update `PRICING`.
3. **Output**: `print_table()` (terminal), `--json` (raw `collect()` output), or `generate_html()` which injects the JSON payload into `HTML_TEMPLATE` — a single self-contained HTML string with inline CSS/JS (no CDN, no network calls), auto light/dark via `prefers-color-scheme`.

Key design point: aggregation keys are **resolved `cwd` paths**, not the encoded directory names Claude Code uses on disk — keep this resolution logic in mind if extending grouping/filtering, since encoded directory names are ambiguous for paths containing dashes.

## Suggested shell aliases (documented in README, not enforced by code)

```bash
claude-usage() {
    python3 ~/DEV/JRDV/ai-monitor/claude_usage.py --html ~/claude-usage.html && xdg-open ~/claude-usage.html >/dev/null 2>&1 &
}
alias claude-usage-table='python3 ~/DEV/JRDV/ai-monitor/claude_usage.py'
```
