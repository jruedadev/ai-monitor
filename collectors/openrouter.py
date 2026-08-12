"""Collector de uso de OpenRouter vía su API REST (/api/v1/activity).
La key se lee de OPENROUTER_API_KEY; como fallback, del archivo de entorno
generado por install.sh (el mismo que usa la unidad systemd). Nunca de archivos
de configuración de otra herramienta (ver spec: el token de OpenCode no es una
API key válida, y su auth.json puede contener keys revocadas).
"""
import json
import os
import urllib.request
from collections import defaultdict

ACTIVITY_URL = "https://openrouter.ai/api/v1/activity"


def _env_file_key(env_file_path=None):
    path = env_file_path or os.path.expanduser("~/.config/ai-monitor/env")
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("OPENROUTER_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return None


def _http_get_json(url, api_key):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def collect(api_key=None, fetch=None, env_file_path=None):
    if api_key is None:
        api_key = os.environ.get("OPENROUTER_API_KEY") or _env_file_key(env_file_path)
    if not api_key:
        return {"unavailable": True, "reason": "OPENROUTER_API_KEY no está definida"}

    if fetch is None:
        fetch = _http_get_json

    try:
        response = fetch(ACTIVITY_URL, api_key)
        if not isinstance(response, dict):
            raise ValueError(f"respuesta inesperada de OpenRouter: {type(response).__name__}")

        models = defaultdict(lambda: {"tokens": 0, "cost": 0.0, "requests": 0})
        by_day = defaultdict(lambda: {"tokens": 0, "cost": 0.0})

        for row in response.get("data", []):
            model = row.get("model", "unknown")
            date = row.get("date", "unknown")
            cost = row.get("usage", 0.0) or 0.0
            tokens = (row.get("prompt_tokens", 0) or 0) + (row.get("completion_tokens", 0) or 0)

            models[model]["tokens"] += tokens
            models[model]["cost"] += cost
            models[model]["requests"] += 1

            by_day[date]["tokens"] += tokens
            by_day[date]["cost"] += cost
    except Exception as e:
        return {"unavailable": True, "reason": str(e)}

    return {
        "unavailable": False,
        "models": {k: {"tokens": v["tokens"], "cost": round(v["cost"], 4), "requests": v["requests"]}
                   for k, v in models.items()},
        "by_day": {k: {"tokens": v["tokens"], "cost": round(v["cost"], 4)} for k, v in by_day.items()},
    }
