# ai-monitor

Script en Python para analizar el uso local de **Claude Code** por proyecto: tokens consumidos, costo estimado y las tareas/sesiones más pesadas. Lee directamente los transcripts que Claude Code guarda en `~/.claude/projects/*/*.jsonl`, sin depender de ninguna API externa.

## Requisitos

- Python 3.8+ (sin dependencias externas, solo librería estándar)
- Haber usado Claude Code al menos una vez en la máquina (para que existan transcripts en `~/.claude/projects/`)

## Uso

```bash
# Resumen en tabla dentro de la terminal
python3 claude_usage.py

# Volcar el agregado completo en JSON (útil para integrarlo con otras herramientas)
python3 claude_usage.py --json

# Generar un dashboard HTML autocontenido
python3 claude_usage.py --html dashboard.html
```

El dashboard HTML no tiene dependencias externas (sin CDN, sin conexión a internet) y se adapta automáticamente a tema claro/oscuro según las preferencias del sistema.

### Alias recomendados

Agrega esto a tu `~/.bashrc` (o `~/.zshrc`) para tener acceso rápido:

```bash
claude-usage() {
    python3 ~/DEV/JRDV/ai-monitor/claude_usage.py --html ~/claude-usage.html && xdg-open ~/claude-usage.html >/dev/null 2>&1 &
}
alias claude-usage-table='python3 ~/DEV/JRDV/ai-monitor/claude_usage.py'
```

Luego recarga la shell (`source ~/.bashrc`) y usa:

- `claude-usage` → regenera el dashboard HTML y lo abre en el navegador.
- `claude-usage-table` → imprime el resumen directamente en la terminal.

## Qué muestra

- **Por proyecto**: tokens de entrada/salida/caché, costo estimado, cantidad de mensajes y de sesiones — agrupado por el directorio de trabajo real (`cwd`) capturado en cada sesión, no por el nombre de carpeta codificado que usa Claude Code internamente.
- **Tareas/sesiones más pesadas**: ranking por tokens consumidos, con el título real de la sesión (cuando Claude Code lo generó) para identificar rápido qué tarea disparó más consumo.
- **Totales globales**: tokens y costo estimado sumado de todos los proyectos.

## Sobre el costo estimado

El costo se calcula con precios de lista de la API pública de Anthropic por modelo (`claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5`, `claude-fable-5`), usando los tokens de entrada, salida, lectura de caché y escritura de caché reportados en cada mensaje.

**Importante**: si usas un plan de suscripción (Pro/Max) en lugar de facturación por API, el costo real que pagas no es este — es un proxy relativo útil para comparar qué tan "pesado" es un proyecto o una tarea frente a otro, no una factura real.

## Cómo funciona

Claude Code guarda un archivo `.jsonl` por sesión dentro de `~/.claude/projects/<carpeta-codificada>/`. Cada línea es un evento; el script filtra los mensajes de tipo `assistant` que traen un bloque `usage` con el conteo de tokens, y los agrupa por el `cwd` real de la sesión (más legible que el nombre de carpeta codificado, que reemplaza `/` por `-`).
