#!/usr/bin/env bash
set -euo pipefail

NEXUS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/nexus_env.sh
source "$NEXUS_ROOT/scripts/nexus_env.sh"

echo "========================================"
echo " NEXUS - Terminal Macroeconomico"
echo "========================================"
echo

if [[ ! -f "$NEXUS_ROOT/main_cli.py" ]]; then
    echo "[ERROR] No se encontro main_cli.py en:"
    echo "$NEXUS_ROOT"
    exit 1
fi

python_cmd="$(nexus_prepare_python "yfinance, pandas, numpy, requests, rich, feedparser")"

echo
echo "Iniciando NEXUS Desktop ..."
if ! "$python_cmd" "$NEXUS_ROOT/nexus_desktop.py"; then
    echo
    echo "[WARN] Fallo en modo desktop. Reintentando en CLI sin RSS ..."
    if ! "$python_cmd" "$NEXUS_ROOT/main_cli.py" --no-news; then
        echo
        echo "[WARN] Segundo fallback: carga unica compacta sin RSS ..."
        if ! "$python_cmd" "$NEXUS_ROOT/main_cli.py" --once --no-news --compact; then
            echo
            echo "[ERROR] NEXUS no pudo arrancar en ninguno de los modos de fallback."
            exit 1
        fi
    fi
fi
