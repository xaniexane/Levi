"""The Indenture: bonded training contracts of the craft guilds.

Origin: apprenticeship in the craft guilds was governed by a bilateral
indenture binding a youth to a master for a fixed term, usually seven
years. The master owed food, lodging, clothing, and full craft
instruction; the apprentice owed exclusive labor, and breaking the
contract was a criminal offense. The indenture was not a wage contract
but a transfer of parental authority with reputational underwriting —
the master was legally liable for the apprentice's debts and conduct,
and instruction was scaffolded from menial mimicry (sweeping, tool
maintenance) to supervised subcomponents, preserving hard-to-codify
tacit knowledge through embodiment rather than text.

What it is in LEVI: ``TrainingContract`` — a master/apprentice binding
with a liability clause. Instruction runs through staged milestones
(mimicry -> subcomponents -> supervised whole); each stage completes
only with the bound master's sign-off, and the master answers for the
apprentice's conduct while the contract is open. The sign-off gate is
the mechanism: no stage may be skipped, and no one but the bound master
may advance the apprentice.

Honesty label: LOAD-BEARING — liability binding + gated staged
advancement is a concrete, transferable mechanism.

Deny-closed inputs: empty master/apprentice names, non-positive term,
unknown stage names, advancing to a non-next stage, advancing without
the master's sign-off, sign-off from anyone but the bound master,
signing off a stage twice or out of order, and logging incidents after
the contract is closed are all rejected with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["TrainingContract", "STAGES"]

#: Instruction scaffold: menial mimicry -> supervised subcomponents ->
#: supervised whole. Embodiment before autonomy.
STAGES = ("mimicry", "subcomponents", "supervised_whole")


@dataclass
class TrainingContract:
    """A bonded training contract between one master and one apprentice.

    The master is liable for the apprentice's conduct while the contract
    is open (``log_incident`` taints the master's record, not some
    abstract ledger). The apprentice advances through ``STAGES`` in
    order; each stage requires the master's sign-off, and the contract
    closes only when the final stage is completed.
    """

    master: str
    apprentice: str
    term_years: int = 7
    _stage_index: int = field(default=0, repr=False)
    _signed: set[str] = field(default_factory=set, repr=False)
    _incidents: list[str] = field(default_factory=list, repr=False)
    _closed: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.master, str) or not self.master.strip():
            raise ValueError("master must be a non-empty string")
        if not isinstance(self.apprentice, str) or not self.apprentice.strip():
            raise ValueError("apprentice must be a non-empty string")
        self.master = self.master.strip()
        self.apprentice = self.apprentice.strip()
        if not isinstance(self.term_years, int) or self.term_years < 1:
            raise ValueError("term_years must be a positive integer")

    # -- the scaffold ---------------------------------------------------
    @property
    def current_stage(self) -> str | None:
        """The stage awaiting completion, or None once the contract closed."""
        if self._closed:
            return None
        return STAGES[self._stage_index]

    @property
    def is_closed(self) -> bool:
        return self._closed

    def _require_stage(self, stage: str) -> str:
        if not isinstance(stage, str) or stage not in STAGES:
            raise ValueError(f"unknown stage: {stage!r}; expected one of {STAGES}")
        return stage

    def sign_off(self, stage: str, signed_by: str) -> None:
        """The master approves a stage as instructed. Sign-off must name the
        bound master and must arrive in stage order — approval cannot be
        banked for a later stage while an earlier one is unfinished."""
        stage = self._require_stage(stage)
        if self._closed:
            raise ValueError("contract is closed; no further sign-off possible")
        if not isinstance(signed_by, str) or signed_by.strip() != self.master:
            raise ValueError(
                f"sign-off must come from the bound master {self.master!r}"
            )
        if stage != STAGES[self._stage_index]:
            raise ValueError(
                f"sign-off out of order: current stage is "
                f"{STAGES[self._stage_index]!r}, not {stage!r}"
            )
        if stage in self._signed:
            raise ValueError(f"stage {stage!r} is already signed off")
        self._signed.add(stage)

    def advance(self) -> str:
        """Complete the current stage and move to the next. Requires the
        master's sign-off for the current stage first; stages cannot be
        skipped. Returns the completed stage."""
        if self._closed:
            raise ValueError("contract is closed; nothing left to advance")
        stage = STAGES[self._stage_index]
        if stage not in self._signed:
            raise ValueError(
                f"cannot advance past {stage!r} without the master's sign-off"
            )
        self._stage_index += 1
        if self._stage_index >= len(STAGES):
            self._closed = True
        return stage

    # -- the liability clause --------------------------------------------
    def log_incident(self, description: str) -> None:
        """Record apprentice misconduct. The master answers for it — the
        incident lands on the master's record while the contract is open."""
        if self._closed:
            raise ValueError("contract is closed; the master is no longer liable")
        if not isinstance(description, str) or not description.strip():
            raise ValueError("incident description must be a non-empty string")
        self._incidents.append(description.strip())

    def master_record(self) -> dict:
        """The master's liability record under this contract."""
        return {
            "master": self.master,
            "apprentice": self.apprentice,
            "incidents": list(self._incidents),
            "closed": self._closed,
        }

    def summary(self) -> dict:
        return {
            "master": self.master,
            "apprentice": self.apprentice,
            "term_years": self.term_years,
            "current_stage": self.current_stage,
            "stages_signed": sorted(self._signed, key=STAGES.index),
            "closed": self._closed,
        }
