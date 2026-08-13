# ai-monitor

Dashboard local de uso de IA: agrega tokens y costo por proyecto a partir de los datos que **Claude Code**, **Codex** y **OpenCode** guardan localmente, más el consumo reportado por **OpenRouter** vía su API. Sin dependencias externas — solo librería estándar de Python.

## Fuentes soportadas

| Fuente | De dónde lee | Agrupa por |
|---|---|---|
| Claude Code | `~/.claude/projects/*/*.jsonl` | proyecto (cwd real) |
| Codex | `~/.codex/state_5.sqlite` | proyecto (cwd) |
| OpenCode | `~/.local/share/opencode/opencode.db` | proyecto (directory) |
| OpenRouter | API `openrouter.ai/api/v1/activity` (requiere `OPENROUTER_API_KEY`) | modelo |

Cada fuente que no esté instalada, o cuya key no esté configurada, se omite silenciosamente de la tabla — solo OpenRouter muestra un aviso explícito cuando falta la API key. El resto del dashboard sigue funcionando.

## Uso

```bash
python3 main.py                     # tabla combinada en terminal (Claude+Codex+OpenCode)
python3 main.py --json              # todas las fuentes crudas + vista combinada, en JSON
python3 main.py --html out.html     # dashboard HTML con pestañas por fuente
```

## OpenRouter

Genera una **management key** en https://openrouter.ai/keys y expórtala:

```bash
export OPENROUTER_API_KEY="sk-or-..."
```

> **Importante:** debe ser una **management key** de la cuenta, no una key normal de uso. OpenRouter solo permite consultar el historial de actividad (`/api/v1/activity`) con management keys; una key de tipo normal autentica correctamente pero responde `403 "Only management keys can fetch activity for an account"`, y una key revocada responde `401 "User not found"`.

El collector busca la key en este orden:
1. Variable de entorno `OPENROUTER_API_KEY`.
2. Archivo `~/.config/ai-monitor/env` (generado por `install.sh` con permisos `600`, el mismo que usa la unidad de systemd).

Así funciona tanto en la terminal como en el timer de systemd, sin hardcodear la key en el código. Sin esta variable/archivo, la pestaña de OpenRouter muestra un aviso en vez de datos; el resto del dashboard no se ve afectado.

**Si persistes la key en `~/.bashrc`**, pon el `export` **antes** del bloque `case $- in ... esac` (el chequeo de shell interactivo), para que también la vean las shells no-interactivas. Y recuerda: `install.sh` copia la variable al `.env` en el momento de ejecutarlo — si revocas o regeneras la key, actualiza el `export` **y** vuelve a correr `./install.sh`.

### Flujo completo para un usuario nuevo

```bash
# 1. Genera la management key en https://openrouter.ai/keys
# 2. Exporta y persiste la key (antes del chequeo de interactividad del ~/.bashrc)
echo 'export OPENROUTER_API_KEY="sk-or-..."' >> ~/.bashrc
source ~/.bashrc

# 3. Instala: copia la key al .env (chmod 600) y genera las unidades systemd
./install.sh

# 4. Activa el timer
systemctl --user daemon-reload
systemctl --user enable --now ai-monitor.timer
```

Resultado: la terminal interactiva lee la key de `~/.bashrc`; el timer de systemd (no-interactivo) la lee de `~/.config/ai-monitor/env` vía `EnvironmentFile`. Si más adelante regeneras la key, repite los pasos 2 y 3.

## Instalación (alias + actualización automática)

1. Clona el repo donde prefieras.
2. Agrega una línea a tu `~/.bashrc` apuntando a donde lo clonaste:

   ```bash
   source "/ruta/donde/clonaste/ai-monitor/shell/aliases.sh"
   ```

3. Recarga la shell (`source ~/.bashrc`). Quedan disponibles:
   - `claude-usage` → regenera `~/claude-usage.html` y lo abre en el navegador.
   - `claude-usage-table` → imprime la tabla combinada en la terminal.

4. (Opcional) Para que el dashboard se mantenga fresco solo, corre:

   ```bash
   ./install.sh
   ```

   Detecta automáticamente dónde quedó el repo y genera una unidad `systemd --user` que regenera el HTML cada 15 minutos. El script imprime el comando final (`systemctl --user enable --now ai-monitor.timer`) sin ejecutarlo — lo corres tú cuando quieras activarlo.

## Dashboard interactivo (opcional)

Además del HTML estático y la tabla en terminal, hay un dashboard web en vivo (React + Server-Sent Events), servido por `server.py` — sin frameworks del lado del backend, solo `http.server` de la librería estándar.

**Requiere Node.js/npm** (a diferencia del resto del proyecto, que solo necesita Python) para compilar el frontend.

```bash
# 1. Compilar el frontend una vez (o cada vez que cambie)
cd frontend
npm install
npm run build
cd ..

# 2. Correr el servidor
python3 server.py
# abre http://127.0.0.1:8420
```

El puerto es configurable con `AI_MONITOR_PORT` (default `8420`). El servidor recolecta datos de las 4 fuentes cada 60 segundos y los empuja al navegador vía SSE — no hace falta recargar la página.

**Como servicio de systemd**: `./install.sh` pregunta si quieres instalar también `ai-monitor-server.service` (servicio de larga duración, separado del `ai-monitor.timer` existente que solo regenera el HTML estático).

### Histórico más allá de la retención de cada proveedor

`server.py` (y también `main.py`, en cada ejecución) guarda un rollup diario por proyecto/modelo en `~/.local/share/ai-monitor/history.db` (SQLite). Si Claude Code, Codex u OpenCode eventualmente rotan o truncan sesiones viejas, ese histórico local no se pierde — el gráfico de tendencia del dashboard interactivo (`GET /api/history`) lee de ahí, no de los datos en vivo.

## Sobre el costo estimado

- Claude Code y Codex: costo **estimado** con una tabla de precios de lista por modelo (`collectors/pricing.py`). Si el modelo no está mapeado, el costo de esa sesión no se estima (no se usa un precio por defecto que podría ser incorrecto).
- Codex no expone un desglose de tokens por input/output/cache — solo un total `tokens_used` por hilo. Por eso el costo de Codex se estima tratando ese total como si fueran todos tokens de input; es una aproximación que puede sobre o subestimar el costo real según la mezcla real de tokens de cada sesión.
- OpenCode: usa el costo que **OpenCode ya calculó** para cada sesión — no se re-estima.
- OpenRouter: costo real reportado por su API.

Ninguno de estos números refleja lo que realmente pagas si usas un plan de suscripción (Pro/Max) en vez de facturación por API — son un proxy relativo para comparar qué tan pesado es un proyecto o tarea frente a otro.

**Nota sobre OpenCode + OpenRouter**: cuando OpenCode enruta un modelo a través de OpenRouter, ese consumo puede aparecer en ambas pestañas. La vista "Todo" combinada solo suma Claude Code + Codex + OpenCode (nunca OpenRouter) para evitar doble conteo.

## Arquitectura

```
main.py                # CLI: --json / --html / tabla por defecto
collectors/
  pricing.py            # tabla de precios compartida
  claude_code.py         # ~/.claude/projects/*.jsonl
  codex.py                # ~/.codex/state_5.sqlite
  opencode.py              # ~/.local/share/opencode/opencode.db
  openrouter.py             # API REST openrouter.ai
dashboard/
  template.py               # HTML con pestañas, self-contained
shell/aliases.sh              # alias portables (BASH_SOURCE-relativo)
install.sh                     # genera unidad systemd --user
```

Cada collector expone `collect(...)` con un parámetro opcional para inyectar la ruta/fuente en tests, y se degrada a `{}` (o `{"unavailable": True, "reason": ...}` en OpenRouter) si la plataforma no está instalada — nunca lanza una excepción que tumbe el resto del dashboard.

## Tests

```bash
python3 -m unittest discover -s tests -v
```
