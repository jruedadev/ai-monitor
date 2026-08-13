#!/usr/bin/env bash
# Genera la unidad systemd --user de ai-monitor con la ruta real del repo,
# sin hardcodear ninguna ruta de usuario en el código versionado.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="$(command -v python3)"
UNITS_DIR="$HOME/.config/systemd/user"
ENV_DIR="$HOME/.config/ai-monitor"
ENV_FILE="$ENV_DIR/env"

mkdir -p "$UNITS_DIR" "$ENV_DIR"

sed \
  -e "s#__REPO_DIR__#${REPO_DIR}#g" \
  -e "s#__PYTHON__#${PYTHON_BIN}#g" \
  -e "s#__ENV_FILE__#${ENV_FILE}#g" \
  "$REPO_DIR/systemd/ai-monitor.service.template" > "$UNITS_DIR/ai-monitor.service"

cp "$REPO_DIR/systemd/ai-monitor.timer" "$UNITS_DIR/ai-monitor.timer"

# Archivo de entorno con la key de OpenRouter (management key), con permisos
# restringidos. systemd lo lee vía EnvironmentFile y el collector como fallback.
umask 077
if [ -n "${OPENROUTER_API_KEY:-}" ]; then
  printf 'OPENROUTER_API_KEY=%s\n' "$OPENROUTER_API_KEY" > "$ENV_FILE"
else
  : > "$ENV_FILE"
fi
chmod 600 "$ENV_FILE"

echo ""
read -r -p "¿Instalar también el servicio del dashboard interactivo (server.py)? [y/N] " REPLY
if [[ "$REPLY" =~ ^[Yy]$ ]]; then
  if [ ! -d "$REPO_DIR/frontend/dist" ]; then
    echo ""
    echo "ADVERTENCIA: no se encontró $REPO_DIR/frontend/dist"
    echo "El frontend no está compilado. Antes de activar el servicio, corre:"
    echo "  cd $REPO_DIR/frontend && npm install && npm run build"
    echo ""
  fi

  sed \
    -e "s#__REPO_DIR__#${REPO_DIR}#g" \
    -e "s#__PYTHON__#${PYTHON_BIN}#g" \
    -e "s#__ENV_FILE__#${ENV_FILE}#g" \
    "$REPO_DIR/systemd/ai-monitor-server.service.template" > "$UNITS_DIR/ai-monitor-server.service"

  echo "Unidad ai-monitor-server.service instalada en $UNITS_DIR"
  echo "Para activarla:"
  echo "  systemctl --user daemon-reload"
  echo "  systemctl --user enable --now ai-monitor-server.service"
fi

echo "Unidades instaladas en $UNITS_DIR"
echo ""
echo "Para activarlas, corre:"
echo "  systemctl --user daemon-reload"
echo "  systemctl --user enable --now ai-monitor.timer"
