# Multi-suscripción Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir varias cuentas por proveedor (en esta versión, Claude Code), cada una con costo mensual y fecha de inicio, y mostrar un veredicto "suscripción vs API" por cuenta en el briefing.

**Architecture:** Un módulo puro `accounts.py` define el modelo (validación, cuenta por defecto, nombre de `source`). `history.py` persiste la lista en `app_settings` (clave `accounts`) y el histórico usa `<provider>@<id>` como `source`, sin cambiar el esquema. `main.collect_all` recolecta una vez por cuenta; `briefing.py` calcula el veredicto por cuenta; el frontend edita las cuentas en la vista de ROI.

**Tech Stack:** Python 3 stdlib (backend, `unittest`); React + TypeScript + Vite + Vitest (frontend).

**Spec:** `docs/superpowers/specs/2026-11-20-multi-suscripcion-design.md`

**Versión:** 1.3.0 (MINOR), desde 1.2.0

## Global Constraints

- Backend solo stdlib (`sqlite3`, `json`, `re`, `os`, `unittest`).
- `history.db` no cambia de esquema y nunca se poda ni se borra filas.
- Ninguna ruta específica de una máquina en el código; las rutas de cuentas viven en `app_settings`.
- La cuenta personal de Claude Code (`~/.claude`) siempre existe y siempre se recolecta, aunque no esté configurada en `accounts`.
- `source` de la cuenta por defecto de un proveedor = `<provider>` (sin sufijo). Cualquier otra = `<provider>@<id>`.
- Valores de `provider` válidos en esta versión: solo `claude_code`. OpenRouter, Codex, OpenCode y Hermes no se activan (spec §8).
- Key de API nunca en `history.db` ni en `app_settings`. La validación de archivos de key de OpenRouter queda para su spec (ver nota en Task 1).
- Mensajes de commit sin `Co-Authored-By: Claude` ni `Claude-Session:`. Commits `feat:` (MINOR), sin `!`.
- Cada tarea que cambia algo visible añade su línea a `## [Sin publicar]` de `CHANGELOG.md` en su propio commit.

## Review Focus

1. **Directorio de una cuenta inexistente o ilegible** → el briefing responde 200 con la cuenta como `sin datos`; nunca 500. (Task 3, Task 4)
2. **Mismo proyecto usado en dos cuentas el mismo día** → dos filas separadas en `daily_project`, ninguna sobrescribe a la otra. (Task 2)
3. **Instalación previa sin clave `accounts`** (solo `subscription_cost_claude`) → aparece la cuenta personal con ese costo y fecha, y el histórico no cambia. (Task 1, Task 2)
4. **Dos cuentas por defecto del mismo proveedor, id repetido o sin cuenta por defecto** → HTTP 400 con mensaje legible; nada se guarda. (Task 1, Task 5)
5. **Snapshot con cuentas adicionales** → `record_snapshot` escribe sus filas; no se descartan en silencio. (Task 2)

## Task 1: Modelo de cuentas (`accounts.py`)

**Files:**
- Create: `accounts.py`
- Test: `tests/test_accounts.py`

**Interfaces:**
- Consumes: nada.
- Produces (todas en `accounts.py`):
  - `SUPPORTED_PROVIDERS: tuple[str, ...] = ("claude_code",)`
  - `class AccountsError(ValueError)`
  - `normalize_accounts(payload) -> list[dict]`: valida y devuelve la lista normalizada. Lanza `AccountsError`.
  - `legacy_accounts(settings: dict) -> list[dict]`: si la clave `accounts` no existe, devuelve la cuenta personal de Claude Code construida desde `subscription_cost_claude` y `subscription_start_claude`; `location` = ruta absoluta de `~/.claude` (expandida). Si no existe ninguna clave, devuelve igualmente la cuenta personal con `monthly_cost=None`.
  - `source_name(account: dict) -> str`
  - `claude_projects_dir(account: dict) -> str`: `os.path.join(account["location"], "projects")`.
  - `provider_of_source(source: str) -> str`: `"claude_code@robc"` → `"claude_code"`.
  - `is_claude_source(source: str) -> bool`

Cada cuenta tiene las claves: `id`, `provider`, `label`, `location`, `default`, `monthly_cost`, `start_date`.

- [ ] **Step 1: Escribir los tests que fallan**

Casos mínimos en `tests/test_accounts.py`:
- `test_normalize_accepts_two_claude_accounts`: `[personal default=True, robc default=False]` se devuelve igual, con `monthly_cost` y `start_date` intactos.
- `test_rejects_two_defaults_for_same_provider`: lanza `AccountsError`.
- `test_rejects_missing_default`: ninguna cuenta con `default=True` → `AccountsError`.
- `test_rejects_duplicate_id`: dos cuentas con `id="robc"` → `AccountsError`.
- `test_rejects_reserved_id`: `id="all"` y `id="openrouter"` → `AccountsError`.
- `test_rejects_unknown_provider`: `provider="cursor"` → `AccountsError`.
- `test_rejects_relative_location`: `location="data/claude"` → `AccountsError`.
- `test_rejects_bad_start_date`: `start_date="19/11/2026"` → `AccountsError`.
- `test_rejects_negative_cost`: `monthly_cost=-1` → `AccountsError`.
- `test_legacy_seeds_personal_from_roi_keys`: `{"subscription_cost_claude": 20, "subscription_start_claude": "2026-01-05"}` → una cuenta `id="personal"`, `default=True`, `monthly_cost=20`, `start_date="2026-01-05"`.
- `test_legacy_without_keys_still_returns_personal`: `{}` → una cuenta personal con `monthly_cost=None`.
- `test_source_name_default_vs_extra`: personal default → `"claude_code"`; robc → `"claude_code@robc"`.
- `test_provider_of_source_and_is_claude_source`: `"claude_code@robc"` y `"claude_code"` son Claude; `"codex"` no.

- [ ] **Step 2: Ejecutar y ver que fallan**

Run: `python3 -m unittest tests.test_accounts -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'accounts'`.

- [ ] **Step 3: Implementar `accounts.py`**

Reglas de validación según spec §4.1: `id` con `^[a-z0-9-]{1,32}$`, único; `provider` en `SUPPORTED_PROVIDERS`; `label` no vacío y ≤40 caracteres; `location` ruta absoluta (`os.path.isabs`); exactamente una cuenta `default=True` por proveedor; `monthly_cost` número ≥0 o `None` (rechazar `bool`); `start_date` `^\d{4}-\d{2}-\d{2}$` o `None`. Un `location` inexistente **no** es error: la cuenta se guarda.

Nota: el spec §4.1 describe también la validación de archivos de key para `openrouter`. Como `openrouter` no es un proveedor soportado en esta versión, esa validación no se implementa aquí; queda para la spec de OpenRouter.

- [ ] **Step 4: Ejecutar y ver que pasan**

Run: `python3 -m unittest tests.test_accounts -v`
Expected: PASS, 13 tests.

- [ ] **Step 5: Commit**

```bash
git add accounts.py tests/test_accounts.py CHANGELOG.md
git commit -m "feat(accounts): modelo de cuentas por proveedor con validación"
```

## Task 2: Persistencia y source por cuenta (`history.py`)

**Files:**
- Modify: `history.py` (`APP_SETTINGS_WRITABLE`, `validate_app_settings`, `get_app_settings`, `save_app_settings`, `record_snapshot`)
- Test: `tests/test_history.py`, `tests/test_app_settings.py`

**Interfaces:**
- Consumes: `accounts.normalize_accounts`, `accounts.legacy_accounts`, `accounts.source_name`, `accounts.is_claude_source` (Task 1).
- Produces:
  - `APP_SETTINGS_WRITABLE = ("client_roots", "accounts")`
  - `get_app_settings(db_path=None)` devuelve además `"accounts": list[dict]`. Si la clave no existe o está corrupta, devuelve `accounts.legacy_accounts(roi)` donde `roi = get_roi_settings(db_path)`.
  - `validate_app_settings(payload)` acepta `accounts` (opcional) y lo valida con `normalize_accounts`. Si falta `client_roots` sigue siendo error, como hoy.
  - `save_app_settings(settings, db_path=None)` escribe `accounts` si está presente.
  - `record_snapshot(sources, db_path=None)` recorre **todas** las claves de `sources` cuyo nombre es un proveedor o empieza por `<provider>@` para `claude_code`. Las claves fijas actuales (`codex`, `opencode`, `hermes`) se mantienen.

- [ ] **Step 1: Escribir los tests que fallan**

En `tests/test_history.py`:
- `test_record_snapshot_keeps_same_project_in_two_accounts`: `sources = {"claude_code": {"/p": {...by_day {"2026-11-20": {"tokens": 10, "cost": 1.0}}}}, "claude_code@robc": {"/p": {...by_day {"2026-11-20": {"tokens": 7, "cost": 0.5}}}}}`. Tras `record_snapshot`, `daily_project` tiene dos filas para `("2026-11-20", "/p")` con `source` distinto y tokens 10 y 7.
- `test_record_snapshot_writes_extra_claude_account`: un `sources` con solo `"claude_code@robc"` deja filas con `source="claude_code@robc"`. (Hoy se descartan.)
- `test_record_snapshot_schema_unchanged`: `PRAGMA table_info(daily_project)` igual que antes (cinco columnas, misma PK).

En `tests/test_app_settings.py`:
- `test_get_app_settings_without_accounts_seeds_personal`: BD sin clave `accounts`, con `roi_settings` `subscription_cost_claude=20` → `get_app_settings()["accounts"]` tiene una cuenta `personal` con `monthly_cost=20`.
- `test_save_and_read_accounts_roundtrip`: guardar dos cuentas y leerlas de vuelta, idénticas.
- `test_validate_rejects_two_defaults`: `validate_app_settings({"client_roots": [], "accounts": [...dos defaults...]})` → `AppSettingsError`.
- `test_validate_still_requires_client_roots`: sin `client_roots` → `AppSettingsError` (comportamiento actual).
- `test_unknown_key_still_rejected`: `{"client_roots": [], "foo": 1}` → `AppSettingsError`.

- [ ] **Step 2: Ejecutar y ver que fallan**

Run: `python3 -m unittest tests.test_history tests.test_app_settings -v`
Expected: FAIL en los casos nuevos; los tests existentes pasan.

- [ ] **Step 3: Implementar**

- En `validate_app_settings`, aceptar `accounts` y envolver `AccountsError` en `AppSettingsError` (misma forma que `ClientRootsError` hoy).
- En `record_snapshot`, construir la lista de claves con `("claude_code", "codex", "opencode", "hermes")` más cualquier clave de `sources` con `accounts.is_claude_source(k)`. Mantener `INSERT OR REPLACE` sin poda.
- `_put_app_setting(db_path, "accounts", normalized)` igual que `client_roots`, con `json.dumps`.

- [ ] **Step 4: Ejecutar y ver que pasan**

Run: `python3 -m unittest tests.test_history tests.test_app_settings -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add history.py tests/test_history.py tests/test_app_settings.py CHANGELOG.md
git commit -m "feat(history): cuentas en app_settings y fuente por cuenta en el histórico"
```

## Task 3: Recolección por cuenta (`main.py`, `server.py`)

**Files:**
- Modify: `main.py` (`collect_all`, `combine_projects`, `main()`)
- Modify: `server.py` (llamada a `combine_projects` línea ~48 y la recolección del hilo)
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `accounts.claude_projects_dir`, `accounts.source_name` (Task 1); `history.get_app_settings` (Task 2).
- Produces:
  - `collect_all(db_path=None, account_list=None) -> dict[str, dict]`. Si `account_list` es `None`, lee las cuentas de `history.get_app_settings(db_path)["accounts"]`. Para cada cuenta de Claude Code llama `claude_code.collect(projects_dir=accounts.claude_projects_dir(acc))` y guarda el resultado bajo `accounts.source_name(acc)`. Codex, OpenCode, Hermes y OpenRouter se recolectan igual que hoy, con las claves `codex`, `opencode`, `hermes`, `openrouter`.
  - `combine_projects(sources: dict[str, dict]) -> dict`. Cambia la firma: ya no recibe cuatro argumentos posicionales. Suma todas las fuentes de proyecto (las que cumplen `is_claude_source` más `codex`, `opencode`, `hermes`); `openrouter` nunca entra.
  - `server.py` pasa el dict completo de `sources` a `combine_projects`.

- [ ] **Step 1: Escribir los tests que fallan**

En `tests/test_main.py`:
- `test_collect_all_calls_claude_once_per_account`: con dos cuentas, `claude_code.collect` se llama dos veces con `projects_dir` distintos; las claves del resultado son `claude_code` y `claude_code@robc`.
- `test_collect_all_skips_missing_dir_without_error`: una cuenta cuyo `location` no existe → `claude_code.collect` devuelve `{}` y no lanza. (Review Focus 1)
- `test_combine_projects_sums_all_claude_accounts`: `combine_projects({"claude_code": {"/p": {...cost 1}}, "claude_code@robc": {"/p": {...cost 2}}})` → `/p` con `cost == 3`.
- `test_combine_projects_excludes_openrouter`: una clave `openrouter` no aparece en el combinado.

Actualizar el test existente de `combine_projects` a la nueva firma (un solo dict).

- [ ] **Step 2: Ejecutar y ver que fallan**

Run: `python3 -m unittest tests.test_main -v`
Expected: FAIL en los casos nuevos y en el de firma.

- [ ] **Step 3: Implementar**

Usar `account_list` como parámetro para que los tests no dependan de la BD real. En `server.py`, el hilo de recolección ya llama `main.collect_all()`; no cambia más que la llamada a `combine_projects`.

- [ ] **Step 4: Ejecutar y ver que pasan**

Run: `python3 -m unittest tests.test_main tests.test_server -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add main.py server.py tests/test_main.py CHANGELOG.md
git commit -m "feat(main): recolecta cada cuenta de Claude Code por separado"
```

## Task 4: Veredicto por cuenta en el briefing (`briefing.py`)

**Files:**
- Modify: `briefing.py` (`SUBSCRIPTION_KEYS`, `VALID_SOURCES`, `SOURCE_LABELS`, `SOURCE_SLUGS`, `rows_for_source`, `_subscription_candidates`, `subscription_summary`, `rule_subscription_missing`, `build_context`, `build_briefing`, `get_briefing`)
- Test: `tests/test_briefing.py`

**Interfaces:**
- Consumes: `accounts.source_name`, `accounts.provider_of_source`, `accounts.is_claude_source`; `history.get_app_settings` (Task 2).
- Produces:
  - `build_briefing(project_rows, model_rows, settings, today, source="all", compare=None, degraded=False, roots=None, accounts=None)`. `accounts` es la lista normalizada; si es `None`, se usa `accounts.legacy_accounts(settings)`.
  - `VALID_SOURCES` se calcula a partir de las cuentas: `("all", "codex", "opencode", "hermes", "openrouter") + tuple(source_name(a) for a in accounts)`. Mantener los nombres actuales válidos (`claude_code` es el nombre de la cuenta por defecto).
  - `subscription_summary(source, project_rows, accounts, window)`. Cambia la firma: recibe la lista de cuentas en lugar de `settings`. Para `source == "all"` suma todas las cuentas configuradas (costo no nulo). Para `source` = nombre de una cuenta, solo esa. Cuentas sin costo o con `start_date` posterior a `window[1]` no cuentan.
  - La respuesta de `build_briefing` añade `"accounts": [{"id", "label", "source", "configured", "paid", "api_equivalent", "winner", "savings"}]`, un elemento por cuenta, con el mismo cálculo que `subscription_summary` aplicado a esa cuenta sola. Los campos existentes (`subscription`, etc.) no cambian de forma.
  - `rule_subscription_missing` usa la lista de cuentas en lugar de `SUBSCRIPTION_KEYS`.

- [ ] **Step 1: Escribir los tests que fallan**

En `tests/test_briefing.py`:
- `test_subscription_summary_robc_starts_on_its_date`: cuenta `robc` con `monthly_cost=20`, `start_date="2026-11-19"`, ventana noviembre 2026; solo cuenta el API equivalente de `claude_code@robc` desde el día 19.
- `test_all_sums_paid_across_accounts`: personal 20 + robc 20 → `paid == 40`.
- `test_account_without_cost_is_not_configured`: `monthly_cost=None` → `configured=False` en su entrada de `accounts`.
- `test_future_start_date_is_not_configured`: `start_date` después de la ventana → `configured=False`.
- `test_per_account_verdict_uses_only_its_rows`: el API de `claude_code` no incluye filas de `claude_code@robc`.
- `test_missing_dir_shows_sin_datos_not_error`: una cuenta sin filas en `daily_project` → `configured=True` si tiene costo, `api_equivalent=0.0`, sin excepción. (Review Focus 1)
- `test_legacy_settings_still_produce_claude_verdict`: solo `subscription_cost_claude` en settings, sin lista de cuentas → mismo `subscription` que antes del cambio.

Los tests existentes de `subscription_summary` se actualizan a la nueva firma con la lista legacy equivalente.

- [ ] **Step 2: Ejecutar y ver que fallan**

Run: `python3 -m unittest tests.test_briefing -v`
Expected: FAIL en los casos nuevos.

- [ ] **Step 3: Implementar**

Reemplazar las lecturas de `SUBSCRIPTION_KEYS` por la lista de cuentas. `rows_for_source` para una cuenta filtra por su `source` exacto; para `all` incluye todas las fuentes que cumplen `is_claude_source` más las de proyecto no Claude. `SOURCE_LABELS` para una cuenta adicional: `"<label> (Claude Code)"`, construido desde la cuenta.

- [ ] **Step 4: Ejecutar y ver que pasan**

Run: `python3 -m unittest tests.test_briefing -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add briefing.py tests/test_briefing.py CHANGELOG.md
git commit -m "feat(briefing): veredicto suscripción vs API por cuenta"
```

## Task 5: Endpoints (`server.py`)

**Files:**
- Modify: `server.py` (`GET /api/briefing`, `POST /api/app-settings`, `GET /api/app-settings`)
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `briefing.get_briefing` acepta cualquier `source` de `VALID_SOURCES` (Task 4); `history.validate_app_settings` (Task 2).
- Produces: sin nuevas funciones. Cambios de contrato:
  - `GET /api/briefing?source=<valor>`: `<valor>` puede ser `claude_code@<id>` para cualquier cuenta configurada. Un id inexistente → HTTP 400 con `{"error": "Fuente desconocida: ..."}`, el mismo formato que hoy.
  - `GET /api/app-settings` devuelve además `accounts`.
  - `POST /api/app-settings` acepta `accounts`. Una validación fallida → HTTP 400 y no escribe nada.

- [ ] **Step 1: Escribir los tests que fallan**

En `tests/test_server.py`:
- `test_briefing_accepts_account_source`: con una cuenta `robc` configurada, `GET /api/briefing?source=claude_code@robc` → 200 y `source` en la respuesta es `claude_code@robc`.
- `test_briefing_unknown_account_is_400`: `source=claude_code@nope` → 400.
- `test_app_settings_post_rejects_two_defaults_without_writing`: POST con dos defaults → 400, y un GET posterior no muestra esas cuentas. (Review Focus 4)
- `test_app_settings_roundtrip_accounts`: POST válido, GET devuelve lo mismo.

- [ ] **Step 2: Ejecutar y ver que fallan**

Run: `python3 -m unittest tests.test_server -v`
Expected: FAIL en los casos nuevos.

- [ ] **Step 3: Implementar**

Sin lógica nueva: `server.py` ya delega en `briefing.get_briefing` y `history.validate_app_settings`. Solo hay que pasar el `source` sin cambios y convertir `AccountsError` en 400 si llega desde la validación de `app-settings`.

- [ ] **Step 4: Ejecutar y ver que pasan**

Run: `python3 -m unittest tests.test_server tests.test_app_settings -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_server.py CHANGELOG.md
git commit -m "feat(server): endpoints de cuentas y fuente por cuenta en el briefing"
```

## Task 6: Frontend — editor de cuentas y selector de fuente

**Files:**
- Modify: `frontend/src/lib/api.ts` (tipos `Account`, `AppSettings.accounts`, `BriefingResponse.accounts`)
- Modify: `frontend/src/components/RoiView.tsx` (lista de cuentas editable)
- Modify: `frontend/src/components/RoiFields.tsx` (campos por cuenta)
- Modify: `frontend/src/lib/roiDraft.ts` (borrador de cuentas: añadir, quitar, validar default)
- Test: `frontend/src/lib/roiDraft.test.ts`

**Interfaces:**
- Consumes: `GET/POST /api/app-settings` con `accounts` (Task 5); `GET /api/briefing` con `accounts` (Task 4).
- Produces (en `roiDraft.ts`):
  - `type AccountDraft = { id: string; provider: "claude_code"; label: string; location: string; default: boolean; monthly_cost: number | null; start_date: string | null }`
  - `validateAccountDrafts(drafts: AccountDraft[]): string | null`: devuelve el primer problema en español, o `null`. Mismas reglas que Task 1.
  - `addAccountDraft(drafts: AccountDraft[], provider: "claude_code"): AccountDraft[]`
  - `removeAccountDraft(drafts: AccountDraft[], id: string): AccountDraft[]`

- [ ] **Step 1: Escribir los tests que fallan**

En `frontend/src/lib/roiDraft.test.ts` (Vitest):
- `validateAccountDrafts` devuelve `null` para dos cuentas con un solo default.
- Devuelve un mensaje para dos defaults, para id vacío, para id repetido, para `location` relativa.
- `addAccountDraft` añade una cuenta con `default: false` y un id que no colisiona.
- `removeAccountDraft` no permite quitar la única cuenta `default` del proveedor (devuelve la lista sin cambios).

- [ ] **Step 2: Ejecutar y ver que fallan**

Run: `cd frontend && npx vitest run src/lib/roiDraft.test.ts`
Expected: FAIL con funciones no exportadas.

- [ ] **Step 3: Implementar**

En `RoiView.tsx`, una sección "Cuentas de suscripción" con una fila por cuenta (etiqueta, directorio, costo mensual, fecha de inicio, marca de default, botón quitar) y un botón "Añadir cuenta". En el selector de fuente del dashboard, una opción por cuenta con etiqueta `"<label> (Claude Code)"`. El botón Guardar envía `accounts` a `POST /api/app-settings`; si `validateAccountDrafts` devuelve error, se muestra y no se envía.

- [ ] **Step 4: Ejecutar y ver que pasan, y compilar**

Run: `cd frontend && npx vitest run && npm run build`
Expected: todos los tests pasan y `tsc -b && vite build` termina sin errores.

- [ ] **Step 5: Commit**

```bash
git add frontend/src CHANGELOG.md
git commit -m "feat(frontend): editor de cuentas de suscripción y selector por cuenta"
```

## Task 7: Release v1.3.0

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `VERSION` (`1.3.0`)
- Modify: `frontend/package.json` y `frontend/package-lock.json` (vía `npm version`)
- Modify: `CLAUDE.md` (regla de OpenRouter ya editada en el espacio de trabajo; se commitea aquí; añadir `accounts.py` a la lista de módulos de arquitectura)
- Modify: `README.md` (sección corta "Varias cuentas por proveedor")

**Interfaces:** ninguna.

- [ ] **Step 1: Escribir la verificación**

Run: `python3 -m unittest tests.test_version -v`
Expected: FAIL si `VERSION` y `CHANGELOG.md` no coinciden todavía.

- [ ] **Step 2: Actualizar documentación y versión**

- `VERSION` → `1.3.0`.
- `cd frontend && npm version 1.3.0 --no-git-tag-version`.
- `CHANGELOG.md`: renombrar `## [Sin publicar]` a `## [1.3.0] - 2026-11-20`, abrir un `## [Sin publicar]` vacío encima y actualizar los enlaces de comparación al final. La subsección `### Añadido` describe, para el usuario: varias cuentas por proveedor, veredicto por cuenta, selector por cuenta. Sin pasos de migración: el histórico y la configuración existente no cambian.
- `CLAUDE.md`: añadir una línea para `accounts.py` en la arquitectura.
- `README.md`: sección corta con cómo añadir una cuenta desde el dashboard y que las rutas deben ser absolutas.

- [ ] **Step 3: Ejecutar la suite completa**

Run: `python3 -m unittest discover -s tests -v && cd frontend && npx vitest run && npm run build`
Expected: todo PASS.

- [ ] **Step 4: Commit de release**

```bash
git add VERSION CHANGELOG.md CLAUDE.md README.md frontend/package.json frontend/package-lock.json
git commit -m "chore(release): v1.3.0"
```

Los pasos de tag, push y release en GitHub **no** forman parte del plan. Se piden al usuario al terminar la rama.
