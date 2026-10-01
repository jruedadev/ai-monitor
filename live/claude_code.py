"""Lector en vivo de Claude Code: cola de ~/.claude/projects/*/*.jsonl.
Solo lee tipos, ids, nombres de herramienta, cwd y timestamps; nunca `input` ni `content`."""
import glob
import json
import os
from datetime import datetime

from live.model import OFFICE_WINDOW_S, SessionFacts, SourceUnavailable

TAIL_BYTES = 65536


def _epoch(ts):
    if not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _tail_lines(path):
    with open(path, "rb") as f:
        size = os.fstat(f.fileno()).st_size
        start = max(0, size - TAIL_BYTES)
        f.seek(start)
        lines = f.read().split(b"\n")
    return lines[1:] if start > 0 else lines


def _parse(path, session_id):
    cwd = None
    last_event = None
    pending = {}  # tool_use id -> (name, timestamp)
    for raw in _tail_lines(path):
        try:
            rec = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(rec, dict):
            continue
        if isinstance(rec.get("cwd"), str) and rec["cwd"]:
            cwd = rec["cwd"]
        kind = rec.get("type")
        ts = _epoch(rec.get("timestamp"))
        if kind in ("user", "assistant") and ts is not None:
            last_event = ts if last_event is None else max(last_event, ts)
        message = rec.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "tool_use" and kind == "assistant" and ts is not None:
                pending[block.get("id")] = (block.get("name"), ts)
            elif btype == "tool_result":
                pending.pop(block.get("tool_use_id"), None)
    tool, since = (None, None)
    for name, ts in pending.values():
        if isinstance(name, str) and (since is None or ts >= since):
            tool, since = name, ts
    return SessionFacts("claude_code", session_id, cwd or "unknown", last_event, tool, since)


def read(now, projects_dir=None):
    root = projects_dir or os.path.expanduser("~/.claude/projects")
    if not os.path.isdir(root):
        raise SourceUnavailable(root)
    facts = []
    try:
        for path in glob.glob(os.path.join(root, "*", "*.jsonl")):
            try:
                if now - os.stat(path).st_mtime > OFFICE_WINDOW_S:
                    continue
                session_id = os.path.basename(path)[: -len(".jsonl")]
                facts.append(_parse(path, session_id))
            except OSError:
                continue  # un archivo que desaparece entre el glob y la lectura no invalida la fuente
    except OSError as exc:
        raise SourceUnavailable(str(exc)) from exc
    return facts
