# Multi-suscripción de Claude Code

- **Fecha:** 2026-11-20
- **Versión objetivo:** 1.3.0 (MINOR) — desde 1.2.0
- **Estado:** aprobado e implementado en v1.3.0
- **Contexto:** el autor tiene dos suscripciones de Claude de 20 USD/mes. La personal (`~/.claude`) lleva tiempo activa. La de ROBC (`~/.claude-robc`) empezó el 19 de noviembre de 2026 y se usa solo desde `~/DEV/ROBC/` mediante `CLAUDE_CONFIG_DIR` (archivo `.envrc` + `direnv`). ai-monitor hoy solo lee `~/.claude/projects`, así que no ve el uso de ROBC.

## 1. Objetivo y criterios de éxito

Poder registrar varias cuentas de cualquier proveedor de uso de IA soportado por ai-monitor (hoy Claude Code, después Codex, OpenCode, Hermes, OpenRouter y los que se añadan), cada una con su costo mensual y su fecha de inicio, y que el dashboard muestre **un veredicto por cuenta** ("suscripción vs API equivalente") junto con el uso de los proyectos de esa cuenta.

**Alcance de esta versión:** el modelo de cuentas nace generalizado (con campo `provider`), pero solo se implementa el colector de Claude Code. Los demás proveedores se activan en specs posteriores, cada uno con su colector y su ubicación de datos.

Criterios, en orden de prioridad:

1. **Sin pérdida de datos:** el histórico existente (`history.db`) sigue válido y se interpreta como la cuenta por defecto de cada proveedor, sin migración destructiva.
2. **Veredicto honesto por cuenta:** cada cuenta compara contra su propia suscripción y solo desde su fecha de inicio. Nunca compara contra la suscripción de otra cuenta.
3. **Mismo proyecto en dos cuentas:** cada fila conserva de qué cuenta viene.

## 2. Principios de diseño

- **La cuenta se determina por el directorio de transcripts, no por el `cwd`.** Un proyecto puede usarse desde cualquiera de las dos cuentas; lo que identifica la cuenta es el directorio `projects/` del que se lee.
- **Rutas absolutas en la configuración.** El monitor corre también desde systemd, donde `CLAUDE_CONFIG_DIR` no existe. Nada depende del entorno de la shell.
- **Contratos existentes intactos.** `collect(projects_dir)` del colector y la forma de `combine_projects` no cambian; solo se llama al colector una vez por cuenta.
- Se mantienen las restricciones del repo: backend solo stdlib, `history.db` con `INSERT OR REPLACE` y sin poda, y ninguna ruta específica de una máquina en el código (las rutas de cuentas viven en la configuración).

## 3. Enfoques considerados

| Enfoque | Qué es | Veredicto |
|---|---|---|
| **A. Lista de cuentas en `app_settings` (elegido)** | Una clave `accounts` con JSON: `[{id, provider, label, location, default, monthly_cost, start_date}]`, editable desde el dashboard. | **Elegido.** Reutiliza el endpoint y la validación de `app_settings`, sin cambiar el esquema. |
| B. Archivo `~/.config/ai-monitor/accounts.json` | Edición a mano, como el archivo de la key de OpenRouter. | Descartado: exige endpoint propio para el dashboard y crea un segundo lugar de configuración. |
| C. Descubrimiento automático de `~/.claude*/projects` | Cada directorio encontrado es una cuenta. | Descartado: cualquier carpeta `.claude*` se volvería cuenta aunque no sea una suscripción. |

## 4. Modelo de datos

### 4.1 Cuentas configuradas (`app_settings`)

Clave `accounts`, valor TEXT con JSON (nombre genérico, no `claude_accounts`, porque la lista cubre todos los proveedores):

```json
[
  {"id": "personal", "provider": "claude_code", "label": "Personal",
   "location": "/home/<usuario>/.claude", "default": true,
   "monthly_cost": 20, "start_date": null},
  {"id": "robc", "provider": "claude_code", "label": "ROBC",
   "location": "/home/<usuario>/.claude-robc", "default": false,
   "monthly_cost": 20, "start_date": "2026-11-19"}
]
```

Campos:

- `provider`: uno de los proveedores soportados. En esta versión, solo `claude_code`. La lista de valores válidos vive en código (`SUPPORTED_PROVIDERS`) y crece con cada colector nuevo.
- `location`: ubicación de los datos del proveedor. Depende del proveedor:
  - `claude_code` y `codex`: directorio de configuración (el monitor lee `<location>/projects` o su equivalente).
  - Otros proveedores (OpenCode, Hermes): directorio de datos; se definirá en su propia spec.
  - `openrouter`: **nunca la key en la base de datos**. `location` guarda la ruta absoluta a un archivo que contiene solo la key de esa cuenta, por ejemplo `~/.config/ai-monitor/keys/robc.env`. Reglas de resolución:
    - La cuenta `default` de OpenRouter sigue la cadena actual: `$OPENROUTER_API_KEY` → `~/.config/ai-monitor/env`. Su `location` no se usa.
    - Las cuentas adicionales leen solo su archivo de `location`. No caen a la variable de entorno ni a `~/.config/ai-monitor/env`, para que una cuenta nunca use la key de otra por accidente.
    - Al guardar la cuenta se valida que el archivo exista y tenga permisos `600`. Si no los tiene, la cuenta se guarda como `sin datos` con el motivo visible (`permisos inseguros` o `archivo no encontrado`); nunca se corrige el archivo automáticamente.
    - El colector nunca imprime ni devuelve la key; en errores solo registra la cuenta y el código HTTP.
- `default`: marca la cuenta por defecto de cada proveedor. Exactamente una por proveedor. Determina el nombre de `source` (§4.2).

Reglas de validación (en `history.validate_app_settings`):

- `id`: `^[a-z0-9-]{1,32}$`, único dentro de la lista. No puede ser `all` ni `openrouter`.
- `provider`: debe estar en `SUPPORTED_PROVIDERS`; en esta versión, `claude_code`.
- `label`: texto no vacío, máximo 40 caracteres.
- `location`: ruta absoluta para proveedores basados en directorio. Si no existe, la cuenta se guarda y se marca `sin datos`; no es error de validación.
- `default`: exactamente una cuenta por proveedor debe tener `default: true`.
- `monthly_cost`: número ≥ 0 o `null`.
- `start_date`: `YYYY-MM-DD` o `null`.

### 4.2 Histórico (`daily_project`) sin cambio de esquema

El valor de `source` identifica la cuenta:

- Cuenta `default` de un proveedor → `source = <provider>` (por ejemplo `claude_code`, valor histórico sin cambio).
- Cualquier otra cuenta → `source = <provider>@<id>`, por ejemplo `claude_code@robc`.

La clave primaria `(date, source, project)` ya distingue las cuentas, así que dos cuentas con el mismo proyecto el mismo día no chocan. No hay migración: las filas existentes siguen siendo válidas.

### 4.3 Compatibilidad con los ROI actuales

Hoy existen `subscription_cost_claude` y `subscription_start_claude` en `roi_settings`. Al leer:

- Si la clave `accounts` no existe, se crea en memoria una cuenta `personal` con `provider = claude_code`, `default = true`, `location = ~/.claude`, `monthly_cost = subscription_cost_claude` y `start_date = subscription_start_claude`. No se borra la clave antigua.
- Al guardar `accounts` por primera vez, se escribe esa cuenta `personal` en la lista. Las claves antiguas quedan como fallback de lectura y no se borran (un downgrade no pierde datos).
- Codex conserva `subscription_cost_codex` y `subscription_start_codex` hasta que se implemente su spec.

## 5. Backend

### 5.1 Recolección (`main.collect_all`)

Para cada cuenta configurada cuyo `provider` tenga colector activo (en esta versión, solo `claude_code`):

1. Llamar al colector del proveedor con la `location` de la cuenta. Para Claude Code: `claude_code.collect(projects_dir=<location>/projects)`.
2. Guardar el resultado bajo el nombre de source de la cuenta (§4.2).

Una cuenta de un proveedor sin colector activo se guarda en la configuración pero no se recolecta; el dashboard la muestra como `próximamente`.

`combine_projects` recibe todas las cuentas. `by_source` lista el `source` de cada cuenta (`claude_code`, `claude_code@robc`), y el combinado por proyecto suma todas.

`live/` y `recommend/` siguen leyendo solo `~/.claude/projects` en esta versión (ver §8).

### 5.2 Briefing (`briefing.py`)

- `subscription_summary(source, ...)`: `_subscription_candidates` pasa a leer de las cuentas configuradas, no de `SUBSCRIPTION_KEYS` fijo. Cada cuenta tiene su costo, su fecha de inicio y su source.
- Filtro `source=claude_code` → todas las cuentas de Claude combinadas (compatibilidad).
- Filtro `source=claude_code@<id>` → solo esa cuenta.
- Filtro `source=all` → veredicto combinado (suma de suscripciones contra API total), sin cambio de regla.
- La regla `compare_costs` no cambia.

Respuesta de `GET /api/briefing`: se añade `accounts` (lista por cuenta con `id`, `label`, `paid`, `api_equivalent`, `winner`, `savings`, `configured`). Los campos existentes no cambian (solo se agrega; ver §6).

### 5.3 Endpoints

- `GET/POST /api/app-settings`: se agrega `accounts` a `APP_SETTINGS_WRITABLE`. Mismo contrato de respuesta.
- `GET /api/briefing`: nuevo campo `accounts` (ver §5.2). Nuevos valores aceptados en `source`: `<provider>@<id>` para cualquier cuenta configurada. Un `source` con id inexistente → HTTP 400.

## 6. Impacto de versión

- **Partes de la API pública tocadas** (`AGENTS.md`):
  - *HTTP:* `GET /api/briefing` gana el campo `accounts` y acepta `source=claude_code@<id>`; `GET/POST /api/app-settings` acepta la clave `accounts`. Son adiciones: las respuestas existentes no cambian de forma.
  - *Datos persistidos:* `history.db` no cambia de esquema. Aparecen nuevos valores de `source` (`<provider>@<id>`) y una nueva clave en `app_settings`. Las filas existentes se conservan tal cual.
  - *Configuración:* se añade un directorio nuevo `~/.config/ai-monitor/keys/` (opcional, solo si hay cuentas de OpenRouter adicionales). `~/.config/ai-monitor/env` no cambia de formato. *CLI y URLs:* sin cambios.
- **Incremento: MINOR.** Es funcionalidad nueva (cuentas múltiples, veredicto por cuenta) y es compatible hacia atrás: un usuario con una sola cuenta ve lo mismo que hoy.
- **No es MAJOR:** no se borra ni reinterpreta ningún dato. Las claves `subscription_*_claude` se siguen leyendo como fallback.
- **Changelog:** `### Añadido` bajo `[Sin publicar]`, escrito para el usuario.

## 7. Frontend

- Configuración de cuentas en la vista de ROI/ajustes existente: lista editable con `provider`, `label`, `location`, `monthly_cost`, `start_date`, y botón para añadir o quitar cuentas.
- El selector de fuente del dashboard muestra una opción por cuenta, además de "Claude Code (todas)".
- Veredicto por cuenta en el briefing, con la misma presentación que el veredicto actual.

*Decisión mía:* ubicación exacta de la UI dentro de la vista de ROI y los textos de estado vacío. Cualquier ajuste visual sigue la identidad del dashboard.

## 8. No objetivos

- **`live/` y `recommend/` no se multi-cuenta en esta versión.** Siguen mirando solo `~/.claude/projects`. Motivo: el monitor en vivo y el motor de recomendaciones tienen su propia lógica por sesión; extenderlos es un subproyecto aparte.
- No se crean las carpetas de cuentas ni se configura `CLAUDE_CONFIG_DIR`; eso ya lo hace `direnv` para ROBC.
- No se detecta automáticamente si dos cuentas son la misma persona o la misma suscripción.
- No se cambian los colectores de Codex, OpenCode, Hermes ni OpenRouter, y no se activan sus cuentas en esta versión. Cada uno requiere su propia spec para definir su `location` y su colector; Cursor además requiere investigar dónde guarda su uso local.
- No se guardan keys de API en `app_settings`: OpenRouter solo guarda la ruta al archivo de su key (§4.1).
- No se verifica automáticamente que dos keys de OpenRouter pertenezcan a cuentas distintas. Se deja como nota en el dashboard y como paso de verificación manual en la documentación.

## 9. Anti-objetivos

- No sumar la suscripción de una cuenta contra el uso de otra.
- No reinterpretar el histórico existente: lo que hoy está en `claude_code` sigue siendo la cuenta personal.
- No guardar costos de suscripción en `roi_settings` (su columna `value` es `REAL`, no sirve para JSON).

## 10. Restricciones

- Solo stdlib en el backend.
- `history.db` nunca se poda ni se borra.
- La ruta de cada cuenta vive en `app_settings`, nunca en código.
- Rutas en la configuración deben ser absolutas; el monitor no expande `~` ni `$CLAUDE_CONFIG_DIR`. *(Nota: el dashboard puede aceptar `~` y convertirla a ruta absoluta al guardar.)*

## 11. Criterios de aceptación

1. Con solo la cuenta personal configurada, el briefing y el histórico son idénticos a hoy (comparación de `GET /api/briefing` antes y después).
2. Con `robc` configurada (`~/.claude-robc`, inicio 2026-11-19), el veredicto de `claude_code@robc` usa solo el API equivalente desde el 19 de noviembre.
3. Un proyecto usado en ambas cuentas aparece en las dos filas del histórico, con sus costos separados.
4. Una cuenta con `location` inexistente aparece como `sin datos` y no rompe el briefing.
5. `history.db` no cambia de esquema (`PRAGMA table_info` igual antes y después).

## 12. Lo que queda para el constructor

- Estructura exacta de las funciones de validación y lectura de `accounts`.
- Pruebas (`tests/`): validación de cuentas, filtro por `source`, veredicto por cuenta, caso de proyecto repetido en dos cuentas.
- Orden de los commits según `AGENTS.md`.
