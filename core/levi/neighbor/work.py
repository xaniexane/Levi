"""Worker side of NeighborOS — `work.py` (spec §4 system 4).

- Worker registry with Credential Graph claims.
- Claim/accept flow, availability.
- Proof-of-Work stream: check-in → progress notes/photos → check-out →
  customer sign-off. A job is not *done* until the ledger says so (§5).
- Disputes: freeze settlement, route to a human — never autonomous (§7/§8).

Credentials are *claims with provenance*, never verified-by-us: every
credential carries who asserted it and when, and ``verified_by_us`` is
False unless the operator runs an external check and records it.
"""

from __future__ import annotations

from typing import Any

from .post import latest_gig, transition
from .store import Store, utcnow


def register_worker(
    store: Store,
    name: str,
    contact: str,
    categories: list[str],
    home_cell: str,
    credentials: list[dict] | None = None,
    now: str | None = None,
) -> dict:
    """Register a worker. Contact is plain and mutual — never masked."""
    worker = {
        "id": store.next_id("worker"),
        "name": name,
        "contact": contact,  # never masked — Site Lift law
        "categories": list(categories),
        "home_cell": home_cell,
        "available": True,
        "status": "active",
        "credentials": [claim_credential(c, now=now) for c in (credentials or [])],
    }
    return store.append("workers", worker, now=now)


def claim_credential(credential: dict, now: str | None = None) -> dict:
    """Wrap a credential as a claim with provenance. Honest by default."""
    claim = dict(credential)
    claim.setdefault("asserted_by", claim.get("issuer", "worker"))
    claim.setdefault("asserted_at", now or utcnow())
    # Never verified-by-us unless the operator records an external check.
    claim.setdefault("verified_by_us", False)
    return claim


def add_credential(
    store: Store, worker_id: str, credential: dict, now: str | None = None
) -> dict:
    worker = latest_worker(store, worker_id)
    if worker is None:
        raise KeyError(f"no worker {worker_id}")
    record = dict(worker)
    record.pop("seq", None)
    record.pop("ts", None)
    record["credentials"] = [
        *record.get("credentials", []),
        claim_credential(credential, now=now),
    ]
    return store.append("workers", record, now=now)


def latest_worker(store: Store, worker_id: str) -> dict | None:
    matches = [w for w in store.read_all("workers") if w.get("id") == worker_id]
    return matches[-1] if matches else None


def set_availability(
    store: Store, worker_id: str, available: bool, now: str | None = None
) -> dict:
    worker = latest_worker(store, worker_id)
    if worker is None:
        raise KeyError(f"no worker {worker_id}")
    record = dict(worker)
    record.pop("seq", None)
    record.pop("ts", None)
    record["available"] = available
    return store.append("workers", record, now=now)


# -- proof-of-work stream ---------------------------------------------
def _proof(
    store: Store, gig_id: str, kind: str, payload: dict, now: str | None
) -> dict:
    entry = {"gig_id": gig_id, "kind": kind, **payload}
    return store.append("ledger", entry, now=now)


def check_in(store: Store, gig_id: str, worker_id: str, now: str | None = None) -> dict:
    gig = latest_gig(store, gig_id)
    if gig is None:
        raise KeyError(f"no gig {gig_id}")
    if gig["status"] != "accepted":
        raise ValueError(f"check-in requires status 'accepted', got {gig['status']!r}")
    transition(store, gig_id, "in_progress", now=now)
    return _proof(store, gig_id, "check_in", {"worker_id": worker_id}, now)


def progress_note(
    store: Store,
    gig_id: str,
    worker_id: str,
    note: str,
    photo_hashes: tuple[str, ...] = (),
    now: str | None = None,
) -> dict:
    return _proof(
        store,
        gig_id,
        "progress",
        {"worker_id": worker_id, "note": note, "photo_hashes": list(photo_hashes)},
        now,
    )


def check_out(
    store: Store, gig_id: str, worker_id: str, now: str | None = None
) -> dict:
    gig = latest_gig(store, gig_id)
    if gig is None:
        raise KeyError(f"no gig {gig_id}")
    if gig["status"] != "in_progress":
        raise ValueError(
            f"check-out requires status 'in_progress', got {gig['status']!r}"
        )
    return _proof(store, gig_id, "check_out", {"worker_id": worker_id}, now)


def sign_off(
    store: Store,
    gig_id: str,
    requester: str,
    rating: int,
    final_amount: float | None = None,
    now: str | None = None,
) -> dict:
    """Customer sign-off closes the ledger (Verify). Rating 1-5."""
    if not 1 <= rating <= 5:
        raise ValueError("rating must be 1-5")
    gig = latest_gig(store, gig_id)
    if gig is None:
        raise KeyError(f"no gig {gig_id}")
    kinds = {e["kind"] for e in store.read_all("ledger") if e.get("gig_id") == gig_id}
    if "check_out" not in kinds:
        raise ValueError("sign-off requires a check-out in the proof stream")
    entry = _proof(
        store,
        gig_id,
        "sign_off",
        {"requester": requester, "rating": rating, "final_amount": final_amount},
        now,
    )
    record = dict(gig)
    record.pop("seq", None)
    record.pop("ts", None)
    record["status"] = "done"
    record["rating"] = rating
    if final_amount is not None:
        record["final_amount"] = final_amount
    store.append("gigs", record, now=now)
    return entry


# -- disputes -----------------------------------------------------------
def dispute(
    store: Store, gig_id: str, raised_by: str, reason: str, now: str | None = None
) -> dict:
    """A dispute freezes settlement and routes to a human. Never autonomous."""
    gig = latest_gig(store, gig_id)
    if gig is None:
        raise KeyError(f"no gig {gig_id}")
    transition(store, gig_id, "disputed", now=now)
    return store.append(
        "disputes",
        {
            "id": store.next_id("dispute"),
            "gig_id": gig_id,
            "raised_by": raised_by,
            "reason": reason,
            "status": "open",
        },
        now=now,
    )


def resolve_dispute(
    store: Store,
    dispute_id: str,
    outcome: str,
    decided_by: str,
    note: str = "",
    now: str | None = None,
) -> dict:
    """Human decision only: ``release`` (→ done, payable) or ``void`` (no settlement)."""
    if outcome not in ("release", "void"):
        raise ValueError("outcome must be 'release' or 'void'")
    matches = [d for d in store.read_all("disputes") if d.get("id") == dispute_id]
    if not matches:
        raise KeyError(f"no dispute {dispute_id}")
    record = dict(matches[-1])
    record.pop("seq", None)
    record.pop("ts", None)
    record["status"] = "resolved"
    record["outcome"] = outcome
    record["decided_by"] = decided_by  # a human name — accountability
    record["note"] = note
    resolved = store.append("disputes", record, now=now)
    if outcome == "release":
        transition(store, record["gig_id"], "done", now=now)
    return resolved


def open_disputes(store: Store) -> list[dict]:
    seen: dict[str, dict] = {}
    for d in store.read_all("disputes"):
        seen[d["id"]] = d
    return [d for d in seen.values() if d.get("status") == "open"]
