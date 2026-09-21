# Reestructura del sidebar: Herramientas / Proyectos (por cliente) / ROI

## Contexto

El sidebar actual del frontend (`frontend/src/components/Sidebar.tsx`) lista
"Todo", cada herramienta de IA (Claude Code, Codex, OpenCode, Hermes,
OpenRouter) y "ROI" como items planos, todos al mismo nivel.

El usuario quiere reagrupar esa navegación en tres secciones:

- **Herramientas**: Todo + cada tool (comportamiento actual, sin cambios).
- **Proyectos**: los proyectos agrupados por cliente (JRDV, ALMS, ...), cada
  cliente expandible para ver sus proyectos individuales.
- **ROI**: como hoy, pero con capacidad de acotar el análisis a un
  proyecto/cliente específico.

Este documento NO cubre el "motor agéntico" descrito en
`docs/external_context/agentic_engine.md` (LangGraph, recomendaciones
automáticas de Skills/Plugins, Streamlit). Eso es una visión a futuro,
explícitamente fuera de alcance de este diseño — que se limita a mejorar la
navegación y el filtrado del dashboard existente.

## Alcance

Dentro:
- Derivar el "cliente" de un proyecto a partir de la convención de carpetas
  `~/DEV/<CLIENTE>/<proyecto>` ya usada en la máquina del usuario.
- Reestructurar el sidebar en tres grupos con la sección "Proyectos"
  expandible por cliente.
- Filtrar por cliente las vistas ya existentes (KpiCards, ProjectTable,
  SessionDetail, TrendChart) cuando se selecciona un cliente en "Proyectos".
- Añadir un selector de cliente/proyecto opcional dentro de `RoiView` para
  acotar el cálculo de ROI.

Fuera:
- Cualquier pieza del motor agéntico (LangGraph, captura de logs para
  recomendaciones automáticas, etc.).
- Mapeo manual de cliente por proyecto (persistencia en DB) — se usa
  únicamente la convención de carpetas; si el path no matchea, el proyecto
  cae en un grupo "Otros".
- Suscripciones de ROI parametrizadas por cliente — la suscripción sigue
  siendo global por herramienta (ya existente en `roi_settings`); el filtro
  de cliente solo acota el costo API real y las horas de sesión mostradas.

## Diseño

### 1. Derivación de cliente (frontend, sin cambios de backend)

Nuevo archivo `frontend/src/lib/clients.ts`:

```ts
export function clientOf(projectPath: string): string {
  const segments = projectPath.split("/");
  const idx = segments.findIndex((s) => s.toUpperCase() === "DEV");
  if (idx === -1 || idx + 1 >= segments.length) return "Otros";
  return segments[idx + 1];
}

export function groupProjectsByClient(
  paths: string[],
): Record<string, string[]> {
  const groups: Record<string, string[]> = {};
  for (const path of paths) {
    const client = clientOf(path);
    (groups[client] ??= []).push(path);
  }
  return groups;
}
```

Los paths de proyecto ya viajan completos como claves de `combined`/
`sources[tool]` (contrato existente de los colectores: "keyed by the real
project directory"), así que esta derivación es puramente de presentación,
sin tocar `collectors/*.py`, `history.py` ni `server.py`.

### 2. Sidebar reestructurado

`Sidebar.tsx` pasa de una lista plana `SECTIONS` a tres grupos:

- **Herramientas**: igual que hoy (`all` + cada `SOURCE_META` tool).
- **Proyectos**: recibe `clients: string[]` (derivados en `App.tsx` desde
  `combined` vía `groupProjectsByClient`), renderiza cada cliente como item
  expandible (estado local `expandedClient: string | null`); al expandir
  muestra los proyectos de ese cliente (nombre corto = basename del path).
  Clic en el nombre del cliente selecciona ese cliente como filtro activo;
  clic en un proyecto abre `ProjectDetailSheet` (ya existente, sin cambios).
- **ROI**: como hoy.

Nuevas props de `Sidebar`: `clients: string[]`, `activeClient: string | null`,
`onSelectClient: (client: string | null) => void`, además de
`onSelectProject: (path: string) => void` para el clic directo en un proyecto
dentro del grupo expandido.

### 3. Modelo de navegación: estado ortogonal

`App.tsx` mantiene `section: SectionKey` (`all` | tool | `roi`, sin cambios
de tipo) y añade `clientFilter: string | null`:

- Clic en herramienta (grupo "Herramientas") → `setSection(tool)`,
  `setClientFilter(null)`.
- Clic en cliente (grupo "Proyectos") → `setSection("all")`,
  `setClientFilter(client)`.
- Clic en "ROI" → `setSection("roi")` (clientFilter se ignora en esa vista,
  que maneja su propio selector interno, ver §5).

`projectsForSection()` aplica el filtro de cliente después del filtro de
sección existente, cuando `clientFilter !== null`:

```ts
const filtered = clientFilter
  ? Object.fromEntries(
      Object.entries(result).filter(([path]) => clientOf(path) === clientFilter),
    )
  : result;
```

### 4. Propagación del filtro a componentes existentes

- `KpiCards`, `ProjectTable`: reciben el `projectsForSection()` ya filtrado
  — sin cambios en esos componentes.
- `SessionDetail`: ya recibe `sources`/`section`; se le añade prop opcional
  `clientFilter?: string | null`, y en `collectSessions` (`lib/sessions.ts`)
  se filtra `rows` por `clientOf(row.project) === clientFilter` cuando está
  definido.
- `TrendChart`: recibe nuevo prop opcional `clientFilter?: string | null`.
  Como `daily_project` (vía `/api/history`) ya incluye el campo `project`
  (path completo), se filtra `rows` por `clientOf(row.project) ===
  clientFilter` antes de agregar por fecha — sin cambios en
  `history.py`/`server.py`.

### 5. Extensión de RoiView

`RoiView` gana un `<select>` opcional (default "Todos los proyectos") con
las opciones: "Todos", cada cliente, y cada proyecto individual (agrupados
visualmente). Al elegir un valor:

- Se recalcula `apiCost` sumando solo los proyectos de `sources[tool]` que
  matchean el filtro (`path === proyecto` o `clientOf(path) === cliente`).
- `sessionDurationSeconds` se filtra igual sobre `sessions_detail`.
- La suscripción (`subscription_cost_claude`/`subscription_cost_codex`)
  permanece global — no se toca `roi_settings` ni `history.py`.

## Testing

- `frontend/src/lib/clients.ts`: no hay test runner configurado en este
  frontend (ya documentado en el proyecto) — se verifica manualmente con
  Playwright vía CLI (según `CLAUDE.md` global del usuario), igual que se
  hizo para la vista ROI: build (`npm run build`), lint, y verificación
  visual headless de: sidebar con los 3 grupos, expandir un cliente,
  filtrar por cliente en "Todo", filtrar ROI por proyecto.
- Sin cambios de backend → sin nuevos tests de `unittest`; se corre la
  suite existente (`python3 -m unittest discover -s tests`) solo para
  confirmar que no hay regresión.

## Riesgos / notas

- La convención `~/DEV/<CLIENTE>/...` es específica del entorno del
  usuario, pero la lógica de detección (`buscar segmento "DEV"`) es
  genérica y no hardcodea ningún path absoluto — cumple la restricción de
  portabilidad de `CLAUDE.md` del repo. Proyectos que no sigan la
  convención caen en "Otros" sin romper la UI.
- Si en el futuro se requiere mapeo manual de cliente (proyectos fuera de
  la convención), se puede añadir después siguiendo el mismo patrón de
  `roi_settings` — explícitamente fuera de alcance ahora (YAGNI).
