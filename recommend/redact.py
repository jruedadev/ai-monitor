"""Redacción de datos sensibles antes de clusterizar o de enviar algo al LLM
(spec §3.2). Se aplica al texto de los prompts y otra vez al draft del LLM.
El orden importa: primero lo más específico (JWT, claves), al final la
heurística de entropía."""
import math
import re
from collections import Counter

SECRET = "<secreto>"
EMAIL = "<correo>"
IP = "<ip>"

_JWT = re.compile(r"\beyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}")
_KEYS = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b")
_KEY_VALUE = re.compile(
    r"(?i)\b(password|passwd|token|api[_-]?key|secret)(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;&]+)")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_URL = re.compile(r"\b(https?://[^\s?#\"'<>]+)[?#][^\s\"'<>]*")
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
# ≥3 grupos "xxxx:" para no confundir horas (10:30:45) con IPv6.
_IPV6 = re.compile(r"\b(?:[0-9A-Fa-f]{0,4}:){3,7}[0-9A-Fa-f]{1,4}\b")
# Ruta absoluta con al menos un directorio; no toca URLs (el "/" va tras ":" o letra)
# ni lo ya redactado ("<ruta>/x").
_PATH = re.compile(r"(?<![\w.<>/:~])(?:~/|/)(?:[\w.@-]+/)+([\w.@-]+)")
_LONG = re.compile(r"[A-Za-z0-9+_=-]{32,}")
_MIN_ENTROPY = 3.5


def _entropy(text):
    counts = Counter(text)
    n = len(text)
    return -sum(c / n * math.log2(c / n) for c in counts.values())


def _long_secret(match):
    token = match.group(0)
    if any(ch.isdigit() for ch in token) and any(ch.isalpha() for ch in token) \
            and _entropy(token) >= _MIN_ENTROPY:
        return SECRET
    return token


def redact(text):
    if not text:
        return ""
    text = _JWT.sub(SECRET, text)
    text = _KEYS.sub(SECRET, text)
    text = _URL.sub(r"\1", text)
    text = _KEY_VALUE.sub(lambda m: f"{m.group(1)}{m.group(2)}{SECRET}", text)
    text = _EMAIL.sub(EMAIL, text)
    text = _IPV6.sub(IP, text)
    text = _IPV4.sub(IP, text)
    text = _PATH.sub(r"<ruta>/\1", text)
    text = _LONG.sub(_long_secret, text)
    return text
