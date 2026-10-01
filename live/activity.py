"""Snapshot de actividad en vivo: cuerpo de GET /api/activity y del evento SSE `activity`."""
import time

from live import claude_code, hermes, opencode
from live.model import iso_utc, to_agent

LIVE_SOURCES = ("claude_code", "opencode", "hermes")


def _default_readers():
    return {"claude_code": claude_code.read, "opencode": opencode.read, "hermes": hermes.read}


def snapshot(now=None, readers=None):
    now = time.time() if now is None else now
    readers = readers or _default_readers()
    agents, sources = [], {}
    for name in LIVE_SOURCES:
        try:
            facts = readers[name](now)
        except Exception:  # SourceUnavailable u otro fallo: esa fuente cae, las demás siguen
            sources[name] = "unavailable"
            continue
        sources[name] = "ok"
        for item in facts:
            agent = to_agent(item, now)
            if agent is not None:
                agents.append(agent)
    agents.sort(key=lambda a: a["since"], reverse=True)
    return {"generated_at": iso_utc(now), "agents": agents, "sources": sources}
