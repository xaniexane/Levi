"""THE SITE LIFT — NeighborOS's hedged capability, built un-hedged.

Canon: docs/LEXICON.md @ 50e2979 — "the thing that keeps getting hedged,
that other platforms don't want out. The forge builds it un-hedged,
LEVI-native, unafraid: whatever the gig platforms suppress, NeighborOS
ships."

What the gig platforms hedge, and what the Lift ships instead:

1. REPUTATION HOSTAGE → PORTABLE PASSPORT. Other platforms own the
   worker's reputation data so it can't leave. Here the worker's
   reputation is assembled from the Credential Graph + Proof-of-Work
   Ledger into a signed, exportable passport. One command exports it;
   leaving costs nothing.

2. OPAQUE DISPATCH → EXPLAINABLE MATCHING. Other platforms run black-box
   throttling — the worker never knows why they got the job or didn't.
   Here every match decision is scored from open rules listed in
   policies.json, every score carries its explanation, and every offer
   is logged to the decisions stream. No rule may be applied that isn't
   in the policy list — hidden rules are a hard error, not a feature.

3. CONTACT HIDING → DIRECT RELATIONSHIPS. Other platforms hide
   worker/customer contact to tax the relationship (disintermediation
   tax). Here contacts are plain and mutual on every record, and
   ``assert_no_contact_hiding`` scans every record for masked/hidden/
   redacted fields. The platform never taxes the worker-customer bond.

4. 20–40% COMMISSIONS → THE 90% FLOOR. ``worker_keep_floor = 0.90`` in
   policy config, enforced on every settlement, with fees existing only
   on completed + paid jobs.

Hierarchy: Alpha & Omega first and last → Levi head of all beneath them
→ the rest. Proving bar: green, lawful, keeper-reviewed.
This module marks itself ready-for-review; it never claims his review.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from . import policies as policies_mod
from .post import assign_worker, latest_gig, transition
from .store import Store
from .work import latest_worker

READY_FOR_REVIEW = True  # keeper review is his act, never claimed here

# The four un-hedged guarantees, as data the platform can report on.
PLATFORM_RULES = (
    "reputation_is_portable",
    "dispatch_is_explainable",
    "relationships_are_direct",
    "workers_keep_ninety_percent",
)

_BANNED_CONTACT_PATTERNS = re.compile(
    r"mask|hidden|redact|anonym|obscur", re.IGNORECASE
)


def assert_no_contact_hiding(record: dict[str, Any]) -> None:
    """Site Lift law 3: no field may suppress worker/customer identity.

    Scans keys (and string values) for masking language. A masked value
    like "•••-•••-1234" or a key like "masked_phone" fails loudly.
    """
    offenders: list[str] = []

    def scan(obj: Any, trail: str) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if _BANNED_CONTACT_PATTERNS.search(str(key)):
                    offenders.append(f"{trail}.{key}")
                scan(value, f"{trail}.{key}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                scan(item, f"{trail}[{i}]")
        elif isinstance(obj, str):
            if "•••" in obj or "***" in obj and "@" not in obj.replace("***", ""):
                offenders.append(f"{trail}={obj!r}")

    scan(record, "record")
    if offenders:
        raise ValueError(
            "contact-hiding detected (Site Lift law: relationships are direct): "
            + ", ".join(offenders)
        )


# -- transparent dispatch ---------------------------------------------
def _rule_fns() -> dict[str, Any]:
    """Open dispatch rules. ONLY ids listed in policies may ever run."""

    def category_match(gig, worker, ctx):
        ok = gig.get("category") in (worker.get("categories") or [])
        return (
            ok,
            f"category '{gig.get('category')}' {'in' if ok else 'not in'} worker skills",
        )

    def dna_familiarity(gig, worker, ctx):
        fam = gig.get("dna_family")
        done = any(
            g.get("worker_id") == worker.get("id")
            and g.get("dna_family") == fam
            and g.get("status") in ("done", "paid")
            for g in ctx["gigs"]
        )
        return done, (
            f"worker has completed this DNA family before ({fam})"
            if done
            else "no prior jobs in this DNA family"
        )

    def proximity(gig, worker, ctx):
        ok = worker.get("home_cell") == gig.get("neighborhood_cell")
        return ok, (
            f"worker home cell '{worker.get('home_cell')}' matches job cell"
            if ok
            else f"worker in '{worker.get('home_cell')}', job in '{gig.get('neighborhood_cell')}'"
        )

    def availability(gig, worker, ctx):
        ok = bool(worker.get("available", True))
        return ok, "worker is available" if ok else "worker is unavailable"

    def rating(gig, worker, ctx):
        ratings = [
            g["rating"]
            for g in ctx["gigs"]
            if g.get("worker_id") == worker.get("id") and g.get("rating")
        ]
        if not ratings:
            return False, "no ratings yet"
        avg = sum(ratings) / len(ratings)
        return True, f"average rating {avg:.1f}/5 over {len(ratings)} jobs"

    return {
        "category_match": category_match,
        "dna_familiarity": dna_familiarity,
        "proximity": proximity,
        "availability": availability,
        "rating": rating,
    }


def explain_dispatch(store: Store, gig_id: str, limit: int = 5) -> list[dict[str, Any]]:
    """Transparent matching: every candidate scored from open rules only.

    Returns ranked candidates; each carries its full rule breakdown and
    plain-language explanations. Raises if a rule outside the policy
    list would be applied — no hidden rules, ever.
    """
    policies = policies_mod.load_policies(store)
    configured = [r["id"] for r in policies.get("dispatch_rules", [])]
    weights = {r["id"]: float(r["weight"]) for r in policies.get("dispatch_rules", [])}
    fns = _rule_fns()
    unknown = [rid for rid in configured if rid not in fns]
    if unknown:
        raise ValueError(
            f"dispatch rules not implemented (refusing hidden logic): {unknown}"
        )

    gig = latest_gig(store, gig_id)
    if gig is None:
        raise KeyError(f"no gig {gig_id}")
    ctx = {"gigs": store.read_all("gigs")}

    # latest snapshot per worker
    workers: dict[str, dict] = {}
    for w in store.read_all("workers"):
        workers[w["id"]] = w
    ranked: list[dict[str, Any]] = []
    for worker in workers.values():
        if worker.get("status") != "active":
            continue
        total = 0.0
        breakdown = []
        for rid in configured:
            matched, explanation = fns[rid](gig, worker, ctx)
            points = weights[rid] if matched else 0.0
            total += points
            breakdown.append(
                {
                    "rule": rid,
                    "weight": weights[rid],
                    "matched": matched,
                    "points": points,
                    "explanation": explanation,
                }
            )
        ranked.append(
            {
                "worker_id": worker["id"],
                "worker_name": worker["name"],
                "worker_contact": worker["contact"],  # direct — never hidden
                "score": round(total, 1),
                "max_score": round(sum(weights.values()), 1),
                "breakdown": breakdown,
            }
        )
    ranked.sort(key=lambda c: c["score"], reverse=True)
    return ranked[:limit]


def _log_decision(store: Store, decision: dict, now: str | None) -> dict:
    return store.append("decisions", decision, now=now)


def offer(
    store: Store,
    gig_id: str,
    worker_id: str,
    operator: str,
    confirm: bool = False,
    override_gate: bool = False,
    now: str | None = None,
) -> dict[str, Any]:
    """Offer a gig to a worker — full safety pipeline.

    Plan → Preview → Permission → Execute → Verify → Receipt.
    The decision (candidate, score, rule breakdown) is logged to the
    decisions stream: the match is explainable after the fact, forever.
    """
    policies = policies_mod.load_policies(store)
    gig = latest_gig(store, gig_id)
    if gig is None:
        raise KeyError(f"no gig {gig_id}")
    if gig["status"] != "open":
        raise ValueError(f"offer requires an 'open' gig, got {gig['status']!r}")

    # Plan: rank candidates transparently.
    candidates = explain_dispatch(store, gig_id, limit=5)
    chosen = next((c for c in candidates if c["worker_id"] == worker_id), None)
    if chosen is None:
        raise ValueError(f"worker {worker_id} is not an eligible candidate")
    plan = {
        "gig_id": gig_id,
        "worker_id": worker_id,
        "candidate": chosen,
        "rank": next(
            i for i, c in enumerate(candidates, 1) if c["worker_id"] == worker_id
        ),
        "of": len(candidates),
    }
    # Preview: human-readable.
    lines = [f"OFFER PREVIEW — gig '{gig['title']}' → {chosen['worker_name']}"]
    lines.append(
        f"  rank #{plan['rank']} of {plan['of']}, score {chosen['score']}/{chosen['max_score']}"
    )
    for b in chosen["breakdown"]:
        mark = "+" if b["matched"] else "·"
        lines.append(
            f"  {mark} {b['rule']} ({b['points']}/{b['weight']}): {b['explanation']}"
        )
    preview = "\n".join(lines)

    # Gate check (spec §10): dispatch needs soft_launch or active_dispatch.
    gate = check_gate(
        store, "dispatch", override=override_gate, operator=operator, now=now
    )

    # Permission: explicit confirm.
    if not confirm:
        raise PermissionError("offer requires confirm=True (Permission step)")
    if not gate["allowed"]:
        raise PermissionError(f"gate refused dispatch: {gate['reason']}")

    # Execute.
    transition(store, gig_id, "offered", now=now)
    assign_worker(store, gig_id, worker_id, now=now)
    _log_decision(
        store,
        {
            "kind": "offer",
            "gig_id": gig_id,
            "worker_id": worker_id,
            "operator": operator,
            "score": chosen["score"],
            "max_score": chosen["max_score"],
            "rank": plan["rank"],
            "breakdown": chosen["breakdown"],
            "gate": gate["stage"],
            "gate_override": gate["override"],
        },
        now,
    )
    # Verify: the decision is in the stream and the gig moved.
    latest = latest_gig(store, gig_id)
    decision_ok = any(
        d.get("kind") == "offer"
        and d.get("gig_id") == gig_id
        and d.get("worker_id") == worker_id
        for d in store.read_all("decisions")
    )
    verified = bool(latest and latest["status"] == "offered" and decision_ok)
    # Receipt.
    return {
        "ok": verified,
        "preview": preview,
        "plan": plan,
        "gate": gate,
        "verified": verified,
    }


def accept_offer(
    store: Store, gig_id: str, worker_id: str, now: str | None = None
) -> dict:
    """Worker accepts (one action). Contact of both sides already mutual."""
    gig = latest_gig(store, gig_id)
    if gig is None:
        raise KeyError(f"no gig {gig_id}")
    if gig["status"] != "offered" or gig.get("worker_id") != worker_id:
        raise ValueError(f"no open offer for worker {worker_id} on gig {gig_id}")
    return transition(store, gig_id, "accepted", now=now)


def decline_offer(
    store: Store, gig_id: str, worker_id: str, now: str | None = None
) -> dict:
    gig = latest_gig(store, gig_id)
    if gig is None:
        raise KeyError(f"no gig {gig_id}")
    if gig["status"] != "offered" or gig.get("worker_id") != worker_id:
        raise ValueError(f"no open offer for worker {worker_id} on gig {gig_id}")
    record = dict(gig)
    record.pop("seq", None)
    record.pop("ts", None)
    record.pop("worker_id", None)
    record["status"] = "open"
    return store.append("gigs", record, now=now)


# -- portable reputation passport --------------------------------------
def _worker_stats(store: Store, worker_id: str) -> dict[str, Any]:
    gigs = [
        g
        for g in store.read_all("gigs")
        if g.get("worker_id") == worker_id and g.get("status") in ("done", "paid")
    ]
    ratings = [g["rating"] for g in gigs if g.get("rating")]
    families = sorted({g.get("dna_family") for g in gigs if g.get("dna_family")})
    categories = sorted({g.get("category") for g in gigs if g.get("category")})
    sign_offs = sum(
        1
        for e in store.read_all("ledger")
        if e.get("kind") == "sign_off"
        and any(
            g.get("id") == e.get("gig_id") and g.get("worker_id") == worker_id
            for g in gigs
        )
    )
    return {
        "jobs_completed": len(gigs),
        "jobs_paid": sum(1 for g in gigs if g.get("status") == "paid"),
        "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "ratings_count": len(ratings),
        "customer_sign_offs": sign_offs,
        "dna_families": families,
        "categories_worked": categories,
    }


def export_passport(
    store: Store, worker_id: str, dest: str | Path | None = None
) -> dict[str, Any]:
    """Site Lift law 1: the worker owns their reputation.

    Assembles the portable passport from the Credential Graph + the
    Proof-of-Work Ledger, signs it with a content hash, and writes it to
    ``dest`` (default: ``<store>/passports/<worker_id>.json``). One
    command; leaving costs nothing.
    """
    policies = policies_mod.load_policies(store)
    worker = latest_worker(store, worker_id)
    if worker is None:
        raise KeyError(f"no worker {worker_id}")
    body = {
        "format": "neighboros-worker-passport",
        "format_version": int(policies.get("passport_format_version", 1)),
        "worker": {
            "id": worker["id"],
            "name": worker["name"],
            "contact": worker["contact"],  # the worker's own data — theirs to carry
            "categories": worker.get("categories", []),
            "home_cell": worker.get("home_cell"),
        },
        "credentials": worker.get("credentials", []),  # claims with provenance
        "proof_of_work": _worker_stats(store, worker_id),
        "issued_by": "NeighborOS Site Lift (local operator)",
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    passport = {
        **body,
        "content_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    dest_path = Path(dest) if dest else store.base / "passports" / f"{worker_id}.json"
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(
        json.dumps(passport, indent=2, sort_keys=True), encoding="utf-8"
    )
    return {"path": str(dest_path), "passport": passport}


def import_passport(path: str | Path) -> dict[str, Any]:
    """Verify a passport's content hash and return it. Tampering fails."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    claimed = data.get("content_hash")
    body = {k: v for k, v in data.items() if k != "content_hash"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    actual = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if claimed != actual:
        raise ValueError("passport content hash mismatch — tampered or corrupt")
    if data.get("format") != "neighboros-worker-passport":
        raise ValueError("not a NeighborOS worker passport")
    return data


# -- gates --------------------------------------------------------------
def _dispatched_volume(store: Store) -> int:
    """Jobs currently in the dispatch flow (past 'open'), latest status wins."""
    seen: dict[str, str] = {}
    for g in store.read_all("gigs"):
        seen[g["id"]] = g.get("status", "")
    return sum(1 for status in seen.values() if status != "open")


# -- gates --------------------------------------------------------------
def gates_status(store: Store) -> dict[str, Any]:
    policies = policies_mod.load_policies(store)
    gates = policies.get("gates", {})
    return {
        "stage": gates.get("stage", "waitlist_only"),
        "stages": gates.get("stages", []),
        "soft_launch": gates.get("soft_launch", {}),
    }


def check_gate(
    store: Store,
    action: str,
    override: bool = False,
    operator: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    """Compliance-gated expansion (spec §10). Dispatch refuses outside
    Active Dispatch (or Soft Launch caps) without a logged override."""
    status = gates_status(store)
    stage = status["stage"]
    reason = ""
    allowed = True
    if action == "dispatch":
        if stage == "active_dispatch":
            allowed = True
        elif stage == "soft_launch":
            cap = int(status["soft_launch"].get("job_cap", 25))
            in_flight = _dispatched_volume(store)
            allowed = in_flight < cap
            reason = (
                ""
                if allowed
                else f"soft-launch cap reached ({cap} jobs in dispatch flow)"
            )
        else:
            allowed = False
            reason = f"stage '{stage}' does not permit dispatch"
    if not allowed and override and operator:
        allowed = True
        _log_decision(
            store,
            {
                "kind": "gate_override",
                "action": action,
                "stage": stage,
                "operator": operator,
                "reason": reason,
            },
            now,
        )
        reason = f"override by {operator} (logged): {reason}"
    return {
        "allowed": allowed,
        "stage": stage,
        "reason": reason,
        "override": bool(override and operator),
    }


# -- platform integrity ---------------------------------------------------
def platform_integrity_report(store: Store) -> dict[str, Any]:
    """The un-hedged invariants, checked against live state."""
    policies = policies_mod.load_policies(store)
    floor = policies_mod.worker_keep_floor(policies)
    report: dict[str, Any] = {"ok": True, "checks": {}}

    # 1. every settlement keeps the worker at/above the floor
    settlements = store.read_all("settlements")
    low = [s["id"] for s in settlements if s.get("keep_rate", 1) < floor - 1e-9]
    report["checks"]["keep_floor"] = {
        "ok": not low,
        "violations": low,
        "settlements": len(settlements),
    }

    # 2. no contact-hiding fields anywhere
    hiding: list[str] = []
    for stream in ("gigs", "workers"):
        for rec in store.read_all(stream):
            try:
                assert_no_contact_hiding(rec)
            except ValueError as exc:
                hiding.append(f"{stream}:{rec.get('id')}: {exc}")
    report["checks"]["no_contact_hiding"] = {"ok": not hiding, "violations": hiding}

    # 3. every offered gig has a logged, explainable decision
    offered = {
        g["id"]
        for g in store.read_all("gigs")
        if g.get("status") in ("offered", "accepted", "in_progress", "done", "paid")
    }
    decided = {
        d.get("gig_id") for d in store.read_all("decisions") if d.get("kind") == "offer"
    }
    missing = sorted(offered - decided)
    report["checks"]["dispatch_explainable"] = {
        "ok": not missing,
        "missing_decisions": missing,
    }

    # 4. streams are append-only (nothing deleted from the ledger)
    integrity = store.verify_integrity()
    report["checks"]["ledger_append_only"] = {
        "ok": integrity["ok"],
        "streams": integrity["streams"],
    }

    report["ok"] = all(c["ok"] for c in report["checks"].values())
    return report
