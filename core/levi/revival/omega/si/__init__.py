"""omega/si: the native synthetic-intelligence cores of the new generators.

This is where Omega's new generators actually live. ``automation_core``
turns a declarative spec into automation-minion dicts; ``skill_core`` turns
a declared name + capability into a LEVI skill scaffold. Both are pure
LEVI logic — stdlib only, no network, no outside models.

Separation law: nothing under ``si/`` imports ``ai/``. The ``ai/``
subpackage holds conventional-protocol bridges *to* these cores; the
cores never reach back.
"""

from __future__ import annotations

ORIGIN = "levi-revival-omega/si"
