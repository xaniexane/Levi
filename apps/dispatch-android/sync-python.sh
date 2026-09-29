#!/bin/bash
# Syncs the pure-Python engine sources from the repo into the Chaquopy
# python dir at build time. The repo stays the single source of truth —
# no duplicated engine code is committed.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$HERE/../.."
SRC="$REPO/core/levi"
DEST="$HERE/dispatch/src/main/python/levi"
mkdir -p "$DEST"
cp "$SRC/__init__.py" "$DEST/__init__.py"
for pkg in dispatch; do
  rm -rf "$DEST/$pkg"
  mkdir -p "$DEST/$pkg"
  cp "$SRC/$pkg/"*.py "$DEST/$pkg/"
done
# app-owned bridge (committed under python-src/)
cp "$HERE/python-src/dispatch_bridge.py" "$HERE/dispatch/src/main/python/dispatch_bridge.py"
echo "synced python sources -> $DEST"
