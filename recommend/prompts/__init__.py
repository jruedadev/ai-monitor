"""Lectores de prompts del usuario por fuente (spec §3.1). Solo leen, nunca
escriben. Cada lector sigue la convención de los collectors: parámetro de
override para tests y [] cuando la fuente no existe."""
import os
import re
from collections import namedtuple
from datetime import datetime, timezone

Prompt = namedtuple("Prompt", "source project session_id day_utc text")

MIN_CHARS = 20
MAX_CHARS = 4000
WINDOW_DAYS = 30
ENGINE_DIR = os.path.expanduser("~/.local/share/ai-monitor/motor-recomendaciones")
# Mensajes que escribe el arnés o la herramienta y que llegan con rol de usuario:
# marcadores entre corchetes ("[Request interrupted by user]", "[IMPORTANT: …]"),
# etiquetas XML ("<command-name>") y órdenes automáticas de condensado. Ninguno
# es una intención del usuario, así que no entran al clustering.
HARNESS_PREFIXES = ("[", "<", "Condense the tool payload")
# Un prompt sin intención es una URL pegada, un secreto o un placeholder de redacción
# ("Bearer <secreto>"): no describe una tarea repetible, así que no entra al clustering.
MIN_INTENT_WORDS = 3
_URL = re.compile(r"https?://\S+")
_PLACEHOLDER = re.compile(r"<[^<>\s]+>")
_WORD = re.compile(r"[^\W\d_]{2,}")


def has_intent(text):
    """True si el texto (ya redactado) tiene al menos MIN_INTENT_WORDS palabras fuera
    de URLs y placeholders."""
    rest = _PLACEHOLDER.sub(" ", _URL.sub(" ", text or ""))
    return len(_WORD.findall(rest)) >= MIN_INTENT_WORDS


def clean_text(text):
    """Texto útil del usuario o None: descarta lo corto y el contexto inyectado
    por la herramienta o el arnés (ver HARNESS_PREFIXES)."""
    if not isinstance(text, str):
        return None
    text = text.strip()
    if len(text) < MIN_CHARS or text.startswith(HARNESS_PREFIXES):
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
