# Oficina pixel-art con actividad en vivo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir la vista `/oficina` (personajes pixel-art según la actividad en vivo de Claude Code, OpenCode y Hermes) con su endpoint `GET /api/activity` + evento SSE `activity`, y corregir las fechas de OpenCode.

**Architecture:** Un paquete nuevo `live/` (hermano de `collectors/`, solo lectura, funciones puras para el estado) alimenta un segundo hilo de `server.py` que publica por el mismo `SSEBroker`. El frontend vendoriza el motor Canvas de Pixel Agents (ya validado en la rama `spike/oficina`), fusiona `/api/activity` con el estado básico derivado de `/api/usage` y lo mapea al motor con funciones puras testeables.

**Tech Stack:** Python 3 stdlib (`sqlite3`, `json`, `unittest`, `threading`); React 19 + Vite 8 + TypeScript estricto + Vitest + oxlint; motor Canvas de Pixel Agents (MIT).

**Spec:** `docs/superpowers/specs/2026-10-01-oficina-actividad-en-vivo-design.md`

**Versión:** 1.1.0 (MINOR) — desde 1.0.0

## Global Constraints

- El backend es **solo stdlib**; el frontend es un proyecto npm aparte (las dependencias del frontend no violan esa regla).
- `live/` **no es un colector**: no participa en `main.collect_all()`, no escribe en `history.db` ni en ningún archivo, y abre bases ajenas solo con `file:...?mode=ro` y `uri=True`.
- Ningún argumento de herramienta, texto de mensaje, razonamiento ni título sale del proceso por `/api/activity`. Nunca se lee `input` de `tool_use`, `content` de `tool_result`, `content`/`api_content`/`reasoning*`/`display_*` de Hermes, ni el resto de `data` de OpenCode.
- Constantes (`live/model.py`): `WAITING_AFTER_S = 8`, `THINKING_WINDOW_S = 60`, `OFFICE_WINDOW_S = 1800`, `CLOCK_SKEW_S = 60`; `TAIL_BYTES = 65536` en el lector de Claude Code.
- Intervalo de actividad = 2 s, **no** expuesto como variable de entorno ni flag.
- Fechas de la API: ISO 8601 UTC con sufijo `Z` y precisión de segundos. `key` = `"<source>:<session_id>"`.
- Un lector lanza `live.model.SourceUnavailable` si no pudo leer la fuente y devuelve `[]` si leyó y no hay sesiones recientes.
- Ningún archivo del repo puede contener rutas de la máquina del autor (`/home/jruedadev`, `~/DEV/JRDV/...`).
- Los tests no leen `~/.claude`, `~/.local/share` ni `~/.hermes`: solo directorios y SQLite temporales.
- Commits Conventional Commits en español, **sin** `Co-Authored-By: Claude` ni `Claude-Session:`. `feat` para lo nuevo, `fix` para las fechas de OpenCode, ninguno con `!`. Cada `feat`/`fix` añade su línea a `## [Sin publicar]` de `CHANGELOG.md` en su propio commit.
- Tag, push y release en GitHub **solo con permiso explícito** del usuario (quedan fuera del plan).
- Automatización de navegador: Playwright por CLI, nunca `mcp__claude-in-chrome__*`.
- Los textos de la interfaz van en español con tildes correctas.

## Review Focus

Entradas/condiciones que el spec implica pero que no nombra, de más a menos probable de afectar a una persona:

1. **`data` de un `part` de OpenCode que no es JSON válido** → `json_extract` lanza `malformed JSON` y tumbaría toda la fuente; esperado: se ignora esa fila y la fuente sigue `ok` (Task 5, `json_valid(data)`).
2. **Última línea del `.jsonl` de Claude Code a medio escribir** (sin `\n` final, JSON truncado) → se salta, no invalida la fuente (Task 4).
3. **Muchas sesiones recientes** (> límite de variables de SQLite en un `IN (...)`) → el lector consulta por lotes en vez de fallar (Tasks 5 y 6).
4. **`tool_calls` de Hermes con formas distintas** (`function.name`, `name` plano, `null`, lista de no-objetos, JSON inválido) → no rompe ni inventa herramientas (Task 6).
5. **Un lector que lanza dentro del hilo de actividad** → el hilo sigue vivo y publica en el siguiente ciclo (Task 8).

---

## File Structure

**Backend (crear)**
- `live/__init__.py` — vacío, marca el paquete.
- `live/model.py` — constantes, `SourceUnavailable`, `SessionFacts`, `classify_tool`, `derive_state`, `to_agent` (puras).
- `live/claude_code.py`, `live/opencode.py`, `live/hermes.py` — un lector por fuente: `read(now, <ruta>=None) -> list[SessionFacts]`.
- `live/activity.py` — `snapshot(now=None, readers=None) -> dict` (cuerpo de §2.3 del spec).
- `tests/test_live_model.py`, `tests/test_live_claude_code.py`, `tests/test_live_opencode.py`, `tests/test_live_hermes.py`, `tests/test_live_activity.py`.

**Backend (modificar)**
- `collectors/opencode.py` — `last_ts`/`first_ts`. Test: `tests/test_opencode.py`.
- `server.py` — hilo `_activity_loop`, holder con lock, `GET /api/activity`. Test: `tests/test_server.py`.

**Frontend (crear)**
- `frontend/src/pixel/**` y `frontend/public/pixel/**` — motor y assets, restaurados desde `spike/oficina`.
- `frontend/src/pixel/fitZoom.ts` (+ test), `frontend/src/pixel/engineState.ts` (+ test) — funciones puras.
- `frontend/src/lib/activity.ts` (+ test) — tipos, `mergeOfficeAgents`, `fetchActivity`.
- `frontend/.oxlintrc.json`, `frontend/scripts/gen-pixel-assets.ts`.
- `NOTICE` (raíz).

**Frontend (modificar)**
- `frontend/src/lib/sessions.ts` (+ test) — `toEpochMs` exportada y correcta.
- `frontend/src/lib/office.ts` (+ test) — nueva forma de `OfficeAgent`.
- `frontend/src/hooks/useUsageStream.ts`, `frontend/src/App.tsx`, `frontend/src/views/OfficeView.tsx`, `frontend/src/pixel/OfficeStage.tsx`, `frontend/src/lib/routes.ts`, `frontend/src/components/Sidebar.tsx`.

**Docs**: `CLAUDE.md`, `README.md`, `NOTICE`, `CHANGELOG.md`, `VERSION`, `frontend/package.json`.

---

### Task 0: Rama de trabajo

**Files:** ninguno.

- [ ] **Step 1: Crear el worktree desde `main`**

```bash
cd ~/DEV/JRDV/ai-monitor   # raíz del repo (el worktree vive en .worktrees/, ya ignorado)
git worktree add .worktrees/oficina-en-vivo -b feat/oficina-en-vivo main
cd .worktrees/oficina-en-vivo
git status --short && cat VERSION
```
Expected: árbol limpio, `1.0.0`. **Todas las tareas siguientes se ejecutan desde este worktree.** La rama `spike/oficina` queda solo como referencia (no se mergea).

- [ ] **Step 2: Línea base de tests**

```bash
python3 -m unittest discover -s tests 2>&1 | tail -3
cd frontend && npm install && npm test 2>&1 | tail -5 && cd ..
```
Expected: ambas suites en verde. Si `npm install` falla por conflicto de peer deps, repetir con `npm install --legacy-peer-deps` y anotarlo (el spike lo encontró).

---

### Task 1: Fechas de OpenCode en el colector (fix)

**Files:**
- Modify: `collectors/opencode.py:19-22` (consulta) y `:61-69` (`sessions_detail`)
- Test: `tests/test_opencode.py`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Produces: `sessions_detail[]` de OpenCode con `last_ts` = `time_updated` (respaldo `time_created`), `first_ts` = `time_created`, ambos en **milisegundos**. `by_day` sin cambios.

- [ ] **Step 1: Actualizar el esquema de test y escribir los tests que fallan**

En `tests/test_opencode.py`, cambiar `SCHEMA` para añadir `time_updated INTEGER` tras `time_created INTEGER`, y añadir `time_updated` al `INSERT` de `setUp` (valor `1777996310131`) y a los demás `INSERT` existentes del archivo (pasar `None` donde el test no lo use; ajustar la lista de columnas y los `?`). Añadir:

```python
    def test_last_ts_is_time_updated_and_first_ts_is_time_created(self):
        data = opencode.collect(db_path=self.tmp.name)
        detail = data["/home/user/DEV/demo"]["sessions_detail"][0]
        self.assertEqual(detail["first_ts"], 1777996210131)
        self.assertEqual(detail["last_ts"], 1777996310131)

    def test_last_ts_falls_back_to_time_created_when_time_updated_is_null(self):
        con = sqlite3.connect(self.tmp.name)
        con.execute("UPDATE session SET time_updated = NULL WHERE id = 's1'")
        con.commit()
        con.close()
        detail = opencode.collect(db_path=self.tmp.name)["/home/user/DEV/demo"]["sessions_detail"][0]
        self.assertEqual(detail["last_ts"], 1777996210131)

    def test_by_day_still_uses_time_created(self):
        con = sqlite3.connect(self.tmp.name)
        con.execute("UPDATE session SET time_updated = time_created + 5 * 86400000 WHERE id = 's1'")
        con.commit()
        con.close()
        by_day = opencode.collect(db_path=self.tmp.name)["/home/user/DEV/demo"]["by_day"]
        self.assertEqual(list(by_day), ["2026-05-05"])
```

(Comprobar el día esperado: `1777996210131 ms` → `datetime.fromtimestamp(1777996210.131, tz=utc)`; si el literal del test existente `test_by_day_derives_date_from_time_created_ms` usa otra fecha, copiar ese valor en lugar de `"2026-05-05"`.)

- [ ] **Step 2: Verlos fallar**

Run: `python3 -m unittest tests.test_opencode -v`
Expected: FAIL (`KeyError: 'first_ts'`).

- [ ] **Step 3: Implementar**

En `collectors/opencode.py`, la consulta añade `time_updated`:

```python
        cur.execute(
            "SELECT id, directory, model, title, cost, tokens_input, tokens_output, "
            "tokens_cache_read, tokens_cache_write, time_created, time_updated FROM session"
        )
```

y el dict de `sessions_detail`:

```python
            time_updated = row["time_updated"]
            p["sessions_detail"].append({
                "session_id": row["id"],
                "tokens": inp + out + cr + cw,
                "cost": round(cost, 4),
                "title": row["title"],
                "first_ts": time_created,
                "last_ts": time_updated if time_updated is not None else time_created,
                "cwd": directory,
                "date": day,
            })
```

Si en una base real faltara la columna `time_updated`, `sqlite3.Error` ya devuelve `{}` (degradación existente); no añadir más lógica.

- [ ] **Step 4: Verlos pasar y la suite completa**

Run: `python3 -m unittest tests.test_opencode -v && python3 -m unittest discover -s tests 2>&1 | tail -3`
Expected: PASS.

- [ ] **Step 5: Changelog y commit**

En `CHANGELOG.md`, bajo `## [Sin publicar]`, crear (si no existe) `### Corregido` con:
`- Las fechas de las sesiones de OpenCode: la última actividad es la real (antes mostraba el inicio de la sesión) y las duraciones se calculan bien.`

```bash
git add collectors/opencode.py tests/test_opencode.py CHANGELOG.md
git commit -m "fix(opencode): last_ts es la última actividad y se añade first_ts"
```

---

### Task 2: `toEpochMs` correcta y exportada (fix, frontend)

**Files:**
- Modify: `frontend/src/lib/sessions.ts:32-36`
- Test: `frontend/src/lib/sessions.test.ts` (crear si no existe)

**Interfaces:**
- Produces: `export function toEpochMs(ts: string | number | null): number | null` — número `> 1e12` ya está en ms; menor se multiplica por 1000; cadena con `Date.parse`; inválido o `NaN` → `null`. Lo usan `lib/office.ts` y `lib/activity.ts`.

- [ ] **Step 1: Test que falla**

```ts
// frontend/src/lib/sessions.test.ts
import { describe, expect, it } from "vitest";
import { sessionDurationSeconds, toEpochMs } from "@/lib/sessions";

describe("toEpochMs", () => {
  it("interpreta ISO, segundos y milisegundos", () => {
    expect(toEpochMs("2026-10-01T12:00:00Z")).toBe(Date.parse("2026-10-01T12:00:00Z"));
    expect(toEpochMs(1_790_000_000)).toBe(1_790_000_000_000);
    expect(toEpochMs(1_790_000_000_000)).toBe(1_790_000_000_000);
  });
  it("devuelve null para null e inválidos", () => {
    expect(toEpochMs(null)).toBeNull();
    expect(toEpochMs("no-es-fecha")).toBeNull();
    expect(toEpochMs(Number.NaN)).toBeNull();
  });
});

describe("sessionDurationSeconds", () => {
  it("calcula bien una sesión de OpenCode (ms)", () => {
    expect(sessionDurationSeconds({ first_ts: 1_790_000_000_000, last_ts: 1_790_000_090_000 })).toBe(90);
  });
  it("mantiene segundos (Codex) e ISO (Claude Code)", () => {
    expect(sessionDurationSeconds({ first_ts: 1_790_000_000, last_ts: 1_790_000_060 })).toBe(60);
    expect(sessionDurationSeconds({ first_ts: "2026-10-01T12:00:00Z", last_ts: "2026-10-01T12:01:00Z" })).toBe(60);
  });
});
```

- [ ] **Step 2:** `cd frontend && npx vitest run src/lib/sessions.test.ts` → FAIL (`toEpochMs` no exportada).

- [ ] **Step 3: Implementar** (sustituir la función y su comentario):

```ts
/**
 * claude_code usa ISO (string), codex y hermes epoch en segundos y opencode epoch en ms.
 * Un número > 1e12 ya está en ms (1e12 s sería el año 33658).
 */
export function toEpochMs(ts: string | number | null): number | null {
  if (ts === null) return null;
  const ms = typeof ts === "number" ? (ts > 1e12 ? ts : ts * 1000) : Date.parse(ts);
  return Number.isNaN(ms) ? null : ms;
}
```

- [ ] **Step 4:** `npx vitest run && npm run lint` → PASS.

- [ ] **Step 5: Commit** (la línea de changelog ya está en la Task 1)

```bash
git add frontend/src/lib/sessions.ts frontend/src/lib/sessions.test.ts
git commit -m "fix(frontend): las duraciones de OpenCode interpretan milisegundos"
```

---

### Task 3: `live/model.py` — estado y clasificación (puras)

**Files:**
- Create: `live/__init__.py` (vacío), `live/model.py`
- Test: `tests/test_live_model.py`

**Interfaces:**
- Produces:
  - constantes `WAITING_AFTER_S`, `THINKING_WINDOW_S`, `OFFICE_WINDOW_S`, `CLOCK_SKEW_S`; `class SourceUnavailable(Exception)`
  - `@dataclass(frozen=True) SessionFacts(source: str, session_id: str, project: str, last_event: float | None, pending_tool: str | None, pending_since: float | None, ended: bool = False)`
  - `classify_tool(name: str | None) -> str` (`"edit" | "read" | "run" | "other"`)
  - `derive_state(facts, now: float) -> tuple[str, float] | None` → `(state, since_epoch)` o `None` si se omite
  - `to_agent(facts, now: float) -> dict | None` → objeto de agente de §2.3
  - `iso_utc(epoch: float) -> str`

- [ ] **Step 1: Tests que fallan**

```python
# tests/test_live_model.py
import unittest

from live import model
from live.model import SessionFacts

NOW = 1_790_000_000.0


def facts(**kw):
    base = dict(source="claude_code", session_id="s1", project="/p", last_event=NOW - 5,
                pending_tool=None, pending_since=None)
    base.update(kw)
    return SessionFacts(**base)


class TestClassifyTool(unittest.TestCase):
    def test_classes_case_insensitive(self):
        for name in ("Edit", "WRITE", "MultiEdit", "NotebookEdit", "patch", "apply_patch",
                     "str_replace_editor", "TodoWrite"):
            self.assertEqual(model.classify_tool(name), "edit", name)
        for name in ("Read", "grep", "Glob", "ls", "list", "WebFetch", "WebSearch", "search", "codesearch"):
            self.assertEqual(model.classify_tool(name), "read", name)
        for name in ("Bash", "shell", "terminal", "exec", "execute_code", "Task", "agent"):
            self.assertEqual(model.classify_tool(name), "run", name)

    def test_other_and_none(self):
        self.assertEqual(model.classify_tool("mcp__x__y"), "other")
        self.assertEqual(model.classify_tool(None), "other")
        self.assertEqual(model.classify_tool(""), "other")


class TestDeriveState(unittest.TestCase):
    def state(self, **kw):
        res = model.derive_state(facts(**kw), NOW)
        return res[0] if res else None

    def test_tool_then_waiting_at_8_seconds(self):
        self.assertEqual(self.state(pending_tool="Bash", pending_since=NOW - 7.9), "tool")
        self.assertEqual(self.state(pending_tool="Bash", pending_since=NOW - 8), "waiting")

    def test_thinking_until_60_seconds_then_idle(self):
        self.assertEqual(self.state(last_event=NOW - 59), "thinking")
        self.assertEqual(self.state(last_event=NOW - 60), "idle")

    def test_omitted_after_30_minutes(self):
        self.assertEqual(self.state(last_event=NOW - 1800), "idle")
        self.assertIsNone(self.state(last_event=NOW - 1801))

    def test_omitted_when_ended_or_without_events(self):
        self.assertIsNone(self.state(ended=True))
        self.assertIsNone(self.state(last_event=None))

    def test_future_event_within_skew_counts_as_now(self):
        self.assertEqual(self.state(last_event=NOW + 30), "thinking")
        self.assertIsNone(self.state(last_event=NOW + 120))

    def test_since_is_pending_since_or_last_event(self):
        self.assertEqual(model.derive_state(facts(pending_tool="Bash", pending_since=NOW - 3), NOW), ("tool", NOW - 3))
        self.assertEqual(model.derive_state(facts(last_event=NOW - 20), NOW), ("thinking", NOW - 20))

    def test_pending_tool_without_since_is_not_pending(self):
        self.assertEqual(self.state(pending_tool="Bash", pending_since=None), "thinking")


class TestToAgent(unittest.TestCase):
    def test_tool_agent_shape(self):
        agent = model.to_agent(facts(pending_tool="Bash", pending_since=NOW - 2), NOW)
        self.assertEqual(agent, {
            "key": "claude_code:s1", "source": "claude_code", "project": "/p", "state": "tool",
            "tool": "Bash", "tool_kind": "run", "since": model.iso_utc(NOW - 2),
        })

    def test_idle_has_null_tool_fields_and_z_suffix(self):
        agent = model.to_agent(facts(last_event=NOW - 600), NOW)
        self.assertIsNone(agent["tool"])
        self.assertIsNone(agent["tool_kind"])
        self.assertRegex(agent["since"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_omitted_returns_none(self):
        self.assertIsNone(model.to_agent(facts(ended=True), NOW))
```

- [ ] **Step 2:** `python3 -m unittest tests.test_live_model -v` → FAIL (`ModuleNotFoundError: live`).

- [ ] **Step 3: Implementar** — `live/__init__.py` vacío y:

```python
# live/model.py
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
```

- [ ] **Step 4:** `python3 -m unittest tests.test_live_model -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add live/__init__.py live/model.py tests/test_live_model.py
git commit -m "feat(live): modelo puro de estados de actividad por sesión"
```

---

### Task 4: `live/claude_code.py` — lector de Claude Code

**Files:**
- Create: `live/claude_code.py`
- Test: `tests/test_live_claude_code.py`

**Interfaces:**
- Consumes: `live.model.SessionFacts`, `SourceUnavailable`, `OFFICE_WINDOW_S`.
- Produces: `read(now: float, projects_dir: str | None = None) -> list[SessionFacts]`; constante `TAIL_BYTES = 65536`.

- [ ] **Step 1: Tests que fallan**

```python
# tests/test_live_claude_code.py
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from live import claude_code
from live.model import SourceUnavailable

NOW = 1_790_000_000.0


def iso(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def assistant_tool(ts, tool_id, name="Bash", cwd="/work/app"):
    return {"type": "assistant", "timestamp": iso(ts), "cwd": cwd,
            "message": {"content": [{"type": "tool_use", "id": tool_id, "name": name,
                                     "input": {"command": "SECRET-XYZ"}}]}}


def user_result(ts, tool_id, cwd="/work/app"):
    return {"type": "user", "timestamp": iso(ts), "cwd": cwd,
            "message": {"content": [{"type": "tool_result", "tool_use_id": tool_id, "content": "SECRET-XYZ"}]}}


class TestClaudeCodeReader(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.proj = os.path.join(self.root, "-work-app")
        os.makedirs(self.proj)

    def write(self, name, records, raw_tail=b"", mtime=None):
        path = os.path.join(self.proj, f"{name}.jsonl")
        with open(path, "wb") as f:
            for rec in records:
                f.write(json.dumps(rec).encode() + b"\n")
            f.write(raw_tail)
        os.utime(path, (mtime or NOW, mtime or NOW))
        return path

    def read(self):
        return claude_code.read(NOW, projects_dir=self.root)

    def test_pending_tool_use(self):
        self.write("sess1", [assistant_tool(NOW - 3, "t1")])
        [f] = self.read()
        self.assertEqual((f.source, f.session_id, f.project), ("claude_code", "sess1", "/work/app"))
        self.assertEqual((f.pending_tool, f.pending_since), ("Bash", NOW - 3))
        self.assertEqual(f.last_event, NOW - 3)

    def test_resolved_tool_use_is_not_pending(self):
        self.write("sess1", [assistant_tool(NOW - 10, "t1"), user_result(NOW - 5, "t1")])
        [f] = self.read()
        self.assertIsNone(f.pending_tool)
        self.assertEqual(f.last_event, NOW - 5)

    def test_several_pending_picks_most_recent(self):
        self.write("sess1", [assistant_tool(NOW - 20, "t1", "Read"), assistant_tool(NOW - 4, "t2", "Edit")])
        [f] = self.read()
        self.assertEqual((f.pending_tool, f.pending_since), ("Edit", NOW - 4))

    def test_corrupt_line_in_the_middle_is_skipped(self):
        path = self.write("sess1", [assistant_tool(NOW - 3, "t1")])
        with open(path, "ab") as f:
            f.write(b"{no es json\n")
        os.utime(path, (NOW, NOW))
        [f] = self.read()
        self.assertEqual(f.pending_tool, "Bash")

    def test_half_written_last_line_is_skipped(self):
        self.write("sess1", [assistant_tool(NOW - 3, "t1")], raw_tail=b'{"type": "assistant", "timest')
        [f] = self.read()
        self.assertEqual(f.pending_tool, "Bash")

    def test_old_mtime_file_is_ignored(self):
        self.write("viejo", [assistant_tool(NOW - 3, "t1")], mtime=NOW - 3600)
        self.assertEqual(self.read(), [])

    def test_only_the_tail_of_a_big_file_is_read(self):
        filler = {"type": "user", "timestamp": iso(NOW - 4000), "cwd": "/viejo", "message": {"content": "x" * 200}}
        path = os.path.join(self.proj, "big.jsonl")
        with open(path, "wb") as f:
            while f.tell() < 5 * 1024 * 1024:
                f.write(json.dumps(filler).encode() + b"\n")
            f.write(json.dumps(assistant_tool(NOW - 2, "t9", cwd="/work/app")).encode() + b"\n")
        os.utime(path, (NOW, NOW))
        [f] = self.read()
        self.assertEqual(f.project, "/work/app")
        self.assertEqual(f.pending_tool, "Bash")

    def test_records_without_valid_timestamp_do_not_crash(self):
        self.write("sess1", [{"type": "user", "cwd": "/work/app", "message": {"content": "hola"}},
                             {"type": "assistant", "timestamp": "no-fecha", "message": {"content": []}}])
        [f] = self.read()
        self.assertIsNone(f.last_event)

    def test_project_unknown_without_cwd(self):
        self.write("sess1", [{"type": "user", "timestamp": iso(NOW - 1), "message": {"content": "x"}}])
        [f] = self.read()
        self.assertEqual(f.project, "unknown")

    def test_output_never_contains_tool_input_or_result(self):
        self.write("sess1", [assistant_tool(NOW - 3, "t1")])
        self.assertNotIn("SECRET-XYZ", repr(self.read()))

    def test_missing_directory_is_unavailable(self):
        with self.assertRaises(SourceUnavailable):
            claude_code.read(NOW, projects_dir=os.path.join(self.root, "no-existe"))
```

- [ ] **Step 2:** `python3 -m unittest tests.test_live_claude_code -v` → FAIL (módulo inexistente).

- [ ] **Step 3: Implementar**

```python
# live/claude_code.py
"""Lector en vivo de Claude Code: cola de ~/.claude/projects/*/*.jsonl.
Solo lee tipos, ids, nombres de herramienta, cwd y timestamps; nunca `input` ni `content`."""
import glob
import json
import os
from datetime import datetime

from live.model import OFFICE_WINDOW_S, SessionFacts, SourceUnavailable

TAIL_BYTES = 65536


def _epoch(ts):
    if not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _tail_lines(path):
    with open(path, "rb") as f:
        size = os.fstat(f.fileno()).st_size
        start = max(0, size - TAIL_BYTES)
        f.seek(start)
        lines = f.read().split(b"\n")
    return lines[1:] if start > 0 else lines


def _parse(path, session_id):
    cwd = None
    last_event = None
    pending = {}  # tool_use id -> (name, timestamp)
    for raw in _tail_lines(path):
        try:
            rec = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(rec, dict):
            continue
        if isinstance(rec.get("cwd"), str) and rec["cwd"]:
            cwd = rec["cwd"]
        kind = rec.get("type")
        ts = _epoch(rec.get("timestamp"))
        if kind in ("user", "assistant") and ts is not None:
            last_event = ts if last_event is None else max(last_event, ts)
        message = rec.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "tool_use" and kind == "assistant" and ts is not None:
                pending[block.get("id")] = (block.get("name"), ts)
            elif btype == "tool_result":
                pending.pop(block.get("tool_use_id"), None)
    tool, since = (None, None)
    for name, ts in pending.values():
        if isinstance(name, str) and (since is None or ts >= since):
            tool, since = name, ts
    return SessionFacts("claude_code", session_id, cwd or "unknown", last_event, tool, since)


def read(now, projects_dir=None):
    root = projects_dir or os.path.expanduser("~/.claude/projects")
    if not os.path.isdir(root):
        raise SourceUnavailable(root)
    facts = []
    try:
        for path in glob.glob(os.path.join(root, "*", "*.jsonl")):
            try:
                if now - os.stat(path).st_mtime > OFFICE_WINDOW_S:
                    continue
                session_id = os.path.basename(path)[: -len(".jsonl")]
                facts.append(_parse(path, session_id))
            except OSError:
                continue  # un archivo que desaparece entre el glob y la lectura no invalida la fuente
    except OSError as exc:
        raise SourceUnavailable(str(exc)) from exc
    return facts
```

- [ ] **Step 4:** `python3 -m unittest tests.test_live_claude_code -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add live/claude_code.py tests/test_live_claude_code.py
git commit -m "feat(live): lector de actividad en vivo de Claude Code"
```

---

### Task 5: `live/opencode.py` — lector de OpenCode

**Files:**
- Create: `live/opencode.py`
- Test: `tests/test_live_opencode.py`

**Interfaces:**
- Consumes: `SessionFacts`, `SourceUnavailable`, `OFFICE_WINDOW_S`.
- Produces: `read(now: float, db_path: str | None = None) -> list[SessionFacts]`; constante `BATCH = 500`.

- [ ] **Step 1: Tests que fallan**

```python
# tests/test_live_opencode.py
import json
import os
import sqlite3
import tempfile
import unittest

from live import opencode
from live.model import SourceUnavailable

NOW = 1_790_000_000.0
MS = 1000

SCHEMA = """
CREATE TABLE session (id text PRIMARY KEY, directory text NOT NULL, title text NOT NULL,
  time_created integer NOT NULL, time_updated integer NOT NULL, time_archived integer);
CREATE TABLE part (id text PRIMARY KEY, message_id text NOT NULL, session_id text NOT NULL,
  time_created integer NOT NULL, time_updated integer NOT NULL, data text NOT NULL);
"""


class TestOpenCodeReader(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(os.unlink, self.db)
        self.con = sqlite3.connect(self.db)
        self.con.executescript(SCHEMA)

    def session(self, sid, updated, directory="/work/oc", archived=None, title="SECRET-XYZ"):
        self.con.execute("INSERT INTO session VALUES (?,?,?,?,?,?)",
                         (sid, directory, title, int((updated - 100) * MS), int(updated * MS),
                          None if archived is None else int(archived * MS)))
        self.con.commit()

    def part(self, pid, sid, created, updated, data):
        payload = data if isinstance(data, str) else json.dumps(data)
        self.con.execute("INSERT INTO part VALUES (?,?,?,?,?,?)",
                         (pid, "m1", sid, int(created * MS), int(updated * MS), payload))
        self.con.commit()

    def read(self):
        return opencode.read(NOW, db_path=self.db)

    def tool_part(self, pid, sid, status, created, tool="bash"):
        self.part(pid, sid, created, created + 1,
                  {"type": "tool", "tool": tool, "state": {"status": status, "input": {"command": "SECRET-XYZ"}}})

    def test_running_tool_is_pending(self):
        self.session("s1", NOW - 2)
        self.tool_part("p1", "s1", "running", NOW - 3)
        [f] = self.read()
        self.assertEqual((f.source, f.session_id, f.project), ("opencode", "s1", "/work/oc"))
        self.assertEqual((f.pending_tool, f.pending_since), ("bash", NOW - 3))
        self.assertFalse(f.ended)

    def test_pending_status_counts_and_completed_does_not(self):
        self.session("s1", NOW - 2)
        self.tool_part("p1", "s1", "pending", NOW - 6, tool="edit")
        self.tool_part("p2", "s1", "completed", NOW - 4, tool="read")
        [f] = self.read()
        self.assertEqual((f.pending_tool, f.pending_since), ("edit", NOW - 6))

    def test_most_recent_pending_wins(self):
        self.session("s1", NOW - 1)
        self.tool_part("p1", "s1", "running", NOW - 9, tool="read")
        self.tool_part("p2", "s1", "running", NOW - 3, tool="bash")
        [f] = self.read()
        self.assertEqual(f.pending_tool, "bash")

    def test_last_event_is_max_of_session_and_parts_in_seconds(self):
        self.session("s1", NOW - 50)
        self.tool_part("p1", "s1", "completed", NOW - 10)
        [f] = self.read()
        self.assertEqual(f.last_event, NOW - 9)

    def test_archived_session_is_ended(self):
        self.session("s1", NOW - 2, archived=NOW - 1)
        [f] = self.read()
        self.assertTrue(f.ended)

    def test_old_sessions_are_not_returned(self):
        self.session("viejo", NOW - 4000)
        self.assertEqual(self.read(), [])

    def test_malformed_part_json_does_not_invalidate_the_source(self):
        self.session("s1", NOW - 2)
        self.part("bad", "s1", NOW - 3, NOW - 3, "{esto no es json")
        self.tool_part("p1", "s1", "running", NOW - 3)
        [f] = self.read()
        self.assertEqual(f.pending_tool, "bash")

    def test_more_sessions_than_the_batch_size(self):
        for i in range(opencode.BATCH * 2 + 50):
            self.session(f"s{i}", NOW - 5)
        self.assertEqual(len(self.read()), opencode.BATCH * 2 + 50)

    def test_output_never_contains_text_or_inputs(self):
        self.session("s1", NOW - 2)
        self.tool_part("p1", "s1", "running", NOW - 3)
        self.assertNotIn("SECRET-XYZ", repr(self.read()))

    def test_missing_db_is_unavailable(self):
        with self.assertRaises(SourceUnavailable):
            opencode.read(NOW, db_path="/no/existe/opencode.db")

    def test_missing_table_is_unavailable(self):
        self.con.execute("DROP TABLE part")
        self.con.commit()
        with self.assertRaises(SourceUnavailable):
            self.read()

    def test_database_is_opened_read_only(self):
        self.session("s1", NOW - 2)
        self.read()
        con = sqlite3.connect(self.db)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM session").fetchone()[0], 1)
```

- [ ] **Step 2:** `python3 -m unittest tests.test_live_opencode -v` → FAIL (módulo inexistente).

- [ ] **Step 3: Implementar**

```python
# live/opencode.py
"""Lector en vivo de OpenCode (~/.local/share/opencode/opencode.db, solo lectura).
`time_*` está en milisegundos. Del JSON de `part.data` solo se extraen tipo, herramienta y estado."""
import os
import sqlite3

from live.model import OFFICE_WINDOW_S, SessionFacts, SourceUnavailable

BATCH = 500  # por debajo del límite de variables de SQLite


def _chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def read(now, db_path=None):
    path = db_path or os.path.expanduser("~/.local/share/opencode/opencode.db")
    if not os.path.isfile(path):
        raise SourceUnavailable(path)
    since_ms = (now - OFFICE_WINDOW_S) * 1000
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            sessions = con.execute(
                "SELECT id, directory, time_updated, time_archived FROM session WHERE time_updated >= ?",
                (since_ms,),
            ).fetchall()
            parts = []
            ids = [row[0] for row in sessions]
            for chunk in _chunks(ids, BATCH):
                marks = ",".join("?" * len(chunk))
                parts.extend(con.execute(
                    "SELECT session_id, time_created, time_updated, json_extract(data,'$.type'), "
                    "json_extract(data,'$.tool'), json_extract(data,'$.state.status') "
                    f"FROM part WHERE json_valid(data) AND session_id IN ({marks}) AND time_updated >= ?",
                    (*chunk, since_ms),
                ).fetchall())
        finally:
            con.close()
    except sqlite3.Error as exc:
        raise SourceUnavailable(str(exc)) from exc

    by_session = {}
    for sid, created, updated, ptype, tool, status in parts:
        entry = by_session.setdefault(sid, {"last": None, "tool": None, "since": None})
        if updated is not None:
            entry["last"] = updated if entry["last"] is None else max(entry["last"], updated)
        if ptype == "tool" and status in ("pending", "running") and isinstance(tool, str) and created is not None:
            if entry["since"] is None or created >= entry["since"]:
                entry["tool"], entry["since"] = tool, created

    facts = []
    for sid, directory, updated, archived in sessions:
        entry = by_session.get(sid, {"last": None, "tool": None, "since": None})
        stamps = [t for t in (updated, entry["last"]) if t is not None]
        facts.append(SessionFacts(
            "opencode", sid, directory or "unknown",
            max(stamps) / 1000 if stamps else None,
            entry["tool"], entry["since"] / 1000 if entry["since"] is not None else None,
            ended=archived is not None,
        ))
    return facts
```

- [ ] **Step 4:** `python3 -m unittest tests.test_live_opencode -v` → PASS. Si `json_valid` no existiera en el SQLite del sistema (< 3.9), el test de tabla ausente/JSON roto lo evidencia: en ese caso usar `try/except` por fila no es posible en SQL; ver `sqlite3.sqlite_version` y escalarlo al usuario.

- [ ] **Step 5: Commit**

```bash
git add live/opencode.py tests/test_live_opencode.py
git commit -m "feat(live): lector de actividad en vivo de OpenCode"
```

---

### Task 6: `live/hermes.py` — lector de Hermes

**Files:**
- Create: `live/hermes.py`
- Test: `tests/test_live_hermes.py`

**Interfaces:**
- Consumes: `SessionFacts`, `SourceUnavailable`, `OFFICE_WINDOW_S`.
- Produces: `read(now: float, db_path: str | None = None) -> list[SessionFacts]`; constante `BATCH = 500`.

- [ ] **Step 1: Tests que fallan**

```python
# tests/test_live_hermes.py
import json
import os
import sqlite3
import tempfile
import unittest

from live import hermes
from live.model import SourceUnavailable

NOW = 1_790_000_000.0

SCHEMA = """
CREATE TABLE sessions (id TEXT PRIMARY KEY, cwd TEXT, last_activity_at REAL, ended_at REAL, title TEXT);
CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, role TEXT NOT NULL,
  content TEXT, tool_calls TEXT, tool_call_id TEXT, timestamp REAL NOT NULL);
"""


class TestHermesReader(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(os.unlink, self.db)
        self.con = sqlite3.connect(self.db)
        self.con.executescript(SCHEMA)

    def session(self, sid, last, cwd="/work/h", ended=None):
        self.con.execute("INSERT INTO sessions VALUES (?,?,?,?,?)", (sid, cwd, last, ended, "SECRET-XYZ"))
        self.con.commit()

    def msg(self, sid, role, ts, tool_calls=None, tool_call_id=None):
        tc = tool_calls if (tool_calls is None or isinstance(tool_calls, str)) else json.dumps(tool_calls)
        self.con.execute(
            "INSERT INTO messages (session_id, role, content, tool_calls, tool_call_id, timestamp) VALUES (?,?,?,?,?,?)",
            (sid, role, "SECRET-XYZ", tc, tool_call_id, ts))
        self.con.commit()

    def read(self):
        return hermes.read(NOW, db_path=self.db)

    def test_pending_tool_call(self):
        self.session("s1", NOW - 2)
        self.msg("s1", "assistant", NOW - 3, [{"id": "c1", "function": {"name": "terminal", "arguments": "SECRET-XYZ"}}])
        [f] = self.read()
        self.assertEqual((f.source, f.session_id, f.project), ("hermes", "s1", "/work/h"))
        self.assertEqual((f.pending_tool, f.pending_since), ("terminal", NOW - 3))

    def test_resolved_tool_call_is_not_pending(self):
        self.session("s1", NOW - 1)
        self.msg("s1", "assistant", NOW - 5, [{"id": "c1", "function": {"name": "terminal"}}])
        self.msg("s1", "tool", NOW - 2, tool_call_id="c1")
        [f] = self.read()
        self.assertIsNone(f.pending_tool)
        self.assertEqual(f.last_event, NOW - 1)

    def test_flat_name_and_most_recent_pending(self):
        self.session("s1", NOW - 1)
        self.msg("s1", "assistant", NOW - 9, [{"id": "c1", "name": "read_file"}])
        self.msg("s1", "assistant", NOW - 4, [{"id": "c2", "function": {"name": "execute_code"}}])
        [f] = self.read()
        self.assertEqual((f.pending_tool, f.pending_since), ("execute_code", NOW - 4))

    def test_odd_tool_calls_shapes_are_ignored(self):
        self.session("s1", NOW - 1)
        for bad in (None, "no es json", "[1, 2, 3]", "{}", '[{"id": "c9"}]', '[{"function": {"name": 7}}]'):
            self.msg("s1", "assistant", NOW - 3, bad)
        [f] = self.read()
        self.assertIsNone(f.pending_tool)

    def test_ended_session(self):
        self.session("s1", NOW - 2, ended=NOW - 1)
        [f] = self.read()
        self.assertTrue(f.ended)

    def test_old_session_not_returned(self):
        self.session("viejo", NOW - 4000)
        self.assertEqual(self.read(), [])

    def test_more_sessions_than_the_batch_size(self):
        for i in range(hermes.BATCH + 30):
            self.session(f"s{i}", NOW - 5)
        self.assertEqual(len(self.read()), hermes.BATCH + 30)

    def test_output_never_contains_content(self):
        self.session("s1", NOW - 2)
        self.msg("s1", "assistant", NOW - 3, [{"id": "c1", "function": {"name": "terminal", "arguments": "SECRET-XYZ"}}])
        self.assertNotIn("SECRET-XYZ", repr(self.read()))

    def test_missing_db_and_missing_table_are_unavailable(self):
        with self.assertRaises(SourceUnavailable):
            hermes.read(NOW, db_path="/no/existe/state.db")
        self.con.execute("DROP TABLE messages")
        self.con.commit()
        with self.assertRaises(SourceUnavailable):
            self.read()
```

- [ ] **Step 2:** `python3 -m unittest tests.test_live_hermes -v` → FAIL.

- [ ] **Step 3: Implementar**

```python
# live/hermes.py
"""Lector en vivo de Hermes (~/.hermes/state.db, solo lectura). Fechas en epoch segundos.
Nunca selecciona content, api_content, reasoning* ni display_*."""
import json
import os
import sqlite3

from live.model import OFFICE_WINDOW_S, SessionFacts, SourceUnavailable

BATCH = 500


def _chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _calls(raw):
    """[(id, nombre)] de un JSON de tool_calls; lo que no encaje se ignora."""
    try:
        data = json.loads(raw) if raw else None
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    out = []
    for call in data:
        if not isinstance(call, dict):
            continue
        fn = call.get("function")
        name = fn.get("name") if isinstance(fn, dict) else call.get("name")
        if isinstance(call.get("id"), str) and isinstance(name, str):
            out.append((call["id"], name))
    return out


def read(now, db_path=None):
    path = db_path or os.path.expanduser("~/.hermes/state.db")
    if not os.path.isfile(path):
        raise SourceUnavailable(path)
    since = now - OFFICE_WINDOW_S
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            sessions = con.execute(
                "SELECT id, cwd, last_activity_at, ended_at FROM sessions WHERE last_activity_at >= ?",
                (since,),
            ).fetchall()
            messages = []
            for chunk in _chunks([row[0] for row in sessions], BATCH):
                marks = ",".join("?" * len(chunk))
                messages.extend(con.execute(
                    "SELECT session_id, role, tool_calls, tool_call_id, timestamp FROM messages "
                    f"WHERE session_id IN ({marks}) AND timestamp >= ? ORDER BY timestamp",
                    (*chunk, since),
                ).fetchall())
        finally:
            con.close()
    except sqlite3.Error as exc:
        raise SourceUnavailable(str(exc)) from exc

    state = {}
    for sid, role, tool_calls, tool_call_id, ts in messages:
        entry = state.setdefault(sid, {"last": None, "pending": {}})
        if role in ("user", "assistant", "tool") and ts is not None:
            entry["last"] = ts if entry["last"] is None else max(entry["last"], ts)
        if role == "assistant":
            for call_id, name in _calls(tool_calls):
                entry["pending"][call_id] = (name, ts)
        elif role == "tool":
            entry["pending"].pop(tool_call_id, None)

    facts = []
    for sid, cwd, activity, ended_at in sessions:
        entry = state.get(sid, {"last": None, "pending": {}})
        stamps = [t for t in (activity, entry["last"]) if t is not None]
        tool, tool_since = None, None
        for name, ts in entry["pending"].values():
            if ts is not None and (tool_since is None or ts >= tool_since):
                tool, tool_since = name, ts
        facts.append(SessionFacts("hermes", sid, cwd or "unknown", max(stamps) if stamps else None,
                                  tool, tool_since, ended=ended_at is not None))
    return facts
```

- [ ] **Step 4:** `python3 -m unittest tests.test_live_hermes -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add live/hermes.py tests/test_live_hermes.py
git commit -m "feat(live): lector de actividad en vivo de Hermes"
```

---

### Task 7: `live/activity.py` — snapshot

**Files:**
- Create: `live/activity.py`
- Test: `tests/test_live_activity.py`

**Interfaces:**
- Consumes: `live.claude_code.read`, `live.opencode.read`, `live.hermes.read`, `model.to_agent`, `SourceUnavailable`.
- Produces: `snapshot(now: float | None = None, readers: dict[str, Callable[[float], list[SessionFacts]]] | None = None) -> dict` con la forma de §2.3 (`generated_at`, `agents`, `sources`). `LIVE_SOURCES = ("claude_code", "opencode", "hermes")`.

- [ ] **Step 1: Tests que fallan**

```python
# tests/test_live_activity.py
import unittest

from live import activity
from live.model import SessionFacts, SourceUnavailable, iso_utc

NOW = 1_790_000_000.0


def f(source, sid, last, **kw):
    return SessionFacts(source, sid, "/p", last, kw.get("tool"), kw.get("since"))


class TestSnapshot(unittest.TestCase):
    def test_exact_shape_and_all_three_sources(self):
        snap = activity.snapshot(NOW, readers={
            "claude_code": lambda now: [f("claude_code", "a", NOW - 2, tool="Bash", since=NOW - 2)],
            "opencode": lambda now: [],
            "hermes": lambda now: (_ for _ in ()).throw(SourceUnavailable("x")),
        })
        self.assertEqual(set(snap), {"generated_at", "agents", "sources"})
        self.assertEqual(snap["generated_at"], iso_utc(NOW))
        self.assertEqual(snap["sources"], {"claude_code": "ok", "opencode": "ok", "hermes": "unavailable"})
        self.assertEqual(snap["agents"], [{
            "key": "claude_code:a", "source": "claude_code", "project": "/p", "state": "tool",
            "tool": "Bash", "tool_kind": "run", "since": iso_utc(NOW - 2),
        }])

    def test_any_exception_marks_only_that_source_unavailable(self):
        def boom(now):
            raise RuntimeError("inesperado")
        snap = activity.snapshot(NOW, readers={
            "claude_code": boom,
            "opencode": lambda now: [f("opencode", "o", NOW - 5)],
            "hermes": lambda now: [],
        })
        self.assertEqual(snap["sources"], {"claude_code": "unavailable", "opencode": "ok", "hermes": "ok"})
        self.assertEqual([a["key"] for a in snap["agents"]], ["opencode:o"])

    def test_sorted_by_since_descending_and_omitted_sessions_dropped(self):
        snap = activity.snapshot(NOW, readers={
            "claude_code": lambda now: [f("claude_code", "viejo", NOW - 900), f("claude_code", "nuevo", NOW - 10),
                                        f("claude_code", "fuera", NOW - 4000)],
            "opencode": lambda now: [],
            "hermes": lambda now: [],
        })
        self.assertEqual([a["key"] for a in snap["agents"]], ["claude_code:nuevo", "claude_code:viejo"])

    def test_default_readers_never_raise_when_nothing_exists(self):
        from unittest.mock import patch
        with patch.dict("os.environ", {"HOME": "/no/existe"}):
            snap = activity.snapshot(NOW)
        self.assertEqual(snap["sources"], {"claude_code": "unavailable", "opencode": "unavailable", "hermes": "unavailable"})
        self.assertEqual(snap["agents"], [])
```

(El último test depende de `os.path.expanduser` honrando `HOME`; es el comportamiento en Linux/macOS.)

- [ ] **Step 2:** `python3 -m unittest tests.test_live_activity -v` → FAIL.

- [ ] **Step 3: Implementar**

```python
# live/activity.py
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
```

(`since` es ISO UTC de ancho fijo, así que el orden léxico descendente equivale al cronológico.)

- [ ] **Step 4:** `python3 -m unittest tests.test_live_activity -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add live/activity.py tests/test_live_activity.py
git commit -m "feat(live): snapshot de actividad con degradación por fuente"
```

---

### Task 8: `server.py` — hilo, endpoint y evento SSE

**Files:**
- Modify: `server.py` (imports, estado global, `make_handler.do_GET`, `build_app`)
- Test: `tests/test_server.py`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: `live.activity.snapshot(now=None, readers=None) -> dict`.
- Produces: `GET /api/activity` (200, JSON de §2.3); `build_app(..., activity_interval_seconds=2, activity_fn=None)` (`activity_fn` es un parámetro de inyección para tests, por defecto `live.activity.snapshot`); evento SSE `activity`; `_activity_loop(broker, interval, holder, fn)`.

- [ ] **Step 1: Tests que fallan**

En `tests/test_server.py` añadir al módulo (la clase existente usa `patch` de `server.main.collect_all` en `setUp`; estos tests construyen su propio servidor con una función de actividad falsa):

```python
class TestActivityEndpoint(unittest.TestCase):
    def build(self, fn, interval=0.05):
        static_dir = tempfile.mkdtemp()
        with open(os.path.join(static_dir, "index.html"), "w") as f:
            f.write("<html></html>")
        patcher = patch("server.main.collect_all", return_value={
            "claude_code": {}, "codex": {}, "opencode": {}, "hermes": {},
            "openrouter": {"unavailable": True, "reason": "x"}})
        patcher.start()
        self.addCleanup(patcher.stop)
        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(db_fd)
        os.unlink(db_path)
        httpd = server.build_app(static_dir, poll_interval_seconds=3600, db_path=db_path,
                                 activity_interval_seconds=interval, activity_fn=fn)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        return httpd.server_address[1]

    def snap(self, state="thinking", source_status="ok", generated="2026-10-01T05:30:00Z"):
        return {"generated_at": generated,
                "agents": [{"key": "claude_code:a", "source": "claude_code", "project": "/p", "state": state,
                            "tool": None, "tool_kind": None, "since": "2026-10-01T05:29:58Z"}],
                "sources": {"claude_code": source_status, "opencode": "ok", "hermes": "ok"}}

    def get(self, port, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as resp:
            return resp.status, resp.headers.get("Content-Type"), resp.read()

    def test_get_activity_returns_the_stored_snapshot(self):
        port = self.build(lambda: self.snap())
        status, ctype, body = self.get(port, "/api/activity")
        self.assertEqual(status, 200)
        self.assertEqual(ctype, "application/json")
        self.assertEqual(json.loads(body), self.snap())

    def test_get_activity_does_not_run_readers_in_the_request_thread(self):
        calls = []
        def fn():
            calls.append(threading.current_thread().name)
            return self.snap()
        port = self.build(fn, interval=3600)
        self.get(port, "/api/activity")
        self.get(port, "/api/activity")
        self.assertEqual(len(calls), 1)  # solo el cálculo inicial de build_app

    def read_sse_events(self, port, wanted, timeout=3):
        import socket
        sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        sock.sendall(b"GET /api/stream HTTP/1.1\r\nHost: x\r\n\r\n")
        buf, deadline = b"", time.time() + timeout
        try:
            while time.time() < deadline and buf.count(b"event: " + wanted) < 2:
                try:
                    buf += sock.recv(65536)
                except socket.timeout:
                    break
        finally:
            sock.close()
        return buf.count(b"event: " + wanted)

    def test_loop_publishes_only_when_agents_or_sources_change(self):
        counter = {"n": 0}
        def fn():
            counter["n"] += 1
            return self.snap(generated=f"2026-10-01T05:30:{counter['n'] % 60:02d}Z")  # solo cambia generated_at
        port = self.build(fn, interval=0.05)
        # Con 1 conexión SSE solo cabe esperar 0 o 1 evento `activity` (el estado fijo), nunca 2.
        self.assertLess(self.read_sse_events(port, b"activity", timeout=1), 2)

    def test_loop_publishes_when_state_changes(self):
        states = iter(["thinking", "tool", "tool", "tool", "tool", "tool"] * 50)
        port = self.build(lambda: self.snap(state=next(states)), interval=0.05)
        self.assertGreaterEqual(self.read_sse_events(port, b"activity", timeout=3), 2)

    def test_loop_survives_a_failing_reader(self):
        calls = {"n": 0}
        def fn():
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("falla puntual")
            return self.snap(state="thinking" if calls["n"] < 3 else "tool")
        port = self.build(fn, interval=0.05)
        deadline = time.time() + 3
        while time.time() < deadline and calls["n"] < 4:
            time.sleep(0.05)
        self.assertGreaterEqual(calls["n"], 4)
        _, _, body = self.get(port, "/api/activity")
        self.assertEqual(json.loads(body)["agents"][0]["state"], "tool")
```

(El primer cálculo de `build_app` también debe tolerar que `fn` lance: ver Step 3.)

- [ ] **Step 2:** `python3 -m unittest tests.test_server -v` → FAIL (`build_app()` no acepta `activity_interval_seconds`).

- [ ] **Step 3: Implementar**

En `server.py`:

```python
# imports
from live import activity as live_activity

# junto a _state / _state_lock
_activity_lock = threading.Lock()
_activity = {"snapshot": None, "published": None}


def _empty_activity():
    return {"generated_at": None, "agents": [], "sources": {s: "unavailable" for s in live_activity.LIVE_SOURCES}}


def _activity_tick(broker, fn):
    """Un ciclo: calcula el snapshot, lo guarda y publica solo si agents/sources cambiaron."""
    try:
        snap = fn()
    except Exception:
        return
    key = json.dumps({"agents": snap["agents"], "sources": snap["sources"]}, sort_keys=True)
    with _activity_lock:
        _activity["snapshot"] = snap
        changed = _activity["published"] != key
        _activity["published"] = key
    if changed:
        broker.publish("activity", json.dumps(snap))


def _activity_loop(broker, interval, fn):
    while True:
        time.sleep(interval)
        _activity_tick(broker, fn)


def _current_activity_json():
    with _activity_lock:
        return json.dumps(_activity["snapshot"] or _empty_activity())
```

En `do_GET`, antes de `/api/stream`:

```python
            elif parsed.path == "/api/activity":
                self._send_json(_current_activity_json())
```

Y en `_handle_sse`, tras enviar el evento `usage` inicial, enviar también el actual de actividad:

```python
                self.wfile.write(format_sse_event("activity", _current_activity_json()))
```

`build_app`:

```python
def build_app(static_dir, poll_interval_seconds=60, port=0, db_path=None, engine_opts=None,
              activity_interval_seconds=2, activity_fn=None):
    ...
    fn = activity_fn or live_activity.snapshot
    with _activity_lock:
        _activity["snapshot"], _activity["published"] = None, None
    _activity_tick(broker, fn)  # primer snapshot antes de aceptar peticiones
    threading.Thread(target=_activity_loop, args=(broker, activity_interval_seconds, fn), daemon=True).start()
```

(Colocar este bloque junto a `_recompute_and_maybe_publish(broker)`. El `_activity_tick` inicial publica con broker sin suscriptores, sin efecto. Verificar que `SSEBroker.publish` sin suscriptores no falla: es el mismo caso que el `usage` inicial.)

- [ ] **Step 4:** `python3 -m unittest tests.test_server -v && python3 -m unittest discover -s tests 2>&1 | tail -3` → PASS.

- [ ] **Step 5: Changelog y commit**

`## [Sin publicar]` → `### Añadido`:
`- Actividad en vivo de Claude Code, OpenCode y Hermes: nuevo endpoint `GET /api/activity` y evento `activity` en `/api/stream` (estado por sesión: pensando, usando una herramienta, esperando o en pausa; sin textos ni argumentos).`

```bash
git add server.py tests/test_server.py CHANGELOG.md
git commit -m "feat(server): GET /api/activity y evento SSE activity cada 2 s"
```

---

### Task 9: Motor vendorizado, assets y lint (frontend)

**Files:**
- Restore from `spike/oficina`: `frontend/src/pixel/**` (excepto `OfficeStage.tsx`, `loadAssets.ts`, `trimLayout.ts` que se revisan abajo — se restauran también), `frontend/public/pixel/**`.
- Create: `frontend/.oxlintrc.json`, `frontend/scripts/gen-pixel-assets.ts`, `NOTICE`.
- Modify: `frontend/src/lib/routes.ts`, `frontend/src/components/Sidebar.tsx` (ruta e ítem del spike), `frontend/package.json` (si el spike añadió dependencias: ninguna esperada).

**Interfaces:**
- Produces: motor compilable (`OfficeState`, `OfficeCanvas`, `EditorState`), `loadOfficeAssets(base)`, `trimLayout(layout)`, ruta `office` → `/oficina`, ítem "Oficina" en el sidebar.

- [ ] **Step 1: Restaurar el spike**

```bash
git checkout spike/oficina -- frontend/src/pixel frontend/public/pixel
git checkout spike/oficina -- frontend/src/lib/routes.ts frontend/src/components/Sidebar.tsx
git status --short | head -5
```
Revisar `git diff --cached frontend/src/lib/routes.ts frontend/src/components/Sidebar.tsx` (solo debe añadir `office`/`/oficina`/`Building2`). **No** restaurar `lib/office.ts`, `App.tsx`, `OfficeView.tsx`: se rehacen en las Tasks 10–13. Si `routes.test.ts` existe, añadir un caso `parsePath("/oficina")` → `{ view: "office", client: null }` y su ida y vuelta con el helper de rutas que ya use el archivo.

- [ ] **Step 2: `.oxlintrc.json`**

```json
{
  "ignorePatterns": ["src/pixel/office/**"]
}
```

- [ ] **Step 3: Script generador de índices** (`frontend/scripts/gen-pixel-assets.ts`; se ejecuta a mano, no en el build)

```ts
/**
 * Regenera public/pixel/assets/asset-index.json y furniture-catalog.json a partir de las carpetas
 * de assets. Uso: `npx tsx scripts/gen-pixel-assets.ts` desde frontend/.
 */
import { readdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";

const ASSETS = join(import.meta.dirname, "..", "public", "pixel", "assets");
const pngs = (dir: string) => readdirSync(join(ASSETS, dir)).filter((f) => f.endsWith(".png")).sort();

const index = {
  floors: pngs("floors"),
  walls: pngs("walls"),
  characters: pngs("characters"),
  defaultLayout: "default-layout-1.json",
};
writeFileSync(join(ASSETS, "asset-index.json"), JSON.stringify(index));

type Member = Record<string, unknown>;
const catalog: Record<string, unknown>[] = [];
for (const dir of readdirSync(join(ASSETS, "furniture")).sort()) {
  const manifestPath = join(ASSETS, "furniture", dir, "manifest.json");
  if (!existsSync(manifestPath)) continue;
  const m = JSON.parse(readFileSync(manifestPath, "utf8")) as Member & { members?: Member[] };
  const base = (id: unknown, file: unknown, w: unknown, h: unknown, fw: unknown, fh: unknown) => ({
    id, name: m.name, label: m.name, category: m.category, file, width: w, height: h,
    footprintW: fw, footprintH: fh, isDesk: m.category === "desks",
    canPlaceOnWalls: m.canPlaceOnWalls, canPlaceOnSurfaces: m.canPlaceOnSurfaces,
    backgroundTiles: m.backgroundTiles, groupId: m.id,
  });
  if (m.type === "group" && m.members) {
    for (const mem of m.members) {
      catalog.push({
        ...base(mem.id, mem.file, mem.width, mem.height, mem.footprintW, mem.footprintH),
        orientation: mem.orientation,
        ...(mem.mirrorSide ? { mirrorSide: true } : {}),
        rotationScheme: m.rotationScheme,
        furniturePath: `furniture/${dir}/${mem.file}`,
      });
    }
  } else {
    catalog.push({
      ...base(m.id, `${m.id}.png`, m.width, m.height, m.footprintW, m.footprintH),
      furniturePath: `furniture/${dir}/${m.id}.png`,
    });
  }
}
writeFileSync(join(ASSETS, "furniture-catalog.json"), JSON.stringify(catalog));
console.log(`asset-index.json y furniture-catalog.json (${catalog.length} muebles) regenerados`);
```

- [ ] **Step 4: Verificar que reproduce los JSON del spike**

```bash
cd frontend
git show spike/oficina:frontend/public/pixel/assets/asset-index.json > /tmp/spike-index.json   # usar el scratchpad de la sesión en lugar de /tmp si se prefiere
git show spike/oficina:frontend/public/pixel/assets/furniture-catalog.json > /tmp/spike-catalog.json
npx tsx scripts/gen-pixel-assets.ts
node -e "
const a=require('fs');const eq=(x,y)=>require('assert').deepStrictEqual(JSON.parse(a.readFileSync(x)),JSON.parse(a.readFileSync(y)));
eq('public/pixel/assets/asset-index.json','/tmp/spike-index.json');
eq('public/pixel/assets/furniture-catalog.json','/tmp/spike-catalog.json');console.log('IGUALES')"
```
Expected: `IGUALES`. Si difiere, ajustar el generador (por ejemplo la regla de `isDesk` o los campos opcionales) hasta que coincida; `deepStrictEqual` ignora el orden de claves pero el generador debe producir el mismo conjunto de campos. Si `tsx` no está disponible: `npx --yes tsx`.

- [ ] **Step 5: `NOTICE` en la raíz**

```
ai-monitor incluye material de terceros:

- Motor de la oficina (frontend/src/pixel/): Pixel Agents, MIT, © Pablo De Lucca.
  https://github.com/pablodelucca/pixel-agents — licencia en frontend/src/pixel/LICENSE.
- Personajes (frontend/public/pixel/assets/characters/): basados en "MetroCity Free Topdown
  Character Pack" de JIK-A-4, licencia CC0 (dominio público; el crédito no es obligatorio).
- Mobiliario, suelos y paredes (frontend/public/pixel/assets/): assets abiertos que Pixel Agents
  incorporó al sustituir su tileset propietario (PR #117 de pixel-agents).
```

(Comprobar el titular del copyright en `frontend/src/pixel/LICENSE` y copiar su nombre exacto.)

- [ ] **Step 6: Verificar tipos, lint y build**

```bash
cd frontend && npx tsc -b && npm run lint && npm run build 2>&1 | tail -8
```
Expected: sin errores de tipo; oxlint sin avisos en código propio (`src/pixel/office/**` ignorado); build correcto y `OfficeStage` en su propio chunk. **`OfficeStage.tsx` del spike todavía referencia `OfficeAgent.active`/`lastMs`**: si `tsc` falla por eso, es esperado hasta la Task 10; en ese caso comprobar solo que los errores se limitan a `OfficeStage.tsx`/`OfficeView` y seguir (no commitear con `tsc` roto: ver Step 7).

- [ ] **Step 7: Commit** — para dejar la rama compilable, ejecutar esta tarea y la 10 antes de commitear solo si `tsc` falla; si `tsc` pasa:

```bash
git add frontend NOTICE
git commit -m "feat(oficina): motor de Pixel Agents vendorizado, assets y generador de índices"
```
Si `tsc` falla por `OfficeStage.tsx`, quitarlo del commit (`git restore --staged frontend/src/pixel/OfficeStage.tsx`) y añadirlo en la Task 13.

---

### Task 10: `lib/activity.ts` y `OfficeAgent` nuevo

**Files:**
- Create: `frontend/src/lib/activity.ts`, `frontend/src/lib/activity.test.ts`
- Create: `frontend/src/lib/office.ts`, `frontend/src/lib/office.test.ts` (adaptados del spike: `git show spike/oficina:frontend/src/lib/office.ts`)

**Interfaces:**
- Produces en `lib/activity.ts`:
  ```ts
  export type ActivityState = "tool" | "waiting" | "thinking" | "idle";
  export type ToolKind = "edit" | "read" | "run" | "other";
  export interface ActivityAgent { key: string; source: string; project: string; state: ActivityState; tool: string | null; tool_kind: ToolKind | null; since: string }
  export interface ActivitySnapshot { generated_at: string | null; agents: ActivityAgent[]; sources: Record<string, "ok" | "unavailable"> }
  export const LIVE_SOURCES = ["claude_code", "opencode", "hermes"] as const;
  export function mergeOfficeAgents(activity: ActivitySnapshot | null, sources: UsageSnapshot["sources"] | null | undefined, nowMs: number, limit?: number): OfficeAgent[]
  export function fetchActivity(fetchImpl?: typeof fetch, timeoutMs?: number): Promise<ActivitySnapshot | null>
  ```
- Produces en `lib/office.ts`: `OFFICE_WINDOW_MS`, `OFFICE_MAX_AGENTS = 12`, `BASIC_THINKING_MS = 3 * 60_000`,
  ```ts
  export interface OfficeAgent { key: string; source: (typeof SESSION_SOURCES)[number]; project: string; label: string; state: ActivityState; tool: string | null; toolKind: ToolKind | null; sinceMs: number; live: boolean }
  export function deriveOfficeAgents(sources, nowMs, limit?): OfficeAgent[]
  export function basename(path: string): string
  ```

- [ ] **Step 1: Tests que fallan**

`frontend/src/lib/office.test.ts` (adaptación del spike; `< 3 min` → `thinking`, resto `idle`, `live: false`):

```ts
import { describe, expect, it } from "vitest";
import type { SessionDetailEntry, UsageSnapshot } from "@/lib/api";
import { BASIC_THINKING_MS, OFFICE_WINDOW_MS, deriveOfficeAgents } from "@/lib/office";

const NOW = Date.parse("2026-10-01T12:00:00Z");

function session(id: string, lastMs: number | string): SessionDetailEntry {
  const last_ts = typeof lastMs === "number" ? new Date(lastMs).toISOString() : lastMs;
  return { session_id: id, tokens: 1, cost: 0, title: null, first_ts: null, last_ts, cwd: null, date: null };
}

export function sources(entries: Record<string, Record<string, SessionDetailEntry[]>>): UsageSnapshot["sources"] {
  const out: Record<string, unknown> = {};
  for (const [source, projects] of Object.entries(entries)) {
    out[source] = Object.fromEntries(Object.entries(projects).map(([p, s]) => [p, { sessions_detail: s }]));
  }
  return out as UsageSnapshot["sources"];
}

describe("deriveOfficeAgents", () => {
  it("convierte cada sesión reciente en un agente básico: thinking < 3 min, idle después", () => {
    const agents = deriveOfficeAgents(
      sources({
        claude_code: { "/srv/acme/web": [session("a", NOW - 60_000)] },
        codex: { "/srv/acme/api": [session("b", NOW - BASIC_THINKING_MS - 1)] },
      }),
      NOW,
    );
    expect(agents).toEqual([
      { key: "claude_code:a", source: "claude_code", project: "/srv/acme/web", label: "web", state: "thinking",
        tool: null, toolKind: null, sinceMs: NOW - 60_000, live: false },
      { key: "codex:b", source: "codex", project: "/srv/acme/api", label: "api", state: "idle",
        tool: null, toolKind: null, sinceMs: NOW - BASIC_THINKING_MS - 1, live: false },
    ]);
  });

  it("descarta sesiones fuera de la ventana, sin last_ts o con fecha inválida", () => {
    const stale = session("viejo", NOW - OFFICE_WINDOW_MS - 1);
    const noTs = { ...session("sin", NOW), last_ts: null };
    const broken = session("roto", "no-es-fecha");
    expect(deriveOfficeAgents(sources({ claude_code: { "/p": [stale, noTs, broken] } }), NOW)).toEqual([]);
  });

  it("ignora OpenRouter, ordena por actividad reciente y respeta el límite", () => {
    const agents = deriveOfficeAgents(
      sources({
        claude_code: { "/p/uno": [session("1", NOW - 5_000), session("2", NOW - 1_000), session("3", NOW - 9_000)] },
        openrouter: { "/p/or": [session("x", NOW)] },
      }),
      NOW,
      2,
    );
    expect(agents.map((a) => a.key)).toEqual(["claude_code:2", "claude_code:1"]);
  });

  it("acepta epoch en ms (OpenCode) y descarta marcas en el futuro", () => {
    const opencode = { ...session("oc", NOW), last_ts: NOW - 30_000 };
    const future = session("fut", NOW + 10 * 60_000);
    const agents = deriveOfficeAgents(sources({ opencode: { "/p/oc": [opencode] }, claude_code: { "/p/f": [future] } }), NOW);
    expect(agents.map((a) => [a.key, a.state])).toEqual([["opencode:oc", "thinking"]]);
  });

  it("devuelve [] sin datos", () => {
    expect(deriveOfficeAgents(null, NOW)).toEqual([]);
  });
});
```

`frontend/src/lib/activity.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";
import type { SessionDetailEntry, UsageSnapshot } from "@/lib/api";
import { fetchActivity, mergeOfficeAgents, type ActivityAgent, type ActivitySnapshot } from "@/lib/activity";
import { OFFICE_MAX_AGENTS } from "@/lib/office";

const NOW = Date.parse("2026-10-01T12:00:00Z");
const iso = (ms: number) => new Date(ms).toISOString().replace(/\.\d{3}Z$/, "Z");

function sess(id: string, lastMs: number): SessionDetailEntry {
  return { session_id: id, tokens: 1, cost: 0, title: null, first_ts: null, last_ts: new Date(lastMs).toISOString(), cwd: null, date: null };
}
function usage(entries: Record<string, Record<string, SessionDetailEntry[]>>): UsageSnapshot["sources"] {
  const out: Record<string, unknown> = {};
  for (const [s, p] of Object.entries(entries)) {
    out[s] = Object.fromEntries(Object.entries(p).map(([k, v]) => [k, { sessions_detail: v }]));
  }
  return out as UsageSnapshot["sources"];
}
function agent(key: string, over: Partial<ActivityAgent> = {}): ActivityAgent {
  const [source] = key.split(":");
  return { key, source, project: "/srv/acme/web", state: "tool", tool: "Bash", tool_kind: "run", since: iso(NOW - 3_000), ...over };
}
function act(agents: ActivityAgent[], sources: ActivitySnapshot["sources"]): ActivitySnapshot {
  return { generated_at: iso(NOW), agents, sources };
}
const ALL_OK = { claude_code: "ok", opencode: "ok", hermes: "ok" } as const;

describe("mergeOfficeAgents", () => {
  it("sin activity (null) todo viene del estado básico de /api/usage", () => {
    const agents = mergeOfficeAgents(null, usage({ claude_code: { "/p": [sess("a", NOW - 1_000)] } }), NOW);
    expect(agents.map((a) => [a.key, a.live, a.state])).toEqual([["claude_code:a", false, "thinking"]]);
  });

  it("una fuente en vivo 'ok' viene de activity y sus sesiones de usage se descartan", () => {
    const agents = mergeOfficeAgents(
      act([agent("claude_code:a")], ALL_OK),
      usage({ claude_code: { "/p": [sess("a", NOW - 1_000), sess("otra", NOW - 2_000)] } }),
      NOW,
    );
    expect(agents).toEqual([{
      key: "claude_code:a", source: "claude_code", project: "/srv/acme/web", label: "web", state: "tool",
      tool: "Bash", toolKind: "run", sinceMs: NOW - 3_000, live: true,
    }]);
  });

  it("una fuente 'unavailable' cae al estado básico de usage", () => {
    const agents = mergeOfficeAgents(
      act([], { ...ALL_OK, hermes: "unavailable" }),
      usage({ hermes: { "/h": [sess("h1", NOW - 5_000)] } }),
      NOW,
    );
    expect(agents.map((a) => [a.key, a.live])).toEqual([["hermes:h1", false]]);
  });

  it("Codex siempre sale de usage, aunque activity esté 'ok' en todo lo demás", () => {
    const agents = mergeOfficeAgents(act([], ALL_OK), usage({ codex: { "/c": [sess("c1", NOW - 5_000)] } }), NOW);
    expect(agents.map((a) => [a.key, a.live])).toEqual([["codex:c1", false]]);
  });

  it("nunca incluye OpenRouter", () => {
    const agents = mergeOfficeAgents(null, usage({ openrouter: { "/or": [sess("x", NOW)] } }), NOW);
    expect(agents).toEqual([]);
  });

  it("si una key llega de ambos lados gana activity", () => {
    const agents = mergeOfficeAgents(
      act([agent("claude_code:a", { state: "waiting" })], ALL_OK),
      usage({ claude_code: { "/p": [sess("a", NOW - 1_000)] } }),
      NOW,
    );
    expect(agents).toHaveLength(1);
    expect(agents[0].state).toBe("waiting");
    expect(agents[0].live).toBe(true);
  });

  it("ordena por sinceMs descendente y respeta el tope", () => {
    const many = Array.from({ length: OFFICE_MAX_AGENTS + 5 }, (_, i) =>
      agent(`claude_code:s${i}`, { since: iso(NOW - (i + 1) * 1_000) }));
    const agents = mergeOfficeAgents(act(many, ALL_OK), usage({}), NOW);
    expect(agents).toHaveLength(OFFICE_MAX_AGENTS);
    expect(agents[0].key).toBe("claude_code:s0");
    expect(agents.map((a) => a.sinceMs)).toEqual([...agents.map((a) => a.sinceMs)].sort((a, b) => b - a));
  });

  it("ignora agentes de activity con fecha o fuente inválidas", () => {
    const agents = mergeOfficeAgents(
      act([agent("claude_code:ok"), agent("claude_code:mala", { since: "no-es-fecha" }), agent("codex:x", { source: "codex" })], ALL_OK),
      usage({}),
      NOW,
    );
    expect(agents.map((a) => a.key)).toEqual(["claude_code:ok"]);
  });

  it("un proyecto 'unknown' no rompe la etiqueta", () => {
    const agents = mergeOfficeAgents(act([agent("claude_code:a", { project: "unknown" })], ALL_OK), usage({}), NOW);
    expect(agents[0].label).toBe("unknown");
  });
});

describe("fetchActivity", () => {
  it("devuelve el snapshot si la respuesta es 200", async () => {
    const snap = act([], ALL_OK);
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => snap });
    await expect(fetchActivity(fetchImpl as unknown as typeof fetch)).resolves.toEqual(snap);
    expect(fetchImpl.mock.calls[0][0]).toBe("/api/activity");
  });

  it("devuelve null ante error de red, estado no-ok o cuerpo inválido", async () => {
    await expect(fetchActivity(vi.fn().mockRejectedValue(new Error("red")) as unknown as typeof fetch)).resolves.toBeNull();
    await expect(fetchActivity(vi.fn().mockResolvedValue({ ok: false }) as unknown as typeof fetch)).resolves.toBeNull();
    await expect(
      fetchActivity(vi.fn().mockResolvedValue({ ok: true, json: async () => ({ otra: 1 }) }) as unknown as typeof fetch),
    ).resolves.toBeNull();
  });

  it("aborta pasados 5 s", async () => {
    vi.useFakeTimers();
    const fetchImpl = vi.fn((_url: string, init?: RequestInit) =>
      new Promise((_res, rej) => init?.signal?.addEventListener("abort", () => rej(new Error("abort")))));
    const pending = fetchActivity(fetchImpl as unknown as typeof fetch, 5_000);
    await vi.advanceTimersByTimeAsync(5_001);
    await expect(pending).resolves.toBeNull();
    vi.useRealTimers();
  });
});
```

- [ ] **Step 2:** `cd frontend && npx vitest run src/lib/office.test.ts src/lib/activity.test.ts` → FAIL (módulos inexistentes).

- [ ] **Step 3: Implementar `lib/office.ts`**

```ts
/**
 * Oficina pixel-art: estado básico de las sesiones a partir de /api/usage (granularidad del
 * colector, ~60 s). La actividad en vivo (herramienta en curso) llega por /api/activity y se
 * fusiona en lib/activity.ts.
 */
import { SESSION_SOURCES, collectSessions, toEpochMs } from "@/lib/sessions";
import type { UsageSnapshot } from "@/lib/api";
import type { ActivityState, ToolKind } from "@/lib/activity";

/** Una sesión con actividad en esta ventana tiene personaje en la oficina. */
export const OFFICE_WINDOW_MS = 30 * 60_000;
/** Estado básico: activa hace menos de esto → "thinking"; después → "idle". */
export const BASIC_THINKING_MS = 3 * 60_000;
export const OFFICE_MAX_AGENTS = 12;
/** Tolerancia de reloj: una marca algo adelantada sigue contando como "ahora". */
const CLOCK_SKEW_MS = 60_000;

export interface OfficeAgent {
  key: string;
  source: (typeof SESSION_SOURCES)[number];
  project: string;
  label: string;
  state: ActivityState;
  tool: string | null;
  toolKind: ToolKind | null;
  sinceMs: number;
  /** true si vino de /api/activity; false si es el estado básico de /api/usage. */
  live: boolean;
}

export function basename(path: string): string {
  return path.split("/").filter(Boolean).pop() ?? path;
}

export function deriveOfficeAgents(
  sources: UsageSnapshot["sources"] | null | undefined,
  nowMs: number,
  limit: number = OFFICE_MAX_AGENTS,
): OfficeAgent[] {
  const agents: OfficeAgent[] = [];
  for (const s of collectSessions(sources, "all")) {
    const lastMs = toEpochMs(s.last_ts);
    if (lastMs === null || lastMs > nowMs + CLOCK_SKEW_MS || nowMs - lastMs > OFFICE_WINDOW_MS) continue;
    agents.push({
      key: `${s.source}:${s.session_id}`,
      source: s.source as OfficeAgent["source"],
      project: s.project,
      label: basename(s.project),
      state: nowMs - lastMs < BASIC_THINKING_MS ? "thinking" : "idle",
      tool: null,
      toolKind: null,
      sinceMs: lastMs,
      live: false,
    });
  }
  return agents.sort((a, b) => b.sinceMs - a.sinceMs).slice(0, limit);
}
```

- [ ] **Step 4: Implementar `lib/activity.ts`**

```ts
import type { UsageSnapshot } from "@/lib/api";
import { OFFICE_MAX_AGENTS, basename, deriveOfficeAgents, type OfficeAgent } from "@/lib/office";

export type ActivityState = "tool" | "waiting" | "thinking" | "idle";
export type ToolKind = "edit" | "read" | "run" | "other";

export interface ActivityAgent {
  key: string;
  source: string;
  project: string;
  state: ActivityState;
  tool: string | null;
  tool_kind: ToolKind | null;
  since: string;
}

export interface ActivitySnapshot {
  generated_at: string | null;
  agents: ActivityAgent[];
  sources: Record<string, "ok" | "unavailable">;
}

/** Fuentes con detección en vivo; Codex solo tiene el estado básico de /api/usage. */
export const LIVE_SOURCES = ["claude_code", "opencode", "hermes"] as const;
const isLiveSource = (s: string): s is (typeof LIVE_SOURCES)[number] => (LIVE_SOURCES as readonly string[]).includes(s);

export function mergeOfficeAgents(
  activity: ActivitySnapshot | null,
  sources: UsageSnapshot["sources"] | null | undefined,
  nowMs: number,
  limit: number = OFFICE_MAX_AGENTS,
): OfficeAgent[] {
  const byKey = new Map<string, OfficeAgent>();
  for (const a of deriveOfficeAgents(sources, nowMs, Infinity)) {
    const liveOk = isLiveSource(a.source) && activity?.sources[a.source] === "ok";
    if (!liveOk) byKey.set(a.key, a);
  }
  for (const a of activity?.agents ?? []) {
    const sinceMs = Date.parse(a.since);
    if (!isLiveSource(a.source) || activity?.sources[a.source] !== "ok" || Number.isNaN(sinceMs)) continue;
    byKey.set(a.key, {
      key: a.key,
      source: a.source,
      project: a.project,
      label: basename(a.project),
      state: a.state,
      tool: a.tool,
      toolKind: a.tool_kind,
      sinceMs,
      live: true,
    });
  }
  return [...byKey.values()].sort((a, b) => b.sinceMs - a.sinceMs).slice(0, limit);
}

const isSnapshot = (v: unknown): v is ActivitySnapshot =>
  typeof v === "object" && v !== null && Array.isArray((v as ActivitySnapshot).agents) &&
  typeof (v as ActivitySnapshot).sources === "object";

/** Snapshot inicial; null si falla (la vista sigue con el estado básico hasta el primer evento SSE). */
export async function fetchActivity(fetchImpl: typeof fetch = fetch, timeoutMs = 5_000): Promise<ActivitySnapshot | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetchImpl("/api/activity", { signal: controller.signal });
    if (!res.ok) return null;
    const body: unknown = await res.json();
    return isSnapshot(body) ? body : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
```

(La dependencia circular `office.ts` ↔ `activity.ts` es solo de tipos en un sentido (`import type`), así que no hay ciclo en tiempo de ejecución.)

- [ ] **Step 5:** `npx vitest run && npx tsc -b 2>&1 | head` → los tests pasan; `tsc` solo puede quejarse de `OfficeStage.tsx`/`OfficeView.tsx` (se rehacen en la Task 13).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib
git commit -m "feat(oficina): fusión de actividad en vivo con el estado básico de uso"
```

---

### Task 11: `useUsageStream` — evento `activity` y snapshot inicial

**Files:**
- Modify: `frontend/src/hooks/useUsageStream.ts`

**Interfaces:**
- Consumes: `ActivitySnapshot`, `fetchActivity` de `@/lib/activity`.
- Produces: `useUsageStream()` devuelve además `activity: ActivitySnapshot | null`. Sigue habiendo **un único** `EventSource`.

- [ ] **Step 1: Implementar** (los hooks del repo no tienen tests unitarios; la lógica testeable ya está en `fetchActivity`)

```ts
import { useEffect, useRef, useState } from "react";
import type { UsageSnapshot } from "@/lib/api";
import { fetchActivity, type ActivitySnapshot } from "@/lib/activity";

export function useUsageStream() {
  const [snapshot, setSnapshot] = useState<UsageSnapshot | null>(null);
  const [activity, setActivity] = useState<ActivitySnapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const [recommendationsVersion, setRecommendationsVersion] = useState(0);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource("/api/stream");
    sourceRef.current = es;
    let alive = true;

    es.addEventListener("usage", (event) => {
      const data = JSON.parse((event as MessageEvent).data) as UsageSnapshot;
      setSnapshot(data);
      setConnected(true);
    });

    es.addEventListener("activity", (event) => {
      setActivity(JSON.parse((event as MessageEvent).data) as ActivitySnapshot);
    });

    es.addEventListener("recommendations", () => setRecommendationsVersion((n) => n + 1));

    es.onerror = () => setConnected(false);

    // Snapshot inicial: si falla queda null hasta el primer evento SSE (sin romper la vista).
    void fetchActivity().then((snap) => {
      if (alive && snap) setActivity((prev) => prev ?? snap);
    });

    return () => {
      alive = false;
      es.close();
    };
  }, []);

  return {
    sources: snapshot?.sources ?? null,
    combined: snapshot?.combined ?? null,
    activity,
    connected,
    recommendationsVersion,
  };
}
```

- [ ] **Step 2:** `cd frontend && npx tsc -b 2>&1 | head -5 && npm run lint` → sin errores en este archivo.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useUsageStream.ts
git commit -m "feat(oficina): el stream expone la actividad en vivo"
```

---

### Task 12: Funciones puras del escenario (`fitZoom`, `engineState`)

**Files:**
- Create: `frontend/src/pixel/fitZoom.ts`, `frontend/src/pixel/fitZoom.test.ts`, `frontend/src/pixel/engineState.ts`, `frontend/src/pixel/engineState.test.ts`

**Interfaces:**
- Produces:
  ```ts
  export function fitZoom(containerW: number, containerH: number, cols: number, rows: number, dpr: number): number
  export interface EngineState { active: boolean; tool: "Read" | "Edit" | null; waiting: boolean }
  export function toEngineState(agent: Pick<OfficeAgent, "state" | "toolKind">): EngineState
  export function engineStateKey(s: EngineState): string
  ```

- [ ] **Step 1: Tests que fallan**

```ts
// fitZoom.test.ts
import { describe, expect, it } from "vitest";
import { fitZoom } from "@/pixel/fitZoom";

describe("fitZoom", () => {
  it("en escritorio elige el mayor entero que cabe (> 2)", () => {
    // 20x12 baldosas de 16 px: a z=5 → 1600x960 ≤ 1700x1000
    expect(fitZoom(1700, 1000, 20, 12, 1)).toBe(5);
  });
  it("tiene en cuenta el devicePixelRatio", () => {
    expect(fitZoom(850, 500, 20, 12, 2)).toBe(5);
  });
  it("en móvil de 390 px devuelve 2", () => {
    expect(fitZoom(390, 360, 20, 12, 1)).toBe(2);
  });
  it("contenedor diminuto o cero devuelve 2", () => {
    expect(fitZoom(10, 10, 20, 12, 1)).toBe(2);
    expect(fitZoom(0, 0, 20, 12, 1)).toBe(2);
  });
  it("lo limita el eje más estrecho", () => {
    expect(fitZoom(4000, 200, 20, 12, 1)).toBe(2);
  });
});
```

```ts
// engineState.test.ts
import { describe, expect, it } from "vitest";
import { engineStateKey, toEngineState } from "@/pixel/engineState";

describe("toEngineState", () => {
  it("tool: activo; read → Read, el resto → Edit", () => {
    expect(toEngineState({ state: "tool", toolKind: "read" })).toEqual({ active: true, tool: "Read", waiting: false });
    for (const kind of ["edit", "run", "other", null] as const) {
      expect(toEngineState({ state: "tool", toolKind: kind })).toEqual({ active: true, tool: "Edit", waiting: false });
    }
  });
  it("waiting: igual que tool más la burbuja", () => {
    expect(toEngineState({ state: "waiting", toolKind: "run" })).toEqual({ active: true, tool: "Edit", waiting: true });
    expect(toEngineState({ state: "waiting", toolKind: "read" })).toEqual({ active: true, tool: "Read", waiting: true });
  });
  it("thinking: activo con Edit; idle: inactivo", () => {
    expect(toEngineState({ state: "thinking", toolKind: null })).toEqual({ active: true, tool: "Edit", waiting: false });
    expect(toEngineState({ state: "idle", toolKind: null })).toEqual({ active: false, tool: null, waiting: false });
  });
  it("la clave solo cambia cuando cambia el estado o la clase del agente", () => {
    const a = engineStateKey(toEngineState({ state: "tool", toolKind: "run" }));
    const b = engineStateKey(toEngineState({ state: "tool", toolKind: "other" })); // misma animación
    const c = engineStateKey(toEngineState({ state: "tool", toolKind: "read" }));
    expect(a).toBe(b);
    expect(a).not.toBe(c);
  });
});
```

- [ ] **Step 2:** `npx vitest run src/pixel` → FAIL.

- [ ] **Step 3: Implementar**

```ts
// fitZoom.ts
const TILE = 16;
const MIN_ZOOM = 2;

/** Mayor zoom entero ≥ 2 con el que el mapa (cols×rows baldosas de 16 px) cabe en el contenedor. */
export function fitZoom(containerW: number, containerH: number, cols: number, rows: number, dpr: number): number {
  if (cols <= 0 || rows <= 0) return MIN_ZOOM;
  const byW = Math.floor((containerW * dpr) / (cols * TILE));
  const byH = Math.floor((containerH * dpr) / (rows * TILE));
  return Math.max(MIN_ZOOM, Math.min(byW, byH));
}
```

```ts
// engineState.ts
import type { OfficeAgent } from "@/lib/office";

export interface EngineState {
  active: boolean;
  tool: "Read" | "Edit" | null;
  waiting: boolean;
}

/** Tabla de §5.2 del spec: estado de actividad → llamadas a OfficeState. */
export function toEngineState(agent: Pick<OfficeAgent, "state" | "toolKind">): EngineState {
  switch (agent.state) {
    case "tool":
    case "waiting":
      return { active: true, tool: agent.toolKind === "read" ? "Read" : "Edit", waiting: agent.state === "waiting" };
    case "thinking":
      return { active: true, tool: "Edit", waiting: false };
    default:
      return { active: false, tool: null, waiting: false };
  }
}

/** Clave estable: solo cambia si hay que volver a llamar al motor (evita reiniciar animaciones). */
export const engineStateKey = (s: EngineState): string => `${s.active}|${s.tool}|${s.waiting}`;
```

- [ ] **Step 4:** `npx vitest run src/pixel && npm run lint` → PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pixel/fitZoom.ts frontend/src/pixel/fitZoom.test.ts frontend/src/pixel/engineState.ts frontend/src/pixel/engineState.test.ts
git commit -m "feat(oficina): zoom adaptable y mapeo de estados al motor"
```

---

### Task 13: `OfficeStage`, `OfficeView` y cableado en `App`

**Files:**
- Modify: `frontend/src/pixel/OfficeStage.tsx` (de la versión del spike)
- Create: `frontend/src/views/OfficeView.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `OfficeAgent`, `mergeOfficeAgents`, `ActivitySnapshot`, `useUsageStream().activity`, `fitZoom`, `toEngineState`, `engineStateKey`, `trimLayout`, `OfficeState.{addAgent,removeAgent,setAgentActive,setAgentTool,showWaitingBubble,getLayout}`.
- Produces: `<OfficeStage agents onSelect />` y `<OfficeView sources activity onSelectProject />`.

- [ ] **Step 1: `OfficeStage.tsx`** — conservar lo del spike (carga de assets, ids, `OfficeCanvas`) y cambiar tres cosas:

(a) Sincronización con diff contra el último estado aplicado:

```tsx
import { engineStateKey, toEngineState } from "./engineState";
import { fitZoom } from "./fitZoom";
...
  const applied = useRef(new Map<number, string>());

  useEffect(() => {
    if (status !== "ready") return;
    const present = new Set<string>();
    for (const agent of agents) {
      present.add(agent.key);
      let id = ids.current.get(agent.key);
      if (id === undefined) {
        id = nextId.current++;
        ids.current.set(agent.key, id);
        office.addAgent(id, undefined, undefined, undefined, false, agent.label);
      }
      const next = toEngineState(agent);
      const key = engineStateKey(next);
      if (applied.current.get(id) === key) continue;
      applied.current.set(id, key);
      office.setAgentActive(id, next.active);
      office.setAgentTool(id, next.tool);
      if (next.waiting) office.showWaitingBubble(id);
    }
    for (const [key, id] of ids.current) {
      if (present.has(key)) continue;
      office.removeAgent(id);
      ids.current.delete(key);
      applied.current.delete(id);
    }
  }, [agents, office, status]);
```

(b) Zoom adaptable con `ResizeObserver` sobre el contenedor, usando el layout recortado:

```tsx
  const containerRef = useRef<HTMLDivElement>(null);
  const layoutSize = useRef({ cols: 0, rows: 0 });
  // dentro del efecto de carga de assets, tras rebuildFromLayout(trimLayout(layout)):
  //   const trimmed = trimLayout(layout); layoutSize.current = { cols: trimmed.cols, rows: trimmed.rows };

  useEffect(() => {
    if (status !== "ready" || !containerRef.current) return;
    const el = containerRef.current;
    const refit = () => {
      const { cols, rows } = layoutSize.current;
      const z = fitZoom(el.clientWidth, el.clientHeight, cols, rows, window.devicePixelRatio || 1);
      setZoom(z);
      const fits = cols * 16 * z <= el.clientWidth * (window.devicePixelRatio || 1)
        && rows * 16 * z <= el.clientHeight * (window.devicePixelRatio || 1);
      if (fits) panRef.current = { x: 0, y: 0 }; // si cabe, el pan se fija en 0; si no, se arrastra
    };
    refit();
    const ro = new ResizeObserver(refit);
    ro.observe(el);
    return () => ro.disconnect();
  }, [status]);
```

y `ref={containerRef}` en el `div` contenedor. Reemplazar el `useState` inicial de `zoom` por `useState(2)`.

(c) Quitar `OfficeAgent.active`/`lastMs` de cualquier referencia (`handleClick` sigue igual).

- [ ] **Step 2: `OfficeView.tsx`**

```tsx
import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import { SourceChip } from "@/components/SourceChip";
import { SectionFallback } from "@/views/SectionFallback";
import type { UsageSnapshot } from "@/lib/api";
import { LIVE_SOURCES, mergeOfficeAgents, type ActivitySnapshot } from "@/lib/activity";
import type { OfficeAgent } from "@/lib/office";

// El motor Canvas va en su propio chunk: solo se descarga al abrir la oficina.
const OfficeStage = lazy(() => import("@/pixel/OfficeStage"));

const SOURCE_LABEL: Record<(typeof LIVE_SOURCES)[number], string> = {
  claude_code: "Claude Code",
  opencode: "OpenCode",
  hermes: "Hermes",
};

export function statusText(agent: OfficeAgent, nowMs: number): string {
  switch (agent.state) {
    case "tool":
      if (agent.toolKind === "run") return `ejecutando ${agent.tool}`;
      if (agent.toolKind === "edit") return "editando";
      if (agent.toolKind === "read") return "leyendo";
      return `usando ${agent.tool}`;
    case "waiting":
      return `esperando · ${Math.max(0, Math.round((nowMs - agent.sinceMs) / 1000))} s`;
    case "thinking":
      return "pensando";
    default:
      return "en pausa";
  }
}

interface OfficeViewProps {
  sources: UsageSnapshot["sources"] | null;
  activity: ActivitySnapshot | null;
  onSelectProject: (project: string | null) => void;
}

export function OfficeView({ sources, activity, onSelectProject }: OfficeViewProps) {
  const [now, setNow] = useState(() => Date.now());
  const agents = useMemo(() => mergeOfficeAgents(activity, sources, now), [activity, sources, now]);
  const anyWaiting = agents.some((a) => a.state === "waiting");

  // Cada segundo mientras haya un agente esperando (contador de segundos); si no, cada 15 s.
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), anyWaiting ? 1_000 : 15_000);
    return () => window.clearInterval(timer);
  }, [anyWaiting]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Oficina</h1>
        <p className="text-sm text-muted-foreground">Actividad en vivo de las sesiones de los últimos 30 min.</p>
      </div>
      <Suspense fallback={<SectionFallback label="Cargando oficina" />}>
        <OfficeStage agents={agents} onSelect={(a) => onSelectProject(a.project)} />
      </Suspense>
      {agents.length === 0 ? (
        <p className="text-sm text-muted-foreground">La oficina está vacía: ninguna sesión reciente.</p>
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {agents.map((a) => (
            <li key={a.key}>
              <button
                type="button"
                onClick={() => onSelectProject(a.project)}
                className="flex w-full items-center justify-between gap-2 rounded-md border px-3 py-2 text-left text-sm hover:bg-muted"
              >
                <span className="truncate font-medium">{a.label}</span>
                <span className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">{statusText(a, now)}</span>
                  <SourceChip source={a.source} />
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs text-muted-foreground">
        En vivo:{" "}
        {LIVE_SOURCES.map((s, i) => (
          <span key={s}>
            {i > 0 && " · "}
            {SOURCE_LABEL[s]}
            {activity?.sources[s] === "ok" ? "" : " (no disponible)"}
          </span>
        ))}
        {" · "}Codex: estado básico
      </p>
    </div>
  );
}
```

Añadir a `frontend/src/views/` un test `OfficeView.test.ts` **solo** para `statusText` (función pura exportada): `run` → `"ejecutando Bash"`, `edit` → `"editando"`, `read` → `"leyendo"`, `other` → `"usando mcp__x"`, `waiting` con `sinceMs = now - 12_400` → `"esperando · 12 s"`, `thinking` → `"pensando"`, `idle` → `"en pausa"`. (El archivo de la vista es `.tsx`; el test importa `statusText` desde `@/views/OfficeView`.)

- [ ] **Step 3: `App.tsx`** — importar `OfficeView`, obtener `activity` de `useUsageStream()` junto a `sources`, y añadir:

```tsx
{route.view === "office" && <OfficeView sources={sources} activity={activity} onSelectProject={route.setSelectedProject} />}
```

(Mantener la forma de las demás ramas del archivo; ver el diff del spike como referencia: `git diff main spike/oficina -- frontend/src/App.tsx`.)

- [ ] **Step 4: Verificar**

```bash
cd frontend && npx tsc -b && npm run lint && npm test 2>&1 | tail -6 && npm run build 2>&1 | tail -6
```
Expected: todo en verde; el chunk de `OfficeStage` sigue siendo lazy y pequeño (~20 kB gzip, como en el spike).

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(oficina): vista /oficina con actividad en vivo y zoom adaptable"
```

Añadir a `CHANGELOG.md` (`### Añadido`, `## [Sin publicar]`) **en este mismo commit**:
`- Vista Oficina (`/oficina`): cada sesión reciente es un personaje pixel-art que se sienta a trabajar, lee, ejecuta comandos o espera según lo que hace en ese momento.`

---

### Task 14: Documentación

**Files:**
- Modify: `CLAUDE.md`, `README.md`

(`NOTICE` ya se creó en la Task 9; las líneas de `CHANGELOG.md` se añadieron en las Tasks 1, 8 y 13.)

- [ ] **Step 1: `CLAUDE.md`** — en "Architecture", tras la entrada de `recommend/`, añadir:

```markdown
- **`live/`** alimenta la Oficina (`GET /api/activity` y el evento SSE `activity`). **No es un colector**: no entra en `main.collect_all()`, no escribe en `history.db` ni en ningún archivo y solo abre bases ajenas en solo lectura (`mode=ro`). Un lector por fuente (`claude_code.py`, `opencode.py`, `hermes.py`) produce `SessionFacts`; solo `model.py` decide el estado (`tool`/`waiting`/`thinking`/`idle`). Un lector lanza `SourceUnavailable` si no pudo leer la fuente y devuelve `[]` si no hay sesiones recientes; `activity.snapshot` degrada por fuente. **Nunca transmite textos, argumentos, rutas tocadas ni salidas de herramientas**: solo el nombre de la herramienta, su clase y marcas de tiempo. `server.py` lo ejecuta en un hilo propio cada 2 s y `GET /api/activity` devuelve el último snapshot sin leer nada en el hilo de la petición. Codex no tiene detección en vivo (usa el estado básico de `/api/usage`).
```

y en la lista de endpoints de `frontend/`, añadir `/api/activity`.

- [ ] **Step 2: `README.md`** — sección breve "Oficina": qué es (`/oficina`), qué fuentes tienen actividad en vivo (Claude Code, OpenCode, Hermes; Codex estado básico), que no sale ningún texto de las sesiones, y el enlace `[NOTICE](NOTICE)` con los créditos de terceros.

- [ ] **Step 3: Comprobar portabilidad y commit**

```bash
grep -rn "/home/jruedadev\|~/DEV/JRDV" --include="*" -I . --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.worktrees --exclude-dir=.claude --exclude-dir=docs | head
git add CLAUDE.md README.md
git commit -m "docs: documentar live/, la vista Oficina y los créditos de terceros"
```
Expected: el `grep` no imprime nada (los specs/planes en `docs/` quedan excluidos porque ya citan rutas de ejemplo).

---

### Task 15: Verificación manual con Playwright

**Files:** ninguno (scripts temporales en el scratchpad de la sesión).

- [ ] **Step 1: Compilar y levantar el servidor real**

```bash
cd frontend && npm run build && cd ..
AI_MONITOR_PORT=8431 python3 server.py &   # puerto distinto del 8420 por si el servicio del usuario está activo
sleep 3
curl -s localhost:8431/api/activity | python3 -m json.tool | head -30
```
Expected: JSON con `generated_at`, `agents`, `sources`; sin campos de texto de mensajes. Comprobar a mano que ningún valor contiene texto de prompts: `curl -s localhost:8431/api/activity | grep -c '"content"'` → `0`.

- [ ] **Step 2: Playwright por CLI** (instalar si falta: `npm i -D playwright` en el scratchpad, no en el repo) con un script que:
  1. abre `http://127.0.0.1:8431/oficina` a 1440×900 y a 390×844 con `colorScheme: "dark"`;
  2. escucha `console` y `pageerror` (deben ser 0 errores);
  3. comprueba `document.documentElement.scrollWidth <= window.innerWidth` (sin scroll horizontal);
  4. en escritorio, verifica que el mapa completo es visible (captura y revisarla);
  5. guarda capturas en el scratchpad y las abre con Read para revisarlas.

- [ ] **Step 3: Sesión real en estado `tool`**
  En otra terminal iniciar una sesión de Claude Code (o usar la actual) que ejecute `sleep 20`; con la oficina abierta comprobar que el personaje se sienta con animación de herramienta en ≤ 4 s, que a los ≥ 8 s aparece la burbuja de espera y que la fila muestra "ejecutando Bash" y luego "esperando · N s". Cuando termina el comando, vuelve a "pensando".

- [ ] **Step 4: Degradación** — `curl -s localhost:8431/api/activity` con `HOME` apuntando a un directorio vacío (`HOME=$(mktemp -d) AI_MONITOR_PORT=8432 python3 server.py`) debe responder `sources` con las tres fuentes `unavailable` y `agents: []`, y `/oficina` mostrar "La oficina está vacía" sin errores.

- [ ] **Step 5: Limpiar** — `kill %1` (y el segundo servidor). No se commitea nada.

---

### Task 16: Release v1.1.0

**Files:**
- Modify: `VERSION`, `frontend/package.json`, `frontend/package-lock.json`, `CHANGELOG.md`

- [ ] **Step 1: Decidir el incremento** — `## [Sin publicar]` solo contiene `Añadido` y `Corregido` aditivos: **MINOR → 1.1.0**.

- [ ] **Step 2: Versión**

```bash
echo "1.1.0" > VERSION
cd frontend && npm version 1.1.0 --no-git-tag-version && cd ..
```

- [ ] **Step 3: Changelog** — renombrar `## [Sin publicar]` a `## [1.1.0] - 2026-10-01` (usar la fecha real de ese día), abrir un `## [Sin publicar]` vacío encima y actualizar los enlaces de comparación del final (`[Sin publicar]: …/compare/v1.1.0...HEAD`, `[1.1.0]: …/compare/v1.0.0...v1.1.0`, siguiendo el formato de los existentes).

- [ ] **Step 4: Suite completa**

```bash
python3 -m unittest discover -s tests -v 2>&1 | tail -5
cd frontend && npm test 2>&1 | tail -6 && npm run lint && npm run build 2>&1 | tail -3
```
Expected: todo en verde (incluido `tests/test_version.py`, que exige `VERSION`, `package.json` y `CHANGELOG.md` sincronizados).

- [ ] **Step 5: Commit**

```bash
git add VERSION CHANGELOG.md frontend/package.json frontend/package-lock.json
git commit -m "chore(release): v1.1.0"
```

Tag, push y release en GitHub quedan **fuera del plan**: pedir permiso al usuario al terminar la rama (`superpowers:finishing-a-development-branch`).

---

## Self-Review

**Cobertura del spec**
- §1 criterios de éxito (≤ 4 s, burbuja 8 s, degradación, privacidad, stdlib): Tasks 3–8, 13, 15.
- §2.1 estados/constantes, §2.2 clases, §2.3 forma y orden: Tasks 3 y 7.
- §3.1–3.4 lectores y `SessionFacts`: Tasks 3–6. §3.5 degradación: Tasks 4–7. §3.6 server (hilo, lock, publicar solo si cambió, primer snapshot, sin env/flag): Task 8.
- §4.1 colector OpenCode: Task 1. §4.2 `toEpochMs`: Task 2.
- §5.1 `mergeOfficeAgents`, `OfficeAgent`, hook, `fetchActivity`: Tasks 10–11. §5.2 mapeo + diff: Tasks 12–13. §5.3 `fitZoom`/`ResizeObserver`/pan: Tasks 12–13. §5.4 vista: Task 13. §5.5 vendorizado, `.oxlintrc.json`, script de assets: Task 9.
- §6 testing: cada módulo lleva su test; verificación manual: Task 15. §7 docs: Tasks 1/8/9/13/14. §8 versión: Task 16.
- Licencias/`NOTICE`: Task 9.

**Decisiones del plan que el spec dejaba abiertas** (revisar):
1. `derive_state` devuelve `(estado, since)` en vez de solo el estado, para que `to_agent` no duplique la lógica.
2. `build_app` recibe `activity_fn` (inyección para tests); no es API pública de configuración.
3. El snapshot de `/api/activity` antes del primer ciclo no existe porque `build_app` calcula uno antes de servir; si `fn` fallase en ese primer cálculo se sirve un snapshot con las tres fuentes `unavailable`.
4. Un `tool_use` de Claude Code que nunca recibe `tool_result` (p. ej. el usuario interrumpe con Esc) quedaría "pendiente" hasta salir de la ventana de 30 min (`waiting` mostrado como espera). El spec no define esa regla; el plan no la inventa. Si en la verificación manual (Task 15) se ve con frecuencia, tratarlo como mejora posterior (p. ej. considerar abandonada una herramienta si hay un mensaje `user` de texto posterior).

**Placeholders:** ninguno (el único valor a verificar en ejecución es la fecha de `by_day` en el test de la Task 1 y el titular del copyright en `NOTICE`, ambos con instrucción explícita de dónde leerlos).

**Consistencia de tipos:** `SessionFacts`, `derive_state`/`to_agent`/`iso_utc`, `snapshot(now, readers)`, `OfficeAgent` (`state`, `toolKind`, `sinceMs`, `live`), `ActivitySnapshot`, `mergeOfficeAgents(activity, sources, nowMs, limit)`, `toEngineState`/`engineStateKey`, `fitZoom` y `statusText` se usan con la misma firma en todas las tareas.
