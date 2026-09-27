# Subproyecto 1 — Nueva estructura + Inicio tipo briefing

- **Fecha:** 2026-09-27
- **Estado:** diseño aprobado en conversación, pendiente de revisión del spec escrito
- **Contexto:** primer subproyecto de la iniciativa "motor agéntico" (ver `docs/external_context/agentic_engine.md`, sin seguimiento en git) para llevar ai-monitor de dashboard de analítica básica a producto pulido, open source y pieza de portafolio.

## 1. Objetivo y criterios de éxito

Reorganizar el dashboard alrededor de **preguntas del usuario** (¿cómo voy?, ¿qué pasó?, ¿cuánto me cuesta?, ¿en qué proyectos?) en vez de alrededor de **fuentes de datos**, y crear un Inicio que responda en segundos.

Criterios, en orden de prioridad:

1. **Briefing en 5 segundos:** al abrir el dashboard se responde "¿cómo voy este mes y qué debo mirar?" sin navegar.
2. **Acabado de portafolio:** identidad visual alineada con jrueda.dev, lista para mostrarse públicamente.
3. **Onboarding mínimo:** un tercero que clona el repo entiende la estructura y encuentra dónde configurar su plan. El asistente de setup completo es del subproyecto 2.

## 2. Principios de diseño

- **Honestidad:** cada número muestra su origen (ventana, cobertura, fuente). Nunca se muestra "$0" ni "+∞ %" donde lo correcto es "sin datos".
- **Línea base propia:** ninguna señal usa un umbral absoluto contra una fuente sin línea base propia. Las reglas se miden contra el patrón de uso de esa fuente. El perfil real del autor (Claude Code principal; Codex y Hermes esporádicos) no debe generar ruido permanente.
- **Las reglas del briefing son la semilla del motor de recomendaciones** (subproyecto 3): se implementan como funciones puras `rule(ctx) -> Signal | None` en Python.
- Se mantienen las restricciones del repo: backend solo stdlib, OpenRouter nunca sumado a "Todas", `history.db` con `INSERT OR REPLACE` sin poda y ninguna ruta específica de una máquina.

## 3. Backend: `briefing.py` + `GET /api/briefing`

### 3.1 Ubicación

`briefing.py` en la raíz, junto a `history.py`. No es un collector: lee `history.db` (`daily_project`, `daily_model`, `roi_settings`) y nunca toca a los proveedores. `server.py` solo agrega la ruta. Lógica en funciones puras sobre filas, y el acceso a SQLite en una capa delgada.

### 3.2 Contrato

`GET /api/briefing?source=<all|claude_code|codex|opencode|hermes|openrouter>&compare=<YYYY-MM>`

- `source` por defecto es `all`, que excluye OpenRouter. `openrouter` usa `daily_model` (fila `__all__`).
- `compare` por defecto es el mes anterior al actual. Un valor inválido o sin datos → HTTP 400 con un mensaje legible.
- "Hoy" es la fecha local del servidor (`date.today()`), comparable con las fechas `YYYY-MM-DD` de `history.db`.

```json
{
  "source": "all",
  "window":  {"month": "2026-09", "from": "2026-09-01", "to": "2026-09-27"},
  "compare": {"month": "2026-08", "from": "2026-08-01", "to": "2026-08-27",
              "coverage": "full", "since": null},
  "eligible_months": [
    {"month": "2026-08", "coverage": "full",    "since": null},
    {"month": "2026-07", "coverage": "partial", "since": "2026-07-18"}
  ],
  "kpis": {
    "cost":        {"current": 657.10, "previous": 799.54, "delta_pct": -17.8},
    "tokens":      {"current": 953620952, "previous": 1982466892, "delta_pct": -51.9},
    "active_days": {"current": 22, "previous": 17},
    "cost_incomplete": false
  },
  "subscription": {
    "configured": true, "paid": 20.0, "api_equivalent": 657.10,
    "winner": "subscription", "savings": 637.10
  },
  "top_projects": [
    {"project": "<ruta>", "client": "<cliente>", "cost": 276.38, "share": 0.42}
  ],
  "attention": [
    {"id": "spike_day", "severity": "warning",
     "title": "Hoy llevas $242,58 — 7,9× tu promedio diario",
     "evidence": ["2026-09-27: $242,58", "Promedio de días activos del mes: $30,78"],
     "link": "/actividad?dia=2026-09-27"}
  ]
}
```

Los textos de `title` y `evidence` los arma el backend en español, porque la interfaz es solo en español por ahora (ver Fuera de alcance). El frontend no reinterpreta las señales.

### 3.3 Reglas de cálculo

- **Ventana equivalente:** del día 1 al día de hoy del mes actual, contra el mismo tramo del mes comparado. Si el mes comparado es más corto, el fin se recorta a su último día (31 → 28 en febrero).
- **Cobertura:** el inicio de cada fuente es `MIN(date)` de sus filas (para `all`, el mínimo entre las fuentes incluidas). Un mes es `full` si ese inicio es anterior o igual al día 1, y `partial` con `since` si no. Un día sin filas posterior al inicio es un 0 real. Los meses anteriores al inicio no son elegibles. Los `partial` sí lo son, pero van marcados.
- **Delta:** `delta_pct = (actual − anterior) / anterior × 100`. Si `anterior == 0`, el delta es `null`.
- **Costos nulos:** `cost IS NULL` suma 0 y activa `cost_incomplete = true`.
- **Suscripción frente a API:**
  - Solo aplica a las fuentes con suscripción posible (`claude_code` → `subscription_cost_claude`, `codex` → `subscription_cost_codex`).
  - `api_equivalent` es el costo del mes actual de esas fuentes, contado desde `subscription_start_*` si esa fecha cae dentro del mes.
  - `winner` y `savings` usan la misma regla de redondeo a centavos que `compareCosts` en `frontend/src/lib/roi.ts`, incluido el empate cuando la diferencia redondea a 0.
  - Sin ningún plan configurado para las fuentes del filtro, se devuelve `configured: false` y el resto de los campos en `null`.
- **Top de proyectos:** los 3 de mayor costo en la ventana actual. `client` sale con la misma regla que `clientOf` en `frontend/src/lib/clients.ts` (el segmento que sigue a `DEV`, sin distinguir mayúsculas, o "Otros" si no hay), portada a Python; un test fija los mismos casos en ambos lados.

### 3.4 Señales de "Atención ahora"

Máximo 3, ordenadas por severidad (`warning` > `info`) y luego por el orden de la lista siguiente. Cada una incluye `evidence` verificable y un `link` a su vista.

| id | Se dispara cuando | Severidad |
|---|---|---|
| `spike_day` | Algún día de la ventana actual supera 2,5× el promedio de costo de los días activos del mes, calculado dentro del filtro de fuente actual (por fuente, o sobre el total en "Todas"). Se exigen al menos 5 días activos en el mes para que el promedio signifique algo | `warning` |
| `project_concentration` | Un proyecto concentra más del 50 % del costo del mes. No aplica con `source=openrouter` | `info` |
| `cost_incomplete` | Hay filas con `cost IS NULL` en la ventana | `info` |
| `subscription_missing` | Una fuente con suscripción posible tuvo actividad relevante en el mes (al menos 3 días activos) y no tiene su plan configurado | `info` |
| `habitual_source_silent` | Una fuente **habitual** (actividad en al menos el 40 % de los días de los 30 anteriores al silencio) lleva sin datos más de max(3 días, 3× su intervalo típico entre días activos) | `warning` |

Las fuentes esporádicas (hoy Codex y Hermes) nunca disparan `habitual_source_silent`. Si su uso se vuelve habitual, la regla las empieza a vigilar sola.

### 3.5 Degradación

- Si `history.db` no existe o está vacía, la respuesta es válida y vacía: KPIs en 0 con delta `null`, `eligible_months: []`, `attention: []` y `subscription.configured` según corresponda. Nunca un 500.
- Un `sqlite3.Error` se registra y devuelve la misma respuesta vacía, con `"degraded": true`.

### 3.6 CLI

`python3 main.py --briefing` imprime el mismo resumen en la terminal: KPIs, comparación y señales.

## 4. Frontend

### 4.1 Rutas

La fuente pasa de ser una ruta a ser un parámetro global `?fuente=<slug>`, que los chips de la barra superior mantienen al navegar.

| Ruta | Contenido | Origen |
|---|---|---|
| `/` Inicio | Briefing (variante A) y selector "Comparar con" (`?comparar=YYYY-MM`) | Nuevo |
| `/actividad` | Tendencia con clic por día + `SessionDetail`, con `?dia=` | Parte baja de la vista "Todo" actual |
| `/gasto`, `/gasto/roi` | Pestañas Gasto (KPIs + tabla de proyectos + tendencia) y ROI (`RoiView` sin cambios de lógica) | Vistas por fuente + `/roi` |
| `/proyectos`, `/proyectos/<cliente>` | Proyectos agrupados por cliente, con `?proyecto=` para abrir `ProjectDetailSheet` | Grupo "Proyectos" del sidebar |
| `/configuracion` | Formulario de suscripción y valor de la hora (movido desde ROI) + estado por fuente (con datos / sin datos / OpenRouter sin clave o con error) | Nuevo, mínimo |

**Redirecciones legadas** (`replace`, conservando la query):

- `/claude-code`, `/codex`, `/opencode`, `/hermes`, `/openrouter` → `/gasto?fuente=<slug>`
- `/roi` → `/gasto/roi`
- `/cliente/<X>` → `/proyectos/<X>`

Una ruta desconocida lleva a `/`.

**OpenRouter con el filtro global:** en `/gasto` se muestra la tabla por modelo, como hoy. En `/` el briefing usa `source=openrouter`. En "Todas" nunca se suma.

### 4.2 Shell

- **Sidebar:** Inicio, Actividad, Gasto y ROI, Proyectos, Recomendaciones (deshabilitada, con la etiqueta "pronto") y Configuración al pie. El logotipo "ai-monitor" usa el gradiente de marca. La navegación activa se marca con cyan (borde interno de 2px más superficie `soft`).
- **Barra superior:** prompt en mono (`ai-monitor:~/<vista>$`; el prefijo `<nombre>@` llega con el nombre configurable del subproyecto 2), chips de fuente, botón ⌘K, indicador "En vivo" y el toggle de tema.
- **⌘K:** con `Command` de shadcn (`cmdk`). Busca vistas, clientes, proyectos y sesiones (por título) sobre el snapshot en memoria, sin backend.

### 4.3 Inicio (variante A · briefing vertical)

De arriba abajo:

1. **Encabezado:** mes actual, ventana ("1–27 sep · comparado con 1–27 ago") y selector "Comparar con" con los `eligible_months`. Los meses `partial` aparecen con la etiqueta "cobertura parcial desde …".
2. **Tres KPIs:**
   - Gasto equivalente API, con su delta.
   - Suscripción vs API ("Pagas $X · equivale a $Y · ahorras $Z").
   - Días activos, con tokens y su delta como dato secundario.
3. **Atención ahora** a ancho completo: cada señal lleva punto de severidad + icono, título, evidencia y enlace a su vista. El color nunca es el único indicador.
4. **Dos columnas:** top 3 de proyectos (barras neutras con el porcentaje) y mini tendencia del gasto diario del mes (color de identidad de la fuente filtrada, o tinta neutra en "Todas").

El Inicio vuelve a pedir `/api/briefing` cuando llega un snapshot SSE nuevo (mismo patrón que `useHistory`), sin skeleton si ya hay datos en caché.

### 4.4 Identidad visual (jrueda.dev)

Fuente de verdad: `jrdv-website/DESIGN.md`. Decisión: **cyan como único acento de interfaz y esmeralda confinado al gradiente del logotipo**.

| Token | Oscuro | Claro |
|---|---|---|
| `--background` | `#09090b` | `#ffffff` |
| `--card` / `--popover` | `#101013` | `#ffffff` |
| `--muted` / `--secondary` | `#242428` | `#f1f5f9` |
| `--foreground` | `#f8fafc` | `#020817` |
| `--muted-foreground` | `#94a3b8` | `#64748b` |
| `--border` / `--input` | `#303036` | `#e2e8f0` |
| `--primary` / `--ring` | `#00ddff` | `#00b1cc` |
| `--primary-foreground` | `#09090b` | `#f8fafc` |
| `--shadow-glow` | `0 0 40px rgb(0 221 255 / .2)` | `0 0 40px rgb(0 177 204 / .15)` |
| `--gradient-brand` | `linear-gradient(135deg, #00ddff, #36d399)` | `linear-gradient(135deg, #00b1cc, #29bc86)` |

- Los tokens `--sidebar-*` se derivan de los anteriores.
- `--radius: 0.75rem`.
- Tipografía: Inter (400–800) para la interfaz y JetBrains Mono para rutas, IDs de sesión y el prompt. Ambas vía `@fontsource`, sin CDN, para que funcionen offline.
- Las variables `--viz-*` (identidad de fuentes) **no cambian**. Motivo medido: el esmeralda de marca contra el aqua de OpenCode da ΔE 10,5, por debajo del mínimo de 15, así que el esmeralda nunca aparece junto a series de datos.
- Antes de cerrar, el validador de dataviz se ejecuta con cyan + `--viz-*` en ambos temas; cualquier FAIL se corrige antes del merge.
- Las tarjetas interactivas usan `hover:shadow-glow` y un borde cyan, siguiendo el patrón `card-active` de jrueda.dev.

### 4.5 Responsive (375px)

- Los chips de fuente pasan a un `select` compacto.
- ⌘K sigue disponible como botón de lupa.
- El sidebar sigue siendo un Sheet.
- Los KPIs quedan en una columna y el bloque de dos columnas se apila.
- Sin scroll horizontal.

### 4.6 Estados

| Situación | Comportamiento |
|---|---|
| Cargando | Skeleton con la altura final (sin salto de layout) |
| Error de `/api/briefing` | Aviso `role="alert"` con el mensaje real y el botón "Reintentar"; el resto de la app sigue funcionando por SSE |
| Sin historial | Estado vacío: "Aún no hay historial. ai-monitor registra un resumen diario cada vez que recolecta; vuelve después de tu primera sesión", con enlace a Configuración |
| Suscripción no configurada | "Configura tu plan para comparar", con enlace a `/configuracion` |
| Sin señales | "Nada requiere tu atención ahora" (tono neutro) |
| Comparación parcial | Delta visible y la etiqueta "cobertura parcial desde …" junto a él |
| Delta `null` | "—" con el tooltip "sin datos para comparar" |
| `degraded: true` | Aviso discreto "Historial no disponible temporalmente" |

## 5. Dependencias nuevas (solo frontend)

- `cmdk`, vía el componente `Command` de shadcn.
- `@fontsource/inter`, `@fontsource/jetbrains-mono`.

El backend no agrega dependencias.

## 6. Pruebas y verificación

- **Backend, TDD con `unittest`:** `tests/test_briefing.py` sobre una base temporal con filas sintéticas:
  - Ventana equivalente, incluido el recorte en febrero.
  - Cobertura `full` y `partial` y meses elegibles.
  - Delta `null`, costos nulos y empate a centavos.
  - Exclusión de OpenRouter en `all` y la rama `openrouter`.
  - Cada regla disparada y no disparada, incluida la línea base por fuente y las fuentes esporádicas que no disparan `habitual_source_silent`.
  - Base inexistente, vacía y con `sqlite3.Error`.
  - Paridad de `client` con `lib/clients.ts`.
  - `tests/test_server.py`: la ruta, `compare` inválido → 400 y la respuesta vacía sin 500.
- **Frontend, TDD con vitest:**
  - `lib/routes.ts`: rutas nuevas, redirecciones legadas y `?fuente=`/`?comparar=`.
  - `lib/briefing.ts`: formateo de deltas, cobertura y etiquetas.
- **E2E con Playwright** (script temporal, como hasta ahora):
  - Las 5 rutas y las redirecciones legadas.
  - ⌘K y el filtro de fuente persistente.
  - Tema claro y oscuro, y 375px sin scroll horizontal ni errores de consola.
- **Paleta:** el validador de dataviz en ambos temas.
- **Portabilidad:** `grep` de rutas específicas de la máquina sobre los archivos nuevos.

## 7. Fuera de alcance (v1)

- El asistente de setup completo (detección de herramientas, nombre y foto, presets de valor de la hora): subproyecto 2.
- La tabla rica de "runs" (duración, modelo, herramientas, estado): subproyecto 2. `/actividad` reutiliza `SessionDetail`.
- Modelo por sesión y recomendaciones de modelo: requieren ampliar los collectors (subproyecto 3).
- El motor de recomendaciones ("el Sueño"), su persistencia con el esquema del spec externo y `claude -p`: subproyecto 3.
- El asistente conversacional: subproyecto 4.
- La vista de estado de collectors que distinga "no instalado" de "falla de lectura": requiere que los collectors reporten su estado.
- i18n (hoy solo español).

## 8. Hoja de ruta de la iniciativa

Orden de ejecución acordado (los números son los de cada subproyecto):

1. **Subproyecto 1 (este spec):** estructura + Inicio.
2. **Subproyecto 3, motor de recomendaciones v1:** reglas deterministas persistidas en `history.db` con el esquema del spec externo, tarjetas con evidencia y "aplicar/saltar", y una capa opcional `claude -p` que usa la suscripción.
3. **Subproyecto 2:** actividad rica + asistente de setup.
4. **Subproyecto 4:** asistente conversacional.
