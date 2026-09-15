#!/usr/bin/env bash
# LEVI Termux toolchain setup — run INSIDE Termux on Android.
#
# Usage:
#   bash setup.sh <path-to-levi-termux.tar.gz>   # from a downloaded snapshot
#   bash setup.sh --clone                         # from GitHub (after push)
#
# What it does:
#   1. installs python + git via pkg
#   2. unpacks (or clones) LEVI into ~/levi
#   3. installs a `levi` wrapper into ~/bin (on PATH in Termux)
#   4. smoke-tests: `levi status` and `levi growth status`
set -euo pipefail

MODE="${1:-}"
TARBALL=""

if [ "$MODE" = "--clone" ]; then
    MODE="clone"
elif [ -n "$MODE" ]; then
    TARBALL="$MODE"; MODE="tarball"
else
    echo "usage: bash setup.sh <levi-termux.tar.gz> | --clone" >&2
    exit 1
fi

echo "==> [1/4] installing python + git"
pkg update -y >/dev/null 2>&1 || true
pkg install -y python git

echo "==> [2/4] installing LEVI into ~/levi"
rm -rf "$HOME/levi"
mkdir -p "$HOME/levi"
if [ "$MODE" = "tarball" ]; then
    if [ ! -f "$TARBALL" ]; then
        echo "tarball not found: $TARBALL" >&2
        echo "hint: download it on the phone, then run: termux-setup-storage" >&2
        echo "      and pass ~/storage/downloads/levi-termux.tar.gz" >&2
        exit 1
    fi
    tar -xzf "$TARBALL" -C "$HOME/levi"
else
    git clone --depth 1 https://github.com/xaniexane/Levi.git "$HOME/levi"
fi

echo "==> [3/4] installing 'levi' wrapper into ~/bin"
mkdir -p "$HOME/bin"
cat > "$HOME/bin/levi" <<'WRAP'
#!/usr/bin/env bash
# LEVI launcher for Termux. Core is stdlib-only: no venv, no pip needed.
export PYTHONPATH="$HOME/levi/core"
exec python3 -m levi.cli.main "$@"
WRAP
chmod +x "$HOME/bin/levi"
# ~/bin is on PATH in Termux by default (via $PREFIX/etc/profile); ensure it now:
export PATH="$HOME/bin:$PATH"

echo "==> [4/4] smoke test"
levi status 2>&1 | head -8
echo "---"
levi growth status 2>&1 | head -6

echo ""
echo "LEVI is ready on Termux. Try:"
echo "  levi ask \"what can you do?\""
echo "  levi growth cycle --no-model"
echo "  levi agent chat"
echo ""
echo "Notes:"
echo "  - data lives in ~/.levi (sessions, memory, growth journal)"
echo "  - vault encryption needs: pip install cryptography  (slow build on device; optional)"
echo "  - the local AI model (levi-local) has no Android runner build;"
echo "    LEVI falls back to its offline rule engine honestly"
echo "  - brain training (torch) is not available on Android — skipped"
