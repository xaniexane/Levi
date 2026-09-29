"""NeighborOS Android bridge — gig dispatch (Uber-for-gigs).

JSON in/out wrappers over levi.neighbor, the REAL dispatch engine:
  customer post -> dispatch match -> worker claim -> proof-of-work ->
  NeighborPay settlement ledger -> receipt.

Chauncey's plan (docs/NEIGHBOROS_SPEC.md; master DNA snapshot 2026-07-27
"NeighborOS = gig dispatch"): customers post jobs, workers accept them,
dispatch matches the two. Verticals: trades (plumbing, HVAC, electrical),
tech support, general gigs.

Bloodline distribution law (Chauncey, 2026-09-27): the founder build runs
the ORIGINAL source at FULL capability. Bloodline (derived) builds are
LIMITED — no gate advancement/override, no dispute resolution, no admin
reads — and METERED: usage events are appended to a local metering log
the founder can provide/meter as a service.

Honest boundaries preserved from the engine: NeighborPay is a settlement
ledger only (real money moves on labeled external rails, never in core);
disputes freeze settlement and route to a human; credentials are claims
with provenance; contact is never masked.
"""

from __future__ import annotations

import json
import traceback
from pathlib import Path

from levi.neighbor import (
    admin as admin_mod,
)
from levi.neighbor import (
    lift as lift_mod,
)
from levi.neighbor import (
    pay as pay_mod,
)
from levi.neighbor import (
    policies as policies_mod,
)
from levi.neighbor import (
    post as post_mod,
)
from levi.neighbor import (
    waitlist as waitlist_mod,
)
from levi.neighbor import (
    work as work_mod,
)
from levi.neighbor.store import Store

_STORE: Store | None = None
_STATE_DIR: Path | None = None
_FLAVOR = "founder"  # "founder" (full) or "bloodline" (limited + metered)

FOUNDER_ONLY = (
    "gate_advance",
    "gate_override",
    "dispute_resolve",
    "metering_log",
)

METERED_KINDS = (
    "gig_publish",
    "offer_make",
    "offer_accept",
    "settle_execute",
)


# --------------------------------------------------------------------------
# laws
#
# L1  A gig is claimed by at most one worker: accept requires status
#     "offered" addressed to that worker (engine-enforced).
# L2  Settlement only on proven work: settle refuses unless the gig is
#     done with customer sign-off; disputed gigs freeze settlement.
# L3  Worker keep >= 90% on every settlement (policies floor).
# L4  Gates enforced: dispatch refuses outside an allowed stage without a
#     logged founder override (engine-enforced).
# L5  Bloodline limits: gate_advance / gate_override / dispute_resolve /
#     metering_log refuse on the bloodline flavor.
# L6  Metering: every publish / offer / accept / settle on a bloodline
#     build appends a metering event.
# L7  Nothing is deleted: the engine is append-only; this bridge exposes
#     no delete path.
# --------------------------------------------------------------------------


def _err(exc: BaseException) -> str:
    return json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def _seed_policies(store: Store) -> None:
    """Seed the workspace policies.json from the packaged operator config.

    levi.neighbor.store.ensure_policies() copies via Path(__file__) — that
    path points INSIDE Chaquopy's app.imy archive on Android, so we seed
    here with importlib.resources, which reads zip-packaged data fine.
    The workspace copy still rules afterward (operator config, not code).
    """
    dest = store.policies_path()
    if dest.exists():
        return
    data = None
    try:
        from importlib import resources
        data = resources.files("levi.neighbor").joinpath(
            "policies.json").read_bytes()
    except Exception:
        try:
            import pkgutil
            data = pkgutil.get_data("levi.neighbor", "policies.json")
        except Exception:
            data = None
    if data is None:
        raise RuntimeError("packaged levi/neighbor/policies.json not found")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def _store() -> Store:
    global _STORE
    if _STORE is None:
        if _STATE_DIR is None:
            raise RuntimeError("workspace not set")
        _STORE = Store(_STATE_DIR / "dispatch")
        _seed_policies(_STORE)
    return _STORE


def _require_founder(action: str) -> None:
    if _FLAVOR != "founder":
        raise PermissionError(
            f"{action} is founder-only — bloodline builds are limited "
            "(Chauncey's bloodline law)"
        )


def _meter(kind: str, detail: dict) -> None:
    """Append a metering event on bloodline builds (the founder meters
    the service off this log)."""
    if kind not in METERED_KINDS:
        return
    if _FLAVOR != "bloodline":
        return
    _store().append("metering", {"kind": kind, "flavor": "bloodline", **detail})


# --------------------------------------------------------------------------
# workspace + flavor
# --------------------------------------------------------------------------


def set_workspace(path: str) -> str:
    """Point state at the app's private files dir. Returns 'true'."""
    global _STATE_DIR, _STORE, _FLAVOR
    try:
        _STATE_DIR = Path(path) / "neighboros"
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        _STORE = None
        flavor_file = _STATE_DIR / "flavor.json"
        if flavor_file.exists():
            _FLAVOR = json.loads(flavor_file.read_text()).get("flavor", "founder")
        return "true"
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def set_flavor(flavor: str) -> str:
    """Pin the build flavor: 'founder' (full) or 'bloodline' (limited)."""
    global _FLAVOR
    try:
        if flavor not in ("founder", "bloodline"):
            raise ValueError("flavor must be 'founder' or 'bloodline'")
        _FLAVOR = flavor
        if _STATE_DIR is not None:
            (_STATE_DIR / "flavor.json").write_text(json.dumps({"flavor": flavor}))
        return json.dumps({"ok": True, "flavor": _FLAVOR})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def flavor() -> str:
    return json.dumps({"ok": True, "flavor": _FLAVOR,
                       "limited": _FLAVOR != "founder"})


def categories() -> str:
    """Dispatch verticals (trades, tech support, gigs) from operator config."""
    try:
        cats = policies_mod.load_policies(_store()).get("categories", [])
        return json.dumps({"ok": True, "categories": cats})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# --------------------------------------------------------------------------
# gig streams (latest snapshot per id — the engine is append-only)
# --------------------------------------------------------------------------


def _latest(records: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for r in records:
        if r.get("id"):
            seen[r["id"]] = r
    return list(seen.values())


def _gig_dict(g: dict) -> dict:
    return {
        "id": g.get("id"),
        "title": g.get("title"),
        "category": g.get("category"),
        "description": g.get("description"),
        "status": g.get("status"),
        "requester": g.get("requester"),
        "requester_contact": g.get("requester_contact"),
        "worker_id": g.get("worker_id"),
        "cell": g.get("neighborhood_cell"),
        "estimate": g.get("estimate"),
        "dna": (g.get("dna") or "")[:16],
        "dna_family": g.get("dna_family"),
    }


def _worker_dict(w: dict) -> dict:
    return {
        "id": w.get("id"),
        "name": w.get("name"),
        "contact": w.get("contact"),
        "categories": list(w.get("categories") or []),
        "cell": w.get("home_cell"),
        "available": bool(w.get("available", True)),
        "status": w.get("status"),
    }


# --------------------------------------------------------------------------
# customer: post a gig (Plan -> Preview -> Permission -> Execute)
# --------------------------------------------------------------------------


def gig_draft(title: str, category: str, description: str, requester: str,
              contact: str, cell: str, estimate: str) -> str:
    """Plan step: build an unpublished gig draft (returned as JSON)."""
    try:
        est = float(estimate) if (estimate or "").strip() else None
        draft = post_mod.draft_gig(
            title=title, category=category, description=description,
            requester=requester, requester_contact=contact,
            neighborhood_cell=cell, estimate=est)
        return json.dumps({"ok": True, "draft": draft})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def gig_preview(draft_json: str) -> str:
    """Preview step: human-readable preview before publishing."""
    try:
        raw = json.loads(draft_json)
        draft = raw["draft"] if "draft" in raw else raw
        text = post_mod.preview_gig(_store(), draft)
        return json.dumps({"ok": True, "preview": text})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def gig_publish(draft_json: str, confirm: bool) -> str:
    """Permission + Execute: publish the draft (confirm=True required)."""
    try:
        raw = json.loads(draft_json)
        draft = raw["draft"] if "draft" in raw else raw
        gig = post_mod.publish_gig(_store(), draft, confirm=bool(confirm))
        _meter("gig_publish", {"gig_id": gig.get("id"),
                               "category": gig.get("category")})
        return json.dumps({"ok": True, "gig": _gig_dict(gig)})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def gigs_list(status_filter: str = "", cell: str = "") -> str:
    try:
        gigs = _latest(_store().read_all("gigs"))
        if status_filter:
            gigs = [g for g in gigs if g.get("status") == status_filter]
        if cell:
            gigs = [g for g in gigs if g.get("neighborhood_cell") == cell]
        return json.dumps({"ok": True,
                           "gigs": [_gig_dict(g) for g in gigs]})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def gig_get(gig_id: str) -> str:
    try:
        g = post_mod.latest_gig(_store(), gig_id)
        if g is None:
            raise KeyError(f"no gig {gig_id}")
        return json.dumps({"ok": True, "gig": _gig_dict(g)})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# --------------------------------------------------------------------------
# dispatch: match -> offer -> accept
# --------------------------------------------------------------------------


def dispatch_candidates(gig_id: str, limit: int = 5) -> str:
    """Explainable dispatch: ranked workers with per-rule breakdown."""
    try:
        cands = lift_mod.explain_dispatch(_store(), gig_id, limit=int(limit))
        out = []
        for c in cands:
            out.append({
                "worker_id": c["worker_id"],
                "worker_name": c["worker_name"],
                "contact": c.get("worker_contact"),
                "score": c["score"],
                "max_score": c["max_score"],
                "breakdown": [
                    {"rule": b["rule"], "matched": b["matched"],
                     "explanation": b["explanation"]}
                    for b in c["breakdown"]
                ],
            })
        return json.dumps({"ok": True, "candidates": out})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def offer_make(gig_id: str, worker_id: str, operator: str,
               confirm: bool) -> str:
    """Offer a gig to a worker (gate-enforced; confirm=True required)."""
    try:
        receipt = lift_mod.offer(_store(), gig_id, worker_id,
                                 operator=operator, confirm=bool(confirm))
        _meter("offer_make", {"gig_id": gig_id, "worker_id": worker_id})
        return json.dumps({"ok": True,
                           "preview": receipt.get("preview"),
                           "verified": receipt.get("verified"),
                           "gate": receipt.get("gate")})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def offer_accept(gig_id: str, worker_id: str) -> str:
    """Worker claims the gig (L1: exactly one worker can claim)."""
    try:
        g = lift_mod.accept_offer(_store(), gig_id, worker_id)
        _meter("offer_accept", {"gig_id": gig_id, "worker_id": worker_id})
        return json.dumps({"ok": True, "gig": _gig_dict(g)})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# --------------------------------------------------------------------------
# worker: proof-of-work stream
# --------------------------------------------------------------------------


def proof_checkin(gig_id: str, worker_id: str) -> str:
    try:
        work_mod.check_in(_store(), gig_id, worker_id)
        return json.dumps({"ok": True})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def proof_note(gig_id: str, worker_id: str, note: str) -> str:
    try:
        work_mod.progress_note(_store(), gig_id, worker_id, note)
        return json.dumps({"ok": True})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def proof_checkout(gig_id: str, worker_id: str) -> str:
    try:
        work_mod.check_out(_store(), gig_id, worker_id)
        return json.dumps({"ok": True})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def proof_signoff(gig_id: str, requester: str, rating: str) -> str:
    """Customer sign-off closes the proof ledger (1-5 rating)."""
    try:
        work_mod.sign_off(_store(), gig_id, requester, int(rating))
        return json.dumps({"ok": True})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def proof_ledger(gig_id: str) -> str:
    try:
        entries = [e for e in _store().read_all("ledger")
                   if e.get("gig_id") == gig_id]
        return json.dumps({"ok": True, "entries": [
            {"kind": e.get("kind"), "ts": e.get("ts"),
             "worker_id": e.get("worker_id"),
             "note": e.get("note"), "rating": e.get("rating")}
            for e in entries]})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# --------------------------------------------------------------------------
# NeighborPay: settlement ledger (records who owes whom — never moves money)
# --------------------------------------------------------------------------


def settle_plan(gig_id: str, amount: str) -> str:
    """Plan step: what settlement would look like — worker keep shown."""
    try:
        plan = pay_mod.plan_settlement(_store(), gig_id, float(amount))
        return json.dumps({"ok": True, "plan": {
            "gig_id": plan["gig_id"],
            "worker_id": plan["worker_id"],
            "gross": plan["gross"],
            "fee": plan["fee"]["fee"],
            "applied_rate": plan["fee"]["applied_rate"],
            "worker_keep": plan["worker_keep"],
            "keep_rate": plan["keep_rate"],
            "floor": plan["fee"]["floor"],
        }, "preview": pay_mod.preview_settlement(plan)})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def settle_execute(gig_id: str, amount: str, rail: str, rail_ref: str,
                   confirm: bool) -> str:
    """Execute + Verify + Receipt (L2: proven work only; confirm required)."""
    try:
        entry = pay_mod.settle(_store(), gig_id, float(amount), rail,
                               rail_ref, confirm=bool(confirm))
        _meter("settle_execute",
               {"gig_id": gig_id, "settlement_id": entry.get("id"),
                "gross": entry.get("gross")})
        return json.dumps({"ok": True, "settlement": {
            "id": entry.get("id"), "gig_id": entry.get("gig_id"),
            "worker_id": entry.get("worker_id"), "gross": entry.get("gross"),
            "fee": entry.get("fee"), "worker_keep": entry.get("worker_keep"),
            "keep_rate": entry.get("keep_rate"),
            "rail": entry.get("rail"), "status": entry.get("status"),
            "verified": entry.get("verified"),
        }})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def settle_receipt(settlement_id: str) -> str:
    try:
        s = _store().find("settlements", "id", settlement_id)
        if s is None:
            raise KeyError(f"no settlement {settlement_id}")
        return json.dumps({"ok": True,
                           "receipt": pay_mod.receipt_text(_store(), s)})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# --------------------------------------------------------------------------
# workers
# --------------------------------------------------------------------------


def worker_register(name: str, contact: str, categories_csv: str,
                    cell: str) -> str:
    try:
        cats = [c.strip() for c in (categories_csv or "").split(",")
                if c.strip()]
        w = work_mod.register_worker(_store(), name, contact, cats, cell)
        return json.dumps({"ok": True, "worker": _worker_dict(w)})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def workers_list() -> str:
    try:
        ws = _latest(_store().read_all("workers"))
        return json.dumps({"ok": True,
                           "workers": [_worker_dict(w) for w in ws]})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def worker_set_available(worker_id: str, available: bool) -> str:
    try:
        w = work_mod.set_availability(_store(), worker_id, bool(available))
        return json.dumps({"ok": True, "worker": _worker_dict(w)})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# --------------------------------------------------------------------------
# disputes (raise: anyone; resolve: founder only — human decision)
# --------------------------------------------------------------------------


def dispute_raise(gig_id: str, raised_by: str, reason: str) -> str:
    try:
        d = work_mod.dispute(_store(), gig_id, raised_by, reason)
        return json.dumps({"ok": True, "dispute_id": d.get("id")})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def disputes_list() -> str:
    try:
        return json.dumps({"ok": True,
                           "disputes": admin_mod.dispute_queue(_store())})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def dispute_resolve(dispute_id: str, operator: str, outcome: str,
                    note: str) -> str:
    try:
        _require_founder("dispute_resolve")
        r = work_mod.resolve_dispute(_store(), dispute_id, outcome,
                                     operator, note=note)
        return json.dumps({"ok": True, "resolved": r.get("id")})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# --------------------------------------------------------------------------
# activation gates (Waitlist -> Recruiting -> Soft Launch -> Active Dispatch)
# --------------------------------------------------------------------------


def gate_stage() -> str:
    try:
        s = _store()
        return json.dumps({"ok": True, "stage": admin_mod.stage(s),
                           "checklist": admin_mod.stage_checklist(
                               s, _next_stage(s))})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def _next_stage(store: Store) -> str:
    stages = policies_mod.load_policies(store).get("gates", {}).get("stages", [])
    cur = admin_mod.stage(store)
    try:
        i = stages.index(cur)
    except ValueError:
        return cur
    return stages[i + 1] if i + 1 < len(stages) else cur


def gate_advance(operator: str, confirm: bool) -> str:
    """Founder only: advance to the next stage (checklist-enforced)."""
    try:
        _require_founder("gate_advance")
        r = admin_mod.advance_stage(_store(), operator, confirm=bool(confirm))
        return json.dumps({"ok": True, "stage": r.get("to")})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def gate_override(operator: str, target: str, note: str) -> str:
    """Founder only: skip a stage (logged override)."""
    try:
        _require_founder("gate_override")
        r = admin_mod.override_stage(_store(), target, operator, note,
                                     confirm=True)
        return json.dumps({"ok": True, "stage": r.get("to")})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# --------------------------------------------------------------------------
# waitlist
# --------------------------------------------------------------------------


def waitlist_add(name: str, contact: str, role: str, cell: str) -> str:
    try:
        e = waitlist_mod.add_to_waitlist(_store(), name, contact, role, cell)
        return json.dumps({"ok": True, "entry_id": e.get("id")})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def waitlist_depth(cell: str) -> str:
    try:
        return json.dumps({"ok": True,
                           "depth": waitlist_mod.waitlist_depth(_store(), cell)})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# --------------------------------------------------------------------------
# metering (founder reads the bloodline usage log)
# --------------------------------------------------------------------------


def metering_log() -> str:
    try:
        _require_founder("metering_log")
        events = _store().read_all("metering")
        return json.dumps({"ok": True, "events": events,
                           "count": len(events)})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# --------------------------------------------------------------------------
# first-launch seed (clearly labeled SAMPLE data, empty store only)
# --------------------------------------------------------------------------


def seed_workspace() -> str:
    """Seed SAMPLE dispatch data on first launch (empty store only)."""
    try:
        s = _store()
        if _latest(s.read_all("gigs")) or _latest(s.read_all("workers")):
            return json.dumps({"ok": True, "seeded": False})
        w = work_mod.register_worker(
            s, "Sample Rosa", "555-0100", ["plumbing", "hvac"],
            "springfield-test")
        draft = post_mod.draft_gig(
            title="SAMPLE — fix leaky faucet", category="plumbing",
            description="Kitchen faucet drips constantly.",
            requester="Sample Customer", requester_contact="555-0101",
            neighborhood_cell="springfield-test", estimate=120.0)
        gig = post_mod.publish_gig(s, draft, confirm=True)
        return json.dumps({"ok": True, "seeded": True,
                           "worker_id": w["id"], "gig_id": gig["id"]})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)
