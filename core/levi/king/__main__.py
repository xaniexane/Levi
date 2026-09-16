"""CLI: python -m levi.king

King — the single control plane for narrative operations. Mirrors
``levi king``: the parser is built by ``levi.king.cli.register_king``
and dispatch goes through the real ``cmd_king`` handler, so the
``python -m`` surface and the ``levi`` surface can never drift.

HITL rules are inherited unchanged: `social-post` requires a
review-approved pack AND explicit --yes; it routes through the plugin
registry and posts nothing otherwise.
"""

from __future__ import annotations

import argparse


def main(argv=None) -> int:
    from levi.king.cli import cmd_king, register_king

    ap = argparse.ArgumentParser(
        prog="levi.king",
        description="King control plane: ledger, engines, social, review "
        "(mirrors `levi king`)",
    )
    sub = ap.add_subparsers()
    register_king(sub)

    # register_king builds the `king` subcommand exactly as the `levi`
    # CLI does; we inject it so `python -m levi.king status` behaves
    # like `levi king status`.
    args = ap.parse_args(["king"] + list(argv or []))
    cmd_king(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
