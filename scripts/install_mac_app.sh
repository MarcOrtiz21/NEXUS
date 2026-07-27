#!/usr/bin/env bash
set -euo pipefail

# Construye NEXUS Workstation.app e instala una copia en /Applications.

NEXUS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="NEXUS Workstation"
SRC_APP="$NEXUS_ROOT/dist/${APP_NAME}.app"
DEST_APP="/Applications/${APP_NAME}.app"

echo "========================================"
echo " Instalar ${APP_NAME} en Applications"
echo "========================================"
echo

"$NEXUS_ROOT/scripts/build_mac_app.sh"

if [[ ! -d "$SRC_APP" ]]; then
  echo "ERROR: no se generó $SRC_APP" >&2
  exit 1
fi

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Aviso: este entorno no es macOS. La app quedó en dist/."
  echo "En tu Mac ejecuta: ./scripts/install_mac_app.sh"
  exit 0
fi

echo "Copiando a $DEST_APP ..."
rm -rf "$DEST_APP"
cp -R "$SRC_APP" "$DEST_APP"

# Actualiza la ruta del proyecto embebida (por si dist/ y Applications divergen).
printf '%s\n' "$NEXUS_ROOT" > "$DEST_APP/Contents/Resources/nexus_root.txt"

if command -v xattr >/dev/null 2>&1; then
  xattr -cr "$DEST_APP" 2>/dev/null || true
fi

echo
echo "✅ Instalada en Applications."
echo "   Abre con Spotlight o:"
echo "   open \"$DEST_APP\""
echo
echo "Nota: la app lanza el código de este repo ($NEXUS_ROOT)."
echo "Si mueves el proyecto, vuelve a ejecutar este instalador."
