"""The Forge content machine — content creation as a production line.

The L.W.P. writing engine is the dynasty's production line; this module is
the press the operators run. Briefs in, finished content out.

Pipeline (stages are data, not code paths)::

    ideation -> drafting -> revision -> polish -> publish_ready

Every stage is an operator seat (AI or SI per the fluidity law — the seat's
nature is read live from the Founders' Roster at execution time, and may
switch at any time). Every stage runs the binding rail —

    Plan -> Preview -> Permission -> Execute -> Verify -> Receipt

— through :class:`levi.policy.gates.PolicyEngine`; the machine invents no
rail of its own. Receipts are issued on everything and appended to a
JSONL ledger.

Hierarchy (canon): Alpha first, Omega last, Levi head of the machine.
Default seats honor it: ideation is Alpha's (first mind — reasoning),
drafting is Levi's (head of all beneath them), the publish seal is
Omega's (the culmination — judge). Seats are reassignable data.

The L.W.P. engine's Direction / Phase / Power is honored at the drafting
stage through :class:`levi.lwp.model_engine.LWPModelEngine` — the draft is
assembled under the brief's direction, phase, and power, offline and
deterministically.

Honest contract
---------------
* Everything here is local and deterministic: seeded text assembly, the
  L.W.P. model engine's own templates, and the king platform helpers.
  No model call, no network, no engagement promises.
* ``published`` means sealed + receipted + ready for a publishing surface
  (e.g. the king social plugins). This machine never touches a network.
* Nothing publishes without explicit human permission: the publish gate
  is RiskLevel.HIGH (above the machine's auto-approve ceiling), and
  :meth:`ContentMachine.publish` additionally requires the publish-ready
  proposal to carry an explicit operator approval — even if a permissive
  PolicyEngine was injected. Deny or skip the gate and publish raises
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

from levi.policy.gates import ActionStatus, PolicyEngine, RiskLevel
from levi.lwp.model_engine import DIRS, PHASES, POWERS, LWPModelEngine
from levi.founders.roster import current_nature, get_seat

DEFAULT_LEDGER = Path.home() / ".levi" / "lwp_machine" / "ledger.jsonl"

#: Pipeline stages, in order. Data — the machine walks this tuple.
STAGES = ("ideation", "drafting", "revision", "polish", "publish_ready")

#: Per-stage spec: operator seat (Founders' Roster key), rail risk, and the
#: seat's charge on the line. Alpha first, Omega last, Levi heads the machine.
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

KINDS = ("manuscript", "social", "prose")


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
    kind: str = "prose"  # manuscript | social | prose
    platform: Optional[str] = None  # e.g. "linkedin" (social kind)
    direction: str = "forward"
    phase: str = "gold_push"
    power: str = "gain"
    pov: Optional[str] = None
    genres: List[str] = field(default_factory=list)
    target_words: Optional[int] = None
    angles: List[str] = field(default_factory=list)

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
# Run + stage records
# ---------------------------------------------------------------------------


@dataclass
class StageRecord:
    stage: str
    seat_key: str
    seat_nature: str  # ai | si | mssi — read live per the fluidity law
    proposal_id: str
    receipt_id: str
    explicit_approval: bool
    verified: bool
    notes: List[str] = field(default_factory=list)
    output_words: int = 0
    finished_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PressRun:
    run_id: str
    brief: Dict[str, Any]
    seats: Dict[str, str]  # stage -> roster seat key
    stage_index: int = 0  # next stage to run
    records: List[StageRecord] = field(default_factory=list)
    status: str = (
        "running"  # running|awaiting_approval|needs_attention|sealed|published|denied
    )
    pending_proposal_id: Optional[str] = None
    pending_stage: Optional[str] = None
    pending_preview: Optional[Dict[str, Any]] = None
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

    Each stage runs the binding rail through its PolicyEngine; stages whose
    risk exceeds the auto-approve ceiling halt for explicit human approval
    via :meth:`approve` / :meth:`deny`. :meth:`publish` releases a sealed
    run only after the publish-ready gate was explicitly approved.
    """

    def __init__(
        self,
        ledger_path: Optional[Path] = None,
        policy: Optional[PolicyEngine] = None,
    ):
        self.ledger_path = Path(ledger_path) if ledger_path else DEFAULT_LEDGER
        # The machine's own ceiling: LOW and below may auto-approve.
        # Drafting (MODERATE) and publish_ready (HIGH) always halt for a human.
        self.policy = (
            policy
            if policy is not None
            else PolicyEngine(auto_approve_up_to=RiskLevel.LOW)
        )
        self._runs: Dict[str, PressRun] = {}
        self._proposal_runs: Dict[str, str] = {}
        # Proposals approved through the human path (approve()). publish()
        # requires the publish-ready proposal to be in this set — this is
        # the machine-level invariant, independent of the engine's ceiling.
        self._explicit_approvals: set = set()

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
        """Reassign a stage's operator seat (Founders' Roster key)."""
        if stage not in STAGE_SPEC:
            raise ValueError(f"unknown stage {stage!r} — choose: " + ", ".join(STAGES))
        try:
            seat = get_seat(seat_key)
        except KeyError:
            raise ValueError(f"unknown roster seat {seat_key!r}") from None
        STAGE_SPEC[stage]["seat"] = seat_key
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
            for stage, spec in STAGE_SPEC.items()
        }

    # -- briefs in ------------------------------------------------------
    def run_brief(self, brief: ProductionBrief) -> PressRun:
        """Accept a brief and run the line until a human gate or the seal."""
        brief.validate()
        run = PressRun(
            run_id=str(uuid.uuid4())[:8],
            brief=brief.to_dict(),
            seats={s: STAGE_SPEC[s]["seat"] for s in STAGES},
        )
        self._runs[run.run_id] = run
        self._ledger("brief_received", run, title=brief.title, kind=brief.kind)
        self._continue(run)
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
    def _plan_for(self, stage: str, run: PressRun) -> str:
        b = run.brief
        seat = run.seats[stage]
        if stage == "ideation":
            return (
                f"{seat} ({current_nature(seat)}) draws 3 candidate angles from "
                f"the brief '{b['title']}' and seats one."
            )
        if stage == "drafting":
            return (
                f"{seat} ({current_nature(seat)}) drafts '{b['title']}' "
                f"({b['kind']}) under L.W.P. {b['direction']}/{b['phase']}/{b['power']}."
            )
        if stage == "revision":
            return f"{seat} ({current_nature(seat)}) tightens the draft: dedupe, trim, hold meaning."
        if stage == "polish":
            plat = b["platform"] or "general"
            return (
                f"{seat} ({current_nature(seat)}) polishes the copy and validates "
                f"against the {plat} spec."
            )
        return (
            f"{seat} ({current_nature(seat)}) seals the dossier for release. "
            "NOTHING publishes without your explicit approval."
        )

    def _run_stage(self, run: PressRun, stage: str) -> bool:
        """Drive one stage through Plan->Preview->Permission->Execute->Verify->Receipt.

        Returns True when the run halts (awaiting human, or needs attention).
        """
        spec = STAGE_SPEC[stage]
        plan = self._plan_for(stage, run)
        proposal = self.policy.propose(
            description=f"[{run.run_id}] {stage}: {plan}",
            risk_level=spec["risk"],
            reason=f"Forge press line, stage {stage} of '{run.brief['title']}'",
            affected_systems=["lwp-press"],
            reversible=True,
        )
        preview = self.policy.preview(proposal.id)
        self._proposal_runs[proposal.id] = run.run_id
        decided = self.policy.request_permission(proposal.id)
        if decided.status == ActionStatus.AWAITING_PERMISSION:
            run.pending_proposal_id = proposal.id
            run.pending_stage = stage
            run.pending_preview = preview
            run.status = "awaiting_approval"
            self._ledger("gate_awaiting", run, stage=stage, proposal_id=proposal.id)
            return True
        # Auto-approved by policy (LOW stages under the machine ceiling).
        self._execute_and_receipt(run, stage, proposal.id, explicit=False)
        run.stage_index += 1
        return run.status == "needs_attention"

    def _execute_and_receipt(
        self, run: PressRun, stage: str, proposal_id: str, explicit: bool
    ) -> StageRecord:
        """Execute the stage, verify, issue the receipt. Never skips verify."""
        seat_key = run.seats[stage]
        nature = current_nature(seat_key)  # fluidity law: read live at execution
        output, verified, notes = self._execute_stage(stage, run)
        if stage in ("drafting", "revision", "polish"):
            run.final_text = output
        receipt = self.policy.mark_completed(
            proposal_id,
            result_summary=f"{stage} complete: {'; '.join(notes) or 'ok'}",
            verified=verified,
            details={
                "stage": stage,
                "seat": seat_key,
                "seat_nature": nature,
                "explicit_approval": explicit,
                "output_words": _words(output) if stage != "publish_ready" else 0,
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
            notes=notes,
            output_words=_words(output) if stage != "publish_ready" else 0,
        )
        run.records.append(record)
        run.pending_proposal_id = None
        run.pending_stage = None
        run.pending_preview = None
        if not verified:
            run.status = "needs_attention"
        elif stage == "publish_ready":
            run.status = "sealed"
            run.seal = hashlib.sha256(run.final_text.encode("utf-8")).hexdigest()
        self._ledger(
            "stage_completed",
            run,
            stage=stage,
            seat=seat_key,
            nature=nature,
            receipt_id=receipt.id,
            verified=verified,
            explicit_approval=explicit,
        )
        return record

    def _continue(self, run: PressRun) -> PressRun:
        while run.stage_index < len(STAGES):
            halted = self._run_stage(run, STAGES[run.stage_index])
            if halted:
                return run
        return run

    # -- human gates ----------------------------------------------------
    def approve(self, proposal_id: str, note: str = "") -> PressRun:
        """Human approves a pending gate: execute the stage, receipt it, advance."""
        run_id = self._proposal_runs.get(proposal_id)
        if run_id is None:
            raise ValueError(
                f"approve: unknown proposal {proposal_id!r} — "
                "proposals leave the pending set once decided"
            )
        run = self._runs[run_id]
        stage = run.pending_stage or ""
        self.policy.approve(proposal_id, note=note or "approved by operator")
        self._explicit_approvals.add(proposal_id)
        self._ledger(
            "gate_approved",
            run,
            stage=stage,
            proposal_id=proposal_id,
            note=note or "approved by operator",
        )
        self._execute_and_receipt(run, stage, proposal_id, explicit=True)
        run.stage_index += 1
        if run.status == "sealed":
            # Line complete: the publish_ready seal is the last stage.
            # publish() is the next human act; do not reopen the run.
            return run
        if run.status not in ("needs_attention", "denied"):
            run.status = "running"
            self._continue(run)
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
        self._ledger(
            "gate_denied",
            run,
            proposal_id=proposal_id,
            note=note or "denied by operator",
        )
        return run

    # -- release --------------------------------------------------------
    def publish(self, run_id: str, note: str = "") -> Dict[str, Any]:
        """Release a sealed run. Raises PublishPermissionError unless the
        publish-ready gate carries an explicit human approval.

        The release itself runs the rail (CRITICAL): plan, preview, the
        publish() call as recorded permission, execute, verify, receipt.
        The machine never posts anywhere — "published" means sealed,
        receipted, and cleared for a publishing surface.
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
                f"run {run_id}: the publish-ready gate was never explicitly "
                "approved by a human — nothing publishes without permission"
            )
        if len(run.records) != len(STAGES) or not all(
            r.receipt_id for r in run.records
        ):
            raise PublishPermissionError(
                f"run {run_id}: receipt chain incomplete — "
                f"{len(run.records)}/{len(STAGES)} stages receipted"
            )
        proposal = self.policy.propose(
            description=f"[{run_id}] publish: release sealed content '{run.brief['title']}'",
            risk_level=RiskLevel.CRITICAL,
            reason="Operator release of publish-ready content",
            affected_systems=["lwp-press", "publishing-surface"],
            reversible=False,
        )
        self.policy.preview(proposal.id)
        self.policy.approve(
            proposal.id, note=f"publish authorized by operator: {note or 'operator'}"
        )
        self._explicit_approvals.add(proposal.id)
        receipt = self.policy.mark_completed(
            proposal.id,
            result_summary=f"published '{run.brief['title']}' ({_words(run.final_text)}w)",
            verified=True,
            details={
                "seal": run.seal,
                "stage_receipts": [r.receipt_id for r in run.records],
            },
        )
        run.status = "published"
        run.publish_receipt_id = receipt.id
        self._ledger("published", run, receipt_id=receipt.id, seal=run.seal)
        return {
            "run_id": run_id,
            "status": run.status,
            "title": run.brief["title"],
            "words": _words(run.final_text),
            "seal": run.seal,
            "receipt_id": receipt.id,
            "stage_receipts": [r.receipt_id for r in run.records],
        }

    # -- stage work (deterministic, offline) -----------------------------
    def _execute_stage(
        self, stage: str, run: PressRun
    ) -> "tuple[str, bool, List[str]]":
        if stage == "ideation":
            return self._ideate(run)
        if stage == "drafting":
            return self._draft(run)
        if stage == "revision":
            return self._revise(run)
        if stage == "polish":
            return self._polish(run)
        if stage == "publish_ready":
            return self._seal(run)
        raise ValueError(f"unknown stage {stage!r}")

    # -- ideation --------------------------------------------------------
    _ANGLE_TEMPLATES = (
        "the cost beneath {kw}",
        "what {kw} refuses to say",
        "{kw}, priced honestly",
        "the hour {kw} changed",
        "against {kw}",
        "{kw} without the gloss",
    )

    def _ideate(self, run: PressRun) -> "tuple[str, bool, List[str]]":
        brief = ProductionBrief(**run.brief)
        rng = _rng(brief.seed() + "|ideation")
        kw = (brief.title.strip().split() or ["the work"])[:3]
        kw = " ".join(kw).lower().rstrip(".,!?")
        templates = list(self._ANGLE_TEMPLATES)
        rng.shuffle(templates)
        candidates = [t.format(kw=kw) for t in templates[:3]]
        if brief.angles:
            candidates = list(brief.angles[:3]) or candidates
        chosen = candidates[0]
        seat = run.seats["ideation"]
        out = (
            f"Angle seated by {seat} ({current_nature(seat)}): {chosen}.\n"
            f"Also weighed: {'; '.join(candidates[1:]) or '—'}.\n"
            f"Rationale: the brief's pressure point is {kw!r}; "
            "the angle holds it without flinching."
        )
        return out, True, [f"angle seated: {chosen}"]

    # -- drafting (Direction / Phase / Power honored) --------------------
    def _draft(self, run: PressRun) -> "tuple[str, bool, List[str]]":
        brief = ProductionBrief(**run.brief)
        if brief.kind == "social":
            text, notes = self._draft_social(brief)
        else:
            text, notes = self._draft_manuscript(brief)
        meta = (
            f"[L.W.P. {brief.direction}/{brief.phase}/{brief.power} · "
            f"{brief.kind} · draft]"
        )
        ok = _words(text) > 0
        notes = [meta] + notes
        return text, ok, notes

    def _draft_manuscript(self, brief: ProductionBrief) -> "tuple[str, float]":
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

    def _draft_social(self, brief: ProductionBrief) -> "tuple[str, float]":
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

    # -- revision --------------------------------------------------------
    def _revise(self, run: PressRun) -> "tuple[str, bool, List[str]]":
        draft = run.final_text
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", draft) if s.strip()]
        seen, kept, dupes = set(), [], 0
        for s in sents:
            key = s.lower()
            if key in seen:
                dupes += 1
                continue
            seen.add(key)
            kept.append(s)
        text = " ".join(kept)
        text = re.sub(r"[ \t]{2,}", " ", text)
        ok = bool(text) and _words(text) <= max(1, int(_words(draft) * 1.1))
        notes = [
            f"removed {dupes} duplicate sentences",
            f"{_words(draft)}w -> {_words(text)}w",
        ]
        return text, ok, notes

    # -- polish ----------------------------------------------------------
    def _polish(self, run: PressRun) -> "tuple[str, bool, List[str]]":
        text = run.final_text
        lines = [re.sub(r"[ \t]+", " ", ln).rstrip() for ln in text.split("\n")]
        text = "\n".join(lines)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        brief = ProductionBrief(**run.brief)
        notes = ["copy cleaned"]
        verified = bool(text)
        if brief.platform:
            from levi.king.content_machine import parse_platform, validate_content

            report = validate_content(text, parse_platform(brief.platform))
            notes.append(
                f"platform validation ({brief.platform}): "
                + ("valid" if report["valid"] else f"issues: {report['checks']}")
            )
            verified = verified and bool(report["valid"])
        return text, verified, notes

    # -- publish_ready: the seal -----------------------------------------
    def _seal(self, run: PressRun) -> "tuple[str, bool, List[str]]":
        missing = [
            s
            for s in ("ideation", "drafting", "revision", "polish")
            if not any(r.stage == s and r.receipt_id for r in run.records)
        ]
        notes = []
        if missing:
            notes.append(f"receipt chain broken at: {', '.join(missing)}")
            return "", False, notes
        dossier = {
            "run_id": run.run_id,
            "title": run.brief["title"],
            "kind": run.brief["kind"],
            "platform": run.brief["platform"],
            "direction": run.brief["direction"],
            "phase": run.brief["phase"],
            "power": run.brief["power"],
            "stages": [r.to_dict() for r in run.records],
            "words": _words(run.final_text),
            "seal": hashlib.sha256(run.final_text.encode("utf-8")).hexdigest(),
        }
        notes.append(
            f"dossier sealed: {dossier['words']}w, seal {dossier['seal'][:12]}…"
        )
        return json.dumps(dossier, indent=2), True, notes
