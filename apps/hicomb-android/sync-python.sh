#!/bin/bash
# Syncs the pure-Python engine sources from the repo into the Chaquopy
# python dir at build time. The repo stays the single source of truth —
# no duplicated engine code is committed.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$HERE/../.."
SRC="$REPO/core/levi"
DEST="$HERE/hicomb/src/main/python/levi"
mkdir -p "$DEST"
cp "$SRC/__init__.py" "$DEST/__init__.py"
for pkg in hicomb quetta_pan surgeon builder; do
  rm -rf "$DEST/$pkg"
  mkdir -p "$DEST/$pkg"
  cp "$SRC/$pkg/"*.py "$DEST/$pkg/"
done
# builder scaffolds live one level down
rm -rf "$DEST/builder/scaffolds"
mkdir -p "$DEST/builder/scaffolds"
cp "$SRC/builder/scaffolds/"*.py "$DEST/builder/scaffolds/"
# app-owned bridge (committed under python-src/)
cp "$HERE/python-src/hicomb_bridge.py" "$HERE/hicomb/src/main/python/hicomb_bridge.py"
echo "synced python sources -> $DEST"
