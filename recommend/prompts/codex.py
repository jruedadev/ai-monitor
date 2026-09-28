"""Prompts de Codex: ~/.codex/sessions/**/*.jsonl, response_item message role=user."""
import glob
import json
import os

from recommend.prompts import Prompt, clean_text, day_from_iso

_TEXT_BLOCKS = ("input_text", "text")


def read_prompts(since, override=None):
    root = override or os.path.expanduser("~/.codex/sessions")
    if not os.path.isdir(root):
        return []
    out = []
    for path in sorted(glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True)):
        session_id, project, pending = None, None, []
        with open(path, "r", errors="ignore") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(rec, dict) or not isinstance(rec.get("payload"), dict):
                    continue
                kind, payload = rec.get("type"), rec["payload"]
                if kind == "session_meta":
                    session_id = session_id or payload.get("id")
                    project = project or payload.get("cwd")
                elif kind == "turn_context":
                    project = project or payload.get("cwd")
                elif kind == "response_item" and payload.get("type") == "message" and payload.get("role") == "user":
                    day = day_from_iso(rec.get("timestamp"))
                    if day is None or day < since:
                        continue
                    blocks = payload.get("content") if isinstance(payload.get("content"), list) else []
                    texts = [b.get("text") for b in blocks if isinstance(b, dict)
                             and b.get("type") in _TEXT_BLOCKS and isinstance(b.get("text"), str)]
                    text = clean_text("\n".join(texts)) if texts else None
                    if text:
                        pending.append((day, text))
        session_id = str(session_id or os.path.basename(path)[: -len(".jsonl")])
        project = project or "unknown"
        out.extend(Prompt("codex", project, session_id, day, text) for day, text in pending)
    return out
