# ai-monitor

Dashboard local de uso de IA: agrega tokens y costo por proyecto a partir de los datos que **Claude Code**, **Codex** y **OpenCode** guardan localmente, más el consumo reportado por **OpenRouter** vía su API. Sin dependencias externas — solo librería estándar de Python.

## Fuentes soportadas

| Fuente | De dónde lee | Agrupa por |
|---|---|---|
| Claude Code | `~/.claude/projects/*/*.jsonl` | proyecto (cwd real) |
| Codex | `~/.codex/state_5.sqlite` | proyecto (cwd) |
| OpenCode | `~/.local/share/opencode/opencode.db` | proyecto (directory) |
| OpenRouter | API `openrouter.ai/api/v1/activity` (requiere `OPENROUTER_API_KEY`) | modelo |

Cada fuente que no esté instalada, o cuya key no esté configurada, se omite con un aviso — el resto del dashboard sigue funcionando.

## Uso

```bash
python3 main.py                     # tabla combinada en terminal (Claude+Codex+OpenCode)
python3 main.py --json              # todas las fuentes crudas + vista combinada, en JSON
python3 main.py --html out.html     # dashboard HTML con pestañas por fuente
```

## OpenRouter

Genera una API key en https://openrouter.ai/keys y expórtala:

```bash
export OPENROUTER_API_KEY="sk-or-..."
```

Sin esta variable, la pestaña de OpenRouter muestra un aviso en vez de datos; el resto del dashboard no se ve afectado.

## Instalación (alias + actualización automática)

1. Clona el repo donde prefieras.
2. Agrega una línea a tu `~/.bashrc` (o `~/.zshrc`) apuntando a donde lo clonaste:

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

## Sobre el costo estimado

- Claude Code y Codex: costo **estimado** con una tabla de precios de lista por modelo (`collectors/pricing.py`). Si el modelo no está mapeado, el costo de esa sesión no se estima (no se usa un precio por defecto que podría ser incorrecto).
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
