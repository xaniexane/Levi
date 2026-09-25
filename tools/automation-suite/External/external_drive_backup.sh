#!/usr/bin/env bash
# external_drive_backup.sh - back up source dirs to an external mount point.
#
# DEFAULT is rsync --dry-run (report only). Pass --apply to actually copy.
# Refuses to run unless the destination is a mounted filesystem.
set -euo pipefail

usage() { # $1 = exit code (default 2)
    echo "usage: $(basename "$0") --dest <mountpoint> <src1> [src2 ...] [--apply]" >&2
    echo "  default: rsync -a --dry-run (preview only)" >&2
    echo "  --apply: perform the copy" >&2
    exit "${1:-2}"
}

DEST=""; APPLY=0; SOURCES=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dest) [[ $# -ge 2 ]] || usage; DEST="$2"; shift 2 ;;
        --apply) APPLY=1; shift ;;
        -h|--help) usage 0 ;;
        --*) echo "error: unknown option: $1" >&2; usage ;;
        *) SOURCES+=("$1"); shift ;;
    esac
done

[[ -n "$DEST" && ${#SOURCES[@]} -gt 0 ]] || usage
command -v rsync >/dev/null 2>&1 || { echo "error: rsync not installed" >&2; exit 2; }

is_mounted() { # $1 = path
    if command -v mountpoint >/dev/null 2>&1 && mountpoint -q "$1" 2>/dev/null; then
        return 0
    fi
    # fallback: check /proc/mounts for the resolved path
    local rp
    rp="$(realpath -m "$1" 2>/dev/null || echo "$1")"
    grep -qsE "[[:space:]]${rp}[[:space:]]" /proc/mounts
}

if ! is_mounted "$DEST"; then
    echo "error: destination is not a mounted filesystem: $DEST" >&2
    echo "refusing to back up to a non-mounted path (typo protection)." >&2
    exit 1
fi

for s in "${SOURCES[@]}"; do
    [[ -e "$s" ]] || { echo "error: source not found: $s" >&2; exit 1; }
done

for src in "${SOURCES[@]}"; do
    target="$DEST/$(basename "$src")"
    if [[ "$APPLY" -eq 1 ]]; then
        echo "--- backing up $src -> $target"
        mkdir -p "$target"
        rsync -a --info=stats1 "$src/" "$target/"
    else
        echo "--- dry-run: $src -> $target (use --apply to copy)"
        rsync -a --dry-run --itemize-changes "$src/" "$target/" | head -n 40
    fi
done
echo "done."
