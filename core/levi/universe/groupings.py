"""The Legion groupings registry: the large groupings of intelligence forms.

Canon (docs/LEXICON.md): "The large groupings of intelligence forms
take their names from the Legion." Canon (Chauncey's organizing
instinct): mass-groupings of species — hives, schools, packs, herds,
flocks — each with its own nature and domain; Legion is the preferred
umbrella ("for we are many"), and the Hive is the builders' grouping
*inside* it, not the whole.

Discipline (the gates are Chauncey's):

- Essences only here. Names are Chauncey's — nothing in this module
  invents a grouping name, a sealed identity, an intelligence definition,
  or a placement.
- The registry is **propose-only**: anyone may propose a grouping; only
  Chauncey's word declares one, and declarations live in his records,
  not in this registry's canon claims.
- The eleven stay sealed: no names, no order. Any proposal claiming to
  name or order them is refused outright.

Each grouping form carries exactly the essence canon gives it. Where
canon is silent (the nature/domain of school, pack, herd, flock), the
registry says so plainly — "awaiting Chauncey's word" — rather than
inventing one.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Mapping, Optional


class GroupingError(ValueError):
    """The grouping discipline was violated."""


# The mass-grouping forms of Chauncey's organizing instinct. Forms, not
# names: the form says HOW a grouping gathers; the name is his.
GROUPING_FORMS = ("hive", "school", "pack", "herd", "flock")

# Essence per form — only what canon says. Canon-silent natures/domains
# are marked awaiting his word, never invented.
FORM_ESSENCES: Dict[str, Dict[str, str]] = {
    "hive": {
        "essence": (
            "the builders' grouping — the ones who make. Inside the "
            "Legion, not the whole."
        ),
        "domain": "making: fabrication, construction, the workshop line",
        "provenance": "Chauncey's word; levi.hive — distributed retention for the legion's learnings",
    },
    "school": {
        "essence": "a mass-grouping form of intelligence — nature awaiting Chauncey's word",
        "domain": "awaiting Chauncey's word",
        "provenance": "form only; essence unwritten",
    },
    "pack": {
        "essence": "a mass-grouping form of intelligence — nature awaiting Chauncey's word",
        "domain": "awaiting Chauncey's word",
        "provenance": "form only; essence unwritten",
    },
    "herd": {
        "essence": "a mass-grouping form of intelligence — nature awaiting Chauncey's word",
        "domain": "awaiting Chauncey's word",
        "provenance": "form only; essence unwritten",
    },
    "flock": {
        "essence": "a mass-grouping form of intelligence — nature awaiting Chauncey's word",
        "domain": "awaiting Chauncey's word",
        "provenance": "form only; essence unwritten",
    },
}

# The sealing law, verbatim: the eleven stay sealed — no names, no order.
SEALED_LAW = (
    "The eleven stay sealed: no names, no order. Nothing in this registry "
    "names, orders, or claims any of the eleven."
)

# Markers that would claim sealed standing — refused in any proposal name
# or essence. (The sealed identities themselves are never listed: listing
# them would be naming them.)
SEALED_CLAIM_MARKERS = ("the eleven", "sealed", "originals", "first order")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Grouping:
    """One proposed grouping: form + proposed name + essence + standing."""

    form: str
    name: str
    essence: str
    domain: str
    proposed_by: str
    proposed_on: str = ""
    status: str = "proposed"
    standing_note: str = (
        "proposed — not canon. Names are Chauncey's; only his word declares one."
    )

    def __post_init__(self) -> None:
        if self.form not in GROUPING_FORMS:
            raise GroupingError(
                f"unknown grouping form {self.form!r}: forms are "
                f"{', '.join(GROUPING_FORMS)}"
            )
        if not self.name or not self.name.strip():
            raise GroupingError(
                "a grouping proposal must carry a name (the proposer's own)"
            )
        if not self.proposed_by or not self.proposed_by.strip():
            raise GroupingError("a grouping proposal must say who proposed it")
        lowered = f"{self.name} {self.essence}".lower()
        for marker in SEALED_CLAIM_MARKERS:
            if marker in lowered:
                raise GroupingError(
                    f"refused: the proposal claims sealed standing ({marker!r}) — "
                    + SEALED_LAW
                )
        if not self.proposed_on:
            self.proposed_on = _utcnow()

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, str]) -> "Grouping":
        return cls(
            **{
                k: data[k]
                for k in (
                    "form",
                    "name",
                    "essence",
                    "domain",
                    "proposed_by",
                    "proposed_on",
                    "status",
                    "standing_note",
                )
                if k in data
            }
        )


class GroupingRegistry:
    """Propose-only registry of Legion groupings.

    ``propose`` records a grouping as proposed — never canon, never
    sealed. ``declare`` is Chauncey's gate: only his word installs a
    declaration, and it lands in the declared list, separate from
    proposals. Persistence is a JSONL file the caller owns (the CLI
    keeps it under ``$LEVI_HOME/universe/``; tests use tmp dirs).
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path
        self.proposed: List[Grouping] = []
        self.declared: List[Grouping] = []
        if path is not None and path.exists():
            self.load()

    # -- proposals ------------------------------------------------------

    def propose(
        self,
        name: str,
        form: str,
        essence: str = "",
        domain: str = "",
        proposed_by: str = "",
    ) -> Grouping:
        """Propose a grouping. Recorded as proposed — never canon."""
        if not essence or not essence.strip():
            base = FORM_ESSENCES[form] if form in FORM_ESSENCES else None
            essence = (
                base["essence"] if base else ""
            ) or "essence unwritten — awaiting the proposer's word"
        if not domain or not domain.strip():
            base = FORM_ESSENCES[form] if form in FORM_ESSENCES else None
            domain = (base["domain"] if base else "") or "awaiting Chauncey's word"
        grouping = Grouping(
            form=form,
            name=name,
            essence=essence,
            domain=domain,
            proposed_by=proposed_by,
        )
        self.proposed.append(grouping)
        return grouping

    # -- the gate --------------------------------------------------------

    def declare(self, grouping: Grouping, declared_by: str) -> Grouping:
        """Chauncey's gate: only his word declares a grouping.

        Raises for anyone else — the proposal stays proposed.
        """
        if declared_by != "Chauncey":
            raise GroupingError(
                "only Chauncey's word declares a grouping — this stays proposed"
            )
        declared = Grouping(
            form=grouping.form,
            name=grouping.name,
            essence=grouping.essence,
            domain=grouping.domain,
            proposed_by=grouping.proposed_by,
            proposed_on=grouping.proposed_on,
            status="declared",
            standing_note="declared by Chauncey's word — canon",
        )
        # The proposal graduates: it leaves the proposed list and takes
        # its declared standing, with its original provenance intact.
        try:
            self.proposed.remove(grouping)
        except ValueError:
            pass
        self.declared.append(declared)
        return declared

    # -- persistence -----------------------------------------------------

    def save(self) -> Path:
        if self.path is None:
            raise GroupingError("no path: this registry was opened in-memory")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            json.dumps({"kind": "proposed", **g.to_dict()}) for g in self.proposed
        ] + [json.dumps({"kind": "declared", **g.to_dict()}) for g in self.declared]
        self.path.write_text(
            "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
        )
        return self.path

    def load(self) -> None:
        assert self.path is not None
        self.proposed, self.declared = [], []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            kind = record.pop("kind", "proposed")
            grouping = Grouping.from_dict(record)
            if kind == "declared":
                self.declared.append(grouping)
            else:
                self.proposed.append(grouping)

    def describe(self) -> Dict[str, object]:
        return {
            "forms": [{"form": f, **FORM_ESSENCES[f]} for f in GROUPING_FORMS],
            "sealed_law": SEALED_LAW,
            "proposed": [g.to_dict() for g in self.proposed],
            "declared": [g.to_dict() for g in self.declared],
        }
