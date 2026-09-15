"""One growth cycle: harvest → reflect → consolidate → journal.

``run_cycle()`` is idempotent: a per-source watermark in
``~/.levi/growth/state.json`` means re-running never re-harvests the
same session records. A cycle with nothing new still journals a quiet
record — the baby book notes quiet days too.

Safety rails (binding):
  * the cycle READS sessions/automations and WRITES ONLY to the memory
    store (growth-tagged entries) and the journal. It never touches
    tools, policy, identity, the charter, or any other subsystem.
  * every learning carries provenance (source, timestamp, engine) and
    ``status: provisional`` — Levi's self-taught beliefs are always
    marked as such, never presented as certain.
  * ``dry_run=True`` previews the whole cycle without writing anything.
"""

from __future__ import annotations

from typing import Any

from levi.growth import journal as _journal
from levi.growth.consolidate import consolidate
from levi.growth.experience import harvest_new
from levi.growth.redact import redact_cloud_experiences
from levi.growth.reflect import reflect, reflect_cloud


def _source_breakdown(experiences: list) -> dict:
    """Counts by origin, plus per-provider counts for cloud."""
    by_origin: dict[str, int] = {}
    providers: dict[str, int] = {}
    for e in experiences:
        origin = str(e.meta.get("origin", "local") or "local")
        by_origin[origin] = by_origin.get(origin, 0) + 1
        if origin == "cloud":
            p = str(e.meta.get("provider", "?") or "?")
            providers[p] = providers.get(p, 0) + 1
    return {"by_origin": by_origin, "cloud_providers": providers}


def run_cycle(
    *,
    use_model: bool = True,
    dry_run: bool = False,
    store: Any = None,
) -> dict[str, Any]:
    """Run one growth cycle. Returns a full report dict.

    Raises ValueError when ``store`` is provided but lacks the
    memory-store interface (``add``/``update``).
    """
    if store is not None and not (hasattr(store, "add") and hasattr(store, "update")):
        raise ValueError(
            "run_cycle: store must provide add() and update(), got %s"
            % type(store).__name__
        )
    cycle_id = _journal.new_cycle_id()
    state = _journal.load_state()
    watermarks = dict(state.get("watermarks", {}))

    experiences, new_marks = harvest_new(since=watermarks)

    # Cloud experiences go through the redaction gate BEFORE any
    # reflection, and are distilled separately (techniques only —
    # never another user's facts/preferences).
    local_exps = [e for e in experiences if e.meta.get("origin") != "cloud"]
    cloud_exps = redact_cloud_experiences(
        [e for e in experiences if e.meta.get("origin") == "cloud"]
    )
    sources = _source_breakdown(experiences)

    report: dict[str, Any] = {
        "cycle_id": cycle_id,
        "dry_run": dry_run,
        "experiences": len(experiences),
        "sources": sources,
        "mode": "rules",
        "learnings_proposed": 0,
        "learnings": [],
        "consolidation": {"accepted": 0, "corroborated": 0, "skipped": 0, "writes": []},
        "quiet": not experiences,
    }

    if experiences:
        learnings, mode = reflect(local_exps, use_model=use_model)
        report["mode"] = mode
        cloud_learnings = reflect_cloud(cloud_exps)
        learnings = list(learnings) + cloud_learnings
        report["cloud_learnings"] = len(cloud_learnings)
        report["learnings_proposed"] = len(learnings)
        report["learnings"] = [learning.to_dict() for learning in learnings]
        report["consolidation"] = consolidate(
            learnings, cycle_id=cycle_id, store=store, dry_run=dry_run
        )

    if not dry_run:
        # advance watermarks past everything we saw (even unharvestable)
        watermarks.update(new_marks)
        state["watermarks"] = watermarks
        state["last_cycle"] = cycle_id
        state["cycles"] = int(state.get("cycles", 0)) + 1
        _journal.save_state(state)
        _journal.append_entry(
            {
                "id": cycle_id,
                "kind": "cycle",
                "experiences": report["experiences"],
                "sources": report["sources"],
                "mode": report["mode"],
                "learnings_proposed": report["learnings_proposed"],
                "cloud_learnings": report.get("cloud_learnings", 0),
                "accepted": report["consolidation"]["accepted"],
                "corroborated": report["consolidation"]["corroborated"],
                "memory_writes": report["consolidation"]["writes"],
                "quiet": report["quiet"],
            }
        )
    return report


def status(store: Any = None) -> dict[str, Any]:
    """Growth dashboard data: stage, counts, last cycle, pending work."""
    state = _journal.load_state()
    cycles = int(state.get("cycles", 0))
    learnings = 0
    by_kind: dict[str, int] = {}
    try:
        from levi.memory.store import MemoryStore

        s = store or MemoryStore()
        entries = [e for e in s.list(limit=5000) if "growth" in e.tags]
        learnings = len(entries)
        for e in entries:
            for t in e.tags:
                if t in ("fact", "preference", "procedural", "correction"):
                    by_kind[t] = by_kind.get(t, 0) + 1
    except Exception:
        pass

    # pending = experiences newer than the watermark
    pending, _ = harvest_new(since=dict(state.get("watermarks", {})))
    pending_sources = _source_breakdown(pending)
    stage_name, stage_blurb = _journal.developmental_stage(learnings, cycles)
    entries = _journal.read_entries(limit=1)
    last = entries[0] if entries else None
    return {
        "stage": stage_name,
        "stage_blurb": stage_blurb,
        "cycles_completed": cycles,
        "learnings_consolidated": learnings,
        "learnings_by_kind": by_kind,
        "experiences_pending": len(pending),
        "pending_by_source": pending_sources,
        "last_cycle": (
            {
                "id": last.get("id"),
                "ts": last.get("ts"),
                "mode": last.get("mode"),
                "accepted": last.get("accepted"),
                "sources": last.get("sources"),
            }
            if last
            else None
        ),
        "growth_dir": str(_journal.growth_dir()),
    }
