#!/usr/bin/env bash
set -euo pipefail

# Empaqueta NEXUS Workstation como .app macOS nativa SwiftUI.
# El binario SwiftUI se incluye en la app y arranca el motor Python del repo.

NEXUS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="NEXUS Workstation"
DIST_DIR="$NEXUS_ROOT/dist"
APP_DIR="$DIST_DIR/${APP_NAME}.app"
CONTENTS="$APP_DIR/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"
ICON_SRC="$NEXUS_ROOT/assets/AppIcon.png"
VERSION="2.0.0"

echo "Construyendo ${APP_NAME} v${VERSION}"
echo "  Fuente: $NEXUS_ROOT"

rm -rf "$APP_DIR"
mkdir -p "$MACOS" "$RESOURCES"

printf '%s\n' "$NEXUS_ROOT" > "$RESOURCES/nexus_root.txt"

if ! command -v swift >/dev/null 2>&1; then
  echo "ERROR: Swift no está disponible. Instala Command Line Tools: xcode-select --install" >&2
  exit 1
fi

echo "  Compilando interfaz SwiftUI (release)…"
(
  cd "$NEXUS_ROOT/native"
  swift build -c release
  NATIVE_BIN="$(swift build -c release --show-bin-path)/NEXUS"
  [[ -x "$NATIVE_BIN" ]] || { echo "ERROR: no se generó binario SwiftUI" >&2; exit 1; }
  cp "$NATIVE_BIN" "$MACOS/NEXUS"
)
chmod +x "$MACOS/NEXUS"

cat > "$MACOS/launch_nexus" <<'LAUNCHER'
#!/bin/bash
set -euo pipefail

# PATH mínimo de Finder no incluye Homebrew.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

APP_CONTENTS="$(cd "$(dirname "$0")/.." && pwd)"
RESOURCES="$APP_CONTENTS/Resources"
ROOT_FILE="$RESOURCES/nexus_root.txt"
LOG_DIR="${HOME}/Library/Logs/NEXUS"
LOG_FILE="${LOG_DIR}/launch.log"
mkdir -p "$LOG_DIR"

exec >>"$LOG_FILE" 2>&1
echo "----- $(date '+%Y-%m-%d %H:%M:%S') launch -----"

die() {
  local msg="$1"
  echo "ERROR: $msg"
  if command -v osascript >/dev/null 2>&1; then
    osascript -e "display dialog \"${msg}\" with title \"NEXUS Workstation\" buttons {\"OK\"} default button 1 with icon stop" >/dev/null 2>&1 || true
  fi
  exit 1
}

[[ -f "$ROOT_FILE" ]] || die "No se encontró nexus_root.txt. Vuelve a ejecutar scripts/build_mac_app.sh"
NEXUS_ROOT="$(tr -d '\r\n' < "$ROOT_FILE")"
[[ -d "$NEXUS_ROOT" ]] || die "La carpeta del proyecto no existe: ${NEXUS_ROOT}. Reconstruye la app."

export NEXUS_ROOT
export NEXUS_NO_PAUSE=1

NATIVE_BIN="$APP_CONTENTS/MacOS/NEXUS"
[[ -x "$NATIVE_BIN" ]] || die "No se encuentra el binario nativo. Vuelve a ejecutar scripts/build_mac_app.sh"
[[ -x "${NEXUS_ROOT}/.venv/bin/python" ]] || die "No hay entorno .venv. Ejecuta setup.command en el repo."

echo "Starting native SwiftUI: $NATIVE_BIN"
exec "$NATIVE_BIN"
LAUNCHER
chmod +x "$MACOS/launch_nexus"

ICON_PLIST_KEY=""
if [[ -f "$ICON_SRC" ]]; then
  cp "$ICON_SRC" "$RESOURCES/AppIcon.png"
  if [[ "$(uname -s)" == "Darwin" ]] && command -v sips >/dev/null 2>&1 && command -v iconutil >/dev/null 2>&1; then
    ICONSET="$RESOURCES/AppIcon.iconset"
    rm -rf "$ICONSET"
    mkdir -p "$ICONSET"
    sips -z 16 16     "$ICON_SRC" --out "$ICONSET/icon_16x16.png" >/dev/null
    sips -z 32 32     "$ICON_SRC" --out "$ICONSET/icon_16x16@2x.png" >/dev/null
    sips -z 32 32     "$ICON_SRC" --out "$ICONSET/icon_32x32.png" >/dev/null
    sips -z 64 64     "$ICON_SRC" --out "$ICONSET/icon_32x32@2x.png" >/dev/null
    sips -z 128 128   "$ICON_SRC" --out "$ICONSET/icon_128x128.png" >/dev/null
    sips -z 256 256   "$ICON_SRC" --out "$ICONSET/icon_128x128@2x.png" >/dev/null
    sips -z 256 256   "$ICON_SRC" --out "$ICONSET/icon_256x256.png" >/dev/null
    sips -z 512 512   "$ICON_SRC" --out "$ICONSET/icon_256x256@2x.png" >/dev/null
    sips -z 512 512   "$ICON_SRC" --out "$ICONSET/icon_512x512.png" >/dev/null
    sips -z 1024 1024 "$ICON_SRC" --out "$ICONSET/icon_512x512@2x.png" >/dev/null
    iconutil -c icns "$ICONSET" -o "$RESOURCES/AppIcon.icns"
    rm -rf "$ICONSET"
    ICON_PLIST_KEY=$'\n  <key>CFBundleIconFile</key><string>AppIcon</string>'
    echo "  Icono: Resources/AppIcon.icns"
  else
    echo "  Aviso: sips/iconutil no disponibles; se incluye AppIcon.png (el .icns se genera en macOS)."
  fi
fi

cat > "$CONTENTS/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>${APP_NAME}</string>
  <key>CFBundleDisplayName</key><string>${APP_NAME}</string>
  <key>CFBundleIdentifier</key><string>com.nexus.workstation</string>
  <key>CFBundleVersion</key><string>${VERSION}</string>
  <key>CFBundleShortVersionString</key><string>${VERSION}</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>launch_nexus</string>${ICON_PLIST_KEY}
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSSupportsAutomaticGraphicsSwitching</key><true/>
</dict>
</plist>
PLIST

if command -v xattr >/dev/null 2>&1; then
  xattr -cr "$APP_DIR" 2>/dev/null || true
fi

echo
echo "✅ App creada en:"
echo "   $APP_DIR"
echo
echo "Abrir ahora:"
echo "   open \"$APP_DIR\""
echo
echo "Instalar en Applications:"
echo "   ./scripts/install_mac_app.sh"
echo "   # o doble clic: install_mac_app.command"
