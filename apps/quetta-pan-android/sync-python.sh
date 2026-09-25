#!/bin/bash
# Syncs the Quetta-Pan engine from the repo into the Chaquopy python dir.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$HERE/../.."
SRC="$REPO/core/levi"
DEST="$HERE/quettapan/src/main/python/levi"
mkdir -p "$DEST"
cp "$SRC/__init__.py" "$DEST/__init__.py"
rm -rf "$DEST/quetta_pan"
mkdir -p "$DEST/quetta_pan"
cp "$SRC/quetta_pan/"*.py "$DEST/quetta_pan/"
cp "$HERE/python-src/qp_bridge.py" "$HERE/quettapan/src/main/python/qp_bridge.py"
echo "synced python sources -> $DEST"
