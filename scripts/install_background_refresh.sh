#!/usr/bin/env bash
set -euo pipefail

# Programa background_refresh.py con launchd: lunes a viernes a las 09:00 y 16:00.
# Si el Mac duerme a esa hora, launchd lo ejecuta una vez al despertar.
# Uso: ./scripts/install_background_refresh.sh [--uninstall]

NEXUS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.nexus.background-refresh"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="$HOME/Library/Logs/NEXUS"
DOMAIN="gui/$(id -u)"

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true

if [[ "${1:-}" == "--uninstall" ]]; then
  rm -f "$PLIST"
  echo "Actualización programada desinstalada."
  exit 0
fi

PYTHON="$NEXUS_ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "ERROR: falta $PYTHON" >&2
  exit 1
fi

mkdir -p "$LOG_DIR" "$(dirname "$PLIST")"

intervals=""
for weekday in 1 2 3 4 5; do
  for hour in 9 16; do
    intervals+="
    <dict><key>Weekday</key><integer>${weekday}</integer><key>Hour</key><integer>${hour}</integer><key>Minute</key><integer>0</integer></dict>"
  done
done

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON}</string>
    <string>${NEXUS_ROOT}/background_refresh.py</string>
  </array>
  <key>WorkingDirectory</key><string>${NEXUS_ROOT}</string>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
  <key>StartCalendarInterval</key>
  <array>${intervals}
  </array>
  <key>ProcessType</key><string>Background</string>
  <key>LowPriorityIO</key><true/>
  <key>StandardOutPath</key><string>${LOG_DIR}/background-refresh.log</string>
  <key>StandardErrorPath</key><string>${LOG_DIR}/background-refresh.log</string>
</dict>
</plist>
PLIST

plutil -lint "$PLIST" >/dev/null
launchctl bootstrap "$DOMAIN" "$PLIST"
echo "Actualización programada instalada: L-V 09:00 y 16:00."
echo "Log: $LOG_DIR/background-refresh.log"
echo "Probar ahora: launchctl kickstart $DOMAIN/$LABEL"
