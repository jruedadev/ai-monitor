# Motor de recomendaciones v1 — Plan de implementación

> **Para agentes:** SUB-SKILL OBLIGATORIA: usa superpowers:subagent-driven-development (recomendada) o superpowers:executing-plans para implementar este plan tarea por tarea. Los pasos usan casillas (`- [ ]`) para el seguimiento.

**Objetivo:** detectar patrones repetidos en los prompts locales y señales de costo, y convertirlos en recomendaciones persistidas en `history.db` (skill, plugin, prompt o costo) con evidencia, borrador copiable y estados aplicar/saltar, visibles en una vista nueva del dashboard.

**Arquitectura:** paquete stdlib `recommend/` con piezas puras y aisladas (lectores de prompts → redacción → clustering léxico → LLM opcional vía Hermes/`claude -p` con runner inyectable → heurística local → persistencia con firma y ciclo de vida). `engine.py` orquesta una corrida con lock; la dispara el timer diario (`python3 -m recommend run`) o `POST /api/recommendations/run` en `server.py`. El frontend lee todo por la API y se entera de corridas nuevas por el evento SSE `recommendations`.

**Stack:** Python 3 stdlib (`sqlite3`, `json`, `re`, `subprocess`, `unittest`); React 19 + TypeScript + Tailwind v4 + shadcn/base-ui + react-router 7; vitest; Playwright por CLI para el E2E.

**Spec:** `docs/superpowers/specs/2026-09-27-motor-recomendaciones-design.md`

## Restricciones globales

- Backend **solo stdlib** (`recommend/`, `server.py`, `history.py`, `briefing.py`). Nada de `pip install`.
- Ningún archivo del repo puede contener rutas del autor (su `$HOME` ni el directorio padre del repo). En tests usa rutas sintéticas como `/home/u/DEV/ACME/app`.
- `history.db` **nunca se poda**: ninguna tabla nueva ni vieja recibe `DELETE`. Las recomendaciones solo cambian de estado.
- OpenRouter nunca entra en la vista "Todo" ni en el motor (no tiene prompts locales).
- El texto completo de los prompts **nunca** se guarda en `history.db`: solo fragmentos redactados de ≤200 caracteres (máximo 3 por recomendación).
- Al LLM solo le llega el resumen por candidato: patrón, sesiones, días, tokens, features y ≤3 fragmentos redactados.
- Backend `hermes`: solo modelos free (terminan en `:free` o empiezan por `stealth/`); si el `usage-file` reporta `estimated_cost_usd > 0`, el intento falla.
- Cadena por defecto: `nous:stealth/space-bunny-alpha`, `nous:upstage/solar-pro4:free`, `nous:inclusionai/ling-3.0-flash-sante:free`.
- Timeout por intento LLM: 120 s. Recortes: `pattern` ≤120, `description` ≤400, `draft` ≤8000 caracteres.
- Umbrales: candidatos Jaccard ≥0,3, ≥2 sesiones, top 40 por tokens; modo léxico Jaccard ≥0,5; umbral final ≥3 sesiones y ≥2 días, top 10 por `sesiones × tokens`; misma recomendación entre corridas si Jaccard de firmas ≥0,5; impacto alto ≥10 %, medio ≥3 %, bajo el resto.
- Directorio de trabajo del motor: `~/.local/share/ai-monitor/motor-recomendaciones/`. Lock: `~/.local/share/ai-monitor/recommend.lock`.
- Nunca un 500 por datos: `sqlite3.Error` en la API → respuesta vacía con `degraded: true`.
- Todo el texto de la UI y de los mensajes al usuario va en español. Nada del LLM se interpreta como HTML.
- Commits sin líneas `Co-Authored-By` ni `Claude-Session`.
- No reiniciar servicios systemd del usuario durante la implementación.
- Comandos: backend `python3 -m unittest discover -s tests -v`; frontend `cd frontend && npx vitest run && npx oxlint && npm run build` (`npm install --legacy-peer-deps` si hace falta).

## Foco de revisión

Estas cinco condiciones no las cubre explícitamente el spec y son las que más probablemente romperían el uso real. Cada una tiene su test en la tarea dueña.

1. **Mensajes sin texto útil** (solo contexto inyectado que empieza por `<`, solo `tool_result`, `content` nulo o de tipo raro) → se omiten sin excepción. Test en la Tarea 2 (`test_skips_injected_tool_result_and_odd_content`).
2. **El LLM envuelve el JSON en prosa o en cercas ```` ```json ````** → se extrae igual desde el primer `{` hasta el último `}`. Test en la Tarea 7 (`test_extract_json_tolerates_fences_and_prose`).
3. **"Analizar ahora" con otra corrida activa** → la API responde `409` y la UI muestra "Ya hay una corrida en curso" sin romper la vista. Tests en la Tarea 9 (`test_run_conflict_returns_409`) y en la Tarea 11 (`runErrorMessage`).
4. **`history.db` antiguo sin las tablas nuevas** → `GET /api/recommendations` y `GET /api/engine-settings` responden 200 con valores vacíos o por defecto. Test en la Tarea 9 (`test_old_history_db_without_new_tables`).
5. **Hermes sale con código 0 pero sin `usage-file` o con `failed: true`** → el intento cuenta como fallido y se pasa al siguiente modelo. Test en la Tarea 7 (`test_hermes_missing_usage_or_failed_is_attempt_failure`).

---

## Estructura de archivos

```
recommend/
  __init__.py            # vacío
  __main__.py            # CLI: python3 -m recommend run --trigger diario|manual   (Tarea 8)
  redact.py              # redact(text) -> str                                      (Tarea 1)
  prompts/
    __init__.py          # Prompt, clean_text, read_all                             (Tarea 2)
    claude_code.py       # read_prompts(since, override=None)                       (Tarea 2)
    codex.py                                                                        (Tarea 2)
    opencode.py                                                                     (Tarea 2)
    hermes.py                                                                       (Tarea 2)
  cluster.py             # normalize, trigrams, jaccard, Cluster, candidates, lexical_clusters, merge (Tarea 3)
  settings.py            # BACKENDS, DEFAULT_CHAIN, is_free, parse_entry, validate_engine_settings (Tarea 4)
  store.py               # esquema, settings, corridas, recomendaciones, apply_run  (Tarea 4)
  cost.py                # cost_recommendations(...) desde briefing.RULES           (Tarea 5)
  heuristics.py          # classify, recommend(cluster)                             (Tarea 6)
  llm.py                 # build_prompt, extract_json, validate_*, run_llm          (Tarea 7)
  engine.py              # lock, start, execute, run                                (Tarea 8)
briefing.py              # + build_context(...) extraído de build_briefing          (Tarea 5)
server.py                # + endpoints /api/recommendations*, /api/engine-settings  (Tarea 9)
systemd/ai-monitor-recommend.service.template, systemd/ai-monitor-recommend.timer  (Tarea 10)
install.sh, README.md, CLAUDE.md                                                    (Tarea 10)
tests/test_recommend_*.py, tests/test_systemd_units.py
frontend/src/lib/api.ts, lib/recommendations.ts (+ .test.ts)                        (Tarea 11)
frontend/src/hooks/useUsageStream.ts, hooks/useRecommendations.ts                   (Tarea 11)
frontend/src/lib/routes.ts, lib/commands.ts, components/Sidebar.tsx, App.tsx        (Tarea 12)
frontend/src/views/RecommendationsView.tsx, components/recommendations/RecommendationCard.tsx (Tarea 12)
frontend/src/components/EngineSettingsForm.tsx, views/SettingsView.tsx,
frontend/src/components/home/HomeView.tsx, components/home/AttentionList.tsx        (Tarea 13)
```

Forma común de una **recomendación de entrada** a `store.apply_run` (la producen `engine.py` y `cost.py`):

```python
{
    "tool": "claude_code",          # claude_code|codex|opencode|hermes|varias
    "tokens": 123456,               # int
    "pattern": "…",                 # ≤120
    "kind": "skill",                # skill|plugin|prompt|costo
    "description": "…",             # ≤400
    "impact": "alto",               # alto|medio|bajo
    "evidence": {...},              # dict serializable a JSON (ver Tareas 3 y 5)
    "draft": "…",                   # ≤8000, ya redactado
    "signature": [...] | {...},     # lista ordenada de trigramas, o {"rule","source","project"} para costo
    "generator": "reglas",          # "reglas" | "costo" | etiqueta del modelo ("nous:…" o "claude")
}
```

---

### Tarea 1: Redacción (`recommend/redact.py`)

**Archivos:**
- Crear: `recommend/__init__.py` (vacío), `recommend/redact.py`
- Test: `tests/test_recommend_redact.py`

**Interfaces:**
- Consume: nada.
- Produce: `redact.redact(text: str | None) -> str` (idempotente); constantes `SECRET = "<secreto>"`, `EMAIL = "<correo>"`, `IP = "<ip>"`.

- [ ] **Paso 1: escribir el test que falla**

```python
# tests/test_recommend_redact.py
import unittest

from recommend.redact import redact

CASES = [
    ("usa sk-abcdefghijklmnopqrstuvwx para", "usa <secreto> para"),
    ("clave ghp_" + "a1" * 18 + " fin", "clave <secreto> fin"),
    ("aws AKIAABCDEFGHIJKLMNOP ok", "aws <secreto> ok"),
    ("jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.abcdefghijk", "jwt <secreto>"),
    ("password=hunter2 y token: abc", "password=<secreto> y token: <secreto>"),
    ('API_KEY="x y z" listo', "API_KEY=<secreto> listo"),
    ("escribe a ana.perez@acme.co hoy", "escribe a <correo> hoy"),
    ("abre /home/ana/DEV/ACME/app/main.py ya", "abre <ruta>/main.py ya"),
    ("mira ~/proyectos/x/notas.md", "mira <ruta>/notas.md"),
    ("ve https://api.acme.co/v1/items?token=x&page=2 ya", "ve https://api.acme.co/v1/items ya"),
    ("host 192.168.1.20 y fe80:0:0:0:200:f8ff:fe21:67cf", "host <ip> y <ip>"),
    ("hash 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08", "hash <secreto>"),
]

UNCHANGED = [
    "a las 10:30:45 en punto",
    "nombre_de_funcion_muy_largo_sin_digitos_para_nada",
    "la fracción 1/2 y el comando /help",
    "https://github.com/acme/app/pull/12",
]


class TestRedact(unittest.TestCase):
    def test_cases(self):
        for text, expected in CASES:
            with self.subTest(text=text):
                self.assertEqual(redact(text), expected)

    def test_unchanged(self):
        for text in UNCHANGED:
            with self.subTest(text=text):
                self.assertEqual(redact(text), text)

    def test_idempotent(self):
        for text, _ in CASES:
            once = redact(text)
            self.assertEqual(redact(once), once)

    def test_none_and_empty(self):
        self.assertEqual(redact(None), "")
        self.assertEqual(redact(""), "")
```

- [ ] **Paso 2: correr el test y verificar que falla**

Run: `python3 -m unittest tests.test_recommend_redact -v`
Esperado: FAIL con `ModuleNotFoundError: No module named 'recommend'`.

- [ ] **Paso 3: implementar**

```python
# recommend/__init__.py
```

```python
# recommend/redact.py
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
    text = _KEY_VALUE.sub(lambda m: f"{m.group(1)}{m.group(2)}{SECRET}", text)
    text = _EMAIL.sub(EMAIL, text)
    text = _URL.sub(r"\1", text)
    text = _IPV6.sub(IP, text)
    text = _IPV4.sub(IP, text)
    text = _PATH.sub(r"<ruta>/\1", text)
    text = _LONG.sub(_long_secret, text)
    return text
```

- [ ] **Paso 4: correr el test y verificar que pasa**

Run: `python3 -m unittest tests.test_recommend_redact -v`
Esperado: PASS (4 tests). Si algún caso de `UNCHANGED` falla, ajusta el regex correspondiente; no borres el caso.

- [ ] **Paso 5: commit**

```bash
git add recommend/__init__.py recommend/redact.py tests/test_recommend_redact.py
git commit -m "feat(recommend): redacción de secretos, correos, rutas, URLs e IPs"
```

---

### Tarea 2: Lectores de prompts (`recommend/prompts/`)

**Archivos:**
- Crear: `recommend/prompts/__init__.py`, `recommend/prompts/claude_code.py`, `recommend/prompts/codex.py`, `recommend/prompts/opencode.py`, `recommend/prompts/hermes.py`
- Test: `tests/test_recommend_prompts.py`

**Interfaces:**
- Consume: `collectors.hermes._project_for(cwd, source, chat_type)` (misma resolución de proyecto que el collector).
- Produce:
  - `Prompt = namedtuple("Prompt", "source project session_id day_utc text")`; `day_utc` es `"YYYY-MM-DD"`, `session_id` siempre `str`.
  - `clean_text(text) -> str | None`: `None` si no es `str`, si tras `strip()` tiene <20 caracteres o si empieza por `<`; si no, el texto truncado a 4000.
  - `day_from_iso(ts) -> str | None`, `day_from_epoch(seconds) -> str | None`.
  - `ENGINE_DIR` (ruta expandida de `~/.local/share/ai-monitor/motor-recomendaciones`), `WINDOW_DAYS = 30`.
  - `is_engine_project(project, engine_dir=ENGINE_DIR) -> bool`.
  - `read_all(since: str, overrides: dict | None = None, engine_dir=ENGINE_DIR) -> (list[Prompt], list[str])`: `overrides` mapea `"claude_code"|"codex"|"opencode"|"hermes"` → ruta; la lista de errores tiene la forma `"<fuente>: <mensaje>"`.
  - Cada lector: `read_prompts(since: str, override: str | None = None) -> list[Prompt]`. Devuelve `[]` si falta el archivo, el directorio o la tabla; **lanza** `sqlite3.Error` si la base está corrupta (lo anota `read_all`); salta las líneas JSON corruptas; conserva solo prompts con `day_utc >= since`.

- [ ] **Paso 1: escribir el test que falla**

```python
# tests/test_recommend_prompts.py
import json
import os
import sqlite3
import tempfile
import unittest

from recommend import prompts
from recommend.prompts import claude_code, codex, hermes, opencode

APP = "/home/u/DEV/ACME/app"
LONG = "revisa el endpoint de facturas y corrige la validación"  # >20 caracteres


def write_jsonl(path, records):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        for rec in records:
            fh.write((rec if isinstance(rec, str) else json.dumps(rec)) + "\n")


def cc_user(content, ts="2026-09-20T10:00:00Z", cwd=APP, **extra):
    return {"type": "user", "timestamp": ts, "cwd": cwd, "sessionId": "x",
            "message": {"role": "user", "content": content}, **extra}


class TestHelpers(unittest.TestCase):
    def test_clean_text(self):
        self.assertIsNone(prompts.clean_text("corto"))
        self.assertIsNone(prompts.clean_text("<command-name>/clear</command-name> y algo más largo"))
        self.assertIsNone(prompts.clean_text(None))
        self.assertIsNone(prompts.clean_text(["no", "es", "texto"]))
        self.assertEqual(prompts.clean_text("  " + LONG + "  "), LONG)
        self.assertEqual(len(prompts.clean_text("x" * 5000)), 4000)

    def test_days(self):
        self.assertEqual(prompts.day_from_iso("2026-09-20T23:30:00-05:00"), "2026-09-21")
        self.assertEqual(prompts.day_from_iso("2026-09-20T10:00:00Z"), "2026-09-20")
        self.assertIsNone(prompts.day_from_iso("no-fecha"))
        self.assertIsNone(prompts.day_from_iso(None))
        self.assertEqual(prompts.day_from_epoch(1790000000), "2026-09-21")
        self.assertIsNone(prompts.day_from_epoch("x"))

    def test_is_engine_project(self):
        self.assertTrue(prompts.is_engine_project("/e/motor", engine_dir="/e/motor"))
        self.assertTrue(prompts.is_engine_project("/e/motor/sub", engine_dir="/e/motor"))
        self.assertFalse(prompts.is_engine_project("/e/motor-otro", engine_dir="/e/motor"))
        self.assertFalse(prompts.is_engine_project(None, engine_dir="/e/motor"))


class TestClaudeCode(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def test_reads_str_and_text_blocks(self):
        write_jsonl(os.path.join(self.root, "-enc", "s1.jsonl"), [
            {"type": "summary"},
            cc_user(LONG),
            cc_user([{"type": "text", "text": LONG + " parte uno"}, {"type": "text", "text": "parte dos"}]),
            "{corrupto",
        ])
        found = claude_code.read_prompts("2026-09-01", self.root)
        self.assertEqual([p.text for p in found], [LONG, LONG + " parte uno\nparte dos"])
        self.assertEqual({(p.source, p.project, p.session_id, p.day_utc) for p in found},
                         {("claude_code", APP, "s1", "2026-09-20")})

    def test_skips_injected_tool_result_and_odd_content(self):
        write_jsonl(os.path.join(self.root, "-enc", "s1.jsonl"), [
            cc_user([{"type": "tool_result", "content": LONG}]),
            cc_user("<local-command-stdout>" + LONG + "</local-command-stdout>"),
            cc_user(LONG, isMeta=True),
            cc_user(LONG, isCompactSummary=True),
            cc_user(None),
            cc_user(42),
            cc_user([None, "texto suelto", {"type": "text"}]),
            {"type": "user", "timestamp": "2026-09-20T10:00:00Z", "message": "no-dict"},
            ["no", "es", "un", "objeto"],
        ])
        self.assertEqual(claude_code.read_prompts("2026-09-01", self.root), [])

    def test_window_and_missing_dir(self):
        write_jsonl(os.path.join(self.root, "-enc", "s1.jsonl"), [
            cc_user(LONG, ts="2026-08-01T10:00:00Z"), cc_user(LONG, ts="sin-fecha")])
        self.assertEqual(claude_code.read_prompts("2026-09-01", self.root), [])
        self.assertEqual(claude_code.read_prompts("2026-09-01", os.path.join(self.root, "no")), [])


class TestCodex(unittest.TestCase):
    def test_reads_user_messages_recursively(self):
        root = tempfile.mkdtemp()
        write_jsonl(os.path.join(root, "2026", "09", "20", "rollout-a.jsonl"), [
            {"type": "session_meta", "timestamp": "2026-09-20T10:00:00Z", "payload": {"id": "th-1", "cwd": APP}},
            {"type": "response_item", "timestamp": "2026-09-20T10:00:01Z",
             "payload": {"type": "message", "role": "user",
                         "content": [{"type": "input_text", "text": "<environment_context>x</environment_context>"}]}},
            {"type": "response_item", "timestamp": "2026-09-20T10:00:02Z",
             "payload": {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": LONG}]}},
            {"type": "response_item", "timestamp": "2026-09-20T10:00:03Z",
             "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": LONG}]}},
        ])
        write_jsonl(os.path.join(root, "2026", "09", "21", "rollout-b.jsonl"), [
            {"type": "turn_context", "timestamp": "2026-09-21T10:00:00Z", "payload": {"cwd": "/tmp/otro"}},
            {"type": "response_item", "timestamp": "2026-09-21T10:00:03Z",
             "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": LONG}]}},
        ])
        found = sorted(codex.read_prompts("2026-09-01", root))
        self.assertEqual([(p.project, p.session_id, p.day_utc) for p in found],
                         [("/tmp/otro", "rollout-b", "2026-09-21"), (APP, "th-1", "2026-09-20")])

    def test_missing_dir(self):
        self.assertEqual(codex.read_prompts("2026-09-01", "/no/existe"), [])


def make_opencode_db(path):
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE session (id TEXT PRIMARY KEY, directory TEXT);
        CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT, time_created INTEGER, data TEXT);
        CREATE TABLE part (id TEXT PRIMARY KEY, message_id TEXT, session_id TEXT, time_created INTEGER, data TEXT);
    """)
    ms = 1790000000 * 1000
    con.execute("INSERT INTO session VALUES ('ses1', ?)", (APP,))
    con.execute("INSERT INTO message VALUES ('m1', 'ses1', ?, ?)", (ms, json.dumps({"role": "user"})))
    con.execute("INSERT INTO message VALUES ('m2', 'ses1', ?, ?)", (ms, json.dumps({"role": "assistant"})))
    con.executemany("INSERT INTO part VALUES (?, ?, 'ses1', ?, ?)", [
        ("p1", "m1", ms, json.dumps({"type": "text", "text": LONG})),
        ("p2", "m1", ms, json.dumps({"type": "text", "text": "y agrega tests", "synthetic": False})),
        ("p3", "m1", ms, json.dumps({"type": "text", "text": "contenido de archivo", "synthetic": True})),
        ("p4", "m2", ms, json.dumps({"type": "text", "text": LONG})),
    ])
    con.commit()
    con.close()


class TestOpenCode(unittest.TestCase):
    def test_concatenates_text_parts_of_user_messages(self):
        path = os.path.join(tempfile.mkdtemp(), "opencode.db")
        make_opencode_db(path)
        found = opencode.read_prompts("2026-09-01", path)
        self.assertEqual(found, [prompts.Prompt("opencode", APP, "ses1", "2026-09-21", LONG + "\ny agrega tests")])

    def test_missing_file_and_corrupt_db(self):
        self.assertEqual(opencode.read_prompts("2026-09-01", "/no/existe.db"), [])
        path = os.path.join(tempfile.mkdtemp(), "opencode.db")
        with open(path, "w") as fh:
            fh.write("esto no es sqlite" * 100)
        with self.assertRaises(sqlite3.Error):
            opencode.read_prompts("2026-09-01", path)


class TestHermes(unittest.TestCase):
    def test_reads_user_messages_with_project_resolution(self):
        path = os.path.join(tempfile.mkdtemp(), "state.db")
        con = sqlite3.connect(path)
        con.executescript("""
            CREATE TABLE sessions (id TEXT PRIMARY KEY, cwd TEXT, source TEXT, chat_type TEXT);
            CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, timestamp REAL);
        """)
        con.execute("INSERT INTO sessions VALUES ('h1', ?, 'cli', NULL)", (APP,))
        con.execute("INSERT INTO sessions VALUES ('h2', NULL, 'telegram', 'dm')")
        con.executemany("INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)", [
            ("h1", "user", LONG, 1790000000.5), ("h1", "assistant", LONG, 1790000001),
            ("h2", "user", LONG, 1790000002), ("h2", "user", None, 1790000003),
        ])
        con.commit()
        con.close()
        found = hermes.read_prompts("2026-09-01", path)
        self.assertEqual([(p.project, p.session_id) for p in found], [(APP, "h1"), ("telegram:dm", "h2")])

    def test_without_messages_table(self):
        path = os.path.join(tempfile.mkdtemp(), "state.db")
        sqlite3.connect(path).close()
        self.assertEqual(hermes.read_prompts("2026-09-01", path), [])


class TestReadAll(unittest.TestCase):
    def test_self_exclusion_and_errors(self):
        tmp = tempfile.mkdtemp()
        engine_dir = os.path.join(tmp, "motor")
        claude_root = os.path.join(tmp, "claude")
        write_jsonl(os.path.join(claude_root, "-a", "s1.jsonl"), [cc_user(LONG)])
        write_jsonl(os.path.join(claude_root, "-b", "s2.jsonl"), [cc_user(LONG, cwd=engine_dir)])
        corrupt = os.path.join(tmp, "opencode.db")
        with open(corrupt, "w") as fh:
            fh.write("basura" * 200)
        found, errors = prompts.read_all("2026-09-01", {
            "claude_code": claude_root, "codex": os.path.join(tmp, "no"),
            "opencode": corrupt, "hermes": os.path.join(tmp, "no.db"),
        }, engine_dir=engine_dir)
        self.assertEqual([p.session_id for p in found], ["s1"])
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("opencode: "))
```

- [ ] **Paso 2: correr el test y verificar que falla**

Run: `python3 -m unittest tests.test_recommend_prompts -v`
Esperado: FAIL con `ModuleNotFoundError: No module named 'recommend.prompts'`.

- [ ] **Paso 3: implementar**

```python
# recommend/prompts/__init__.py
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
```

```python
# recommend/prompts/claude_code.py
"""Prompts de Claude Code: ~/.claude/projects/*/*.jsonl, registros type=user."""
import glob
import json
import os

from recommend.prompts import Prompt, clean_text, day_from_iso


def _user_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = [b.get("text") for b in content
                 if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str)]
        return "\n".join(texts) if texts else None
    return None


def read_prompts(since, override=None):
    root = override or os.path.expanduser("~/.claude/projects")
    if not os.path.isdir(root):
        return []
    out = []
    for path in sorted(glob.glob(os.path.join(root, "*", "*.jsonl"))):
        session_id = os.path.basename(path)[: -len(".jsonl")]
        project, pending = None, []
        with open(path, "r", errors="ignore") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(rec, dict):
                    continue
                if project is None and isinstance(rec.get("cwd"), str) and rec["cwd"]:
                    project = rec["cwd"]
                if rec.get("type") != "user" or rec.get("isMeta") or rec.get("isCompactSummary"):
                    continue
                day = day_from_iso(rec.get("timestamp"))
                if day is None or day < since:
                    continue
                message = rec.get("message")
                text = clean_text(_user_text(message.get("content") if isinstance(message, dict) else None))
                if text:
                    pending.append((day, text))
        project = project or os.path.basename(os.path.dirname(path))
        out.extend(Prompt("claude_code", project, session_id, day, text) for day, text in pending)
    return out
```

```python
# recommend/prompts/codex.py
"""Prompts de Codex: ~/.codex/sessions/**/*.jsonl, response_item message role=user."""
import glob
import json
import os

from recommend.prompts import Prompt, clean_text, day_from_iso

_TEXT_BLOCKS = ("input_text", "text")


def read_prompts(since, override=None):
    root = override or os.path.expanduser("~/.codex/sessions")
    if not os.path.isdir(root):
        return []
    out = []
    for path in sorted(glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True)):
        session_id, project, pending = None, None, []
        with open(path, "r", errors="ignore") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(rec, dict) or not isinstance(rec.get("payload"), dict):
                    continue
                kind, payload = rec.get("type"), rec["payload"]
                if kind == "session_meta":
                    session_id = session_id or payload.get("id")
                    project = project or payload.get("cwd")
                elif kind == "turn_context":
                    project = project or payload.get("cwd")
                elif kind == "response_item" and payload.get("type") == "message" and payload.get("role") == "user":
                    day = day_from_iso(rec.get("timestamp"))
                    if day is None or day < since:
                        continue
                    blocks = payload.get("content") if isinstance(payload.get("content"), list) else []
                    texts = [b.get("text") for b in blocks if isinstance(b, dict)
                             and b.get("type") in _TEXT_BLOCKS and isinstance(b.get("text"), str)]
                    text = clean_text("\n".join(texts)) if texts else None
                    if text:
                        pending.append((day, text))
        session_id = str(session_id or os.path.basename(path)[: -len(".jsonl")])
        project = project or "unknown"
        out.extend(Prompt("codex", project, session_id, day, text) for day, text in pending)
    return out
```

```python
# recommend/prompts/opencode.py
"""Prompts de OpenCode: opencode.db, message(role=user) + part(type=text)."""
import json
import os
import sqlite3
from pathlib import Path

from recommend.prompts import Prompt, clean_text, day_from_epoch

_SQL = """
SELECT s.id, s.directory, m.id, m.time_created, m.data, p.data
FROM message m JOIN session s ON s.id = m.session_id JOIN part p ON p.message_id = m.id
ORDER BY m.time_created, m.id, p.id
"""


def _json(value):
    try:
        data = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def read_prompts(since, override=None):
    path = override or os.path.expanduser("~/.local/share/opencode/opencode.db")
    if not os.path.isfile(path):
        return []
    con = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        tables = {name for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if not {"session", "message", "part"} <= tables:
            return []
        rows = con.execute(_SQL).fetchall()
    finally:
        con.close()

    messages = {}  # message_id -> [session_id, directory, day, [textos]]
    for session_id, directory, message_id, created, message_data, part_data in rows:
        if _json(message_data).get("role") != "user":
            continue
        part = _json(part_data)
        if part.get("type") != "text" or part.get("synthetic") or not isinstance(part.get("text"), str):
            continue
        entry = messages.setdefault(message_id, [session_id, directory, day_from_epoch((created or 0) / 1000), []])
        entry[3].append(part["text"])

    out = []
    for session_id, directory, day, texts in messages.values():
        text = clean_text("\n".join(texts))
        if text and day and day >= since:
            out.append(Prompt("opencode", directory or "unknown", str(session_id), day, text))
    return out
```

```python
# recommend/prompts/hermes.py
"""Prompts de Hermes: state.db, messages role=user (+ sessions para el proyecto)."""
import os
import sqlite3
from pathlib import Path

from collectors.hermes import _project_for
from recommend.prompts import Prompt, clean_text, day_from_epoch

_SESSION_COLUMNS = ("cwd", "source", "chat_type")


def read_prompts(since, override=None):
    path = override or os.path.expanduser("~/.hermes/state.db")
    if not os.path.isfile(path):
        return []
    con = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        tables = {name for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "messages" not in tables:
            return []
        existing = set()
        if "sessions" in tables:
            existing = {r[1] for r in con.execute("PRAGMA table_info(sessions)")}
        cols = [c for c in _SESSION_COLUMNS if c in existing]
        select = ", ".join([f"s.{c}" for c in cols]) or "NULL"
        join = "LEFT JOIN sessions s ON s.id = m.session_id" if "sessions" in tables else ""
        rows = con.execute(
            f"SELECT m.session_id, m.timestamp, m.content, {select} FROM messages m {join} "
            "WHERE m.role = 'user' ORDER BY m.timestamp").fetchall()
    finally:
        con.close()

    out = []
    for row in rows:
        session_id, timestamp, content = row[0], row[1], row[2]
        info = dict(zip(cols, row[3:]))
        day = day_from_epoch(timestamp)
        text = clean_text(content)
        if not text or day is None or day < since:
            continue
        project = _project_for(info.get("cwd"), info.get("source"), info.get("chat_type"))
        out.append(Prompt("hermes", project, str(session_id), day, text))
    return out
```

- [ ] **Paso 4: correr el test y verificar que pasa**

Run: `python3 -m unittest tests.test_recommend_prompts -v`
Esperado: PASS. Si `test_days` falla por el epoch, calcula el día con `python3 -c "from datetime import *;print(datetime.fromtimestamp(1790000000,tz=timezone.utc))"` y corrige la **expectativa** del test (no el código).

- [ ] **Paso 5: commit**

```bash
git add recommend/prompts tests/test_recommend_prompts.py
git commit -m "feat(recommend): lectores de prompts de Claude Code, Codex, OpenCode y Hermes"
```

---

---

### Tarea 3: Clustering léxico y features (`recommend/cluster.py`)

**Archivos:**
- Crear: `recommend/cluster.py`
- Test: `tests/test_recommend_cluster.py`

**Interfaces:**
- Consume: `recommend.prompts.Prompt` (Tarea 2). Los textos llegan **ya redactados** (lo hace `engine.py`).
- Produce:
  - `normalize(text) -> list[str]`, `trigrams(words) -> set[str]`, `jaccard(a: set, b: set) -> float`.
  - `SERVICES` (tupla de servicios conocidos), `IMPERATIVE_VERBS` (frozenset normalizado).
  - `@dataclass Cluster(cluster_id: str, members: list[Prompt], signature: set[str], session_tokens: dict, features: dict)` con:
    - propiedades `sessions` (set de `(source, session_id)`), `days` (set), `projects` (lista ordenada), `sources` (lista ordenada), `tokens` (int), `tool` (`str`: la fuente única o `"varias"`), `score` (`len(sessions) * tokens`) y `pattern` (`str` ≤120);
    - métodos `snippets() -> list[str]` (≤3, ≤200 caracteres cada uno), `common_steps() -> list[str]` y `evidence() -> dict` con las claves `sessions`, `days`, `tokens`, `projects`, `sources` y `snippets`.
  - `features` es un dict `{"pega_datos": bool, "menciona_servicio": list[str], "mismos_pasos": bool}`.
  - `candidates(prompts, session_tokens, limit=40) -> list[Cluster]` (ids `c1`…).
  - `lexical_clusters(prompts, session_tokens, limit=10) -> list[Cluster]` (ids `c1`…; ya aplica los umbrales finales).
  - `merge(clusters, group_id) -> Cluster`, `passes_final(cluster) -> bool`, `rank_final(clusters, limit=10) -> list[Cluster]`.
  - `session_tokens` mapea `(source, session_id)` → tokens de esa sesión según el collector. Si una sesión falta en el mapa, se estima como `len(texto)//4` sumado sobre sus prompts del cluster.

- [ ] **Paso 1: escribir el test que falla**

```python
# tests/test_recommend_cluster.py
import unittest

from recommend import cluster
from recommend.prompts import Prompt

REPEATED = "revisa los logs del servicio de pagos y dime por qué falla el cobro con tarjeta"
OTHER = "explícame cómo funciona el patrón repositorio en una aplicación hexagonal grande"


def p(text, session, day="2026-09-20", source="claude_code", project="/home/u/DEV/ACME/app"):
    return Prompt(source, project, session, day, text)


class TestNormalize(unittest.TestCase):
    def test_normalize_strips_accents_punctuation_and_stopwords(self):
        self.assertEqual(cluster.normalize("¡Revisa LOS logs, del Servicio de pagos!"),
                         ["revisa", "logs", "servicio", "pagos"])

    def test_trigrams(self):
        self.assertEqual(cluster.trigrams(["a", "b", "c", "d"]), {"a b c", "b c d"})
        self.assertEqual(cluster.trigrams(["hola", "mundo"]), {"hola mundo"})
        self.assertEqual(cluster.trigrams([]), set())

    def test_jaccard(self):
        self.assertEqual(cluster.jaccard({"a", "b"}, {"b", "c"}), 1 / 3)
        self.assertEqual(cluster.jaccard(set(), {"a"}), 0.0)


class TestGrouping(unittest.TestCase):
    def test_thresholds_via_union_find(self):
        sets = [{"a", "b", "c", "d"}, {"a", "b", "c", "e"}, {"a", "b", "f", "g"}, {"x", "y"}]
        # J(0,1)=0.6, J(0,2)=J(1,2)=2/6≈0.33
        self.assertEqual(sorted(map(sorted, cluster._union_find_groups(sets, 0.5))), [[0, 1], [2], [3]])
        self.assertEqual(sorted(map(sorted, cluster._union_find_groups(sets, 0.3))), [[0, 1, 2], [3]])

    def test_candidates_need_two_sessions_and_are_ranked_by_tokens(self):
        prompts = [p(REPEATED, "s1"), p(REPEATED, "s1"),                  # una sola sesión: no es candidato
                   p(OTHER, "s2"), p(OTHER + " ahora", "s3"),               # dos sesiones: candidato
                   p("tarea única sin parecido con ninguna otra cosa", "s4")]
        found = cluster.candidates(prompts, {("claude_code", "s2"): 50, ("claude_code", "s3"): 70})
        self.assertEqual([c.cluster_id for c in found], ["c1"])
        self.assertEqual(found[0].tokens, 120)
        self.assertEqual(len(found[0].sessions), 2)

    def test_candidates_limit(self):
        prompts = []
        for i in range(45):
            text = f"tema{i} alfa{i} beta{i} gamma{i} delta{i}"
            prompts += [p(text, f"a{i}"), p(text, f"b{i}")]
        tokens = {("claude_code", f"a{i}"): i for i in range(45)}
        found = cluster.candidates(prompts, tokens)
        self.assertEqual(len(found), 40)
        self.assertEqual(found[0].cluster_id, "c1")
        self.assertGreaterEqual(found[0].tokens, found[-1].tokens)

    def test_lexical_mode_applies_final_thresholds(self):
        three_sessions_two_days = [p(REPEATED, "s1", "2026-09-20"), p(REPEATED, "s2", "2026-09-20"),
                                   p(REPEATED, "s3", "2026-09-21")]
        three_sessions_one_day = [p(OTHER, f"o{i}", "2026-09-22") for i in range(3)]
        found = cluster.lexical_clusters(three_sessions_two_days + three_sessions_one_day, {})
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].days, {"2026-09-20", "2026-09-21"})
        self.assertEqual(found[0].cluster_id, "c1")

    def test_missing_session_tokens_fall_back_to_text_length(self):
        found = cluster.lexical_clusters([p(REPEATED, "s1", "2026-09-20"), p(REPEATED, "s2", "2026-09-20"),
                                          p(REPEATED, "s3", "2026-09-21")], {("claude_code", "s1"): 1000})
        self.assertEqual(found[0].tokens, 1000 + 2 * (len(REPEATED) // 4))


class TestClusterProperties(unittest.TestCase):
    def test_pattern_tool_and_evidence(self):
        c = cluster._build("c1", [p(REPEATED + "\nsegunda línea", "s1"), p(REPEATED, "s2", source="codex"),
                                  p(REPEATED + " y más contexto", "s3", "2026-09-21", project="/home/u/DEV/OTRO/x")], {})
        self.assertEqual(c.pattern, REPEATED)
        self.assertEqual(c.tool, "varias")
        ev = c.evidence()
        self.assertEqual(ev["sessions"], 3)
        self.assertEqual(ev["days"], 2)
        self.assertEqual(ev["sources"], ["claude_code", "codex"])
        self.assertEqual(ev["projects"], ["/home/u/DEV/ACME/app", "/home/u/DEV/OTRO/x"])
        self.assertLessEqual(len(ev["snippets"]), 3)
        self.assertTrue(all(len(s) <= 200 for s in ev["snippets"]))

    def test_features(self):
        log = "Traceback (most recent call last):\n  File \"x.py\", line 1\nValueError: boom"
        c = cluster._build("c1", [p("revisa este error de sentry: " + log, "s1"),
                                  p("revisa y corrige y luego ejecuta los tests del módulo", "s2"),
                                  p("revisa y corrige y luego ejecuta los tests del otro módulo", "s3")], {})
        self.assertTrue(c.features["pega_datos"])
        self.assertEqual(c.features["menciona_servicio"], ["sentry"])
        self.assertTrue(c.features["mismos_pasos"])
        self.assertEqual(c.common_steps(), ["revisa", "corrige", "ejecuta"])

    def test_plain_text_has_no_features(self):
        c = cluster._build("c1", [p(OTHER, "s1"), p(OTHER, "s2")], {})
        self.assertEqual(c.features, {"pega_datos": False, "menciona_servicio": [], "mismos_pasos": False})


class TestMerge(unittest.TestCase):
    def test_merge_unions_members_signature_and_ors_features(self):
        a = cluster._build("c1", [p("revisa este error de sentry " + "x " * 800, "s1")], {})
        b = cluster._build("c2", [p(OTHER, "s2", "2026-09-21"), p(OTHER, "s3", "2026-09-22")], {})
        merged = cluster.merge([a, b], "g1")
        self.assertEqual(merged.cluster_id, "g1")
        self.assertEqual(len(merged.sessions), 3)
        self.assertEqual(merged.signature, a.signature | b.signature)
        self.assertTrue(merged.features["pega_datos"])
        self.assertEqual(merged.features["menciona_servicio"], ["sentry"])
        self.assertTrue(cluster.passes_final(merged))

    def test_rank_final_filters_and_orders(self):
        weak = cluster._build("c1", [p(OTHER, "s1"), p(OTHER, "s2")], {})
        strong = cluster._build("c2", [p(REPEATED, f"s{i}", f"2026-09-2{i}") for i in range(3)], {})
        self.assertEqual([c.cluster_id for c in cluster.rank_final([weak, strong])], ["c2"])
```

Nota: el test usa `cluster._build(cluster_id, members, session_tokens)`, el constructor interno que calcula firma y features; forma parte de la interfaz de la tarea.

- [ ] **Paso 2: correr el test y verificar que falla**

Run: `python3 -m unittest tests.test_recommend_cluster -v`
Esperado: FAIL con `ImportError: cannot import name 'cluster' from 'recommend'`.

- [ ] **Paso 3: implementar**

```python
# recommend/cluster.py
"""Clustering léxico de prompts (spec §3.3): trigramas de palabras + Jaccard
con índice invertido y union-find. Dos modos: candidatos para el LLM
(≥0,3, ≥2 sesiones, top 40) y solo léxico (≥0,5, umbrales finales, top 10)."""
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field

CANDIDATE_THRESHOLD = 0.3
CANDIDATE_MIN_SESSIONS = 2
CANDIDATE_LIMIT = 40
LEXICAL_THRESHOLD = 0.5
FINAL_MIN_SESSIONS = 3
FINAL_MIN_DAYS = 2
FINAL_LIMIT = 10
SIGNATURE_SIZE = 50
SNIPPETS = 3
SNIPPET_CHARS = 200
PATTERN_CHARS = 120

STOPWORDS = frozenset("""
a al algo como con de del el ella en entre es esa ese eso esta este esto la las le les lo los mas me mi muy
no nos o para pero por que se si sin sobre su sus te tu un una uno unos y ya yo hay son fue ser esta estan
the a an and are as at be but by for from has have i in is it its me my of on or so that the this to was
we with you your do does can please
""".split())

SERVICES = ("jira", "github", "gitlab", "sentry", "slack", "notion", "linear", "confluence", "figma",
            "trello", "asana", "bitbucket", "jenkins", "datadog", "grafana", "vercel", "supabase", "stripe")

IMPERATIVE_VERBS = frozenset("""
revisa corrige arregla ejecuta corre crea agrega anade actualiza sube despliega genera escribe lee abre
compila prueba haz elimina borra busca documenta refactoriza migra instala configura valida verifica
analiza resume traduce commitea
review fix run create add update deploy generate write read open build test remove delete search find
document refactor migrate install configure validate verify check analyze summarize translate commit push
""".split())

_WORD = re.compile(r"[a-z0-9]+")
_PASTED = re.compile(
    r"Traceback \(most recent call last\)|^\s+at [\w.$<>]+\(|^\s*[{\[]\s*\"|\b(?:ERROR|WARN(?:ING)?|FATAL)\b"
    r"|^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}", re.MULTILINE)
PASTED_MIN_CHARS = 1500
PASTED_MIN_LINES = 15


def normalize(text):
    plain = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(ch for ch in plain if not unicodedata.combining(ch))
    return [w for w in _WORD.findall(plain) if w not in STOPWORDS]


def trigrams(words):
    if not words:
        return set()
    if len(words) < 3:
        return {" ".join(words)}
    return {" ".join(words[i:i + 3]) for i in range(len(words) - 2)}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _union_find_groups(sets, threshold):
    parent = list(range(len(sets)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    index = defaultdict(list)
    for i, grams in enumerate(sets):
        for gram in grams:
            index[gram].append(i)
    for i, grams in enumerate(sets):
        neighbours = {j for gram in grams for j in index[gram] if j > i}
        for j in neighbours:
            if find(i) != find(j) and jaccard(grams, sets[j]) >= threshold:
                parent[find(j)] = find(i)

    groups = defaultdict(list)
    for i in range(len(sets)):
        groups[find(i)].append(i)
    return list(groups.values())


def _verb_sequence(text):
    seq = []
    for word in normalize(text):
        if word in IMPERATIVE_VERBS and (not seq or seq[-1] != word):
            seq.append(word)
    return seq


def _step_pairs(text):
    seq = _verb_sequence(text)
    return {(seq[i], seq[i + 1]) for i in range(len(seq) - 1)}


def _features(members):
    pasted = any(_PASTED.search(m.text) or len(m.text) >= PASTED_MIN_CHARS
                 or m.text.count("\n") >= PASTED_MIN_LINES for m in members)
    words = set()
    for m in members:
        words.update(normalize(m.text))
    services = [s for s in SERVICES if s in words]
    pair_counts = Counter(pair for m in members for pair in _step_pairs(m.text))
    same_steps = any(count >= 2 for count in pair_counts.values())
    return {"pega_datos": bool(pasted), "menciona_servicio": services, "mismos_pasos": same_steps}


def _signature(members):
    counts = Counter(gram for m in members for gram in trigrams(normalize(m.text)))
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return {gram for gram, _ in ranked[:SIGNATURE_SIZE]}


@dataclass
class Cluster:
    cluster_id: str
    members: list
    signature: set
    session_tokens: dict = field(repr=False)
    features: dict

    @property
    def sessions(self):
        return {(m.source, m.session_id) for m in self.members}

    @property
    def days(self):
        return {m.day_utc for m in self.members}

    @property
    def projects(self):
        return sorted({m.project for m in self.members})

    @property
    def sources(self):
        return sorted({m.source for m in self.members})

    @property
    def tokens(self):
        estimated = Counter()
        for m in self.members:
            estimated[(m.source, m.session_id)] += len(m.text) // 4
        return sum(self.session_tokens.get(key, estimated[key]) for key in self.sessions)

    @property
    def tool(self):
        sources = self.sources
        return sources[0] if len(sources) == 1 else "varias"

    @property
    def score(self):
        return len(self.sessions) * self.tokens

    @property
    def pattern(self):
        shortest = min(self.members, key=lambda m: (len(m.text), m.text))
        return shortest.text.strip().splitlines()[0][:PATTERN_CHARS]

    def snippets(self):
        out, seen_sessions = [], set()
        for m in sorted(self.members, key=lambda m: (m.day_utc, m.session_id)):
            key = (m.source, m.session_id)
            snippet = m.text.strip()[:SNIPPET_CHARS]
            if key in seen_sessions or snippet in out:
                continue
            seen_sessions.add(key)
            out.append(snippet)
            if len(out) == SNIPPETS:
                break
        return out

    def common_steps(self):
        sequences = [tuple(_verb_sequence(m.text)) for m in self.members]
        counts = Counter(seq for seq in sequences if len(seq) >= 2)
        if not counts:
            return []
        seq, _ = max(counts.items(), key=lambda kv: (kv[1], len(kv[0]), kv[0]))
        return list(seq)

    def evidence(self):
        return {"sessions": len(self.sessions), "days": len(self.days), "tokens": self.tokens,
                "projects": self.projects, "sources": self.sources, "snippets": self.snippets()}


def _build(cluster_id, members, session_tokens):
    return Cluster(cluster_id, list(members), _signature(members), session_tokens, _features(members))


def _groups(prompts, threshold):
    usable = [(p, trigrams(normalize(p.text))) for p in prompts]
    usable = [(p, grams) for p, grams in usable if grams]
    indices = _union_find_groups([grams for _, grams in usable], threshold)
    return [[usable[i][0] for i in group] for group in indices]


def _renumber(clusters):
    for i, c in enumerate(clusters, start=1):
        c.cluster_id = f"c{i}"
    return clusters


def candidates(prompts, session_tokens, limit=CANDIDATE_LIMIT):
    built = [_build("", members, session_tokens) for members in _groups(prompts, CANDIDATE_THRESHOLD)]
    built = [c for c in built if len(c.sessions) >= CANDIDATE_MIN_SESSIONS]
    built.sort(key=lambda c: (-c.tokens, c.pattern))
    return _renumber(built[:limit])


def passes_final(c):
    return len(c.sessions) >= FINAL_MIN_SESSIONS and len(c.days) >= FINAL_MIN_DAYS


def rank_final(clusters, limit=FINAL_LIMIT):
    kept = [c for c in clusters if passes_final(c)]
    kept.sort(key=lambda c: (-c.score, c.pattern))
    return kept[:limit]


def lexical_clusters(prompts, session_tokens, limit=FINAL_LIMIT):
    built = [_build("", members, session_tokens) for members in _groups(prompts, LEXICAL_THRESHOLD)]
    return _renumber(rank_final(built, limit))


def merge(clusters, group_id):
    members = [m for c in clusters for m in c.members]
    features = {
        "pega_datos": any(c.features["pega_datos"] for c in clusters),
        "menciona_servicio": [s for s in SERVICES if any(s in c.features["menciona_servicio"] for c in clusters)],
        "mismos_pasos": any(c.features["mismos_pasos"] for c in clusters),
    }
    signature = set().union(*(c.signature for c in clusters)) if clusters else set()
    session_tokens = clusters[0].session_tokens if clusters else {}
    return Cluster(group_id, members, signature, session_tokens, features)
```

Nota: en `Cluster`, un campo sin valor por defecto no puede ir después de uno con `field(...)` con default, pero `field(repr=False)` no define default, así que el orden es válido.

- [ ] **Paso 4: correr el test y verificar que pasa**

Run: `python3 -m unittest tests.test_recommend_cluster -v`
Esperado: PASS. Si `test_normalize_strips_accents_punctuation_and_stopwords` falla porque una palabra esperada está en `STOPWORDS`, corrige la lista de stopwords, no el test.

- [ ] **Paso 5: commit**

```bash
git add recommend/cluster.py tests/test_recommend_cluster.py
git commit -m "feat(recommend): clustering léxico con candidatos, modo léxico y features"
```

---

### Tarea 4: Configuración del motor y persistencia (`recommend/settings.py`, `recommend/store.py`)

**Archivos:**
- Crear: `recommend/settings.py`, `recommend/store.py`
- Test: `tests/test_recommend_store.py`

**Interfaces:**
- Consume: `history.DB_PATH_DEFAULT`, `history.ensure_schema(db_path)`; `recommend.cluster.jaccard` (Tarea 3).
- Produce, en `recommend/settings.py` (sin dependencias de `store` ni de `llm`, para evitar imports circulares):
  - `BACKENDS = ("hermes", "claude", "none")`, `DEFAULT_BACKEND = "hermes"`, `DEFAULT_CHAIN` (lista de 3 entradas).
  - `is_free(model) -> bool`; `parse_entry(entry) -> (provider, model)`, que lanza `ValueError`.
  - `EngineSettingsError(ValueError)`; `validate_engine_settings(payload) -> dict` normalizado `{"backend", "llm_chain"}`.
- Produce, en `recommend/store.py`:
  - `SCHEMA`, `STATUSES = ("nueva", "aplicada", "saltada", "resuelta")`, `USER_STATUSES = ("nueva", "aplicada", "saltada")`.
  - `connect(db_path=None) -> sqlite3.Connection` (con `row_factory = sqlite3.Row`).
  - `get_engine_settings(db_path=None) -> {"backend", "llm_chain"}` y `save_engine_settings(settings, db_path=None)`.
  - `start_run(db_path, trigger, backend, now) -> int`, `finish_run(db_path, run_id, status, now, **fields)`, `get_run(db_path, run_id) -> dict | None`, `last_run(db_path) -> dict | None` y `latest_finished_run_id(db_path) -> int | None`.
  - `list_recommendations(db_path, status="nueva") -> list[dict]` (con `evidence` ya parseado a dict; `status="todas"` devuelve todas).
  - `set_status(db_path, rec_id, status, now) -> dict | None`.
  - `apply_run(db_path, pattern_recs, cost_recs, now) -> {"created", "updated", "resolved"}`.
  - `now` es siempre un ISO UTC `str`.

- [ ] **Paso 1: escribir el test que falla**

```python
# tests/test_recommend_store.py
import os
import sqlite3
import tempfile
import unittest

from recommend import settings as engine_settings
from recommend import store

NOW1, NOW2, NOW3 = "2026-09-20T07:00:00+00:00", "2026-09-21T07:00:00+00:00", "2026-09-22T07:00:00+00:00"
SIG_A = [f"tri {i}" for i in range(10)]
SIG_A2 = SIG_A[:8] + ["otro 1", "otro 2"]          # Jaccard 8/12 ≈ 0,67 con SIG_A
SIG_B = [f"zzz {i}" for i in range(10)]


def pattern_rec(signature, generator="reglas", kind="prompt", tokens=100, **extra):
    rec = {"tool": "claude_code", "tokens": tokens, "pattern": "revisa los logs", "kind": kind,
           "description": "desc", "impact": "medio", "evidence": {"sessions": 3, "sources": ["claude_code"]},
           "draft": "borrador", "signature": signature, "generator": generator}
    rec.update(extra)
    return rec


def cost_rec(project="/home/u/DEV/ACME/app", title="ACME concentra el 80 %"):
    return {"tool": "claude_code", "tokens": 5000, "pattern": title, "kind": "costo", "description": "d",
            "impact": "medio", "evidence": {"rule": "project_concentration", "sources": ["claude_code"]},
            "draft": "revisa", "generator": "costo",
            "signature": {"rule": "project_concentration", "source": "claude_code", "project": project}}


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "history.db")


class TestSettings(StoreTestCase):
    def test_is_free_and_parse_entry(self):
        self.assertTrue(engine_settings.is_free("upstage/solar-pro4:free"))
        self.assertTrue(engine_settings.is_free("stealth/space-bunny-alpha"))
        self.assertFalse(engine_settings.is_free("anthropic/claude-sonnet"))
        self.assertEqual(engine_settings.parse_entry("nous:upstage/solar-pro4:free"),
                         ("nous", "upstage/solar-pro4:free"))
        for bad in ("sinproveedor", ":modelo", "prov:", "", None):
            with self.assertRaises(ValueError):
                engine_settings.parse_entry(bad)

    def test_validate(self):
        ok = engine_settings.validate_engine_settings({"backend": "hermes", "llm_chain": ["nous:stealth/x"]})
        self.assertEqual(ok, {"backend": "hermes", "llm_chain": ["nous:stealth/x"]})
        claude = engine_settings.validate_engine_settings({"backend": "claude", "llm_chain": ["nous:pago/m"]})
        self.assertEqual(claude["backend"], "claude")
        for bad in ({"backend": "otro", "llm_chain": ["nous:stealth/x"]},
                    {"backend": "hermes", "llm_chain": []},
                    {"backend": "hermes", "llm_chain": "nous:stealth/x"},
                    {"backend": "hermes", "llm_chain": ["nous:pago/modelo"]},
                    {"backend": "hermes"}, {"backend": "hermes", "llm_chain": ["x"], "extra": 1}, []):
            with self.assertRaises(engine_settings.EngineSettingsError, msg=str(bad)):
                engine_settings.validate_engine_settings(bad)

    def test_get_defaults_save_and_corrupt_fallback(self):
        self.assertEqual(store.get_engine_settings(self.db),
                         {"backend": "hermes", "llm_chain": list(engine_settings.DEFAULT_CHAIN)})
        store.save_engine_settings({"backend": "none", "llm_chain": ["nous:stealth/x"]}, self.db)
        self.assertEqual(store.get_engine_settings(self.db), {"backend": "none", "llm_chain": ["nous:stealth/x"]})
        con = sqlite3.connect(self.db)
        con.execute("UPDATE engine_settings SET value = '{roto' WHERE key = 'llm_chain'")
        con.execute("UPDATE engine_settings SET value = 'raro' WHERE key = 'backend'")
        con.commit()
        con.close()
        self.assertEqual(store.get_engine_settings(self.db),
                         {"backend": "hermes", "llm_chain": list(engine_settings.DEFAULT_CHAIN)})


class TestRuns(StoreTestCase):
    def test_run_lifecycle(self):
        self.assertIsNone(store.last_run(self.db))
        self.assertIsNone(store.latest_finished_run_id(self.db))
        run_id = store.start_run(self.db, "manual", "hermes", NOW1)
        self.assertEqual(store.get_run(self.db, run_id)["status"], "corriendo")
        self.assertIsNone(store.latest_finished_run_id(self.db))
        store.finish_run(self.db, run_id, "ok", NOW2, model="nous:stealth/x", attempts=1, prompts=10,
                         clusters=2, created=2, updated=0, resolved=0, llm_tokens=900, llm_cost=0.0)
        run = store.last_run(self.db)
        self.assertEqual((run["id"], run["status"], run["model"], run["finished_at"]),
                         (run_id, "ok", "nous:stealth/x", NOW2))
        self.assertEqual(store.latest_finished_run_id(self.db), run_id)
        with self.assertRaises(ValueError):
            store.finish_run(self.db, run_id, "ok", NOW2, columna_rara=1)


class TestApplyRun(StoreTestCase):
    def test_creates_then_updates_by_similar_signature(self):
        self.assertEqual(store.apply_run(self.db, [pattern_rec(SIG_A)], [], NOW1),
                         {"created": 1, "updated": 0, "resolved": 0})
        first = store.list_recommendations(self.db)[0]
        counts = store.apply_run(self.db, [pattern_rec(SIG_A2, tokens=900, impact="alto")], [], NOW2)
        self.assertEqual(counts, {"created": 0, "updated": 1, "resolved": 0})
        [row] = store.list_recommendations(self.db)
        self.assertEqual((row["id"], row["first_seen"], row["last_seen"], row["tokens"], row["impact"]),
                         (first["id"], NOW1, NOW2, 900, "alto"))
        self.assertEqual(row["evidence"], {"sessions": 3, "sources": ["claude_code"]})

    def test_different_signature_creates_new(self):
        store.apply_run(self.db, [pattern_rec(SIG_A)], [], NOW1)
        store.apply_run(self.db, [pattern_rec(SIG_B)], [], NOW2)
        self.assertEqual(len(store.list_recommendations(self.db)), 2)

    def test_skipped_stays_hidden_and_only_last_seen_changes(self):
        store.apply_run(self.db, [pattern_rec(SIG_A)], [], NOW1)
        rec_id = store.list_recommendations(self.db)[0]["id"]
        store.set_status(self.db, rec_id, "saltada", NOW1)
        store.apply_run(self.db, [pattern_rec(SIG_A, tokens=999, generator="nous:stealth/x",
                                              description="nueva")], [], NOW2)
        self.assertEqual(store.list_recommendations(self.db), [])
        [row] = store.list_recommendations(self.db, "saltada")
        self.assertEqual((row["last_seen"], row["tokens"], row["description"]), (NOW2, 100, "desc"))

    def test_applied_keeps_status_but_updates_evidence(self):
        store.apply_run(self.db, [pattern_rec(SIG_A)], [], NOW1)
        rec_id = store.list_recommendations(self.db)[0]["id"]
        store.set_status(self.db, rec_id, "aplicada", NOW1)
        store.apply_run(self.db, [pattern_rec(SIG_A, tokens=500)], [], NOW2)
        [row] = store.list_recommendations(self.db, "aplicada")
        self.assertEqual((row["status"], row["tokens"]), ("aplicada", 500))

    def test_llm_enriches_rules_generated_recommendation(self):
        store.apply_run(self.db, [pattern_rec(SIG_A)], [], NOW1)
        store.apply_run(self.db, [pattern_rec(SIG_A, generator="nous:stealth/x", kind="skill",
                                              description="mejor", draft="---\nname: x\n---")], [], NOW2)
        [row] = store.list_recommendations(self.db)
        self.assertEqual((row["generator"], row["kind"], row["description"]), ("nous:stealth/x", "skill", "mejor"))
        store.apply_run(self.db, [pattern_rec(SIG_A, generator="reglas", description="peor")], [], NOW3)
        self.assertEqual(store.list_recommendations(self.db)[0]["description"], "mejor")

    def test_cost_matches_exactly_and_resolves_when_rule_stops(self):
        store.apply_run(self.db, [], [cost_rec()], NOW1)
        store.apply_run(self.db, [], [cost_rec(title="ACME concentra el 90 %")], NOW2)
        [row] = store.list_recommendations(self.db)
        self.assertEqual(row["pattern"], "ACME concentra el 90 %")
        counts = store.apply_run(self.db, [], [], NOW3)
        self.assertEqual(counts["resolved"], 1)
        self.assertEqual(store.list_recommendations(self.db), [])
        self.assertEqual(store.list_recommendations(self.db, "resuelta")[0]["status_at"], NOW3)
        store.apply_run(self.db, [], [cost_rec()], NOW3)  # vuelve a dispararse → se reabre
        self.assertEqual(len(store.list_recommendations(self.db)), 1)

    def test_other_project_is_a_different_cost_recommendation(self):
        store.apply_run(self.db, [], [cost_rec(), cost_rec(project="/home/u/DEV/OTRO/x")], NOW1)
        self.assertEqual(len(store.list_recommendations(self.db)), 2)

    def test_never_deletes_rows(self):
        store.apply_run(self.db, [pattern_rec(SIG_A)], [cost_rec()], NOW1)
        for now in (NOW2, NOW3):
            store.apply_run(self.db, [], [], now)
        self.assertEqual(len(store.list_recommendations(self.db, "todas")), 2)

    def test_rollback_on_failure_keeps_previous_rows(self):
        store.apply_run(self.db, [pattern_rec(SIG_A)], [], NOW1)
        before = store.list_recommendations(self.db, "todas")
        broken = pattern_rec(SIG_B)
        del broken["draft"]
        with self.assertRaises(KeyError):
            store.apply_run(self.db, [pattern_rec(SIG_A, tokens=777), broken], [], NOW2)
        self.assertEqual(store.list_recommendations(self.db, "todas"), before)


class TestStatus(StoreTestCase):
    def test_set_status_and_listing(self):
        store.apply_run(self.db, [pattern_rec(SIG_A, impact="bajo"), pattern_rec(SIG_B, impact="alto")], [], NOW1)
        rows = store.list_recommendations(self.db)
        self.assertEqual([r["impact"] for r in rows], ["alto", "bajo"])
        updated = store.set_status(self.db, rows[0]["id"], "aplicada", NOW2)
        self.assertEqual((updated["status"], updated["status_at"]), ("aplicada", NOW2))
        self.assertIsNone(store.set_status(self.db, "noexiste", "aplicada", NOW2))
        with self.assertRaises(ValueError):
            store.set_status(self.db, rows[0]["id"], "resuelta", NOW2)
        with self.assertRaises(ValueError):
            store.list_recommendations(self.db, "rara")
```

- [ ] **Paso 2: correr el test y verificar que falla**

Run: `python3 -m unittest tests.test_recommend_store -v`
Esperado: FAIL con `ImportError: cannot import name 'settings' from 'recommend'`.

- [ ] **Paso 3: implementar `recommend/settings.py`**

```python
# recommend/settings.py
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
```

- [ ] **Paso 4: implementar `recommend/store.py`**

```python
# recommend/store.py
"""Persistencia del motor en history.db (spec §4). Nunca borra filas: las
recomendaciones solo cambian de estado. Todas las escrituras de una corrida
van en una transacción; si algo falla, rollback y las filas previas quedan."""
import hashlib
import json
import sqlite3

import history
from recommend.cluster import jaccard
from recommend.settings import BACKENDS, DEFAULT_BACKEND, DEFAULT_CHAIN, parse_entry

SCHEMA = """
CREATE TABLE IF NOT EXISTS recommendations (
  id TEXT PRIMARY KEY, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, tool TEXT NOT NULL,
  tokens INTEGER NOT NULL, pattern TEXT NOT NULL, kind TEXT NOT NULL, description TEXT NOT NULL,
  impact TEXT NOT NULL, evidence TEXT NOT NULL, draft TEXT NOT NULL, signature TEXT NOT NULL,
  status TEXT NOT NULL, status_at TEXT NOT NULL, generator TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS recommendation_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, finished_at TEXT,
  trigger TEXT NOT NULL, backend TEXT NOT NULL, model TEXT, attempts INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL, prompts INTEGER, clusters INTEGER, created INTEGER, updated INTEGER,
  resolved INTEGER, error TEXT, llm_tokens INTEGER, llm_cost REAL
);
CREATE TABLE IF NOT EXISTS engine_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

STATUSES = ("nueva", "aplicada", "saltada", "resuelta")
USER_STATUSES = ("nueva", "aplicada", "saltada")
SAME_PATTERN_THRESHOLD = 0.5
_RUN_FIELDS = ("model", "attempts", "prompts", "clusters", "created", "updated", "resolved",
               "error", "llm_tokens", "llm_cost")
_IMPACT_ORDER = "CASE impact WHEN 'alto' THEN 0 WHEN 'medio' THEN 1 ELSE 2 END"
_NON_LLM = ("reglas", "costo")


def connect(db_path=None):
    db_path = db_path or history.DB_PATH_DEFAULT
    history.ensure_schema(db_path)
    con = sqlite3.connect(db_path, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout = 30000")
    con.executescript(SCHEMA)
    return con


# --- Configuración -------------------------------------------------------------

def _valid_chain(value):
    try:
        chain = json.loads(value)
        if not isinstance(chain, list) or not chain:
            return None
        for entry in chain:
            parse_entry(entry)
    except (TypeError, ValueError):
        return None
    return chain


def get_engine_settings(db_path=None):
    con = connect(db_path)
    try:
        rows = dict(con.execute("SELECT key, value FROM engine_settings").fetchall())
    finally:
        con.close()
    backend = rows.get("backend") if rows.get("backend") in BACKENDS else DEFAULT_BACKEND
    chain = _valid_chain(rows.get("llm_chain")) or list(DEFAULT_CHAIN)
    return {"backend": backend, "llm_chain": chain}


def save_engine_settings(settings, db_path=None):
    """Recibe un payload ya validado con settings.validate_engine_settings."""
    con = connect(db_path)
    try:
        with con:
            con.execute("INSERT OR REPLACE INTO engine_settings (key, value) VALUES ('backend', ?)",
                        (settings["backend"],))
            con.execute("INSERT OR REPLACE INTO engine_settings (key, value) VALUES ('llm_chain', ?)",
                        (json.dumps(settings["llm_chain"]),))
    finally:
        con.close()


# --- Corridas --------------------------------------------------------------------

def start_run(db_path, trigger, backend, now):
    con = connect(db_path)
    try:
        with con:
            cur = con.execute(
                "INSERT INTO recommendation_runs (started_at, trigger, backend, status) VALUES (?, ?, ?, 'corriendo')",
                (now, trigger, backend))
        return cur.lastrowid
    finally:
        con.close()


def finish_run(db_path, run_id, status, now, **fields):
    unknown = set(fields) - set(_RUN_FIELDS)
    if unknown:
        raise ValueError(f"Campos de corrida desconocidos: {sorted(unknown)}")
    columns = ["status = ?", "finished_at = ?"] + [f"{key} = ?" for key in fields]
    con = connect(db_path)
    try:
        with con:
            con.execute(f"UPDATE recommendation_runs SET {', '.join(columns)} WHERE id = ?",
                        (status, now, *fields.values(), run_id))
    finally:
        con.close()


def _one(db_path, sql, params=()):
    con = connect(db_path)
    try:
        row = con.execute(sql, params).fetchone()
    finally:
        con.close()
    return dict(row) if row else None


def get_run(db_path, run_id):
    return _one(db_path, "SELECT * FROM recommendation_runs WHERE id = ?", (run_id,))


def last_run(db_path):
    return _one(db_path, "SELECT * FROM recommendation_runs ORDER BY id DESC LIMIT 1")


def latest_finished_run_id(db_path):
    row = _one(db_path, "SELECT MAX(id) AS id FROM recommendation_runs WHERE finished_at IS NOT NULL")
    return row["id"] if row else None


# --- Recomendaciones ---------------------------------------------------------------

def _public(row):
    rec = dict(row)
    rec["evidence"] = json.loads(rec["evidence"])
    rec.pop("signature", None)
    return rec


def list_recommendations(db_path, status="nueva"):
    if status != "todas" and status not in STATUSES:
        raise ValueError(f"Estado desconocido: {status}")
    where, params = ("", ()) if status == "todas" else ("WHERE status = ?", (status,))
    con = connect(db_path)
    try:
        rows = con.execute(f"SELECT * FROM recommendations {where} "
                           f"ORDER BY {_IMPACT_ORDER}, tokens DESC, last_seen DESC, id", params).fetchall()
    finally:
        con.close()
    return [_public(r) for r in rows]


def set_status(db_path, rec_id, status, now):
    if status not in USER_STATUSES:
        raise ValueError(f"Estado inválido: {status}")
    con = connect(db_path)
    try:
        with con:
            cur = con.execute("UPDATE recommendations SET status = ?, status_at = ? WHERE id = ?",
                              (status, now, rec_id))
        if cur.rowcount == 0:
            return None
        return _public(con.execute("SELECT * FROM recommendations WHERE id = ?", (rec_id,)).fetchone())
    finally:
        con.close()


def _canon(signature):
    return json.dumps(signature, sort_keys=True, ensure_ascii=False)


def _new_id(rec, used):
    base = rec["kind"] + _canon(rec["signature"])
    rec_id, n = hashlib.sha1(base.encode()).hexdigest()[:16], 0
    while rec_id in used:
        n += 1
        rec_id = hashlib.sha1(f"{base}#{n}".encode()).hexdigest()[:16]
    used.add(rec_id)
    return rec_id


def _insert(con, rec, now, used):
    con.execute(
        "INSERT INTO recommendations (id, first_seen, last_seen, tool, tokens, pattern, kind, description, impact, "
        "evidence, draft, signature, status, status_at, generator) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'nueva', ?, ?)",
        (_new_id(rec, used), now, now, rec["tool"], rec["tokens"], rec["pattern"], rec["kind"],
         rec["description"], rec["impact"], json.dumps(rec["evidence"], ensure_ascii=False), rec["draft"],
         _canon(rec["signature"]), now, rec["generator"]))


def _update(con, row, rec, now, is_cost):
    if row["status"] == "saltada":
        con.execute("UPDATE recommendations SET last_seen = ? WHERE id = ?", (now, row["id"]))
        return
    sets = {"last_seen": now, "tokens": rec["tokens"], "impact": rec["impact"],
            "evidence": json.dumps(rec["evidence"], ensure_ascii=False)}
    if is_cost:
        sets.update(pattern=rec["pattern"], description=rec["description"], draft=rec["draft"], tool=rec["tool"])
        if row["status"] == "resuelta":
            sets.update(status="nueva", status_at=now)
    elif row["generator"] == "reglas" and rec["generator"] not in _NON_LLM:
        sets.update(description=rec["description"], draft=rec["draft"], generator=rec["generator"], kind=rec["kind"])
    assignments = ", ".join(f"{key} = ?" for key in sets)
    con.execute(f"UPDATE recommendations SET {assignments} WHERE id = ?", (*sets.values(), row["id"]))


def apply_run(db_path, pattern_recs, cost_recs, now):
    counts = {"created": 0, "updated": 0, "resolved": 0}
    con = connect(db_path)
    try:
        with con:
            rows = [dict(r) for r in con.execute("SELECT * FROM recommendations")]
            used = {r["id"] for r in rows}

            patterns = [r for r in rows if r["kind"] != "costo"]
            matched = set()
            for rec in pattern_recs:
                signature = set(rec["signature"])
                best, best_score = None, SAME_PATTERN_THRESHOLD
                for row in patterns:
                    if row["id"] in matched:
                        continue
                    score = jaccard(signature, set(json.loads(row["signature"])))
                    if score >= best_score and (best is None or score > best_score):
                        best, best_score = row, score
                if best is None:
                    _insert(con, rec, now, used)
                    counts["created"] += 1
                else:
                    matched.add(best["id"])
                    _update(con, best, rec, now, is_cost=False)
                    counts["updated"] += 1

            costs = {r["signature"]: r for r in rows if r["kind"] == "costo"}
            fired = set()
            for rec in cost_recs:
                key = _canon(rec["signature"])
                fired.add(key)
                if key in costs:
                    _update(con, costs[key], rec, now, is_cost=True)
                    counts["updated"] += 1
                else:
                    _insert(con, rec, now, used)
                    counts["created"] += 1
            for key, row in costs.items():
                if key not in fired and row["status"] == "nueva":
                    con.execute("UPDATE recommendations SET status = 'resuelta', status_at = ? WHERE id = ?",
                                (now, row["id"]))
                    counts["resolved"] += 1
    finally:
        con.close()
    return counts
```

Nota: la firma de costo se guarda con `_canon` (JSON con `sort_keys`), así que la comparación exacta es una igualdad de strings.

- [ ] **Paso 5: correr el test y verificar que pasa**

Run: `python3 -m unittest tests.test_recommend_store -v`
Esperado: PASS.

- [ ] **Paso 6: correr toda la suite (no romper `history`)**

Run: `python3 -m unittest discover -s tests -v 2>&1 | tail -5`
Esperado: `OK` (o solo los 2 fallos preexistentes de `test_openrouter.py` si `OPENROUTER_API_KEY` está en el entorno; en ese caso córrela con `env -u OPENROUTER_API_KEY`).

- [ ] **Paso 7: commit**

```bash
git add recommend/settings.py recommend/store.py tests/test_recommend_store.py
git commit -m "feat(recommend): configuración del motor y persistencia con firma y ciclo de vida"
```

---

### Tarea 5: Señales de costo (`briefing.build_context`, `recommend/cost.py`)

**Archivos:**
- Modificar: `briefing.py` (extraer `build_context` de `build_briefing`, alrededor de las líneas 367-396)
- Crear: `recommend/cost.py`
- Test: `tests/test_recommend_cost.py` y un test nuevo en `tests/test_briefing.py`

**Interfaces:**
- Consume: `briefing.rows_for_source`, `month_of`, `month_window`, `in_range`, `sum_tokens`, `PROJECT_SOURCES`, `SOURCE_LABELS` y `rule_spike_day` / `rule_project_concentration` / `rule_subscription_missing` (ya existen).
- Produce:
  - `briefing.build_context(project_rows, model_rows, settings, today, source="all") -> dict` con las claves `source`, `today`, `window`, `rows`, `window_rows`, `project_rows`, `model_rows` y `settings` (las mismas que hoy arma `build_briefing` en línea).
  - `cost.PERSISTED_RULES`, `cost.IMPACT = {"warning": "alto", "info": "medio"}`.
  - `cost.project_from_link(link) -> str | None`.
  - `cost.cost_recommendations(project_rows, model_rows, settings, today) -> list[dict]`, con la forma de entrada a `store.apply_run`:
    - `kind="costo"`, `generator="costo"`;
    - `signature={"rule", "source", "project"}`;
    - `evidence={"rule", "items", "link", "projects", "sources"}`.

- [ ] **Paso 1: escribir los tests que fallan**

```python
# tests/test_recommend_cost.py
import unittest
from datetime import date

from recommend import cost

TODAY = date(2026, 9, 20)
APP = "/home/u/DEV/ACME/app"
OTHER = "/home/u/DEV/OTRO/x"


def row(day, source="claude_code", project=APP, tokens=1000, cost_usd=1.0):
    return {"date": day, "source": source, "project": project, "tokens": tokens, "cost": cost_usd}


class TestCost(unittest.TestCase):
    def test_project_from_link(self):
        self.assertEqual(cost.project_from_link("/proyectos/ACME?proyecto=%2Fhome%2Fu%2FDEV%2FACME%2Fapp"), APP)
        self.assertIsNone(cost.project_from_link("/configuracion"))

    def test_concentration_and_spike_become_cost_recommendations(self):
        rows = [row(f"2026-09-{d:02d}") for d in range(1, 8)] + [row("2026-09-08", cost_usd=20.0)]
        rows += [row("2026-09-02", project=OTHER, cost_usd=0.5)]
        recs = cost.cost_recommendations(rows, [], {"subscription_cost_claude": 20}, TODAY)
        by_rule = {r["signature"]["rule"]: r for r in recs}
        self.assertEqual(set(by_rule), {"spike_day", "project_concentration"})

        spike = by_rule["spike_day"]
        self.assertEqual((spike["kind"], spike["impact"], spike["generator"], spike["tool"]),
                         ("costo", "alto", "costo", "claude_code"))
        self.assertEqual(spike["signature"], {"rule": "spike_day", "source": "claude_code", "project": None})
        self.assertEqual(spike["evidence"]["link"], "/actividad?dia=2026-09-08")
        self.assertEqual(spike["evidence"]["sources"], ["claude_code"])
        self.assertEqual(spike["tokens"], 9000)

        conc = by_rule["project_concentration"]
        self.assertEqual(conc["impact"], "medio")
        self.assertEqual(conc["signature"]["project"], APP)
        self.assertEqual(conc["evidence"]["projects"], [APP])
        self.assertIn("app", conc["draft"])
        for rec in recs:
            self.assertLessEqual(len(rec["pattern"]), 120)
            self.assertLessEqual(len(rec["description"]), 400)
            self.assertTrue(rec["draft"])

    def test_informative_rules_are_not_persisted(self):
        rows = [row(f"2026-09-{d:02d}", cost_usd=None) for d in range(1, 4)]
        recs = cost.cost_recommendations(rows, [], {}, TODAY)
        self.assertNotIn("cost_incomplete", {r["signature"]["rule"] for r in recs})

    def test_subscription_missing_per_source(self):
        rows = [row(f"2026-09-{d:02d}", source="codex", project=APP, cost_usd=0.1) for d in range(1, 5)]
        rows += [row(f"2026-09-{d:02d}", source="codex", project=OTHER, cost_usd=0.1) for d in range(1, 5)]
        recs = cost.cost_recommendations(rows, [], {}, TODAY)
        subs = [r for r in recs if r["signature"]["rule"] == "subscription_missing"]
        self.assertEqual([r["signature"]["source"] for r in subs], ["codex"])
        self.assertEqual(subs[0]["evidence"]["link"], "/configuracion")

    def test_no_rows_no_recommendations(self):
        self.assertEqual(cost.cost_recommendations([], [], {}, TODAY), [])
```

Añade a `tests/test_briefing.py`, dentro de una clase nueva al final del archivo:

```python
class TestBuildContext(unittest.TestCase):
    def test_build_context_filters_source_and_window(self):
        from datetime import date
        rows = [{"date": "2026-09-01", "source": "codex", "project": "/p", "tokens": 5, "cost": 1.0},
                {"date": "2026-08-01", "source": "codex", "project": "/p", "tokens": 7, "cost": 1.0},
                {"date": "2026-09-01", "source": "claude_code", "project": "/p", "tokens": 9, "cost": 1.0}]
        ctx = briefing.build_context(rows, [], {}, date(2026, 9, 20), source="codex")
        self.assertEqual(ctx["window"], ("2026-09-01", "2026-09-20"))
        self.assertEqual([r["tokens"] for r in ctx["rows"]], [5, 7])
        self.assertEqual([r["tokens"] for r in ctx["window_rows"]], [5])
        self.assertEqual(set(ctx), {"source", "today", "window", "rows", "window_rows",
                                    "project_rows", "model_rows", "settings"})
```

Antes de pegarlo, confirma con `grep -n "def month_window" -A 6 briefing.py` que `month_window` devuelve una tupla `(inicio, fin)`. Si devuelve una lista, ajusta la expectativa a lista.

- [ ] **Paso 2: correr los tests y verificar que fallan**

Run: `python3 -m unittest tests.test_recommend_cost tests.test_briefing -v 2>&1 | tail -15`
Esperado: FAIL con `ImportError: cannot import name 'cost'` y `AttributeError: module 'briefing' has no attribute 'build_context'`.

- [ ] **Paso 3: extraer `build_context` en `briefing.py`**

Añade antes de `def build_briefing(`:

```python
def build_context(project_rows, model_rows, settings, today, source="all"):
    """Contexto que consumen las RULES: lo usan el briefing y el motor de
    recomendaciones (recommend/cost.py), que lo evalúa por fuente."""
    rows = rows_for_source(source, project_rows, model_rows)
    window = month_window(month_of(today), today.day)
    return {"source": source, "today": today, "window": window, "rows": rows,
            "window_rows": in_range(rows, *window), "project_rows": project_rows,
            "model_rows": model_rows, "settings": settings}
```

En `build_briefing`, reemplaza estas líneas:

```python
    rows = rows_for_source(source, project_rows, model_rows)
```

por:

```python
    ctx = build_context(project_rows, model_rows, settings, today, source)
    rows = ctx["rows"]
```

reemplaza:

```python
    window = month_window(current, today.day)
    compare_window = month_window(compare_month, today.day)
    window_rows = in_range(rows, *window)
```

por:

```python
    window, window_rows = ctx["window"], ctx["window_rows"]
    compare_window = month_window(compare_month, today.day)
```

y borra el bloque `ctx = {"source": source, ...}` que hoy está antes del `return`.

- [ ] **Paso 4: implementar `recommend/cost.py`**

```python
# recommend/cost.py
"""Señales de costo persistidas como recomendaciones kind=costo (spec §3.4).
Reutiliza las RULES del briefing por fuente; el draft es texto determinista,
nunca pasa por el LLM."""
from urllib.parse import parse_qs, urlparse

import briefing

PERSISTED_RULES = (briefing.rule_spike_day, briefing.rule_project_concentration,
                   briefing.rule_subscription_missing)
IMPACT = {"warning": "alto", "info": "medio"}


def project_from_link(link):
    values = parse_qs(urlparse(link or "").query).get("proyecto")
    return values[0] if values else None


def _draft(signal, source, project):
    label = briefing.SOURCE_LABELS[source]
    if signal["id"] == "spike_day":
        return (f"Revisa el día marcado en {label} ({signal['link']} en el dashboard):\n"
                "1. Ordena las sesiones de ese día por costo y abre la más cara.\n"
                "2. Decide si fue un uso puntual o algo repetible (contexto muy largo, reintentos en bucle, "
                "modelo más caro de lo necesario).\n"
                "3. Si es repetible, fija una pauta: /compact antes de tareas largas o un modelo más barato "
                "para lo rutinario.")
    if signal["id"] == "project_concentration":
        name = project.rstrip("/").split("/")[-1] if project else "el proyecto"
        return (f"{name} concentra la mayor parte del gasto de {label} este mes. Opciones:\n"
                "1. Revisa sus sesiones más largas y qué contexto cargan en cada turno.\n"
                "2. Recorta el CLAUDE.md/AGENTS.md del proyecto a lo imprescindible.\n"
                "3. Usa un modelo más barato para tareas rutinarias de ese proyecto.")
    return ("Abre Configuración → ROI e indica el costo mensual y la fecha de inicio de tu plan "
            f"de {label}. Con eso el dashboard compara suscripción frente a precio de API.")


def cost_recommendations(project_rows, model_rows, settings, today):
    out = []
    for source in briefing.PROJECT_SOURCES:
        ctx = briefing.build_context(project_rows, model_rows, settings, today, source)
        for rule in PERSISTED_RULES:
            signal = rule(ctx)
            if not signal:
                continue
            project = project_from_link(signal["link"])
            out.append({
                "tool": source,
                "tokens": briefing.sum_tokens(ctx["window_rows"]),
                "pattern": signal["title"][:120],
                "kind": "costo",
                "description": " · ".join(signal["evidence"])[:400],
                "impact": IMPACT.get(signal["severity"], "medio"),
                "evidence": {"rule": signal["id"], "items": signal["evidence"], "link": signal["link"],
                             "projects": [project] if project else [], "sources": [source]},
                "draft": _draft(signal, source, project),
                "signature": {"rule": signal["id"], "source": source, "project": project},
                "generator": "costo",
            })
    return out
```

- [ ] **Paso 5: correr los tests y verificar que pasan**

Run: `python3 -m unittest tests.test_recommend_cost tests.test_briefing -v 2>&1 | tail -5`
Esperado: `OK`. Todos los tests previos de `test_briefing.py` deben seguir pasando: son la red de seguridad del refactor. Si `test_concentration_and_spike_become_cost_recommendations` no dispara `spike_day`, revisa `SPIKE_MIN_ACTIVE_DAYS` (5) y `SPIKE_FACTOR` (2,5) y corrige el fixture, no las constantes.

- [ ] **Paso 6: commit**

```bash
git add briefing.py recommend/cost.py tests/test_recommend_cost.py tests/test_briefing.py
git commit -m "feat(recommend): señales de costo desde las RULES del briefing"
```

---

---

### Tarea 6: Heurística local (`recommend/heuristics.py`)

**Archivos:**
- Crear: `recommend/heuristics.py`
- Test: `tests/test_recommend_heuristics.py`

**Interfaces:**
- Consume: `recommend.cluster.Cluster` (con `features`, `pattern`, `evidence()`, `snippets()`, `common_steps()`) y `recommend.cluster.normalize` (Tarea 3); `recommend.redact.redact` (Tarea 1).
- Produce:
  - `classify(features: dict) -> str`: devuelve `"plugin"`, `"skill"` o `"prompt"`.
  - `recommend(cluster) -> {"kind", "pattern", "description", "draft", "generator": "reglas"}`, con los recortes 120/400/8000 ya aplicados.

- [ ] **Paso 1: escribir el test que falla**

```python
# tests/test_recommend_heuristics.py
import unittest

from recommend import cluster, heuristics
from recommend.prompts import Prompt

LOG = "Traceback (most recent call last):\n  File \"x.py\", line 1\nValueError: boom"


def p(text, session, day="2026-09-20"):
    return Prompt("claude_code", "/home/u/DEV/ACME/app", session, day, text)


def build(texts):
    return cluster._build("c1", [p(t, f"s{i}", f"2026-09-2{i % 3}") for i, t in enumerate(texts)], {})


class TestClassify(unittest.TestCase):
    def test_rules(self):
        f = lambda **kw: {"pega_datos": False, "menciona_servicio": [], "mismos_pasos": False, **kw}
        self.assertEqual(heuristics.classify(f(pega_datos=True, menciona_servicio=["jira"])), "plugin")
        self.assertEqual(heuristics.classify(f(menciona_servicio=["jira"])), "prompt")
        self.assertEqual(heuristics.classify(f(mismos_pasos=True)), "skill")
        self.assertEqual(heuristics.classify(f(pega_datos=True)), "prompt")
        self.assertEqual(heuristics.classify(f()), "prompt")
        self.assertEqual(heuristics.classify(f(pega_datos=True, menciona_servicio=["jira"], mismos_pasos=True)),
                         "plugin")


class TestRecommend(unittest.TestCase):
    def test_skill_has_frontmatter_and_steps(self):
        rec = heuristics.recommend(build(["revisa y corrige y luego ejecuta los tests del módulo de pagos"] * 3))
        self.assertEqual((rec["kind"], rec["generator"]), ("skill", "reglas"))
        self.assertTrue(rec["draft"].startswith("---\nname: revisa-corrige-luego-ejecuta-tests\n"))
        self.assertIn("1. Revisa", rec["draft"])
        self.assertIn("3. Ejecuta", rec["draft"])
        self.assertIn("3 sesiones", rec["description"])

    def test_plugin_names_the_service(self):
        rec = heuristics.recommend(build(["mira este error de sentry y arréglalo: " + LOG] * 3))
        self.assertEqual(rec["kind"], "plugin")
        self.assertIn("claude mcp add sentry", rec["draft"])
        self.assertIn("sentry", rec["description"])

    def test_prompt_quotes_snippets(self):
        text = "explícame cómo funciona el patrón repositorio en esta aplicación hexagonal"
        rec = heuristics.recommend(build([text] * 3))
        self.assertEqual(rec["kind"], "prompt")
        self.assertIn("CLAUDE.md", rec["draft"])
        self.assertIn(f"- {text}", rec["draft"])

    def test_limits_and_redaction(self):
        rec = heuristics.recommend(build(["escribe a ana@acme.com sobre " + "palabra " * 700] * 3))
        self.assertLessEqual(len(rec["pattern"]), 120)
        self.assertLessEqual(len(rec["description"]), 400)
        self.assertLessEqual(len(rec["draft"]), 8000)
        self.assertNotIn("ana@acme.com", rec["draft"])
```

- [ ] **Paso 2: correr el test y verificar que falla**

Run: `python3 -m unittest tests.test_recommend_heuristics -v`
Esperado: FAIL con `ImportError: cannot import name 'heuristics' from 'recommend'`.

- [ ] **Paso 3: implementar**

```python
# recommend/heuristics.py
"""Recomendación local sin LLM (spec §3.6). generator = "reglas". Las
corridas siguientes con LLM enriquecen estos registros (store.apply_run)."""
from recommend.cluster import normalize
from recommend.redact import redact

LIMITS = {"pattern": 120, "description": 400, "draft": 8000}
_SLUG_WORDS = 5


def classify(features):
    if features.get("menciona_servicio") and features.get("pega_datos"):
        return "plugin"
    if features.get("mismos_pasos"):
        return "skill"
    return "prompt"


def _slug(pattern):
    words = normalize(pattern)[:_SLUG_WORDS]
    return "-".join(words) if words else "patron-repetido"


def _summary(ev):
    return f"Se repite en {ev['sessions']} sesiones durante {ev['days']} días ({ev['tokens']:,} tokens)".replace(",", ".")


def _skill(c, ev):
    steps = c.common_steps()
    lines = [f"{i}. {step.capitalize()} …" for i, step in enumerate(steps, start=1)] or \
            ["1. Describe aquí el primer paso que repites."]
    description = f"{_summary(ev)} y sigue siempre los mismos pasos. Una skill los deja escritos una sola vez."
    draft = (f"---\nname: {_slug(c.pattern)}\n"
             f"description: Úsala cuando pidas algo como \"{c.pattern[:80]}\".\n---\n\n"
             f"# {c.pattern}\n\nPasos:\n" + "\n".join(lines) + "\n")
    return description, draft


def _plugin(c, ev):
    svc = c.features["menciona_servicio"][0]
    description = (f"{_summary(ev)}. Pegas a mano datos de {svc}; un servidor MCP de {svc} "
                   "los traería directamente a la sesión.")
    draft = (f"# Conectar {svc} por MCP\n\n"
             f"1. Busca el servidor MCP oficial (o uno mantenido por la comunidad) para {svc}.\n"
             "2. Regístralo en Claude Code:\n\n"
             f"   claude mcp add {svc} -- <comando del servidor MCP de {svc}>\n\n"
             f"3. En vez de pegar el contenido, pide: \"consulta en {svc} …\".\n")
    return description, draft


def _prompt(c, ev):
    reason = ("Pegas datos a mano (logs, trazas o JSON) con las mismas indicaciones"
              if c.features.get("pega_datos") else "Repites las mismas indicaciones")
    description = f"{_summary(ev)}. {reason}; guárdalas en CLAUDE.md o AGENTS.md para no escribirlas cada vez."
    examples = "\n".join(f"- {s.splitlines()[0]}" for s in c.snippets())
    draft = (f"## {c.pattern}\n\n"
             "Cuando te pida algo como lo siguiente, aplica siempre estas pautas sin que tenga que repetirlas:\n\n"
             "- (escribe aquí las pautas que hoy repites en cada prompt)\n\n"
             f"Ejemplos de cómo lo pido:\n{examples}\n")
    return description, draft


_BUILDERS = {"skill": _skill, "plugin": _plugin, "prompt": _prompt}


def recommend(c):
    kind = classify(c.features)
    ev = c.evidence()
    description, draft = _BUILDERS[kind](c, ev)
    return {
        "kind": kind,
        "pattern": redact(c.pattern)[:LIMITS["pattern"]],
        "description": redact(description)[:LIMITS["description"]],
        "draft": redact(draft)[:LIMITS["draft"]],
        "generator": "reglas",
    }
```

- [ ] **Paso 4: correr el test y verificar que pasa**

Run: `python3 -m unittest tests.test_recommend_heuristics -v`
Esperado: PASS. Si el slug esperado no coincide porque `normalize` quita otra palabra, revisa `STOPWORDS` (Tarea 3): "y" y "los" deben ser stopwords, y "luego" no.

- [ ] **Paso 5: commit**

```bash
git add recommend/heuristics.py tests/test_recommend_heuristics.py
git commit -m "feat(recommend): heurística local para clasificar y redactar sin LLM"
```

---

### Tarea 7: Capa LLM (`recommend/llm.py`)

**Archivos:**
- Crear: `recommend/llm.py`
- Test: `tests/test_recommend_llm.py`

**Interfaces:**
- Consume: `recommend.cluster.Cluster` (Tarea 3), `recommend.redact.redact` (Tarea 1) y `recommend.settings.is_free` / `parse_entry` (Tarea 4).
- Produce:
  - `KINDS = ("skill", "plugin", "prompt")`, `TIMEOUT_SECONDS = 120`, `LIMITS = {"pattern": 120, "description": 400, "draft": 8000}`, `AttemptError(Exception)`.
  - `candidate_payload(cluster) -> dict` y `build_prompt(candidates) -> str`.
  - `extract_json(text) -> dict` (lanza `ValueError`) y `check_schema(data)` (lanza `ValueError`).
  - `validate_groups(data, ids: list[str]) -> dict[str, list[str]]`: `group_id` → ids de candidatos. Todo candidato queda en exactamente un grupo.
  - `validate_recommendations(data, group_ids) -> dict[str, dict]`: `group_id` → `{"kind", "pattern", "description", "draft"}`, ya redactado y recortado.
  - `subprocess_runner(args, cwd, timeout) -> (returncode, stdout, stderr)` (puede lanzar `subprocess.TimeoutExpired` u `OSError`).
  - `run_llm(candidates, backend, chain, runner=subprocess_runner, cwd=".") -> dict` con las claves `ok`, `data`, `model`, `attempts`, `errors` (lista de `"<entrada>: <motivo>"`), `llm_tokens` y `llm_cost`. `model` es la entrada de la cadena (`"nous:…"`) o `"claude"`.

- [ ] **Paso 1: escribir el test que falla**

```python
# tests/test_recommend_llm.py
import json
import os
import subprocess
import tempfile
import unittest

from recommend import cluster, llm
from recommend.prompts import Prompt

CHAIN = ["nous:stealth/space-bunny-alpha", "nous:upstage/solar-pro4:free", "nous:inclusionai/ling:free"]
GOOD = {"groups": [{"group_id": "g1", "members": ["c1", "c2"]}],
        "recommendations": [{"group_id": "g1", "kind": "skill", "pattern": "Diagnosticar cobros",
                             "description": "Se repite", "draft": "---\nname: cobros\n---"}]}


def p(text, session):
    return Prompt("claude_code", "/home/u/DEV/ACME/app", session, "2026-09-20", text)


def cands():
    return [cluster._build("c1", [p("revisa los logs del servicio de pagos", "s1"),
                                  p("revisa los logs del servicio de pagos", "s2")], {}),
            cluster._build("c2", [p("mira las trazas del módulo de cobros", "s3"),
                                  p("mira las trazas del módulo de cobros", "s4")], {})]


class FakeRunner:
    """Cada llamada consume un comportamiento: dict → respuesta Hermes con
    usage-file; ("rc", código); ("timeout",); ("raw", stdout, usage|None)."""

    def __init__(self, *behaviours):
        self.behaviours = list(behaviours)
        self.calls = []

    def __call__(self, args, cwd, timeout):
        self.calls.append(args)
        behaviour = self.behaviours.pop(0)
        usage_path = args[args.index("--usage-file") + 1] if "--usage-file" in args else None
        if isinstance(behaviour, dict):
            behaviour = ("raw", json.dumps(behaviour), {"total_tokens": 900, "estimated_cost_usd": 0.0})
        if behaviour[0] == "timeout":
            raise subprocess.TimeoutExpired(args, timeout)
        if behaviour[0] == "rc":
            return behaviour[1], "", "fallo del proveedor"
        _, stdout, usage = behaviour
        if usage is not None and usage_path:
            with open(usage_path, "w") as fh:
                json.dump(usage, fh)
        return 0, stdout, ""


class TestParsing(unittest.TestCase):
    def test_extract_json_tolerates_fences_and_prose(self):
        text = "Claro, aquí va:\n```json\n" + json.dumps(GOOD) + "\n```\nEspero que sirva."
        self.assertEqual(llm.extract_json(text), GOOD)

    def test_extract_json_rejects_garbage(self):
        for bad in ("sin json", "{roto", "[1, 2]", "", None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                llm.extract_json(bad)

    def test_check_schema(self):
        llm.check_schema(GOOD)
        for bad in ({}, {"groups": [], "recommendations": {}}, {"groups": "x", "recommendations": []}):
            with self.assertRaises(ValueError):
                llm.check_schema(bad)


class TestValidateGroups(unittest.TestCase):
    def test_valid_groups_and_orphans(self):
        groups = llm.validate_groups({"groups": [{"group_id": "g1", "members": ["c1", "c3"]}]}, ["c1", "c2", "c3"])
        self.assertEqual(groups, {"g1": ["c1", "c3"], "c2": ["c2"]})

    def test_unknown_member_discards_whole_group(self):
        groups = llm.validate_groups({"groups": [{"group_id": "g1", "members": ["c1", "c9"]}]}, ["c1", "c2"])
        self.assertEqual(groups, {"c1": ["c1"], "c2": ["c2"]})

    def test_repeated_candidate_first_claim_wins(self):
        data = {"groups": [{"group_id": "g1", "members": ["c1", "c2"]},
                           {"group_id": "g2", "members": ["c2", "c3"]},
                           {"group_id": "g3", "members": ["c3", "c3"]}]}
        self.assertEqual(llm.validate_groups(data, ["c1", "c2", "c3"]), {"g1": ["c1", "c2"], "c3": ["c3"]})

    def test_malformed_entries_and_orphan_id_collision(self):
        data = {"groups": ["x", {"group_id": 5, "members": ["c1"]}, {"group_id": "c2", "members": []},
                           {"group_id": "c2", "members": ["c1"]}]}
        self.assertEqual(llm.validate_groups(data, ["c1", "c2"]), {"c2": ["c1"], "c2-solo": ["c2"]})


class TestValidateRecommendations(unittest.TestCase):
    def test_filters_trims_and_redacts(self):
        data = {"recommendations": [
            {"group_id": "g1", "kind": "skill", "pattern": "p" * 300, "description": "d" * 900,
             "draft": "escribe a ana@acme.com\n" + "x" * 9000},
            {"group_id": "g1", "kind": "prompt", "pattern": "duplicado", "description": "d", "draft": "d"},
            {"group_id": "g9", "kind": "skill", "pattern": "p", "description": "d", "draft": "d"},
            {"group_id": "g2", "kind": "agente", "pattern": "p", "description": "d", "draft": "d"},
            {"group_id": "g3", "kind": "prompt", "pattern": "p", "description": "   ", "draft": "d"},
            {"group_id": ["g4"], "kind": "prompt", "pattern": "p", "description": "d", "draft": "d"},
            "basura",
        ]}
        recs = llm.validate_recommendations(data, {"g1", "g2", "g3"})
        self.assertEqual(list(recs), ["g1"])
        rec = recs["g1"]
        self.assertEqual((rec["kind"], len(rec["pattern"]), len(rec["description"]), len(rec["draft"])),
                         ("skill", 120, 400, 8000))
        self.assertNotIn("ana@acme.com", rec["draft"])


class TestPrompt(unittest.TestCase):
    def test_prompt_only_carries_summaries(self):
        long_text = "revisa los logs del servicio de pagos " + "detalle " * 80
        c = cluster._build("c1", [p(long_text, "s1"), p(long_text, "s2")], {})
        payload = llm.candidate_payload(c)
        self.assertEqual(set(payload), {"id", "pattern", "sessions", "days", "tokens", "features", "snippets"})
        prompt = llm.build_prompt([c])
        self.assertIn('"id": "c1"', prompt)
        self.assertIn('"groups"', prompt)
        self.assertNotIn(long_text.strip(), prompt)


class TestRunLlm(unittest.TestCase):
    def setUp(self):
        self.cwd = tempfile.mkdtemp()

    def run_chain(self, runner, chain=CHAIN, backend="hermes"):
        return llm.run_llm(cands(), backend, chain, runner=runner, cwd=self.cwd)

    def test_hermes_success_first_model(self):
        runner = FakeRunner(GOOD)
        result = self.run_chain(runner)
        self.assertTrue(result["ok"])
        self.assertEqual((result["model"], result["attempts"], result["llm_tokens"], result["llm_cost"]),
                         (CHAIN[0], 1, 900, 0.0))
        args = runner.calls[0]
        self.assertEqual(args[:2], ["hermes", "-z"])
        self.assertEqual(args[3:9], ["--provider", "nous", "-m", "stealth/space-bunny-alpha",
                                     "--ignore-rules", "--safe-mode"])
        self.assertEqual(os.listdir(self.cwd), [])  # el usage-file temporal se borra

    def test_fallback_through_chain(self):
        runner = FakeRunner(("rc", 1), ("timeout",), GOOD)
        result = self.run_chain(runner)
        self.assertTrue(result["ok"])
        self.assertEqual((result["model"], result["attempts"]), (CHAIN[2], 3))
        self.assertEqual(len(result["errors"]), 2)
        self.assertTrue(result["errors"][0].startswith(CHAIN[0] + ": "))
        self.assertIn("timeout", result["errors"][1])

    def test_invalid_json_and_cost_fall_through(self):
        runner = FakeRunner(("raw", "no es json", {"total_tokens": 5, "estimated_cost_usd": 0}),
                            ("raw", json.dumps(GOOD), {"total_tokens": 5, "estimated_cost_usd": 0.01}),
                            ("raw", json.dumps({"groups": {}}), {"total_tokens": 5}))
        result = self.run_chain(runner)
        self.assertFalse(result["ok"])
        self.assertIsNone(result["data"])
        self.assertEqual(result["attempts"], 3)
        self.assertIn("costo", result["errors"][1])

    def test_hermes_missing_usage_or_failed_is_attempt_failure(self):
        runner = FakeRunner(("raw", json.dumps(GOOD), None),
                            ("raw", json.dumps(GOOD), {"failed": True, "estimated_cost_usd": 0}),
                            GOOD)
        result = self.run_chain(runner)
        self.assertEqual((result["ok"], result["model"], result["attempts"]), (True, CHAIN[2], 3))
        self.assertIn("usage-file", result["errors"][0])
        self.assertIn("failed", result["errors"][1])

    def test_non_free_model_is_rejected_without_running(self):
        runner = FakeRunner(GOOD)
        result = self.run_chain(runner, chain=["nous:anthropic/claude-sonnet", CHAIN[0]])
        self.assertEqual((result["ok"], result["model"], result["attempts"]), (True, CHAIN[0], 2))
        self.assertEqual(len(runner.calls), 1)
        self.assertIn("free", result["errors"][0])

    def test_claude_backend_single_attempt(self):
        envelope = {"type": "result", "is_error": False, "result": "```json\n" + json.dumps(GOOD) + "\n```",
                    "total_cost_usd": 0.12,
                    "usage": {"input_tokens": 10, "output_tokens": 20, "cache_read_input_tokens": 30,
                              "cache_creation_input_tokens": 40}}
        runner = FakeRunner(("raw", json.dumps(envelope), None))
        result = self.run_chain(runner, backend="claude")
        self.assertEqual((result["ok"], result["model"], result["attempts"], result["llm_tokens"], result["llm_cost"]),
                         (True, "claude", 1, 100, 0.12))
        self.assertEqual(runner.calls[0], ["claude", "-p", runner.calls[0][2], "--output-format", "json"])

    def test_claude_backend_error_does_not_retry(self):
        runner = FakeRunner(("raw", json.dumps({"is_error": True, "result": "límite"}), None))
        result = self.run_chain(runner, backend="claude")
        self.assertEqual((result["ok"], result["attempts"], len(runner.calls)), (False, 1, 1))
```

- [ ] **Paso 2: correr el test y verificar que falla**

Run: `python3 -m unittest tests.test_recommend_llm -v`
Esperado: FAIL con `ImportError: cannot import name 'llm' from 'recommend'`.

- [ ] **Paso 3: implementar**

```python
# recommend/llm.py
"""Capa LLM (spec §3.5): una sola llamada por corrida que agrupa candidatos
por significado y redacta una recomendación por grupo. Todo lo que devuelve
el modelo es dato no confiable: se valida, se redacta y se recorta aquí."""
import json
import os
import subprocess
import tempfile

from recommend.redact import redact
from recommend.settings import is_free, parse_entry

KINDS = ("skill", "plugin", "prompt")
TIMEOUT_SECONDS = 120
LIMITS = {"pattern": 120, "description": 400, "draft": 8000}

INSTRUCTIONS = """Eres un asistente que analiza patrones repetidos en los prompts de un desarrollador.
Recibes una lista JSON de candidatos. Cada uno resume prompts parecidos: id, patrón, sesiones, días,
tokens, features y hasta 3 fragmentos (ya anonimizados).

Haz dos cosas:
1. Agrupa los candidatos que expresan la MISMA intención aunque usen palabras distintas. Un candidato
   solo puede estar en un grupo. Los que no se parecen a ningún otro pueden quedar fuera.
2. Para cada grupo, clasifica y redacta UNA recomendación:
   - "skill": el usuario repite los mismos pasos; propón un SKILL.md con frontmatter (name, description) y pasos.
   - "plugin": el usuario pega a mano datos de un servicio externo; propón conectar un servidor MCP.
   - "prompt": el usuario repite instrucciones; propón una sección para CLAUDE.md o AGENTS.md.

No calcules cifras: sesiones, tokens e impacto se calculan aparte. Escribe en español.
Responde SOLO con un objeto JSON con esta forma exacta, sin texto adicional:
{"groups":[{"group_id":"g1","members":["c3","c7"]}],
 "recommendations":[{"group_id":"g1","kind":"skill|plugin|prompt","pattern":"título corto",
                     "description":"por qué conviene (máx. 400 caracteres)","draft":"borrador listo para copiar"}]}"""


class AttemptError(Exception):
    """Un intento falló; run_llm pasa al siguiente modelo de la cadena."""


def candidate_payload(c):
    ev = c.evidence()
    return {"id": c.cluster_id, "pattern": c.pattern, "sessions": ev["sessions"], "days": ev["days"],
            "tokens": ev["tokens"], "features": c.features, "snippets": ev["snippets"]}


def build_prompt(candidates):
    payload = json.dumps([candidate_payload(c) for c in candidates], ensure_ascii=False, indent=1)
    return f"{INSTRUCTIONS}\n\nCandidatos:\n{payload}\n"


def extract_json(text):
    """Del primer '{' al último '}': tolera prosa y cercas ```json alrededor."""
    if not isinstance(text, str):
        raise ValueError("La respuesta no es texto")
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("La respuesta no contiene un objeto JSON")
    data = json.loads(text[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("La respuesta no es un objeto JSON")
    return data


def check_schema(data):
    if not isinstance(data.get("groups"), list) or not isinstance(data.get("recommendations"), list):
        raise ValueError("La respuesta no tiene groups y recommendations como listas")


def validate_groups(data, ids):
    known, claimed, groups = set(ids), set(), {}
    for group in data.get("groups", []):
        if not isinstance(group, dict):
            continue
        gid, members = group.get("group_id"), group.get("members")
        if not isinstance(gid, str) or not gid or gid in groups or not isinstance(members, list) or not members:
            continue
        if len(set(map(str, members))) != len(members):
            continue
        if any(not isinstance(m, str) or m not in known or m in claimed for m in members):
            continue
        claimed.update(members)
        groups[gid] = list(members)
    for cid in ids:
        if cid not in claimed:
            groups[cid if cid not in groups else f"{cid}-solo"] = [cid]
    return groups


def _clean(value, limit):
    if not isinstance(value, str) or not value.strip():
        return None
    return redact(value.strip())[:limit]


def validate_recommendations(data, group_ids):
    out = {}
    for rec in data.get("recommendations", []):
        if not isinstance(rec, dict):
            continue
        gid = rec.get("group_id")
        if not isinstance(gid, str) or gid not in group_ids or gid in out or rec.get("kind") not in KINDS:
            continue
        fields = {key: _clean(rec.get(key), limit) for key, limit in LIMITS.items()}
        if None in fields.values():
            continue
        out[gid] = {"kind": rec["kind"], **fields}
    return out


def subprocess_runner(args, cwd, timeout):
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def _call(runner, args, cwd):
    try:
        code, stdout, stderr = runner(args, cwd, TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        raise AttemptError(f"timeout de {TIMEOUT_SECONDS} s") from None
    except OSError as exc:
        raise AttemptError(f"no se pudo ejecutar: {exc}") from None
    if code != 0:
        raise AttemptError(f"salió con código {code}: {(stderr or '').strip()[:200]}")
    return stdout


def _parse(text):
    try:
        data = extract_json(text)
        check_schema(data)
    except ValueError as exc:
        raise AttemptError(f"JSON inválido: {exc}") from None
    return data


def _hermes_attempt(prompt, entry, runner, cwd):
    try:
        provider, model = parse_entry(entry)
    except ValueError as exc:
        raise AttemptError(str(exc)) from None
    if not is_free(model):
        raise AttemptError("con Hermes solo se permiten modelos free")
    fd, usage_path = tempfile.mkstemp(prefix="usage-", suffix=".json", dir=cwd)
    os.close(fd)
    os.unlink(usage_path)  # Hermes lo crea; si no aparece, el intento falla
    try:
        stdout = _call(runner, ["hermes", "-z", prompt, "--provider", provider, "-m", model,
                                "--ignore-rules", "--safe-mode", "--usage-file", usage_path], cwd)
        try:
            with open(usage_path) as fh:
                usage = json.load(fh)
        except (OSError, ValueError):
            raise AttemptError("Hermes no escribió el usage-file") from None
        if not isinstance(usage, dict) or usage.get("failed"):
            raise AttemptError("Hermes reportó failed en el usage-file")
        try:
            cost = float(usage.get("estimated_cost_usd") or 0)
            tokens = int(usage.get("total_tokens") or 0)
        except (TypeError, ValueError):
            raise AttemptError("usage-file con valores no numéricos") from None
        if cost > 0:
            raise AttemptError(f"costo {cost} > 0 con un modelo que debía ser free")
        return _parse(stdout), tokens, cost
    finally:
        if os.path.exists(usage_path):
            os.unlink(usage_path)


def _claude_attempt(prompt, runner, cwd):
    stdout = _call(runner, ["claude", "-p", prompt, "--output-format", "json"], cwd)
    try:
        envelope = json.loads(stdout)
    except ValueError:
        raise AttemptError("salida de claude -p no es JSON") from None
    if not isinstance(envelope, dict) or envelope.get("is_error"):
        raise AttemptError(f"claude -p devolvió error: {str(envelope.get('result', ''))[:200]}"
                           if isinstance(envelope, dict) else "salida de claude -p inesperada")
    usage = envelope.get("usage") or {}
    tokens = sum(int(usage.get(key) or 0) for key in
                 ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    return _parse(envelope.get("result")), tokens, float(envelope.get("total_cost_usd") or 0)


def run_llm(candidates, backend, chain, runner=subprocess_runner, cwd="."):
    prompt = build_prompt(candidates)
    result = {"ok": False, "data": None, "model": None, "attempts": 0, "errors": [],
              "llm_tokens": 0, "llm_cost": 0.0}
    plan = [(entry, lambda e=entry: _hermes_attempt(prompt, e, runner, cwd)) for entry in chain] \
        if backend == "hermes" else [("claude", lambda: _claude_attempt(prompt, runner, cwd))]
    for label, attempt in plan:
        result["attempts"] += 1
        try:
            data, tokens, cost = attempt()
        except AttemptError as exc:
            result["errors"].append(f"{label}: {exc}")
            continue
        result.update(ok=True, data=data, model=label, llm_tokens=tokens, llm_cost=cost)
        break
    return result
```

- [ ] **Paso 4: correr el test y verificar que pasa**

Run: `python3 -m unittest tests.test_recommend_llm -v`
Esperado: PASS.

- [ ] **Paso 5: commit**

```bash
git add recommend/llm.py tests/test_recommend_llm.py
git commit -m "feat(recommend): capa LLM con Hermes free, claude -p, cadena de respaldo y validación"
```

---

### Tarea 8: Orquestador con lock y CLI (`recommend/engine.py`, `recommend/__main__.py`)

**Archivos:**
- Crear: `recommend/engine.py`, `recommend/__main__.py`
- Test: `tests/test_recommend_engine.py`

**Interfaces:**
- Consume:
  - Tarea 2: `recommend.prompts.read_all(since, overrides, engine_dir)` y `ENGINE_DIR`.
  - Tarea 1: `recommend.redact.redact`.
  - Tarea 3: `recommend.cluster.candidates`, `lexical_clusters`, `merge` y `rank_final`.
  - Tarea 7: `recommend.llm.run_llm`, `validate_groups`, `validate_recommendations` y `subprocess_runner`.
  - Tarea 6: `recommend.heuristics.recommend`.
  - Tarea 5: `recommend.cost.cost_recommendations`.
  - Tarea 4: `recommend.store.*`.
  - Existentes: `briefing.load(db_path)` y `history.DB_PATH_DEFAULT`.
- Produce:
  - `LOCK_PATH`, `WINDOW_DAYS = 30` y `EngineBusy(Exception)`.
  - Lock: `acquire_lock(lock_path=LOCK_PATH)` (lanza `EngineBusy`) y `release_lock(lock_path=LOCK_PATH)`.
  - `impact_for(tokens, total) -> "alto" | "medio" | "bajo"` y `load_session_tokens(db_path=None) -> dict[(source, session_id), int]`.
  - `start(trigger, db_path=None, lock_path=LOCK_PATH) -> (run_id, settings)`: adquiere el lock y registra la corrida `corriendo`; si algo falla, libera el lock.
  - `execute(run_id, settings, db_path=None, lock_path=LOCK_PATH, today=None, prompt_overrides=None, session_tokens=None, runner=llm.subprocess_runner, engine_dir=ENGINE_DIR) -> str`: devuelve `"ok"`, `"degraded"` o `"error"`. **Siempre** libera el lock.
  - `run(trigger, db_path=None, lock_path=LOCK_PATH, **kw) -> (run_id, status)`, donde `**kw` son los mismos argumentos opcionales de `execute`.
  - CLI `python3 -m recommend run --trigger diario|manual`, con código de salida 0 (`ok`/`degraded`), 1 (`error`) o 2 (lock ocupado).
  - `server.py` (Tarea 9) usa `start` en el hilo de la petición y `execute` en un hilo aparte, para poder responder `202 {run_id}` o `409` al instante.

- [ ] **Paso 1: escribir el test que falla**

```python
# tests/test_recommend_engine.py
import io
import json
import os
import sqlite3
import subprocess
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from unittest import mock

from recommend import __main__ as cli
from recommend import engine, store

APP = "/home/u/DEV/ACME/app"
TODAY = date(2026, 9, 25)
TEXT_A = "revisa los logs del servicio de pagos y dime por qué falla el cobro con tarjeta"
TEXT_B = "mira las trazas del módulo de cobros y explícame el fallo al cobrar con la visa"
GROUPED = {"groups": [{"group_id": "g1", "members": ["c1", "c2"]}],
           "recommendations": [{"group_id": "g1", "kind": "skill", "pattern": "Diagnosticar fallos de cobro",
                                "description": "Pides lo mismo con palabras distintas.",
                                "draft": "---\nname: diagnostico-cobros\n---\nEscribe a ana@acme.com"}]}


def write_session(root, session_id, text, day):
    folder = os.path.join(root, "-home-u-DEV-ACME-app")
    os.makedirs(folder, exist_ok=True)
    rec = {"type": "user", "timestamp": f"{day}T10:00:00Z", "cwd": APP, "sessionId": session_id,
           "message": {"role": "user", "content": text}}
    with open(os.path.join(folder, f"{session_id}.jsonl"), "w") as fh:
        fh.write(json.dumps(rec) + "\n")


def hermes_runner(*outputs):
    """Runner falso: cada llamada escribe un usage-file free y devuelve el siguiente output
    (dict → JSON; None → código de salida 1)."""
    queue = list(outputs)

    def run(args, cwd, timeout):
        out = queue.pop(0)
        if out is None:
            return 1, "", "caído"
        with open(args[args.index("--usage-file") + 1], "w") as fh:
            json.dump({"total_tokens": 1234, "estimated_cost_usd": 0.0}, fh)
        return 0, json.dumps(out), ""
    return run


class EngineTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.db = os.path.join(tmp, "history.db")
        self.lock = os.path.join(tmp, "recommend.lock")
        self.engine_dir = os.path.join(tmp, "motor-recomendaciones")
        self.cc_root = os.path.join(tmp, "claude-projects")
        missing = os.path.join(tmp, "no-existe")
        self.overrides = {"claude_code": self.cc_root, "codex": missing, "opencode": missing + ".db",
                          "hermes": missing + ".db"}

    def run_engine(self, runner=None, session_tokens=None):
        return engine.run("manual", db_path=self.db, lock_path=self.lock, today=TODAY,
                          prompt_overrides=self.overrides, session_tokens=session_tokens or {},
                          runner=runner or hermes_runner(), engine_dir=self.engine_dir)


class TestLock(EngineTestCase):
    def test_second_acquire_is_busy_and_release_frees(self):
        engine.acquire_lock(self.lock)
        with self.assertRaises(engine.EngineBusy):
            engine.acquire_lock(self.lock)
        engine.release_lock(self.lock)
        self.assertFalse(os.path.exists(self.lock))
        engine.acquire_lock(self.lock)
        engine.release_lock(self.lock)

    def test_dead_pid_lock_is_recovered(self):
        proc = subprocess.Popen(["true"])
        proc.wait()
        with open(self.lock, "w") as fh:
            fh.write(str(proc.pid))
        engine.acquire_lock(self.lock)
        with open(self.lock) as fh:
            self.assertEqual(fh.read(), str(os.getpid()))
        engine.release_lock(self.lock)

    def test_garbage_lock_is_busy_while_fresh_and_recovered_when_old(self):
        with open(self.lock, "w") as fh:
            fh.write("")
        with self.assertRaises(engine.EngineBusy):
            engine.acquire_lock(self.lock)
        old = time.time() - 3600
        os.utime(self.lock, (old, old))
        engine.acquire_lock(self.lock)
        engine.release_lock(self.lock)


class TestImpact(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(engine.impact_for(100, 1000), "alto")
        self.assertEqual(engine.impact_for(30, 1000), "medio")
        self.assertEqual(engine.impact_for(29, 1000), "bajo")
        self.assertEqual(engine.impact_for(10, 0), "bajo")


class TestRun(EngineTestCase):
    def synonyms_fixture(self):
        # A y B no comparten trigramas: solo el LLM puede unirlos. Por separado
        # ninguno pasa el umbral final (2 sesiones); juntos suman 4 sesiones en 3 días.
        write_session(self.cc_root, "a1", TEXT_A, "2026-09-20")
        write_session(self.cc_root, "a2", TEXT_A, "2026-09-21")
        write_session(self.cc_root, "b1", TEXT_B, "2026-09-22")
        write_session(self.cc_root, "b2", TEXT_B, "2026-09-22")
        return {("claude_code", "a1"): 5000, ("claude_code", "a2"): 5000,
                ("claude_code", "b1"): 1000, ("claude_code", "b2"): 1000}

    def test_llm_groups_synonyms_end_to_end(self):
        tokens = self.synonyms_fixture()
        run_id, status = self.run_engine(hermes_runner(GROUPED), tokens)
        self.assertEqual(status, "ok")
        run = store.get_run(self.db, run_id)
        self.assertEqual((run["status"], run["model"], run["attempts"], run["prompts"], run["clusters"],
                          run["created"], run["llm_tokens"]),
                         ("ok", "nous:stealth/space-bunny-alpha", 1, 4, 1, 1, 1234))
        [rec] = store.list_recommendations(self.db)
        self.assertEqual((rec["kind"], rec["tool"], rec["tokens"], rec["generator"], rec["impact"]),
                         ("skill", "claude_code", 12000, "nous:stealth/space-bunny-alpha", "bajo"))
        self.assertEqual((rec["evidence"]["sessions"], rec["evidence"]["days"]), (4, 3))
        self.assertNotIn("ana@acme.com", rec["draft"])
        self.assertFalse(os.path.exists(self.lock))
        self.assertTrue(os.path.isdir(self.engine_dir))

    def test_backend_none_uses_lexical_only_and_never_deletes(self):
        tokens = self.synonyms_fixture()
        self.run_engine(hermes_runner(GROUPED), tokens)
        store.save_engine_settings({"backend": "none", "llm_chain": ["nous:stealth/x"]}, self.db)
        run_id, status = self.run_engine(session_tokens=tokens)
        self.assertEqual(status, "degraded")
        self.assertEqual(store.get_run(self.db, run_id)["clusters"], 0)
        self.assertEqual(len(store.list_recommendations(self.db, "todas")), 1)

    def test_chain_exhausted_falls_back_to_rules(self):
        for i, day in enumerate(("2026-09-20", "2026-09-20", "2026-09-21")):
            write_session(self.cc_root, f"a{i}", TEXT_A, day)
        run_id, status = self.run_engine(hermes_runner(None, None, None))
        self.assertEqual(status, "degraded")
        run = store.get_run(self.db, run_id)
        self.assertEqual((run["attempts"], run["model"], run["created"]), (3, None, 1))
        self.assertIn("nous:stealth/space-bunny-alpha: ", run["error"])
        [rec] = store.list_recommendations(self.db)
        self.assertEqual(rec["generator"], "reglas")

    def test_no_prompts_skips_llm(self):
        def never(*_):
            raise AssertionError("no debe llamarse al LLM sin candidatos")
        run_id, status = self.run_engine(never)
        self.assertEqual(status, "ok")
        self.assertEqual(store.get_run(self.db, run_id)["attempts"], 0)

    def test_write_failure_marks_error_and_releases_lock(self):
        self.synonyms_fixture()
        with mock.patch("recommend.engine.store.apply_run", side_effect=sqlite3.OperationalError("disco lleno")):
            run_id, status = self.run_engine(hermes_runner(GROUPED))
        self.assertEqual(status, "error")
        run = store.get_run(self.db, run_id)
        self.assertEqual(run["status"], "error")
        self.assertIn("disco lleno", run["error"])
        self.assertFalse(os.path.exists(self.lock))

    def test_busy_lock_raises_before_registering_run(self):
        engine.acquire_lock(self.lock)
        try:
            with self.assertRaises(engine.EngineBusy):
                self.run_engine()
        finally:
            engine.release_lock(self.lock)
        self.assertIsNone(store.last_run(self.db))


class TestSessionTokens(unittest.TestCase):
    def test_load_session_tokens_from_collectors(self):
        detail = lambda *pairs: {"/p": {"sessions_detail": [{"session_id": s, "tokens": t} for s, t in pairs]}}
        with mock.patch("collectors.claude_code.collect", return_value=detail(("s1", 10))), \
             mock.patch("collectors.codex.collect", return_value=detail(("t1", 20))), \
             mock.patch("collectors.opencode.collect", return_value={}), \
             mock.patch("collectors.hermes.collect", return_value=detail((7, 30), (None, 99))):
            self.assertEqual(engine.load_session_tokens(),
                             {("claude_code", "s1"): 10, ("codex", "t1"): 20, ("hermes", "7"): 30})


class TestCli(unittest.TestCase):
    def call(self, result):
        out, err = io.StringIO(), io.StringIO()
        patch = mock.patch("recommend.engine.run", **result)
        with patch as run, redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["run", "--trigger", "diario"])
        return code, run, out.getvalue(), err.getvalue()

    def test_exit_codes(self):
        code, run, out, _ = self.call({"return_value": (5, "ok")})
        self.assertEqual(code, 0)
        run.assert_called_once_with("diario")
        self.assertIn("Corrida 5: ok", out)
        self.assertEqual(self.call({"return_value": (6, "degraded")})[0], 0)
        self.assertEqual(self.call({"return_value": (7, "error")})[0], 1)
        code, _, _, err = self.call({"side_effect": engine.EngineBusy()})
        self.assertEqual(code, 2)
        self.assertIn("Ya hay una corrida en curso", err)
```

- [ ] **Paso 2: correr el test y verificar que falla**

Run: `python3 -m unittest tests.test_recommend_engine -v`
Esperado: FAIL con `ImportError: cannot import name '__main__' from 'recommend'` (o `engine`).

- [ ] **Paso 3: implementar `recommend/engine.py`**

```python
# recommend/engine.py
"""Orquesta una corrida del motor (spec §3 y §5): lock → prompts (30 días) →
redacción → candidatos → LLM o solo léxico → heurística → señales de costo
→ store.apply_run en una transacción → registro de la corrida → liberar lock."""
import os
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone

import briefing
import history
from recommend import cluster as clustering
from recommend import cost, heuristics, llm, store
from recommend.prompts import ENGINE_DIR, read_all
from recommend.redact import redact

LOCK_PATH = os.path.expanduser("~/.local/share/ai-monitor/recommend.lock")
WINDOW_DAYS = 30
IMPACT_HIGH = 0.10
IMPACT_MEDIUM = 0.03
FRESH_LOCK_SECONDS = 10


class EngineBusy(Exception):
    """Ya hay una corrida viva (lock con un PID vivo)."""


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, OverflowError):
        return False
    return True


def lock_is_live(lock_path):
    try:
        with open(lock_path) as fh:
            content = fh.read().strip()
        age = time.time() - os.path.getmtime(lock_path)
    except OSError:
        return False  # desapareció entre medias: se reintenta
    if not content.isdigit():
        # Otro proceso acaba de crearlo y aún no escribió su PID.
        return age < FRESH_LOCK_SECONDS
    return _pid_alive(int(content))


def acquire_lock(lock_path=LOCK_PATH):
    os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
    for _ in range(3):
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            if lock_is_live(lock_path):
                raise EngineBusy() from None
            try:
                os.unlink(lock_path)
            except FileNotFoundError:
                pass
            continue
        with os.fdopen(fd, "w") as fh:
            fh.write(str(os.getpid()))
        return
    raise EngineBusy()


def release_lock(lock_path=LOCK_PATH):
    try:
        with open(lock_path) as fh:
            if fh.read().strip() != str(os.getpid()):
                return
        os.unlink(lock_path)
    except OSError:
        pass


def impact_for(tokens, total):
    share = tokens / total if total > 0 else 0
    if share >= IMPACT_HIGH:
        return "alto"
    if share >= IMPACT_MEDIUM:
        return "medio"
    return "bajo"


def load_session_tokens(db_path=None):
    """Tokens por sesión según los collectors, la misma fuente de verdad que el
    dashboard. Los collectors ya degradan solos si falta su archivo."""
    from collectors import claude_code, codex, hermes, opencode

    sources = {"claude_code": claude_code.collect(db_path=db_path), "codex": codex.collect(db_path=db_path),
               "opencode": opencode.collect(), "hermes": hermes.collect()}
    out = {}
    for source, projects in sources.items():
        for data in projects.values():
            for session in data.get("sessions_detail") or []:
                sid = session.get("session_id")
                if sid is None:
                    continue
                key = (source, str(sid))
                out[key] = out.get(key, 0) + int(session.get("tokens") or 0)
    return out


def _source_totals(project_rows, since, until):
    totals = {}
    for row in project_rows:
        if since <= row["date"] <= until:
            totals[row["source"]] = totals.get(row["source"], 0) + (row["tokens"] or 0)
    return totals


def _pattern_rec(c, texts, model, totals):
    generator = model if texts else "reglas"
    texts = texts or heuristics.recommend(c)
    total = sum(totals.get(source, 0) for source in c.sources)
    return {"tool": c.tool, "tokens": c.tokens, "pattern": texts["pattern"], "kind": texts["kind"],
            "description": texts["description"], "impact": impact_for(c.tokens, total),
            "evidence": c.evidence(), "draft": texts["draft"], "signature": sorted(c.signature),
            "generator": generator}


def _analyze(settings, db_path, today, prompt_overrides, session_tokens, runner, engine_dir):
    os.makedirs(engine_dir, exist_ok=True)
    since = (today - timedelta(days=WINDOW_DAYS - 1)).isoformat()
    raw, errors = read_all(since, prompt_overrides, engine_dir)
    prompts = [p._replace(text=redact(p.text)) for p in raw]
    if session_tokens is None:
        session_tokens = load_session_tokens(db_path)
    try:
        project_rows, model_rows, roi = briefing.load(db_path or history.DB_PATH_DEFAULT)
    except sqlite3.Error as exc:
        project_rows, model_rows, roi = [], [], {}
        errors.append(f"history: {exc}")

    fields = {"model": None, "attempts": 0, "llm_tokens": 0, "llm_cost": 0.0}
    texts, degraded = {}, False
    if settings["backend"] == "none":
        groups, degraded = clustering.lexical_clusters(prompts, session_tokens), True
    else:
        cands = clustering.candidates(prompts, session_tokens)
        groups = []
        if cands:
            result = llm.run_llm(cands, settings["backend"], settings["llm_chain"], runner=runner, cwd=engine_dir)
            fields.update(attempts=result["attempts"], llm_tokens=result["llm_tokens"], llm_cost=result["llm_cost"])
            errors.extend(result["errors"])
            if result["ok"]:
                fields["model"] = result["model"]
                by_id = {c.cluster_id: c for c in cands}
                grouped = llm.validate_groups(result["data"], list(by_id))
                merged = [clustering.merge([by_id[m] for m in members], gid) for gid, members in grouped.items()]
                groups = clustering.rank_final(merged)
                texts = llm.validate_recommendations(result["data"], set(grouped))
            else:
                groups, degraded = clustering.lexical_clusters(prompts, session_tokens), True

    totals = _source_totals(project_rows, since, today.isoformat())
    pattern_recs = [_pattern_rec(c, texts.get(c.cluster_id), fields["model"], totals) for c in groups]
    cost_recs = cost.cost_recommendations(project_rows, model_rows, roi, today)
    counts = store.apply_run(db_path, pattern_recs, cost_recs, now_iso())
    return {"status": "degraded" if degraded else "ok", **fields, "prompts": len(prompts),
            "clusters": len(groups), **counts, "error": "; ".join(errors)[:1000] or None}


def start(trigger, db_path=None, lock_path=LOCK_PATH):
    acquire_lock(lock_path)
    try:
        settings = store.get_engine_settings(db_path)
        run_id = store.start_run(db_path, trigger, settings["backend"], now_iso())
    except BaseException:
        release_lock(lock_path)
        raise
    return run_id, settings


def execute(run_id, settings, db_path=None, lock_path=LOCK_PATH, today=None, prompt_overrides=None,
            session_tokens=None, runner=llm.subprocess_runner, engine_dir=ENGINE_DIR):
    try:
        result = _analyze(settings, db_path, today or date.today(), prompt_overrides, session_tokens,
                          runner, engine_dir)
        status = result.pop("status")
        store.finish_run(db_path, run_id, status, now_iso(), **result)
        return status
    except Exception as exc:  # noqa: BLE001 — la corrida queda en error, nunca colgada en "corriendo"
        try:
            store.finish_run(db_path, run_id, "error", now_iso(), error=f"{type(exc).__name__}: {exc}"[:1000])
        except sqlite3.Error:
            pass
        return "error"
    finally:
        release_lock(lock_path)


def run(trigger, db_path=None, lock_path=LOCK_PATH, **kw):
    run_id, settings = start(trigger, db_path, lock_path)
    return run_id, execute(run_id, settings, db_path, lock_path, **kw)
```

- [ ] **Paso 4: implementar `recommend/__main__.py`**

```python
# recommend/__main__.py
"""CLI: python3 -m recommend run --trigger diario|manual (lo usa el timer diario)."""
import argparse
import sys

from recommend import engine


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python3 -m recommend", description="Motor de recomendaciones de ai-monitor")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run", help="Ejecuta una corrida completa")
    run_parser.add_argument("--trigger", choices=("diario", "manual"), default="manual")
    args = parser.parse_args(argv)
    try:
        run_id, status = engine.run(args.trigger)
    except engine.EngineBusy:
        print("Ya hay una corrida en curso", file=sys.stderr)
        return 2
    print(f"Corrida {run_id}: {status}")
    return 1 if status == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Paso 5: correr el test y verificar que pasa**

Run: `python3 -m unittest tests.test_recommend_engine -v`
Esperado: PASS. Si `test_llm_groups_synonyms_end_to_end` falla porque A y B comparten algún trigrama y ya se unen en modo léxico, cambia `TEXT_B` por una frase sin tres palabras seguidas en común con `TEXT_A`. No toques los umbrales.

- [ ] **Paso 6: correr toda la suite y el CLI con una base temporal**

Run: `python3 -m unittest discover -s tests 2>&1 | tail -3`
Esperado: `OK`.

Run: `python3 -m recommend --help`
Esperado: la ayuda con el subcomando `run`. **No** ejecutes `python3 -m recommend run` contra tu `history.db` real en este paso: lo cubre la verificación de cierre (Tarea 14).

- [ ] **Paso 7: commit**

```bash
git add recommend/engine.py recommend/__main__.py tests/test_recommend_engine.py
git commit -m "feat(recommend): orquestador con lock, corrida completa y CLI"
```

---

---

### Tarea 9: API del motor en `server.py`

**Archivos:**
- Modificar: `server.py`
- Test: `tests/test_server_recommendations.py` (nuevo); `tests/test_server.py` debe seguir pasando sin cambios.

**Interfaces:**
- Consume:
  - Tarea 8: `engine.start`, `engine.execute`, `engine.EngineBusy`, `engine.LOCK_PATH`, `engine.lock_is_live(lock_path)` y `engine.now_iso()`.
  - Tarea 4: `store.list_recommendations`, `store.set_status`, `store.last_run`, `store.latest_finished_run_id`, `store.get_engine_settings`, `store.save_engine_settings` y `store.USER_STATUSES`.
  - Tarea 4: `settings.validate_engine_settings`, `settings.EngineSettingsError`, `settings.DEFAULT_BACKEND` y `settings.DEFAULT_CHAIN`.
  - Existente: `sse.SSEBroker.publish(event, data)`.
- Produce:
  - `GET /api/recommendations?estado=nueva|aplicada|saltada|resuelta|todas` (por defecto `nueva`) → `200 {recommendations, last_run, running, degraded}`. Un `estado` desconocido → `400 {"error"}`. Un `sqlite3.Error` → `200` con `{recommendations: [], last_run: null, running: false, degraded: true}`.
  - `POST /api/recommendations/<id>/estado` con `{"status": "nueva"|"aplicada"|"saltada"}` → `200` con la recomendación; `404` si no existe; `400` si el estado no es de usuario (incluido `resuelta`) o falta; `415` sin JSON.
  - `POST /api/recommendations/run` (cuerpo JSON cualquiera, p. ej. `{}`) → `202 {"run_id"}`; `409 {"error": "Ya hay una corrida en curso"}`; `415` sin JSON. El cuerpo JSON obligatorio es la defensa CSRF: un formulario HTML de otro origen no puede enviar `application/json` sin preflight.
  - `GET /api/engine-settings` → `{backend, llm_chain}` (valores por defecto si la base falla). `POST /api/engine-settings` → `200` con lo guardado, `400 {"error"}` o `415`.
  - Evento SSE `recommendations` con `{"run_id": N}`: lo publica el hilo de una corrida manual al terminar y el loop de fondo cuando aparece una corrida terminada nueva (la del timer diario).
  - `make_handler(static_dir, broker, db_path=None, engine_opts=None)` y `build_app(static_dir, poll_interval_seconds=60, port=0, db_path=None, engine_opts=None)`. `engine_opts` son kwargs extra para `engine.execute` (`lock_path`, `prompt_overrides`, `session_tokens`, `runner`, `engine_dir`, `today`); solo los usan los tests y el E2E.
  - `_check_recommendation_runs(broker, db_path, last) -> last` (función pura sobre la base, testeable sin sockets).

- [ ] **Paso 1: escribir el test que falla**

```python
# tests/test_server_recommendations.py
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

import history
import server
from recommend import engine, store

EMPTY_SOURCES = {"claude_code": {}, "codex": {}, "opencode": {}, "hermes": {},
                 "openrouter": {"unavailable": True, "reason": "x"}}
NOW = "2026-09-20T07:00:00+00:00"


def pattern_rec(signature, pattern="revisa los logs"):
    return {"tool": "claude_code", "tokens": 100, "pattern": pattern, "kind": "prompt", "description": "desc",
            "impact": "medio", "evidence": {"sessions": 3, "days": 2, "tokens": 100, "projects": [],
                                            "sources": ["claude_code"], "snippets": []},
            "draft": "borrador", "signature": signature, "generator": "reglas"}


class RecommendationsAPITestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.static_dir = os.path.join(tmp, "dist")
        os.makedirs(self.static_dir)
        with open(os.path.join(self.static_dir, "index.html"), "w") as fh:
            fh.write("<html>fallback</html>")
        self.db = os.path.join(tmp, "history.db")
        self.lock = os.path.join(tmp, "recommend.lock")
        missing = os.path.join(tmp, "no-existe")
        self.engine_opts = {
            "lock_path": self.lock,
            "prompt_overrides": {"claude_code": missing, "codex": missing, "opencode": missing + ".db",
                                 "hermes": missing + ".db"},
            "session_tokens": {},
            "runner": lambda args, cwd, timeout: (1, "", "no debería llamarse sin candidatos"),
            "engine_dir": os.path.join(tmp, "motor-recomendaciones"),
        }
        patcher = patch("server.main.collect_all", return_value=EMPTY_SOURCES)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.httpd = server.build_app(self.static_dir, poll_interval_seconds=3600, db_path=self.db,
                                      engine_opts=self.engine_opts)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def request(self, method, path, body=None, content_type="application/json"):
        data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        headers = {"Content-Type": content_type} if data is not None else {}
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method,
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = resp.read()
                return resp.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                return exc.code, json.loads(raw) if raw else None
            except ValueError:
                return exc.code, None

    def seed(self):
        store.apply_run(self.db, [pattern_rec([f"tri {i}" for i in range(10)])], [], NOW)
        return store.list_recommendations(self.db, "nueva")[0]["id"]


class TestListAndStatus(RecommendationsAPITestCase):
    def test_empty_database_lists_nothing(self):
        status, body = self.request("GET", "/api/recommendations")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"recommendations": [], "last_run": None, "running": False, "degraded": False})

    def test_unknown_estado_is_400(self):
        status, body = self.request("GET", "/api/recommendations?estado=borrada")
        self.assertEqual(status, 400)
        self.assertIn("borrada", body["error"])

    def test_status_lifecycle_and_tabs(self):
        rec_id = self.seed()
        status, body = self.request("POST", f"/api/recommendations/{rec_id}/estado", {"status": "aplicada"})
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "aplicada")
        self.assertNotIn("signature", body)
        self.assertEqual(self.request("GET", "/api/recommendations")[1]["recommendations"], [])
        applied = self.request("GET", "/api/recommendations?estado=aplicada")[1]["recommendations"]
        self.assertEqual([r["id"] for r in applied], [rec_id])
        self.assertEqual(applied[0]["evidence"]["sessions"], 3)
        # Deshacer = volver a "nueva".
        self.assertEqual(self.request("POST", f"/api/recommendations/{rec_id}/estado", {"status": "nueva"})[0], 200)
        self.assertEqual(len(self.request("GET", "/api/recommendations?estado=todas")[1]["recommendations"]), 1)

    def test_status_errors(self):
        rec_id = self.seed()
        path = f"/api/recommendations/{rec_id}/estado"
        self.assertEqual(self.request("POST", "/api/recommendations/noexiste/estado", {"status": "aplicada"})[0], 404)
        self.assertEqual(self.request("POST", path, {"status": "resuelta"})[0], 400)
        self.assertEqual(self.request("POST", path, {"otro": 1})[0], 400)
        self.assertEqual(self.request("POST", path, [1, 2])[0], 400)
        self.assertEqual(self.request("POST", path, b"{roto", "application/json")[0], 400)
        self.assertEqual(self.request("POST", path, {"status": "aplicada"}, "text/plain")[0], 415)
        self.assertEqual(self.request("POST", "/api/recommendations/a-b/estado", {"status": "aplicada"})[0], 404)

    def test_sqlite_error_is_degraded_not_500(self):
        with patch("server.rec_store.list_recommendations", side_effect=sqlite3.OperationalError("disk I/O")):
            status, body = self.request("GET", "/api/recommendations")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"recommendations": [], "last_run": None, "running": False, "degraded": True})

    def test_old_history_db_without_new_tables(self):
        old = os.path.join(tempfile.mkdtemp(), "old.db")
        history.ensure_schema(old)  # solo las tablas previas al motor
        self.httpd.RequestHandlerClass = server.make_handler(self.static_dir, server.SSEBroker(), db_path=old,
                                                             engine_opts=self.engine_opts)
        status, body = self.request("GET", "/api/recommendations")
        self.assertEqual((status, body["recommendations"], body["degraded"]), (200, [], False))
        status, body = self.request("GET", "/api/engine-settings")
        self.assertEqual(status, 200)
        self.assertEqual(body["backend"], "hermes")
        self.assertEqual(len(body["llm_chain"]), 3)


class TestRun(RecommendationsAPITestCase):
    def wait_finished(self, run_id, timeout=5):
        deadline = time.time() + timeout
        while time.time() < deadline:
            run = store.get_run(self.db, run_id)
            if run and run["finished_at"]:
                return run
            time.sleep(0.05)
        self.fail("la corrida no terminó")

    def test_run_returns_202_and_publishes_sse(self):
        queue = self.httpd.RequestHandlerClass.broker.subscribe()
        status, body = self.request("POST", "/api/recommendations/run", {})
        self.assertEqual(status, 202)
        run = self.wait_finished(body["run_id"])
        self.assertEqual((run["trigger"], run["status"]), ("manual", "ok"))
        self.assertFalse(os.path.exists(self.lock))
        event = queue.get(timeout=5)
        self.assertTrue(event.startswith(b"event: recommendations\n"))
        self.assertIn(f'"run_id": {body["run_id"]}'.encode(), event)
        listed = self.request("GET", "/api/recommendations")[1]
        self.assertEqual(listed["last_run"]["id"], body["run_id"])
        self.assertFalse(listed["running"])

    def test_run_conflict_returns_409(self):
        engine.acquire_lock(self.lock)
        try:
            status, body = self.request("POST", "/api/recommendations/run", {})
            self.assertEqual(status, 409)
            self.assertEqual(body["error"], "Ya hay una corrida en curso")
            self.assertTrue(self.request("GET", "/api/recommendations")[1]["running"])
        finally:
            engine.release_lock(self.lock)
        self.assertIsNone(store.last_run(self.db))  # un 409 no registra corrida

    def test_run_requires_json(self):
        self.assertEqual(self.request("POST", "/api/recommendations/run", b"", "text/plain")[0], 415)
        self.assertEqual(self.request("POST", "/api/recommendations/run")[0], 415)


class TestEngineSettings(RecommendationsAPITestCase):
    def test_roundtrip_and_validation(self):
        payload = {"backend": "claude", "llm_chain": ["nous:upstage/solar-pro4:free"]}
        self.assertEqual(self.request("POST", "/api/engine-settings", payload), (200, payload))
        self.assertEqual(self.request("GET", "/api/engine-settings"), (200, payload))
        status, body = self.request("POST", "/api/engine-settings",
                                    {"backend": "hermes", "llm_chain": ["openrouter:openai/gpt-5"]})
        self.assertEqual(status, 400)
        self.assertIn("free", body["error"])
        self.assertEqual(self.request("POST", "/api/engine-settings", {"backend": "x"})[0], 400)
        self.assertEqual(self.request("POST", "/api/engine-settings", payload, "text/plain")[0], 415)


class TestCheckRecommendationRuns(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "history.db")
        self.broker = server.SSEBroker()
        self.queue = self.broker.subscribe()

    def test_publishes_only_new_finished_runs(self):
        self.assertIsNone(server._check_recommendation_runs(self.broker, self.db, None))
        run_id = store.start_run(self.db, "diario", "hermes", NOW)
        self.assertIsNone(server._check_recommendation_runs(self.broker, self.db, None))  # aún corriendo
        store.finish_run(self.db, run_id, "ok", NOW)
        self.assertEqual(server._check_recommendation_runs(self.broker, self.db, None), run_id)
        self.assertIn(b"event: recommendations", self.queue.get_nowait())
        self.assertEqual(server._check_recommendation_runs(self.broker, self.db, run_id), run_id)
        self.assertTrue(self.queue.empty())

    def test_sqlite_error_keeps_last(self):
        with patch("server.rec_store.latest_finished_run_id", side_effect=sqlite3.OperationalError("x")):
            self.assertEqual(server._check_recommendation_runs(self.broker, self.db, 7), 7)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Paso 2: correr el test y verificar que falla**

Run: `python3 -m unittest tests.test_server_recommendations -v 2>&1 | tail -5`
Esperado: FAIL con `TypeError: build_app() got an unexpected keyword argument 'engine_opts'`.

- [ ] **Paso 3: implementar en `server.py`**

Imports nuevos (junto a los existentes):

```python
import re
import sqlite3
from urllib.parse import urlparse, parse_qs

import briefing
import history
import main
from recommend import engine as rec_engine
from recommend import settings as rec_settings
from recommend import store as rec_store
from sse import SSEBroker, format_sse_event
```

Tras `_current_snapshot_json`, las funciones del motor (sin sockets, testeables):

```python
REC_ESTADOS = ("nueva", "aplicada", "saltada", "resuelta", "todas")
_STATUS_PATH = re.compile(r"^/api/recommendations/([A-Za-z0-9]+)/estado$")
_INVALID = object()


def _recommendations_payload(db_path, estado, lock_path):
    try:
        recs = rec_store.list_recommendations(db_path, estado)
        last = rec_store.last_run(db_path)
    except sqlite3.Error:
        return {"recommendations": [], "last_run": None, "running": False, "degraded": True}
    return {"recommendations": recs, "last_run": last, "running": rec_engine.lock_is_live(lock_path),
            "degraded": False}


def _check_recommendation_runs(broker, db_path, last):
    """Publica `recommendations` si apareció una corrida terminada nueva (p. ej. la
    del timer diario, que corre en otro proceso). Devuelve el último id visto."""
    try:
        current = rec_store.latest_finished_run_id(db_path)
    except sqlite3.Error:
        return last
    if current is None or current == last:
        return last
    broker.publish("recommendations", json.dumps({"run_id": current}))
    return current
```

`_background_loop` pasa a vigilar también las corridas:

```python
def _background_loop(broker, poll_interval_seconds, db_path=None, last_run_id=None):
    while True:
        time.sleep(poll_interval_seconds)
        try:
            _recompute_and_maybe_publish(broker)
        except Exception:
            pass  # una falla de recolección no debe tumbar el hilo de fondo
        last_run_id = _check_recommendation_runs(broker, db_path, last_run_id)
```

`make_handler` recibe `engine_opts` y expone `broker` como atributo de clase (lo usa el test de SSE):

```python
def make_handler(static_dir, broker, db_path=None, engine_opts=None):
    opts = dict(engine_opts or {})
    lock_path = opts.pop("lock_path", rec_engine.LOCK_PATH)

    def run_in_background(run_id, settings):
        try:
            rec_engine.execute(run_id, settings, db_path, lock_path=lock_path, **opts)
        finally:
            broker.publish("recommendations", json.dumps({"run_id": run_id}))

    class Handler(BaseHTTPRequestHandler):
        ...
    Handler.broker = broker
    return Handler
```

(`Handler.broker = broker` va justo antes del `return Handler` existente.)

En `do_GET`, dos ramas nuevas antes de `/api/stream`:

```python
            elif parsed.path == "/api/recommendations":
                estado = parse_qs(parsed.query).get("estado", ["nueva"])[0]
                if estado not in REC_ESTADOS:
                    self._send_json(json.dumps({"error": f"Estado desconocido: {estado}"}), status=400)
                    return
                self._send_json(json.dumps(_recommendations_payload(db_path, estado, lock_path)))
            elif parsed.path == "/api/engine-settings":
                try:
                    data = rec_store.get_engine_settings(db_path)
                except sqlite3.Error:
                    data = {"backend": rec_settings.DEFAULT_BACKEND, "llm_chain": list(rec_settings.DEFAULT_CHAIN)}
                self._send_json(json.dumps(data))
```

`do_POST` completo (la rama de `roi-settings` pasa a usar `_read_json_body`; su comportamiento no cambia):

```python
        def do_POST(self):
            parsed = urlparse(self.path)
            status_match = _STATUS_PATH.match(parsed.path)

            if parsed.path == "/api/roi-settings":
                settings = self._read_json_body()
                if settings is _INVALID:
                    return
                try:
                    history.validate_roi_settings(settings)
                except history.RoiSettingsError as exc:
                    self._send_json(json.dumps({"error": str(exc)}), status=400)
                    return
                history.save_roi_settings(settings, db_path=db_path)
                self._send_json(json.dumps(history.get_roi_settings(db_path=db_path)))
            elif parsed.path == "/api/recommendations/run":
                if self._read_json_body() is _INVALID:
                    return
                try:
                    run_id, settings = rec_engine.start("manual", db_path, lock_path)
                except rec_engine.EngineBusy:
                    self._send_json(json.dumps({"error": "Ya hay una corrida en curso"}), status=409)
                    return
                except sqlite3.Error as exc:
                    self._send_json(json.dumps({"error": f"Base no disponible: {exc}"}), status=503)
                    return
                threading.Thread(target=run_in_background, args=(run_id, settings), daemon=True).start()
                self._send_json(json.dumps({"run_id": run_id}), status=202)
            elif status_match:
                body = self._read_json_body()
                if body is _INVALID:
                    return
                status = body.get("status") if isinstance(body, dict) else None
                if status not in rec_store.USER_STATUSES:
                    self._send_json(json.dumps({"error": f"Estado inválido: {status}"}), status=400)
                    return
                try:
                    rec = rec_store.set_status(db_path, status_match.group(1), status, rec_engine.now_iso())
                except sqlite3.Error as exc:
                    self._send_json(json.dumps({"error": f"Base no disponible: {exc}"}), status=503)
                    return
                if rec is None:
                    self._send_json(json.dumps({"error": "Recomendación no encontrada"}), status=404)
                    return
                self._send_json(json.dumps(rec))
            elif parsed.path == "/api/engine-settings":
                body = self._read_json_body()
                if body is _INVALID:
                    return
                try:
                    clean = rec_settings.validate_engine_settings(body)
                except rec_settings.EngineSettingsError as exc:
                    self._send_json(json.dumps({"error": str(exc)}), status=400)
                    return
                rec_store.save_engine_settings(clean, db_path)
                self._send_json(json.dumps(rec_store.get_engine_settings(db_path)))
            else:
                self.send_response(404)
                self.end_headers()

        def _read_json_body(self):
            """Cuerpo JSON o _INVALID tras responder 415 (no es JSON) / 400 (JSON roto)."""
            content_type = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if content_type != "application/json":
                self.send_response(415)
                self.end_headers()
                return _INVALID
            length = int(self.headers.get("Content-Length", 0))
            try:
                return json.loads(self.rfile.read(length))
            except json.JSONDecodeError:
                self.send_response(400)
                self.end_headers()
                return _INVALID
```

`build_app` acepta `engine_opts` y arranca el loop con el último id conocido (así no re-publica la corrida de ayer al arrancar):

```python
def build_app(static_dir, poll_interval_seconds=60, port=0, db_path=None, engine_opts=None):
    static_dir = os.path.abspath(static_dir)
    broker = SSEBroker()
    handler_cls = make_handler(static_dir, broker, db_path=db_path, engine_opts=engine_opts)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler_cls)

    # (comentario existente sobre el primer ciclo síncrono)
    _recompute_and_maybe_publish(broker)
    last_run_id = _check_recommendation_runs(broker, db_path, None)

    thread = threading.Thread(
        target=_background_loop, args=(broker, poll_interval_seconds, db_path, last_run_id), daemon=True
    )
    thread.start()

    return httpd
```

- [ ] **Paso 4: correr los tests y verificar que pasan**

Run: `python3 -m unittest tests.test_server_recommendations tests.test_server -v 2>&1 | tail -5`
Esperado: `OK`. Si `test_run_returns_202_and_publishes_sse` se cuelga, revisa que el `finally` de `run_in_background` publique aunque `execute` falle.

- [ ] **Paso 5: suite completa**

Run: `env -u OPENROUTER_API_KEY python3 -m unittest discover -s tests 2>&1 | tail -3`
Esperado: `OK`.

- [ ] **Paso 6: commit**

```bash
git add server.py tests/test_server_recommendations.py
git commit -m "feat(server): API del motor de recomendaciones y evento SSE recommendations"
```

---

### Tarea 10: Timer diario, `install.sh` y documentación

**Archivos:**
- Crear: `systemd/ai-monitor-recommend.service.template`, `systemd/ai-monitor-recommend.timer`
- Modificar: `systemd/ai-monitor-server.service.template`, `install.sh`, `README.md`, `CLAUDE.md`
- Test: `tests/test_systemd_units.py`

**Interfaces:**
- Consume: CLI de la Tarea 8 (`python3 -m recommend run --trigger diario`) y los endpoints de la Tarea 9.
- Produce: unidades `ai-monitor-recommend.service` (oneshot) y `ai-monitor-recommend.timer` (07:00, `Persistent=true`). Los marcadores `__REPO_DIR__`, `__PYTHON__`, `__ENV_FILE__` y el nuevo `__PATH__` los sustituye `install.sh`. `__PATH__` existe porque `hermes` y `claude` suelen vivir en `~/.local/bin` o en un gestor de versiones de Node, que el `PATH` mínimo de systemd no incluye.

- [ ] **Paso 1: escribir el test que falla**

```python
# tests/test_systemd_units.py
import configparser
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def unit(name):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    parser.read(os.path.join(REPO, "systemd", name))
    return parser


class TestRecommendUnits(unittest.TestCase):
    def test_service_runs_the_engine_daily_trigger(self):
        service = unit("ai-monitor-recommend.service.template")["Service"]
        self.assertEqual(service["Type"], "oneshot")
        self.assertEqual(service["EnvironmentFile"], "-__ENV_FILE__")
        self.assertEqual(service["Environment"], "PATH=__PATH__")
        self.assertEqual(service["WorkingDirectory"], "__REPO_DIR__")
        self.assertEqual(service["ExecStart"], "__PYTHON__ -m recommend run --trigger diario")

    def test_timer_is_daily_and_persistent(self):
        timer = unit("ai-monitor-recommend.timer")
        self.assertEqual(timer["Timer"]["OnCalendar"], "*-*-* 07:00")
        self.assertEqual(timer["Timer"]["Persistent"], "true")
        self.assertEqual(timer["Timer"]["Unit"], "ai-monitor-recommend.service")
        self.assertEqual(timer["Install"]["WantedBy"], "timers.target")

    def test_server_gets_path_for_manual_runs(self):
        self.assertEqual(unit("ai-monitor-server.service.template")["Service"]["Environment"], "PATH=__PATH__")

    def test_install_substitutes_every_placeholder(self):
        with open(os.path.join(REPO, "install.sh")) as fh:
            script = fh.read()
        for marker in ("__REPO_DIR__", "__PYTHON__", "__ENV_FILE__", "__PATH__"):
            self.assertIn(f"s#{marker}#", script)
        self.assertIn("ai-monitor-recommend.service.template", script)
        self.assertIn("ai-monitor-recommend.timer", script)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Paso 2: correr el test y verificar que falla**

Run: `python3 -m unittest tests.test_systemd_units -v 2>&1 | tail -5`
Esperado: FAIL con `KeyError: 'Service'` (la plantilla aún no existe).

- [ ] **Paso 3: crear las unidades**

```ini
# systemd/ai-monitor-recommend.service.template
[Unit]
Description=ai-monitor: motor de recomendaciones (corrida diaria)

[Service]
Type=oneshot
EnvironmentFile=-__ENV_FILE__
Environment=PATH=__PATH__
WorkingDirectory=__REPO_DIR__
ExecStart=__PYTHON__ -m recommend run --trigger diario
```

```ini
# systemd/ai-monitor-recommend.timer
[Unit]
Description=ai-monitor: motor de recomendaciones cada día a las 07:00

[Timer]
OnCalendar=*-*-* 07:00
Persistent=true
Unit=ai-monitor-recommend.service

[Install]
WantedBy=timers.target
```

(Los comentarios `# systemd/...` de arriba son solo para ubicar el archivo en el plan: no los escribas en las unidades.)

En `systemd/ai-monitor-server.service.template`, añade `Environment=PATH=__PATH__` justo debajo de `EnvironmentFile=-__ENV_FILE__`.

- [ ] **Paso 4: actualizar `install.sh`**

1. Tras `ENV_FILE="$ENV_DIR/env"`, añade `UNIT_PATH="$PATH"`.
2. En **los dos** bloques `sed` existentes (el de `ai-monitor.service` y el de `ai-monitor-server.service`), añade la línea `-e "s#__PATH__#${UNIT_PATH}#g" \`. En `ai-monitor.service` no tiene efecto (no usa el marcador), pero deja los tres bloques iguales.
3. Tras `cp "$REPO_DIR/systemd/ai-monitor.timer" ...`, instala las unidades del motor:

```bash
sed \
  -e "s#__REPO_DIR__#${REPO_DIR}#g" \
  -e "s#__PYTHON__#${PYTHON_BIN}#g" \
  -e "s#__ENV_FILE__#${ENV_FILE}#g" \
  -e "s#__PATH__#${UNIT_PATH}#g" \
  "$REPO_DIR/systemd/ai-monitor-recommend.service.template" > "$UNITS_DIR/ai-monitor-recommend.service"

cp "$REPO_DIR/systemd/ai-monitor-recommend.timer" "$UNITS_DIR/ai-monitor-recommend.timer"
```

4. Al final, tras `echo "  systemctl --user enable --now ai-monitor.timer"`:

```bash
echo "  systemctl --user enable --now ai-monitor-recommend.timer   # motor de recomendaciones, 07:00"
```

Comprueba la sintaxis sin ejecutar nada: `bash -n install.sh`. **No** corras `install.sh` ni `systemctl`.

- [ ] **Paso 5: documentar**

`README.md`, nueva sección `## Motor de recomendaciones` tras "Histórico más allá de la retención de cada proveedor":

```markdown
## Motor de recomendaciones

Cada día a las 07:00 (`ai-monitor-recommend.timer`) o con **Analizar ahora** en la vista Recomendaciones, ai-monitor lee tus prompts de los últimos 30 días (Claude Code, Codex, OpenCode y Hermes; OpenRouter no tiene prompts locales), los redacta (claves, correos, rutas e IPs), agrupa los que se repiten y propone una **skill**, un **plugin/MCP** o un **prompt reutilizable** para cada patrón, más recomendaciones de **costo** a partir de las señales del Inicio.

- Backend por defecto: Hermes con modelos free (`nous:…:free` o `stealth/…`), en cadena con fallback. Alternativas: `claude -p` (consume tu suscripción y aparece como proyecto `motor-recomendaciones` en el dashboard) o `ninguno` (solo reglas locales). Se configura en Configuración → Motor de recomendaciones.
- Si ningún modelo responde, la corrida queda **degradada**: agrupación léxica y textos por plantilla.
- Al LLM solo le llegan resúmenes por patrón con ≤3 fragmentos redactados de ≤200 caracteres; `history.db` guarda solo esos fragmentos.
- A mano: `python3 -m recommend run --trigger manual` (código 0 ok/degradada, 1 error, 2 ya hay una corrida en curso).
- API: `GET /api/recommendations?estado=nueva|aplicada|saltada|resuelta|todas`, `POST /api/recommendations/<id>/estado`, `POST /api/recommendations/run` (202/409), `GET|POST /api/engine-settings`. Evento SSE `recommendations` al terminar cada corrida.
```

En la sección de instalación del README, añade `systemctl --user enable --now ai-monitor-recommend.timer` junto a los otros `enable`.

`CLAUDE.md`, en "Architecture", un punto nuevo tras el de `briefing.py`:

```markdown
- **`recommend/`** es el motor de recomendaciones (subproyecto 3). No es un collector: lee prompts locales con lectores propios (`recommend/prompts/`), los redacta (`redact.py`) antes de cualquier otro uso, agrupa en local (`cluster.py`), llama opcionalmente a un LLM (`llm.py`: Hermes free o `claude -p`, siempre vía un `runner` inyectable) y persiste con `store.py` en tablas propias de `history.db` (`recommendations`, `recommendation_runs`, `engine_settings`). Igual que el resto de `history.db`, **nunca borra filas**: una recomendación que deja de detectarse pasa a `resuelta`. `engine.py` serializa las corridas con un lock de archivo; `server.py` expone `/api/recommendations*` y `/api/engine-settings` y el evento SSE `recommendations`. El texto completo de un prompt nunca se guarda ni sale del proceso: solo fragmentos redactados de ≤200 caracteres.
```

Y en la línea de `frontend/` de `CLAUDE.md`, añade `/api/recommendations` y `/api/engine-settings` a la lista de endpoints.

- [ ] **Paso 6: correr los tests**

Run: `python3 -m unittest tests.test_systemd_units -v 2>&1 | tail -3 && bash -n install.sh && git grep -nF "$HOME" -- systemd install.sh README.md CLAUDE.md; echo "grep: $?"`
Esperado: `OK` y `grep: 1` (ninguna ruta del autor).

- [ ] **Paso 7: commit**

```bash
git add systemd/ai-monitor-recommend.service.template systemd/ai-monitor-recommend.timer \
  systemd/ai-monitor-server.service.template install.sh README.md CLAUDE.md tests/test_systemd_units.py
git commit -m "feat(systemd): timer diario del motor de recomendaciones y documentación"
```

---

---

### Tarea 11: Tipos, cliente de API, lógica pura y hooks del frontend

**Archivos:**
- Modificar: `frontend/src/lib/api.ts`, `frontend/src/lib/api.test.ts`, `frontend/src/hooks/useUsageStream.ts`
- Crear: `frontend/src/lib/recommendations.ts`, `frontend/src/lib/recommendations.test.ts`, `frontend/src/hooks/useRecommendations.ts`

**Interfaces:**
- Consume: API de la Tarea 9. Forma de `evidence` de las Tareas 3 (`{sessions, days, tokens, projects, sources, snippets}`) y 5 (`{rule, items, link, projects, sources}`).
- Produce:
  - Tipos en `api.ts`: `RecommendationKind`, `RecommendationImpact`, `RecommendationStatus`, `UserStatus`, `PatternEvidence`, `CostEvidence`, `Recommendation`, `RecommendationRun`, `RecommendationsResponse`, `EngineBackend` y `EngineSettings`.
  - Funciones en `api.ts`: `fetchRecommendations(status)`, `setRecommendationStatus(id, status)`, `runRecommendations()`, `fetchEngineSettings()` y `saveEngineSettings(settings)`.
  - `lib/recommendations.ts`: `REC_TABS`, `parseRecTab`, `KIND_LABEL`, `IMPACT_LABEL`, `isCostEvidence`, `filterBySource`, `evidenceLines`, `runErrorMessage`, `removeRecommendation`, `restoreRecommendation`, `emptyMessage`, `runModelLabel`, `isRunInProgress`, `recommendationsLine`, `parseChain` y `BACKEND_OPTIONS`.
  - `hooks/useRecommendations.ts`: `useRecommendations(status, refreshKey)` → `{state, update, retry}` y `useNewRecommendationsCount(refreshKey)` → `number`.
  - `useUsageStream()` devuelve además `recommendationsVersion: number`, que sube con cada evento SSE `recommendations`.

- [ ] **Paso 1: escribir los tests que fallan**

Añade al final de `frontend/src/lib/api.test.ts` (y agrega `runRecommendations` y `setRecommendationStatus` al import de `@/lib/api`):

```ts
describe("API del motor de recomendaciones", () => {
  it("runRecommendations manda JSON (defensa CSRF) y un 409 llega como HttpError", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: "Ya hay una corrida en curso" }), { status: 409 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const err = await runRecommendations().catch((e: unknown) => e);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/recommendations/run");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
    });
    expect((err as HttpError).status).toBe(409);
  });

  it("setRecommendationStatus codifica el id y envía el estado", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await setRecommendationStatus("abc123", "aplicada");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/recommendations/abc123/estado");
    expect(fetchMock.mock.calls[0][1].body).toBe(JSON.stringify({ status: "aplicada" }));
  });
});
```

```ts
// frontend/src/lib/recommendations.test.ts
import { describe, expect, it } from "vitest";
import { HttpError, type PatternEvidence, type Recommendation, type RecommendationRun, type RecommendationsResponse } from "@/lib/api";
import {
  emptyMessage, evidenceLines, filterBySource, isRunInProgress, parseChain, parseRecTab, recommendationsLine,
  removeRecommendation, restoreRecommendation, runErrorMessage, runModelLabel,
} from "@/lib/recommendations";

// Intl usa espacios no separables; se normalizan para comparar (igual que format.test.ts).
const norm = (lines: string[]) => lines.map((l) => l.replace(/\s/g, " "));

const EV: PatternEvidence = {
  sessions: 4, days: 3, tokens: 1200, projects: ["/home/u/DEV/ACME/app"], sources: ["claude_code"], snippets: ["revisa los logs"],
};

function rec(id: string, extra: Partial<Recommendation> = {}): Recommendation {
  return {
    id, first_seen: "2026-09-20T07:00:00+00:00", last_seen: "2026-09-21T07:00:00+00:00", tool: "claude_code",
    tokens: 1200, pattern: `patrón ${id}`, kind: "skill", description: "d", impact: "medio",
    evidence: EV,
    draft: "---\nname: x\n---", status: "nueva", status_at: null, generator: "reglas", ...extra,
  };
}

const RUN: RecommendationRun = {
  id: 3, started_at: "2026-09-21T12:00:00+00:00", finished_at: "2026-09-21T12:01:00+00:00", trigger: "diario",
  backend: "hermes", model: "nous:upstage/solar-pro4:free", attempts: 1, status: "ok", prompts: 80, clusters: 2,
  created: 1, updated: 1, resolved: 0, error: null, llm_tokens: 900, llm_cost: 0,
};

describe("parseRecTab", () => {
  it("acepta las cuatro pestañas y cae en nueva", () => {
    expect(parseRecTab("aplicada")).toBe("aplicada");
    expect(parseRecTab("resuelta")).toBe("resuelta");
    expect(parseRecTab("todas")).toBe("nueva");
    expect(parseRecTab(null)).toBe("nueva");
  });
});

describe("filterBySource", () => {
  const multi = rec("m", { tool: "varias", evidence: { ...EV, sources: ["codex", "hermes"] } });
  const list = [rec("a"), rec("b", { tool: "codex", evidence: { ...EV, sources: ["codex"] } }), multi];
  it("sin filtro devuelve todo", () => expect(filterBySource(list, "all")).toHaveLength(3));
  it("filtra por tool y por las fuentes de un patrón compartido", () => {
    expect(filterBySource(list, "codex").map((r) => r.id)).toEqual(["b", "m"]);
    expect(filterBySource(list, "claude_code").map((r) => r.id)).toEqual(["a"]);
    expect(filterBySource(list, "openrouter")).toEqual([]);
  });
});

describe("evidenceLines", () => {
  it("resume un patrón en texto plano", () => {
    expect(norm(evidenceLines(rec("a")))).toEqual(["4 sesiones en 3 días", "1,2 mil tokens", "Proyectos: app"]);
  });
  it("singular y sin proyectos", () => {
    const r = rec("a", { evidence: { sessions: 1, days: 1, tokens: 5, projects: [], sources: [], snippets: [] } });
    expect(norm(evidenceLines(r))).toEqual(["1 sesión en 1 día", "5 tokens"]);
  });
  it("una recomendación de costo muestra los ítems de la señal", () => {
    const r = rec("c", { kind: "costo", evidence: { rule: "spike_day", items: ["Día 20: 3× la mediana"], link: "/actividad?dia=2026-09-20", projects: [], sources: ["claude_code"] } });
    expect(evidenceLines(r)).toEqual(["Día 20: 3× la mediana"]);
  });
});

describe("acciones optimistas", () => {
  it("quitar y restaurar deja la lista igual, en la misma posición", () => {
    const list = [rec("a"), rec("b"), rec("c")];
    const { next, removed } = removeRecommendation(list, "b");
    expect(next.map((r) => r.id)).toEqual(["a", "c"]);
    expect(restoreRecommendation(next, removed).map((r) => r.id)).toEqual(["a", "b", "c"]);
  });
  it("restaurar no duplica si la recomendación ya volvió (p. ej. por una recarga)", () => {
    const list = [rec("a"), rec("b")];
    const { removed } = removeRecommendation(list, "b");
    expect(restoreRecommendation(list, removed).map((r) => r.id)).toEqual(["a", "b"]);
  });
  it("un id desconocido no cambia nada", () => {
    const { next, removed } = removeRecommendation([rec("a")], "zz");
    expect(next.map((r) => r.id)).toEqual(["a"]);
    expect(removed).toBeNull();
  });
});

describe("mensajes", () => {
  it("409 → corrida en curso; otro error → mensaje genérico", () => {
    expect(runErrorMessage(new HttpError("x", 409))).toBe("Ya hay una corrida en curso");
    expect(runErrorMessage(new Error("red caída"))).toBe("No se pudo iniciar el análisis (red caída)");
  });
  it("estados vacíos", () => {
    expect(emptyMessage("nueva", null)).toBe("Aún no hay corridas: pulsa Analizar ahora");
    expect(emptyMessage("nueva", RUN)).toBe("Sin patrones repetidos en los últimos 30 días");
    expect(emptyMessage("aplicada", RUN)).toBe("No has aplicado ninguna recomendación");
    expect(emptyMessage("saltada", RUN)).toBe("No has saltado ninguna recomendación");
    expect(emptyMessage("resuelta", RUN)).toBe("Ninguna recomendación se ha resuelto todavía");
  });
  it("modelo de la corrida", () => {
    expect(runModelLabel(RUN)).toBe("nous:upstage/solar-pro4:free");
    expect(runModelLabel({ ...RUN, model: null, status: "degraded" })).toBe("reglas locales");
    expect(runModelLabel({ ...RUN, backend: "claude", model: "claude" })).toBe("claude -p");
  });
  it("línea del Inicio", () => {
    expect(recommendationsLine(1)).toBe("1 recomendación nueva →");
    expect(recommendationsLine(4)).toBe("4 recomendaciones nuevas →");
  });
});

describe("isRunInProgress", () => {
  const data = (extra: Partial<RecommendationsResponse>): RecommendationsResponse =>
    ({ recommendations: [], last_run: RUN, running: false, degraded: false, ...extra });
  it("el servidor manda", () => expect(isRunInProgress(data({ running: true }), null)).toBe(true));
  it("una corrida pedida sigue en curso hasta verla terminada", () => {
    expect(isRunInProgress(data({ last_run: { ...RUN, id: 2 } }), 3)).toBe(true);
    expect(isRunInProgress(data({ last_run: { ...RUN, finished_at: null, status: "corriendo" } }), 3)).toBe(true);
    expect(isRunInProgress(data({}), 3)).toBe(false);
  });
  it("sin datos ni corrida pedida no hay nada en curso", () => expect(isRunInProgress(null, null)).toBe(false));
});

describe("parseChain", () => {
  it("una entrada por línea, sin vacías ni espacios", () => {
    expect(parseChain(" nous:a:free \n\n nous:b:free\n")).toEqual(["nous:a:free", "nous:b:free"]);
  });
});
```

- [ ] **Paso 2: correr los tests y verificar que fallan**

Run: `cd frontend && npx vitest run src/lib/recommendations.test.ts src/lib/api.test.ts 2>&1 | tail -8`
Esperado: FAIL con `Failed to resolve import "@/lib/recommendations"`.

- [ ] **Paso 3: implementar tipos y cliente en `api.ts`**

Al final de `frontend/src/lib/api.ts`:

```ts
export type RecommendationKind = "skill" | "plugin" | "prompt" | "costo";
export type RecommendationImpact = "alto" | "medio" | "bajo";
export type RecommendationStatus = "nueva" | "aplicada" | "saltada" | "resuelta";
export type UserStatus = Exclude<RecommendationStatus, "resuelta">;

export interface PatternEvidence {
  sessions: number;
  days: number;
  tokens: number;
  projects: string[];
  sources: string[];
  snippets: string[];
}

export interface CostEvidence {
  rule: string;
  items: string[];
  link: string;
  projects: string[];
  sources: string[];
}

export interface Recommendation {
  id: string;
  first_seen: string;
  last_seen: string;
  /** Fuente única o "varias". */
  tool: string;
  tokens: number;
  pattern: string;
  kind: RecommendationKind;
  description: string;
  impact: RecommendationImpact;
  evidence: PatternEvidence | CostEvidence;
  draft: string;
  status: RecommendationStatus;
  status_at: string | null;
  /** "reglas", "costo" o el modelo que la redactó. */
  generator: string;
}

export interface RecommendationRun {
  id: number;
  started_at: string;
  finished_at: string | null;
  trigger: "diario" | "manual";
  backend: EngineBackend;
  model: string | null;
  attempts: number;
  status: "corriendo" | "ok" | "degraded" | "error";
  prompts: number | null;
  clusters: number | null;
  created: number | null;
  updated: number | null;
  resolved: number | null;
  error: string | null;
  llm_tokens: number | null;
  llm_cost: number | null;
}

export interface RecommendationsResponse {
  recommendations: Recommendation[];
  last_run: RecommendationRun | null;
  running: boolean;
  degraded: boolean;
}

export type EngineBackend = "hermes" | "claude" | "none";

export interface EngineSettings {
  backend: EngineBackend;
  llm_chain: string[];
}

const JSON_POST = { method: "POST", headers: { "Content-Type": "application/json" } } as const;

export function fetchRecommendations(status: RecommendationStatus): Promise<RecommendationsResponse> {
  return getJson(`/api/recommendations?estado=${status}`);
}

export function setRecommendationStatus(id: string, status: UserStatus): Promise<Recommendation> {
  return getJson(`/api/recommendations/${encodeURIComponent(id)}/estado`, { ...JSON_POST, body: JSON.stringify({ status }) });
}

/** Cuerpo JSON obligatorio: el servidor rechaza con 415 cualquier otro tipo (defensa CSRF). */
export function runRecommendations(): Promise<{ run_id: number }> {
  return getJson("/api/recommendations/run", { ...JSON_POST, body: "{}" });
}

export function fetchEngineSettings(): Promise<EngineSettings> {
  return getJson("/api/engine-settings");
}

export function saveEngineSettings(settings: EngineSettings): Promise<EngineSettings> {
  return getJson("/api/engine-settings", { ...JSON_POST, body: JSON.stringify(settings) });
}
```

- [ ] **Paso 4: implementar `lib/recommendations.ts`**

```ts
// frontend/src/lib/recommendations.ts
/** Lógica pura de la vista Recomendaciones (testeable sin DOM). */
import {
  HttpError, type CostEvidence, type EngineBackend, type Recommendation, type RecommendationImpact,
  type RecommendationKind, type RecommendationRun, type RecommendationStatus, type RecommendationsResponse,
} from "@/lib/api";
import { formatCompact } from "@/lib/format";
import type { SourceKey } from "@/lib/sources";
import { basename } from "@/lib/tree";

export const REC_TABS: { status: RecommendationStatus; label: string }[] = [
  { status: "nueva", label: "Nuevas" },
  { status: "aplicada", label: "Aplicadas" },
  { status: "saltada", label: "Saltadas" },
  { status: "resuelta", label: "Resueltas" },
];

export function parseRecTab(value: string | null): RecommendationStatus {
  return REC_TABS.find((t) => t.status === value)?.status ?? "nueva";
}

export const KIND_LABEL: Record<RecommendationKind, string> = {
  skill: "Skill", plugin: "Plugin", prompt: "Prompt", costo: "Costo",
};

export const IMPACT_LABEL: Record<RecommendationImpact, string> = {
  alto: "Impacto alto", medio: "Impacto medio", bajo: "Impacto bajo",
};

export const BACKEND_OPTIONS: { value: EngineBackend; label: string; hint: string }[] = [
  { value: "hermes", label: "Hermes", hint: "Modelos free en cadena; no consume tu suscripción." },
  { value: "claude", label: "claude -p", hint: "Usa tu suscripción de Claude; aparece como proyecto motor-recomendaciones." },
  { value: "none", label: "Ninguno", hint: "Solo reglas locales: agrupación léxica y textos por plantilla." },
];

export function isCostEvidence(evidence: Recommendation["evidence"]): evidence is CostEvidence {
  return "rule" in evidence;
}

/** ?fuente=: la fuente única de la recomendación o cualquiera de las de un patrón compartido. */
export function filterBySource(recs: Recommendation[], source: SourceKey): Recommendation[] {
  if (source === "all") return recs;
  return recs.filter((r) => r.tool === source || r.evidence.sources.includes(source));
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

export function evidenceLines(rec: Recommendation): string[] {
  const ev = rec.evidence;
  if (isCostEvidence(ev)) return ev.items;
  const lines = [
    `${plural(ev.sessions, "sesión", "sesiones")} en ${plural(ev.days, "día", "días")}`,
    `${formatCompact(ev.tokens)} tokens`,
  ];
  if (ev.projects.length) lines.push(`Proyectos: ${ev.projects.map(basename).join(", ")}`);
  return lines;
}

export function runErrorMessage(err: unknown): string {
  if (err instanceof HttpError && err.status === 409) return "Ya hay una corrida en curso";
  return `No se pudo iniciar el análisis (${err instanceof Error ? err.message : String(err)})`;
}

export interface Removed {
  rec: Recommendation;
  index: number;
}

/** Acción optimista: la tarjeta sale de la pestaña actual antes de que responda el servidor. */
export function removeRecommendation(list: Recommendation[], id: string): { next: Recommendation[]; removed: Removed | null } {
  const index = list.findIndex((r) => r.id === id);
  if (index < 0) return { next: list, removed: null };
  return { next: [...list.slice(0, index), ...list.slice(index + 1)], removed: { rec: list[index], index } };
}

/** Reversión si el servidor rechaza el cambio. */
export function restoreRecommendation(list: Recommendation[], removed: Removed | null): Recommendation[] {
  if (!removed || list.some((r) => r.id === removed.rec.id)) return list;
  const index = Math.min(removed.index, list.length);
  return [...list.slice(0, index), removed.rec, ...list.slice(index)];
}

const EMPTY: Record<RecommendationStatus, string> = {
  nueva: "Sin patrones repetidos en los últimos 30 días",
  aplicada: "No has aplicado ninguna recomendación",
  saltada: "No has saltado ninguna recomendación",
  resuelta: "Ninguna recomendación se ha resuelto todavía",
};

export function emptyMessage(tab: RecommendationStatus, lastRun: RecommendationRun | null): string {
  return lastRun ? EMPTY[tab] : "Aún no hay corridas: pulsa Analizar ahora";
}

export function runModelLabel(run: RecommendationRun): string {
  if (!run.model) return "reglas locales";
  return run.backend === "claude" ? "claude -p" : run.model;
}

/** En curso si el servidor lo dice o si la corrida que pidió esta pestaña aún no aparece terminada. */
export function isRunInProgress(data: RecommendationsResponse | null, pendingRunId: number | null): boolean {
  if (data?.running) return true;
  if (pendingRunId === null) return false;
  const last = data?.last_run;
  return !last || last.id < pendingRunId || last.finished_at === null;
}

export function recommendationsLine(count: number): string {
  return count === 1 ? "1 recomendación nueva →" : `${count} recomendaciones nuevas →`;
}

export function parseChain(text: string): string[] {
  return text.split("\n").map((line) => line.trim()).filter(Boolean);
}
```

- [ ] **Paso 5: hooks**

```ts
// frontend/src/hooks/useRecommendations.ts
import { useCallback, useEffect, useState } from "react";
import { fetchRecommendations, type RecommendationStatus, type RecommendationsResponse } from "@/lib/api";

export type RecommendationsState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: RecommendationsResponse };

/** `refreshKey` cambia con cada evento SSE `recommendations` o tras una acción del usuario. */
export function useRecommendations(tab: RecommendationStatus, refreshKey: unknown) {
  const [state, setState] = useState<RecommendationsState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchRecommendations(tab)
      .then((data) => !cancelled && setState({ status: "ready", data }))
      .catch((err: Error) => {
        // Con datos en pantalla, una revalidación fallida no los reemplaza por un error.
        if (!cancelled) setState((prev) => (prev.status === "ready" ? prev : { status: "error", message: err.message }));
      });
    return () => {
      cancelled = true;
    };
  }, [tab, refreshKey, attempt]);

  // Cambiar de pestaña muestra el skeleton en vez de las tarjetas de la pestaña anterior.
  useEffect(() => setState({ status: "loading" }), [tab]);

  const update = useCallback(
    (fn: (data: RecommendationsResponse) => RecommendationsResponse) =>
      setState((prev) => (prev.status === "ready" ? { status: "ready", data: fn(prev.data) } : prev)),
    [],
  );
  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { state, update, retry };
}

/** Badge del sidebar y línea del Inicio. Un fallo cuenta como 0: no es crítico. */
export function useNewRecommendationsCount(refreshKey: unknown): number {
  const [count, setCount] = useState(0);
  useEffect(() => {
    let cancelled = false;
    fetchRecommendations("nueva")
      .then((data) => !cancelled && setCount(data.recommendations.length))
      .catch(() => !cancelled && setCount(0));
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);
  return count;
}
```

En `frontend/src/hooks/useUsageStream.ts`: añade `const [recommendationsVersion, setRecommendationsVersion] = useState(0);`, dentro del `useEffect` el listener

```ts
    es.addEventListener("recommendations", () => setRecommendationsVersion((n) => n + 1));
```

y `recommendationsVersion` en el objeto que devuelve el hook.

- [ ] **Paso 6: verificar**

Run: `cd frontend && npx vitest run && npx oxlint && npx tsc -b --noEmit 2>&1 | tail -8`
Esperado: todos los tests en verde, oxlint sin errores y `tsc` sin salida. `formatCompact` usa el locale es-CO (`1200` → `"1,2 mil"` con espacio no separable; por eso el test normaliza).

- [ ] **Paso 7: commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/api.test.ts frontend/src/lib/recommendations.ts \
  frontend/src/lib/recommendations.test.ts frontend/src/hooks/useRecommendations.ts frontend/src/hooks/useUsageStream.ts
git commit -m "feat(frontend): cliente, lógica pura y hooks de recomendaciones"
```

---

### Tarea 12: Ruta, navegación y vista Recomendaciones

**Archivos:**
- Modificar: `frontend/src/lib/routes.ts`, `frontend/src/lib/routes.test.ts`, `frontend/src/lib/commands.ts`, `frontend/src/lib/commands.test.ts`, `frontend/src/components/Sidebar.tsx`, `frontend/src/App.tsx`
- Crear: `frontend/src/views/RecommendationsView.tsx`, `frontend/src/components/recommendations/RecommendationCard.tsx`

**Interfaces:**
- Consume: Tarea 11 completa; `SourceChip`, `SectionFallback`, `withSource`, `withQuery`, `Button`.
- Produce:
  - `ViewKey` incluye `"recommendations"` → `/recomendaciones`, con `?estado=aplicada|saltada|resuelta` (ausente = nueva) y `?fuente=`.
  - `REC_STATUS_PARAM = "estado"` en `routes.ts`.
  - `AppSidebar` recibe la prop `newRecommendations: number`.
  - `RecommendationsView({ source, refreshKey, onChange })`, donde `onChange()` avisa a `App` de que cambió algo (refresca el badge y el Inicio).

- [ ] **Paso 1: tests que fallan**

En `frontend/src/lib/routes.test.ts`, dentro del `it` de rutas conocidas de `describe("parsePath")`, añade:

```ts
    expect(parsePath("/recomendaciones")).toEqual({ view: "recommendations", client: null });
```

y en el de rutas desconocidas:

```ts
    expect(parsePath("/recomendaciones/otra")).toBeNull();
```

(El `it.each(VIEW_KEYS)` existente cubre el ida y vuelta de `viewPath` en cuanto la clave exista.)

En `frontend/src/lib/commands.test.ts`, reemplaza el test de las vistas:

```ts
  it("incluye las siete vistas", () => {
    expect(byGroup("Vistas").map((e) => e.to)).toEqual([
      "/", "/actividad", "/gasto", "/gasto/roi", "/proyectos", "/recomendaciones", "/configuracion",
    ]);
  });
```

Run: `cd frontend && npx vitest run src/lib/routes.test.ts src/lib/commands.test.ts 2>&1 | tail -6`
Esperado: FAIL (`/recomendaciones` devuelve `null` y el ⌘K tiene 6 vistas).

- [ ] **Paso 2: `routes.ts` y `commands.ts`**

En `routes.ts`:
- En el comentario de cabecera, bajo `/configuracion`, añade ` *   /recomendaciones         → recomendaciones del motor (?estado=aplicada|saltada|resuelta)`.
- `export const VIEW_KEYS = ["home", "activity", "spend", "roi", "projects", "recommendations", "settings"] as const;`
- `export const REC_STATUS_PARAM = "estado";` junto a las otras constantes `*_PARAM`.
- En `VIEW_PATH`: `recommendations: "/recomendaciones",` antes de `settings`.
- En `parsePath`, antes de la línea de `configuracion`:

```ts
  if (head === "recomendaciones" && rest.length === 0) return { view: "recommendations", client: null };
```

En `commands.ts`, en `VIEWS`, antes de `settings`:

```ts
  { view: "recommendations", label: "Recomendaciones", keywords: ["motor", "skills", "plugins", "prompts", "sugerencias"] },
```

Run: `cd frontend && npx vitest run src/lib/routes.test.ts src/lib/commands.test.ts 2>&1 | tail -3`
Esperado: PASS.

- [ ] **Paso 3: sidebar**

En `frontend/src/components/Sidebar.tsx`:
- Añade a `NAV`, tras Proyectos: `{ views: ["recommendations"], to: "recommendations", label: "Recomendaciones", icon: Lightbulb },`.
- Añade `newRecommendations: number;` a `AppSidebarProps` y recíbela en la desestructuración.
- Tras el `</SidebarMenuButton>` del `map`, antes del bloque de clientes:

```tsx
                      {item.to === "recommendations" && newRecommendations > 0 && (
                        <SidebarMenuBadge aria-label={`${newRecommendations} nuevas`}>{newRecommendations}</SidebarMenuBadge>
                      )}
```

- Borra el `<SidebarMenuItem>` deshabilitado con el badge "pronto" (el de `disabled aria-disabled="true"`).

- [ ] **Paso 4: la tarjeta**

```tsx
// frontend/src/components/recommendations/RecommendationCard.tsx
import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Check, Copy, Undo2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SourceChip } from "@/components/SourceChip";
import type { Recommendation, UserStatus } from "@/lib/api";
import { IMPACT_LABEL, KIND_LABEL, evidenceLines, isCostEvidence } from "@/lib/recommendations";
import { withSource } from "@/lib/routes";
import { cn } from "@/lib/utils";

const IMPACT_CLASS = {
  alto: "border-amber-500/40 text-amber-700 dark:text-amber-400",
  medio: "border-link/40 text-link",
  bajo: "text-muted-foreground",
} as const;

interface Props {
  rec: Recommendation;
  onStatus: (status: UserStatus) => void;
}

/** Todo el texto viene del LLM o del usuario: se renderiza siempre como texto plano. */
export function RecommendationCard({ rec, onStatus }: Props) {
  const { search } = useLocation();
  const [copied, setCopied] = useState(false);
  const ev = rec.evidence;
  const sources = rec.tool === "varias" ? ev.sources : [rec.tool];

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(rec.draft);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("No se pudo copiar el borrador:", err);
    }
  };

  return (
    <article aria-labelledby={`rec-${rec.id}`} className="min-w-0 space-y-3 rounded-xl border bg-card p-5">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded-full bg-muted px-2 py-0.5 font-medium">{KIND_LABEL[rec.kind]}</span>
        <span className={cn("rounded-full border px-2 py-0.5", IMPACT_CLASS[rec.impact])}>{IMPACT_LABEL[rec.impact]}</span>
        {sources.map((s) => <SourceChip key={s} source={s} />)}
      </div>
      <h2 id={`rec-${rec.id}`} className="break-words text-base font-semibold">{rec.pattern}</h2>
      <p className="break-words text-sm text-muted-foreground">{rec.description}</p>

      <details className="text-sm">
        <summary className="cursor-pointer select-none font-medium">Evidencia</summary>
        <ul className="mt-2 space-y-0.5 text-xs text-muted-foreground">
          {evidenceLines(rec).map((line) => <li key={line} className="break-words">{line}</li>)}
        </ul>
        {!isCostEvidence(ev) && ev.snippets.length > 0 && (
          <ul className="mt-2 space-y-1">
            {ev.snippets.map((s) => (
              <li key={s} className="break-words border-l-2 pl-2 text-xs italic text-muted-foreground">“{s}”</li>
            ))}
          </ul>
        )}
        {isCostEvidence(ev) && (
          <Link to={withSource(ev.link, search)} className="mt-2 inline-block text-xs text-link underline-offset-4 hover:underline">
            Ver en el dashboard
          </Link>
        )}
      </details>

      <div className="relative">
        <pre className="max-h-72 overflow-y-auto whitespace-pre-wrap break-words rounded-lg bg-muted p-3 pr-24 text-xs">
          <code>{rec.draft}</code>
        </pre>
        <Button size="sm" variant="outline" onClick={copy} className="absolute right-2 top-2">
          {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
          {copied ? "Copiado" : "Copiar"}
        </Button>
      </div>

      <div className="flex flex-wrap gap-2">
        {rec.status === "nueva" && (
          <>
            <Button size="sm" onClick={() => onStatus("aplicada")}>Aplicar<span className="sr-only">: {rec.pattern}</span></Button>
            <Button size="sm" variant="outline" onClick={() => onStatus("saltada")}>Saltar<span className="sr-only">: {rec.pattern}</span></Button>
          </>
        )}
        {(rec.status === "aplicada" || rec.status === "saltada") && (
          <Button size="sm" variant="outline" onClick={() => onStatus("nueva")}>
            <Undo2 aria-hidden />Deshacer<span className="sr-only">: {rec.pattern}</span>
          </Button>
        )}
      </div>
    </article>
  );
}
```

Si `Button` no acepta `size="sm"` o `variant="outline"`, usa las variantes que exporte `components/ui/button.tsx` (míralas en su `cva`); no añadas variantes nuevas.

- [ ] **Paso 5: la vista**

```tsx
// frontend/src/views/RecommendationsView.tsx
import { useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { AlertCircle, Loader2, RotateCw, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { RecommendationCard } from "@/components/recommendations/RecommendationCard";
import { SectionFallback } from "@/views/SectionFallback";
import { useRecommendations } from "@/hooks/useRecommendations";
import { runRecommendations, setRecommendationStatus, type Recommendation, type UserStatus } from "@/lib/api";
import {
  REC_TABS, emptyMessage, filterBySource, isRunInProgress, parseRecTab, removeRecommendation,
  restoreRecommendation, runErrorMessage, runModelLabel,
} from "@/lib/recommendations";
import { REC_STATUS_PARAM, withQuery, withSource } from "@/lib/routes";
import type { SourceKey } from "@/lib/sources";
import { cn } from "@/lib/utils";

const whenFormat = new Intl.DateTimeFormat("es", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

interface Props {
  source: SourceKey;
  refreshKey: unknown;
  onChange: () => void;
}

export function RecommendationsView({ source, refreshKey, onChange }: Props) {
  const { search } = useLocation();
  const [params] = useSearchParams();
  const tab = parseRecTab(params.get(REC_STATUS_PARAM));
  const { state, update, retry } = useRecommendations(tab, refreshKey);
  const [pendingRunId, setPendingRunId] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const data = state.status === "ready" ? state.data : null;
  const running = isRunInProgress(data, pendingRunId);

  const analyze = async () => {
    setNotice(null);
    try {
      const { run_id } = await runRecommendations();
      setPendingRunId(run_id);
    } catch (err) {
      setNotice(runErrorMessage(err));
    }
  };

  const changeStatus = async (rec: Recommendation, status: UserStatus) => {
    setNotice(null);
    let removed: ReturnType<typeof removeRecommendation>["removed"] = null;
    update((d) => {
      const result = removeRecommendation(d.recommendations, rec.id);
      removed = result.removed;
      return { ...d, recommendations: result.next };
    });
    try {
      await setRecommendationStatus(rec.id, status);
      onChange();
    } catch (err) {
      update((d) => ({ ...d, recommendations: restoreRecommendation(d.recommendations, removed) }));
      setNotice(`No se pudo actualizar la recomendación (${err instanceof Error ? err.message : String(err)})`);
    }
  };

  const tabHref = (status: string) => {
    const next = new URLSearchParams(search);
    if (status === "nueva") next.delete(REC_STATUS_PARAM);
    else next.set(REC_STATUS_PARAM, status);
    return withQuery("/recomendaciones", next);
  };

  const last = data?.last_run ?? null;

  return (
    <div className="min-w-0 space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <h1 className="text-xl font-semibold">Recomendaciones</h1>
          {last && (
            <p className="break-words text-sm text-muted-foreground">
              Última corrida: {whenFormat.format(new Date(last.started_at))} · {runModelLabel(last)}
              {last.status === "degraded" && <span className="ml-2 rounded-full border px-2 py-0.5 text-xs">degradado (reglas)</span>}
              {last.status === "error" && <span className="ml-2 rounded-full border border-destructive/50 px-2 py-0.5 text-xs text-destructive">falló</span>}
            </p>
          )}
        </div>
        <Button onClick={analyze} disabled={running} aria-busy={running}>
          {running ? <Loader2 className="animate-spin" aria-hidden /> : <Sparkles aria-hidden />}
          {running ? "Analizando…" : "Analizar ahora"}
        </Button>
      </div>

      {notice && (
        <p role="status" className="flex items-center gap-2 rounded-lg border bg-muted px-3 py-2 text-sm">
          <AlertCircle className="h-4 w-4 shrink-0" aria-hidden />{notice}
        </p>
      )}
      {data?.degraded && (
        <p role="status" className="rounded-lg border bg-muted px-3 py-2 text-sm text-muted-foreground">
          Historial no disponible temporalmente
        </p>
      )}

      <nav aria-label="Estado de las recomendaciones" className="flex max-w-full flex-wrap gap-1 rounded-lg border p-1">
        {REC_TABS.map((t) => (
          <Link
            key={t.status}
            to={tabHref(t.status)}
            aria-current={tab === t.status ? "page" : undefined}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm",
              tab === t.status ? "bg-muted font-medium shadow-[inset_0_-2px_0_var(--primary)]" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
          </Link>
        ))}
      </nav>

      {state.status === "loading" && <SectionFallback label="Cargando recomendaciones" />}
      {state.status === "error" && (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl border bg-card p-5 text-sm">
          <AlertCircle className="h-4 w-4 shrink-0 text-destructive" aria-hidden />
          <span className="min-w-0 flex-1 break-words">No se pudieron cargar las recomendaciones ({state.message}).</span>
          <Button variant="outline" size="sm" onClick={retry}><RotateCw aria-hidden />Reintentar</Button>
        </div>
      )}
      {data && (() => {
        const visible = filterBySource(data.recommendations, source);
        if (visible.length === 0) {
          return <p className="rounded-xl border bg-card p-8 text-center text-sm text-muted-foreground">{emptyMessage(tab, last)}</p>;
        }
        return (
          <div className="grid min-w-0 grid-cols-1 gap-4 xl:grid-cols-2">
            {visible.map((rec) => (
              <RecommendationCard key={rec.id} rec={rec} onStatus={(status) => changeStatus(rec, status)} />
            ))}
          </div>
        );
      })()}
      <p className="text-xs text-muted-foreground">
        Las recomendaciones se generan cada día a las 07:00. Configura el motor en{" "}
        <Link to={withSource("/configuracion", search)} className="text-link underline-offset-4 hover:underline">Configuración</Link>.
      </p>
    </div>
  );
}
```

Nota: con `refreshKey` cambiando tras el evento SSE, `useRecommendations` recarga y `isRunInProgress` ve la corrida terminada; el botón vuelve a "Analizar ahora" sin estado extra. `pendingRunId` no se limpia a mano: una vez terminada esa corrida deja de influir.

- [ ] **Paso 6: cablear en `App.tsx`**

```tsx
import { useReducer } from "react";
import { useNewRecommendationsCount } from "@/hooks/useRecommendations";
import { RecommendationsView } from "@/views/RecommendationsView";
```

Dentro de `App`, antes de los `return` tempranos (las reglas de hooks lo exigen):

```tsx
  const { sources, combined, connected, recommendationsVersion } = useUsageStream();
  const [localVersion, bumpRecommendations] = useReducer((n: number) => n + 1, 0);
  const recommendationsKey = `${recommendationsVersion}:${localVersion}`;
  const newRecommendations = useNewRecommendationsCount(recommendationsKey);
```

(Reemplaza la desestructuración actual de `useUsageStream()` por la de arriba.)

- `<AppSidebar ... newRecommendations={newRecommendations} />`
- Tras el bloque de `projects`:

```tsx
          {route.view === "recommendations" && (
            <RecommendationsView source={route.source} refreshKey={recommendationsKey} onChange={bumpRecommendations} />
          )}
```

- [ ] **Paso 7: verificar**

Run: `cd frontend && npx vitest run && npx oxlint && npm run build 2>&1 | tail -5`
Esperado: tests en verde, oxlint sin errores y build correcto.

- [ ] **Paso 8: commit**

```bash
git add frontend/src/lib/routes.ts frontend/src/lib/routes.test.ts frontend/src/lib/commands.ts \
  frontend/src/lib/commands.test.ts frontend/src/components/Sidebar.tsx frontend/src/App.tsx \
  frontend/src/views/RecommendationsView.tsx frontend/src/components/recommendations/RecommendationCard.tsx
git commit -m "feat(frontend): vista Recomendaciones con pestañas, acciones optimistas y Analizar ahora"
```

---

### Tarea 13: Configuración del motor y línea en el Inicio

**Archivos:**
- Crear: `frontend/src/components/EngineSettingsForm.tsx`
- Modificar: `frontend/src/views/SettingsView.tsx`, `frontend/src/components/home/HomeView.tsx`, `frontend/src/components/home/AttentionList.tsx`, `frontend/src/App.tsx`

**Interfaces:**
- Consume: `fetchEngineSettings`, `saveEngineSettings`, `HttpError`, `BACKEND_OPTIONS`, `parseChain` y `recommendationsLine` (Tarea 11); `newRecommendations` de `App` (Tarea 12).
- Produce: sección "Motor de recomendaciones" en Configuración. `HomeView` y `AttentionList` reciben la prop `newRecommendations: number`.

- [ ] **Paso 1: `EngineSettingsForm`**

```tsx
// frontend/src/components/EngineSettingsForm.tsx
import { useEffect, useState } from "react";
import { AlertCircle, Check, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { HttpError, fetchEngineSettings, saveEngineSettings, type EngineBackend } from "@/lib/api";
import { BACKEND_OPTIONS, parseChain } from "@/lib/recommendations";

interface Draft {
  backend: EngineBackend;
  chain: string;
}

export function EngineSettingsForm() {
  const [draft, setDraft] = useState<Draft | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    fetchEngineSettings()
      .then((s) => setDraft({ backend: s.backend, chain: s.llm_chain.join("\n") }))
      .catch((err: Error) => setLoadError(err.message));
  }, []);

  if (loadError) {
    return (
      <div role="alert" className="flex items-center gap-2 rounded-xl border bg-card p-5 text-sm">
        <AlertCircle className="h-4 w-4 shrink-0 text-destructive" aria-hidden />
        No se pudo cargar la configuración del motor ({loadError}).
      </div>
    );
  }
  if (!draft) return <Skeleton className="h-64 w-full rounded-xl" />;

  const edit = (next: Partial<Draft>) => {
    setDraft({ ...draft, ...next });
    setSaveStatus("idle");
  };

  const handleSave = async () => {
    setSaveStatus("saving");
    setSaveError(null);
    try {
      const saved = await saveEngineSettings({ backend: draft.backend, llm_chain: parseChain(draft.chain) });
      setDraft({ backend: saved.backend, chain: saved.llm_chain.join("\n") });
      setSaveStatus("saved");
    } catch (err) {
      // Un 400 trae el motivo del backend (p. ej. un modelo no free con Hermes).
      setSaveError(err instanceof HttpError && err.status === 400 ? err.message.split(": ").slice(1).join(": ") : null);
      setSaveStatus("error");
    }
  };

  return (
    <section aria-labelledby="engine-title" className="space-y-4 rounded-xl border bg-card p-5">
      <div>
        <h2 id="engine-title" className="text-sm font-medium">Motor de recomendaciones</h2>
        <p className="mt-1 text-xs text-muted-foreground">Qué modelo redacta las recomendaciones de la corrida diaria y de Analizar ahora.</p>
      </div>
      <fieldset className="space-y-2">
        <legend className="text-sm">Backend</legend>
        {BACKEND_OPTIONS.map((option) => (
          <label key={option.value} className="flex items-start gap-2 text-sm">
            <input
              type="radio"
              name="engine-backend"
              value={option.value}
              checked={draft.backend === option.value}
              onChange={() => edit({ backend: option.value })}
              className="mt-1"
            />
            <span className="min-w-0">
              <span className="font-medium">{option.label}</span>
              <span className="block text-xs text-muted-foreground">{option.hint}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <label className="block space-y-1 text-sm">
        <span>Cadena de modelos (uno por línea, en orden de preferencia; formato proveedor:modelo)</span>
        <textarea
          value={draft.chain}
          onChange={(e) => edit({ chain: e.target.value })}
          disabled={draft.backend !== "hermes"}
          rows={4}
          spellCheck={false}
          className="w-full rounded-lg border bg-background p-2 font-mono text-xs disabled:opacity-60"
        />
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={handleSave} disabled={saveStatus === "saving"}>
          <Save aria-hidden />Guardar
        </Button>
        <span role="status" className="text-sm">
          {saveStatus === "saved" && <span className="inline-flex items-center gap-1"><Check className="h-4 w-4" aria-hidden />Cambios guardados</span>}
          {saveStatus === "error" && <span className="text-destructive">No se pudo guardar{saveError ? `: ${saveError}` : ""}</span>}
        </span>
      </div>
    </section>
  );
}
```

En `SettingsView.tsx`: importa `EngineSettingsForm` y colócalo entre `<SettingsForm />` y la sección de Fuentes.

- [ ] **Paso 2: línea en el Inicio**

En `AttentionList.tsx`, cambia la firma a `({ signals, search, newRecommendations = 0 }: { signals: BriefingSignal[]; search: string; newRecommendations?: number })`, importa `recommendationsLine` de `@/lib/recommendations` y, justo antes del `</section>`, añade:

```tsx
      {newRecommendations > 0 && (
        <Link
          to={withSource("/recomendaciones", search)}
          className="mt-3 inline-block border-t pt-3 text-sm text-link underline-offset-4 hover:underline"
        >
          {recommendationsLine(newRecommendations)}
        </Link>
      )}
```

En `HomeView.tsx`: añade `newRecommendations: number` a `HomeViewProps`, recíbela y pásala: `<AttentionList signals={b.attention} search={search} newRecommendations={newRecommendations} />`.

En `App.tsx`: `<HomeView ... newRecommendations={newRecommendations} />`.

- [ ] **Paso 3: verificar**

Run: `cd frontend && npx vitest run && npx oxlint && npm run build 2>&1 | tail -5`
Esperado: todo en verde.

- [ ] **Paso 4: commit**

```bash
git add frontend/src/components/EngineSettingsForm.tsx frontend/src/views/SettingsView.tsx \
  frontend/src/components/home/HomeView.tsx frontend/src/components/home/AttentionList.tsx frontend/src/App.tsx
git commit -m "feat(frontend): configuración del motor y aviso de recomendaciones nuevas en el Inicio"
```

---

### Tarea 14: E2E con Playwright, portabilidad y verificación de cierre

**Archivos:**
- Crear (fuera del repo, en el scratchpad de la sesión; `$SCRATCH` en los comandos): `e2e_server.py` y `e2e.cjs`.
- No se commitea nada de esta tarea salvo arreglos que salgan de ella (cada uno con su test y su commit).

**Interfaces:**
- Consume: todo lo anterior; `server.build_app(..., engine_opts=...)`; `frontend/dist` compilado.
- Produce: evidencia de que el flujo completo funciona en el navegador.

- [ ] **Paso 1: servidor E2E con datos sintéticos**

```python
# $SCRATCH/e2e_server.py — uso: python3 e2e_server.py <repo> <tmpdir>
import json
import os
import sys
from datetime import date
from unittest.mock import patch

repo, tmp = sys.argv[1], sys.argv[2]
sys.path.insert(0, repo)
import server  # noqa: E402
from recommend import store  # noqa: E402

db = os.path.join(tmp, "history.db")
cc_root = os.path.join(tmp, "claude-projects", "-home-u-DEV-ACME-app")
os.makedirs(cc_root, exist_ok=True)
# Tres sesiones en tres días con el mismo pedido (sintético): la corrida manual lo detecta en modo léxico.
for i, day in enumerate(("2026-09-18", "2026-09-19", "2026-09-20")):
    with open(os.path.join(cc_root, f"s{i}.jsonl"), "w") as fh:
        fh.write(json.dumps({"type": "user", "timestamp": f"{day}T10:00:00Z", "cwd": "/home/u/DEV/ACME/app",
                             "sessionId": f"s{i}", "message": {"role": "user", "content":
                             "revisa los logs del servicio de pagos y dime por qué falla el cobro con tarjeta"}}) + "\n")

store.save_engine_settings({"backend": "none", "llm_chain": ["nous:upstage/solar-pro4:free"]}, db)
evidence = {"sessions": 5, "days": 4, "tokens": 48000, "projects": ["/home/u/DEV/ACME/app"],
            "sources": ["claude_code"], "snippets": ["genera el changelog de la versión"]}
store.apply_run(db, [
    {"tool": "claude_code", "tokens": 48000, "pattern": "Generar el changelog de cada versión", "kind": "skill",
     "description": "Lo pides en cada release.", "impact": "alto", "evidence": evidence,
     "draft": "---\nname: changelog\n---\n1. Lee los commits\n2. <b>no es html</b>",
     "signature": [f"a {i}" for i in range(10)], "generator": "reglas"},
    {"tool": "codex", "tokens": 9000, "pattern": "Consultar el estado de Jira", "kind": "plugin",
     "description": "Pegas tickets a mano.", "impact": "medio", "evidence": {**evidence, "sources": ["codex"]},
     "draft": "Instala el MCP de Jira", "signature": [f"b {i}" for i in range(10)], "generator": "reglas"},
], [], "2026-09-20T07:00:00+00:00")

missing = os.path.join(tmp, "no-existe")
opts = {"lock_path": os.path.join(tmp, "recommend.lock"), "engine_dir": os.path.join(tmp, "motor"),
        "today": date(2026, 9, 21), "session_tokens": {},
        "prompt_overrides": {"claude_code": os.path.dirname(cc_root), "codex": missing,
                             "opencode": missing + ".db", "hermes": missing + ".db"}}
empty = {"claude_code": {}, "codex": {}, "opencode": {}, "hermes": {}, "openrouter": {"unavailable": True, "reason": "e2e"}}
with patch("server.main.collect_all", return_value=empty):
    httpd = server.build_app(os.path.join(repo, "frontend", "dist"), poll_interval_seconds=3600,
                             port=8431, db_path=db, engine_opts=opts)
    print("e2e listo en http://127.0.0.1:8431", flush=True)
    httpd.serve_forever()
```

Run (en segundo plano): `cd frontend && npm run build && cd .. && SCRATCH=<scratchpad>; T=$(mktemp -d -p "$SCRATCH"); python3 "$SCRATCH/e2e_server.py" "$PWD" "$T"`
Esperado: `e2e listo en http://127.0.0.1:8431`. Usa un puerto libre distinto de 8420: el servicio real del usuario puede estar corriendo y **no** se reinicia.

- [ ] **Paso 2: script de Playwright**

```js
// $SCRATCH/e2e.cjs — uso: NODE_PATH=frontend/node_modules node $SCRATCH/e2e.cjs
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const BASE = "http://127.0.0.1:8431";

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({ permissions: ["clipboard-read", "clipboard-write"] });
  const page = await context.newPage();
  const errors = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));

  // Inicio: línea de recomendaciones nuevas y badge del sidebar.
  await page.goto(BASE + "/");
  await page.getByRole("link", { name: "2 recomendaciones nuevas →" }).waitFor();
  await page.getByRole("link", { name: "2 recomendaciones nuevas →" }).click();
  await page.getByRole("heading", { name: "Recomendaciones" }).waitFor();
  assert.equal(await page.getByLabel("2 nuevas").count(), 1);

  // Tarjeta: texto plano (sin HTML interpretado), evidencia y copiar.
  const card = page.getByRole("article", { name: "Generar el changelog de cada versión" });
  assert.match(await card.locator("pre").innerText(), /<b>no es html<\/b>/);
  await card.getByText("Evidencia").click();
  await card.getByText("5 sesiones en 4 días").waitFor();
  await card.getByRole("button", { name: /Copiar/ }).click();
  assert.match(await page.evaluate(() => navigator.clipboard.readText()), /name: changelog/);

  // ?fuente= filtra por fuente.
  await page.goto(BASE + "/recomendaciones?fuente=codex");
  await page.getByRole("article", { name: "Consultar el estado de Jira" }).waitFor();
  assert.equal(await page.getByRole("article").count(), 1);

  // Aplicar → pestaña Aplicadas → Deshacer; Saltar.
  await page.goto(BASE + "/recomendaciones");
  await card.getByRole("button", { name: /^Aplicar/ }).click();
  await card.waitFor({ state: "detached" });
  await page.getByRole("link", { name: "Aplicadas" }).click();
  await card.getByRole("button", { name: /Deshacer/ }).click();
  await card.waitFor({ state: "detached" });
  await page.getByRole("link", { name: "Nuevas" }).click();
  const jira = page.getByRole("article", { name: "Consultar el estado de Jira" });
  await jira.getByRole("button", { name: /^Saltar/ }).click();
  await jira.waitFor({ state: "detached" });
  await page.getByRole("link", { name: "Saltadas" }).click();
  await jira.waitFor();
  await page.getByRole("link", { name: "Nuevas" }).click();

  // Analizar ahora: spinner y, al terminar (SSE), la línea de última corrida degradada.
  await page.getByRole("button", { name: "Analizar ahora" }).click();
  await page.getByText("degradado (reglas)").waitFor({ timeout: 15000 });
  await page.getByRole("button", { name: "Analizar ahora" }).waitFor();
  await page.getByRole("article", { name: /revisa los logs/i }).first().waitFor();

  // Configuración del motor.
  await page.goto(BASE + "/configuracion");
  await page.getByRole("heading", { name: "Motor de recomendaciones" }).waitFor();
  await page.getByLabel(/claude -p/).check();
  await page.getByRole("button", { name: "Guardar" }).last().click();
  await page.getByText("Cambios guardados").last().waitFor();

  // Móvil: una columna y sin scroll horizontal.
  await page.setViewportSize({ width: 375, height: 800 });
  for (const path of ["/recomendaciones", "/configuracion", "/"]) {
    await page.goto(BASE + path);
    await page.waitForLoadState("networkidle");
    const [scrollWidth, innerWidth] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
    assert.ok(scrollWidth <= innerWidth, `${path}: scroll horizontal (${scrollWidth} > ${innerWidth})`);
  }
  await page.goto(BASE + "/recomendaciones");
  await page.screenshot({ path: process.env.SCRATCH + "/recomendaciones-375.png", fullPage: true });

  assert.deepEqual(errors, []);
  await browser.close();
  console.log("E2E OK");
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
```

Run: `SCRATCH=<scratchpad> NODE_PATH=frontend/node_modules node "$SCRATCH/e2e.cjs"`
Esperado: `E2E OK`. Si falta el navegador: `cd frontend && npx playwright install chromium`. Revisa también la captura `recomendaciones-375.png`. Si algo falla por un bug real (no por el script), arréglalo con un test que lo reproduzca y un commit propio. Al terminar, detén el servidor E2E.

- [ ] **Paso 3: portabilidad y suites completas**

Run:

```bash
git grep -nF "$HOME" ; echo "portabilidad: $?"
env -u OPENROUTER_API_KEY python3 -m unittest discover -s tests 2>&1 | tail -3
cd frontend && npx vitest run && npx oxlint && npm run build 2>&1 | tail -3
```

Esperado: `portabilidad: 1` sin líneas encima (ningún archivo con rutas del autor), `OK` en la suite de Python y todo en verde en el frontend.

- [ ] **Paso 4: corrida real (solo con permiso explícito del usuario)**

Pregunta al usuario antes de correrla: es la única vez que el motor toca el `history.db` real y manda resúmenes redactados a Hermes.

Run: `python3 -m recommend run --trigger manual; echo "salida: $?"`
Esperado: `Corrida N: ok` (o `degraded` si ningún modelo free respondió) y `salida: 0`. Muestra al usuario el conteo de recomendaciones con `sqlite3 ~/.local/share/ai-monitor/history.db "SELECT kind, impact, pattern FROM recommendations WHERE status='nueva'"` (patrones ya redactados). **No** imprimas `draft` ni `evidence`: pueden contener fragmentos de sus prompts. **No** reinicies `ai-monitor-server.service`; indica al usuario que lo haga cuando quiera ver la vista con el backend nuevo, y que active el timer con `systemctl --user enable --now ai-monitor-recommend.timer` tras correr `install.sh`.
