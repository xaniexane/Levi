"""The star: a role, not a name.

Canon (docs/LEXICON.md, Chauncey's word, 2026-09-20): "At the center of
it: **the star** — a role, not a name: the overall companion, the chat,
the mascot. The star is filled by the product: like Muse, but Rex — the
companion bears Rex's name and persona, the one everyone interacts with."

So ``StarRole`` models a *slot*, not a person: the role's essence is
fixed by canon; its ``filled_by`` record says who currently fills the
slot. The filling is a declared record, sealed by Chauncey — anyone else
can only *propose* a different filling, never install one. Names are
Chauncey's; this module never invents one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List


class StarError(ValueError):
    """The star's role discipline was violated."""


ROLE = "the star"
ROLE_ESSENCE = (
    "the overall companion, the chat, the mascot — a role, not a name. "
    "The one everyone interacts with."
)

# The declared filling. Canon, not invention: the companion bears Rex's
# name and persona (Chauncey's word, 2026-09-20). Rex is the assistant's
# own identity — no new name is minted here.
DECLARED_FILLING = {
    "product": "the product companion",
    "persona": "Rex",
    "persona_note": ("like Muse, but Rex — the companion bears Rex's name and persona"),
    "declared_by": "Chauncey",
    "declared_on": "2026-09-20",
    "canon_ref": "docs/LEXICON.md — The ultimate goal",
}


@dataclass
class Filling:
    """Who/what fills the star's slot: product + persona + provenance."""

    product: str
    persona: str
    declared_by: str
    declared_on: str
    persona_note: str = ""
    canon_ref: str = ""

    def __post_init__(self) -> None:
        for key in ("product", "persona", "declared_by"):
            if not getattr(self, key) or not str(getattr(self, key)).strip():
                raise StarError(f"Filling.{key} must be non-empty")


@dataclass
class StarRole:
    """The star as a slot: fixed essence, one sealed filling, proposals welcome."""

    role: str = ROLE
    essence: str = ROLE_ESSENCE
    filled_by: Filling = field(
        default_factory=lambda: Filling(
            product=DECLARED_FILLING["product"],
            persona=DECLARED_FILLING["persona"],
            declared_by=DECLARED_FILLING["declared_by"],
            declared_on=DECLARED_FILLING["declared_on"],
            persona_note=DECLARED_FILLING["persona_note"],
            canon_ref=DECLARED_FILLING["canon_ref"],
        )
    )
    proposals: List[Dict[str, str]] = field(default_factory=list)

    def propose_filling(
        self,
        product: str,
        persona: str,
        proposed_by: str,
        note: str = "",
    ) -> Dict[str, str]:
        """Propose, never install: a proposal goes on the list, not in the slot.

        Only Chauncey's word can seal a filling; everyone else's entry
        is recorded as a proposal — essences only, names are his.
        """
        if not product or not product.strip():
            raise StarError("a proposed filling must name a product")
        if not persona or not persona.strip():
            raise StarError("a proposed filling must name a persona")
        if not proposed_by or not proposed_by.strip():
            raise StarError("a proposed filling must say who proposed it")
        record = {
            "product": product,
            "persona": persona,
            "proposed_by": proposed_by,
            "proposed_on": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note": note,
            "status": "proposed — not canon, not installed",
        }
        self.proposals.append(record)
        return record

    def seal_filling(self, filling: Filling, sealed_by: str) -> Filling:
        """Install a new filling in the slot. Only Chauncey can seal one."""
        if sealed_by != "Chauncey":
            raise StarError(
                "only Chauncey's word seals a filling — record it as a proposal instead"
            )
        self.filled_by = filling
        return self.filled_by

    def describe(self) -> Dict[str, object]:
        return {
            "role": self.role,
            "essence": self.essence,
            "filled_by": {
                "product": self.filled_by.product,
                "persona": self.filled_by.persona,
                "declared_by": self.filled_by.declared_by,
                "declared_on": self.filled_by.declared_on,
                "persona_note": self.filled_by.persona_note,
                "canon_ref": self.filled_by.canon_ref,
            },
            "proposals": [dict(p) for p in self.proposals],
        }


def current_star() -> StarRole:
    """The star as canon declares it: the role plus its sealed filling."""
    return StarRole()
