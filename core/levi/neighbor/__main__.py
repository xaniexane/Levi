"""`python -m levi.neighbor ...` — NeighborOS CLI without the levi wrapper."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
