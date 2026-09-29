"""Agrupación de proyectos por cliente según raíces configurables (spec 2026-09-29 §2).
Módulo puro: lo usan briefing.py e history.py. frontend/src/lib/clients.ts es su port
y tests/fixtures/client_of_cases.json el contrato compartido entre ambos."""
import json

OTHER = "Otros"
MODES = ("cliente", "plano")
MAX_ROOTS = 20
MAX_ROOT_CHARS = 200
_DEFAULT = ({"root": "DEV", "mode": "cliente"},)


class ClientRootsError(ValueError):
    """Lista de raíces inválida; history/server lo traducen a HTTP 400."""


def default_roots():
    return [dict(r) for r in _DEFAULT]


def _next_index(segments, root):
    """Índice del segmento que sigue a la raíz, o None si la raíz no coincide.
    Nombre: primera aparición, sin distinguir mayúsculas. Ruta absoluta: prefijo
    por segmentos completos (así /srv/trabajo2 no coincide con /srv/trabajo)."""
    if root.startswith("/"):
        prefix = root.rstrip("/").split("/")
        return len(prefix) if segments[:len(prefix)] == prefix else None
    target = root.upper()
    for idx, segment in enumerate(segments):
        if segment.upper() == target:
            return idx + 1
    return None


def client_of(path, roots):
    segments = path.split("/")
    for entry in roots:
        nxt = _next_index(segments, entry["root"])
        if nxt is None:
            continue
        if entry["mode"] == "plano":
            return entry["root"].rstrip("/").split("/")[-1]
        return segments[nxt] if nxt < len(segments) and segments[nxt] else OTHER
    return OTHER


def normalize_roots(value):
    if not isinstance(value, list):
        raise ClientRootsError("client_roots debe ser una lista")
    if not 1 <= len(value) <= MAX_ROOTS:
        raise ClientRootsError(f"client_roots debe tener entre 1 y {MAX_ROOTS} raíces")
    out, seen = [], set()
    for i, item in enumerate(value, start=1):
        if not isinstance(item, dict) or set(item) != {"root", "mode"}:
            raise ClientRootsError(f"Raíz {i}: debe tener exactamente root y mode")
        root, mode = item["root"], item["mode"]
        if not isinstance(root, str):
            raise ClientRootsError(f"Raíz {i}: root debe ser texto")
        root = root.strip()
        absolute = root.startswith("/")
        if absolute:
            root = root.rstrip("/")
            if not root:
                raise ClientRootsError(f"Raíz {i}: una ruta absoluta necesita al menos una carpeta")
        elif "/" in root:
            raise ClientRootsError(f"Raíz {i}: un nombre de carpeta no puede contener /; usa una ruta absoluta")
        if not root:
            raise ClientRootsError(f"Raíz {i}: root no puede estar vacío")
        if len(root) > MAX_ROOT_CHARS:
            raise ClientRootsError(f"Raíz {i}: root admite como máximo {MAX_ROOT_CHARS} caracteres")
        if mode not in MODES:
            raise ClientRootsError(f"Raíz {i}: mode debe ser cliente o plano")
        key = root if absolute else root.upper()
        if key in seen:
            raise ClientRootsError(f"Raíz {i}: {root} está repetida")
        seen.add(key)
        out.append({"root": root, "mode": mode})
    return out


def parse_stored_roots(raw):
    if raw is None:
        return default_roots()
    try:
        return normalize_roots(json.loads(raw))
    except (ValueError, TypeError):
        return default_roots()
