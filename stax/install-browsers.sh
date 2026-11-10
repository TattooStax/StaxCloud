#!/usr/bin/env bash
# Install the agent's two browser engines into <openfang home>/bin, where the
# daemon looks for them (see BrowserConfig.engines; default order
# lightpanda -> obscura -> chromium).
#
#   ./install-browsers.sh            # both
#   ./install-browsers.sh lightpanda # one
#
# Lightpanda: AGPL-3.0, https://github.com/lightpanda-io/browser (nightly).
#   Light and fast; runs page scripts, draws nothing (no screenshots).
#   Its usage reporting is switched off by the daemon
#   (LIGHTPANDA_DISABLE_TELEMETRY=true).
# Obscura: Apache-2.0, https://github.com/h4ckf0r0day/obscura (latest).
#   Renders pages and takes screenshots; the daemon starts it with
#   --stealth. `obscura` and `obscura-worker` must stay side by side.
#
# Both need glibc 2.35+ (Lightpanda arm64: 2.38+). Re-running replaces the
# installed copies; the previous ones are kept as *.prev for rollback.
# Prints each file's SHA-256 so the install can be recorded.
set -euo pipefail

HOME_DIR="${OPENFANG_HOME:-$HOME/.openfang}"
BIN="$HOME_DIR/bin"
mkdir -p "$BIN"

case "$(uname -m)" in
  x86_64|amd64) ARCH=x86_64 ;;
  aarch64|arm64) ARCH=aarch64 ;;
  *) echo "Unsupported CPU: $(uname -m)"; exit 1 ;;
esac
GLIBC="$(ldd --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+$' || echo unknown)"
echo "CPU $ARCH, glibc $GLIBC, installing into $BIN"

WANT="${1:-all}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

keep_prev() { [ -f "$1" ] && mv -f "$1" "$1.prev" || true; }

if [ "$WANT" = all ] || [ "$WANT" = lightpanda ]; then
  URL="https://github.com/lightpanda-io/browser/releases/download/nightly/lightpanda-$ARCH-linux"
  echo "Lightpanda: $URL"
  curl -fsSL -o "$TMP/lightpanda" "$URL"
  chmod +x "$TMP/lightpanda"
  keep_prev "$BIN/lightpanda"
  mv "$TMP/lightpanda" "$BIN/lightpanda"
  echo "  version: $(LIGHTPANDA_DISABLE_TELEMETRY=true "$BIN/lightpanda" version 2>&1 | head -1)"
  echo "  sha256:  $(sha256sum "$BIN/lightpanda" | cut -d' ' -f1)"
fi

if [ "$WANT" = all ] || [ "$WANT" = obscura ]; then
  URL="https://github.com/h4ckf0r0day/obscura/releases/latest/download/obscura-$ARCH-linux.tar.gz"
  echo "Obscura: $URL"
  curl -fsSL -o "$TMP/obscura.tgz" "$URL"
  mkdir -p "$TMP/obscura"
  tar xzf "$TMP/obscura.tgz" -C "$TMP/obscura"
  for f in obscura obscura-worker; do
    src="$(find "$TMP/obscura" -type f -name "$f" | head -1)"
    [ -n "$src" ] || { echo "  $f missing from the archive"; exit 1; }
    chmod +x "$src"
    keep_prev "$BIN/$f"
    mv "$src" "$BIN/$f"
    echo "  $f sha256: $(sha256sum "$BIN/$f" | cut -d' ' -f1)"
  done
fi

echo "Done. Restart the daemon so the browser picks them up."
