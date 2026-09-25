"""The Forge content machine — content creation as interpenetrating twin-pairs.

The L.W.P. writing engine is the dynasty's expander; this module is the
press the operators run. Briefs in, finished content out — grown, not
pipelined.

There is no linear stage walk. A run is N interpenetrating PASSES over the
canon twin-pairs (``levi.lwp.twinpair``):

- **Echo x Mandella** — echo expands the draft into variants; mandella
  stakes one under fog and phantom-runs the unchosen angles.
- **REIM x RIEM** — draft failures are composted into lessons (REIM) and
  grown into genome guards (RIEM).

Each pass builds material ``{"id", "kind", "text", "failures", "domain":
"write"}`` from the current draft and runs the Expander over CANON_PAIRS
with rounds=1 — the machine owns the pass count, so the expander's
born-feedback loop stays off and every PairResult describes the machine's
own material.
Every PairResult is applied through the binding rail —

    Plan -> Preview -> Permission -> Execute -> Verify -> Receipt

— through :class:`levi.policy.gates.PolicyEngine`; the machine invents no
rail of its own. Each twin's application becomes StageRecord entries
(``stage`` is the pair name + pass, e.g. ``"echo_mandella:pass1"``) with
receipts on everything, appended to a JSONL ledger. Refused pairs are
recorded in the dossier as veto verdicts and never forced. Phantoms go to
the dossier and the :class:`levi.lwp.symbiosis.SymbioticLedger`; compost
lessons go to the ledger as compost records.

``STAGES`` / ``STAGE_SPEC`` remain as data: the declared pressures, seats,
and risks the pair-passes draw their operators from. Alpha first, Omega
last, Levi head of the machine — the draft assembly runs under Levi's
pressure, the publish seal under Omega's. Seats are reassignable data.

The L.W.P. engine's Direction / Phase / Power is honored at draft assembly
through :class:`levi.lwp.model_engine.LWPModelEngine` — the draft is
assembled under the brief's direction, phase, and power, offline and
deterministically.

Honest contract
---------------
* Everything here is local and deterministic: seeded text assembly, the
  L.W.P. model engine's own templates, the twin-pair expansions, and the
  king platform helpers. No model call, no network, no engagement promises.
* ``published`` means sealed + receipted + ready for a publishing surface
  (e.g. the king social plugins). This machine never touches a network.
* Nothing publishes without explicit human permission: the publish seal is
  RiskLevel.HIGH (above the machine's auto-approve ceiling), and
  :meth:`ContentMachine.publish` additionally requires the seal to carry an
  explicit operator approval — even if a permissive PolicyEngine was
  injected. Deny or skip the gate and publish raises
  :class:`PublishPermissionError`, always.

Revival laws hold: this is an original LEVI-native composition — never a
copy, never a mask, never reverse-engineered.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json
import random
import re
import uuid

from levi.policy.gates import (
    ActionProposal,
    ActionStatus,
    PolicyEngine,
    Receipt,
    RiskLevel,
)
from levi.lwp.model_engine import DIRS, PHASES, POWERS, LWPModelEngine
from levi.lwp.twinpair import (
    CANON_PAIRS,
    ECHO_MANDELLA,
    REIM_RIEM,
    Expander,
    TwinPair,
)
from levi.lwp.symbiosis import SymbioticLedger
from levi.founders.roster import current_nature, get_seat

DEFAULT_LEDGER = Path.home() / ".levi" / "lwp_machine" / "ledger.jsonl"

#: Declared press pressures, in canonical order. Data — the machine no
#: longer walks this tuple; pair-passes draw their operators, seats, and
#: declared risks from it.
STAGES = ("ideation", "drafting", "revision", "polish", "publish_ready")

#: Per-pressure spec: operator seat (Founders' Roster key), rail risk, and
#: the seat's charge on the line. Alpha first, Omega last, Levi heads the
#: machine. Twin-pairs draw operators through _TWIN_SLOTS below.
STAGE_SPEC: Dict[str, Dict[str, Any]] = {
    "ideation": {
        "seat": "alpha",
        "risk": RiskLevel.LOW,
        "charge": "First mind: draw candidate angles from the brief and seat one.",
    },
    "drafting": {
        "seat": "levi",
        "risk": RiskLevel.MODERATE,
        "charge": "Head of the machine: draft under the brief's Direction/Phase/Power.",
    },
    "revision": {
        "seat": "echo",
        "risk": RiskLevel.LOW,
        "charge": "Tighten the draft: dedupe, trim, hold the meaning.",
    },
    "polish": {
        "seat": "mandella",
        "risk": RiskLevel.LOW,
        "charge": "Polish the copy and validate it against the platform spec.",
    },
    "publish_ready": {
        "seat": "omega",
        "risk": RiskLevel.HIGH,
        "charge": (
            "The culmination: seal the dossier for release. "
            "Nothing publishes without explicit human permission."
        ),
    },
}

#: Which declared pressure each twin operates under. Echo tightens and
#: expands (revision's pressure); Mandella stakes and validates (polish's);
#: REIM composts under the first mind (ideation's); RIEM grows the genome
#: under the head of the machine (drafting's). Seat overrides on these
#: pressures reassign the twins' operators.
_TWIN_SLOTS: Dict[str, str] = {
    ECHO_MANDELLA.twin_a.name: "revision",
    ECHO_MANDELLA.twin_b.name: "polish",
    REIM_RIEM.twin_a.name: "ideation",
    REIM_RIEM.twin_b.name: "drafting",
}


#: Stage-label namespace for a twin-pair: the pair's verbatim name
#: normalized (× → _) so receipts read ``echo_mandella:pass1``. Veto and
#: PairResult records keep the twinpair module's verbatim name.
def _pair_stage(pair_name: str) -> str:
    return pair_name.replace("×", "_")


#: Declared pressure the draft assembly runs under (Levi heads the machine).
_ASSEMBLY_SLOT = "drafting"
#: Rail risk of the draft assembly: above the machine's auto-approve ceiling,
#: so the first human gate stands where drafting's used to.
_ASSEMBLY_RISK = RiskLevel.MODERATE
#: Declared pressure of the publish seal (Omega culminates).
_SEAL_SLOT = "publish_ready"
#: Rail risk of the seal: always a human gate.
_SEAL_RISK = RiskLevel.HIGH

KINDS = ("manuscript", "social", "prose", "reversible")


class PublishPermissionError(PermissionError):
    """Raised when publish is attempted without explicit human permission."""


class BriefError(ValueError):
    """Raised when a production brief fails validation."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rng(seed: str) -> random.Random:
    h = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16], 16)
    return random.Random(h)


def _words(t: str) -> int:
    return len([w for w in (t or "").split() if w])


# ---------------------------------------------------------------------------
# Briefs in
# ---------------------------------------------------------------------------


@dataclass
class ProductionBrief:
    """A production brief: the single input the press machine accepts."""

    title: str
    brief_text: str
    kind: str = "prose"  # manuscript | social | prose | reversible
    platform: Optional[str] = None  # e.g. "linkedin" (social kind)
    direction: str = "forward"
    phase: str = "gold_push"
    power: str = "gain"
    pov: Optional[str] = None
    genres: List[str] = field(default_factory=list)
    target_words: Optional[int] = None
    angles: List[str] = field(default_factory=list)
    # Optional dramatis personae: when set, the press mints this many
    # characters from the L.W.P. character graph at draft assembly
    # (manuscript/prose kinds only). Additive metadata — the draft text is
    # identical with or without a cast; cast_size is deliberately NOT part
    # of seed() so minting can never perturb the draft.
    cast_size: Optional[int] = None

    def validate(self) -> "ProductionBrief":
        if not isinstance(self.title, str) or not self.title.strip():
            raise BriefError("brief title must be a non-empty string")
        if not isinstance(self.brief_text, str) or not self.brief_text.strip():
            raise BriefError("brief_text must be a non-empty string")
        if self.kind not in KINDS:
            raise BriefError(f"kind must be one of {KINDS}, got {self.kind!r}")
        if self.direction not in DIRS:
            raise BriefError(
                f"direction {self.direction!r} unknown — choose: "
                + ", ".join(sorted(DIRS))
            )
        if self.phase not in PHASES:
            raise BriefError(
                f"phase {self.phase!r} unknown — choose: " + ", ".join(sorted(PHASES))
            )
        if self.power not in POWERS:
            raise BriefError(
                f"power {self.power!r} unknown — choose: " + ", ".join(sorted(POWERS))
            )
        if self.platform is not None:
            from levi.king.content_machine import parse_platform

            parse_platform(self.platform)  # raises ValueError when unknown
        if self.target_words is not None and (
            not isinstance(self.target_words, int) or self.target_words <= 0
        ):
            raise BriefError("target_words must be a positive int or None")
        for name in ("genres", "angles"):
            vals = getattr(self, name)
            if not isinstance(vals, list) or any(not isinstance(v, str) for v in vals):
                raise BriefError(f"{name} must be a list of strings")
        if self.cast_size is not None:
            if isinstance(self.cast_size, bool) or not isinstance(self.cast_size, int):
                raise BriefError("cast_size must be a positive int or None")
            if not 1 <= self.cast_size <= 12:
                raise BriefError("cast_size must be 1-12 (a bounded dramatis personae)")
            if self.kind not in ("manuscript", "prose"):
                raise BriefError(
                    f"cast_size applies to manuscript/prose kinds, not {self.kind!r}"
                )
        return self

    def seed(self) -> str:
        """Deterministic seed: identical briefs draft identically."""
        payload = "|".join(
            [
                self.title.strip(),
                self.brief_text.strip(),
                self.kind,
                self.platform or "",
                self.direction,
                self.phase,
                self.power,
                ",".join(self.genres),
                str(self.target_words or ""),
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Run + pair-pass records
# ---------------------------------------------------------------------------


@dataclass
class StageRecord:
    stage: str  # "draft_assembly" | "<pair>:pass<n>" | "publish_ready"
    seat_key: str
    seat_nature: str  # ai | si | mssi — read live per the fluidity law
    proposal_id: str
    receipt_id: str
    explicit_approval: bool
    verified: bool
    twin: str = ""  # twin that worked the act ("" for assembly/seal)
    notes: List[str] = field(default_factory=list)
    output_words: int = 0
    risk: str = "LOW"  # rail RiskLevel name for this act
    finished_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PressRun:
    run_id: str
    brief: Dict[str, Any]
    seats: Dict[str, str]  # declared pressure -> roster seat key, snapshotted
    passes: int = 2
    act_plan: List[Dict[str, Any]] = field(default_factory=list)
    act_index: int = 0  # next act in act_plan to run
    assembly_planned: bool = False
    passes_planned: int = 0
    seal_planned: bool = False
    records: List[StageRecord] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)  # accumulated draft failures
    composted: List[str] = field(default_factory=list)  # failures already composted
    phantoms: List[Dict[str, Any]] = field(default_factory=list)
    compost: List[Dict[str, Any]] = field(default_factory=list)
    vetoes: List[Dict[str, Any]] = field(default_factory=list)
    born: List[Dict[str, Any]] = field(default_factory=list)
    # The dramatis personae minted at draft assembly when the brief
    # declared cast_size (manuscript/prose kinds). Additive metadata —
    # the draft text is identical with or without a cast.
    cast: List[Dict[str, Any]] = field(default_factory=list)
    expansions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    status: str = (
        "running"  # running|awaiting_approval|needs_attention|sealed|published|denied
    )
    pending_proposal_id: Optional[str] = None
    pending_stage: Optional[str] = None
    pending_preview: Optional[Dict[str, Any]] = None
    pending_act: Optional[Dict[str, Any]] = None
    final_text: str = ""
    seal: str = ""
    publish_receipt_id: Optional[str] = None
    created_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["records"] = [r.to_dict() for r in self.records]
        return d


# ---------------------------------------------------------------------------
# The machine
# ---------------------------------------------------------------------------


class ContentMachine:
    """The press: briefs in, finished content out, receipts on everything.

    A run is ``passes`` interpenetrating pair-passes over CANON_PAIRS. Each
    twin's application runs the binding rail through the PolicyEngine; twins
    whose risk exceeds the auto-approve ceiling halt for explicit human
    approval via :meth:`approve` / :meth:`deny`. The draft assembly and the
    publish seal are their own rail acts. :meth:`publish` releases a sealed
    run only after the seal carries an explicit human approval.
    """

    def __init__(
        self,
        ledger_path: Optional[Path] = None,
        policy: Optional[PolicyEngine] = None,
    ):
        self.ledger_path = Path(ledger_path) if ledger_path else DEFAULT_LEDGER
        # The machine's own ceiling: LOW and below may auto-approve.
        # Assembly (MODERATE), the seal (HIGH), and twins above LOW halt.
        self.policy = (
            policy
            if policy is not None
            else PolicyEngine(auto_approve_up_to=RiskLevel.LOW)
        )
        self._runs: Dict[str, PressRun] = {}
        self._proposal_runs: Dict[str, str] = {}
        # Proposals approved through the human path (approve()). publish()
        # requires the seal proposal to be in this set — this is the
        # machine-level invariant, independent of the engine's ceiling.
        self._explicit_approvals: set = set()
        # Run store: runs, proposal routing, explicit approvals, and the
        # policy engine's own proposals/receipts persist as JSON beside the
        # ledger so the `levi lwp` console can approve, deny, and publish
        # across separate invocations. The store is per ledger file
        # (ledger stem + ".store.json"), so two machines on different
        # ledgers never share state.
        self._owns_policy = policy is None
        self.store_path = self.ledger_path.parent / (
            self.ledger_path.stem + ".store.json"
        )
        # Seats are reassignable data — but the reassignment is per-machine,
        # not per-module: each machine works its own copy of STAGE_SPEC so
        # one machine's `seat()` can never leak into another machine sharing
        # the process. Overrides persist in the store (per ledger) so they
        # hold across separate `levi lwp` invocations; in-flight runs keep
        # the seats they started with (snapshotted at run_brief).
        self.stage_spec = {stage: dict(spec) for stage, spec in STAGE_SPEC.items()}
        self._seat_overrides: Dict[str, str] = {}
        self._symbiosis: Optional[SymbioticLedger] = None
        self._load_store()
        for _stage, _seat in self._seat_overrides.items():
            if _stage in self.stage_spec:
                self.stage_spec[_stage]["seat"] = _seat

    @property
    def symbiosis(self) -> SymbioticLedger:
        """The organism's residue ledger (phantoms + compost), per ledger file."""
        if self._symbiosis is None:
            self._symbiosis = SymbioticLedger(
                directory=self.ledger_path.parent
                / (self.ledger_path.stem + ".symbiosis")
            )
        return self._symbiosis

    @property
    def _born_dir(self) -> Path:
        """Born-registry dir for the Expander, per ledger file.

        The expander appends born entries to a registry on disk; pointing
        it here keeps runs hermetic (no HOME writes) and scoped to the
        ledger, mirroring the symbiosis dir above.
        """
        return self.ledger_path.parent / (self.ledger_path.stem + ".born")

    @property
    def _characters_path(self) -> Path:
        """Ledger-scoped character graph file (hermetic like symbiosis/born).

        The dramatis personae a brief asks for persist beside the ledger,
        never in HOME — one graph per press ledger.
        """
        return self.ledger_path.parent / (self.ledger_path.stem + ".characters.json")

    def _mint_cast(self, brief: "ProductionBrief") -> List[Dict[str, Any]]:
        """Mint the brief's dramatis personae from the character graph.

        Deterministic: character ``i`` is minted with seed
        ``f"{brief.seed()}|cast|{i}"``, so identical briefs mint identical
        casts. The mint happens AFTER draft assembly (see _draft) and
        cast_size is not part of brief.seed() — minting can never perturb
        the draft text. Raises nothing the brief validation didn't already
        rule out; a mint failure would surface as an assembly failure.
        """
        from levi.lwp.character_graph import CharacterGraph

        graph = CharacterGraph(path=self._characters_path)
        out = []
        for i in range(brief.cast_size or 0):
            node = graph.mint(seed=f"{brief.seed()}|cast|{i}")
            out.append(asdict(node))
        return out

    # -- run store (persistence across invocations) ----------------------
    @staticmethod
    def _run_from_dict(d: Dict[str, Any]) -> "PressRun":
        dd = dict(d)
        dd.pop("stage_index", None)  # pre-interpenetration field, retired
        dd.pop("pass_failed", None)  # interim field, retired
        recs = [StageRecord(**r) for r in dd.get("records", [])]
        dd["records"] = recs
        return PressRun(**dd)

    @staticmethod
    def _proposal_from_dict(d: Dict[str, Any]) -> ActionProposal:
        dd = dict(d)
        dd["risk_level"] = RiskLevel(dd["risk_level"])
        dd["status"] = ActionStatus(dd["status"])
        return ActionProposal(**dd)

    def _load_store(self) -> None:
        if not self.store_path.exists():
            return
        try:
            payload = json.loads(self.store_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RuntimeError(
                f"lwp press store unreadable at {self.store_path}: {exc}"
            ) from exc
        for run_id, rd in (payload.get("runs") or {}).items():
            self._runs[run_id] = self._run_from_dict(rd)
        self._proposal_runs.update(payload.get("proposal_runs") or {})
        for pid in payload.get("explicit_approvals") or []:
            self._explicit_approvals.add(pid)
        self._seat_overrides.update(payload.get("seat_overrides") or {})
        # The policy engine's proposals live in its own memory; restore
        # them so a later invocation can approve/deny/complete what an
        # earlier one proposed. Only when the machine owns the engine —
        # an injected policy belongs to its caller.
        if self._owns_policy:
            pol = payload.get("policy") or {}
            for pid, pd in (pol.get("pending") or {}).items():
                self.policy._pending[pid] = self._proposal_from_dict(pd)
            self.policy._history.extend(
                self._proposal_from_dict(p) for p in pol.get("history") or []
            )
            for rid, rd in (pol.get("receipts") or {}).items():
                self.policy._receipts[rid] = Receipt(**rd)

    def _save_store(self) -> None:
        payload = {
            "runs": {rid: r.to_dict() for rid, r in self._runs.items()},
            "proposal_runs": self._proposal_runs,
            "explicit_approvals": sorted(self._explicit_approvals),
            "seat_overrides": dict(self._seat_overrides),
            "policy": {
                "pending": {
                    pid: p.to_dict() for pid, p in self.policy._pending.items()
                },
                "history": [p.to_dict() for p in self.policy._history],
                "receipts": {
                    rid: asdict(r) for rid, r in self.policy._receipts.items()
                },
            },
        }
        try:
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.store_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
            tmp.replace(self.store_path)
        except OSError:
            pass  # store is best-effort like the ledger; memory stays live

    # -- ledger ---------------------------------------------------------
    def _ledger(self, event: str, run: PressRun, **extra: Any) -> None:
        entry = {
            "ts": _utcnow(),
            "event": event,
            "run_id": run.run_id,
            "status": run.status,
            **extra,
        }
        try:
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with self.ledger_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except OSError:
            pass  # ledger is best-effort; the run record is authoritative

    # -- seats ----------------------------------------------------------
    def seat(self, stage: str, seat_key: str) -> Dict[str, str]:
        """Reassign a declared pressure's operator seat (Founders' Roster key).

        Twin-pairs draw their operators through these pressures (see
        _TWIN_SLOTS), so reassigning e.g. ``polish`` reassigns Mandella's
        stake. The override is stored per-ledger in the press store, so it
        holds across separate invocations; runs already briefed keep the
        seats they started with.
        """
        if stage not in self.stage_spec:
            raise ValueError(f"unknown stage {stage!r} — choose: " + ", ".join(STAGES))
        try:
            seat = get_seat(seat_key)
        except KeyError:
            raise ValueError(f"unknown roster seat {seat_key!r}") from None
        self.stage_spec[stage]["seat"] = seat_key
        self._seat_overrides[stage] = seat_key
        self._save_store()
        return {
            "stage": stage,
            "seat": seat_key,
            "nature": current_nature(seat_key),
            "role": seat.role,
        }

    def seats(self) -> Dict[str, Dict[str, str]]:
        """Current seat assignments with live natures (fluidity law)."""
        return {
            stage: {
                "seat": spec["seat"],
                "nature": current_nature(spec["seat"]),
                "risk": spec["risk"].name,
                "charge": spec["charge"],
            }
            for stage, spec in self.stage_spec.items()
        }

    # -- briefs in ------------------------------------------------------
    def run_brief(self, brief: ProductionBrief, passes: int = 2) -> PressRun:
        """Accept a brief and run pair-passes until a human gate or the seal."""
        brief.validate()
        if not isinstance(passes, int) or passes < 1:
            raise BriefError("passes must be a positive int")
        run = PressRun(
            run_id=str(uuid.uuid4())[:8],
            brief=brief.to_dict(),
            seats={s: self.stage_spec[s]["seat"] for s in STAGES},
            passes=passes,
        )
        self._runs[run.run_id] = run
        self._ledger(
            "brief_received", run, title=brief.title, kind=brief.kind, passes=passes
        )
        self._continue(run)
        self._save_store()
        return run

    def get_run(self, run_id: str) -> PressRun:
        try:
            return self._runs[run_id]
        except KeyError:
            raise ValueError(f"unknown run {run_id!r}") from None

    def pending(self) -> List[Dict[str, Any]]:
        """Proposals awaiting a human decision across all runs."""
        out = []
        for run in self._runs.values():
            if run.pending_proposal_id:
                out.append(
                    {
                        "run_id": run.run_id,
                        "proposal_id": run.pending_proposal_id,
                        "stage": run.pending_stage,
                        "preview": run.pending_preview,
                    }
                )
        return out

    # -- the rail -------------------------------------------------------
    def _assembly_act(self, run: PressRun) -> Dict[str, Any]:
        return {
            "label": "draft_assembly",
            "stage": "draft_assembly",
            "seat_key": run.seats[_ASSEMBLY_SLOT],
            "risk": int(_ASSEMBLY_RISK),
            "kind": "assembly",
            "pair_name": "",
            "twin_name": "",
            "pass_no": 0,
        }

    def _twin_act(
        self, run: PressRun, pair: TwinPair, twin_name: str, pass_no: int
    ) -> Dict[str, Any]:
        slot = _TWIN_SLOTS.get(twin_name, "revision")
        risk = next(
            (t.risk for t in (pair.twin_a, pair.twin_b) if t.name == twin_name), 1
        )
        # The rail's risk enum is 0-4; a twin declaring outside it is read
        # at the nearest rail, never as a crash.
        risk = max(0, min(4, int(risk)))
        stage = f"{_pair_stage(pair.name)}:pass{pass_no}"
        return {
            "label": f"{stage}:{twin_name}",
            "stage": stage,
            "seat_key": run.seats[slot],
            "risk": risk,
            "kind": "twin",
            "pair_name": pair.name,
            "twin_name": twin_name,
            "pass_no": pass_no,
        }

    def _seal_act(self, run: PressRun) -> Dict[str, Any]:
        return {
            "label": "publish_ready",
            "stage": "publish_ready",
            "seat_key": run.seats[_SEAL_SLOT],
            "risk": int(_SEAL_RISK),
            "kind": "seal",
            "pair_name": "",
            "twin_name": "",
            "pass_no": 0,
        }

    def _plan_for(self, act: Dict[str, Any], run: PressRun) -> str:
        b = run.brief
        seat = act["seat_key"]
        nature = current_nature(seat)  # fluidity law: read live at plan time
        kind = act["kind"]
        if kind == "assembly":
            return (
                f"{seat} ({nature}) assembles the draft of '{b['title']}' "
                f"({b['kind']}) under L.W.P. "
                f"{b['direction']}/{b['phase']}/{b['power']}."
            )
        if kind == "seal":
            return (
                f"{seat} ({nature}) seals the dossier for release. "
                "NOTHING publishes without your explicit approval."
            )
        pair, twin, pno = act["pair_name"], act["twin_name"], act["pass_no"]
        if twin == ECHO_MANDELLA.twin_a.name:
            return (
                f"{seat} ({nature}) expands the pass-{pno} draft into "
                f"variants ({pair})."
            )
        if twin == ECHO_MANDELLA.twin_b.name:
            return (
                f"{seat} ({nature}) stakes the pass-{pno} variants under fog; "
                f"unchosen angles become phantoms ({pair})."
            )
        if twin == REIM_RIEM.twin_a.name:
            return (
                f"{seat} ({nature}) composts pass-{pno} draft failures into "
                f"lessons ({pair})."
            )
        if twin == REIM_RIEM.twin_b.name:
            return (
                f"{seat} ({nature}) grows the pass-{pno} compost into genome "
                f"guards ({pair})."
            )
        return f"{seat} ({nature}) works the {pair} seam, pass {pno}."

    def _run_act(self, run: PressRun, act: Dict[str, Any]) -> bool:
        """Drive one rail act through Plan->Preview->Permission->Execute->Verify->Receipt.

        Returns True when the run halts (awaiting human, or needs attention).
        """
        risk = RiskLevel(act["risk"])
        plan = self._plan_for(act, run)
        proposal = self.policy.propose(
            description=f"[{run.run_id}] {act['label']}: {plan}",
            risk_level=risk,
            reason=f"Forge press, {act['label']} of '{run.brief['title']}'",
            affected_systems=["lwp-press"],
            reversible=True,
        )
        preview = self.policy.preview(proposal.id)
        self._proposal_runs[proposal.id] = run.run_id
        decided = self.policy.request_permission(proposal.id)
        if decided.status == ActionStatus.AWAITING_PERMISSION:
            run.pending_proposal_id = proposal.id
            run.pending_stage = act["label"]
            run.pending_preview = preview
            run.pending_act = act
            run.status = "awaiting_approval"
            self._ledger(
                "gate_awaiting", run, stage=act["label"], proposal_id=proposal.id
            )
            return True
        # Auto-approved by policy (risk at/below the machine ceiling).
        self._execute_and_receipt(run, act, proposal.id, explicit=False)
        run.act_index += 1
        return run.status in ("needs_attention", "denied")

    def _execute_and_receipt(
        self, run: PressRun, act: Dict[str, Any], proposal_id: str, explicit: bool
    ) -> StageRecord:
        """Execute the act, verify, issue the receipt. Never skips verify."""
        seat_key = act["seat_key"]
        nature = current_nature(seat_key)  # fluidity law: read live at execution
        output, verified, notes = self._execute_act(run, act)
        stage = act["stage"]
        receipt = self.policy.mark_completed(
            proposal_id,
            result_summary=f"{act['label']} complete: {'; '.join(notes) or 'ok'}",
            verified=verified,
            details={
                "stage": stage,
                "label": act["label"],
                "seat": seat_key,
                "seat_nature": nature,
                "explicit_approval": explicit,
                "output_words": _words(output) if stage != "publish_ready" else 0,
                # The dramatis personae ride the assembly receipt: the ids
                # the press minted for this run, auditable against the
                # ledger-scoped character graph. Other stages carry [].
                "cast": (
                    [c["id"] for c in run.cast] if stage == "draft_assembly" else []
                ),
            },
        )
        record = StageRecord(
            stage=stage,
            seat_key=seat_key,
            seat_nature=nature,
            proposal_id=proposal_id,
            receipt_id=receipt.id,
            explicit_approval=explicit,
            verified=verified,
            twin=act.get("twin_name", ""),
            notes=notes,
            output_words=_words(output) if stage != "publish_ready" else 0,
            risk=RiskLevel(act["risk"]).name,
        )
        run.records.append(record)
        run.pending_proposal_id = None
        run.pending_stage = None
        run.pending_preview = None
        run.pending_act = None
        if not verified:
            if act["kind"] in ("assembly", "seal"):
                # Broken before the pairs (or at the seal): halt now.
                run.status = "needs_attention"
            # A twin stumble accumulates in run.failures; later passes'
            # REIM×RIEM composts it. The pass — and the run — continue.
        elif act["kind"] == "seal":
            run.status = "sealed"
            run.seal = hashlib.sha256(run.final_text.encode("utf-8")).hexdigest()
        self._ledger(
            "stage_completed",
            run,
            stage=stage,
            label=act["label"],
            seat=seat_key,
            nature=nature,
            receipt_id=receipt.id,
            verified=verified,
            explicit_approval=explicit,
        )
        return record

    def _extend_plan(self, run: PressRun) -> bool:
        """Append the next chunk of rail acts. True when acts were appended."""
        while True:
            if not run.assembly_planned:
                run.assembly_planned = True
                run.act_plan.append(self._assembly_act(run))
                return True
            if run.passes_planned < run.passes:
                run.passes_planned += 1
                if self._plan_pass(run, run.passes_planned):
                    return True
                continue  # every pair vetoed this pass — never forced; next
            if not run.seal_planned:
                run.seal_planned = True
                run.act_plan.append(self._seal_act(run))
                return True
            return False

    def _continue(self, run: PressRun) -> PressRun:
        while run.status not in ("needs_attention", "denied", "sealed", "published"):
            if run.act_index >= len(run.act_plan):
                if not self._extend_plan(run):
                    return run
                continue
            halted = self._run_act(run, run.act_plan[run.act_index])
            if halted:
                return run
        return run

    # -- pair-passes ----------------------------------------------------
    def _plan_pass(self, run: PressRun, pass_no: int) -> bool:
        """Build material, run the Expander, ingest the report. True if acts.

        One expander round per machine pass: the ContentMachine owns the
        pass count, so the expander's born-feedback loop stays off and
        every PairResult describes the machine's own material.
        """
        brief = ProductionBrief(**run.brief)
        material = {
            "id": f"{run.run_id}:pass{pass_no}",
            "kind": brief.kind,
            "text": run.final_text,
            # REIM×RIEM's fit rule needs failure records; only uncomposted
            # ones go in, as dicts in the shape the organ normalizes.
            "failures": [
                {
                    "what": f,
                    "source": "lwp",
                    "context": brief.kind,
                    "severity": "medium",
                }
                for f in run.failures
                if f not in run.composted
            ],
            "domain": "write",
        }
        expander = Expander(
            seed=brief.seed() + f"|pass{pass_no}", born_dir=self._born_dir
        )
        report = expander.expand(material, pairs=CANON_PAIRS, rounds=1)
        rep = report.to_dict()
        # The failures this pass may compost: exactly what the expander
        # saw. A twin that stumbles mid-pass queues its failure for a
        # LATER pass — the reim act never composts the current pass's own.
        rep["material_failures"] = [f["what"] for f in material["failures"]]
        run.expansions[f"pass{pass_no}"] = rep
        return self._ingest_expansion(run, rep, pass_no)

    @staticmethod
    def _verdict_info(verdict: Any) -> Dict[str, Any]:
        if isinstance(verdict, dict):
            return {
                "pair_name": verdict.get("pair_name", "?"),
                "reason": verdict.get("reason", ""),
                "paired": verdict.get("paired", False),
            }
        return {
            "pair_name": getattr(verdict, "pair_name", "?"),
            "reason": getattr(verdict, "reason", ""),
            "paired": getattr(verdict, "paired", False),
        }

    def _ingest_expansion(
        self, run: PressRun, rep: Dict[str, Any], pass_no: int
    ) -> bool:
        """Record veto verdicts, queue twin acts. Refused pairs are never forced."""
        for verdict in rep.get("refused", []):
            info = self._verdict_info(verdict)
            run.vetoes.append(
                {"pass": pass_no, "pair": info["pair_name"], "reason": info["reason"]}
            )
            self._ledger(
                "pair_vetoed",
                run,
                stage=f"pass{pass_no}",
                pair=info["pair_name"],
                reason=info["reason"],
            )
        by_pair = {p.name: p for p in CANON_PAIRS}
        added = False
        results = rep.get("pair_results", [])
        for idx, pr in enumerate(results):
            pair = by_pair.get(pr.get("pair_name", ""))
            if pair is None:
                continue  # unknown pair: the press does not run strangers
            # Ordinal of this result among the pair's results this pass —
            # the expander may return several rounds per pair.
            ordinal = sum(
                1 for q in results[:idx] if q.get("pair_name") == pr.get("pair_name")
            )
            for twin in (pair.twin_a, pair.twin_b):
                act = self._twin_act(run, pair, twin.name, pass_no)
                act["result_no"] = ordinal
                run.act_plan.append(act)
                added = True
        self._ledger(
            "pass_expanded",
            run,
            stage=f"pass{pass_no}",
            pairs=[pr.get("pair_name") for pr in rep.get("pair_results", [])],
            vetoed=[v["pair"] for v in run.vetoes if v["pass"] == pass_no],
        )
        return added

    def _pair_result_for(self, run: PressRun, act: Dict[str, Any]) -> Dict[str, Any]:
        """The pair result this twin act executes (by ordinal among the
        pair's results this pass)."""
        rep = run.expansions.get(f"pass{act['pass_no']}", {})
        matches = [
            pr
            for pr in rep.get("pair_results", [])
            if pr.get("pair_name") == act["pair_name"]
        ]
        want = act.get("result_no", 0)
        if 0 <= want < len(matches):
            return matches[want]
        raise ValueError(
            f"no {act['pair_name']} result #{want} for pass {act['pass_no']}"
        )

    # -- act execution (deterministic, offline) --------------------------
    def _execute_act(
        self, run: PressRun, act: Dict[str, Any]
    ) -> "tuple[str, bool, List[str]]":
        kind = act["kind"]
        if kind == "assembly":
            return self._assemble(run)
        if kind == "seal":
            return self._seal(run)
        pr = self._pair_result_for(run, act)
        pair_name, twin = act["pair_name"], act["twin_name"]
        if pair_name == ECHO_MANDELLA.name:
            if twin == ECHO_MANDELLA.twin_a.name:
                return self._apply_echo(run, pr, act)
            return self._apply_mandella(run, pr, act)
        if pair_name == REIM_RIEM.name:
            if twin == REIM_RIEM.twin_a.name:
                return self._apply_reim(run, pr, act)
            return self._apply_riem(run, pr, act)
        return "", True, [f"{twin} worked the {pair_name} seam: no press application"]

    def _assemble(self, run: PressRun) -> "tuple[str, bool, List[str]]":
        """Draft assembly: the brief's Direction/Phase/Power honored here."""
        text, ok, notes = self._draft(run)
        if ok:
            run.final_text = text
        return text, ok, notes

    # -- Echo × Mandella -------------------------------------------------
    def _apply_echo(
        self, run: PressRun, pr: Dict[str, Any], act: Dict[str, Any]
    ) -> "tuple[str, bool, List[str]]":
        """Echo expands: the organ's variants are recorded and born."""
        output = pr.get("output") or {}
        variants = [v for v in output.get("variants", []) if isinstance(v, dict)]
        desc = ", ".join(f"{v.get('kind')}:{v.get('label')}" for v in variants)
        notes = [f"echo expanded {len(variants)} variant(s): {desc}"]
        born = pr.get("born") or []
        if born:
            run.born.append(
                {"pass": act["pass_no"], "pair": pr.get("pair_name"), "born": born}
            )
            notes.append(f"{len(born)} angles born")
        verified = bool(variants)
        if not verified:
            failure = f"pass{act['pass_no']} echo expansion failed: no variants"
            run.failures.append(failure)
            notes.append(failure)
        # Echo births angles, not copy — the draft stands.
        return "", verified, notes

    def _dedupe_text(self, text: str) -> str:
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        seen, kept = set(), []
        for s in sents:
            key = s.lower()
            if key in seen:
                continue
            seen.add(key)
            kept.append(s)
        return re.sub(r"[ \t]{2,}", " ", " ".join(kept))

    def _apply_mandella(
        self, run: PressRun, pr: Dict[str, Any], act: Dict[str, Any]
    ) -> "tuple[str, bool, List[str]]":
        """Mandella stakes: the organ already staked the taken variant under
        fog; the press records the stake, validates the staked text, and
        files the unchosen angles as phantoms."""
        output = pr.get("output") or {}
        stakes = output.get("stakes") or {}
        brief = ProductionBrief(**run.brief)
        notes = [
            f"mandella staked '{stakes.get('chosen')}' "
            f"(stake {stakes.get('stake_id')}, "
            f"pressure {stakes.get('pressure')})",
            f"mandella recommended: {stakes.get('mandella_recommended')}",
        ]
        text = run.final_text
        verified = bool(text.strip())
        if brief.platform:
            from levi.king.content_machine import parse_platform, validate_content

            report = validate_content(text, parse_platform(brief.platform))
            notes.append(
                f"platform validation ({brief.platform}): "
                + ("valid" if report["valid"] else f"issues: {report['checks']}")
            )
            verified = verified and bool(report["valid"])
        if not verified:
            failure = (
                f"pass{act['pass_no']} mandella stake failed: "
                f"stake {stakes.get('stake_id')}; " + "; ".join(notes[-2:])
            )
            run.failures.append(failure)
            notes.append("draft held at previous text; failure queued for REIM×RIEM")
        # Phantoms: the unchosen angles — dossier + symbiotic ledger.
        phantoms = pr.get("phantoms") or []
        for ph in phantoms:
            if isinstance(ph, dict):
                label = str(ph.get("label", "unchosen"))
                summary = str(ph.get("summary", ""))
            else:
                label, summary = "unchosen", str(ph)
            entry = {
                "pass": act["pass_no"],
                "pair": pr.get("pair_name"),
                "label": label,
                "summary": summary,
            }
            run.phantoms.append(entry)
            self._file_phantom(run, act, entry)
        notes.append(
            f"{len(phantoms)} phantoms filed to the dossier and symbiotic ledger"
        )
        return text, verified, notes

    def _file_phantom(
        self, run: PressRun, act: Dict[str, Any], entry: Dict[str, Any]
    ) -> None:
        # Unchosen draft angles are filed as phantoms on the organism's own
        # residue ledger — stake → haunt → resolve/compost, never vanished.
        key = f"lwp-{run.run_id}-pass{act['pass_no']}-{_pair_stage(act['pair_name'])}"
        body = {
            "unchosen": str(entry.get("label", ""))[:500],
            "summary": str(entry.get("summary", ""))[:2000],
            "pass": act["pass_no"],
            "pair": act["pair_name"],
            "brief_title": run.brief["title"],
        }
        try:
            self.symbiosis.file_phantom(key, body, provenance="press")
        except OSError as exc:
            entry["ledger_error"] = str(exc)  # residue ledger is best-effort

    # -- REIM × RIEM ------------------------------------------------------
    def _apply_reim(
        self, run: PressRun, pr: Dict[str, Any], act: Dict[str, Any]
    ) -> "tuple[str, bool, List[str]]":
        """REIM composts accumulated draft failures into ledger compost records.

        Only the failures this pass's material carried (earlier passes')
        are composted — a twin that stumbles mid-pass queues its failure
        for a LATER pass. Lessons come from the pair result, aligned with
        the material failures.
        """
        output = pr.get("output") or {}
        lessons = [
            lesson
            for lesson in (output.get("lessons") or [])
            if isinstance(lesson, dict)
        ]
        guards = output.get("guards") or []
        rep = run.expansions.get(f"pass{act['pass_no']}", {})
        material_failures = rep.get("material_failures", []) or []
        targets = [
            (f, lessons[i] if i < len(lessons) else {})
            for i, f in enumerate(material_failures)
            if f in run.failures and f not in run.composted
        ]
        count = 0
        for failure, lesson in targets:
            analysis = str(lesson.get("lesson") or failure)
            retry = ""
            if guards and isinstance(guards[0], dict):
                retry = str(guards[0].get("content", ""))[:500]
            try:
                self.symbiosis.compost(
                    f"lwp-{run.run_id}-pass{act['pass_no']}",
                    failure,
                    analysis,
                    retry,
                )
            except OSError as exc:
                run.compost.append(
                    {
                        "pass": act["pass_no"],
                        "failure": failure[:300],
                        "lesson": f"ledger write failed: {exc}",
                    }
                )
                run.composted.append(failure)
                continue
            run.composted.append(failure)
            run.compost.append(
                {
                    "pass": act["pass_no"],
                    "failure": failure[:300],
                    "lesson": analysis[:500],
                }
            )
            count += 1
        notes = [
            f"reim composted {count} failure(s) ({len(lessons)} lessons from the pair)"
        ]
        return "", True, notes

    def _apply_riem(
        self, run: PressRun, pr: Dict[str, Any], act: Dict[str, Any]
    ) -> "tuple[str, bool, List[str]]":
        """RIEM grows the compost into genome proposals and guards."""
        output = pr.get("output") or {}
        genome = output.get("genome") or {}
        proposals = genome.get("proposals") or []
        guards = output.get("guards") or []
        notes = [
            f"riem grew genome: {genome.get('count', len(proposals))} "
            f"proposal(s), {len(guards)} guard(s)"
        ]
        for g in guards[:4]:
            if isinstance(g, dict):
                notes.append(f"guard: {g.get('content', '')}"[:200])
            else:
                notes.append(f"guard: {g}"[:200])
        born = pr.get("born") or []
        if born:
            run.born.append(
                {"pass": act["pass_no"], "pair": pr.get("pair_name"), "born": born}
            )
        return "", True, notes

    # -- human gates ----------------------------------------------------
    def approve(self, proposal_id: str, note: str = "") -> PressRun:
        """Human approves a pending gate: execute the act, receipt it, advance."""
        run_id = self._proposal_runs.get(proposal_id)
        if run_id is None:
            raise ValueError(
                f"approve: unknown proposal {proposal_id!r} — "
                "proposals leave the pending set once decided"
            )
        run = self._runs[run_id]
        act = run.pending_act or {}
        label = act.get("label") or run.pending_stage or ""
        self.policy.approve(proposal_id, note=note or "approved by operator")
        self._explicit_approvals.add(proposal_id)
        self._ledger(
            "gate_approved",
            run,
            stage=label,
            proposal_id=proposal_id,
            note=note or "approved by operator",
        )
        self._execute_and_receipt(run, act, proposal_id, explicit=True)
        run.act_index += 1
        if run.status == "sealed":
            # The seal is the last act. publish() is the next human act;
            # do not reopen the run.
            self._save_store()
            return run
        if run.status not in ("needs_attention", "denied"):
            run.status = "running"
            self._continue(run)
        self._save_store()
        return run

    def deny(self, proposal_id: str, note: str = "") -> PressRun:
        """Human denies a pending gate: the run stops, denial receipted."""
        run_id = self._proposal_runs.get(proposal_id)
        if run_id is None:
            raise ValueError(f"deny: unknown proposal {proposal_id!r}")
        run = self._runs[run_id]
        self.policy.deny(proposal_id, note=note or "denied by operator")
        run.status = "denied"
        run.pending_proposal_id = None
        run.pending_stage = None
        run.pending_preview = None
        run.pending_act = None
        self._ledger(
            "gate_denied",
            run,
            proposal_id=proposal_id,
            note=note or "denied by operator",
        )
        self._save_store()
        return run

    # -- release --------------------------------------------------------
    def publish(self, run_id: str, note: str = "") -> Dict[str, Any]:
        """Release a sealed run. Raises PublishPermissionError unless the
        seal carries an explicit human approval.

        The release itself runs the rail (CRITICAL): plan, preview, the
        publish() call as recorded execution under the operator's earlier
        explicit publish_ready seal approval, execute, verify, receipt.
        The rail's own approval of its CRITICAL proposal grants no new
        permission — the permission is the seal approval above. The machine
        never posts anywhere — "published" means sealed, receipted, and
        cleared for a publishing surface.
        """
        run = self.get_run(run_id)
        if run.status == "denied":
            raise PublishPermissionError(
                f"run {run_id} was denied at a gate — nothing publishes from a denied run"
            )
        if run.status != "sealed":
            raise PublishPermissionError(
                f"run {run_id} is '{run.status}', not sealed — "
                "complete the press line before publishing"
            )
        seal_records = [r for r in run.records if r.stage == "publish_ready"]
        if not seal_records or not all(
            r.receipt_id and r.proposal_id in self._explicit_approvals
            for r in seal_records
        ):
            raise PublishPermissionError(
                f"run {run_id}: the publish seal was never explicitly "
                "approved by a human — nothing publishes without permission"
            )
        if not all(r.receipt_id for r in run.records):
            receipted = sum(1 for r in run.records if r.receipt_id)
            raise PublishPermissionError(
                f"run {run_id}: receipt chain incomplete — "
                f"{receipted}/{len(run.records)} pair-pass records receipted"
            )
        proposal = self.policy.propose(
            description=f"[{run_id}] publish: release sealed content '{run.brief['title']}'",
            risk_level=RiskLevel.CRITICAL,
            reason="Operator release of publish-ready content",
            affected_systems=["lwp-press", "publishing-surface"],
            reversible=False,
        )
        self.policy.preview(proposal.id)
        # Honest receipting: the permission for this release is the
        # operator's EARLIER explicit publish_ready seal approval (gated on
        # above via _explicit_approvals). This rail approval is the machine
        # receipting its own CRITICAL rail execution — it grants no new
        # permission, so the note must not claim "authorized by operator".
        self.policy.approve(
            proposal.id,
            note=(
                "rail execution of publish() under the operator's earlier "
                "explicit publish_ready seal approval; this rail approval "
                "grants no new permission; "
                f"release note: {note or 'none'}"
            ),
        )
        self._explicit_approvals.add(proposal.id)
        receipt = self.policy.mark_completed(
            proposal.id,
            result_summary=f"published '{run.brief['title']}' ({_words(run.final_text)}w)",
            verified=True,
            details={
                "seal": run.seal,
                "stage_receipts": [r.receipt_id for r in run.records],
                # The permission chain: the seal records whose explicitly
                # human-approved proposals authorized this release.
                "seal_proposal_ids": [r.proposal_id for r in seal_records],
            },
        )
        run.status = "published"
        run.publish_receipt_id = receipt.id
        self._ledger("published", run, receipt_id=receipt.id, seal=run.seal)
        self._save_store()
        return {
            "run_id": run_id,
            "status": run.status,
            "title": run.brief["title"],
            "words": _words(run.final_text),
            "seal": run.seal,
            "receipt_id": receipt.id,
            "stage_receipts": [r.receipt_id for r in run.records],
        }

    # -- draft assembly (Direction / Phase / Power honored) ---------------
    def _draft(self, run: PressRun) -> "tuple[str, bool, List[str]]":
        brief = ProductionBrief(**run.brief)
        if brief.kind == "social":
            text, notes = self._draft_social(brief)
        elif brief.kind == "reversible":
            text, notes = self._draft_reversible(brief)
        else:
            text, notes = self._draft_manuscript(brief)
        meta = (
            f"[L.W.P. {brief.direction}/{brief.phase}/{brief.power} · "
            f"{brief.kind} · draft]"
        )
        ok = _words(text) > 0
        notes = [meta] + notes
        if brief.cast_size and brief.kind in ("manuscript", "prose"):
            # The cast is minted AFTER assembly from a seed independent of
            # the draft — the dramatis personae can never perturb the text.
            # (validate() already confined cast_size to manuscript/prose.)
            run.cast = self._mint_cast(brief)
            dramatis = ", ".join(
                f"{c['name']} ({c['drive']}/{c['wound']})" for c in run.cast
            )
            notes.append(f"cast minted: {dramatis}")
        if brief.angles:
            notes.append(f"angles seated: {', '.join(brief.angles[:3])}")
        return text, ok, notes

    def _draft_reversible(self, brief: ProductionBrief) -> "tuple[str, List[str]]":
        """The press itself as a production kind: print verified books.

        ``target_words`` is read as the number of books (default 3, cap 50);
        the seed derives from the brief so identical briefs press identically.
        """
        from levi.lwp.reversible import (
            CLAUSES,
            press_run,
            reading,
            story_counts,
            verify_pool,
        )

        failures = verify_pool()
        if failures:
            raise BriefError(f"press halted: {'; '.join(failures)}")
        count = brief.target_words or 3
        if count > 50:
            raise BriefError("reversible press run capped at 50 books per brief")
        seed = int(brief.seed()[:8], 16)
        books = press_run(count, seed)
        parts = [
            f"Press run — {count} books from the {len(CLAUSES)}-clause pool, "
            f"seed {seed}: {brief.title.strip()}"
        ]
        for b in books:
            parts.append("")
            parts.append(
                f"— Book {b['index']} ({b['clauses']} clauses, {b['words']} words) —"
            )
            parts.append(" ".join(reading(b["order"])))
        counts = story_counts(len(CLAUSES))
        notes = [
            f"press_run: {count} books, seed {seed}, pool verified",
            "story space: " + ", ".join(f"{k}={v}" for k, v in counts.items()),
        ]
        return "\n".join(parts), notes

    def _draft_manuscript(self, brief: ProductionBrief) -> "tuple[str, List[str]]":
        engine = LWPModelEngine()
        # Honor Direction / Phase / Power on the engine state directly
        # (no persistence: drafting is side-effect free).
        engine.state.direction = brief.direction
        engine.state.phase = brief.phase
        engine.state.power = brief.power
        if brief.pov:
            engine.state.pov = brief.pov
        if brief.genres:
            engine.state.genres = list(brief.genres)[:4]
        target = brief.target_words or engine.target_words()
        built = engine.assemble(
            seed=brief.brief_text.strip(),
            key=brief.seed() + "|draft",
            target=target,
        )
        notes = [
            f"{built['words']} words under {brief.direction}/{brief.phase}/{brief.power}",
            f"event: {built['event']}",
        ]
        return built["text"], notes

    def _draft_social(self, brief: ProductionBrief) -> "tuple[str, List[str]]":
        from levi.king.content_machine import (
            HOOK_PATTERNS,
            HookFormula,
            build_linkedin_post,
            build_x_thread,
            parse_platform,
            render_hook,
        )

        seed_int = int(brief.seed()[:8], 16)
        formulas = list(HookFormula)
        formula = formulas[seed_int % len(formulas)]
        pattern = HOOK_PATTERNS[formula]
        title = brief.title.strip()
        kw = " ".join(title.split()[:4]).lower().rstrip(".,!?")
        fills = {
            "claim": title,
            "experiment": f"shipping {kw}",
            "duration": f"{3 + seed_int % 27} days",
            "day": str(1 + seed_int % 28),
            "number": str(3 + seed_int % 8),
            "unit": "moves",
            "timeframe": "one quarter",
            "method": kw,
            "count": str(3 + seed_int % 5),
            "outcome": "a year",
            "role": "operator",
            "habit": "shipping by hand",
            "trigger": kw,
            "take": title,
        }
        variables = {s: fills.get(s, kw) for s in pattern.slots}
        rendered = render_hook(formula, variables)
        hook = rendered["hook"]
        body = " ".join(brief.brief_text.strip().split())
        cta = "Sealed on the LEVI press line — nothing published without permission."
        platform = parse_platform(brief.platform) if brief.platform else None
        if platform is not None and platform.name == "LINKEDIN":
            text = build_linkedin_post(hook, body, cta, hashtags=[kw.replace(" ", "")])
        elif platform is not None and platform.name == "X":
            posts = [hook]
            chunk, chunks = 260, []
            for i in range(0, len(body), chunk):
                chunks.append(body[i : i + chunk])
            posts.extend(chunks[:3])
            text = build_x_thread(posts)
        else:
            text = "\n\n".join([hook, body, cta])
        return text, [
            f"hook formula: {formula.value}",
            f"platform: {platform.value if platform else 'general'}",
        ]

    # -- publish_ready: the seal -----------------------------------------
    def _seal(self, run: PressRun) -> "tuple[str, bool, List[str]]":
        """Seal the dossier: every applied pair-pass receipted, vetoes declared."""
        problems = []
        if not any(r.stage == "draft_assembly" and r.receipt_id for r in run.records):
            problems.append("draft_assembly missing from the receipt chain")
        for p in range(1, run.passes + 1):
            rep = run.expansions.get(f"pass{p}", {})
            results = rep.get("pair_results", [])
            for pair in CANON_PAIRS:
                if any(v["pair"] == pair.name and v["pass"] == p for v in run.vetoes):
                    continue  # refused pairs are never forced; the dossier says so
                want = 2 * sum(1 for pr in results if pr.get("pair_name") == pair.name)
                got = sum(
                    1
                    for r in run.records
                    if r.stage == f"{_pair_stage(pair.name)}:pass{p}" and r.receipt_id
                )
                if got < want:
                    problems.append(
                        f"{_pair_stage(pair.name)}:pass{p} receipt chain broken "
                        f"({got}/{want} twin receipts)"
                    )
        if problems:
            return "", False, problems
        dossier = {
            "run_id": run.run_id,
            "title": run.brief["title"],
            "kind": run.brief["kind"],
            "platform": run.brief["platform"],
            "direction": run.brief["direction"],
            "phase": run.brief["phase"],
            "power": run.brief["power"],
            "passes": run.passes,
            "pair_stages": [r.to_dict() for r in run.records],
            "phantoms": run.phantoms,
            "failures": run.failures,
            "compost": run.compost,
            "vetoes": run.vetoes,
            "born": run.born,
            "cast": run.cast,
            "words": _words(run.final_text),
            "seal": hashlib.sha256(run.final_text.encode("utf-8")).hexdigest(),
        }
        notes = [
            f"dossier sealed: {dossier['words']}w across {run.passes} passes, "
            f"{len(run.phantoms)} phantoms, {len(run.compost)} composted, "
            f"{len(run.vetoes)} vetoed — seal {dossier['seal'][:12]}…"
        ]
        if run.cast:
            notes.append(
                f"cast: {len(run.cast)} character(s) minted for the "
                "dramatis personae (ledger-scoped character graph)"
            )
        uncomposted = [f for f in run.failures if f not in run.composted]
        if uncomposted:
            notes.append(
                f"{len(uncomposted)} failure(s) still uncomposted — "
                "the dossier carries them; the operator decides"
            )
        return json.dumps(dossier, indent=2), True, notes
