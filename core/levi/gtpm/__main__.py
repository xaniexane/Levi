"""Entry point: ``python -m levi.gtpm demo`` (run from the repo root with
``core/`` on the path, e.g. ``PYTHONPATH=core python -m levi.gtpm demo``).
"""

from __future__ import annotations

import json
import sys


def main(argv: list) -> int:
    from levi.gtpm.flagship import run_demo

    if argv and argv[0] not in ("demo",):
        print("usage: python -m levi.gtpm demo", file=sys.stderr)
        return 2
    summary = run_demo()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
