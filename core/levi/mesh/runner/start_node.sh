#!/bin/bash
# Fleet node launcher for Linux / ChromeOS Crostini / Termux.
# No install, no root — the folder is the program.
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "[node] python3 not found. Install it first:"
    echo "  Crostini / Debian:  sudo apt install -y python3"
    echo "  Termux:             pkg install -y python"
    exit 1
fi
exec "$PY" run_node.py --config node_config.json
