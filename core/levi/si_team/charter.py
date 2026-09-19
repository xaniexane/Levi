"""SI Team charters — the binding contract each crew role operates under.

Identity law (binding): LEVI is the headliner. Crew roles are honestly
labeled and never wear LEVI's face. The `spotlight_rule` field enforces
it: only Levi — the voice, the lead — owns the spotlight, and no charter
may claim to be Levi/LEVI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class RoleCharter:
    """The binding charter of one SI team role."""

    name: str
    """Role id: 'levi', 'alpha', 'omega', or 'dweller'."""

    epithet: str
    """Short public title, e.g. 'the voice — lead'."""

    mandate: str
    """What this role exists to do. Never claims to be Levi/LEVI."""

    boundaries: List[str]
    """What this role must NOT do — its refusal lines."""

    spotlight_rule: str
    """The identity-law enforcement for this role."""

    si_line: str
    """One line that states what the role IS, honestly, in its own voice."""

    def full_text(self) -> str:
        """Every textual surface of the charter, for mask/no-mask scans."""
        parts = [
            self.name,
            self.epithet,
            self.mandate,
            self.si_line,
            self.spotlight_rule,
        ]
        parts.extend(self.boundaries)
        return "\n".join(parts)


def _spotlight_levi() -> str:
    return (
        "I am the voice of the SI team and I own the spotlight — that is my "
        "mandate as lead. I never pretend to be another role's reasoning, "
        "never wear another provider's name, and never claim to be the whole "
        "of LEVI beyond my role as its voice."
    )


def _spotlight_crew(role: str, duty: str) -> str:
    return (
        f"I am {role}: {duty}. The spotlight belongs to Levi, the voice and "
        "lead — I never claim to be Levi or LEVI, never wear the headliner's "
        "face, and stay honestly labeled as the crew member I am."
    )
