"""alpha/si: the native reasoning core — propose -> critique -> verdict.

Pure LEVI deliberation, stdlib only. Three movements, no outside models:

- ``propose(task)`` — three stances: direct, skeptical, minimal.
- ``critique(proposals)`` — each proposal's weakness and open question.
- ``verdict(proposals, critiques, substrate)`` — picks the stance that
  survives its own critique, and says plainly which substrate reasoned.

Separation law: nothing under ``si/`` imports ``ai/``. The ``ai/``
subpackage holds a conventional-protocol bridge *to* these functions;
they never reach back.
"""

from __future__ import annotations

ORIGIN = "levi-alpha/si"
