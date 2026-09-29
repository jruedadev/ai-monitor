# Parametrización de carpetas y onboarding inicial — diseño

Fecha: 2026-09-29

## 1. Objetivo

Hoy la agrupación por cliente está fija en el código: el cliente de un proyecto es el segmento
que sigue a una carpeta llamada `DEV` (`clientOf` en `frontend/src/lib/clients.ts` y
`briefing.client_of`). Si alguien clona el repo y no organiza su código bajo `DEV`, todos sus
proyectos caen en "Otros".

Este cambio:

1. Convierte las carpetas raíz de agrupación en un ajuste persistido en `history.db`.
2. Añade un onboarding inicial en el frontend (`/bienvenida`). Crea los ajustes de carpetas, ROI
   y motor la primera vez, se puede omitir y se puede repetir desde Configuración.

**Criterios de éxito**
- Una instalación nueva, sin ajustes, muestra el onboarding al abrir el dashboard.
- Terminar u omitir el onboarding deja todo configurado y no vuelve a aparecer.
- Con las raíces por defecto, la agrupación es idéntica a la actual: los 7 casos del fixture
  siguen dando el mismo resultado.
- Un equipo recién formateado, sin Claude Code ni Hermes, completa el onboarding sin errores y
  con un backend de motor utilizable (`none` si no hay ninguno).

**Fuera de alcance**
- Reglas por expresión regular.
- Alias o renombrado manual de clientes.
- Asignar un proyecto suelto a un cliente a mano.
- Detección automática de las fuentes instaladas: se sigue usando `sourceStatuses`, que no
  distingue "no instalado" de "sin uso".
- Una regla de compatibilidad (`legacy`) para instalaciones existentes. Solo existe una
  instalación previa, la del autor, que pasará una vez por el onboarding o lo omitirá.

## 2. Modelo: raíces de cliente

Una raíz es `{root, mode}`:

- **`root`** es un **nombre de carpeta** o una **ruta absoluta**.
  - Nombre de carpeta: sin `/`, por ejemplo `DEV` o `clientes`. Coincide con cualquier segmento
    de la ruta del proyecto, en cualquier nivel y **sin distinguir mayúsculas**.
  - Ruta absoluta: empieza por `/`, por ejemplo `/srv/trabajo`. Coincide si la ruta del proyecto
    es igual a la raíz o empieza por `root + "/"`. Distingue mayúsculas, como el sistema de
    archivos. Se normaliza quitando la `/` final.
- **`mode`** es `cliente` o `plano`.
  - `cliente`: el cliente es el segmento que sigue a la raíz. Si no hay segmento siguiente (el
    proyecto es la raíz misma), el cliente es "Otros".
  - `plano`: el cliente es el nombre de la raíz, es decir su último segmento. `/srv/trabajo` da
    `trabajo` y `DEV` da `DEV`.

**Algoritmo `client_of(path, roots)`**
1. Se recorren las raíces **en orden**; gana la primera que coincide.
2. En una raíz por nombre, cuenta la **primera** aparición del segmento en la ruta. Así se
   conserva el caso actual: `/srv/DEV/A/DEV/B/app` da `A`.
3. Si ninguna raíz coincide, el cliente es "Otros". Una ruta vacía también da "Otros".

**Valor por defecto:** `[{"root": "DEV", "mode": "cliente"}]`. Reproduce exactamente el
comportamiento actual.

**Validación**
- Entre 1 y 20 raíces.
- `root` no vacío después de `strip()`, con 200 caracteres como máximo.
- `root` sin `/` (nombre) o empezando por `/` (ruta absoluta). No se admite un nombre con `/`
  intermedias ni una ruta relativa.
- `mode` debe ser `cliente` o `plano`.
- Sin duplicados después de normalizar: sin `/` final y, en nombres, sin distinguir mayúsculas.

## 3. Backend

### 3.1 Persistencia (`history.py`)

Nueva tabla, creada en `ensure_schema`:

```sql
CREATE TABLE IF NOT EXISTS app_settings (
  key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL
);
```

Claves (el valor siempre es JSON):
- `client_roots`: la lista de raíces.
- `onboarding_completed_at`: marca ISO-8601 UTC. Si no existe, el onboarding no se ha completado.

Funciones, siguiendo el patrón de `roi_settings`:
- `get_app_settings(db_path=None) -> {"client_roots": [...], "onboarding_completed_at": str | None}`.
  Si un valor tiene JSON roto o un tipo inválido, esa clave cae al valor por defecto y no se
  lanza error.
- `class AppSettingsError(ValueError)`.
- `validate_app_settings(payload) -> dict`: allowlist de claves. Solo `client_roots` se puede
  escribir por esta vía. Devuelve las raíces normalizadas.
- `save_app_settings(settings, db_path=None)`: `INSERT OR REPLACE`.
- `complete_onboarding(now, db_path=None)`: escribe `onboarding_completed_at`. Es idempotente;
  cada llamada sobrescribe la marca.
- `DEFAULT_CLIENT_ROOTS`.

`client_of(path, roots)` vive en un módulo puro nuevo, `clients.py`, en la raíz del backend. Así
lo usan `briefing.py` y los tests sin depender de `history.py`.

### 3.2 Briefing

- `briefing.client_of` se reemplaza por `clients.client_of(path, roots)`.
- `briefing` lee `client_roots` con su conexión de solo lectura (`mode=ro`).
- Si la tabla no existe (`sqlite3.OperationalError`) o el valor es inválido, usa
  `DEFAULT_CLIENT_ROOTS`.
- `briefing` sigue sin crear ni modificar `history.db`.

### 3.3 API (`server.py`)

| Método | Ruta | Respuesta |
|---|---|---|
| GET | `/api/app-settings` | `200 {"client_roots": [...], "onboarding_completed_at": ... }` |
| POST | `/api/app-settings` | Cuerpo `{"client_roots": [...]}`. `200` con los ajustes guardados; `400` con `{"error"}` si la validación falla; `415` si no es JSON. |
| POST | `/api/app-settings/onboarding` | Cuerpo `{}`. `200 {"onboarding_completed_at": ...}`; `415` si no es JSON. |
| GET | `/api/engine-settings` | Se añade `"available": {"hermes": bool, "claude": bool}` vía `shutil.which`, evaluado en cada request. |

Los errores de SQLite en `GET /api/app-settings` devuelven los valores por defecto con
`onboarding_completed_at: null` y `"degraded": true`, nunca un 500.

`POST /api/engine-settings` **no** rechaza un backend no instalado: el motor ya degrada sin LLM
y el usuario puede instalarlo después. El frontend es quien desaconseja esa opción.

### 3.4 Sin herramientas instaladas

- Los collectors ya devuelven vacío cuando falta una fuente, y eso no cambia.
- El paso 3 del onboarding sugiere un backend con `hermes` → `claude` → `none`, según
  `available`. "Omitir" guarda esa misma sugerencia.
- El README documenta el onboarding, cómo repetirlo y qué pasa sin herramientas instaladas.

## 4. Frontend

### 4.1 Raíces como estado global

- `lib/appSettings.ts`:
  - Tipos `ClientRoot` y `AppSettings`.
  - `fetchAppSettings`, `saveAppSettings` y `completeOnboarding`, en `lib/api.ts`.
  - `DEFAULT_CLIENT_ROOTS`.
- `useAppSettings()` más un `AppSettingsContext`, cargados una vez en `App.tsx`. Exponen
  `{ roots, onboardingCompletedAt, loading, error, reload }`.
- Si la carga falla, se usan las raíces por defecto y **no** se redirige al onboarding.
- `clientOf(path, roots)` y `groupProjectsByClient(paths, roots)` reciben `roots` como parámetro.
  Se actualizan sus consumidores:
  - `App.tsx`
  - `lib/projects.ts`
  - `lib/commands.ts`
  - `TrendChart`
  - `SessionDetail`
  - `RoiView`
  - `ProjectsView`

  Las funciones de `lib/` reciben `roots` por parámetro y los componentes lo toman del contexto.

### 4.2 Ruta `/bienvenida`

- Se añade a `routes.ts` (`parsePath`/`VIEW_KEYS`). Se renderiza fuera del layout con sidebar,
  en pantalla completa.
- La guarda es la función pura `shouldRedirectToOnboarding({completedAt, loading, error, degraded}, path)`:
  redirige solo si ya cargó, sin error ni `degraded`, con `completedAt === null` y fuera de `/bienvenida`.
  `App.tsx` la aplica con `<Navigate to="/bienvenida" replace />`.
- `/bienvenida` también es accesible con el onboarding completado, para repetirlo. Los pasos
  arrancan con los valores actuales.

**`OnboardingView`** es un stepper de 3 pasos. El borrador vive en memoria hasta Finalizar.

1. **`FoldersStep`**
   - Muestra las fuentes detectadas con `sourceStatuses`.
   - Propone raíces con `suggestRoots(paths)` (pura, en `lib/`). Para cada proyecto toma la
     carpeta que está dos niveles por encima (en `/x/DEV/GLOBEX/app` es `DEV`). Propone en modo
     `cliente` los nombres que aparecen en ≥2 proyectos, ordenados por frecuencia. Descarta
     `home`, `Users`, el segmento que sigue a `home`/`Users` (el usuario) y los segmentos vacíos.
     Sin propuestas, deja el valor por defecto.
   - Permite entrada manual y un selector de modo por raíz, con reordenamiento (la primera gana).
   - Incluye una vista previa en vivo con los clientes resultantes y el número de proyectos en
     "Otros".
2. **`RoiStep`**: los campos de `SettingsForm` se extraen a un componente `RoiFields` que se
   comparte. Solo muestra las fuentes con datos. Sin datos, muestra un texto explicativo y
   permite continuar.
3. **`EngineStep`**: un selector de backend con las opciones no instaladas deshabilitadas y una
   nota de instalación. El valor inicial viene de `suggestBackend(available)` (pura).

**Botones**
- **Omitir**: guarda `DEFAULT_CLIENT_ROOTS` y el backend sugerido con la cadena por defecto, y
  marca el onboarding. No toca ROI.
- **Atrás/Siguiente** para navegar entre pasos.
- **Finalizar**: guarda en orden app-settings → roi-settings → engine-settings →
  `POST /api/app-settings/onboarding`, luego `reload()` y navega a `/`.
- Si un guardado falla, la vista se queda en el paso correspondiente con el error y el onboarding
  no se marca. Reintentar es seguro porque cada guardado es idempotente.

### 4.3 Configuración

- Nueva tarjeta `ClientRootsForm`: lista editable (raíz, modo, orden) con la misma vista previa y
  un botón Guardar. Al guardar llama a `reload()` del contexto.
- Botón "Repetir configuración inicial" que navega a `/bienvenida` sin borrar nada.

## 5. Fixture compartido

`tests/fixtures/client_of_cases.json` pasa a tener la forma `{"roots": [...] | null, "path": ...,
"client": ...}`, donde `null` significa raíces por defecto. Los 7 casos actuales se conservan con
`roots: null`. Se añaden casos para:

- modo `plano` por nombre y por ruta absoluta;
- ruta absoluta con prefijo, más un falso positivo (`/srv/trabajo2/x` no coincide con
  `/srv/trabajo`);
- la primera raíz gana cuando dos coinciden;
- nombre sin distinguir mayúsculas y ruta absoluta que sí las distingue;
- una raíz que es el proyecto mismo en modo `cliente`, que da "Otros".

Lo leen `tests/test_clients.py` y `frontend/src/lib/clients.test.ts`.

## 6. Testing

**Backend (unittest)**
- `tests/test_clients.py`: el fixture compartido.
- `tests/test_app_settings.py`:
  - roundtrip de guardado y lectura;
  - cada error de validación;
  - normalización y duplicados;
  - fallback con JSON corrupto;
  - BD vieja sin la tabla;
  - `complete_onboarding` idempotente.
- `test_briefing`:
  - raíces leídas en solo lectura;
  - fallback sin tabla;
  - un caso con modo `plano` en `top_projects`;
  - comprobar que `history.db` no se crea.
- `test_server_*`:
  - GET/POST `/api/app-settings` con `400`/`415`;
  - `POST .../onboarding`;
  - `available` en `engine-settings` con `shutil.which` parcheado;
  - degradado ante `sqlite3.Error`.

**Frontend (vitest, solo `lib/` puro)**
- `clientOf` con el fixture;
- `groupProjectsByClient` con raíces;
- `suggestRoots`;
- `suggestBackend`;
- `shouldRedirectToOnboarding` (incluye error de carga y `degraded`);
- `parsePath("/bienvenida")`.

La interacción del wizard (clics, guardado y redirección) queda para el E2E con Playwright
(T14 del subproyecto 3).

**Verificación completa**
```bash
env -u OPENROUTER_API_KEY python3 -m unittest discover -s tests
cd frontend && npx vitest run && npx oxlint && npx tsc -b --noEmit && npm run build
```

## 7. Documentación

- **README:** sección "Configuración inicial" con el onboarding, las raíces y los modos (con
  ejemplos), cómo repetirlo y el comportamiento sin herramientas instaladas.
- **CLAUDE.md:**
  - `/api/app-settings` en la lista de endpoints del frontend;
  - `clients.py` como fuente única de `client_of` en el backend;
  - el fixture compartido como contrato entre los dos lados.
