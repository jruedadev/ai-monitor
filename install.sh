#!/usr/bin/env bash
# Instala ai-monitor como servicios systemd --user con la ruta real del repo,
# sin hardcodear ninguna ruta de usuario en el código versionado: genera las
# unidades, compila el frontend si hace falta y activa timers y servidor.
#
#   ./install.sh                 pregunta si instalar el servidor; activa todo
#   ./install.sh -y|--yes        instala y activa también el servidor, sin preguntar
#   ./install.sh --sin-activar   solo genera las unidades; no toca systemctl
set -euo pipefail

ASSUME_YES=0
ACTIVATE=1
for arg in "$@"; do
  case "$arg" in
    -y|--yes) ASSUME_YES=1 ;;
    --sin-activar) ACTIVATE=0 ;;
    -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Opción desconocida: $arg (usa --help)" >&2; exit 2 ;;
  esac
done
INSTALL_SERVER=0

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="$(command -v python3)"
UNITS_DIR="$HOME/.config/systemd/user"
ENV_DIR="$HOME/.config/ai-monitor"
ENV_FILE="$ENV_DIR/env"
# PATH para Environment="PATH=..." de las unidades: se escapan \ y " (va entre
# comillas, así un directorio con espacios no corta la asignación) y % (systemd
# lo lee como especificador). Luego se escapa para el reemplazo de sed (\ & #).
UNIT_PATH="${PATH//\\/\\\\}"
UNIT_PATH="${UNIT_PATH//\"/\\\"}"
UNIT_PATH="${UNIT_PATH//%/%%}"
UNIT_PATH="$(printf '%s' "$UNIT_PATH" | sed -e 's/[\\&#]/\\&/g')"

mkdir -p "$UNITS_DIR" "$ENV_DIR"

sed \
  -e "s#__REPO_DIR__#${REPO_DIR}#g" \
  -e "s#__PYTHON__#${PYTHON_BIN}#g" \
  -e "s#__ENV_FILE__#${ENV_FILE}#g" \
  -e "s#__PATH__#${UNIT_PATH}#g" \
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
if [ "$ASSUME_YES" -eq 1 ]; then
  REPLY=y
else
  read -r -p "¿Instalar también el servicio del dashboard interactivo (server.py)? [y/N] " REPLY || REPLY=""
fi
if [[ "$REPLY" =~ ^[Yy]$ ]]; then
  INSTALL_SERVER=1
  # Compila si no hay dist o si el código fuente es más nuevo que el build
  # (p. ej. tras actualizar el repo con una vista nueva).
  DIST_INDEX="$REPO_DIR/frontend/dist/index.html"
  if [ ! -f "$DIST_INDEX" ] || [ -n "$(find "$REPO_DIR/frontend/src" "$REPO_DIR/frontend/package.json" -newer "$DIST_INDEX" -print -quit 2>/dev/null)" ]; then
    if command -v npm >/dev/null 2>&1; then
      echo ""
      echo "Frontend sin compilar o desactualizado — compilando $REPO_DIR/frontend/dist..."
      if (cd "$REPO_DIR/frontend" && { [ -d node_modules ] || npm install --legacy-peer-deps; } && npm run build); then
        echo "Frontend compilado en $REPO_DIR/frontend/dist"
      else
        echo ""
        echo "ADVERTENCIA: falló la compilación automática del frontend."
        echo "El servicio no arrancará hasta que compiles a mano:"
        echo "  cd $REPO_DIR/frontend && npm install --legacy-peer-deps && npm run build"
        echo ""
      fi
    else
      echo ""
      echo "ADVERTENCIA: no se encontró $REPO_DIR/frontend/dist y no hay npm instalado."
      echo "El frontend no está compilado. Antes de activar el servicio, instala Node/npm y corre:"
      echo "  cd $REPO_DIR/frontend && npm install --legacy-peer-deps && npm run build"
      echo ""
    fi
  fi

  sed \
    -e "s#__REPO_DIR__#${REPO_DIR}#g" \
    -e "s#__PYTHON__#${PYTHON_BIN}#g" \
    -e "s#__ENV_FILE__#${ENV_FILE}#g" \
    -e "s#__PATH__#${UNIT_PATH}#g" \
    "$REPO_DIR/systemd/ai-monitor-server.service.template" > "$UNITS_DIR/ai-monitor-server.service"

  echo "Unidad ai-monitor-server.service instalada en $UNITS_DIR"
fi

sed \
  -e "s#__REPO_DIR__#${REPO_DIR}#g" \
  -e "s#__PYTHON__#${PYTHON_BIN}#g" \
  -e "s#__ENV_FILE__#${ENV_FILE}#g" \
  -e "s#__PATH__#${UNIT_PATH}#g" \
  "$REPO_DIR/systemd/ai-monitor-recommend.service.template" > "$UNITS_DIR/ai-monitor-recommend.service"

cp "$REPO_DIR/systemd/ai-monitor-recommend.timer" "$UNITS_DIR/ai-monitor-recommend.timer"

echo "Unidades instaladas en $UNITS_DIR"

UNITS=(ai-monitor.timer ai-monitor-recommend.timer)
[ "$INSTALL_SERVER" -eq 1 ] && UNITS+=(ai-monitor-server.service)

if [ "$ACTIVATE" -eq 1 ] && command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload
  systemctl --user enable --now "${UNITS[@]}"
  # Si el servidor ya corría, que cargue el código y la unidad nuevos.
  if [ "$INSTALL_SERVER" -eq 1 ]; then
    systemctl --user restart ai-monitor-server.service
  fi
  echo "Activado: ${UNITS[*]}"
  [ "$INSTALL_SERVER" -eq 1 ] && echo "Dashboard: http://localhost:${AI_MONITOR_PORT:-8420}"
else
  echo ""
  echo "Para activarlas, corre:"
  echo "  systemctl --user daemon-reload"
  echo "  systemctl --user enable --now ${UNITS[*]}"
fi
