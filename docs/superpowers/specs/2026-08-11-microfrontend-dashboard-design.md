# Microfrontend interactivo — diseño

**Fecha**: 2026-08-11
**Estado**: aprobado, pendiente de plan de implementación

## Contexto

`ai-monitor` genera hoy un archivo HTML estático (`main.py --html out.html`) que hay que recargar manualmente para ver datos frescos, aunque un timer de systemd lo regenere cada 15 minutos en segundo plano. El objetivo de este diseño es agregar un dashboard interactivo servido en vivo: un frontend React con una UI moderna (shadcn/ui + Tremor, en el espíritu de plantillas tipo "architect-ui"), consumiendo datos en tiempo real de un backend nuevo — sin modificar nada de lo que ya existe (`main.py`, `collectors/`, `dashboard/template.py` siguen funcionando exactamente igual que hoy).

Esto es una extensión, no un reemplazo: el CLI actual (`main.py --json`/`--html`/tabla) se mantiene como modo de uso rápido sin servidor.

## Decisión de alcance: dos mundos de dependencias

El backend Python mantiene la regla existente del proyecto ("cero dependencias, solo stdlib") — usa `http.server`, no Flask/FastAPI. El frontend React, en cambio, es un proyecto Node/npm normal con sus propias dependencias (React, Vite, shadcn/ui, Tremor) — esto es estándar para cualquier app frontend moderna y no compromete la promesa de "cero dependencias" del *backend*, pero sí cambia la promesa general del README: correr el dashboard interactivo requiere Node/npm instalado (el CLI y el HTML estático NO lo requieren, siguen funcionando solo con Python).

## Backend: `server.py`

- **Librería**: `http.server` de la librería estándar de Python (`http.server.ThreadingHTTPServer` + `BaseHTTPRequestHandler`), sin frameworks externos.
- **Endpoints**:
  - `GET /api/usage` → JSON `{"sources": {...}, "combined": {...}}`, misma forma que ya produce `main.py --json`. Implementado reutilizando `collect_all()` y `combine_projects()` de `main.py` sin duplicar lógica — `server.py` importa esas dos funciones.
  - `GET /api/stream` → SSE (`Content-Type: text/event-stream`). Cada conexión recibe inmediatamente el snapshot actual como primer evento (`event: usage`, `data: <json>`), y luego un evento nuevo cada vez que el snapshot cambia.
  - `GET /*` (cualquier otra ruta GET) → sirve archivos estáticos desde `frontend/dist/` (el build de producción de React), con fallback a `index.html` para que el routing del lado del cliente funcione (SPA fallback).
- **Recolección en segundo plano**: un hilo (`threading.Thread`, daemon) corre cada 60 segundos: llama a `collect_all()` + `combine_projects()`, calcula un hash del JSON resultante, y si cambió respecto al último snapshot publicado, actualiza el estado compartido (protegido con `threading.Lock`) y notifica a todas las conexiones SSE activas.
- **Gestión de conexiones SSE**: una lista protegida por lock de "queues" (una `queue.Queue` por cliente conectado); el hilo de fondo hace `put()` del nuevo snapshot en cada queue cuando hay cambios; cada handler de conexión SSE hace `get()` bloqueante sobre su queue y escribe el evento al socket. Al desconectarse el cliente (excepción de escritura), el handler remueve su queue de la lista.
- **Puerto**: configurable vía variable de entorno `AI_MONITOR_PORT` (default `8420` — puerto arbitrario elegido para no chocar con servicios comunes), sin hardcodear un puerto fijo no configurable.

## Frontend: `frontend/`

- **Build tool**: Vite + React + TypeScript.
- **UI kit**: shadcn/ui (layout, sidebar, tabla, tabs, toggle de tema) + Tremor (KPI cards, gráfico de línea de tendencia tokens/costo por día).
- **Estructura de vistas**: sidebar con las 5 secciones (Todo / Claude Code / Codex / OpenCode / OpenRouter), replicando las pestañas del dashboard HTML actual pero como rutas de verdad (`react-router`), no un `display:none` por JS.
- **Datos en vivo**: hook `useUsageStream()` que abre `new EventSource('/api/stream')`, parsea cada evento `usage` y actualiza un estado global (React Context o Zustand — decisión de implementación, no bloquea el diseño). Sin polling manual del lado del cliente: el servidor empuja cuando hay cambios.
- **Gráfico de tendencia**: usa el campo `by_day` que ya expone OpenRouter (`{fecha: {tokens, cost}}`). Los otros 3 collectors (`claude_code`, `codex`, `opencode`) no exponen `by_day` hoy — se extienden en este trabajo para agregarlo, con la misma forma, reutilizando el timestamp que cada uno ya captura por sesión (`sessions_detail[].last_ts`) para derivar el día. Esto es un cambio a los 4 collectors existentes, acotado y aditivo (agregar una clave nueva al dict de salida, no cambia las que ya existen — `main.py`'s `combine_projects()` sigue funcionando igual, solo ignora la clave nueva como ya ignora `sessions_detail`).
- **Tema**: claro/oscuro vía `prefers-color-scheme` + toggle manual persistido en `localStorage`, mismo criterio visual que el HTML estático actual.
- **Desarrollo**: `npm run dev` levanta el servidor de Vite con proxy de `/api/*` hacia `server.py` (corriendo aparte, `python3 server.py`). **Producción**: `npm run build` genera `frontend/dist/`, servido directamente por `server.py` — un solo proceso, un solo puerto, en producción.

## Systemd

- **`systemd/ai-monitor.timer`** (existente): sin cambios, sigue regenerando el HTML estático opcionalmente.
- **`systemd/ai-monitor-server.service.template`** (nuevo): `Type=simple`, `ExecStart=__PYTHON__ __REPO_DIR__/server.py`, `Restart=on-failure` — a diferencia del timer (que corre una vez y termina), este es un servicio de larga duración.
- **`install.sh`** se extiende: pregunta (con confirmación explícita, no automático) si se quiere también instalar el servicio del dashboard interactivo — y si el usuario confirma, verifica que exista `frontend/dist/` (si no, imprime instrucciones para correr `npm install && npm run build` en `frontend/` antes de continuar, no lo ejecuta por sí solo). El patrón de placeholders (`__REPO_DIR__`, `__PYTHON__`) se reutiliza igual que en la unidad existente.

## Fuera de alcance (esta fase)

- Autenticación/autorización sobre el dashboard servido (asume uso local, `localhost` — no se expone a red pública en este diseño; si el usuario quisiera exponerlo, es su responsabilidad poner un proxy/auth delante).
- Persistencia histórica más allá de lo que cada collector ya puede derivar de sus archivos fuente actuales (no se agrega una base de datos propia de `ai-monitor` para guardar históricos más largos que lo que Claude Code/Codex/OpenCode retienen).
- Empaquetado/distribución del frontend como binario único (sigue siendo "clona, `npm run build`, corre `server.py`").
