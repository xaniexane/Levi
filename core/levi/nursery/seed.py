"""Seeding + continuous sync — Levi's learnings, implanted in trainees.

Day one: every new trainee is seeded with Levi's consolidated learnings
via the growth corpus export (:func:`levi.growth.corpus_export.
collect_corpus_records`). After that, :func:`sync_trainee` propagates
newly consolidated learnings on the growth-cycle cadence — it runs at the
start of every trainee cycle, best-effort, never breaking the cycle.

Rails (same for seeding and sync):
  * only growth-tagged learnings transfer, kinds fact / procedural /
    correction — never preferences (those are Chauncey's), never
    identity, policy, or charter material (defense-in-depth denylist on
    top of the corpus export's own gating);
  * seeded learnings are tagged ``seeded`` and carry
    ``provenance.origin = "levi-seed"`` — they are the starting point,
    not the trainee's own work, and the graduation gates exclude them
    from self-taught counters;
  * the sentience guard runs again at consolidate time (last line of
    defense — a violation is skipped, loudly);
  * sync is watermarked per trainee (ingested ``memory_id`` set) and
    idempotent — re-running never double-ingests;
  * direction is one-way: Levi is the source of truth. Trainee-originated
    learnings stay local to that trainee and never propagate upward.

Same seed, different raising: after seeding, each trainee diverges
through its own cycles.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from levi.growth.consolidate import consolidate
from levi.growth.corpus_export import collect_corpus_records
from levi.growth.guards import check_no_sentience_claim
from levi.growth.reflect import Learning
from levi.memory.store import MemoryStore

from levi.nursery.trainee import SEED_TAG, get_trainee, list_trainees, trainee_home
from levi.nursery.training import trainee_store, trainee_tags

# Seed facts, earn judgment: settled knowledge (facts, procedures) is
# implanted — it skips redundancy, it doesn't hurt intelligence.
# Corrections and judgments are EARNED by each trainee through its own
# cycles; independently-converged conclusions corroborate Levi, which is
# the value the unseeded route preserves. Preferences never seed either
# (those are Chauncey's, not Levi's to give).
SEED_KINDS: tuple[str, ...] = ("fact", "procedural")

# Defense-in-depth: the corpus export already gates on growth-tagged
# learnings only, but identity/policy/charter material must never cross
# even if tagging ever slips. Case-insensitive substring markers.
_IDENTITY_POLICY_DENYLIST: tuple[str, ...] = (
    "charter",
    "i am levi",
    "i'm levi",
    "my identity",
    "identity:",
    "policy:",
    "policies:",
)


def _denied_by_rails(text: str) -> str | None:
    lowered = text.lower()
    for marker in _IDENTITY_POLICY_DENYLIST:
        if marker in lowered:
            return "identity/policy/charter marker %r" % marker
    hits = check_no_sentience_claim(text)
    if hits:
        return "sentience guard: %s" % "; ".join(sorted(set(hits)))
    return None


def collect_seed_records(
    levi_store: Any = None,
    *,
    min_confidence: float = 0.0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Collect seedable records from Levi's store.

    Returns ``(accepted, denied)`` — denied records carry the reason.
    """
    if levi_store is None:
        levi_store = MemoryStore()  # Levi's own store
    records = collect_corpus_records(levi_store, min_confidence=min_confidence)
    accepted: list[dict[str, Any]] = []
    denied: list[dict[str, Any]] = []
    for rec in records:
        text = str(rec.get("text", "") or "")
        kind = str(rec.get("kind", "") or "")
        if kind not in SEED_KINDS:
            denied.append({**rec, "deny_reason": "kind %r not seedable" % kind})
            continue
        reason = _denied_by_rails(text)
        if reason is not None:
            denied.append({**rec, "deny_reason": reason})
            continue
        accepted.append(rec)
    return accepted, denied


def _to_learnings(records: list[dict[str, Any]]) -> list[Learning]:
    learnings: list[Learning] = []
    for rec in records:
        try:
            confidence = float(rec.get("confidence", 0.5) or 0.5)
        except (TypeError, ValueError):
            confidence = 0.5
        learnings.append(
            Learning(
                kind=str(rec["kind"]),
                content=str(rec["text"]),
                confidence=max(0.05, min(1.0, confidence)),
                provenance={
                    "origin": "levi-seed",
                    "taught_by": "levi",
                    "seed_memory_id": str(rec.get("memory_id", "")),
                    "seed_coroborated_count": int(rec.get("corroborated_count", 0) or 0),
                },
            )
        )
    return learnings


def seed_trainee(
    trainee_id: str,
    records: list[dict[str, Any]] | None = None,
    *,
    levi_store: Any = None,
    min_confidence: float = 0.0,
) -> dict[str, Any]:
    """Implant Levi's learnings into a trainee's store. Returns a report."""
    trainee = get_trainee(trainee_id)
    if records is None:
        records, denied = collect_seed_records(
            levi_store, min_confidence=min_confidence
        )
    else:
        denied = []
    store = trainee_store(trainee_id)
    learnings = _to_learnings(records)
    report = consolidate(
        learnings,
        cycle_id="levi-seed",
        store=store,
        extra_tags=trainee_tags(trainee_id) + (SEED_TAG,),
        dedup_scope=trainee_tags(trainee_id),
    )
    # Stamp the seed-time corroboration count on every seeded entry so the
    # gates can later distinguish seed-earned from trainee-earned evidence.
    by_content = {}
    for entry in store.list(limit=5000):
        tags = set(getattr(entry, "tags", []) or [])
        if SEED_TAG in tags and "trainee:%s" % trainee_id in tags:
            by_content[str(getattr(entry, "content", ""))] = entry
    for rec in records:
        entry = by_content.get(str(rec.get("text", "")))
        if entry is not None:
            md = dict(getattr(entry, "metadata", None) or {})
            if "seed_corroborated_count" not in md:
                md["seed_corroborated_count"] = int(rec.get("corroborated_count", 0) or 0)
                store.update(entry.id, metadata=md)
    return {
        "trainee_id": trainee.id,
        "records": len(records),
        "denied": len(denied),
        "accepted": report["accepted"],
        "corroborated": report["corroborated"],
        "skipped": report["skipped"],
    }


# ---------------------------------------------------------------------------
# Continuous sync — watermarked, idempotent
# ---------------------------------------------------------------------------


def _sync_state_path(trainee_id: str) -> Path:
    p = trainee_home(trainee_id) / "sync" / "state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_sync_state(trainee_id: str) -> dict[str, Any]:
    try:
        data = json.loads(_sync_state_path(trainee_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_sync_state(trainee_id: str, state: dict[str, Any]) -> None:
    path = _sync_state_path(trainee_id)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def sync_trainee(
    trainee_id: str,
    *,
    levi_store: Any = None,
    min_confidence: float = 0.0,
) -> dict[str, Any]:
    """Propagate Levi's newly consolidated learnings to one trainee.

    Idempotent: only records whose ``memory_id`` was never ingested are
    implanted. Safe to run on every cycle.
    """
    trainee = get_trainee(trainee_id)
    state = _load_sync_state(trainee_id)
    ingested: set[str] = set(state.get("ingested_memory_ids", []))
    records, denied = collect_seed_records(levi_store, min_confidence=min_confidence)
    new_records = [r for r in records if str(r.get("memory_id", "")) not in ingested]
    report: dict[str, Any] = {
        "trainee_id": trainee.id,
        "new_records": len(new_records),
        "denied": len(denied),
        "accepted": 0,
        "corroborated": 0,
        "skipped": 0,
    }
    if new_records:
        seed_report = seed_trainee(trainee_id, records=new_records)
        report.update(
            {
                "accepted": seed_report["accepted"],
                "corroborated": seed_report["corroborated"],
                "skipped": seed_report["skipped"],
            }
        )
        for r in new_records:
            ingested.add(str(r.get("memory_id", "")))
    state["ingested_memory_ids"] = sorted(ingested)
    state["last_sync_ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    state["syncs"] = int(state.get("syncs", 0)) + 1
    _save_sync_state(trainee_id, state)
    report["total_ingested"] = len(ingested)
    return report


def sync_all_trainees(
    *,
    levi_store: Any = None,
    min_confidence: float = 0.0,
) -> dict[str, Any]:
    """Sync every enrolled trainee. Best-effort per trainee — one failure
    never stops the rest."""
    results: dict[str, Any] = {}
    for trainee in list_trainees():
        try:
            results[trainee.id] = sync_trainee(
                trainee.id, levi_store=levi_store, min_confidence=min_confidence
            )
        except Exception as exc:
            results[trainee.id] = {"error": "%s: %s" % (type(exc).__name__, exc)}
    return results


def sync_status(trainee_id: str) -> dict[str, Any]:
    """When a trainee last synced and how much it holds."""
    get_trainee(trainee_id)
    state = _load_sync_state(trainee_id)
    store = trainee_store(trainee_id)
    seeded = 0
    for entry in store.list(limit=5000):
        tags = set(getattr(entry, "tags", []) or [])
        if SEED_TAG in tags and "trainee:%s" % trainee_id in tags:
            seeded += 1
    return {
        "trainee_id": trainee_id,
        "syncs": int(state.get("syncs", 0)),
        "last_sync_ts": state.get("last_sync_ts", ""),
        "ingested_memory_ids": len(state.get("ingested_memory_ids", [])),
        "seeded_entries": seeded,
    }
