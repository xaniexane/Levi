#!/usr/bin/env bash
# backup_rotator.sh - rotating timestamped snapshots of a source directory.
#
# Creates <backup_root>/snap-YYYYMMDD-HHMMSS/ containing a copy of <src>.
# Uses hardlinked snapshots (cp -al) from the latest snapshot when possible
# so unchanged files share disk space; falls back to a full copy.
# Keeps the newest KEEP snapshots (default 7), prunes older ones.
set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    echo "usage: $(basename "$0") <src_dir> <backup_root> [keep_n]"
    echo "Rotating timestamped snapshots; keeps newest keep_n (default 7)."
    exit 0
fi

usage() {
    echo "usage: $(basename "$0") <src_dir> <backup_root> [keep_n]" >&2
    echo "  keep_n: number of newest snapshots to retain (default 7)" >&2
    exit 2
}

[[ $# -ge 2 && $# -le 3 ]] || usage
SRC="$1"; ROOT="$2"; KEEP="${3:-7}"
[[ -d "$SRC" ]] || { echo "error: source not a directory: $SRC" >&2; exit 1; }
[[ "$KEEP" =~ ^[1-9][0-9]*$ ]] || { echo "error: keep_n must be a positive integer" >&2; exit 1; }
mkdir -p "$ROOT" || { echo "error: cannot create backup root: $ROOT" >&2; exit 1; }

stamp="$(date +%Y%m%d-%H%M%S)"
dest="$ROOT/snap-$stamp"
latest="$(ls -d "$ROOT"/snap-* 2>/dev/null | sort | tail -n 1 || true)"

if [[ -n "${latest:-}" && -d "$latest" ]]; then
    if cp -al "$latest/." "$dest" 2>/dev/null; then
        echo "seeded hardlink snapshot from $(basename "$latest")"
    else
        echo "note: hardlink seeding unavailable, doing full copy"
        mkdir -p "$dest"
    fi
else
    mkdir -p "$dest"
fi

# Copy source over the top. --remove-destination unlinks hardlinked targets
# first so the previous snapshot's inodes are never modified in place.
cp -a --remove-destination "$SRC/." "$dest/"
echo "snapshot created: $dest"

# Prune: keep newest $KEEP snapshots.
mapfile -t snaps < <(ls -d "$ROOT"/snap-* 2>/dev/null | sort || true)
if (( ${#snaps[@]} > KEEP )); then
    prune_count=$((${#snaps[@]} - KEEP))
    for ((i = 0; i < prune_count; i++)); do
        rm -rf "${snaps[$i]}"
        echo "pruned: ${snaps[$i]}"
    done
fi
echo "retained snapshots: $(ls -d "$ROOT"/snap-* 2>/dev/null | wc -l)"
