#!/bin/zsh
set -euo pipefail

# Doble clic estable: la aplicación empaquetada gestiona por sí sola el motor,
# su ciclo de vida y la ruta del entorno Python. Evita compilar con el SDK más
# reciente de macOS y evita levantar una segunda API en el mismo puerto.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSTALLED_APP="/Applications/NEXUS Workstation.app"
LOCAL_APP="$ROOT/dist/NEXUS Workstation.app"

if [[ -d "$INSTALLED_APP" ]]; then
  echo "Abriendo NEXUS Workstation desde Aplicaciones…"
  open "$INSTALLED_APP"
  exit 0
fi

if [[ ! -d "$LOCAL_APP" ]]; then
  echo "NEXUS aún no está empaquetado. Construyendo la aplicación…"
  "$ROOT/scripts/build_mac_app.sh"
fi

echo "Abriendo NEXUS Workstation…"
open "$LOCAL_APP"
