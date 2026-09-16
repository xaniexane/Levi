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

import os
from pathlib import Path
from typing import Any

from levi.growth import journal as _journal
from levi.growth.consolidate import consolidate
from levi.growth.distribute import distribute_learnings
from levi.growth.experience import harvest_new
from levi.growth.redact import redact_cloud_experiences
from levi.growth.reflect import reflect_detailed, reflect_cloud
from levi.growth.stages import gather_stats, stage_for


def _distribute_enabled() -> bool:
    """Distribution kill switch: ``LEVI_GROWTH_DISTRIBUTE=0`` disables."""
    return os.environ.get("LEVI_GROWTH_DISTRIBUTE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def _cycle_trigger() -> str:
    """What started this cycle: cron, study-hall, or a manual run."""
    hint = os.environ.get("LEVI_GROWTH_TRIGGER", "").strip().lower()
    if hint in ("cron", "study", "manual", "heartbeat"):
        return hint
    return "manual"


def _confidence_summary(learnings: list[dict]) -> dict[str, Any]:
    """Mean/min/max confidence over proposed learnings (0 when none)."""
    confs = [
        c
        for c in (learning.get("confidence") for learning in learnings)
        if isinstance(c, (int, float))
    ]
    if not confs:
        return {"n": 0, "mean": 0.0, "min": 0.0, "max": 0.0}
    return {
        "n": len(confs),
        "mean": round(sum(confs) / len(confs), 3),
        "min": round(min(confs), 3),
        "max": round(max(confs), 3),
    }
    """Distribution kill switch: ``LEVI_GROWTH_DISTRIBUTE=0`` disables."""
    return os.environ.get("LEVI_GROWTH_DISTRIBUTE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def _levi_home() -> Path:
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


def _creed_corroboration_hook():
    """The creed promotion hook for ``consolidate(on_corroborate=...)``.

    Lazy import + exception swallowing: growth must never break because
    the creed tracker hiccuped (``consolidate`` itself also wraps the
    call, belt and suspenders). Returns ``None`` when the creed package
    is unavailable.
    """
    try:
        from levi.creed.promotion import consolidation_corroboration_hook
    except Exception:
        return None

    def _safe(entry_id: str, store: Any) -> Any:
        try:
            return consolidation_corroboration_hook(entry_id, store)
        except Exception:
            return None

    return _safe


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
        "evidence": {},
        "learnings_proposed": 0,
        "learnings": [],
        "consolidation": {"accepted": 0, "corroborated": 0, "skipped": 0, "writes": []},
        "distribution": {
            "distributed": 0,
            "skipped": 0,
            "duplicates": 0,
            "entries": [],
            "subsystems": {},
            "bus_published": 0,
            "journal_records": [],
        },
        "quiet": not experiences,
    }

    if experiences:
        learnings, mode, evidence = reflect_detailed(local_exps, use_model=use_model)
        report["mode"] = mode
        report["evidence"] = evidence
        cloud_learnings = reflect_cloud(cloud_exps)
        learnings = list(learnings) + cloud_learnings
        report["cloud_learnings"] = len(cloud_learnings)
        report["learnings_proposed"] = len(learnings)
        report["learnings"] = [learning.to_dict() for learning in learnings]
        report["consolidation"] = consolidate(
            learnings,
            cycle_id=cycle_id,
            store=store,
            dry_run=dry_run,
            on_corroborate=_creed_corroboration_hook(),
        )
        # AXIS 9: route consolidated learnings to every subsystem they
        # concern (memory routing slips + bloodstream bus + journal).
        # Distribution is best-effort: it must never break the cycle.
        if not dry_run and _distribute_enabled():
            try:
                report["distribution"] = distribute_learnings(
                    learnings,
                    _levi_home(),
                    store=store,
                    cycle_id=cycle_id,
                )
            except Exception as exc:  # log and continue — never break the cycle
                report["distribution"] = {
                    "distributed": 0,
                    "error": "distribution failed (continuing): %s" % exc,
                }
                print("growth: %s" % report["distribution"]["error"])

    if not dry_run:
        # advance watermarks past everything we saw (even unharvestable)
        watermarks.update(new_marks)
        state["watermarks"] = watermarks
        state["last_cycle"] = cycle_id
        state["cycles"] = int(state.get("cycles", 0)) + 1
        if "first_cycle" not in state:
            state["first_cycle"] = cycle_id
            state["first_cycle_ts"] = _journal.now_iso()
        _journal.save_state(state)
        _journal.append_entry(
            {
                "id": cycle_id,
                "kind": "cycle",
                # structured fields: what started this cycle, what each
                # extractor found, and how confident the learnings were
                "trigger": _cycle_trigger(),
                "evidence": report["evidence"],
                "confidence": _confidence_summary(report["learnings"]),
                "experiences": report["experiences"],
                "sources": report["sources"],
                "mode": report["mode"],
                "learnings_proposed": report["learnings_proposed"],
                "cloud_learnings": report.get("cloud_learnings", 0),
                "accepted": report["consolidation"]["accepted"],
                "corroborated": report["consolidation"]["corroborated"],
                "memory_writes": report["consolidation"]["writes"],
                "distributed": report["distribution"].get("distributed", 0),
                "distribution_subsystems": report["distribution"].get("subsystems", {}),
                "quiet": report["quiet"],
            }
        )
    return report


def status(store: Any = None) -> dict[str, Any]:
    """Growth dashboard data: stage, counts, last cycle, pending work.

    The stage comes from :func:`levi.growth.stages.stage_for` over
    observable counters (see :func:`gather_stats`) — explicit criteria,
    no vibes. ``next_stage`` carries each unmet requirement as an
    explicit current/threshold pair so the CLI can render real progress.
    """
    state = _journal.load_state()
    entries: list[dict[str, Any]] = []
    journal_bytes = 0
    try:
        entries = _journal.read_entries(limit=200000)
        journal_bytes = _journal.journal_path().stat().st_size
    except OSError:
        pass

    learnings = 0
    by_kind: dict[str, int] = {}
    stats: dict[str, float] = {
        "learnings": 0.0,
        "corroborations": 0.0,
        "days_active": 0.0,
        "curriculum_units": 0.0,
        "cycles": 0.0,
    }
    recent_7d = 0
    try:
        from levi.memory.store import MemoryStore

        s = store or MemoryStore()
        mem_entries = s.list(limit=5000)
        stats = gather_stats(s, state, entries)
        learnings = int(stats["learnings"])
        distributed = len(
            [
                e
                for e in mem_entries
                if "growth" in (e.tags or []) and "distribution" in (e.tags or [])
            ]
        )
        for e in mem_entries:
            tags = set(e.tags or [])
            if "growth" not in tags or "distribution" in tags or "curriculum" in tags:
                continue
            for t in tags:
                if t in ("fact", "preference", "procedural", "correction"):
                    by_kind[t] = by_kind.get(t, 0) + 1
        recent_7d = _recent_learnings(mem_entries, days=7)
    except Exception:
        distributed = 0

    # pending = experiences newer than the watermark
    pending, _ = harvest_new(since=dict(state.get("watermarks", {})))
    pending_sources = _source_breakdown(pending)
    stage = stage_for(stats)
    last = next((e for e in entries if e.get("kind") in ("cycle", "study")), None)
    return {
        "stage": stage["name"],
        "stage_blurb": f"{stage['blurb']} "
        f"({learnings} learnings over {int(stats['cycles'])} cycles)",
        "stage_criteria": stage["criteria"],
        "next_stage": stage["next"],
        "stats": stats,
        "cycles_completed": int(stats["cycles"]),
        "learnings_consolidated": learnings,
        "learnings_distributed": distributed,
        "learnings_by_kind": by_kind,
        "recent_learnings_7d": recent_7d,
        "experiences_pending": len(pending),
        "pending_by_source": pending_sources,
        "journal_records": len(entries),
        "journal_bytes": journal_bytes,
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


def _recent_learnings(mem_entries: list[Any], *, days: int = 7) -> int:
    """Count self-taught growth learnings created within the last N days."""
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    n = 0
    for e in mem_entries:
        tags = set(getattr(e, "tags", []) or [])
        if "growth" not in tags or "distribution" in tags or "curriculum" in tags:
            continue
        if not any(
            k in tags for k in ("fact", "preference", "procedural", "correction")
        ):
            continue
        try:
            dt = datetime.fromisoformat(
                str(getattr(e, "created_at", "")).replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt >= cutoff:
            n += 1
    return n
