"""Admin Command Center — `admin.py` (spec §4 system 2, §10, §5).

The operator's console for market activation: gate stages, checklist
gates, launch readiness, the dispute queue, and the pull-based nudge
queue. Disputes are decided by a human (`work.resolve_dispute`); this
module only surfaces the queue.

LAWS (machine-checked by `check_laws`):
- L1: stages advance one step at a time, never skipped — an override
  requires a named operator and is always logged to the decisions
  stream.
- L2: advancing requires the target stage's checklist fully checked
  (config in policies.json `gates.checklists` — the operator's list,
  not code).
- L3: nudges are pull-first, push-second. `pull_nudges` always works and
  never delivers anything. The push path is additive and explicit:
  only `drain_nudges` sends, it goes through the notifier's honest
  backends, and a nudge is never double-sent. Nothing here sends on
  its own — the drain runs from a scheduled job the operator owns.
- L4: the stage history is append-only — every change is an entry in
  the decisions stream with who, what, and why.
"""

from __future__ import annotations

from typing import Any

from . import policies as policies_mod
from .store import Store
from .waitlist import waitlist_depth
from .work import open_disputes


def stage(store: Store) -> str:
    return policies_mod.load_policies(store).get("gates", {}).get(
        "stage", "waitlist_only"
    )


def _write_stage(
    store: Store, new_stage: str, operator: str, note: str, now: str | None
) -> dict[str, Any]:
    """Persist the stage in the operator's policies.json and log it."""
    path = store.ensure_policies()
    import json

    cfg = json.loads(path.read_text(encoding="utf-8"))
    old = cfg.get("gates", {}).get("stage", "waitlist_only")
    cfg["gates"]["stage"] = new_stage
    path.write_text(json.dumps(cfg, indent=2, sort_keys=True), encoding="utf-8")
    return store.append(
        "decisions",
        {
            "kind": "gate_stage",
            "from": old,
            "to": new_stage,
            "operator": operator,
            "note": note,
        },
        now=now,
    )


def stage_checklist(store: Store, target_stage: str) -> dict[str, Any]:
    """Evaluate the operator's checklist for a stage (config, not vibes)."""
    policies = policies_mod.load_policies(store)
    checklists = policies.get("gates", {}).get("checklists", {})
    items = checklists.get(target_stage, [])
    done = [i for i in items if i.get("done")]
    return {
        "stage": target_stage,
        "items": items,
        "done": len(done),
        "total": len(items),
        "complete": bool(items) and len(done) == len(items),
    }


def advance_stage(
    store: Store, operator: str, confirm: bool = False, now: str | None = None
) -> dict[str, Any]:
    """Move to the next activation stage. Permission = explicit confirm.

    Refuses when the next stage's checklist is incomplete; refuses to
    skip stages (use `override_stage`, which logs the override).
    """
    if not confirm:
        raise PermissionError("advance_stage requires confirm=True (Permission step)")
    if not operator:
        raise ValueError("advance_stage requires a named human operator")
    policies = policies_mod.load_policies(store)
    stages = policies.get("gates", {}).get("stages", [])
    current = stage(store)
    idx = stages.index(current)
    if idx + 1 >= len(stages):
        raise ValueError(f"stage '{current}' is already the final stage")
    nxt = stages[idx + 1]
    checklist = stage_checklist(store, nxt)
    if not checklist["complete"]:
        missing = [i.get("id") for i in checklist["items"] if not i.get("done")]
        raise ValueError(
            f"stage '{nxt}' checklist incomplete — missing: {missing}"
        )
    return _write_stage(store, nxt, operator, "checklist complete", now)


def override_stage(
    store: Store,
    target_stage: str,
    operator: str,
    reason: str,
    confirm: bool = False,
    now: str | None = None,
) -> dict[str, Any]:
    """Explicit operator override of the stage machine. Always logged."""
    if not confirm:
        raise PermissionError("override_stage requires confirm=True (Permission step)")
    if not operator or not reason:
        raise ValueError("override_stage requires a named operator and a reason")
    policies = policies_mod.load_policies(store)
    stages = policies.get("gates", {}).get("stages", [])
    if target_stage not in stages:
        raise ValueError(f"unknown stage {target_stage!r}")
    return _write_stage(
        store, target_stage, operator, f"OVERRIDE: {reason}", now
    )


def stage_history(store: Store) -> list[dict[str, Any]]:
    return [
        d for d in store.read_all("decisions") if d.get("kind") == "gate_stage"
    ]


# -- launch readiness ----------------------------------------------------
def launch_readiness(store: Store, neighborhood_cell: str) -> dict[str, Any]:
    """Launch Readiness Score (spec §5, phase 2): 0–100 per cell.

    Formula (documented, config-thresholded, honest about thin data):
    - waitlist depth: 0–30 pts (full at `waitlist_full` waitlisted/invited)
    - worker supply: 0–30 pts (full at `workers_full` active workers in cell)
    - gate checklist: 0–40 pts (fraction of the *current* stage's checklist)
    """
    policies = policies_mod.load_policies(store)
    cfg = policies.get("readiness", {"waitlist_full": 10, "workers_full": 5})
    depth = waitlist_depth(store, neighborhood_cell)["total"]
    depth_pts = round(30 * min(1.0, depth / max(1, cfg["waitlist_full"])), 1)

    workers: dict[str, dict] = {}
    for w in store.read_all("workers"):
        workers[w["id"]] = w
    active = sum(
        1
        for w in workers.values()
        if w.get("status") == "active"
        and w.get("available", True)
        and w.get("home_cell") == neighborhood_cell
    )
    supply_pts = round(30 * min(1.0, active / max(1, cfg["workers_full"])), 1)

    checklist = stage_checklist(store, stage(store))
    gate_pts = round(
        40 * (checklist["done"] / checklist["total"]) if checklist["total"] else 0.0,
        1,
    )
    return {
        "cell": neighborhood_cell,
        "score": round(depth_pts + supply_pts + gate_pts, 1),
        "components": {
            "waitlist_depth": {"points": depth_pts, "depth": depth},
            "worker_supply": {"points": supply_pts, "active_workers": active},
            "gate_checklist": {"points": gate_pts, **{k: checklist[k] for k in ("done", "total")}},
        },
    }


# -- dispute queue ---------------------------------------------------------
def dispute_queue(store: Store) -> list[dict[str, Any]]:
    """Admin view of open disputes with their gig context (humans decide)."""
    from .post import latest_gig

    queue = []
    for d in open_disputes(store):
        gig = latest_gig(store, d.get("gig_id")) or {}
        queue.append(
            {
                "dispute": d,
                "gig_title": gig.get("title"),
                "gig_status": gig.get("status"),
                "worker_id": gig.get("worker_id"),
                "requester": gig.get("requester"),
            }
        )
    return queue


# -- nudge queue: pull-first, push-second (drain_nudges is additive) ------
def queue_nudge(
    store: Store,
    kind: str,
    message: str,
    cell: str | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Queue a nudge for the operator to pull. Never delivered anywhere."""
    return store.append(
        "nudges",
        {
            "id": store.next_id("nudge"),
            "kind": kind,
            "message": message,
            "cell": cell,
            "status": "queued",
        },
        now=now,
    )


def pull_nudges(store: Store, now: str | None = None) -> list[dict[str, Any]]:
    """The operator pulls queued nudges; pulled ones are marked read."""
    latest: dict[str, dict] = {}
    for n in store.read_all("nudges"):
        latest[n["id"]] = n
    queued = [n for n in latest.values() if n.get("status") == "queued"]
    for n in queued:
        record = dict(n)
        record.pop("seq", None)
        record.pop("ts", None)
        record["status"] = "pulled"
        store.append("nudges", record, now=now)
    return queued


def drain_nudges(
    store: Store,
    notifier: Any,
    backends: list[str] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Push-path drain of the nudge queue (L3: additive, never automatic).

    Sends each queued nudge through the notifier's backends. A nudge is
    marked "sent" (statuses recorded on the stream entry) unless a
    backend reported a transient "failed" — failures stay queued for
    the next drain, and the notifier's dedupe means a retry never
    double-sends. `pull_nudges` keeps working as the pull fallback.
    """
    latest: dict[str, dict] = {}
    for n in store.read_all("nudges"):
        latest[n["id"]] = n
    queued = [n for n in latest.values() if n.get("status") == "queued"]
    receipt: dict[str, Any] = {
        "drained": len(queued),
        "sent": [],
        "retried": [],
        "statuses": {},
    }
    for n in queued:
        notification = {
            "id": n["id"],
            "title": f"NeighborOS nudge [{n.get('kind', 'note')}]",
            "body": n.get("message", ""),
            "kind": f"nudge:{n.get('kind', 'note')}",
            "cell": n.get("cell"),
        }
        statuses = notifier.send(notification, backends=backends)
        for b, s in statuses.items():
            receipt["statuses"].setdefault(b, []).append(s)
        if any(str(s).startswith("failed") for s in statuses.values()):
            receipt["retried"].append(n["id"])
            continue  # stays queued; the next drain retries
        record = dict(n)
        record.pop("seq", None)
        record.pop("ts", None)
        record["status"] = "sent"
        record["via"] = statuses
        store.append("nudges", record, now=now)
        receipt["sent"].append(n["id"])
    return receipt


def check_laws(store: Store) -> dict[str, Any]:
    """Machine-check the admin laws against live state."""
    checks: dict[str, dict] = {}
    policies = policies_mod.load_policies(store)
    stages = policies.get("gates", {}).get("stages", [])
    hist = stage_history(store)
    # L1/L4: every stage change logged, and logged changes form a valid
    # forward walk unless marked OVERRIDE.
    ok = True
    prev = None
    for h in hist:
        if "OVERRIDE" not in h.get("note", ""):
            if prev is not None and stages.index(h["to"]) != stages.index(prev) + 1:
                ok = False
        prev = h["to"]
    checks["stage_history_valid"] = {"ok": ok, "changes": len(hist)}
    missing_operator = [h.get("seq") for h in hist if not h.get("operator")]
    checks["changes_have_operator"] = {
        "ok": not missing_operator,
        "violations": missing_operator,
    }
    current = stage(store)
    checks["stage_known"] = {"ok": current in stages, "stage": current}
    return {"ok": all(c["ok"] for c in checks.values()), "checks": checks}
