# Dashboard multiplataforma de uso de IA — diseño

**Fecha**: 2026-08-11
**Estado**: aprobado, pendiente de plan de implementación

## Contexto

`jrdv-ai-monitor` ya tiene un script (`claude_usage.py`) que agrega tokens/costo por proyecto a partir de los transcripts locales de Claude Code (`~/.claude/projects/*.jsonl`). El objetivo de este diseño es extender esa idea a otras plataformas de IA que el usuario usa localmente: **Codex**, **OpenCode** y **OpenRouter**. Se investigó también **Hermes Agent** y **Antigravity**, pero se excluyen de esta fase:

- **Hermes**: es una app Electron; sus datos viven en perfil tipo Chrome (LevelDB/IndexedDB/Cache), sin un log estructurado de uso accesible. No hay evidencia de que exponga tokens/costo en un formato parseable.
- **Antigravity**: no se encontró ningún rastro local en esta máquina. Puede no estar instalado, o solo mantener estado en la nube.

Ambas quedan fuera del alcance; se podrán reevaluar si en el futuro se confirma que exponen datos usables.

## Fuentes de datos confirmadas

### Claude Code (ya implementado)
- Fuente: `~/.claude/projects/<dir-codificado>/*.jsonl`
- Cada línea `type: "assistant"` con bloque `usage` trae `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, `model`, `timestamp`. El `cwd` de cualquier registro de la sesión resuelve el proyecto real.
- Costo: estimado con tabla de precios de lista hardcodeada por modelo.

### Codex
- Fuente: `~/.codex/state_5.sqlite` (SQLite, vía `sqlite3` de la librería estándar de Python — no requiere el CLI `sqlite3`).
- Tabla `threads`: columnas relevantes `cwd`, `model`, `tokens_used` (total único, sin desglose input/output), `title`, `created_at` (epoch), `id`.
- Costo: estimado con la misma lógica de tabla de precios que Claude Code, extendida con precios de modelos OpenAI (`gpt-5.5`, etc.). Si el modelo no está en la tabla, el costo se marca como no disponible (no se inventa un precio) en vez de usar un default silencioso — evita cifras engañosas para modelos nuevos no mapeados.
- `~/.codex/history.jsonl` existe pero solo tiene texto de prompts, no usage — no se usa.

### OpenCode
- Fuente: `~/.local/share/opencode/opencode.db` (SQLite).
- Tabla `session`: columnas relevantes `directory`, `model` (JSON string con `id`/`providerID`/`variant`), `cost` (ya calculado por OpenCode, en USD), `tokens_input`, `tokens_output`, `tokens_reasoning`, `tokens_cache_read`, `tokens_cache_write`, `title`, `time_created` (epoch ms).
- Costo: se usa el campo `cost` tal cual lo reporta OpenCode — no se re-estima, porque ya viene calculado con el precio real del proveedor usado en cada sesión (que puede variar: OpenAI directo, OpenRouter, etc.).

### OpenRouter
- Fuente: API REST `https://openrouter.ai/api/v1/activity`, autenticada con `Authorization: Bearer $OPENROUTER_API_KEY`.
- La key debe leerse de la variable de entorno `OPENROUTER_API_KEY`. **No se lee automáticamente de `~/.local/share/opencode/auth.json`** — se probó ese token y devuelve `401 User not found` contra la API real (es un token de sesión propio de OpenCode, no una API key cruda). El usuario deberá generar una key nueva en `openrouter.ai/keys` cuando la necesite.
- Si `OPENROUTER_API_KEY` no está definida, el collector devuelve un resultado vacío con un flag `unavailable: true` y un mensaje — el resto del dashboard funciona igual.
- Esta fuente agrega por **modelo**, no por proyecto (OpenRouter no tiene noción de directorio de trabajo). Se muestra en su propia pestaña, sin fusionarse con la tabla combinada por proyecto.
- **Nota de posible solapamiento**: cuando OpenCode enruta a través de `providerID: "openrouter"`, ese consumo puede aparecer tanto en la sesión de OpenCode como en la actividad de OpenRouter. No se intenta deduplicar (no hay un ID común confiable entre ambas fuentes); se muestra una nota visible en el dashboard advirtiendo esto, y la vista "Todo" combinado solo suma Claude Code + Codex + OpenCode (nunca OpenRouter), precisamente para no inflar cifras por doble conteo.

## Arquitectura de código

```
jrdv-ai-monitor/
  main.py                    # orquesta collectors, genera tabla/JSON/HTML
  collectors/
    __init__.py
    claude_code.py           # collect() -> dict[proyecto] = {...}  (ya existente, se mueve aquí)
    codex.py                 # collect() -> misma forma
    opencode.py               # collect() -> misma forma
    openrouter.py             # collect() -> dict[modelo] = {...}, o {"unavailable": True, "reason": ...}
  dashboard/
    template.py                # HTML_TEMPLATE con pestañas
  systemd/
    jrdv-ai-monitor.service
    jrdv-ai-monitor.timer
  README.md
  CLAUDE.md
```

Cada collector de fuente "por proyecto" (`claude_code`, `codex`, `opencode`) expone la misma forma de datos que ya usa `claude_usage.py` hoy: `{input, output, cache_read, cache_write, total_tokens, cost, messages, session_count, sessions_detail: [...]}`, para que `main.py` los pueda combinar sin lógica especial por fuente. `openrouter.py` expone una forma distinta (por modelo, con actividad diaria) que se renderiza en su propia sección.

Cada collector debe fallar de forma aislada: si un archivo/BD no existe (plataforma no instalada) o hay un error de parseo, ese collector devuelve datos vacíos y una razón (`{"unavailable": True, "reason": "..."}`), sin interrumpir a los demás. `main.py` muestra un aviso por fuente no disponible en vez de fallar todo el dashboard.

## Dashboard HTML

Mismo estilo visual que el actual (self-contained: sin CDN, sin llamadas de red desde el HTML, tema claro/oscuro automático vía `prefers-color-scheme`). Se agregan pestañas:

- **Todo**: tabla combinada por proyecto sumando Claude Code + Codex + OpenCode, con una etiqueta de color por fuente en cada fila (o fila expandible mostrando el desglose por fuente del mismo proyecto).
- **Claude Code**, **Codex**, **OpenCode**: la misma vista de tabla por proyecto + top de sesiones pesadas que ya existe hoy, una por fuente.
- **OpenRouter**: tabla por modelo con tokens/costo/requests, más actividad por día. Si `unavailable`, se muestra un mensaje explicando cómo activar la key (`OPENROUTER_API_KEY`) en vez de la tabla.

## Automatización (systemd --user)

- `jrdv-ai-monitor.service`: `ExecStart=python3 <repo>/main.py --html %h/claude-usage.html`.
- `jrdv-ai-monitor.timer`: `OnUnitActiveSec=15min` (más `OnBootSec` corto para que corra una vez al iniciar sesión).
- Instalación: copiar/symlinkear ambos units a `~/.config/systemd/user/` y `systemctl --user enable --now jrdv-ai-monitor.timer`. El README documenta este paso manual (no se automatiza la instalación del timer desde el script, para no tocar `systemctl` sin que el usuario lo apruebe explícitamente).

## Alias de shell

`~/.bashrc` se actualiza:

```bash
claude-usage() {
    python3 ~/DEV/JRDV/jrdv-ai-monitor/main.py --html ~/claude-usage.html && xdg-open ~/claude-usage.html >/dev/null 2>&1 &
}
alias claude-usage-table='python3 ~/DEV/JRDV/jrdv-ai-monitor/main.py'
```

El timer mantiene `~/claude-usage.html` fresco cada 15 min en segundo plano; el alias `claude-usage` sigue forzando una regeneración inmediata antes de abrir, para ver el dato más reciente al instante sin esperar al próximo tick del timer.

## Fuera de alcance (esta fase)

- Hermes Agent, Antigravity: sin fuente de datos local viable identificada.
- Deduplicación real entre OpenCode↔OpenRouter (requeriría un ID de request común que no existe en los datos disponibles).
- Instalación automática del timer systemd sin confirmación explícita del usuario.
