#!/usr/bin/env bash
# quick_note.sh - append a timestamped note to today's markdown note file.
#
# Usage: quick_note.sh <note text...>        (args joined as the note)
#        echo "text" | quick_note.sh         (or read from stdin)
#
# Notes land in ~/Ultimate-Automation-Suite/Productivity/notes/YYYY-MM-DD.md
# Override the directory with NOTES_DIR.
set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    echo "usage: $(basename "$0") <note text...>   (or pipe text via stdin)"
    echo "Appends a timestamped note to \$NOTES_DIR/YYYY-MM-DD.md"
    echo "(default: ~/Ultimate-Automation-Suite/Productivity/notes/)."
    exit 0
fi

NOTES_DIR="${NOTES_DIR:-$HOME/Ultimate-Automation-Suite/Productivity/notes}"
mkdir -p "$NOTES_DIR"
file="$NOTES_DIR/$(date +%F).md"

if [[ $# -gt 0 ]]; then
    note="$*"
else
    if [[ -t 0 ]]; then
        echo "usage: $(basename "$0") <note text...>  (or pipe text via stdin)" >&2
        exit 2
    fi
    note="$(cat)"
fi

# Refuse to write blank notes.
if [[ -z "${note//[[:space:]]/}" ]]; then
    echo "empty note: nothing written." >&2
    exit 1
fi

{
    echo "## $(date +%T)"
    echo
    echo "$note"
    echo
} >> "$file"
echo "appended to $file"
