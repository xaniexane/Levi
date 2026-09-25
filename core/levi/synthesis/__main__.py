"""``python -m levi.synthesis`` — the front door without the big CLI tree."""

from levi.synthesis.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
