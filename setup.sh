#!/usr/bin/env bash
set -euo pipefail

NEXUS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/nexus_env.sh
source "$NEXUS_ROOT/scripts/nexus_env.sh"

echo "========================================"
echo " NEXUS - Configuracion inicial (macOS)"
echo "========================================"
echo

python_cmd="$(nexus_prepare_python "yfinance, pandas, numpy, requests, rich, feedparser")"

echo
echo "Comprobando tkinter (requerido para la app de escritorio) ..."
if ! nexus_check_imports "$python_cmd" tkinter >/dev/null 2>&1; then
    echo "[WARN] tkinter no esta disponible."
    echo "En macOS con Homebrew suele resolverse con: brew install python-tk@3.14"
    echo "La CLI seguira funcionando; el modo desktop puede fallar hasta instalar tkinter."
else
    echo "tkinter OK."
fi

echo
echo "Entorno listo. Puedes usar:"
echo "  ./run_nexus.sh       -> desktop con fallback a CLI"
echo "  ./run_program.sh     -> solo desktop"
echo "  ./run_terminal.sh    -> solo CLI"
echo "  ./run_history.sh     -> historial de decisiones"
echo "  ./run_paper.sh       -> paper trading / P&L virtual"
echo "  ./run_dashboard.sh   -> dashboard web local"
echo "  ./run_checks.sh      -> tests y validaciones"
echo "  ./scripts/build_mac_app.sh -> empaquetar .app de macOS"
