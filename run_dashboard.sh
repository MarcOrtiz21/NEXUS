#!/usr/bin/env bash
set -euo pipefail

NEXUS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$NEXUS_ROOT/scripts/nexus_env.sh"

python_cmd="$(nexus_prepare_python "yfinance, pandas, numpy, requests, rich, feedparser, fastapi, uvicorn")"

echo "========================================"
echo " NEXUS - Dashboard Web Local"
echo "========================================"
echo
echo "Abriendo dashboard en http://127.0.0.1:8765"
echo "Ctrl+C para detener."
echo

exec "$python_cmd" "$NEXUS_ROOT/web_dashboard.py"
