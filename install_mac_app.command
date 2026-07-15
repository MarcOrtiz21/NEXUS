#!/usr/bin/env bash
# Doble clic en Finder: construye e instala NEXUS en Applications.
set -euo pipefail
trap 'echo; read -r -p "Pulsa Enter para cerrar..." _' EXIT

NEXUS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$NEXUS_ROOT/scripts/install_mac_app.sh"
