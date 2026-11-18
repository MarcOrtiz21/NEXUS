#!/usr/bin/env bash
set -euo pipefail
NEXUS_TEST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NEXUS_TEST_SDK="${SDKROOT:-}"
if [[ ! -d "$NEXUS_TEST_SDK" ]]; then
  NEXUS_TEST_SDK="$(xcrun --sdk macosx --show-sdk-path)" || NEXUS_TEST_SDK=""
fi
if [[ ! -d "$NEXUS_TEST_SDK" ]]; then
  echo "ERROR: no se encuentra un SDK de macOS. Selecciona Xcode/CLT o indica SDKROOT." >&2
  exit 1
fi
# El shim de swiftc también consulta SDKROOT al resolver el toolchain.
export SDKROOT="$NEXUS_TEST_SDK"
NEXUS_TEST_DIR="$(mktemp -d -t nexus-presentation)"
trap 'rm -f -- "$NEXUS_TEST_DIR/checks"; rmdir -- "$NEXUS_TEST_DIR"' EXIT
NEXUS_TEST_SOURCES="$NEXUS_TEST_ROOT/native/Sources/NEXUS"
echo "SDK de las pruebas nativas: $NEXUS_TEST_SDK"
swiftc -parse-as-library -O -sdk "$NEXUS_TEST_SDK" \
  "$NEXUS_TEST_SOURCES/Models.swift" \
  "$NEXUS_TEST_SOURCES/APIClient.swift" \
  "$NEXUS_TEST_SOURCES/ChartDataStore.swift" \
  "$NEXUS_TEST_SOURCES/PresentationPolicy.swift" \
  "$NEXUS_TEST_SOURCES/Theme.swift" \
  "$NEXUS_TEST_SOURCES/Localization.swift" \
  "$NEXUS_TEST_SOURCES/LiquidGlass.swift" \
  "$NEXUS_TEST_ROOT/native/Tests/NativeSnapshotContractChecks.swift" \
  "$NEXUS_TEST_ROOT/native/Tests/PresentationChecks.swift" \
  -o "$NEXUS_TEST_DIR/checks"
"$NEXUS_TEST_DIR/checks" "$NEXUS_TEST_ROOT/tests/fixtures/native_snapshot.json"
