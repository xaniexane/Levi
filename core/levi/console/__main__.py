"""CLI: python -m levi.console

Boots the interactive LEVI console dashboard (same as ``levi console``).
Refuses to run without an interactive terminal — never hangs on input()
in a pipe — and exits 1 with a one-line explanation in that case.
"""

from __future__ import annotations

import argparse


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.console",
        description="LEVI interactive console dashboard "
        "(needs an interactive terminal)",
    )
    ap.parse_args(argv)

    from levi.console.app import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
