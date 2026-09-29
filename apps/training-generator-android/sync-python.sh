#!/bin/bash
# Syncs the pure-Python academy engine from the repo into the Chaquopy
# python dir at build time. The repo stays the single source of truth —
# no duplicated engine code is committed.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$HERE/../.."
SRC="$REPO/core/levi"
DEST="$HERE/tg/src/main/python/levi"
mkdir -p "$DEST"
cp "$SRC/__init__.py" "$DEST/__init__.py"
# academy package: all modules + package data (syllabus, data dir)
rm -rf "$DEST/academy"
mkdir -p "$DEST/academy"
cp "$SRC/academy/"*.py "$DEST/academy/"
cp "$SRC/academy/syllabus.json" "$DEST/academy/syllabus.json"
for sub in data differentiators lessons; do
  if [ -d "$SRC/academy/$sub" ]; then
    rm -rf "$DEST/academy/$sub"
    mkdir -p "$DEST/academy/$sub"
    cp -r "$SRC/academy/$sub/"* "$DEST/academy/$sub/" 2>/dev/null || true
  fi
done
# app-owned bridge (committed under python-src/)
cp "$HERE/python-src/academy_bridge.py" "$HERE/tg/src/main/python/academy_bridge.py"
echo "synced python sources -> $DEST"
