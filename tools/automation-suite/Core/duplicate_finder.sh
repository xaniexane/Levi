#!/usr/bin/env bash
# duplicate_finder.sh - find duplicate files by sha256.
#
# DEFAULT: report groups of duplicates, change nothing.
# --move-dupes: move all but the NEWEST file of each group into
#   <dir>/duplicates/ (never deletes anything outright).
set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    echo "usage: $(basename "$0") <dir> [--move-dupes]"
    echo "Report duplicate files by sha256; --move-dupes quarantines all but"
    echo "the newest of each group into <dir>/duplicates/ (never deletes)."
    exit 0
fi

usage() {
    echo "usage: $(basename "$0") <dir> [--move-dupes]" >&2
    exit 2
}

[[ $# -ge 1 && $# -le 2 ]] || usage
DIR="$1"
MODE="${2:-}"
[[ -z "$MODE" || "$MODE" == "--move-dupes" ]] || usage
[[ -d "$DIR" ]] || { echo "error: not a directory: $DIR" >&2; exit 1; }

if command -v sha256sum >/dev/null 2>&1; then
    HASHER=(sha256sum)
elif command -v shasum >/dev/null 2>&1; then
    HASHER=(shasum -a 256)
else
    echo "error: neither sha256sum nor shasum found" >&2
    exit 1
fi

tmp="$(mktemp)"; dupes="$(mktemp)"
trap 'rm -f "$tmp" "$dupes"' EXIT

find "$DIR" -type f -not -path "*/duplicates/*" -print0 \
    | xargs -0 "${HASHER[@]}" \
    | sort -k1,1 > "$tmp"
awk '{print $1}' "$tmp" | uniq -d > "$dupes"

unique_dest() { # $1=dir $2=basename -> prints a free path
    local d="$1" b="$2" dest="$1/$2"
    if [[ ! -e "$dest" ]]; then echo "$dest"; return; fi
    local stem="$b" ext=""
    if [[ "$b" == *.* ]]; then stem="${b%.*}"; ext=".${b##*.}"; fi
    local i=1
    while [[ -e "$d/${stem}_$i${ext}" ]]; do i=$((i + 1)); done
    echo "$d/${stem}_$i${ext}"
}

groups=0
dup_files=0
moved=0
while IFS= read -r hash; do
    [[ -n "$hash" ]] || continue
    groups=$((groups + 1))
    mapfile -t files < <(awk -v h="$hash" '$1 == h { sub(/^[^ ]+ ./, ""); print }' "$tmp")
    echo "group $groups (sha256 ${hash:0:16}..., ${#files[@]} files):"
    # newest by mtime wins the keep slot
    newest=""; newest_m=-1
    for f in "${files[@]}"; do
        m="$(stat -c %Y "$f")"
        if (( m > newest_m )); then newest_m="$m"; newest="$f"; fi
        dup_files=$((dup_files + 1))
    done
    for f in "${files[@]}"; do
        if [[ "$f" == "$newest" ]]; then
            echo "  KEEP (newest): $f"
        else
            if [[ "$MODE" == "--move-dupes" ]]; then
                mkdir -p "$DIR/duplicates"
                dest="$(unique_dest "$DIR/duplicates" "$(basename "$f")")"
                mv -- "$f" "$dest"
                moved=$((moved + 1))
                echo "  MOVED: $f -> $dest"
            else
                echo "  dupe: $f"
            fi
        fi
    done
done < "$dupes"

if [[ "$groups" -eq 0 ]]; then
    echo "no duplicates found in $DIR"
    exit 0
fi
echo "---"
echo "$groups duplicate group(s), $dup_files file(s) involved."
if [[ "$MODE" == "--move-dupes" ]]; then
    echo "$moved file(s) moved to $DIR/duplicates/ (nothing deleted)."
else
    echo "dry-run: nothing moved (use --move-dupes to quarantine dupes)."
fi
