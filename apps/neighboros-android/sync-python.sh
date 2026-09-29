#!/bin/bash
# Syncs the pure-Python NeighborOS engine sources from the repo into the
# Chaquopy python dir at build time. The repo stays the single source of
# truth — no duplicated engine code is committed.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$HERE/../.."
SRC="$REPO/core/levi"
DEST="$HERE/neighboros/src/main/python/levi"
mkdir -p "$DEST"
cp "$SRC/__init__.py" "$DEST/__init__.py"
for pkg in neighboros neighbor; do
  rm -rf "$DEST/$pkg"
  mkdir -p "$DEST/$pkg"
  cp "$SRC/$pkg/"*.py "$DEST/$pkg/"
done
# packaged operator config: levi.neighbor.store.ensure_policies() seeds the
# workspace copy from the package default on first use. Chaquopy must see
# the .json at build time or first-run seeding fails on-device.
cp "$SRC/neighbor/policies.json" "$DEST/neighbor/policies.json"
# app-owned bridge (committed under python-src/)
cp "$HERE/python-src/neighboros_bridge.py" "$HERE/neighboros/src/main/python/neighboros_bridge.py"
echo "synced python sources -> $DEST"
