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
        "cost": 0.0, "cost_incomplete": False, "messages": 0, "sessions": set(),
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
                raw_cost = cost_of(inp, out, cr, cw, model)
                c = raw_cost or 0.0

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
            "cost_incomplete": p["cost_incomplete"],
            "messages": p["messages"],
            "session_count": len(p["sessions"]),
            "sessions_detail": [
                {"session_id": sid, "tokens": v["tokens"], "cost": round(v["cost"], 4),
                 "title": v["title"], "last_ts": v["last_ts"], "cwd": v["cwd"]}
                for sid, v in p["sessions_detail"].items()
            ],
        }
    return out
