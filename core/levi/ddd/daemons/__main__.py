# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: 2026-09-25.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""``python -m levi.ddd.daemons`` — CLI for the DDD daily income daemons.

Usage (from ~/workspace/levi):
    PYTHONPATH=core python3 -m levi.ddd.daemons --daemon audit --run
    PYTHONPATH=core python3 -m levi.ddd.daemons --daemon listing --run
    PYTHONPATH=core python3 -m levi.ddd.daemons --daemon leads --run
    PYTHONPATH=core python3 -m levi.ddd.daemons --daemon audit --watch
    PYTHONPATH=core python3 -m levi.ddd.daemons --register
"""

from __future__ import annotations

import argparse
import json

__all__ = ["main"]


def _daemon_cls(name: str):
    from levi.ddd.daemons.audit_daemon import AuditDaemon
    from levi.ddd.daemons.leads_daemon import LeadsDaemon
    from levi.ddd.daemons.listing_daemon import ListingDaemon

    table = {"audit": AuditDaemon, "listing": ListingDaemon, "leads": LeadsDaemon}
    try:
        return table[name]
    except KeyError:
        raise SystemExit(
            f"unknown daemon {name!r} — choose audit, listing, or leads"
        ) from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DDD daily income daemons")
    parser.add_argument(
        "--daemon", choices=["audit", "listing", "leads"], default="audit"
    )
    parser.add_argument("--run", action="store_true", help="run the daily pass")
    parser.add_argument("--watch", action="store_true", help="read-only queue state")
    parser.add_argument("--register", action="store_true", help="register automations")
    args = parser.parse_args(argv)

    if args.register:
        from levi.ddd.daemons.register import main as reg_main

        return reg_main()

    daemon = _daemon_cls(args.daemon)()
    if args.run:
        receipt = daemon.run_daily()
    else:
        receipt = daemon.watch()
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
