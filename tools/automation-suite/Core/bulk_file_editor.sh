#!/usr/bin/env bash
# bulk_file_editor.sh - literal find/replace across files.
#
# DEFAULT is a dry-run showing a diff-like preview; nothing is written.
# Pass --apply to write changes (each modified file gets a .bak first).
#
# Matching is literal (not regex). Binary files are skipped (grep -I).
# Replacement is done via python3 for safe literal-string handling of
# arbitrary find/replace text.
set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    echo "usage: $(basename "$0") <dir> <find> <replace> [--ext EXT] [--apply]"
    echo "Literal find/replace across files. Dry-run preview by default;"
    echo "--apply writes changes (each modified file gets a .bak first)."
    exit 0
fi

usage() {
    echo "usage: $(basename "$0") <dir> <find> <replace> [--ext EXT] [--apply]" >&2
    echo "  <dir>     directory to search (recursive, skips .git/)" >&2
    echo "  <find>    literal text to find" >&2
    echo "  <replace> literal replacement text" >&2
    echo "  --ext EXT only consider *.<EXT> files" >&2
    echo "  --apply   write changes (default: dry-run preview)" >&2
    exit 2
}

[[ $# -ge 3 ]] || usage
DIR="$1"; FIND="$2"; REPLACE="$3"
shift 3
EXT=""
APPLY=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --ext)   [[ $# -ge 2 ]] || usage; EXT="$2"; shift 2 ;;
        --apply) APPLY=1; shift ;;
        *) usage ;;
    esac
done

[[ -d "$DIR" ]] || { echo "error: not a directory: $DIR" >&2; exit 1; }
[[ -n "$FIND" ]] || { echo "error: <find> must not be empty" >&2; exit 1; }

# Collect candidate files (NUL-delimited for odd filenames).
mapfile -d '' -t FILES < <(
    if [[ -n "$EXT" ]]; then
        find "$DIR" -type f -name "*.${EXT}" -not -path "*/.git/*" -not -name "*.bak" -print0
    else
        find "$DIR" -type f -not -path "*/.git/*" -not -name "*.bak" -print0
    fi
)

MATCHED=()
for f in "${FILES[@]}"; do
    if grep -q -F -I -e "$FIND" "$f" 2>/dev/null; then
        MATCHED+=("$f")
    fi
done

if [[ ${#MATCHED[@]} -eq 0 ]]; then
    echo "no files contain: $FIND"
    exit 0
fi

preview_file() { # $1 = file
    FIND_STR="$FIND" REPLACE_STR="$REPLACE" python3 - "$1" <<'PYEOF'
import os, sys
path = sys.argv[1]
needle = os.environ["FIND_STR"]
repl = os.environ["REPLACE_STR"]
try:
    fh = open(path, "r", encoding="utf-8", errors="replace")
except OSError as exc:
    print(f"  (unreadable: {exc})")
    sys.exit(0)
with fh:
    for i, line in enumerate(fh, 1):
        if needle in line:
            print(f"  - L{i}: {line.rstrip(chr(10))[:200]}")
            print(f"  + L{i}: {line.replace(needle, repl).rstrip(chr(10))[:200]}")
PYEOF
}

apply_file() { # $1 = file ; prints replacement count
    cp -p "$1" "$1.bak"
    FIND_STR="$FIND" REPLACE_STR="$REPLACE" python3 - "$1" <<'PYEOF'
import os, sys
path = sys.argv[1]
needle = os.environ["FIND_STR"]
repl = os.environ["REPLACE_STR"]
with open(path, "r", encoding="utf-8") as fh:
    text = fh.read()
count = text.count(needle)
with open(path, "w", encoding="utf-8") as fh:
    fh.write(text.replace(needle, repl))
print(count)
PYEOF
}

if [[ "$APPLY" -eq 0 ]]; then
    echo "dry-run: ${#MATCHED[@]} file(s) would change (use --apply to write):"
    for f in "${MATCHED[@]}"; do
        echo "--- $f"
        preview_file "$f"
    done
    exit 0
fi

total=0
for f in "${MATCHED[@]}"; do
    n="$(apply_file "$f")"
    total=$((total + n))
    echo "updated $f ($n replacement(s), backup: $f.bak)"
done
echo "done: ${#MATCHED[@]} file(s), $total replacement(s)."
