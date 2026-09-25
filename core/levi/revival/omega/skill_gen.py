"""Omega LEVI-skill generator: declared name + capability -> skill scaffold.

Organ-facing API over the SI core (``levi.revival.omega.si.skill_core``).
The real logic lives in the core; this module is the organ's front door.

``scaffold_skill(name, capability)`` returns ``{"ok", "name", "files",
"errors"}``. The scaffold is pure scaffolding — every generated file is
honestly labeled "scaffold, not a skill" — and invalid names are refused,
never silently renamed.
"""

from __future__ import annotations

from .si.skill_core import ORIGIN, SCAFFOLD_BANNER, scaffold_skill

__all__ = ["ORIGIN", "SCAFFOLD_BANNER", "scaffold_skill"]
