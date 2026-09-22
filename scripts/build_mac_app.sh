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
VERSION="3.10.0"

echo "Construyendo ${APP_NAME} v${VERSION}"
echo "  Fuente: $NEXUS_ROOT"

rm -rf "$APP_DIR"
mkdir -p "$MACOS" "$RESOURCES"

printf '%s\n' "$NEXUS_ROOT" > "$RESOURCES/nexus_root.txt"
for locale_dir in "$NEXUS_ROOT"/native/Sources/NEXUS/Resources/*.lproj; do
  [[ -d "$locale_dir" ]] && cp -R "$locale_dir" "$RESOURCES/"
done

if ! command -v swift >/dev/null 2>&1; then
  echo "ERROR: Swift no está disponible. Instala Command Line Tools: xcode-select --install" >&2
  exit 1
fi

# Algunas versiones recientes de Command Line Tools incluyen un SDK preliminar
# sin el plugin SwiftUIMacros. Cuando está disponible, 26.5 es la base estable
# compatible con el despliegue mínimo de NEXUS. Se puede anular con SDKROOT.
if [[ -z "${SDKROOT:-}" && -d "/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk" ]]; then
  export SDKROOT="/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk"
  echo "  SDK estable: $SDKROOT"
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
  <key>CFBundleExecutable</key><string>NEXUS</string>${ICON_PLIST_KEY}
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSUserNotificationsUsageDescription</key>
  <string>NEXUS avisa cuando cambia la acción operativa o se activa un bloqueo de calendario.</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSSupportsAutomaticGraphicsSwitching</key><true/>
</dict>
</plist>
PLIST

if command -v xattr >/dev/null 2>&1; then
  xattr -cr "$APP_DIR" 2>/dev/null || true
fi

# Firma local ad hoc: evita que macOS trate el bundle como un ejecutable sin
# identidad. No sustituye una firma Developer ID para distribuirlo fuera del
# equipo, pero estabiliza LaunchServices y las APIs de accesibilidad locales.
if [[ "$(uname -s)" == "Darwin" ]] && command -v codesign >/dev/null 2>&1; then
  codesign --force --deep --sign - "$APP_DIR"
  echo "  Firma local: ad hoc"
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
