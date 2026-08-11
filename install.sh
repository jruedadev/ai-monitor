#!/usr/bin/env bash
# Genera la unidad systemd --user de ai-monitor con la ruta real del repo,
# sin hardcodear ninguna ruta de usuario en el código versionado.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="$(command -v python3)"
UNITS_DIR="$HOME/.config/systemd/user"

mkdir -p "$UNITS_DIR"

sed \
  -e "s#__REPO_DIR__#${REPO_DIR}#g" \
  -e "s#__PYTHON__#${PYTHON_BIN}#g" \
  "$REPO_DIR/systemd/ai-monitor.service.template" > "$UNITS_DIR/ai-monitor.service"

cp "$REPO_DIR/systemd/ai-monitor.timer" "$UNITS_DIR/ai-monitor.timer"

echo "Unidades instaladas en $UNITS_DIR"
echo ""
echo "Para activarlas, corre:"
echo "  systemctl --user daemon-reload"
echo "  systemctl --user enable --now ai-monitor.timer"
