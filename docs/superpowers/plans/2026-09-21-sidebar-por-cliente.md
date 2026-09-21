# Sidebar por cliente (Herramientas / Proyectos / ROI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reestructurar el sidebar del frontend en tres grupos (Herramientas, Proyectos por cliente, ROI) y propagar el filtro de cliente a las vistas de KPIs, tabla de proyectos, detalle de sesiones, tendencia y ROI.

**Architecture:** Cambio puramente frontend. Un nuevo módulo puro `lib/clients.ts` deriva el cliente de cada path de proyecto (ya presente como clave de `combined`/`sources`) a partir de la convención `~/DEV/<CLIENTE>/...`. `Sidebar.tsx` se reestructura en tres grupos visuales. `App.tsx` añade un estado ortogonal `clientFilter` que se aplica sobre el resultado existente de `projectsForSection()`, y se propaga a `TrendChart` y `SessionDetail`. `RoiView` gana un selector interno independiente. No hay cambios de backend (`collectors/`, `history.py`, `server.py`).

**Tech Stack:** React + TypeScript + Vite (frontend/), sin test runner configurado — verificación vía `npm run build`, `npm run lint` y Playwright headless (siguiendo el patrón ya usado en la implementación de ROI de este mismo proyecto).

**Spec:** `docs/superpowers/specs/2026-09-21-sidebar-por-cliente-design.md`

## Global Constraints

- Ningún archivo del repo puede contener un path absoluto específico de esta máquina (`/home/jruedadev`, `~/DEV/JRDV/...`) — la detección de cliente en `lib/clients.ts` busca el segmento literal `"DEV"` (case-insensitive) dentro de paths que ya llegan como datos en tiempo de ejecución, nunca hardcodea un path completo.
- Sin backend nuevo: `collectors/*.py`, `history.py`, `server.py` no se tocan en este plan.
- Verificación de frontend: no hay Jest/Vitest configurado en este repo. Cada tarea se verifica con `npm run build` (tsc + vite build) y `npm run lint` (oxlint); la verificación funcional end-to-end se hace una sola vez al final con Playwright vía CLI (nunca con `mcp__claude-in-chrome__*`, por instrucción global del usuario).
- La suscripción de ROI (`roi_settings`) sigue siendo global por herramienta — el selector de cliente/proyecto en `RoiView` solo acota el costo API real y las horas de sesión mostradas, nunca la suscripción.

---

### Task 1: Utilidad de derivación de cliente

**Files:**
- Create: `frontend/src/lib/clients.ts`

**Interfaces:**
- Consumes: nada (módulo puro, sin dependencias del proyecto).
- Produces: `clientOf(projectPath: string): string` y `groupProjectsByClient(paths: string[]): Record<string, string[]>` — usados por `Sidebar.tsx`, `App.tsx`, `SessionDetail.tsx` y `RoiView.tsx` en tareas siguientes.

- [ ] **Step 1: Crear el módulo**

```ts
// frontend/src/lib/clients.ts

/**
 * Deriva el "cliente" de un path de proyecto según la convención
 * ~/DEV/<CLIENTE>/<proyecto>. Si el path no contiene un segmento "DEV",
 * el proyecto se agrupa bajo "Otros" en vez de romper la UI.
 */
export function clientOf(projectPath: string): string {
  const segments = projectPath.split("/");
  const idx = segments.findIndex((s) => s.toUpperCase() === "DEV");
  if (idx === -1 || idx + 1 >= segments.length) return "Otros";
  return segments[idx + 1];
}

export function groupProjectsByClient(paths: string[]): Record<string, string[]> {
  const groups: Record<string, string[]> = {};
  for (const path of paths) {
    const client = clientOf(path);
    (groups[client] ??= []).push(path);
  }
  return groups;
}
```

- [ ] **Step 2: Verificar manualmente con un script desechable**

No hay test runner en este frontend. Verifica la lógica con un script Node
desechable (se borra al final del paso, no se commitea):

```bash
cd frontend && node -e '
const { clientOf, groupProjectsByClient } = require("./src/lib/clients.ts");
' 2>&1 || true
```

Como `clients.ts` es TypeScript sin compilar, en su lugar verifica vía
`tsc` (compilación exitosa = sin errores de tipos) y una inspección visual
de los dos casos límite ya contemplados en el código: path con `DEV` (ej.
`/home/user/DEV/JRDV/ai-monitor` → `"JRDV"`) y path sin `DEV` (ej.
`/home/user/projects/foo` → `"Otros"`). Confirma leyendo el archivo que
ambos casos están cubiertos por el `findIndex`/fallback.

Run: `cd frontend && npx tsc --noEmit src/lib/clients.ts`
Expected: sin errores (puede imprimir warnings de módulos no resueltos si
el archivo se compila aislado sin el resto del proyecto; en ese caso usa
`npm run build` completo en el Step 3 como verificación real).

- [ ] **Step 3: Compilación completa**

Run: `cd frontend && npm run build`
Expected: build exitoso, sin errores de TypeScript relacionados a
`clients.ts` (el archivo aún no se importa desde ningún componente, así
que esto solo confirma que no rompe la compilación existente).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/clients.ts
git commit -m "feat: utilidad de derivación de cliente por convención de carpetas DEV/<CLIENTE>"
```

---

### Task 2: Sidebar reestructurado en tres grupos

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx` (reescritura completa)

**Interfaces:**
- Consumes: `SOURCE_META` de `@/lib/sources` (sin cambios, ya existente).
- Produces: `SectionKey` (tipo, sin cambios de valores posibles: `"all"|"claude_code"|"codex"|"opencode"|"hermes"|"openrouter"|"roi"`), y el componente `Sidebar` con nuevas props: `projectsByClient: Record<string, string[]>`, `activeClient: string | null`, `onSelectClient: (client: string | null) => void`, `onSelectProject: (path: string) => void` — usados por `App.tsx` en la Task 3.

- [ ] **Step 1: Reescribir el componente**

```tsx
// frontend/src/components/Sidebar.tsx
import { useState } from "react";
import { LayoutGrid, Activity, Scale, ChevronRight, FolderKanban } from "lucide-react";
import { SOURCE_META } from "@/lib/sources";

const TOOL_SECTIONS = [
  { key: "all", label: "Todo", icon: LayoutGrid, color: undefined },
  { key: "claude_code", ...SOURCE_META.claude_code },
  { key: "codex", ...SOURCE_META.codex },
  { key: "opencode", ...SOURCE_META.opencode },
  { key: "hermes", ...SOURCE_META.hermes },
  { key: "openrouter", ...SOURCE_META.openrouter },
] as const;

const ROI_ITEM = { key: "roi", label: "ROI", icon: Scale, color: "var(--viz-aqua)" } as const;

export type SectionKey = (typeof TOOL_SECTIONS)[number]["key"] | typeof ROI_ITEM.key;

interface SidebarProps {
  active: SectionKey;
  onSelect: (key: SectionKey) => void;
  projectsByClient: Record<string, string[]>;
  activeClient: string | null;
  onSelectClient: (client: string | null) => void;
  onSelectProject: (path: string) => void;
}

function basename(path: string): string {
  return path.split("/").filter(Boolean).pop() ?? path;
}

const navButtonClass = (isActive: boolean) =>
  `group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
    isActive
      ? "bg-accent text-accent-foreground font-medium"
      : "text-muted-foreground hover:bg-muted hover:text-foreground"
  }`;

export function Sidebar({
  active, onSelect, projectsByClient, activeClient, onSelectClient, onSelectProject,
}: SidebarProps) {
  const [expandedClient, setExpandedClient] = useState<string | null>(null);
  const clients = Object.keys(projectsByClient).sort();

  const handleSelectClient = (client: string) => {
    setExpandedClient((prev) => (prev === client ? null : client));
    onSelectClient(client);
  };

  return (
    <nav className="w-56 shrink-0 border-r bg-sidebar flex flex-col overflow-y-auto">
      <div className="flex items-center gap-2 px-5 h-16 border-b">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Activity className="h-4 w-4" />
        </div>
        <span className="font-semibold tracking-tight">ai-monitor</span>
      </div>
      <div className="flex-1 p-3 space-y-4">
        <div className="space-y-1">
          <p className="px-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Herramientas
          </p>
          {TOOL_SECTIONS.map((s) => {
            const Icon = s.icon;
            const isActive = active === s.key && !activeClient;
            return (
              <button
                key={s.key}
                onClick={() => { onSelect(s.key); onSelectClient(null); }}
                className={navButtonClass(isActive)}
              >
                <Icon className="h-4 w-4 shrink-0" style={{ color: isActive ? s.color : undefined }} />
                {s.label}
              </button>
            );
          })}
        </div>

        <div className="space-y-1">
          <p className="px-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Proyectos
          </p>
          {clients.length === 0 ? (
            <p className="px-3 text-xs text-muted-foreground">Sin proyectos</p>
          ) : (
            clients.map((client) => {
              const isActive = activeClient === client;
              const isExpanded = expandedClient === client;
              return (
                <div key={client}>
                  <button
                    onClick={() => handleSelectClient(client)}
                    className={navButtonClass(isActive) + " gap-2"}
                  >
                    <ChevronRight
                      className={`h-3.5 w-3.5 shrink-0 transition-transform ${isExpanded ? "rotate-90" : ""}`}
                    />
                    <FolderKanban className="h-4 w-4 shrink-0" />
                    <span className="truncate">{client}</span>
                  </button>
                  {isExpanded && (
                    <div className="ml-6 border-l pl-2 space-y-0.5 py-1">
                      {projectsByClient[client].map((path) => (
                        <button
                          key={path}
                          onClick={() => onSelectProject(path)}
                          className="block w-full truncate rounded-md px-2 py-1.5 text-left text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
                          title={path}
                        >
                          {basename(path)}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        <div className="space-y-1">
          <p className="px-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            ROI
          </p>
          <button
            onClick={() => { onSelect(ROI_ITEM.key); onSelectClient(null); }}
            className={navButtonClass(active === ROI_ITEM.key)}
          >
            <ROI_ITEM.icon
              className="h-4 w-4 shrink-0"
              style={{ color: active === ROI_ITEM.key ? ROI_ITEM.color : undefined }}
            />
            {ROI_ITEM.label}
          </button>
        </div>
      </div>
    </nav>
  );
}
```

- [ ] **Step 2: Compilar (fallará porque `App.tsx` aún no pasa las nuevas props)**

Run: `cd frontend && npm run build`
Expected: FAIL — error de TypeScript en `App.tsx` porque `<Sidebar active={section} onSelect={setSection} />` ya no satisface las props requeridas (`projectsByClient`, `activeClient`, `onSelectClient`, `onSelectProject` faltantes). Esto confirma que el nuevo contrato de props está siendo exigido por el compilador antes de tocar `App.tsx` en la Task 3.

- [ ] **Step 3: Commit (junto con el ajuste mínimo de App.tsx para que compile)**

Este paso se difiere al final de la Task 3 — no hacer commit todavía con
el build roto. Continúa directamente a la Task 3.

---

### Task 3: Wiring en App.tsx (clientFilter + props del Sidebar)

**Files:**
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `clientOf`, `groupProjectsByClient` de `@/lib/clients` (Task 1); `Sidebar` con las props de la Task 2.
- Produces: `clientFilter` propagado como prop a `TrendChart` (Task 4) y `SessionDetail` (Task 5).

- [ ] **Step 1: Editar imports y estado**

En `frontend/src/App.tsx`, añade el import y el nuevo estado junto a los
existentes:

```tsx
import { clientOf, groupProjectsByClient } from "@/lib/clients";
```

```tsx
const [clientFilter, setClientFilter] = useState<string | null>(null);
```

- [ ] **Step 2: Calcular `projectsByClient` y el handler de selección de cliente**

Justo después de `const { sources, combined, connected } = useUsageStream();`:

```tsx
const projectsByClient = groupProjectsByClient(Object.keys(combined ?? {}));

const handleSelectClient = (client: string | null) => {
  setClientFilter(client);
  if (client) setSection("all");
};
```

- [ ] **Step 3: Aplicar el filtro de cliente en `projectsForSection`**

Reemplaza el cuerpo de `projectsForSection` para aplicar `clientFilter` al
final, excepto cuando `section === "roi"` (esa vista maneja su propio
filtro en la Task 6):

```tsx
const projectsForSection = (): Record<string, ProjectUsage> => {
  if (!sources || !combined) return {};

  let result: Record<string, ProjectUsage>;
  if (section === "all" || section === "roi") {
    result = combined;
  } else if (section === "openrouter") {
    const or = sources.openrouter;
    if (!or || or.unavailable || !or.models) return {};
    result = Object.fromEntries(
      Object.entries(or.models).map(([model, v]) => [
        model,
        { total_tokens: v.tokens, cost: v.cost, messages: v.requests, session_count: v.requests, by_source: ["openrouter"] },
      ]),
    );
  } else {
    result = Object.fromEntries(
      Object.entries(sources[section]).map(([name, v]) => [
        name,
        { total_tokens: v.total_tokens, cost: v.cost, messages: v.messages, session_count: v.session_count, by_source: [section] },
      ]),
    );
  }

  if (clientFilter && section !== "roi") {
    result = Object.fromEntries(
      Object.entries(result).filter(([path]) => clientOf(path) === clientFilter),
    );
  }

  return result;
};
```

- [ ] **Step 4: Ajustar `activeLabel` para reflejar el cliente activo**

```tsx
const activeLabel = clientFilter
  ? `Proyectos — ${clientFilter}`
  : section === "all"
    ? "Vista general"
    : { claude_code: "Claude Code", codex: "Codex", opencode: "OpenCode", hermes: "Hermes", openrouter: "OpenRouter", roi: "ROI" }[section];
```

- [ ] **Step 5: Pasar las nuevas props a `Sidebar`, `TrendChart` y `SessionDetail`**

```tsx
<Sidebar
  active={section}
  onSelect={setSection}
  projectsByClient={projectsByClient}
  activeClient={clientFilter}
  onSelectClient={handleSelectClient}
  onSelectProject={setSelectedProject}
/>
```

```tsx
<TrendChart section={section} clientFilter={clientFilter} onSelectDate={setSelectedDate} />
```

```tsx
<SessionDetail
  sources={sources}
  section={section}
  clientFilter={clientFilter}
  selectedDate={selectedDate}
  onSelectDate={setSelectedDate}
  onSelectProject={setSelectedProject}
/>
```

(`TrendChart` y `SessionDetail` no aceptan aún `clientFilter` — se añade
en las Tasks 4 y 5. El build fallará hasta completarlas; es esperado,
continúa.)

- [ ] **Step 6: Compilar (seguirá fallando hasta las Tasks 4-5)**

Run: `cd frontend && npm run build`
Expected: FAIL — `Property 'clientFilter' does not exist on type
'IntrinsicAttributes & TrendChartProps'` (y lo mismo para
`SessionDetailProps`). Confirma que el error es exactamente ese, no un
typo en otra parte.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/Sidebar.tsx
git commit -m "feat: sidebar en tres grupos (Herramientas/Proyectos/ROI) con filtro de cliente en App.tsx"
```

(Se commitea con el build roto de forma intencional aquí porque las Tasks
4 y 5 son pequeñas y siguen inmediatamente en la misma sesión de trabajo;
si prefieres mantener cada commit verde, combina las Tasks 3-5 en un solo
commit al final del Step de la Task 5 en su lugar.)

---

### Task 4: `TrendChart` con filtro de cliente

**Files:**
- Modify: `frontend/src/components/TrendChart.tsx`

**Interfaces:**
- Consumes: `clientOf` de `@/lib/clients` (Task 1).
- Produces: `TrendChart` acepta ahora `clientFilter?: string | null`.

- [ ] **Step 1: Añadir el import y la prop**

```tsx
import { clientOf } from "@/lib/clients";
```

Actualiza la interfaz de props (busca `interface TrendChartProps` o el
tipo equivalente cerca de la línea 20-25 del archivo) añadiendo:

```tsx
clientFilter?: string | null;
```

Y desestructura `clientFilter` junto a `section` en la firma del
componente.

- [ ] **Step 2: Filtrar las filas por cliente antes de agregar por fecha**

El archivo ya tiene, tras el guard `if (section === "roi") return null;`
(agregado en una sesión previa), dos ramas que llenan `byDate` a partir de
`rows`/`modelRows`. Aplica el filtro de cliente sobre `rows` (la rama
`else`, que es la que aplica a proyectos con `section` distinto de
`"openrouter"`) antes del `for`:

```tsx
} else {
  const filteredRows = clientFilter
    ? rows.filter((row) => clientOf(row.project) === clientFilter)
    : rows;
  for (const row of filteredRows) {
    if (section !== "all" && row.source !== section) continue;
    const date = row.date.slice(0, 10);
    byDate[date] = (byDate[date] ?? 0) + row.tokens;
  }
}
```

(La rama `openrouter` no se toca — OpenRouter agrega por modelo, no por
proyecto, y no participa del filtro de cliente por diseño, tal como ya
excluye "Todo" en `combine_projects()`.)

- [ ] **Step 3: Compilar**

Run: `cd frontend && npm run build`
Expected: el error de `clientFilter` en `TrendChartProps` desaparece; si
`SessionDetail` (Task 5) aún no está lista, el build seguirá fallando solo
por esa parte — confirma que el mensaje de error restante menciona
únicamente `SessionDetailProps`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/TrendChart.tsx
git commit -m "feat: TrendChart filtra por cliente activo"
```

---

### Task 5: `SessionDetail` con filtro de cliente

**Files:**
- Modify: `frontend/src/components/SessionDetail.tsx`

**Interfaces:**
- Consumes: `clientOf` de `@/lib/clients` (Task 1); `collectSessions` de `@/lib/sessions` (sin cambios de firma).
- Produces: `SessionDetail` acepta ahora `clientFilter?: string | null`.

- [ ] **Step 1: Añadir el import y la prop**

```tsx
import { clientOf } from "@/lib/clients";
```

```tsx
interface SessionDetailProps {
  sources: UsageSnapshot["sources"] | null | undefined;
  section: SectionKey;
  clientFilter?: string | null;
  selectedDate: string | null;
  onSelectDate: (date: string | null) => void;
  onSelectProject?: (project: string) => void;
}
```

- [ ] **Step 2: Filtrar `allSessions` por cliente**

```tsx
export function SessionDetail({
  sources, section, clientFilter, selectedDate, onSelectDate, onSelectProject,
}: SessionDetailProps) {
  if (section === "openrouter") {
    return null;
  }

  const rawSessions = collectSessions(sources, section);
  const allSessions = clientFilter
    ? rawSessions.filter((s) => clientOf(s.project) === clientFilter)
    : rawSessions;
  // ... resto del componente sin cambios (usa `allSessions` como ya lo hace)
```

- [ ] **Step 3: Compilar**

Run: `cd frontend && npm run build`
Expected: PASS — build completo sin errores de TypeScript.

- [ ] **Step 4: Lint**

Run: `cd frontend && npm run lint`
Expected: sin errores nuevos (puede haber warnings preexistentes no
relacionados; confirma que ninguno referencia los archivos tocados en
este plan).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/SessionDetail.tsx
git commit -m "feat: SessionDetail filtra por cliente activo"
```

---

### Task 6: Selector de cliente/proyecto en `RoiView`

**Files:**
- Modify: `frontend/src/components/RoiView.tsx`

**Interfaces:**
- Consumes: `clientOf`, `groupProjectsByClient` de `@/lib/clients` (Task 1); `collectSessions`, `sessionDurationSeconds` de `@/lib/sessions` (sin cambios de firma).
- Produces: ninguna interfaz nueva consumida por otros componentes — `RoiView` sigue recibiendo solo `{ sources }` desde `App.tsx`.

- [ ] **Step 1: Añadir estado de filtro y opciones del selector**

En `frontend/src/components/RoiView.tsx`, añade el import:

```tsx
import { clientOf, groupProjectsByClient } from "@/lib/clients";
```

Dentro de `export function RoiView({ sources }: RoiViewProps)`, junto a los
`useState` existentes:

```tsx
const [scopeFilter, setScopeFilter] = useState<string>("");
```

Justo antes del `return`, calcula las opciones del selector a partir de
los proyectos de las dos fuentes que cubre ROI:

```tsx
const allProjectPaths = Array.from(
  new Set(ROI_SOURCES.flatMap((source) => Object.keys(sources?.[source] ?? {}))),
);
const projectsByClient = groupProjectsByClient(allProjectPaths);
const clientOptions = Object.keys(projectsByClient).sort();
```

- [ ] **Step 2: Render del selector en el panel de parametrización**

Dentro del `<div className="rounded-xl border bg-card p-5 space-y-4">`
(el mismo bloque que ya contiene el título "Parametrización" y el grid de
3 `Field`), añade el selector justo debajo del `<h2>`:

```tsx
<h2 className="text-sm font-medium">Parametrización</h2>
<label className="block space-y-1.5">
  <span className="text-xs text-muted-foreground">Acotar a</span>
  <select
    className="w-full max-w-xs rounded-lg border bg-background px-3 py-2 text-sm"
    value={scopeFilter}
    onChange={(e) => setScopeFilter(e.target.value)}
  >
    <option value="">Todos los proyectos</option>
    {clientOptions.map((client) => (
      <optgroup key={client} label={client}>
        <option value={`client:${client}`}>Todo {client}</option>
        {projectsByClient[client].map((path) => (
          <option key={path} value={`project:${path}`}>
            {path.split("/").filter(Boolean).pop() ?? path}
          </option>
        ))}
      </optgroup>
    ))}
  </select>
</label>
```

- [ ] **Step 3: Definir el predicado de filtro y pasarlo a `SourceRoiCard`**

Justo debajo de la definición de `clientOptions`, añade un predicado que
`SourceRoiCard` usará para filtrar proyectos:

```tsx
const matchesScope = (path: string): boolean => {
  if (!scopeFilter) return true;
  if (scopeFilter.startsWith("client:")) return clientOf(path) === scopeFilter.slice(7);
  if (scopeFilter.startsWith("project:")) return path === scopeFilter.slice(8);
  return true;
};
```

Pasa `matchesScope` como nueva prop a cada `SourceRoiCard`:

```tsx
{ROI_SOURCES.map((source) => (
  <SourceRoiCard key={source} source={source} sources={sources} settings={settings} matchesScope={matchesScope} />
))}
```

- [ ] **Step 4: Aplicar el filtro dentro de `SourceRoiCard`**

Actualiza la firma y el cuerpo de `SourceRoiCard` para filtrar tanto el
cálculo de `apiCost` como las sesiones usadas en `totalHours`:

```tsx
function SourceRoiCard({
  source,
  sources,
  settings,
  matchesScope,
}: {
  source: RoiSource;
  sources: UsageSnapshot["sources"] | null;
  settings: RoiSettings;
  matchesScope: (path: string) => boolean;
}) {
  const meta = SOURCE_META[source];
  const projects = sources?.[source] ?? {};
  const apiCost = Object.entries(projects)
    .filter(([path]) => matchesScope(path))
    .reduce((sum, [, p]) => sum + p.cost, 0);
  const subscriptionCost = settings[SUBSCRIPTION_KEY[source]];

  const sessions = collectSessions(sources, source).filter((s) => matchesScope(s.project));
  const totalHours = sessions.reduce((sum, s) => sum + sessionDurationSeconds(s), 0) / 3600;
  const hourlyRate = settings.hourly_rate;
  const valueGenerated = hourlyRate !== null ? totalHours * hourlyRate : null;

  // ... resto del componente sin cambios
```

- [ ] **Step 5: Compilar**

Run: `cd frontend && npm run build`
Expected: PASS — build completo sin errores de TypeScript.

- [ ] **Step 6: Lint**

Run: `cd frontend && npm run lint`
Expected: sin errores nuevos.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/RoiView.tsx
git commit -m "feat: selector de cliente/proyecto en RoiView para acotar el cálculo de ROI"
```

---

### Task 7: Verificación visual end-to-end con Playwright y suite de backend

**Files:**
- Create (temporal, se borra al final del paso): `frontend/pw_sidebar_check.cjs`

**Interfaces:**
- Consumes: todo lo construido en las Tasks 1-6.
- Produces: nada (tarea de verificación, no de código de producción).

- [ ] **Step 1: Confirmar que `playwright` sigue disponible**

Run: `cd frontend && test -d node_modules/playwright && echo OK`
Expected: `OK` (ya se usó en la sesión anterior para verificar la vista de
ROI; si no está, instalar con `npm install -D playwright` antes de
continuar, por instrucción global del usuario de usar Playwright en vez
de `mcp__claude-in-chrome__*`).

- [ ] **Step 2: Levantar el backend de desarrollo**

Run (en background):
```bash
cd /home/jruedadev/DEV/JRDV/ai-monitor && python3 server.py --port 8421 &
```
Expected: servidor escuchando en `http://localhost:8421/`. Usa un puerto
distinto al del servicio systemd de producción (`ai-monitor-server.service`,
que ya corre en su puerto habitual) para no interferir con él.

- [ ] **Step 3: Script de verificación Playwright**

Crea `frontend/pw_sidebar_check.cjs`:

```js
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
  page.on('pageerror', err => errors.push(err.message));

  await page.goto('http://localhost:8421/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: '/tmp/claude-1000/sidebar_grouped.png' });

  // Expandir el primer cliente en "Proyectos"
  const clientBtn = page.locator('nav button', { hasText: /^(?!Todo|ROI).+/ }).first();
  await clientBtn.waitFor({ timeout: 5000 });
  await clientBtn.click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: '/tmp/claude-1000/sidebar_client_expanded.png' });

  // Verificar que la vista se filtró (el header cambia a "Proyectos — <cliente>")
  const header = await page.locator('header h1').textContent();
  if (!header || !header.startsWith('Proyectos')) {
    errors.push(`Header no refleja el filtro de cliente: "${header}"`);
  }

  // Volver a "Todo"
  await page.locator('nav button', { hasText: 'Todo' }).click();
  await page.waitForTimeout(500);

  // Ir a ROI y usar el selector de acotar
  await page.locator('nav button', { hasText: 'ROI' }).click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: '/tmp/claude-1000/roi_scope_selector.png' });

  console.log(errors.length === 0 ? 'OK: sin errores de consola' : `ERRORES: ${JSON.stringify(errors)}`);
  await browser.close();
})();
```

- [ ] **Step 4: Ejecutar el script**

Run: `cd frontend && node pw_sidebar_check.cjs`
Expected: imprime `OK: sin errores de consola`. Si imprime `ERRORES: ...`,
lee el mensaje, corrige el componente correspondiente (Sidebar, App o
RoiView) y repite este step antes de continuar.

- [ ] **Step 5: Revisar las capturas**

Lee `/tmp/claude-1000/sidebar_grouped.png`,
`/tmp/claude-1000/sidebar_client_expanded.png` y
`/tmp/claude-1000/roi_scope_selector.png` con la herramienta Read para
confirmar visualmente: (a) los tres grupos del sidebar (Herramientas,
Proyectos, ROI) están presentes, (b) al expandir un cliente se ven sus
proyectos anidados, (c) el selector "Acotar a" aparece en la vista ROI.

- [ ] **Step 6: Limpieza**

```bash
rm frontend/pw_sidebar_check.cjs
kill %1  # detiene el server.py de verificación levantado en el Step 2
```

- [ ] **Step 7: Suite de backend (confirmar cero regresión)**

Run: `cd /home/jruedadev/DEV/JRDV/ai-monitor && python3 -m unittest discover -s tests`
Expected: mismo resultado que antes de este plan (60 tests, solo los 2
fallos preexistentes y no relacionados de `test_openrouter.py` por la
variable de entorno `OPENROUTER_API_KEY` real de esta máquina — ningún
fallo nuevo).

- [ ] **Step 8: Commit final (si Step 4 requirió fixes) y recompilación de producción**

Si el Step 4 no requirió ningún cambio de código, no hay nada que
commitear en este step (el script temporal ya se borró y nunca se
commiteó). Si sí requirió fixes, commitea esos cambios puntuales con un
mensaje descriptivo del fix antes de continuar.

Luego, recompila el bundle de producción y reinicia el servicio systemd
para que sirva la nueva UI (mismo procedimiento ya usado tras el commit
anterior de este proyecto):

```bash
cd /home/jruedadev/DEV/JRDV/ai-monitor/frontend && npm run build
systemctl --user restart ai-monitor-server.service
```

Expected: build exitoso y `systemctl --user status ai-monitor-server.service`
muestra `active (running)` con un PID nuevo.
