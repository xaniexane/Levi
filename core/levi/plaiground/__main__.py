"""Standalone entry: ``python -m levi.plaiground <command> ...``.

The ``levi plaiground`` top-level hook for ``cli/main.py`` is staged
separately — this entry works today with zero changes to shared files.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from levi.plaiground.cli import main as _cli_main

    return _cli_main(list(argv) if argv is not None else sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
