"""CLI: python -m levi.dweller <grind|jobs|receipt> [options]

The Dweller grinds in the depths: deep sweeps, exhaustive
cross-references, long-horizon watches — quietly, with a receipt for
every job.
"""

from __future__ import annotations

import argparse
import sys

from .cli import _add_subcommands, cmd_dweller


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="levi.dweller",
        description="Dweller: the SI that dwells in the depths of the work",
    )
    cmds = p.add_subparsers(dest="dweller_cmd", required=True)
    _add_subcommands(cmds)
    args = p.parse_args(argv)
    return cmd_dweller(args)


if __name__ == "__main__":
    sys.exit(main())
