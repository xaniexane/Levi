"""CLI: python -m levi.uniforge <plan|build> [options]

One build plan across heterogeneous targets, through the forge law:
Plan -> Preview -> Permission -> Execute -> Verify -> Receipt.
"""

from __future__ import annotations

import argparse
import sys

from .cli import _add_subcommands, cmd_uniforge


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="levi.uniforge",
        description="UniForge: one build plan across heterogeneous targets",
    )
    cmds = p.add_subparsers(dest="uniforge_cmd", required=True)
    _add_subcommands(cmds)
    args = p.parse_args(argv)
    return cmd_uniforge(args)


if __name__ == "__main__":
    sys.exit(main())
