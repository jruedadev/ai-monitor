"""Lectores de prompts del usuario por fuente (spec §3.1). Solo leen, nunca
escriben. Cada lector sigue la convención de los collectors: parámetro de
override para tests y [] cuando la fuente no existe."""
import os
from collections import namedtuple
from datetime import datetime, timezone

Prompt = namedtuple("Prompt", "source project session_id day_utc text")

MIN_CHARS = 20
MAX_CHARS = 4000
WINDOW_DAYS = 30
ENGINE_DIR = os.path.expanduser("~/.local/share/ai-monitor/motor-recomendaciones")


def clean_text(text):
    """Texto útil del usuario o None: descarta lo corto y el contexto inyectado
    por la herramienta (etiquetas tipo <command-name>, <environment_context>)."""
    if not isinstance(text, str):
        return None
    text = text.strip()
    if len(text) < MIN_CHARS or text.startswith("<"):
        return None
    return text[:MAX_CHARS]


def day_from_iso(ts):
    if not isinstance(ts, str):
        return None
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d")


def day_from_epoch(seconds):
    try:
        return datetime.fromtimestamp(float(seconds), tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def is_engine_project(project, engine_dir=ENGINE_DIR):
    if not project:
        return False
    norm = os.path.normpath(project)
    base = os.path.normpath(engine_dir)
    return norm == base or norm.startswith(base + os.sep)


def read_all(since, overrides=None, engine_dir=ENGINE_DIR):
    """(prompts, errores). Una fuente que falla no tumba a las demás: su error
    queda anotado para la corrida."""
    from recommend.prompts import claude_code, codex, hermes, opencode

    readers = (("claude_code", claude_code.read_prompts), ("codex", codex.read_prompts),
               ("opencode", opencode.read_prompts), ("hermes", hermes.read_prompts))
    overrides = overrides or {}
    found, errors = [], []
    for source, reader in readers:
        try:
            items = reader(since, overrides.get(source))
        except Exception as exc:  # noqa: BLE001 — cualquier falla de una fuente se anota y se sigue
            errors.append(f"{source}: {exc}")
            continue
        found.extend(p for p in items if not is_engine_project(p.project, engine_dir))
    return found, errors
