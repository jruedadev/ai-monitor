"""Modelo puro de la actividad en vivo: hechos por sesión -> estado de agente.
Los lectores producen SessionFacts; solo este módulo decide estados."""
from dataclasses import dataclass
from datetime import datetime, timezone

WAITING_AFTER_S = 8
THINKING_WINDOW_S = 60
OFFICE_WINDOW_S = 1800
CLOCK_SKEW_S = 60

_EDIT = frozenset({"edit", "write", "multiedit", "notebookedit", "patch", "apply_patch",
                   "str_replace_editor", "todowrite"})
_READ = frozenset({"read", "grep", "glob", "ls", "list", "webfetch", "websearch", "search", "codesearch"})
_RUN = frozenset({"bash", "shell", "terminal", "exec", "execute_code", "task", "agent"})


class SourceUnavailable(Exception):
    """La fuente no se pudo leer en absoluto (ausente, corrupta, sin tabla)."""


@dataclass(frozen=True)
class SessionFacts:
    source: str
    session_id: str
    project: str
    last_event: float | None
    pending_tool: str | None
    pending_since: float | None
    ended: bool = False


def classify_tool(name):
    if not name:
        return "other"
    key = name.lower()
    if key in _EDIT:
        return "edit"
    if key in _READ:
        return "read"
    if key in _RUN:
        return "run"
    return "other"


def iso_utc(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def derive_state(facts, now):
    """(estado, since) según la tabla de §2.1 del spec, o None si la sesión se omite."""
    if facts.ended or facts.last_event is None:
        return None
    if facts.last_event - now > CLOCK_SKEW_S:
        return None
    last = min(facts.last_event, now)
    if now - last > OFFICE_WINDOW_S:
        return None
    if facts.pending_tool is not None and facts.pending_since is not None:
        since = min(facts.pending_since, now)
        return ("waiting" if now - since >= WAITING_AFTER_S else "tool"), since
    return ("thinking" if now - last < THINKING_WINDOW_S else "idle"), last


def to_agent(facts, now):
    derived = derive_state(facts, now)
    if derived is None:
        return None
    state, since = derived
    on_tool = state in ("tool", "waiting")
    return {
        "key": f"{facts.source}:{facts.session_id}",
        "source": facts.source,
        "project": facts.project or "unknown",
        "state": state,
        "tool": facts.pending_tool if on_tool else None,
        "tool_kind": classify_tool(facts.pending_tool) if on_tool else None,
        "since": iso_utc(since),
    }
