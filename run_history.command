#!/usr/bin/env bash
set -euo pipefail
trap 'nexus_pause_if_interactive' EXIT

NEXUS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$NEXUS_ROOT/scripts/nexus_env.sh"

python_cmd="$(nexus_prepare_python "yfinance, pandas, numpy, requests, rich, feedparser")"
"$python_cmd" "$NEXUS_ROOT/history_cli.py" "$@"
