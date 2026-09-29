#!/bin/bash
# Syncs the pure-Python engine sources from the repo into the Chaquopy
# python dir at build time. The repo stays the single source of truth —
# no duplicated engine code is committed.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$HERE/../.."
SRC="$REPO/core/levi"
DEST="$HERE/buzztunes/src/main/python/levi"
mkdir -p "$DEST"
cp "$SRC/__init__.py" "$DEST/__init__.py"
rm -rf "$DEST/buzztunes"
mkdir -p "$DEST/buzztunes"
cp "$SRC/buzztunes/"*.py "$DEST/buzztunes/"
# app-owned bridge (committed under python-src/)
cp "$HERE/python-src/buzztunes_bridge.py" "$HERE/buzztunes/src/main/python/buzztunes_bridge.py"
echo "synced python sources -> $DEST"
