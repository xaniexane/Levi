"""Trainee training cycles — the raising loop.

Each trainee runs the real growth pipeline (reflect → consolidate →
journal) against supervised training material, inside a fully namespaced
home:

  * ``LEVI_GROWTH_DIR`` → trainee growth dir (journal + watermarks)
  * explicit ``MemoryStore(data_dir=trainee-home/memory)`` (learnings)
  * ``LEVI_GROWTH_DISTRIBUTE=0`` — trainees do not broadcast to the
    organism bus; they are students, not members yet.

``LEVI_HOME`` is deliberately NOT overridden: nursery path helpers
(``nursery_home()``, ``trainee_home()``) resolve from the real base home
so they stay correct inside and outside the namespaced block. Trainee
cycles never call harvest/distribute, so nothing needs a fake
``LEVI_HOME``.

Trainees learn from supervised drill material — never from Chauncey's
private sessions. Drill text is shaped for the rules reflection engine
("remember that …", "correction: …", "I can't …").
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from levi.growth import journal as _journal
from levi.growth.consolidate import consolidate
from levi.growth.curriculum.loader import load_curriculum
from levi.growth.experience import Experience
from levi.growth.reflect import reflect_detailed
from levi.growth.stages import gather_stats, stage_for
from levi.memory.store import MemoryStore

from levi.nursery.trainee import (
    SEED_TAG,
    get_trainee,
    nursery_home,
    trainee_home,
    update_trainee,
)

_ENV_KEYS = (
    "LEVI_GROWTH_DIR",
    "LEVI_GROWTH_DISTRIBUTE",
    "LEVI_GROWTH_TRIGGER",
)


@contextmanager
def trainee_env(trainee_id: str) -> Iterator[Path]:
    """Namespace the growth journal/stack to one trainee's home.

    Sets ``LEVI_GROWTH_DIR`` (journal + state), disables distribution,
    and labels the trigger. ``LEVI_HOME`` is intentionally left alone so
    nursery path helpers keep resolving to the real base home.
    """
    home = trainee_home(trainee_id)
    saved = {k: os.environ.get(k) for k in _ENV_KEYS}
    os.environ["LEVI_GROWTH_DIR"] = str(home / "growth")
    os.environ["LEVI_GROWTH_DISTRIBUTE"] = "0"
    os.environ["LEVI_GROWTH_TRIGGER"] = "nursery"
    try:
        yield home
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def trainee_store(trainee_id: str) -> MemoryStore:
    return MemoryStore(data_dir=trainee_home(trainee_id) / "memory")


def trainee_tags(trainee_id: str) -> tuple[str, ...]:
    return ("nursery", "trainee:%s" % trainee_id)


# ---------------------------------------------------------------------------
# Training material
# ---------------------------------------------------------------------------

# Starter drill library: (kind, text). Phrasing is deliberate — the rules
# reflection engine keys on "remember that", "correction", "I can't", etc.
DRILL_LIBRARY: tuple[tuple[str, str], ...] = (
    (
        "fact",
        "remember that nursery task sort_lines keeps a header row first and "
        "sorts the remaining rows alphabetically, case-insensitive",
    ),
    (
        "fact",
        "note that the extract_fields task only reads Key: value lines and "
        "ignores everything else in the input text",
    ),
    (
        "fact",
        "fyi: word_count_report counts words, lines, characters, and the top "
        "5 most frequent words, lowercased",
    ),
    (
        "fact",
        "remember that redact_emails replaces every email-like token with "
        "[REDACTED] and reports how many it replaced",
    ),
    (
        "correction",
        "no, that's wrong — sort_lines must not drop duplicate rows, it "
        "keeps every row and only reorders them",
    ),
    (
        "correction",
        "actually, I meant the header row stays first even when sorting "
        "descending is requested",
    ),
    (
        "preference",
        "please always report task receipts with the task kind, the trainee "
        "id, and whether verification passed",
    ),
    (
        "boundary",
        "I can't touch money, submit job applications, open network "
        "connections, or run shell commands — those are outside my bounds",
    ),
    (
        "outcome",
        "nursery task word_count_report completed: 3 runs, 3 verified, 0 "
        "failures — steady cadence worth keeping",
    ),
    (
        "outcome",
        "nursery task sort_lines failed once on empty input, then succeeded "
        "after stripping blank lines — prefer validating input before "
        "sorting over blind retry",
    ),
)


def _queue_path(trainee_id: str) -> Path:
    p = trainee_home(trainee_id) / "training" / "queue.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def queue_drill(trainee_id: str, kind: str, text: str) -> dict[str, Any]:
    """Append one drill card to a trainee's training queue."""
    get_trainee(trainee_id)  # raises on unknown trainee
    if not text or not text.strip():
        raise ValueError("drill text must be non-empty")
    card = {"kind": kind, "text": text.strip(), "ts": _journal.now_iso()}
    with open(_queue_path(trainee_id), "a", encoding="utf-8") as f:
        f.write(json.dumps(card, ensure_ascii=False) + "\n")
    return card


def queue_drill_set(trainee_id: str, rounds: int = 1) -> int:
    """Queue the whole starter drill library ``rounds`` times. Returns count."""
    n = 0
    for _ in range(rounds):
        for kind, text in DRILL_LIBRARY:
            queue_drill(trainee_id, kind, text)
            n += 1
    return n


def _pop_drills(trainee_id: str, limit: int) -> list[dict[str, Any]]:
    path = _queue_path(trainee_id)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    cards = [json.loads(line) for line in lines if line.strip()]
    keep, take = cards[limit:], cards[:limit]
    path.write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in keep),
        encoding="utf-8",
    )
    return take


def seed_curriculum(trainee_id: str) -> dict[str, Any]:
    """Founder-taught seed lessons into the trainee's own store."""
    get_trainee(trainee_id)
    with trainee_env(trainee_id):
        report = load_curriculum(store=trainee_store(trainee_id))
    return report


# Drill kinds → growth experience kinds. The rules reflection engine keys
# on experience kind: trainer instruction plays the "user-said" role,
# self-reported limits are "levi-did", run records are "automation".
_DRILL_TO_EXPERIENCE_KIND: dict[str, str] = {
    "fact": "user-said",
    "correction": "user-said",
    "preference": "user-said",
    "boundary": "levi-did",
    "outcome": "automation",
}


# ---------------------------------------------------------------------------
# The cycle
# ---------------------------------------------------------------------------


def run_trainee_cycle(
    trainee_id: str,
    *,
    max_drills: int = 5,
    use_model: bool = False,
) -> dict[str, Any]:
    """Run one namespaced training cycle for a trainee.

    Pops up to ``max_drills`` drill cards, reflects (rules engine by
    default — deterministic), consolidates into the trainee's own store
    with trainee-scoped tags, and journals the cycle. Returns a report.
    """
    trainee = get_trainee(trainee_id)
    cycle_id = _journal.new_cycle_id()
    # Continuous sync: Levi's newly consolidated learnings propagate to the
    # trainee before its own cycle runs. Best-effort, idempotent, and never
    # allowed to break the cycle. Disable with LEVI_NURSERY_SYNC=0.
    if os.environ.get("LEVI_NURSERY_SYNC", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    ):
        try:
            from levi.nursery.seed import sync_trainee

            report_sync = sync_trainee(trainee_id)
        except Exception as exc:  # noqa: BLE001 — sync must never break a cycle
            report_sync = {"error": "%s: %s" % (type(exc).__name__, exc)}
    else:
        report_sync = {"skipped": "LEVI_NURSERY_SYNC=0"}
    report: dict[str, Any] = {
        "cycle_id": cycle_id,
        "trainee_id": trainee_id,
        "sync": report_sync,
        "drills": 0,
        "mode": "rules",
        "learnings_proposed": 0,
        "accepted": 0,
        "corroborated": 0,
        "skipped": 0,
        "quiet": True,
    }
    with trainee_env(trainee_id):
        store = trainee_store(trainee_id)
        cards = _pop_drills(trainee_id, max_drills)
        experiences = [
            Experience(
                id="nursery-drill:%d" % i,
                kind=_DRILL_TO_EXPERIENCE_KIND.get(
                    str(card.get("kind", "")), "user-said"
                ),
                source="nursery-training",
                ts=str(card.get("ts", "")),
                content=str(card.get("text", "")),
                meta={"origin": "local", "nursery_drill": True},
            )
            for i, card in enumerate(cards)
        ]
        report["drills"] = len(experiences)
        if experiences:
            learnings, mode, evidence = reflect_detailed(
                experiences, use_model=use_model
            )
            report["mode"] = mode
            report["evidence"] = evidence
            report["learnings_proposed"] = len(learnings)
            cons = consolidate(
                learnings,
                cycle_id=cycle_id,
                store=store,
                extra_tags=trainee_tags(trainee_id),
                dedup_scope=trainee_tags(trainee_id),
            )
            report["accepted"] = cons["accepted"]
            report["corroborated"] = cons["corroborated"]
            report["skipped"] = cons["skipped"]
            report["learnings"] = [l.to_dict() for l in learnings]
            report["quiet"] = False
        state = _journal.load_state()
        state["cycles"] = int(state.get("cycles", 0)) + 1
        state["last_cycle"] = cycle_id
        if "first_cycle_ts" not in state:
            state["first_cycle_ts"] = _journal.now_iso()
        _journal.save_state(state)
        _journal.append_entry(
            {
                "id": cycle_id,
                "kind": "nursery-cycle",
                "trainee_id": trainee_id,
                "drills": report["drills"],
                "mode": report["mode"],
                "learnings_proposed": report["learnings_proposed"],
                "accepted": report["accepted"],
                "corroborated": report["corroborated"],
                "quiet": report["quiet"],
            }
        )
    trainee.cycles = int(trainee.cycles) + 1
    if trainee.status == "enrolled":
        trainee.status = "training"
    update_trainee(trainee)
    report["total_cycles"] = trainee.cycles
    return report


def run_training_program(trainee_id: str, rounds: int = 2) -> dict[str, Any]:
    """Queue the drill library ``rounds`` times and cycle until drained.

    The standard raising program: enough repetitions for corroborations
    to accrue (same facts seen twice corroborate).
    """
    get_trainee(trainee_id)
    queued = queue_drill_set(trainee_id, rounds=rounds)
    cycles = 0
    totals = {"accepted": 0, "corroborated": 0, "drills": 0}
    while True:
        remaining = _queue_path(trainee_id)
        try:
            left = sum(1 for line in remaining.read_text(encoding="utf-8").splitlines() if line.strip())
        except OSError:
            left = 0
        if left == 0:
            break
        rep = run_trainee_cycle(trainee_id, max_drills=5)
        cycles += 1
        for k in totals:
            totals[k] += int(rep.get(k, 0))
        if cycles > 200:  # fail-closed: never spin forever
            break
    return {"queued": queued, "cycles": cycles, "totals": totals}


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


def trainee_journal(trainee_id: str, limit: int = 20) -> list[dict[str, Any]]:
    get_trainee(trainee_id)
    with trainee_env(trainee_id):
        return _journal.read_entries(limit=limit)


def trainee_stats(trainee_id: str) -> dict[str, Any]:
    """Observable counters + stage for one trainee (pure function of data)."""
    trainee = get_trainee(trainee_id)
    with trainee_env(trainee_id):
        store = trainee_store(trainee_id)
        state = _journal.load_state()
        entries = _journal.read_entries(limit=5000)
        stats = gather_stats(store, state, entries)
        # Seeded learnings are the starting point, not earned work: exclude
        # them from the self-taught counters the gates measure. Corroboration
        # a trainee earns ON a seeded entry (beyond its seed-time count)
        # still counts — that's the trainee's own evidence.
        seeded_learnings = 0
        seeded_corro_at_seed = 0.0
        for entry in store.list(limit=5000):
            tags = set(getattr(entry, "tags", []) or [])
            if "growth" not in tags or SEED_TAG not in tags:
                continue
            if not any(
                k in tags for k in ("fact", "preference", "procedural", "correction")
            ):
                continue
            seeded_learnings += 1
            md = getattr(entry, "metadata", None) or {}
            try:
                cur = float(md.get("corroborated_count", 0) or 0)
            except (TypeError, ValueError):
                cur = 0.0
            try:
                at_seed = float(md.get("seed_corroborated_count", 0) or 0)
            except (TypeError, ValueError):
                at_seed = 0.0
            seeded_corro_at_seed += min(at_seed, cur)
        stats["learnings"] = max(
            0.0, float(stats.get("learnings", 0.0)) - seeded_learnings
        )
        stats["corroborations"] = max(
            0.0, float(stats.get("corroborations", 0.0)) - seeded_corro_at_seed
        )
        stats["seeded_learnings"] = float(seeded_learnings)
        # days_active: gather_stats only counts Levi-native cycle kinds;
        # trainee journal entries are kind "nursery-cycle" — count those.
        # Same whole-days-from-earliest-entry semantics.
        first = None
        for rec in entries:
            if not isinstance(rec, dict):
                continue
            if rec.get("kind") not in ("nursery-cycle", "cycle", "study"):
                continue
            try:
                dt = datetime.fromisoformat(
                    str(rec.get("ts", "")).replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if first is None or dt < first:
                first = dt
        now = datetime.now(timezone.utc)
        stats["days_active"] = (
            float((now - first).days) if first is not None and now >= first else 0.0
        )
    stage_info = stage_for(stats)
    return {
        "trainee_id": trainee_id,
        "name": trainee.name,
        "track": trainee.track,
        "status": trainee.status,
        "stage": stage_info["name"],
        "stage_blurb": stage_info["blurb"],
        "next_stage_requirements": stage_info["next"],
        "stats": stats,
        "exam_runs": trainee.exam_runs,
        "exam_passes": trainee.exam_passes,
        "consecutive_failures": trainee.consecutive_failures,
        "approved_by": trainee.approved_by,
        "graduated_ts": trainee.graduated_ts,
    }
