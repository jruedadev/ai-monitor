# shell/aliases.sh
# Alias portables para ai-monitor. Agregar a ~/.bashrc:
#   source "/ruta/donde/clonaste/ai-monitor/shell/aliases.sh"

_AI_MONITOR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

claude-usage() {
    python3 "$_AI_MONITOR_DIR/main.py" --html "$HOME/claude-usage.html" \
        && xdg-open "$HOME/claude-usage.html" >/dev/null 2>&1 &
}

alias claude-usage-table="python3 \"$_AI_MONITOR_DIR/main.py\""
