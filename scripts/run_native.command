#!/bin/zsh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Arranca API si no responde
if ! curl -sf "http://127.0.0.1:8765/api/health" >/dev/null 2>&1; then
  echo "Arrancando motor NEXUS (FastAPI :8765)…"
  # shellcheck disable=SC1091
  source "$ROOT/scripts/nexus_env.sh" 2>/dev/null || true
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    "$ROOT/.venv/bin/python" -m uvicorn web_dashboard:app --host 127.0.0.1 --port 8765 &
  else
    python3 -m uvicorn web_dashboard:app --host 127.0.0.1 --port 8765 &
  fi
  API_PID=$!
  for _ in {1..40}; do
    if curl -sf "http://127.0.0.1:8765/api/health" >/dev/null 2>&1; then
      break
    fi
    sleep 0.25
  done
else
  API_PID=""
  echo "Motor ya activo en :8765"
fi

cd "$ROOT/native"
echo "Compilando NEXUS Native (SwiftUI)…"
swift build -c release
BIN="$(swift build -c release --show-bin-path)/NEXUS"
echo "Lanzando $BIN"
"$BIN"
STATUS=$?

if [[ -n "${API_PID}" ]]; then
  kill "$API_PID" 2>/dev/null || true
fi
exit "$STATUS"
