#!/bin/bash
# Syncs the LEVI engine sources from the repo into the Chaquopy python dir
# at build time. The repo stays the single source of truth — no duplicated
# engine code is committed.
#
# MEGA-APK closure (2026-09-23): the whole core/levi tree ships, EXCEPT:
#   brain/      — 1.8G of weights/checkpoints + torch; not on-device (honest gate).
#   knowledge/  — 80M corpus data; stays on the workstation (honest gate).
#   dynasty/    — EYES-ONLY (Chauncey + Rex). Dynasty materials never ship in
#                 a distributable build. Never add this back without his word.
#   __pycache__ / *.pyc — never shipped.
#
# Everything imports cleanly with the full tree present (verified 2026-09-23:
# levi.plaiground, levi.advisor, levi.oracle, levi.cybrus, levi.creator,
# levi.voidbox.payments, levi.legion, levi.hive, levi.device.alerter,
# levi.editions.transport.hos_copilot, levi.neighboros, levi.daemon,
# levi.demand, levi.organs, levi.media, levi.neighbor — all OK stdlib-only),
# so no __init__ shims are needed anymore.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$HERE/../.."
SRC="$REPO/core/levi"
DEST="$HERE/creator/src/main/python/levi"
mkdir -p "$DEST"

# full tree, minus the exclusions above.
# Nothing deletes: overlay-copy into DEST without removing anything first
# (stale files are harmless; the tree is regenerated every build).
tar --exclude='__pycache__' --exclude='*.pyc' --exclude='./brain' \
    --exclude='./knowledge' --exclude='./dynasty' \
    -cf - -C "$SRC" . | tar --no-same-owner -xf - -C "$DEST"

# exclusion guard: fail the build loudly if a prohibited directory is present
for banned in brain knowledge dynasty; do
  if [ -e "$DEST/$banned" ]; then
    echo "sync-python.sh: REFUSING — prohibited directory present: $DEST/$banned" >&2
    exit 1
  fi
done

# app-owned bridge modules (committed under python-src/)
cp "$HERE/python-src/levi_bridge.py" "$HERE/creator/src/main/python/levi_bridge.py"
cp "$HERE/python-src/levi_systems_registry.py" "$HERE/creator/src/main/python/levi_systems_registry.py"

echo "synced python sources -> $DEST"
du -sh "$DEST"
