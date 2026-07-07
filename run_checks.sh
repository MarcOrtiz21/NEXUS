#!/usr/bin/env bash
set -euo pipefail

NEXUS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/nexus_env.sh
source "$NEXUS_ROOT/scripts/nexus_env.sh"

echo "========================================"
echo " NEXUS - Checks y Validaciones"
echo "========================================"
echo

python_cmd="$(nexus_prepare_python "yfinance, pandas, numpy, requests, rich, feedparser")"

echo "[1/3] Ejecutando tests ..."
if ! "$python_cmd" -m unittest discover -v; then
    echo "[ERROR] Fallaron tests."
    exit 1
fi

echo
echo "[2/3] Smoke test CLI (una carga compacta sin RSS) ..."
if ! "$python_cmd" "$NEXUS_ROOT/main_cli.py" --once --compact --no-news --no-clear --max-alerts 3; then
    echo "[ERROR] Fallo en smoke test de CLI."
    exit 1
fi

echo
echo "[3/3] Backtest rapido ..."
if ! "$python_cmd" "$NEXUS_ROOT/backtest.py" --period 2y --rebalance-days 10; then
    echo "[ERROR] Fallo en backtest."
    exit 1
fi

echo
echo "Checks completados correctamente."
