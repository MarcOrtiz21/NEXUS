#!/usr/bin/env bash
set -euo pipefail
trap 'nexus_pause_if_interactive' EXIT

NEXUS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/nexus_env.sh
source "$NEXUS_ROOT/scripts/nexus_env.sh"

echo "========================================"
echo " NEXUS Workstation (Desktop App)"
echo "========================================"
echo

python_cmd="$(nexus_prepare_python "customtkinter, PIL, tkinter, yfinance, pandas, numpy, requests, feedparser, Quartz")"

echo
echo "Iniciando programa local NEXUS ..."
echo
"$python_cmd" "$NEXUS_ROOT/nexus_desktop.py"
