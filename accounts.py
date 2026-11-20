"""Modelo de cuentas por proveedor: validación y nombres de fuente."""
import math
import os
import re

SUPPORTED_PROVIDERS = ("claude_code",)
RESERVED_IDS = ("all", "openrouter")
DEFAULT_PROVIDER = "claude_code"

_ID_RE = re.compile(r"[a-z0-9-]{1,32}")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


class AccountsError(ValueError):
    pass


def _normalize_one(raw):
    if not isinstance(raw, dict):
        raise AccountsError("cada cuenta debe ser un objeto")
    acc_id = raw.get("id")
    if not isinstance(acc_id, str) or not _ID_RE.fullmatch(acc_id):
        raise AccountsError("id inválido: use a-z, 0-9 y guion (máx. 32)")
    if acc_id in RESERVED_IDS:
        raise AccountsError("id reservado: %s" % acc_id)
    provider = raw.get("provider")
    if provider not in SUPPORTED_PROVIDERS:
        raise AccountsError("proveedor no soportado: %s" % (provider,))
    label = raw.get("label")
    if not isinstance(label, str) or not label.strip() or len(label) > 40:
        raise AccountsError("label requerido (máx. 40 caracteres) en %s" % acc_id)
    location = raw.get("location")
    if not isinstance(location, str) or not os.path.isabs(location):
        raise AccountsError("location debe ser una ruta absoluta en %s" % acc_id)
    location = os.path.normpath(location)
    if os.path.basename(location) == "projects":
        raise AccountsError(
            "location apunta a projects en %s: indique la carpeta padre que contiene projects/" % acc_id)
    is_default = raw.get("default")
    if not isinstance(is_default, bool):
        raise AccountsError("default debe ser booleano en %s" % acc_id)
    cost = raw.get("monthly_cost")
    if cost is not None and (isinstance(cost, bool)
                             or not isinstance(cost, (int, float))
                             or not math.isfinite(cost) or cost < 0):
        raise AccountsError("monthly_cost debe ser un número >= 0 en %s" % acc_id)
    start = raw.get("start_date")
    if start is not None and (not isinstance(start, str) or not _DATE_RE.fullmatch(start)):
        raise AccountsError("start_date debe ser AAAA-MM-DD en %s" % acc_id)
    return {
        "id": acc_id, "provider": provider, "label": label, "location": location,
        "default": is_default, "monthly_cost": cost, "start_date": start,
    }


def normalize_accounts(payload):
    if not isinstance(payload, list):
        raise AccountsError("accounts debe ser una lista")
    result = [_normalize_one(raw) for raw in payload]
    ids = [a["id"] for a in result]
    if len(set(ids)) != len(ids):
        raise AccountsError("hay ids de cuenta repetidos")
    locations = [a["location"] for a in result]
    if len(set(locations)) != len(locations):
        raise AccountsError("hay cuentas con la misma ubicación")
    for provider in sorted({a["provider"] for a in result} | {DEFAULT_PROVIDER}):
        defaults = [a for a in result if a["provider"] == provider and a["default"]]
        if len(defaults) != 1:
            raise AccountsError(
                "debe haber exactamente una cuenta por defecto para %s" % provider)
    return result


def legacy_accounts(settings):
    return [{
        "id": "personal",
        "provider": DEFAULT_PROVIDER,
        "label": "Personal",
        "location": os.path.expanduser("~/.claude"),
        "default": True,
        "monthly_cost": settings.get("subscription_cost_claude"),
        "start_date": settings.get("subscription_start_claude"),
    }]


def source_name(account):
    if account["default"]:
        return account["provider"]
    return "%s@%s" % (account["provider"], account["id"])


def claude_projects_dir(account):
    return os.path.join(account["location"], "projects")


def provider_of_source(source):
    return source.split("@", 1)[0]


def is_claude_source(source):
    return provider_of_source(source) == "claude_code"
