"""Genesis package: the lifetime one-copy buyable variant of the LEVI system.

A genesis pack ships remixed agent variants — renamed, remixed, recycled,
mutated — never the raw originals. This package is the forge, the
assembler, the license mint, the paper-money seam, and the CLI surface.

Submodules:
  parts    — capability catalog (static, no heavy imports)
  remix    — variant forging (rename / remix / recycle / mutate)
  assemble — pack assembler: spec -> pack directory
  license  — lifetime 1-copy terms as data + license mint
  money    — paper-mode price quote + checkout seam (paper only)
  cli      — ``levi genesis`` command handlers
"""

from __future__ import annotations

__all__ = [
    "parts",
    "remix",
    "assemble",
    "license",
    "money",
    "cli",
    "odd_sets",
]
