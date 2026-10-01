# Oficina pixel-art con actividad en vivo — diseño

Fecha: 2026-10-01
Versión objetivo: 1.1.0 (MINOR) — desde 1.0.0

## 1. Objetivo

Dar al dashboard un gancho visual: una vista `/oficina` donde cada sesión reciente de un agente
de IA es un personaje pixel-art que se sienta a trabajar, lee, ejecuta comandos, espera o
deambula según lo que está haciendo **ahora**, con una latencia de unos 2 segundos.

El cambio tiene tres partes:

1. Un endpoint de actividad en vivo (`GET /api/activity` y el evento SSE `activity`) alimentado
   por lectores nuevos en `live/` para Claude Code, OpenCode y Hermes.
2. La vista `/oficina` en el frontend, construida sobre el motor Canvas de
   [Pixel Agents](https://github.com/pablodelucca/pixel-agents) (MIT) ya validado en el spike
   (rama `spike/oficina`, commit `b205bc7`).
3. La corrección de las fechas de OpenCode en `/api/usage` y en el frontend.

Criterios de éxito:

- Mientras una sesión de Claude Code, OpenCode o Hermes ejecuta una herramienta, su personaje
  aparece sentado con la animación de esa herramienta en ≤ 4 s (2 s de intervalo + render).
- Una herramienta sin resultado durante ≥ 8 s muestra la burbuja de espera.
- Si `/api/activity` falla o una fuente no está disponible, la oficina sigue mostrando esas
  sesiones con el estado básico derivado de `/api/usage`; nunca queda vacía por ese fallo.
- Ningún argumento de herramienta, texto de mensaje, razonamiento ni título sale del proceso
  por el endpoint nuevo.
- El backend sigue siendo solo stdlib.

### Partida: lo que ya probó el spike

El spike (desechable, se usa como referencia) demostró que el motor compila con nuestro
`tsconfig` estricto y el mismo stack (React 19, Vite 8, Tailwind 4), que el chunk lazy pesa
20,7 kB gzip y los assets 400 KB, y que `/oficina` renderiza sin errores en escritorio y móvil.
Del spike se reutilizan, revisados: `frontend/src/pixel/**` (motor vendorizado, sin editor,
sonido ni transporte de VS Code), `loadAssets.ts`, `trimLayout.ts` (+ test), `OfficeStage.tsx`,
`lib/office.ts` (+ test), la ruta, el ítem del sidebar y los assets de `public/pixel/`.

### Licencias

- Código de Pixel Agents: MIT (se conserva su `LICENSE` en `frontend/src/pixel/`).
- Personajes: basados en *MetroCity Free Topdown Character Pack* de JIK-A-4, licencia **CC0**;
  el crédito no es obligatorio pero se da.
- Mobiliario, suelos y paredes: los assets abiertos que Pixel Agents incorporó al sustituir su
  tileset propietario (PR #117 de pixel-agents).

Se añade `NOTICE` en la raíz con estos tres créditos y el README lo enlaza.

## 2. Contrato de datos

### 2.1 Estados

`derive_state` es la única implementación de esta tabla (backend). `now` es la hora del
snapshot; `last_event` es el último evento de la sesión (mensaje de usuario, del modelo o
resultado de herramienta); `pending_since` es el inicio de la herramienta en curso, si la hay.

| Estado | Regla (evaluada en este orden) |
|---|---|
| *(omitida)* | `last_event` es `null`, o `now - last_event > 30 min`, o la sesión está terminada (Hermes `ended_at`, OpenCode `time_archived`) |
| `waiting` | hay herramienta pendiente y `now - pending_since >= 8 s` |
| `tool` | hay herramienta pendiente y `now - pending_since < 8 s` |
| `thinking` | sin herramienta pendiente y `now - last_event < 60 s` |
| `idle` | resto (último evento entre 60 s y 30 min) |

Un evento con fecha en el futuro hasta 60 s se trata como `now` (deriva de reloj); más allá de
60 s en el futuro, la sesión se omite. Constantes en `live/model.py`: `WAITING_AFTER_S = 8`,
`THINKING_WINDOW_S = 60`, `OFFICE_WINDOW_S = 1800`, `CLOCK_SKEW_S = 60`.

`since` es `pending_since` en `tool`/`waiting` y `last_event` en `thinking`/`idle`.

### 2.2 Clase de herramienta

`classify_tool(name) -> "edit" | "read" | "run" | "other"`, sin distinguir mayúsculas:

- `edit`: `edit`, `write`, `multiedit`, `notebookedit`, `patch`, `apply_patch`, `str_replace_editor`, `todowrite`.
- `read`: `read`, `grep`, `glob`, `ls`, `list`, `webfetch`, `websearch`, `search`, `codesearch`.
- `run`: `bash`, `shell`, `terminal`, `exec`, `execute_code`, `task`, `agent`.
- `other`: cualquier otro nombre o `null`.

### 2.3 `GET /api/activity` y evento SSE `activity`

Ambos llevan el mismo cuerpo:

```json
{
  "generated_at": "2026-10-01T05:30:00Z",
  "agents": [
    {
      "key": "claude_code:3f2a…",
      "source": "claude_code",
      "project": "/ruta/real/del/proyecto",
      "state": "tool",
      "tool": "Bash",
      "tool_kind": "run",
      "since": "2026-10-01T05:29:58Z"
    }
  ],
  "sources": {"claude_code": "ok", "opencode": "ok", "hermes": "unavailable"}
}
```

- `key` = `"<source>:<session_id>"`, el mismo formato que usa `lib/office.ts` con `/api/usage`.
- `project` es el directorio real del proyecto (la misma clave que usa `/api/usage`); si una
  fuente no lo conoce, `"unknown"`.
- `tool` y `tool_kind` son `null` salvo en `tool` y `waiting`. `tool` es el nombre tal como lo
  da la fuente; nada más de la llamada (argumentos, rutas tocadas, salida) se transmite.
- `agents` va ordenado por `since` descendente y no tiene tope en el backend.
- `sources` lista siempre las tres fuentes en vivo con `"ok"` o `"unavailable"`.
- Fechas en ISO 8601 UTC con sufijo `Z` y precisión de segundos.

## 3. Backend

### 3.1 Módulo `live/`

Paquete nuevo, hermano de `collectors/`. **No es un colector**: no participa en
`main.collect_all()`, no escribe en `history.db` ni en ningún archivo, y solo abre bases de
datos ajenas en solo lectura (`file:...?mode=ro`, `uri=True`).

```
live/
  __init__.py
  model.py        # constantes, SessionFacts, classify_tool, derive_state, to_agent  (puras)
  claude_code.py  # read(now, projects_dir=None) -> list[SessionFacts]
  opencode.py     # read(now, db_path=None)      -> list[SessionFacts]
  hermes.py       # read(now, db_path=None)      -> list[SessionFacts]
  activity.py     # snapshot(now=None, readers=None) -> dict  (cuerpo de §2.3)
```

`SessionFacts` (dataclass) es lo único que un lector produce:

```python
@dataclass(frozen=True)
class SessionFacts:
    source: str                 # "claude_code" | "opencode" | "hermes"
    session_id: str
    project: str                # directorio real o "unknown"
    last_event: float | None    # epoch en segundos
    pending_tool: str | None    # nombre de la herramienta en curso
    pending_since: float | None # epoch en segundos
    ended: bool = False
```

`model.to_agent(facts, now) -> dict | None` aplica §2.1 y §2.2 y devuelve el objeto de agente de
§2.3, o `None` si la sesión se omite. Los lectores no deciden estados.

Si una sesión tiene varias herramientas pendientes, `pending_tool`/`pending_since` son los de la
**más reciente**.

### 3.2 Lector de Claude Code (`live/claude_code.py`)

- Recorre `~/.claude/projects/*/*.jsonl` (o `projects_dir`) y descarta con `os.stat` los
  archivos cuyo `mtime` tenga más de `OFFICE_WINDOW_S`.
- De cada archivo restante lee como máximo los últimos **64 KiB** (`TAIL_BYTES = 65536`). Si
  empezó a leer a mitad del archivo, descarta la primera línea (puede venir cortada).
- Cada línea se parsea con `json.loads`; una línea inválida se salta.
- `session_id` = nombre del archivo sin `.jsonl`. `project` = el último `cwd` no vacío visto en
  la cola; si no hay, `"unknown"`.
- `last_event` = el mayor `timestamp` (ISO) de los registros de tipo `user` o `assistant`.
- Pendientes: los bloques `{"type": "tool_use", "id", "name"}` de mensajes `assistant` cuyo `id`
  no aparece como `tool_use_id` de ningún bloque `tool_result` posterior en la cola. Su
  `pending_since` es el `timestamp` del registro que contiene el `tool_use`.
- Nunca lee los campos `input` de `tool_use` ni `content` de `tool_result` más allá de comprobar
  su `type` y su id.

### 3.3 Lector de OpenCode (`live/opencode.py`)

Base: `~/.local/share/opencode/opencode.db` (o `db_path`). `time_*` está en milisegundos.

1. `SELECT id, directory, time_updated, time_archived FROM session WHERE time_updated >= ?`
   con `?` = `(now - OFFICE_WINDOW_S) * 1000`.
2. Para esas sesiones:
   `SELECT session_id, time_created, time_updated, json_extract(data,'$.type'),
   json_extract(data,'$.tool'), json_extract(data,'$.state.status') FROM part
   WHERE session_id IN (...) AND time_updated >= ?`.
3. `last_event` = el mayor `time_updated` entre la sesión y sus parts, en segundos.
   `pending_tool` = `tool` del part de tipo `tool` con estado `pending` o `running` más reciente;
   `pending_since` = su `time_created`. `ended` = `time_archived IS NOT NULL`.

Solo se extraen esos campos con `json_extract`; el resto de `data` (entradas, salidas, texto)
nunca se lee en Python.

### 3.4 Lector de Hermes (`live/hermes.py`)

Base: `~/.hermes/state.db` (o `db_path`). Fechas en epoch segundos (`REAL`).

1. `SELECT id, cwd, last_activity_at, ended_at FROM sessions WHERE last_activity_at >= ?`.
2. Para esas sesiones, los mensajes de la ventana:
   `SELECT session_id, role, tool_calls, tool_call_id, timestamp FROM messages
   WHERE session_id IN (...) AND timestamp >= ? ORDER BY timestamp`.
3. `last_event` = el mayor entre `last_activity_at` y los `timestamp` de mensajes `user`,
   `assistant` y `tool`. De `tool_calls` (JSON, mensajes `assistant`) solo se toman `id` y el
   nombre de la función (`function.name`, o `name` si viene plano); un JSON inválido se salta.
   Pendientes: ids sin fila `role='tool'` con ese `tool_call_id`; `pending_since` = `timestamp`
   del mensaje `assistant`. `ended` = `ended_at IS NOT NULL`.

Nunca se seleccionan `content`, `api_content`, `reasoning*` ni `display_*`.

### 3.5 Degradación

Ante archivo o base ausente, tabla o columna ausente, `sqlite3.Error` u `OSError`, el lector no
devuelve datos parciales engañosos. Contrato: `read(...)` lanza `live.model.SourceUnavailable` cuando la fuente no se pudo
leer en absoluto, y devuelve `[]` cuando se leyó y no hay sesiones recientes. `activity.snapshot`
captura `SourceUnavailable` y **cualquier otra excepción** de un lector, marca esa fuente
`"unavailable"` y sigue con las demás. Una fuente que simplemente no existe en la máquina
(directorio o base ausente) es `"unavailable"`. Una línea JSONL o un JSON de `tool_calls`
inválido no invalida la fuente: se salta ese registro.

### 3.6 `server.py`

- `build_app(..., activity_interval_seconds=2)` arranca un segundo hilo daemon
  `_activity_loop(broker, interval, state)` que cada `interval` segundos llama a
  `live.activity.snapshot()`, guarda el resultado en un holder protegido por `threading.Lock` y
  publica `broker.publish("activity", json)` **solo** si `agents` o `sources` cambiaron respecto
  al último publicado (`generated_at` no cuenta).
- `build_app` calcula un primer snapshot antes de arrancar el hilo, igual que hace con `usage`.
- `GET /api/activity` devuelve el último snapshot guardado (`200`, `application/json`). Nunca
  ejecuta lectores en el hilo de la petición.
- El intervalo no se expone como variable de entorno ni flag (no amplía la API pública de
  configuración).
- El hilo de `usage` (60 s) no cambia.

## 4. Corrección de fechas de OpenCode

### 4.1 Colector (`collectors/opencode.py`)

- La consulta añade `time_updated`.
- `sessions_detail[].last_ts` pasa a ser `time_updated` (si es `NULL`, `time_created`).
- Se añade `sessions_detail[].first_ts = time_created`.
- La unidad sigue siendo milisegundos (cambiarla alteraría la forma de la respuesta).
- `by_day` sigue usando `time_created` (no cambia el histórico ni `history.db`).

### 4.2 Frontend (`frontend/src/lib/sessions.ts`)

`toEpochMs(ts)`: un número `> 1e12` ya está en milisegundos y se devuelve tal cual; un número
menor se multiplica por 1000; una cadena se parsea con `Date.parse`; lo inválido da `null`. Se
exporta y `lib/office.ts` la reutiliza (sustituye a `lastActivityMs` del spike).

## 5. Frontend

### 5.1 Datos

- `lib/activity.ts`: tipos `ActivityAgent`, `ActivitySnapshot`, `ActivityState`, `ToolKind` que
  reflejan §2.3, y la función pura:

  ```ts
  mergeOfficeAgents(
    activity: ActivitySnapshot | null,
    sources: UsageSources,
    nowMs: number,
    limit = OFFICE_MAX_AGENTS,
  ): OfficeAgent[]
  ```

  - Las fuentes con `activity.sources[src] === "ok"` vienen de `activity.agents`.
  - Codex, y cualquier fuente en vivo ausente o `"unavailable"` (o `activity === null`), vienen
    de `deriveOfficeAgents` (ventana de 30 min sobre `/api/usage`): `< 3 min` → `thinking`,
    resto → `idle`, sin herramienta. OpenRouter nunca aparece.
  - Si una misma `key` viniera de ambos lados, gana la de `activity`.
  - Orden por `sinceMs` descendente; tope `OFFICE_MAX_AGENTS = 12`.

- `OfficeAgent` pasa a ser
  `{key, source, project, label, state, tool, toolKind, sinceMs, live}` (`live` = vino de
  `/api/activity`).

- `hooks/useUsageStream.ts` (dueño del único `EventSource` de `/api/stream`) añade
  `es.addEventListener("activity", ...)` y devuelve también `activity: ActivitySnapshot | null`;
  no se abre una segunda conexión.
- El snapshot inicial lo trae `fetchActivity()` en `lib/activity.ts`: `fetch("/api/activity")`
  con `AbortController` y timeout de 5 s, llamado desde el mismo hook al montar. Si falla, el
  valor queda en `null` hasta el primer evento SSE, sin romper la vista. `App.tsx` pasa
  `activity` a `OfficeView`.

### 5.2 Mapeo al motor (`pixel/OfficeStage.tsx`)

| Estado | Llamadas a `OfficeState` |
|---|---|
| `tool` | `setAgentActive(id, true)`, `setAgentTool(id, toolKind === "read" ? "Read" : "Edit")` |
| `waiting` | lo mismo que `tool` y `showWaitingBubble(id)` |
| `thinking` | `setAgentActive(id, true)`, `setAgentTool(id, "Edit")` |
| `idle` | `setAgentActive(id, false)`, `setAgentTool(id, null)` |

Las llamadas solo se hacen cuando cambia el estado o la clase del agente (comparando contra el
último valor aplicado por id), para no reiniciar animaciones en cada render.

### 5.3 Zoom adaptable

Función pura en `pixel/fitZoom.ts`:

```ts
fitZoom(containerW: number, containerH: number, cols: number, rows: number, dpr: number): number
```

Devuelve el mayor entero `z >= 2` tal que `cols*16*z <= containerW*dpr` y
`rows*16*z <= containerH*dpr`; si ni `z = 2` cabe, devuelve 2. `OfficeStage` la recalcula con un
`ResizeObserver` sobre el contenedor usando el layout ya recortado por `trimLayout`. Si el mapa
no cabe a zoom 2, el arrastre con el puntero desplaza el mapa (`panRef`); si cabe, el pan se
fija en 0.

### 5.4 Vista `/oficina` (`views/OfficeView.tsx`)

- Título "Oficina" y una línea: "Actividad en vivo de las sesiones de los últimos 30 min."
- Canvas (lazy, con `Suspense`) y debajo la lista de agentes: etiqueta del proyecto, estado
  legible y `SourceChip`. Textos de estado:
  - `tool`: `run` → "ejecutando {tool}", `edit` → "editando", `read` → "leyendo",
    `other` → "usando {tool}".
  - `waiting`: "esperando · {n} s" (segundos desde `since`, actualizado con el reloj de la vista).
  - `thinking`: "pensando". `idle`: "en pausa".
- Clic en un personaje o en una fila → detalle del proyecto (`onSelectProject`).
- Pie: "En vivo: Claude Code · OpenCode · Hermes" con cada fuente `unavailable` marcada
  "no disponible", y "Codex: estado básico".
- Estado vacío: "La oficina está vacía: ninguna sesión reciente."
- El reloj de la vista se actualiza cada segundo solo mientras haya algún agente `waiting`; si
  no, cada 15 s.

### 5.5 Código vendorizado

- `frontend/src/pixel/office/**` se mantiene lo más cercano posible al original para facilitar
  actualizaciones; los cambios propios viven fuera de esa carpeta (`loadAssets.ts`,
  `trimLayout.ts`, `fitZoom.ts`, `OfficeStage.tsx`).
- Se crea `frontend/.oxlintrc.json` con `"ignorePatterns": ["src/pixel/office/**"]` (hoy no
  hay archivo de configuración); el resto de `src/pixel/` sí se lintea.
- El script que genera `asset-index.json` y `furniture-catalog.json` se versiona en
  `frontend/scripts/gen-pixel-assets.ts` (se ejecuta a mano con `npx tsx`, no en el build) y los
  JSON generados se commitean.

## 6. Testing

### Backend (`python3 -m unittest`, sin tocar datos reales)

Todo con directorios y SQLite temporales; ningún test lee `~/.claude`, `~/.local/share` ni
`~/.hermes`.

- `tests/test_live_model.py`: `classify_tool` (los nombres de §2.2, mayúsculas, `None`);
  `derive_state`/`to_agent` en las fronteras 7,9 s/8 s, 59 s/60 s, 1800 s/1801 s, `ended`,
  evento 30 s en el futuro (cuenta como ahora) y 120 s en el futuro (omitido).
- `tests/test_live_claude_code.py`: `tool_use` pendiente y resuelto; primera línea cortada al
  leer la cola; línea corrupta en medio; archivo con `mtime` viejo ignorado; archivo de 5 MB del
  que solo se leen los últimos 64 KiB; varias pendientes → la más reciente; directorio ausente
  → `SourceUnavailable`.
- `tests/test_live_opencode.py` y `tests/test_live_hermes.py`: parts/mensajes `pending`,
  `running`, `completed`; sesión archivada o terminada; base ausente y tabla ausente →
  `SourceUnavailable`; un `content`/`data` con el marcador `SECRET-XYZ` que no aparece en
  `json.dumps` de la salida.
- `tests/test_live_activity.py`: un lector que lanza `RuntimeError` deja su fuente
  `unavailable` y las demás `ok`; orden por `since`; forma exacta de §2.3.
- `tests/test_server.py`: `GET /api/activity` responde la forma de §2.3; el bucle publica solo
  cuando cambian `agents`/`sources` (con lectores falsos inyectados).
- `tests/test_opencode.py`: `last_ts = time_updated`, respaldo a `time_created`, `first_ts`
  presente, `by_day` sin cambios.

### Frontend (Vitest)

- `lib/activity.test.ts`: `mergeOfficeAgents` con `activity` `null`, fuente `unavailable`,
  Codex desde usage, colisión de `key`, orden y tope; nunca OpenRouter.
- `lib/sessions.test.ts`: `toEpochMs` con ISO, segundos, milisegundos, `null` e inválido;
  duración de una sesión de OpenCode correcta.
- `lib/office.test.ts` y `pixel/trimLayout.test.ts`: los del spike, adaptados a `toEpochMs`.
- `pixel/fitZoom.test.ts`: escritorio (zoom > 2), móvil 390 px (2) y contenedor diminuto (2).

### Verificación manual al final de la rama

Playwright por CLI contra el server real: `/oficina` en escritorio y en 390 px oscuro, sin
errores de consola ni scroll horizontal, con el mapa completo visible en escritorio; y una
sesión real de Claude Code apareciendo en estado `tool` mientras ejecuta un comando largo.

## 7. Documentación

- `CLAUDE.md`: entrada de arquitectura para `live/` (no es colector, solo lectura, nunca
  transmite texto ni argumentos) y añadir `/api/activity` a la lista de endpoints del frontend.
- `README.md`: sección breve de la vista Oficina y enlace a `NOTICE`.
- `NOTICE`: créditos de §1.
- `CHANGELOG.md`, en `## [Sin publicar]`:
  - Añadido: la vista Oficina en `/oficina`; la actividad en vivo de Claude Code, OpenCode y
    Hermes (`GET /api/activity` y evento SSE `activity`).
  - Corregido: las fechas y duraciones de las sesiones de OpenCode (última actividad real en
    lugar del inicio, y milisegundos interpretados correctamente).

## 8. Impacto de versión

| API pública | Cambio | Tipo |
|---|---|---|
| HTTP | `GET /api/activity` nuevo; evento SSE `activity` nuevo en `/api/stream` | aditivo |
| HTTP | `/api/usage`: OpenCode `last_ts` = última actividad (antes, inicio); `first_ts` nuevo | corrección + campo aditivo |
| URLs del dashboard | `/oficina` nueva | aditivo |
| CLI, `history.db`, configuración e instalación | sin cambios | — |

Es **MINOR** según la tabla de `AGENTS.md`: añade una vista, un endpoint y un evento sin quitar
ni renombrar nada. Los clientes del evento SSE que no conozcan `activity` lo ignoran. La
corrección de `last_ts` de OpenCode cambia un valor que estaba mal, no su tipo ni su unidad, y
`first_ts` es un campo nuevo; ambos son compatibles. No hay migración de `history.db` ni de la
configuración.

Commits: `feat` para lo nuevo y `fix` para §4; ninguno con `!`. El plan termina con la tarea
"Release v1.1.0".

## 9. Fuera de alcance

- Detección en vivo de Codex (queda con estado básico; se añadiría en 1.2.0 con la misma
  interfaz `read(now) -> list[SessionFacts]`).
- Detección exacta de solicitudes de permiso (ninguna fuente las persiste; se usa la
  heurística de 8 s).
- Editor de layout, sonido, mascotas y áreas de Pixel Agents.
- Personalizar el layout o los personajes desde la configuración.
