#!/usr/bin/env bash
set -euo pipefail
NEXUS_TEST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NEXUS_TEST_DIR="$(mktemp -d -t nexus-presentation)"
NEXUS_TEST_SDK="${SDKROOT:-/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk}"
NEXUS_TEST_SOURCES="$NEXUS_TEST_ROOT/native/Sources/NEXUS"
swiftc -parse-as-library -O -sdk "$NEXUS_TEST_SDK" \
  "$NEXUS_TEST_SOURCES/Models.swift" \
  "$NEXUS_TEST_SOURCES/APIClient.swift" \
  "$NEXUS_TEST_SOURCES/ChartDataStore.swift" \
  "$NEXUS_TEST_SOURCES/PresentationPolicy.swift" \
  "$NEXUS_TEST_SOURCES/Theme.swift" \
  "$NEXUS_TEST_SOURCES/Localization.swift" \
  "$NEXUS_TEST_SOURCES/LiquidGlass.swift" \
  "$NEXUS_TEST_ROOT/native/Tests/PresentationChecks.swift" \
  -o "$NEXUS_TEST_DIR/checks"
"$NEXUS_TEST_DIR/checks"
