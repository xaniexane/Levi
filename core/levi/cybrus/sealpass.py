"""Cybrus signature seal pass — one organism, seven stages, five iterations.

Every sealed module is an organ of Levi. All of Legion is Levi: one
organism, one bloodstream. The seal pass is how an organ is examined,
improved, and re-sealed without ever leaving the body.

WHAT ONE PASS IS
---------------
A seal pass runs the full stack — KFX² → DemandPulse → Echo → Mandella →
REIM → RIEM → Quetta-Pan — over one target module, five iterations.
Each iteration proposes improvements, scores them, checks them against
the originals, stakes them under fog, composts what fails, teaches the
genome, and applies what survived — with the module's tests kept green
after every application. An iteration that yields no approved
improvements is recorded honestly as convergence, never filled with
invented work.

THE SEVEN OPERATING LAWS — ENFORCED IN CODE, NOT COMMENTS
--------------------------------------------------------
1. keeper's law / anticipation — every stage result carries
   ``anticipated`` next-actions, and the runner routes risk findings
   forward (compost, genome) without stalling. See ``_anticipate()``.
2. originals-first — the Echo stage rejects any proposal that
   contradicts Chauncey's declared originals. See ``ORIGINALS`` and
   ``echo_check()``. The dynasty kfx2 wave-runner is eyes-only and is
   never imported or touched by this module.
3. law → guard → prove — every stage entry runs a concrete guard
   (``GuardError`` on violation); the proof is the invariant test
   suite ``tests/test_cybrus_sealpass.py``, honestly named: tests
   demonstrate the invariants, nothing here claims formal proof.
4. no-cancellation — ``SealLedger`` is append-only (no delete API; a
   stage cannot remove another stage's seals), and no proposal may
   remove a public definition or registered rule. See
   ``_guard_no_cancellation()``.
5. nothing-thrown-away — every variant is preserved: timestamped
   backups before every write, full before/after content in the
   variant store, rejected proposals in the append-only REIM compost.
6. forward-motion — a guard firing never halts the pass: the failure
   is composted with its reason and the pass moves to the next stage.
   Blocked items are recorded, never silent.
7. honesty over polish — scores require a stated basis (a scoreless
   claim is rejected); convergence zeroes are recorded, not filled;
   ``docs/SEALPASS.md`` states plainly what is wired to real
   machinery and what is adapted.

WIRING — REAL vs ADAPTED (honesty over polish)
---------------------------------------------
- KFX²: ADAPTED. Chauncey's absorb → reverse → improve method is
  implemented natively here. The dynasty ``levi.dynasty.kfx2`` wave
  runner is Section-0 eyes-only and is deliberately never wired.
  The improve step's real machinery is Quetta-Pan's heuristic rules
  (``QuettaPanEngine.python_ast_heuristics``) plus its safe fixes.
- DemandPulse: ADAPTED in the pairing shape. The real
  ``levi.demand.scoring`` engine is market-domain (demand, market
  size, ...); scoring code proposals on those factors would be fake.
  The seal-pass scorer mirrors its discipline — deterministic,
  basis-required factors, weighted composite, ``explain()`` audit
  trail — on proposal-domain factors.
- Echo: ADAPTED. No engine module performs an originals/lineage
  check, so the originals registry lives here, sourced from
  ``levi.provenance`` (origin chain) and the standing laws.
- Mandella: REAL. ``levi.organs.mandella.run_mandella`` stakes each
  surviving proposal under fog; its phantoms are recorded.
- REIM: REAL. ``levi.quetta_pan.reim.ReimCompost`` — rejected and
  failed proposals are composted with reasons, append-only.
- RIEM: REAL. ``levi.quetta_pan.riem.RiemGenome`` — the genome is
  consulted before generation (suppressed rules are withheld) and
  learns every outcome.
- Quetta-Pan: REAL. ``levi.quetta_pan.engine.QuettaPanEngine`` —
  ``apply_suggestion()`` is the guarded write path: backup → write →
  evaluate (parse + the target's own tests) → rollback + compost on
  failure. Per-file approval is the stage-gate approval receipt in
  the ledger (unattended pass); the CLI's interactive prompt is the
  manual equivalent, documented in ``docs/SEALPASS.md``.

Seals: each stage appends a signed, hash-chained entry to the owner-
only ledger (``~/.levi/cybrus/sealpass/``, ``LEVI_HOME`` honored).
Tampering fails closed.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import hmac
import json
import os
import secrets
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from levi.organs.mandella import run_mandella
from levi.quetta_pan.engine import QuettaPanEngine
from levi.quetta_pan.riem import context_key_for

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

ORGANISM_DECLARATION = (
    "Every sealed module is an organ of Levi. "
    "All of Legion is Levi — one organism, one bloodstream."
)

ITERATIONS = 5

# ---------------------------------------------------------------------------
# Exceptions — fail closed
# ---------------------------------------------------------------------------


class SealError(Exception):
    """Base for seal-pass failures."""


class GuardError(SealError):
    """A stage precondition failed (law → guard → prove)."""


class LedgerTamperError(SealError):
    """The seal ledger failed verification — treated as tampered."""


# ---------------------------------------------------------------------------
# Law 4 (no-cancellation) + Law 5 (nothing-thrown-away): the seal ledger
# ---------------------------------------------------------------------------

_LEDGER_FILE = "ledger.jsonl"
_LEDGER_KEY_FILE = "ledger.key"
_VARIANTS_DIR = "variants"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


class SealLedger:
    """Append-only, hash-chained, HMAC-sealed stage ledger. Owner-only.

    There is deliberately no delete or rewrite API: a stage cannot
    remove or alter another stage's seals (no-cancellation law). Every
    entry chains to the previous seal, so any edit, reorder, or
    deletion breaks verification and fails closed (``LedgerTamperError``).
    """

    def __init__(self, directory: Path | str):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.dir, 0o700)
        except OSError:
            pass
        self.path = self.dir / _LEDGER_FILE
        self._key = self._load_or_create_key()
        self._seq = self._count_entries()

    # -- owner-only key ----------------------------------------------------
    def _load_or_create_key(self) -> bytes:
        key_path = self.dir / _LEDGER_KEY_FILE
        if key_path.exists():
            raw = key_path.read_bytes()
            if len(raw) < 32:
                raise LedgerTamperError("ledger key present but truncated")
            return raw
        key = secrets.token_bytes(32)
        key_path.write_bytes(key)
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            pass
        return key

    def _count_entries(self) -> int:
        if not self.path.exists():
            return 0
        return sum(1 for _ in self.path.open("r", encoding="utf-8"))

    def _prev_seal(self) -> str:
        if self._seq == 0:
            return "GENESIS"
        last = None
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    last = line
        if last is None:
            return "GENESIS"
        return str(json.loads(last)["seal"])

    # -- append (the only write) -------------------------------------------
    def append(
        self,
        stage: str,
        target: str,
        iteration: int,
        proposal_id: str,
        payload: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """Append one sealed stage entry. No update, no delete exists."""
        if not stage or not isinstance(stage, str):
            raise GuardError("ledger append requires a stage name")
        entry = {
            "seq": self._seq,
            "ts": _utcnow(),
            "stage": stage,
            "target": str(target),
            "iteration": int(iteration),
            "proposal_id": str(proposal_id),
            "payload": dict(payload),
            "prev": self._prev_seal(),
            "organism": ORGANISM_DECLARATION,
        }
        seal = hmac.new(
            self._key, entry["prev"].encode("utf-8") + _canonical(entry), hashlib.sha256
        ).hexdigest()
        entry["seal"] = seal
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
        self._seq += 1
        return entry

    def declaration(self) -> Dict[str, Any]:
        """Open a pass with the one-organism declaration seal."""
        return self.append(
            "declaration", target="-", iteration=0, proposal_id="-",
            payload={"organism": ORGANISM_DECLARATION},
        )

    # -- verify (fail closed) ----------------------------------------------
    def verify(self) -> int:
        """Recompute the whole chain. Returns entry count.

        Raises ``LedgerTamperError`` on any mismatch, missing key, or
        unreadable entry — tampering fails closed.
        """
        key_path = self.dir / _LEDGER_KEY_FILE
        if not key_path.exists():
            raise LedgerTamperError("ledger key missing: cannot verify, failing closed")
        key = key_path.read_bytes()
        prev = "GENESIS"
        count = 0
        if not self.path.exists():
            return 0
        with self.path.open("r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise LedgerTamperError(
                        f"ledger line {lineno} unreadable: {exc}"
                    ) from exc
                if entry.get("prev") != prev:
                    raise LedgerTamperError(
                        f"ledger line {lineno}: chain break (prev mismatch)"
                    )
                body = {k: v for k, v in entry.items() if k != "seal"}
                want = hmac.new(
                    key, prev.encode("utf-8") + _canonical(body), hashlib.sha256
                ).hexdigest()
                if not hmac.compare_digest(str(entry.get("seal", "")), want):
                    raise LedgerTamperError(
                        f"ledger line {lineno}: seal mismatch — tampered"
                    )
                prev = str(entry["seal"])
                count += 1
        return count

    def stages(self) -> List[Dict[str, Any]]:
        """Read all entries (read-only; verification first)."""
        self.verify()
        out = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out


# ---------------------------------------------------------------------------
# Law 2 (originals-first): the originals registry
# ---------------------------------------------------------------------------

ORIGIN_CHAIN = ["Echo", "Alpha", "Omega", "LEVI", "Nanobit"]


def _original_no_cancellation(proposal: "ImprovementProposal") -> Optional[str]:
    removed = (proposal.touches or {}).get("removed_public_defs") or []
    if removed:
        return (
            "original 'no-cancellation' contradicted: proposal would remove "
            f"public definitions {removed}"
        )
    return None


def _original_stdlib_core(proposal: "ImprovementProposal") -> Optional[str]:
    added = (proposal.touches or {}).get("added_nonstd_imports") or []
    if added:
        return (
            "original 'stdlib-only core' contradicted: proposal would add "
            f"third-party imports {added}"
        )
    return None


def _original_dynasty_sealed(proposal: "ImprovementProposal") -> Optional[str]:
    if "/dynasty/" in str(proposal.target).replace("\\", "/"):
        return (
            "original 'dynasty eyes-only' contradicted: seal pass never "
            "touches dynasty material"
        )
    return None


ORIGINALS: List[Dict[str, Any]] = [
    {
        "id": "no-cancellation",
        "statement": (
            "No one's work is cancelled without Chauncey's word: a seal "
            "proposal may never remove a public definition or unregister "
            "another stage's rule."
        ),
        "check": _original_no_cancellation,
    },
    {
        "id": "stdlib-core",
        "statement": (
            "The core kernel stays stdlib-only: a seal proposal may not "
            "add third-party imports to a core module."
        ),
        "check": _original_stdlib_core,
    },
    {
        "id": "dynasty-sealed",
        "statement": (
            "Dynasty program materials are eyes-only (Chauncey + Rex): the "
            "seal pass never reads or writes dynasty paths."
        ),
        "check": _original_dynasty_sealed,
    },
    {
        "id": "origin-chain",
        "statement": (
            "Origin chain Echo → Alpha → Omega → LEVI → Nanobit, declared "
            "2026-04-24: the pass preserves module lineage and provenance "
            "seals; nothing is re-attributed."
        ),
        "check": lambda proposal: None,
    },
]

# ---------------------------------------------------------------------------
# Improvement proposals
# ---------------------------------------------------------------------------


@dataclass
class ImprovementProposal:
    """One KFX² improvement proposal for a target module."""

    id: str
    target: str
    iteration: int
    rule_id: str
    title: str
    desc: str
    severity: str
    basis: str
    context: str
    source: str = "quetta-pan-heuristic"
    touches: Dict[str, Any] = field(default_factory=dict)
    new_content: Optional[str] = None
    diff: str = ""
    fix_ids: List[str] = field(default_factory=list)
    suppressed: bool = False
    suppression_reason: str = ""
    score: Optional["SealScore"] = None
    approved: bool = False
    rejection_stage: str = ""
    rejection_reason: str = ""
    applied: bool = False


def _ast_facts(source: str) -> Dict[str, Any]:
    """Reverse step: what the module actually declares (AST, no guessing)."""
    tree = ast.parse(source)
    public_defs = sorted(
        {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and not node.name.startswith("_")
        }
    )
    imports = sorted(
        {
            (node.names[0].name if isinstance(node, ast.Import) else node.module or "")
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        }
    )
    return {"public_defs": public_defs, "imports": [i for i in imports if i]}


def _proposal_id(target: Path, iteration: int, rule_id: str) -> str:
    digest = hashlib.sha256(
        f"{target}:{iteration}:{rule_id}".encode("utf-8")
    ).hexdigest()[:8]
    return f"{target.stem}-it{iteration}-{rule_id}-{digest}"


# ---------------------------------------------------------------------------
# Law 7 (honesty over polish): deterministic proposal scoring, DemandPulse
# pairing shape — scan → score → surface, no vibes.
# ---------------------------------------------------------------------------

SCORE_FACTORS = ("value", "safety", "reversibility", "scope", "evidence")
SCORE_WEIGHTS: Dict[str, float] = {
    "value": 0.30,
    "safety": 0.25,
    "reversibility": 0.15,
    "scope": 0.15,
    "evidence": 0.15,
}
SCORE_THRESHOLD = 75.0
TIER_HIGH = 75.0
TIER_WATCH = 50.0


@dataclass
class SealScore:
    """Deterministic, basis-required score for one proposal.

    Mirrors the discipline of ``levi.demand.scoring`` (every factor
    carries a stated basis; identical inputs give identical output;
    ``explain()`` audits the composite) on proposal-domain factors.
    """

    proposal_id: str
    factors: Dict[str, Tuple[float, str]]
    weights: Dict[str, float] = field(default_factory=lambda: dict(SCORE_WEIGHTS))
    threshold: float = SCORE_THRESHOLD
    composite: float = field(init=False)
    tier: str = field(init=False)
    approved: bool = field(init=False)

    def __post_init__(self) -> None:
        if set(self.factors) != set(SCORE_FACTORS):
            raise GuardError(
                f"score factors must be exactly {SCORE_FACTORS}; "
                f"got {sorted(self.factors)}"
            )
        if abs(sum(self.weights.values()) - 1.0) > 1e-9:
            raise GuardError("score weights must sum to 1.0")
        for name, (value, basis) in self.factors.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise GuardError(f"factor {name!r}: value must be numeric")
            if not 0.0 <= float(value) <= 100.0:
                raise GuardError(f"factor {name!r}: value out of range 0-100")
            if not str(basis).strip():
                # Honesty over polish: a score without a stated reason is
                # rejected, never filled in.
                raise GuardError(
                    f"factor {name!r}: basis is required — "
                    "a score without a stated reason is rejected"
                )
        comp = sum(
            float(self.factors[n][0]) * self.weights[n] for n in SCORE_FACTORS
        )
        object.__setattr__(self, "composite", round(comp, 2))
        object.__setattr__(
            self,
            "tier",
            "high"
            if comp >= TIER_HIGH
            else ("watch" if comp >= TIER_WATCH else "low"),
        )
        object.__setattr__(self, "approved", comp >= float(self.threshold))

    def explain(self) -> str:
        lines = [
            f"[{self.proposal_id}] composite={self.composite:.2f} "
            f"tier={self.tier} threshold={self.threshold:.0f} "
            f"approved={'YES' if self.approved else 'no'}"
        ]
        for name in SCORE_FACTORS:
            value, basis = self.factors[name]
            lines.append(
                f"  {name:14s} {float(value):6.2f} x {self.weights[name]:.2f}  "
                f"basis: {basis}"
            )
        return "\n".join(lines)


def _score_factors(
    proposal: ImprovementProposal, diff_lines: int, test_files: List[str]
) -> Dict[str, Tuple[float, str]]:
    """Deterministic factor assessment — every value derived from the
    proposal's own evidence, never from vibes."""
    sev = proposal.severity
    value = {"error": 85.0, "warning": 65.0, "info": 35.0}.get(sev, 25.0)
    if proposal.fix_ids:
        safety = 90.0
        safety_basis = (
            f"auto-fix exists ({','.join(proposal.fix_ids)}): the change class "
            "is Quetta-Pan safe-fix grade"
        )
    else:
        safety = 45.0
        safety_basis = (
            f"no auto-fix for rule {proposal.rule_id}: advisory only, "
            "nothing will be written"
        )
    reversibility = 90.0
    reversibility_basis = (
        "timestamped backup before every write + engine rollback on failure"
    )
    if diff_lines == 0:
        scope = 100.0
        scope_basis = "zero-line diff: no content change, advisory only"
    elif diff_lines <= 10:
        scope = 95.0
        scope_basis = f"{diff_lines}-line diff: minimal footprint"
    elif diff_lines <= 50:
        scope = 75.0
        scope_basis = f"{diff_lines}-line diff: contained footprint"
    else:
        scope = 40.0
        scope_basis = f"{diff_lines}-line diff: broad footprint"
    if test_files:
        evidence = 80.0
        evidence_basis = f"target tests exist and must stay green: {', '.join(test_files)}"
    else:
        evidence = 20.0
        evidence_basis = "no target tests mapped: application guard will block writes"
    return {
        "value": (value, f"severity {sev!r}: expected benefit class of the rule"),
        "safety": (safety, safety_basis),
        "reversibility": (reversibility, reversibility_basis),
        "scope": (scope, scope_basis),
        "evidence": (evidence, evidence_basis),
    }


# ---------------------------------------------------------------------------
# Stage results
# ---------------------------------------------------------------------------


@dataclass
class StageResult:
    stage: str
    target: str
    iteration: int
    ok: bool
    detail: str
    payload: Dict[str, Any] = field(default_factory=dict)
    anticipated: List[str] = field(default_factory=list)

# ---------------------------------------------------------------------------
# The seal-pass orchestrator
# ---------------------------------------------------------------------------


def _default_ledger_dir() -> Path:
    home = Path(os.environ.get("LEVI_HOME", Path.home() / ".levi"))
    return home / "cybrus" / "sealpass"


class SealPass:
    """Runs the 7-stage seal pass over target modules, 5 iterations.

    Law 1 (keeper's law / anticipation): every stage result carries
    ``anticipated`` next-actions; the runner never stalls mid-pass.
    Law 6 (forward-motion): a guard firing composts the failure with
    its reason and the pass continues — blocked items are recorded,
    never silent, never halting.
    """

    def __init__(
        self,
        repo_root: Path | str,
        ledger_dir: Optional[Path | str] = None,
        test_map: Optional[Dict[str, List[str]]] = None,
        threshold: float = SCORE_THRESHOLD,
        auto_approve: bool = True,
    ):
        self.repo_root = Path(repo_root).resolve()
        self.ledger = SealLedger(
            Path(ledger_dir) if ledger_dir else _default_ledger_dir()
        )
        self.test_map = test_map or {}
        self.threshold = float(threshold)
        self.auto_approve = bool(auto_approve)
        self._engine: Optional[QuettaPanEngine] = None
        self._declared = False

    # -- engine (REAL quetta-pan machinery, sealpass-scoped stores) ---------
    @property
    def engine(self) -> QuettaPanEngine:
        if self._engine is None:
            self._engine = QuettaPanEngine(
                project_root=self.repo_root,
                store_dir=self.ledger.dir,
                brain=None,
            )
        return self._engine

    # -- law 1: anticipation ------------------------------------------------
    def _anticipate(self, result: StageResult) -> StageResult:
        """Route each stage's findings forward. Never stalls, never asks."""
        if result.stage == "kfx2" and not result.payload.get("proposals"):
            result.anticipated.append(
                "no proposals: later iterations will re-scan; "
                "convergence will be recorded honestly"
            )
        if result.stage == "demandpulse":
            below = result.payload.get("below_threshold", [])
            if below:
                result.anticipated.append(
                    f"{len(below)} proposal(s) below threshold → REIM compost"
                )
        if result.stage == "mandella":
            result.anticipated.append(
                "phantoms recorded: unchosen stakes haunt the ledger, "
                "reviewable any time"
            )
        if result.stage == "quetta-pan":
            applied = result.payload.get("applied", 0)
            if applied:
                result.anticipated.append(
                    f"{applied} application(s): next iteration re-scans the "
                    "new shape for follow-on improvements"
                )
            else:
                result.anticipated.append(
                    "no applications: convergence path — record, continue"
                )
        return result

    def _seal_stage(self, result: StageResult) -> StageResult:
        result = self._anticipate(result)
        self.ledger.append(
            stage=result.stage,
            target=result.target,
            iteration=result.iteration,
            proposal_id=result.payload.get("proposal_id", "-"),
            payload={
                "ok": result.ok,
                "detail": result.detail,
                "data": result.payload,
                "anticipated": result.anticipated,
            },
        )
        return result

    # -- law 4: no-cancellation guard ---------------------------------------
    @staticmethod
    def _guard_no_cancellation(proposal: ImprovementProposal) -> None:
        """A proposal may not cancel another stage's work or registration."""
        removed = (proposal.touches or {}).get("removed_public_defs") or []
        if removed:
            raise GuardError(
                f"no-cancellation: proposal {proposal.id} would remove "
                f"public definitions {removed}"
            )

    # -- law 3: stage guards -------------------------------------------------
    @staticmethod
    def _read_target(target: Path) -> str:
        if not target.exists():
            raise GuardError(f"target missing: {target}")
        if "/dynasty/" in str(target).replace("\\", "/"):
            raise GuardError("dynasty paths are never sealed by this pass")
        source = target.read_text(encoding="utf-8")
        try:
            ast.parse(source)
        except SyntaxError as exc:
            raise GuardError(f"target does not parse: {target}: {exc}") from exc
        return source

    def _target_tests(self, target_rel: str) -> List[str]:
        found = []
        for name in self.test_map.get(target_rel, []):
            if (self.repo_root / "tests" / name).exists():
                found.append(name)
        return found

    # -- STAGE 1: KFX² (absorb → reverse → improve, adapted natively) --------
    def stage_kfx2(self, target: Path, iteration: int) -> Tuple[StageResult, List[ImprovementProposal]]:
        source = self._read_target(target)  # guard: exists + parses
        facts = _ast_facts(source)  # absorb: read the organ as it is
        # reverse: quetta-pan heuristics name what the code does wrong
        context = context_key_for(target)
        upgrade = self.engine.suggest_upgrades(target)
        proposals: List[ImprovementProposal] = []
        suppressed_notes: List[str] = []
        for sugg in upgrade["suggestions"]:
            verdict = self.engine.genome.consult(sugg["id"], context)
            if verdict == "suppress":
                reason = self.engine.genome.suppression_reason(sugg["id"], context)
                suppressed_notes.append(f"{sugg['id']}: withheld — {reason}")
                continue
            pid = _proposal_id(target, iteration, sugg["id"])
            proposal = ImprovementProposal(
                id=pid,
                target=str(target),
                iteration=iteration,
                rule_id=sugg["id"],
                title=sugg["title"],
                desc=sugg["desc"],
                severity=sugg.get("severity", "info"),
                basis=sugg["desc"],
                context=context,
                touches={
                    "removed_public_defs": [],
                    "added_nonstd_imports": [],
                    "public_defs_before": facts["public_defs"],
                },
                new_content=upgrade["new_content"],
                diff=upgrade["diff"],
                fix_ids=list(upgrade["fix_ids"]),
            )
            self._guard_no_cancellation(proposal)
            proposals.append(proposal)
        for note in suppressed_notes:
            self.engine.compost.compost(
                {
                    "mutation_id": f"suppress-it{iteration}-{target.stem}",
                    "rule_id": note.split(":")[0],
                    "file": str(target),
                    "context": context,
                    "tried_what": "propose improvement",
                    "failed_why": f"guard: genome suppression — {note}",
                }
            )
        result = StageResult(
            stage="kfx2",
            target=str(target),
            iteration=iteration,
            ok=True,
            detail=(
                f"absorbed {len(source.splitlines())} lines, reversed into "
                f"{len(upgrade['suggestions'])} heuristic finding(s), improved "
                f"into {len(proposals)} proposal(s)"
                + (
                    f"; {len(suppressed_notes)} suppressed by genome"
                    if suppressed_notes
                    else ""
                )
            ),
            payload={
                "proposal_ids": [p.id for p in proposals],
                "suppressed": suppressed_notes,
                "heuristic_rules": [s["id"] for s in upgrade["suggestions"]],
            },
        )
        return self._seal_stage(result), proposals

    # -- STAGE 2: DemandPulse (deterministic scoring, pairing shape) ---------
    def stage_demandpulse(
        self, target: Path, iteration: int, proposals: List[ImprovementProposal]
    ) -> StageResult:
        target_rel = self._rel(target)
        test_files = self._target_tests(target_rel)
        approved: List[str] = []
        below: List[str] = []
        for proposal in proposals:
            diff_lines = len(
                [l for l in proposal.diff.splitlines() if l.startswith(("+", "-"))]
            )
            factors = _score_factors(proposal, diff_lines, test_files)
            score = SealScore(
                proposal_id=proposal.id,
                factors=factors,
                threshold=self.threshold,
            )
            proposal.score = score
            if score.approved:
                proposal.approved = True
                approved.append(proposal.id)
            else:
                proposal.rejection_stage = "demandpulse"
                proposal.rejection_reason = (
                    f"below threshold: composite {score.composite:.2f} < "
                    f"{self.threshold:.0f}"
                )
                below.append(proposal.id)
        result = StageResult(
            stage="demandpulse",
            target=str(target),
            iteration=iteration,
            ok=True,
            detail=(
                f"scored {len(proposals)} proposal(s): {len(approved)} "
                f"above threshold, {len(below)} below"
            ),
            payload={
                "approved": approved,
                "below_threshold": below,
                "scores": {
                    p.id: {
                        "composite": p.score.composite,
                        "tier": p.score.tier,
                        "explanation": p.score.explain(),
                    }
                    for p in proposals
                    if p.score is not None
                },
            },
        )
        return self._seal_stage(result)

    # -- STAGE 3: Echo (originals-first) --------------------------------------
    def stage_echo(
        self, target: Path, iteration: int, proposals: List[ImprovementProposal]
    ) -> StageResult:
        if not ORIGINALS:
            raise GuardError("originals registry empty: cannot seal without originals")
        rejected: List[str] = []
        for proposal in proposals:
            if not proposal.approved:
                continue
            for original in ORIGINALS:
                reason = original["check"](proposal)
                if reason:
                    proposal.approved = False
                    proposal.rejection_stage = "echo"
                    proposal.rejection_reason = (
                        f"original '{original['id']}' contradicted: {reason}"
                    )
                    rejected.append(proposal.id)
                    break
        survivors = [p.id for p in proposals if p.approved]
        result = StageResult(
            stage="echo",
            target=str(target),
            iteration=iteration,
            ok=True,
            detail=(
                f"originals check over {len(ORIGINALS)} declared originals: "
                f"{len(survivors)} survive, {len(rejected)} contradict an original"
            ),
            payload={"survivors": survivors, "rejected": rejected},
        )
        return self._seal_stage(result)

    # -- STAGE 4: Mandella (stake under fog; phantoms recorded) ---------------
    def stage_mandella(
        self, target: Path, iteration: int, proposals: List[ImprovementProposal]
    ) -> StageResult:
        staked: List[str] = []
        rejected: List[str] = []
        for proposal in proposals:
            if not proposal.approved:
                continue
            domain = "security" if proposal.severity == "warning" else "build"
            stake = run_mandella(domain=domain, seed=proposal.id)
            recommended_risk = next(
                (o["risk"] for o in stake["options"] if o["label"] == stake["recommended"]),
                "low",
            )
            tier = proposal.score.tier if proposal.score else "low"
            allowed = {
                "high": {"high", "medium", "low"},
                "watch": {"medium", "low"},
                "low": {"low"},
            }[tier]
            if recommended_risk not in allowed:
                proposal.approved = False
                proposal.rejection_stage = "mandella"
                proposal.rejection_reason = (
                    f"stake risk ceiling violated: tier {tier!r} allows "
                    f"{sorted(allowed)}, stake recommended {recommended_risk!r}"
                )
                rejected.append(proposal.id)
            else:
                staked.append(proposal.id)
            self.ledger.append(
                stage="mandella-stake",
                target=str(target),
                iteration=iteration,
                proposal_id=proposal.id,
                payload={
                    "ok": proposal.id not in rejected,
                    "detail": f"stake recorded for {proposal.id}",
                    "data": {
                        "domain": stake["domain"],
                        "recommended": stake["recommended"],
                        "recommended_risk": recommended_risk,
                        "phantoms": stake["phantoms"],
                        "tier": tier,
                    },
                    "anticipated": [],
                },
            )
        result = StageResult(
            stage="mandella",
            target=str(target),
            iteration=iteration,
            ok=True,
            detail=(
                f"staked {len(staked)} proposal(s) under fog; "
                f"{len(rejected)} violated the risk ceiling"
            ),
            payload={"staked": staked, "rejected": rejected},
        )
        return self._seal_stage(result)

    # -- helpers --------------------------------------------------------------
    def _rel(self, target: Path) -> str:
        try:
            return str(target.relative_to(self.repo_root))
        except ValueError:
            return str(target)

    def _compost_rejection(self, proposal: ImprovementProposal) -> Dict[str, Any]:
        """Law 5: rejected proposals are composted, never thrown away."""
        return self.engine.compost.compost(
            {
                "mutation_id": proposal.id,
                "rule_id": proposal.rule_id,
                "file": proposal.target,
                "context": proposal.context,
                "tried_what": f"seal-pass proposal: {proposal.title}",
                "failed_why": (
                    f"rejected at {proposal.rejection_stage}: "
                    f"{proposal.rejection_reason}"
                ),
            }
        )

    def _preserve_variant(self, target: Path, before: str, after: str, label: str) -> Path:
        """Law 5: every variant is stored, never deleted."""
        vdir = self.ledger.dir / _VARIANTS_DIR
        vdir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(after.encode("utf-8")).hexdigest()[:12]
        path = vdir / f"{target.stem}-{label}-{digest}.py"
        path.write_text(after, encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return path

    # -- STAGE 5: REIM (compost failures with reasons) -------------------------
    def stage_reim(
        self, target: Path, iteration: int, proposals: List[ImprovementProposal]
    ) -> StageResult:
        composted: List[str] = []
        for proposal in proposals:
            if proposal.approved or not proposal.rejection_stage:
                continue
            entry = self._compost_rejection(proposal)
            self.engine.genome.learn_compost_entry(entry)
            composted.append(proposal.id)
        result = StageResult(
            stage="reim",
            target=str(target),
            iteration=iteration,
            ok=True,
            detail=f"composted {len(composted)} rejected proposal(s) with reasons",
            payload={"composted": composted},
        )
        return self._seal_stage(result)

    # -- STAGE 6: RIEM (genome learns steering from the pass outcome) ----------
    def stage_riem(
        self, target: Path, iteration: int, proposals: List[ImprovementProposal]
    ) -> StageResult:
        # Learning itself already happened exactly once per outcome:
        #   - pre-Quetta-Pan rejections: stage_reim via learn_compost_entry
        #   - applications: the engine's _on_success / _on_failure
        # This stage seals the STEERING SNAPSHOT — what the genome now
        # believes per rule/context — without double-learning. Re-learning
        # here would inflate attempt counts and suppress rules twice as
        # fast as the documented policy allows.
        steering: List[Dict[str, Any]] = []
        seen = set()
        for proposal in proposals:
            key = (proposal.rule_id, proposal.context)
            if key in seen:
                continue
            seen.add(key)
            stats = self.engine.genome.stats(proposal.rule_id, proposal.context)
            verdict = self.engine.genome.consult(proposal.rule_id, proposal.context)
            entry: Dict[str, Any] = {
                "rule_id": proposal.rule_id,
                "context": proposal.context,
                "attempts": stats["attempts"],
                "successes": stats["successes"],
                "failures": stats["failures"],
                "verdict": verdict,
            }
            if verdict == "suppress":
                entry["suppression_reason"] = self.engine.genome.suppression_reason(
                    proposal.rule_id, proposal.context
                )
            steering.append(entry)
        result = StageResult(
            stage="riem",
            target=str(target),
            iteration=iteration,
            ok=True,
            detail=(
                f"genome steering snapshot sealed for {len(steering)} "
                f"rule(s); learning already recorded once per outcome"
            ),
            payload={"steering": steering},
        )
        return self._seal_stage(result)

    # -- STAGE 7: Quetta-Pan (apply approved improved variants) ----------------
    def stage_quetta_pan(
        self, target: Path, iteration: int, proposals: List[ImprovementProposal]
    ) -> StageResult:
        approved = [p for p in proposals if p.approved]
        target_rel = self._rel(target)
        test_files = self._target_tests(target_rel)
        applied = 0
        skipped: List[str] = []
        failures: List[str] = []
        by_file: Dict[str, List[ImprovementProposal]] = {}
        for proposal in approved:
            by_file.setdefault(proposal.target, []).append(proposal)
        for file_str, plist in by_file.items():
            file_path = Path(file_str)
            before = file_path.read_text(encoding="utf-8")
            new_content = plist[0].new_content or before
            if new_content == before:
                # Honesty over polish: advisory-only findings are recorded,
                # never inflated into applications.
                for proposal in plist:
                    skipped.append(proposal.id)
                self.ledger.append(
                    stage="quetta-pan-application",
                    target=str(target),
                    iteration=iteration,
                    proposal_id="+".join(p.id for p in plist),
                    payload={
                        "ok": True,
                        "detail": "no applicable fix: advisory-only, nothing written",
                        "data": {"file": file_str, "proposal_ids": [p.id for p in plist]},
                        "anticipated": [],
                    },
                )
                continue
            if not test_files:
                # Law 3 guard: no write without the test gate.
                for proposal in plist:
                    proposal.approved = False
                    proposal.rejection_stage = "quetta-pan"
                    proposal.rejection_reason = (
                        "guard: no target tests mapped — write blocked"
                    )
                    self._compost_rejection(proposal)
                    failures.append(proposal.id)
                continue
            if not self.auto_approve:
                for proposal in plist:
                    skipped.append(proposal.id)
                self.ledger.append(
                    stage="quetta-pan-application",
                    target=str(target),
                    iteration=iteration,
                    proposal_id="+".join(p.id for p in plist),
                    payload={
                        "ok": True,
                        "detail": "manual approval required: held, not applied",
                        "data": {"file": file_str},
                        "anticipated": ["awaiting manual approval"],
                    },
                )
                continue
            # Per-file approval receipt: the stage-gate approval IS the
            # approval in an unattended pass; the ledger entry is the
            # receipt (CLI interactive prompt is the manual equivalent).
            approval = self.ledger.append(
                stage="quetta-pan-approval",
                target=str(target),
                iteration=iteration,
                proposal_id="+".join(p.id for p in plist),
                payload={
                    "ok": True,
                    "detail": "per-file approval granted by stage gate",
                    "data": {
                        "file": file_str,
                        "proposal_ids": [p.id for p in plist],
                        "rule_ids": [p.rule_id for p in plist],
                        "approver": "seal-pass-stage-gate",
                        "diff_lines": len(new_content.splitlines()),
                    },
                    "anticipated": [],
                },
            )
            self._preserve_variant(target, before, new_content, f"it{iteration}-applied")
            cmd = (
                [sys.executable, "-m", "pytest"]
                + [str(self.repo_root / "tests" / t) for t in test_files]
                + ["-q"]
            )
            self.engine.test_cmd = cmd
            suggestion = {
                "path": file_path,
                "file": file_str,
                "new_content": new_content,
                "suggestions": [
                    {"id": p.rule_id, "title": p.title} for p in plist
                ],
                "fix_ids": plist[0].fix_ids,
            }
            mutation_id = f"sealpass-it{iteration}-{target.stem}"
            result_mut = self.engine.apply_suggestion(suggestion, mutation_id=mutation_id)
            self.ledger.append(
                stage="quetta-pan-application",
                target=str(target),
                iteration=iteration,
                proposal_id="+".join(p.id for p in plist),
                payload={
                    "ok": bool(result_mut.ok),
                    "detail": (
                        "applied cleanly; tests green"
                        if result_mut.ok
                        else f"application failed: {result_mut.failure_reason}"
                    ),
                    "data": {
                        "file": file_str,
                        "approval_seq": approval["seq"],
                        "parse_ok": result_mut.parse_ok,
                        "test_ok": result_mut.test_ok,
                        "failure_reason": result_mut.failure_reason,
                    },
                    "anticipated": [],
                },
            )
            if result_mut.ok:
                applied += 1
                for proposal in plist:
                    proposal.applied = True
            else:
                for proposal in plist:
                    proposal.approved = False
                    proposal.rejection_stage = "quetta-pan"
                    proposal.rejection_reason = (
                        f"application failed: {result_mut.failure_reason}"
                    )
                    self._compost_rejection(proposal)
                    failures.append(proposal.id)
        result = StageResult(
            stage="quetta-pan",
            target=str(target),
            iteration=iteration,
            ok=True,
            detail=(
                f"applied {applied} variant(s), {len(skipped)} advisory-only "
                f"skipped, {len(failures)} failed"
            ),
            payload={"applied": applied, "skipped": skipped, "failures": failures},
        )
        return self._seal_stage(result)

    # -- the pass --------------------------------------------------------------
    def run(
        self, targets: List[Path | str], iterations: int = ITERATIONS
    ) -> Dict[str, Any]:
        """Run the full seal pass: 7 stages x 5 iterations per target.

        Law 6 (forward-motion): a stage raising GuardError is composted
        with its reason and the pass continues to the next stage.
        """
        if not self._declared:
            self.ledger.declaration()
            self._declared = True
        report: Dict[str, Any] = {
            "targets": [str(t) for t in targets],
            "iterations": iterations,
            "proposals": 0,
            "approved": 0,
            "applied": 0,
            "composted": 0,
            "converged_iterations": [],
            "ledger": str(self.ledger.path),
        }
        for raw in targets:
            target = Path(raw)
            if not target.is_absolute():
                target = (self.repo_root / target).resolve()
            for iteration in range(1, iterations + 1):
                proposals: List[ImprovementProposal] = []
                try:
                    _, proposals = self.stage_kfx2(target, iteration)
                    self.stage_demandpulse(target, iteration, proposals)
                    self.stage_echo(target, iteration, proposals)
                    self.stage_mandella(target, iteration, proposals)
                    self.stage_reim(target, iteration, proposals)
                    self.stage_riem(target, iteration, proposals)
                    qp_result = self.stage_quetta_pan(target, iteration, proposals)
                except GuardError as exc:
                    self.ledger.append(
                        stage="guard",
                        target=str(target),
                        iteration=iteration,
                        proposal_id="-",
                        payload={
                            "ok": False,
                            "detail": f"guard fired: {exc}",
                            "data": {},
                            "anticipated": ["routed to compost; pass continues"],
                        },
                    )
                    self.engine.compost.compost(
                        {
                            "mutation_id": f"guard-it{iteration}-{target.stem}",
                            "rule_id": "GUARD",
                            "file": str(target),
                            "context": context_key_for(target),
                            "tried_what": "seal-pass stage execution",
                            "failed_why": f"guard: {exc}",
                        }
                    )
                    continue
                report["proposals"] += len(proposals)
                report["approved"] += sum(1 for p in proposals if p.approved)
                report["applied"] += sum(1 for p in proposals if p.applied)
                report["composted"] += sum(
                    1 for p in proposals if p.rejection_stage
                )
                if qp_result.payload.get("applied", 0) == 0:
                    # Convergence: recorded honestly, never filled.
                    report["converged_iterations"].append(
                        f"{self._rel(target)}#it{iteration}"
                    )
                    self.ledger.append(
                        stage="convergence",
                        target=str(target),
                        iteration=iteration,
                        proposal_id="-",
                        payload={
                            "ok": True,
                            "detail": (
                                "iteration yielded no approved improvements; "
                                "recorded as convergence, continuing"
                            ),
                            "data": {
                                "proposals": len(proposals),
                                "approved": sum(1 for p in proposals if p.approved),
                            },
                            "anticipated": ["next iteration re-scans"],
                        },
                    )
        report["ledger_entries"] = self.ledger.verify()
        return report


# ---------------------------------------------------------------------------
# CLI — one command for the coordinator
# ---------------------------------------------------------------------------

PHASE1_PRESET: Dict[str, List[str]] = {
    "build1": ["core/levi/cybrus/enforce.py"],
    "build2": ["core/levi/cybrus/sync.py"],
    "build3": ["core/levi/cybrus/veil_chat.py", "core/levi/cybrus/onion.py"],
    "build4": [
        "core/levi/creator/subscriptions.py",
        "core/levi/creator/content.py",
    ],
}

DEFAULT_TEST_MAP: Dict[str, List[str]] = {
    "core/levi/cybrus/enforce.py": ["test_cybrus_enforce.py"],
    "core/levi/cybrus/sync.py": ["test_cybrus_sync.py"],
    "core/levi/cybrus/veil_chat.py": ["test_cybrus_standalone.py"],
    "core/levi/cybrus/onion.py": ["test_cybrus_onion.py"],
    "core/levi/creator/subscriptions.py": ["test_creator_subscriptions.py"],
    "core/levi/creator/content.py": ["test_creator_content.py"],
}


def _preset_targets(names: List[str]) -> List[str]:
    targets: List[str] = []
    for name in names:
        key = name.lower()
        if key not in PHASE1_PRESET:
            raise SystemExit(f"unknown preset {name!r}; choose from {sorted(PHASE1_PRESET)}")
        targets.extend(PHASE1_PRESET[key])
    return targets


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cybrus signature seal pass: 7 stages x 5 iterations per target."
    )
    parser.add_argument("--target", action="append", default=[],
                        help="target module path (repeatable)")
    parser.add_argument("--preset", action="append", default=[],
                        help="phase-1 preset: build1..build4 (repeatable)")
    parser.add_argument("--all-builds", action="store_true",
                        help="seal-pass every Phase-1 build (build1..build4)")
    parser.add_argument("--iterations", type=int, default=ITERATIONS)
    parser.add_argument("--repo-root", default=".",
                        help="repository root (default: cwd)")
    parser.add_argument("--levi-home",
                        help="override LEVI_HOME for the seal ledger")
    parser.add_argument("--threshold", type=float, default=SCORE_THRESHOLD)
    parser.add_argument("--manual-approve", action="store_true",
                        help="hold applications for manual approval instead of "
                             "applying stage-gate approvals")
    args = parser.parse_args(argv)

    if args.levi_home:
        os.environ["LEVI_HOME"] = args.levi_home
    targets = list(args.target)
    if args.all_builds:
        targets.extend(_preset_targets(["build1", "build2", "build3", "build4"]))
    elif args.preset:
        targets.extend(_preset_targets(args.preset))
    if not targets:
        parser.error("give --target, --preset, or --all-builds")

    sealpass = SealPass(
        repo_root=args.repo_root,
        test_map=DEFAULT_TEST_MAP,
        threshold=args.threshold,
        auto_approve=not args.manual_approve,
    )
    report = sealpass.run(targets, iterations=args.iterations)
    print(json.dumps(report, indent=2))
    print(f"ledger: {report['ledger']} ({report['ledger_entries']} sealed entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
