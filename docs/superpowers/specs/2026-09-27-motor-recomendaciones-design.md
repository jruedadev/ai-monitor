# Subproyecto 3 — Motor de recomendaciones v1

- **Fecha:** 2026-09-27
- **Estado:** diseño aprobado en conversación, pendiente de revisión del spec escrito
- **Contexto:** segundo subproyecto ejecutado de la iniciativa "motor agéntico" (ver `docs/external_context/agentic_engine.md`, sin seguimiento en git, y §8 de `2026-09-27-inicio-briefing-design.md`). Parte de las `RULES` de `briefing.py` como semilla.

## 1. Objetivo y criterios de éxito

Detectar **patrones repetidos** en cómo el usuario usa sus herramientas de IA y **señales de costo**, y convertirlos en recomendaciones accionables (una skill, un plugin/MCP, un prompt mejor o un ajuste de costo) con evidencia y un borrador listo para copiar.

Criterios, en orden de prioridad:

1. **Privacidad:** el texto completo de los prompts nunca se guarda ni sale de la máquina sin redactar. Al LLM solo le llega un resumen por cluster con fragmentos redactados de ≤200 caracteres.
2. **Costo cero por defecto:** el backend por defecto (Hermes) solo acepta modelos free; cualquier costo reportado > 0 invalida la corrida.
3. **Nunca rompe el dashboard:** toda falla degrada (fuente vacía → reglas locales → respuesta `degraded`), jamás un 500.
4. **Historia persistente:** las recomendaciones nunca se borran; los estados son la memoria del usuario (lo saltado no vuelve).
5. **Stdlib only** en el backend, igual que el resto de `collectors/`, `history.py` y `server.py`.

## 2. Decisiones de alcance (acordadas)

| Tema | Decisión |
|---|---|
| Alcance | Costo (reglas del briefing) + patrones de uso (clusters de prompts) |
| Fuentes de prompts | Todas las locales: Claude Code, Codex, OpenCode, Hermes. OpenRouter no tiene prompts locales |
| Privacidad | Resumen local + fragmentos redactados |
| Frecuencia | Diario (timer) + botón "Analizar ahora" |
| "Aplicar" | Marca el estado + borrador copiable; el motor no instala ni escribe nada fuera de `history.db` |
| Backend LLM | Hermes con modelos free (por defecto), `claude -p` opcional, o ninguno |
| Arquitectura | Enfoque A: módulo stdlib `recommend/`. Se descartó LangGraph (enfoque B del spec externo) por dependencias y peso |

## 3. Arquitectura

```
recommend/
  __init__.py
  __main__.py        # CLI: python3 -m recommend run --trigger diario|manual
  prompts/
    __init__.py      # Prompt(source, project, session_id, day_utc, text); read_all(since)
    claude_code.py   # read_prompts(since, override=None) -> list[Prompt]
    codex.py
    opencode.py
    hermes.py
  redact.py          # redact(text) -> str
  cluster.py         # cluster(prompts) -> list[Cluster]
  cost.py            # señales de costo a partir de briefing.RULES
  llm.py             # backends hermes / claude / none + cadena de respaldo + validación
  heuristics.py      # clasificación local cuando no hay LLM (generator "reglas")
  store.py           # esquema, dedupe por firma, ciclo de vida, runs, settings
  engine.py          # orquesta una corrida completa con lock
```

Flujo de una corrida: `lock` → leer prompts (30 días) → redactar → candidatos léxicos (top 40) → LLM agrupa por significado y redacta (o, sin LLM, clusters solo léxicos + heurística) → umbrales y top 10 en local → señales de costo → `store.upsert` en una transacción → registrar `recommendation_runs` → publicar evento SSE (si corre dentro de `server.py`) → liberar lock.

### 3.1 Lectores de prompts (`recommend/prompts/`)

Cada lector devuelve `list[Prompt]` con `Prompt(source, project, session_id, day_utc, text)`, siguiendo la misma convención que los collectors (parámetro de override para tests, degradación graciosa).

| Fuente | Dónde vive el texto del usuario |
|---|---|
| Claude Code | `~/.claude/projects/*/*.jsonl`: entradas `type=user` cuyo `content` es `str` o bloques `text`; se ignoran los `tool_result` |
| Codex | `~/.codex/sessions/**/*.jsonl`: `response_item` de tipo `message` con `role=user` |
| OpenCode | `~/.local/share/opencode/opencode.db`: tablas `message` + `part` (`type=text`) de mensajes de usuario |
| Hermes | `~/.hermes/state.db`: tabla `messages` con `role=user` (`session_id`, `content`, `timestamp`) |

Reglas comunes:

- `project` es el directorio real del proyecto (misma resolución que el collector correspondiente).
- Ventana: últimos 30 días en UTC.
- Se descartan textos de <20 caracteres; se truncan a 4000.
- **Autoexclusión:** se descartan los prompts cuyo proyecto sea el directorio de trabajo del motor (`~/.local/share/ai-monitor/motor-recomendaciones/`), para que el motor no se analice a sí mismo.
- Archivo o tabla ausente, `sqlite3.Error`, JSON corrupto → esa fuente devuelve `[]` y el error se anota en la corrida.

### 3.2 Redacción (`recommend/redact.py`)

Se aplica a todo texto antes de clusterizar y otra vez al `draft` devuelto por el LLM.

| Patrón | Reemplazo |
|---|---|
| Secretos (claves tipo `sk-…`, `ghp_…`, `AKIA…`, JWT, `password=`/`token=`/`api_key=` con valor, cadenas de alta entropía ≥32) | `<secreto>` |
| Correos | `<correo>` |
| Rutas absolutas | `<ruta>/<último segmento>` |
| URLs | se conserva esquema + host + path; se elimina la query |
| IPs v4/v6 | `<ip>` |

### 3.3 Clustering (`recommend/cluster.py`)

- Normalización: minúsculas, sin acentos, sin puntuación, sin stopwords (es/en).
- Trigramas de palabras; similitud de Jaccard con índice invertido para no comparar todos contra todos.
- **Dos modos**, según haya LLM disponible:
  - **Candidatos para agrupación semántica** (backend `hermes`/`claude`): se unen los pares con similitud ≥0,3 (union-find); un candidato necesita **≥2 sesiones distintas**; pasan los **40** con más tokens.
  - **Solo léxico** (backend `none` o cadena LLM agotada): se unen los pares con similitud ≥0,5; un cluster es válido con **≥3 sesiones distintas** y **≥2 días distintos**; se ordenan por `sesiones × tokens` y pasan los **10 primeros**.
- La agrupación por significado la hace el LLM sobre los candidatos (§3.5). Los umbrales definitivos (≥3 sesiones, ≥2 días, top 10 por `sesiones × tokens`) se aplican siempre en local sobre el grupo final.
- Límite conocido: un prompt que aparece una sola vez sin parecido léxico con otro no llega como candidato; la agrupación semántica une grupos que ya se repiten.
- Features deterministas por cluster: `pega_datos` (bloques largos, logs, JSON o stacktraces pegados), `menciona_servicio` (lista cerrada: jira, github, gitlab, sentry, slack, notion, linear, confluence, figma, etc.) y `mismos_pasos` (secuencias de verbos imperativos que se repiten).
- `cluster_id` es estable dentro de la corrida (`c1`…`c40`); la identidad entre corridas la da la firma (§4.2). Las features de un grupo son el OR de las de sus miembros.

### 3.4 Señales de costo (`recommend/cost.py`)

Reutiliza `briefing.load()` + `briefing.RULES` por cada fuente. Se persisten como `kind = costo` las señales de `spike_day`, `project_concentration` y `subscription_missing`. `cost_incomplete` y `habitual_source_silent` son informativas y se quedan solo en el Inicio. El `draft` de costo es texto determinista generado por la regla; no pasa por el LLM.

### 3.5 Capa LLM (`recommend/llm.py`)

- **Backends:** `hermes` (por defecto), `claude` (`claude -p`, opcional) y `none` (solo heurística local).
- **Una sola llamada por corrida** con hasta 40 candidatos como JSON (patrón, sesiones, días, tokens, features, hasta 3 fragmentos redactados). El LLM hace dos cosas en esa llamada: **agrupa por significado** los candidatos que expresan la misma intención y **clasifica y redacta** una recomendación por grupo.
- **El LLM no calcula nada.** Umbrales, tokens, impacto y evidencia se calculan en local y de forma determinista sobre los grupos resultantes.
- **Contrato de salida:**
  ```json
  {"groups":[{"group_id":"g1","members":["c3","c7","c12"]}],
   "recommendations":[{"group_id":"g1","kind":"skill|plugin|prompt","pattern":"…","description":"…","draft":"…"}]}
  ```
- **Validación de `groups`:** cada `members` debe contener solo `cluster_id` enviados, sin repetir un candidato entre grupos; un grupo inválido se descarta entero. Los candidatos que no aparecen en ningún grupo válido forman grupo propio. Después se aplican en local los umbrales definitivos (≥3 sesiones, ≥2 días) y el top 10 por `sesiones × tokens`; las recomendaciones de grupos que no pasan se descartan.
- **Validación de `recommendations` (dato no confiable):** `group_id` debe existir entre los grupos válidos (si no, se descarta la entrada); un grupo que pasa los umbrales pero no tiene recomendación del LLM se completa con la heurística local; `kind` en la lista permitida; recortes `pattern` ≤120, `description` ≤400, `draft` ≤8000 caracteres; `draft` se redacta de nuevo. Nada se ejecuta ni se interpreta como HTML.
- **Cadena de modelos** en `engine_settings.llm_chain`, lista ordenada `proveedor:modelo`. Por defecto:
  1. `nous:stealth/space-bunny-alpha`
  2. `nous:upstage/solar-pro4:free`
  3. `nous:inclusionai/ling-3.0-flash-sante:free`
- **Regla de solo free** (backend `hermes`): se rechaza al guardar y al ejecutar cualquier modelo que no termine en `:free` ni empiece por `stealth/`. Si el `usage-file` de Hermes reporta `estimated_cost_usd > 0`, el intento se considera fallido.
- **Invocación Hermes:** `hermes -z <prompt> --provider <p> -m <m> --ignore-rules --safe-mode --usage-file <tmp>` con `cwd` = directorio de trabajo del motor. **Invocación Claude:** `claude -p <prompt> --output-format json` con el mismo `cwd`.
- **Respaldo:** error del proceso, timeout de 120 s, JSON inválido o fuera de esquema, o costo > 0 → siguiente modelo de la cadena. Cadena agotada → `heuristics.py` (generator `reglas`), corrida `degraded`. Las corridas siguientes enriquecen esos registros (mismo fingerprint, se actualizan `description`/`draft`/`generator`).
- **Ejecución inyectable:** el runner de procesos se pasa como parámetro para poder probarlo sin procesos reales.

#### Justificación de la cadena por defecto (benchmark del 2026-09-27)

Payload sintético de 5 clusters (2 skill, 2 plugin, 1 prompt), dos rondas, sin prompts reales del usuario:

| Modelo | JSON válido | Acierto R1 / R2 | Latencia | Borradores |
|---|---|---|---|---|
| `nous:stealth/space-bunny-alpha` | sí / sí | 5/5 · 5/5 | ~30 s | los más completos |
| `nous:upstage/solar-pro4:free` | sí / sí | 5/5 · 5/5 | 28–73 s | muy buenos |
| `nous:inclusionai/ling-3.0-flash-sante:free` | sí / sí | 5/5 · 4/5 | 9–13 s | correctos, escuetos |
| `nous:poolside/laguna-s-2.1:free` | sí / sí | 5/5 · 5/5 | 61–72 s | buenos |
| `openrouter:thinkingmachines/inkling:free` | sí / sí | 5/5 · 5/5 | 8–9 s | demasiado breves |
| `openrouter:nvidia/nemotron-3-*:free` | no | – | 34–95 s | JSON mal escapado |
| `openrouter:qwen/qwen3.8-27b:free`, `google/gemma-4-31b-it:free` | no | – | – | 429 en ambas rondas |
| `copilot:*-free-auto` | no | – | – | 400 "model not supported" |

Los modelos `stealth/` son temporales; por eso la cadena es configurable y no está fija en código.

### 3.6 Heurística local (`recommend/heuristics.py`)

Se usa cuando no hay LLM (con la agrupación solo léxica de §3.3) y para completar grupos sin recomendación del LLM. Reglas: `menciona_servicio` + `pega_datos` → `plugin`; `mismos_pasos` → `skill`; `pega_datos` sin servicio → `prompt`; resto → `prompt`. `description` y `draft` salen de plantillas en español con los datos del cluster. `generator = "reglas"`.

## 4. Persistencia (`history.db`)

`store.py` crea las tablas con `CREATE TABLE IF NOT EXISTS`. Mismas garantías que el resto de `history.db`: **nunca se borra nada**.

### 4.1 Tablas

```sql
CREATE TABLE IF NOT EXISTS recommendations (
  id           TEXT PRIMARY KEY,   -- fingerprint
  first_seen   TEXT NOT NULL,      -- ISO UTC
  last_seen    TEXT NOT NULL,
  tool         TEXT NOT NULL,      -- herramienta_ia: claude_code|codex|opencode|hermes|varias
  tokens       INTEGER NOT NULL,   -- tokens_consumidos
  pattern      TEXT NOT NULL,      -- patron_detectado
  kind         TEXT NOT NULL,      -- tipo_propuesta: skill|plugin|prompt|costo
  description  TEXT NOT NULL,      -- descripcion_propuesta
  impact       TEXT NOT NULL,      -- impacto_estimado: alto|medio|bajo
  evidence     TEXT NOT NULL,      -- JSON: sesiones, días, proyectos, fragmentos redactados (≤3, ≤200 chars)
  draft        TEXT NOT NULL,
  signature    TEXT NOT NULL,      -- JSON: conjunto de trigramas representativos (costo: regla+fuente+proyecto)
  status       TEXT NOT NULL,      -- nueva|aplicada|saltada|resuelta
  status_at    TEXT NOT NULL,
  generator    TEXT NOT NULL       -- modelo que redactó, "reglas" o "costo"
);

CREATE TABLE IF NOT EXISTS recommendation_runs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at  TEXT NOT NULL,
  finished_at TEXT,
  trigger     TEXT NOT NULL,       -- diario|manual
  backend     TEXT NOT NULL,       -- hermes|claude|none
  model       TEXT,                -- el que respondió de verdad
  attempts    INTEGER NOT NULL DEFAULT 0,
  status      TEXT NOT NULL,       -- corriendo|ok|degraded|error
  prompts     INTEGER, clusters INTEGER, created INTEGER, updated INTEGER, resolved INTEGER,
  error       TEXT,
  llm_tokens  INTEGER,
  llm_cost    REAL
);

CREATE TABLE IF NOT EXISTS engine_settings (
  key   TEXT PRIMARY KEY,          -- backend | llm_chain
  value TEXT NOT NULL              -- llm_chain como JSON
);
```

Mapeo al esquema del spec externo: `fecha`→`first_seen`/`last_seen`, `herramienta_ia`→`tool`, `tokens_consumidos`→`tokens`, `patron_detectado`→`pattern`, `tipo_propuesta`→`kind` (se añade `costo`), `descripcion_propuesta`→`description`, `impacto_estimado`→`impact`.

### 4.2 Identidad y ciclo de vida

- **Firma de un grupo:** unión de las firmas (trigramas representativos) de sus candidatos; así, si otra corrida agrupa algo distinto, sigue reconociéndose.
- **Misma recomendación:** similitud de Jaccard entre firmas ≥0,5 (para `costo`, igualdad exacta de regla+fuente+proyecto). Se actualizan `last_seen`, `tokens`, `evidence` e `impact`; el `id` se conserva.
- **Impacto** (local, determinista): proporción de `tokens` del cluster sobre el total de 30 días de su fuente — alto ≥10 %, medio ≥3 %, bajo el resto. Para `costo` lo fija la regla (`warning` → alto, `info` → medio).
- **`saltada`** queda oculta aunque el patrón reaparezca (solo se actualiza `last_seen`).
- **`aplicada`** se mantiene; si el patrón sigue apareciendo se actualiza la evidencia, sin cambiar el estado.
- **`resuelta`** la asigna solo el motor: una de `costo` en estado `nueva` cuya regla deja de dispararse.
- El texto completo de los prompts nunca se guarda.
- Todas las escrituras de una corrida van en una transacción con `busy_timeout`; si falla, rollback y la corrida queda `error` con las recomendaciones previas intactas.

## 5. Ejecución

- **Directorio de trabajo del motor:** `~/.local/share/ai-monitor/motor-recomendaciones/` (se crea si no existe).
- **Visibilidad del consumo:** los collectors de uso (`claude_code`, `hermes`) **no** excluyen ese directorio. Las corridas del motor aparecen en el dashboard como el proyecto **motor-recomendaciones**; `claude -p` hereda la estimación de `pricing.py` y entra en Gasto y ROI. `recommendation_runs` guarda backend, modelo, tokens y costo para auditoría, pero la fuente de verdad del gasto es el collector.
- **Diario:** `systemd/ai-monitor-recommend.timer` (`OnCalendar=*-*-* 07:00`, `Persistent=true`) + `ai-monitor-recommend.service.template` (`Type=oneshot`, mismo `EnvironmentFile`) que ejecuta `python3 -m recommend run --trigger diario`. `install.sh` los instala junto al resto de unidades, resolviendo rutas como hoy (`dirname "$0"`, sin rutas del autor).
- **Manual:** `POST /api/recommendations/run` lanza la corrida en un hilo de `server.py` y responde `202` con `run_id`.
- **Lock:** archivo `~/.local/share/ai-monitor/recommend.lock` con el PID. Si ya hay una corrida viva → `409` (API) o salida con código distinto de cero (CLI). Un lock cuyo PID ya no existe se recupera.
- **SSE:** al terminar una corrida lanzada desde `server.py`, se publica el evento `recommendations` en el `/api/stream` existente. Las corridas del timer las detecta el loop de `server.py` comparando el último `recommendation_runs.id`.

## 6. API

Mismo patrón de validación que `/api/roi-settings` (`Content-Type: application/json` obligatorio → `415`; payload inválido → `400`).

| Método y ruta | Respuesta |
|---|---|
| `GET /api/recommendations?estado=nueva\|aplicada\|saltada\|resuelta\|todas` | `{recommendations: [...], last_run: {...}\|null, running: bool, degraded: bool}`; por defecto `estado=nueva`. `sqlite3.Error` → respuesta vacía con `degraded: true` |
| `POST /api/recommendations/<id>/estado` `{"status": "aplicada"\|"saltada"\|"nueva"}` | `200` con la recomendación; `404` id inexistente; `400` estado inválido (incluido `resuelta`) |
| `POST /api/recommendations/run` | `202 {run_id}` o `409` |
| `GET /api/engine-settings` | `{backend, llm_chain}` |
| `POST /api/engine-settings` | valida `backend` en la lista y `llm_chain` como lista no vacía de `proveedor:modelo`; con `hermes`, aplica la regla de solo free → `400` si no cumple |

El frontend sigue sin otra vía hacia los datos que la API.

## 7. Frontend

- **Ruta** `/recomendaciones` (`ViewKey` `recommendations`), añadida a `routes.ts`, al ⌘K y al sidebar. El ítem "Recomendaciones" deja de estar deshabilitado y el badge "pronto" pasa a mostrar el número de nuevas (oculto si es 0).
- **Encabezado:** fecha de la última corrida, modelo que respondió y aviso "degradado (reglas)" si aplica; botón **Analizar ahora** con spinner mientras `running`.
- **Pestañas:** Nuevas (por defecto), Aplicadas, Saltadas, Resueltas. El filtro global `?fuente=` filtra por `tool`.
- **Tarjeta:** chip de tipo (Skill/Plugin/Prompt/Costo), badge de impacto, `SourceChip` de la herramienta, `pattern` como título, `description`, evidencia plegable (sesiones, días, tokens, proyectos, fragmentos), `draft` en bloque de código con **Copiar**, acciones **Aplicar**/**Saltar** (y **Deshacer** en Aplicadas/Saltadas). Todo el texto del LLM se renderiza como texto plano.
- **Acciones optimistas:** si el `POST` falla, se revierte y se muestra un aviso.
- **Inicio:** al final de "Atención ahora", línea "N recomendaciones nuevas →" que enlaza a la vista (no se duplican tarjetas).
- **Configuración:** sección "Motor de recomendaciones" con selector de backend (`hermes`, `claude -p`, `ninguno`) y la cadena de modelos editable como lista ordenada.
- **Estados:** sin corridas → "Aún no hay corridas: pulsa Analizar ahora"; sin patrones → "Sin patrones repetidos en los últimos 30 días"; error de API → `SectionFallback` sin afectar el resto; `degraded` → aviso.
- **Responsive:** tarjetas en una columna a 375 px, sin scroll horizontal (los bloques de código hacen scroll interno).

## 8. Errores (resumen)

| Falla | Comportamiento |
|---|---|
| Fuente de prompts ausente o corrupta | `[]` para esa fuente, error anotado en la corrida |
| LLM falla, timeout, JSON inválido, costo > 0 | siguiente modelo de la cadena |
| Cadena agotada o backend `none` | heurística local, corrida `degraded` |
| Error al escribir | rollback, corrida `error`, datos previos intactos |
| Lock huérfano | se recupera |
| `sqlite3.Error` en la API | respuesta vacía con `degraded: true` |

## 9. Pruebas y verificación

TDD con `unittest` (backend) y vitest (frontend). Todos los fixtures son sintéticos.

**Backend** (`tests/test_recommend_*.py`):

- `prompts/*`: JSONL de Claude Code y Codex, SQLite temporal de OpenCode y Hermes; filtro <20, truncado, ventana UTC, autoexclusión, degradación.
- `redact`: tabla de casos (secretos, correos, rutas, URLs con query, IPs).
- `cluster`: modo candidatos (Jaccard ≥0,3, ≥2 sesiones, top 40) y modo solo léxico (Jaccard ≥0,5, ≥3 sesiones, ≥2 días, top 10); features y OR de features por grupo.
- Agrupación semántica: `groups` válidos e inválidos (miembro inexistente, candidato repetido), candidatos huérfanos como grupo propio, umbrales aplicados tras unir, firma como unión; fixture con prompts sinónimos que solo se unen vía `groups` del runner falso.
- `llm`: runner falso; JSON válido e inválido, timeout, costo > 0, respaldo, cadena agotada → `reglas`, regla de solo free.
- `store`: dedupe por firma, `saltada` oculta, `resuelta` automática de costo, nunca se borra, rollback.
- `cost`: mapeo de señales de `briefing.RULES` a recomendaciones.
- `server`: 202/409, 404/400/415, `degraded`.
- Fin a fin: corrida con fixtures y runner falso → filas esperadas en `history.db`.

**Frontend:** mapeo API → tarjetas, filtro por pestaña y `?fuente=`, reversión optimista, formato de evidencia.

**Verificación de cierre:** E2E con Playwright por CLI contra un servidor de prueba (ver tarjetas, aplicar, saltar, deshacer, copiar, analizar ahora) y chequeo de portabilidad (sin rutas del autor). No hay pruebas automáticas contra modelos reales.

## 10. Fuera de alcance (v1)

- Instalar o escribir la skill/plugin sugerido: el usuario copia el borrador.
- Análisis de OpenRouter (no tiene prompts locales).
- Embeddings (no hay runtime local y un servicio remoto recibiría el texto de todos los prompts); la agrupación semántica la hace el LLM sobre candidatos léxicos. Candidato para v2 con un modelo local.
- Varias llamadas al LLM por corrida o agentes multi-paso.
- Medir el ahorro real tras aplicar una recomendación (candidato para una v2).
