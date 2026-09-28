"""Prompts de Claude Code: ~/.claude/projects/*/*.jsonl, registros type=user."""
import glob
import json
import os

from recommend.prompts import Prompt, clean_text, day_from_iso


def _user_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = [b.get("text") for b in content
                 if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str)]
        return "\n".join(texts) if texts else None
    return None


def read_prompts(since, override=None):
    root = override or os.path.expanduser("~/.claude/projects")
    if not os.path.isdir(root):
        return []
    out = []
    for path in sorted(glob.glob(os.path.join(root, "*", "*.jsonl"))):
        session_id = os.path.basename(path)[: -len(".jsonl")]
        project, pending = None, []
        with open(path, "r", errors="ignore") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(rec, dict):
                    continue
                if project is None and isinstance(rec.get("cwd"), str) and rec["cwd"]:
                    project = rec["cwd"]
                if rec.get("type") != "user" or rec.get("isMeta") or rec.get("isCompactSummary"):
                    continue
                day = day_from_iso(rec.get("timestamp"))
                if day is None or day < since:
                    continue
                message = rec.get("message")
                text = clean_text(_user_text(message.get("content") if isinstance(message, dict) else None))
                if text:
                    pending.append((day, text))
        project = project or os.path.basename(os.path.dirname(path))
        out.extend(Prompt("claude_code", project, session_id, day, text) for day, text in pending)
    return out
