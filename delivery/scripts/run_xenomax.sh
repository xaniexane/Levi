#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/runtimes/xenomax"
export LEVI_HOME="${LEVI_HOME:-$HOME/levi}"
exec python3 levi.py "$@"
