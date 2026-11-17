# Compatibilidad con macOS — diseño

Fecha: 2026-10-01
Versión objetivo: 1.3.0 (MINOR) — desde 1.2.0

## 1. Objetivo

Que un usuario de macOS clone el repo, corra `./install.sh` y obtenga lo mismo que en Linux:
colectores, dashboard interactivo, motor de recomendaciones y las dos tareas periódicas
(regenerar el HTML cada 15 minutos y el motor a las 07:00), sin editar nada a mano.

Windows queda fuera (ver §9): este es el primer paso de una compatibilidad por etapas.

Hoy el backend ya es casi portable (solo biblioteca estándar, sin `fcntl`, `/proc` ni señales
POSIX). Lo que falla en macOS es la **instalación** (systemd) y unos pocos supuestos de Linux.
El cambio tiene cuatro partes:

1. Un módulo `paths.py` que centraliza dónde viven los datos de cada herramienta y los propios.
2. `install.sh` con una rama para macOS que genera y carga agentes **launchd**.
3. Ajustes de portabilidad en `install.sh` (utilidades BSD) y en `shell/aliases.sh` (`open`).
4. Integración continua en una matriz Linux + macOS, que es lo único que garantiza que macOS
   siga funcionando (el autor desarrolla en Linux).

## 2. Hallazgos del código actual

| Punto | Estado | Acción |
|---|---|---|
| `os.path.expanduser("~/...")` repartido en 12 archivos (`collectors/`, `live/`, `recommend/`, `history.py`, `engine.py`) | Funciona en macOS si las rutas coinciden | Centralizar en `paths.py` (§3) |
| Lock del motor (`recommend/engine.py`): `O_CREAT\|O_EXCL` + PID vivo | Portable | Sin cambios |
| `server.py`: `shutil.which`, hilos, `http.server` | Portable | Sin cambios |
| `systemd/*` + `install.sh` | Solo Linux | launchd en macOS (§4) |
| `install.sh`: `find -print -quit`, `sed`, arrays de bash | `-quit` no existe en BSD `find`; bash 3.2 en macOS | Reescribir esas partes (§5) |
| `shell/aliases.sh`: `xdg-open` | Solo Linux | `open` en macOS (§5) |
| `clients.py` / `clients.ts` / `onboarding.ts` | Rutas con `/` | Sin cambios: macOS usa `/Users/...` (ya contemplado en `HOME_DIRS`) |
| `recommend/redact.py` | Regex de rutas Unix | Sin cambios; añadir caso `/Users/...` al test |

## 3. `paths.py`: rutas por fuente

Módulo nuevo en la raíz, sin lógica de negocio. Cada función devuelve la ruta por defecto y
respeta una variable de entorno de sobrescritura antes de mirar el sistema operativo:

```python
def claude_projects_dir() -> str     # ~/.claude/projects
def codex_state_db() -> str          # ~/.codex/state_5.sqlite
def codex_sessions_dir() -> str      # ~/.codex/sessions
def opencode_db() -> str             # ~/.local/share/opencode/opencode.db
def hermes_state_db() -> str         # ~/.hermes/state.db
def data_dir() -> str                # datos propios (history.db, lock, motor)
def config_dir() -> str              # ~/.config/ai-monitor (env)
```

- Todas se resuelven con `os.path.expanduser` en el momento de la llamada, no al importar, para
  que los tests con `HOME` falso sigan funcionando.
- Los colectores, los lectores de `live/` y de `recommend/prompts/` reemplazan su
  `expanduser("~/...")` literal por estas funciones. Los parámetros de sobrescritura
  (`projects_dir`, `db_path`, `override`…) no cambian.
- **Los datos propios no se mueven.** En macOS `data_dir()` y `config_dir()` siguen siendo
  `~/.local/share/ai-monitor` y `~/.config/ai-monitor`, igual que en Linux. Usar
  `~/Library/Application Support` sería lo idiomático, pero rompería la regla de "una sola
  ubicación documentada", obligaría a una migración y no aporta nada al usuario de una
  herramienta de terminal. Decisión: mismas rutas en ambos sistemas.

### Rutas de las herramientas en macOS: a verificar antes de implementar

Es la principal incógnita de la spec. Se parte de este supuesto y se **confirma en un macOS
real** como primera tarea del plan, dejando el resultado en el ledger:

| Fuente | Ruta supuesta (igual que Linux) | Por qué |
|---|---|---|
| Claude Code | `~/.claude/projects` | Usa `~/.claude` en todas las plataformas |
| Codex | `~/.codex/...` | Usa `~/.codex` en todas las plataformas |
| Hermes | `~/.hermes/state.db` | Directorio propio bajo `~` |
| OpenCode | `~/.local/share/opencode/opencode.db` | Usa XDG también en macOS, a confirmar |

Si alguna difiere, `paths.py` devuelve la correcta según `sys.platform` y la tabla de arriba se
corrige en el spec. Si una fuente no existe, el colector ya degrada a vacío (regla de
"graceful degradation" de `CLAUDE.md`).

## 4. launchd

Plantillas nuevas en `launchd/` (paralelas a `systemd/`), con los mismos marcadores
`__REPO_DIR__`, `__PYTHON__`, `__ENV_FILE__`, `__PATH__`:

| Agente | Equivale a | Clave principal |
|---|---|---|
| `dev.jrueda.ai-monitor.plist` | `ai-monitor.timer` + servicio | `StartInterval` 900, `RunAtLoad` |
| `dev.jrueda.ai-monitor-recommend.plist` | `ai-monitor-recommend.timer` | `StartCalendarInterval` Hour 7, Minute 0 |
| `dev.jrueda.ai-monitor-server.plist` | `ai-monitor-server.service` | `KeepAlive` (reinicia al fallar), `RunAtLoad` |

- Se instalan en `~/Library/LaunchAgents/`. Etiquetas con prefijo `dev.jrueda.` (dominio del autor,
  evita colisiones).
- launchd no tiene `EnvironmentFile`: el script de arranque lee `~/.config/ai-monitor/env`.
  Cada plist ejecuta `__PYTHON__ __REPO_DIR__/main.py ...` a través de un pequeño envoltorio
  `launchd/run-with-env.sh` que hace `set -a; . "$ENV_FILE"; set +a; exec "$@"`.
- Salida estándar y de error a `~/Library/Logs/ai-monitor/*.log`.
- Los agentes `--user` no existen como concepto: los LaunchAgents ya corren como el usuario,
  que es lo que necesitamos (leen `$HOME`).
- Diferencia de comportamiento documentada: el timer de systemd usa `Persistent=true` (ejecuta
  una corrida perdida al despertar). `StartCalendarInterval` de launchd también ejecuta al
  despertar si el equipo estaba dormido, así que la semántica es equivalente.

## 5. `install.sh` y `shell/aliases.sh`

- Detección con `uname -s`: `Linux` → ruta systemd actual; `Darwin` → ruta launchd; otro → error
  claro ("sistema no soportado, usa --sin-activar").
- Activación en macOS: `launchctl bootstrap gui/$(id -u) <plist>` (y `bootout` previo si ya
  estaba cargado, para que reinstalar recargue). Misma semántica que `daemon-reload` +
  `enable --now` + `restart`.
- Las opciones `-y`/`--yes` y `--sin-activar` se conservan idénticas.
- Compilación del frontend: la comprobación de "dist desactualizado" se reescribe sin `find
  -print -quit` (no existe en BSD): `[ -n "$(find ... -newer "$DIST_INDEX" | head -n 1)" ]`.
- `PYTHON_BIN`: si `python3` es el de las Command Line Tools (3.9) y el repo exige más, el
  script avisa y sugiere Homebrew (§7 fija la versión mínima).
- `shell/aliases.sh`: `xdg-open` se sustituye por `open` cuando `uname` es `Darwin`.
- Bash 3.2 (el de macOS): `install.sh` ya evita `mapfile`/arrays asociativos; las matrices
  indexadas y `[[ ]]` funcionan. La CI lo ejecuta con el bash del runner de macOS.

## 6. Testing

- Unitarios de `paths.py`: ruta por defecto, `HOME` falso, y que cada función se evalúa al
  llamarla (no al importar).
- Los tests existentes con `HOME` o rutas de override deben seguir pasando sin cambios; es la
  prueba de que la centralización es transparente.
- Plantillas launchd: test de que cada `.plist` es XML válido (`plistlib`), que no queda ningún
  marcador `__X__` sin sustituir y que `StartInterval`/`StartCalendarInterval` son los esperados
  (mismo estilo que `tests/test_systemd_units.py`).
- `install.sh`: test de la rama macOS simulando `uname` con un `PATH` falso y `--sin-activar`,
  verificando que genera los plists en un `HOME` temporal y no invoca `launchctl`.
- `redact.py`: caso nuevo con una ruta `/Users/<nombre>/...`.
- **CI** (`.github/workflows/ci.yml`): matriz `ubuntu-latest` + `macos-latest`, Python 3.10 y el
  más reciente, `python3 -m unittest discover -s tests` y, en el frontend, `npm ci
  --legacy-peer-deps`, `npm run lint`, `tsc`, `vitest` y `npm run build`. Los 2 fallos
  existentes de `tests/test_openrouter.py` (dependen del entorno) se aíslan con el entorno
  limpio del runner o se corrigen en esta spec si siguen fallando.

## 7. Requisitos y documentación

- Versión mínima de Python: se fija en 3.10 (ya cubierta por `test_py_compat.py`) y se documenta
  en el README. En macOS se recomienda Homebrew (`brew install python node`).
- README: nueva sección "macOS" (requisitos, `./install.sh`, ubicación de logs, cómo
  desinstalar con `launchctl bootout`) y una tabla de compatibilidad (Linux ✓, macOS ✓,
  Windows: ver WSL).
- `CLAUDE.md`: documentar `paths.py` como única fuente de rutas por defecto y la regla de no
  añadir `expanduser("~/...")` sueltos; `launchd/` junto a `systemd/`.
- `install.sh`, las unidades y `shell/aliases.sh` son API pública (AGENTS.md §4); aquí solo
  cambian de forma aditiva.

## 8. Impacto de versión

Versión objetivo: **1.3.0 (MINOR)**.

- **API pública tocada:** (4) configuración e instalación — `install.sh` gana una rama para
  macOS y `shell/aliases.sh` cambia de comportamiento solo en macOS; (3) datos persistidos —
  **sin cambios** (`history.db` y la ubicación de datos son idénticos).
- **Por qué MINOR:** es funcionalidad nueva compatible hacia atrás (soporte de una plataforma
  nueva). Un usuario de Linux que actualiza no pierde nada ni interviene a mano: sus rutas,
  unidades y flags son las mismas.
- Ninguna ruta, flag, endpoint ni esquema se elimina o renombra, por lo que no hay migración.

## 9. Fuera de alcance

- **Windows**, nativo o con instalador PowerShell: segunda etapa. Mientras tanto, WSL funciona
  sin cambios y se documenta.
- Mover los datos propios a `~/Library/Application Support` (§3).
- Empaquetado (Homebrew tap, `.app`, firma y notarización).
- Detección de herramientas que solo existan como app de escritorio en macOS con almacenamiento
  propio fuera de las rutas de §3.
- Cualquier cambio en `clients.py`/`clients.ts` (las rutas de macOS ya funcionan).

## 10. Preguntas abiertas

1. ¿Las rutas de datos de OpenCode, Hermes y Codex en macOS coinciden con el supuesto de §3?
   (se resuelve en la primera tarea del plan, con un macOS real o ayuda de un tercero).
2. ¿Hay un macOS disponible para probar a mano la activación con `launchctl`, o nos apoyamos
   solo en la CI (que no puede cargar agentes de usuario)? La carga real quedaría sin probar
   automáticamente.
3. ¿Se acepta fijar Python 3.10 como mínimo y declararlo en el README?
