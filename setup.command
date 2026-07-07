#!/usr/bin/env bash
set -euo pipefail
trap 'nexus_pause_if_interactive' EXIT

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
echo "Entorno listo. En Finder puedes abrir con doble clic:"
echo "  run_nexus.command     -> desktop con fallback a CLI"
echo "  run_program.command   -> solo panel de escritorio"
echo "  run_terminal.command  -> solo terminal CLI"
echo "  run_history.command   -> historial de decisiones"
echo "  run_paper.command     -> paper trading / P&L virtual"
echo "  run_dashboard.command -> dashboard web local"
echo "  run_checks.command    -> tests y validaciones"
