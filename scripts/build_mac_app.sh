#!/usr/bin/env bash
set -euo pipefail

# NEXUS_ROOT es el directorio padre de scripts/
NEXUS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="NEXUS Workstation"
APP_DIR="$NEXUS_ROOT/dist/${APP_NAME}.app"
CONTENTS="$APP_DIR/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"

echo "Construyendo ${APP_NAME} desde: $NEXUS_ROOT"

rm -rf "$APP_DIR"
mkdir -p "$MACOS" "$RESOURCES"

# Script de lanzamiento — usa variables expandidas en tiempo de build
cat > "$MACOS/launch_nexus" <<LAUNCHER
#!/usr/bin/env bash
cd "${NEXUS_ROOT}"
exec "${NEXUS_ROOT}/run_program.command"
LAUNCHER
chmod +x "$MACOS/launch_nexus"

cat > "$CONTENTS/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>${APP_NAME}</string>
  <key>CFBundleDisplayName</key><string>${APP_NAME}</string>
  <key>CFBundleIdentifier</key><string>com.nexus.workstation</string>
  <key>CFBundleVersion</key><string>1.2</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>launch_nexus</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

echo "✅ App creada en: $APP_DIR"
echo "   Abre con: open \"$APP_DIR\""
