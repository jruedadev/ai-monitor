"""Validación de la configuración del motor (spec §3.5 y §6). Módulo sin
dependencias internas: lo usan store.py, llm.py y server.py."""

BACKENDS = ("hermes", "claude", "none")
DEFAULT_BACKEND = "hermes"
DEFAULT_CHAIN = (
    "nous:stealth/space-bunny-alpha",
    "nous:upstage/solar-pro4:free",
    "nous:inclusionai/ling-3.0-flash-sante:free",
)
_KEYS = {"backend", "llm_chain"}


class EngineSettingsError(ValueError):
    """Payload inválido para /api/engine-settings; server.py lo traduce a HTTP 400."""


def is_free(model):
    return isinstance(model, str) and (model.endswith(":free") or model.startswith("stealth/"))


def parse_entry(entry):
    """'proveedor:modelo' → (proveedor, modelo). El modelo puede contener ':' (p. ej. ':free')."""
    if not isinstance(entry, str) or ":" not in entry:
        raise ValueError(f"Entrada inválida: {entry!r} (se espera proveedor:modelo)")
    provider, model = entry.split(":", 1)
    if not provider.strip() or not model.strip():
        raise ValueError(f"Entrada inválida: {entry!r} (se espera proveedor:modelo)")
    return provider.strip(), model.strip()


def validate_engine_settings(payload):
    if not isinstance(payload, dict) or set(payload) != _KEYS:
        raise EngineSettingsError("El cuerpo debe ser un objeto con backend y llm_chain")
    backend, chain = payload["backend"], payload["llm_chain"]
    if backend not in BACKENDS:
        raise EngineSettingsError(f"Backend desconocido: {backend}")
    if not isinstance(chain, list) or not chain:
        raise EngineSettingsError("llm_chain debe ser una lista no vacía")
    normalized = []
    for entry in chain:
        try:
            provider, model = parse_entry(entry)
        except ValueError as exc:
            raise EngineSettingsError(str(exc)) from None
        if backend == "hermes" and not is_free(model):
            raise EngineSettingsError(f"Con Hermes solo se permiten modelos free: {entry}")
        normalized.append(f"{provider}:{model}")
    return {"backend": backend, "llm_chain": normalized}
