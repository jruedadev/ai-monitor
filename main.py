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
import history


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


def collect_all(db_path=None):
    sources = {
        "claude_code": claude_code.collect(),
        "codex": codex.collect(),
        "opencode": opencode.collect(),
        "openrouter": openrouter.collect(),
    }
    history.record_snapshot(sources, db_path=db_path)
    return sources


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
