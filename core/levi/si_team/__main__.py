"""`python -m levi.si_team` — run the si-team CLI standalone."""

from __future__ import annotations

import sys

from levi.si_team.cli import main

if __name__ == "__main__":
    sys.exit(main())
