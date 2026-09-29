"""agent x pi — the fan-out/fan-in pass at the heart of the Quetta-Pan loop.

Chauncey's formula (2026-09-27, his ruling): one agent x pi — one job fans
out into parallel agent work, then the results converge into one answer.
It lives in REIM/RIEM: recursion WITHOUT collapse, controlled compression.
His note on this build: "It was supposed to have it from begining anyway" —
so this is a core loop pass, not a bolt-on: it sits between suggestion and
the guarded write path, and that write path itself is untouched.

The constant: AGENT_PI (math.pi) names the pass. The expansion is pi-like —
in principle without end or repetition; in practice bounded by
PI_FANOUT_CAP so the loop stays tractable. Variants beyond the cap are
receipted as declined-cap, never silently dropped (Qpi2).

LAWS (declared up front, machine-checked in tests/test_agent_pi.py):
  Qpi1 NO-COLLAPSE     Distinct winning rule-sets keep distinct genome
                      slots. Fan-in folds equivalent wins into one
                      bundle slot — that folding IS the controlled
                      compression. It never merges different rule-sets
                      into one slot.
  Qpi2 NO-SILENT-DROP Every fanned-out proposal ends receipted: win,
                      composted, or declined-cap. The receipt always
                      covers every proposal, including cap overflow.
  Qpi3 GENOME-FIRST   The genome is consulted before generation.
                      suggest_upgrades() already withholds suppressed
                      rules and their fixes, so a suppressed fix can
                      never become a variant.
  Qpi4 OFFLINE        No network in this pass. stdlib only; no
                      networking-library imports (grep-gated).
  Qpi5 FAIL-CLOSED    A variant that raises during evaluation fails:
                      composted, never applied, target file untouched.
  Qpi6 PASS-WRITES-NOTHING  The pass itself never writes the target
                      file. Variants are evaluated against temp copies;
                      the single real write (if any) goes through the
                      engine's guarded apply_suggestion path
                      (backup -> write -> evaluate -> rollback/compost).
"""

from __future__ import annotations

import itertools
import math
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .evaluate import evaluate_mutation
from .riem import context_key_for

# The formula's constant. The pass expands a single job the way pi
# expands: without repeating, without end in principle — bounded in
# practice by PI_FANOUT_CAP below.
AGENT_PI = math.pi

# Max variant proposals per job. 7 = every non-empty subset of up to 3
# safe fixes. Overflow subsets are receipted as declined-cap (Qpi2),
# never silently dropped.
PI_FANOUT_CAP = 7

OUTCOMES = ("win", "composted", "declined-cap")


@dataclass(frozen=True)
class PiProposal:
    """One fanned-out variant: a subset of safe fixes applied to the
    original content. Immutable — evaluation never mutates it."""

    variant_id: str
    fix_ids: Tuple[str, ...]
    content: str
    risk: float


@dataclass(frozen=True)
class PiDisposition:
    """What fan-in did with one proposal. One per proposal, always."""

    proposal_id: str
    outcome: str  # one of OUTCOMES
    detail: str = ""


@dataclass
class PiReceipt:
    """The whole pass, receipted. Qpi2: dispositions cover every
    proposal, including cap overflow."""

    ts: str
    job_id: str
    file: str
    n_proposals: int
    dispositions: List[PiDisposition] = field(default_factory=list)
    winner: Optional[PiProposal] = None
    composted: int = 0
    genome_wins: int = 0
    applied: bool = False
    note: str = ""

    def disposition_for(self, proposal_id: str) -> Optional[PiDisposition]:
        for d in self.dispositions:
            if d.proposal_id == proposal_id:
                return d
        return None


def _subsets(fix_ids: List[str]):
    """Non-empty subsets, deterministic order: by size, then
    lexicographic. The pi-like expansion, truncated by the cap."""
    ids = sorted(set(fix_ids))
    out = []
    for size in range(1, len(ids) + 1):
        for combo in itertools.combinations(ids, size):
            out.append(combo)
    return out


def fan_out(
    engine, suggestion: Dict, max_variants: int = PI_FANOUT_CAP
) -> Tuple[List[PiProposal], List[Tuple[str, ...]]]:
    """Fan one job out into parallel variant proposals.

    Takes a suggestion dict from engine.suggest_upgrades() — the genome
    has already been consulted there (Qpi3), so suppressed fixes are
    already withheld and can never become variants here.

    Returns (proposals, declined): declined holds fix-subsets beyond
    max_variants, receipted later as declined-cap (Qpi2).
    """
    path = Path(suggestion["path"])
    suffix = path.suffix
    original = path.read_text(encoding="utf-8")
    subsets = _subsets(list(suggestion.get("fix_ids", [])))

    proposals: List[PiProposal] = []
    declined: List[Tuple[str, ...]] = []
    for idx, combo in enumerate(subsets):
        if idx >= max_variants:
            declined.append(combo)
            continue
        content, _applied = engine.safe_fixes(original, suffix, only=set(combo))
        proposals.append(
            PiProposal(
                variant_id=f"pi-{idx + 1:02d}",
                fix_ids=combo,
                content=content,
                risk=0.02 + 0.05 * len(combo),
            )
        )
    return proposals, declined


def fan_in(
    engine,
    proposals: List[PiProposal],
    declined: List[Tuple[str, ...]] = (),
    *,
    context: str,
    file_label: str,
    job_id: str,
    original_content: str,
    suffix: str,
) -> PiReceipt:
    """Converge the fanned-out proposals into one answer.

    Each variant is evaluated against a temp copy — the target file is
    never touched here (Qpi6). Wins compress into the genome via the
    engine's own learning path (equivalent bundles fold into one slot:
    controlled compression; distinct rule-sets keep distinct slots:
    no collapse — Qpi1). Failures compost to REIM, each with its own
    entry. Every proposal ends receipted (Qpi2); anything that raises
    during evaluation fails closed (Qpi5).
    """
    ts = datetime.now(timezone.utc).isoformat()
    dispositions: List[PiDisposition] = []
    wins: List[Tuple[PiProposal, object]] = []
    composted = 0

    for prop in proposals:
        bundle = "+".join(prop.fix_ids)
        try:
            with tempfile.TemporaryDirectory(prefix="agent-pi-") as tmp:
                probe = Path(tmp) / f"probe{suffix}"
                probe.write_text(prop.content, encoding="utf-8")
                result = evaluate_mutation(
                    probe,
                    original_content,
                    prop.content,
                    suggest_fn=engine.all_heuristics,
                    test_cmd=engine.test_cmd,
                )
        except Exception as exc:  # Qpi5: fail closed, never apply
            result = None
            failure_reason = f"pi guard: evaluation raised: {exc}"
        else:
            failure_reason = result.failure_reason

        if result is not None and result.ok:
            wins.append((prop, result))
            dispositions.append(
                PiDisposition(prop.variant_id, "win", "parse+tests green")
            )
        else:
            engine.compost.compost(
                {
                    "mutation_id": f"{job_id}:{prop.variant_id}",
                    "rule_id": bundle or "NO_RULE",
                    "file": file_label,
                    "context": context,
                    "tried_what": (
                        f"agent-pi variant {sorted(prop.fix_ids)} (fan-out of {job_id})"
                    ),
                    "failed_why": failure_reason,
                }
            )
            composted += 1
            dispositions.append(
                PiDisposition(prop.variant_id, "composted", failure_reason)
            )

    for combo in declined:
        dispositions.append(
            PiDisposition(
                "pi-cap:" + "+".join(combo),
                "declined-cap",
                f"beyond PI_FANOUT_CAP={PI_FANOUT_CAP}; not evaluated",
            )
        )

    # Controlled compression: equivalent wins fold into one bundle slot
    # (attempts accumulate); distinct rule-sets keep distinct slots —
    # that distinction IS the no-collapse guarantee (Qpi1).
    genome_wins = 0
    for prop, _result in wins:
        engine._learn_outcome(
            list(prop.fix_ids),
            context,
            True,
            f"{job_id}:{prop.variant_id} agent-pi win on {file_label}",
        )
        genome_wins += 1

    # One answer: best heuristic improvement, then lowest risk, then
    # deterministic variant order.
    winner = None
    if wins:
        wins.sort(
            key=lambda pr: (
                -(pr[1].heuristics_before - pr[1].heuristics_after),
                pr[0].risk,
                pr[0].variant_id,
            )
        )
        winner = wins[0][0]

    return PiReceipt(
        ts=ts,
        job_id=job_id,
        file=file_label,
        n_proposals=len(proposals),
        dispositions=dispositions,
        winner=winner,
        composted=composted,
        genome_wins=genome_wins,
    )


def agent_pi_pass(engine, file_path, *, apply: bool = False) -> PiReceipt:
    """The agent x pi core-loop pass for one file.

    suggest (genome-first) -> fan out -> fan in -> optionally apply the
    winner through the engine's guarded write path. The pass itself
    never writes the target file (Qpi6); apply=False is the default,
    keeping the package's dry-run posture.
    """
    file_path = Path(file_path)
    context = context_key_for(file_path)
    job_id = f"pi-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
    suggestion = engine.suggest_upgrades(file_path)

    if not suggestion.get("has_changes") or not suggestion.get("fix_ids"):
        return PiReceipt(
            ts=datetime.now(timezone.utc).isoformat(),
            job_id=job_id,
            file=suggestion["file"],
            n_proposals=0,
            note="no variants: nothing to fan out",
        )

    proposals, declined = fan_out(engine, suggestion)
    original = file_path.read_text(encoding="utf-8")
    receipt = fan_in(
        engine,
        proposals,
        declined,
        context=context,
        file_label=suggestion["file"],
        job_id=job_id,
        original_content=original,
        suffix=file_path.suffix,
    )

    if apply and receipt.winner is not None:
        winner = receipt.winner
        winner_suggestion = {
            "path": file_path,
            "file": suggestion["file"],
            "new_content": winner.content,
            "fix_ids": list(winner.fix_ids),
            # The mutation's rules ARE the winning fix ids — the
            # guarded path learns per rule from these.
            "suggestions": [
                {"id": fid, "title": f"agent-pi win: {fid}"} for fid in winner.fix_ids
            ],
        }
        result = engine.apply_suggestion(winner_suggestion)
        receipt.applied = result.ok
        if not result.ok:
            receipt.note = f"winner failed the guarded write: {result.failure_reason}"
    return receipt


def run_pi(engine, dry_run: bool = True) -> Dict[str, int]:
    """Scan -> agent-pi pass per file -> optional per-file apply.

    dry_run=True (default): the pass evaluates, nothing is written, ever.
    """
    stats = {
        "scanned": 0,
        "fanned": 0,
        "wins": 0,
        "composted": 0,
        "applied": 0,
    }
    for file_path in engine.scan():
        stats["scanned"] += 1
        receipt = agent_pi_pass(engine, file_path)
        if receipt.n_proposals == 0:
            continue
        stats["fanned"] += 1
        stats["composted"] += receipt.composted
        if receipt.winner is not None:
            stats["wins"] += 1
            wid = receipt.winner.variant_id
            fixes = "+".join(receipt.winner.fix_ids)
            print(f"  [agent-pi] {receipt.file}: winner {wid} ({fixes})")
        else:
            print(
                f"  [agent-pi] {receipt.file}: no winner "
                f"({receipt.composted} composted)"
            )
        if dry_run:
            continue
        if receipt.winner is None:
            continue
        choice = (
            input(f"Apply agent-pi winner to {receipt.file}? (y/n/q): ").strip().lower()
        )
        if choice == "q":
            break
        if choice != "y":
            continue
        applied_receipt = agent_pi_pass(engine, file_path, apply=True)
        if applied_receipt.applied:
            stats["applied"] += 1
            print(f"  applied {receipt.file}")
        else:
            print(f"  guarded write refused: {applied_receipt.note}")
    return stats
