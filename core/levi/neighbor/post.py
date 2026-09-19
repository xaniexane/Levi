"""Job intake for NeighborOS — `post.py` (spec §4 system 3, §7 steps 1-2).

Pipeline: **draft → preview → publish** (the Plan→Preview half of the
safety pipeline; Permission is the explicit publish confirmation).

Job DNA (§5): a stable fingerprint of category, scope tokens, location
cell, price band, and photo hashes. Powers matching, estimate
calibration, and fraud detection (same-DNA reposts). Pure local compute.

Contacts are plain, mutual, and never masked — the Site Lift's third
guarantee (no contact-hiding). ``requester_contact`` is stored on the gig
and shown to the worker verbatim.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from . import policies as policies_mod
from .store import Store

STATUSES = (
    "open",
    "offered",
    "accepted",
    "in_progress",
    "done",
    "paid",
    "disputed",
)

_STOPWORDS = frozenset(
    "a an the and or to of in on for with is it my our their this that fix please need".split()
)


def scope_tokens(title: str, description: str) -> list[str]:
    """Stable scope tokens from free text: lowercase words, stopwords out."""
    words = re.findall(r"[a-z]{3,}", f"{title} {description}".lower())
    return sorted({w for w in words if w not in _STOPWORDS})


def price_band(estimate: float | None) -> str:
    if estimate is None:
        return "unknown"
    if estimate < 100:
        return "micro"
    if estimate < 500:
        return "small"
    if estimate < 2000:
        return "medium"
    return "large"


def job_dna(
    category: str,
    title: str,
    description: str,
    neighborhood_cell: str,
    estimate: float | None = None,
    photo_hashes: tuple[str, ...] = (),
) -> dict[str, str]:
    """Stable fingerprint. Same inputs → same dna, always."""
    tokens = scope_tokens(title, description)
    band = price_band(estimate)
    core = "|".join(
        [
            category.strip().lower(),
            ",".join(tokens),
            neighborhood_cell.strip().lower(),
            band,
            ",".join(sorted(photo_hashes)),
        ]
    )
    digest = hashlib.sha256(core.encode("utf-8")).hexdigest()
    return {
        "dna": digest,
        "dna_family": f"{category.strip().lower()}@{neighborhood_cell.strip().lower()}/{band}",
        "scope_tokens": tokens,
        "price_band": band,
    }


def estimate_band(
    store: Store, dna_family: str, fallback: list[int] | None = None
) -> dict[str, Any]:
    """Estimate band from same-DNA-family history.

    Honestly labeled when history is thin: ``history_thin`` is True and the
    band comes from the operator's configured fallback, never presented
    as data-backed.
    """
    amounts = [
        float(g["final_amount"])
        for g in store.read_all("gigs")
        if g.get("dna_family") == dna_family
        and g.get("status") in ("done", "paid")
        and g.get("final_amount")
    ]
    if len(amounts) >= 3:
        lo, hi = min(amounts), max(amounts)
        return {
            "low": round(lo, 2),
            "high": round(hi, 2),
            "history_thin": False,
            "based_on": len(amounts),
        }
    band = fallback or [50, 400]
    return {
        "low": band[0],
        "high": band[1],
        "history_thin": True,
        "based_on": len(amounts),
    }


def draft_gig(
    title: str,
    category: str,
    description: str,
    requester: str,
    requester_contact: str,
    neighborhood_cell: str,
    estimate: float | None = None,
    photo_hashes: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Build an unpublished gig record (Plan step)."""
    return {
        "title": title,
        "category": category,
        "description": description,
        "requester": requester,
        "requester_contact": requester_contact,  # never masked — Site Lift law
        "neighborhood_cell": neighborhood_cell,
        "estimate": estimate,
        "photo_hashes": list(photo_hashes),
        "status": "draft",
        **job_dna(
            category, title, description, neighborhood_cell, estimate, photo_hashes
        ),
    }


def preview_gig(store: Store, gig: dict[str, Any]) -> str:
    """Human-readable preview (Preview step) before publishing."""
    band = estimate_band(store, gig["dna_family"])
    thin = " (thin history — operator fallback band)" if band["history_thin"] else ""
    return (
        f"GIG PREVIEW\n"
        f"  title:    {gig['title']}\n"
        f"  category: {gig['category']}  cell: {gig['neighborhood_cell']}\n"
        f"  requester: {gig['requester']} <{gig['requester_contact']}>\n"
        f"  estimate band: ${band['low']:.0f}–${band['high']:.0f}{thin}\n"
        f"  job DNA: {gig['dna'][:16]}…  family: {gig['dna_family']}\n"
        f"  tokens: {', '.join(gig['scope_tokens'][:8])}"
    )


def publish_gig(
    store: Store, gig: dict[str, Any], confirm: bool = False, now: str | None = None
) -> dict[str, Any]:
    """Publish a draft (Permission = explicit ``confirm=True``)."""
    if not confirm:
        raise PermissionError("publish_gig requires confirm=True (Permission step)")
    policies_mod.load_policies(store)  # fail fast if config is broken
    gig = dict(gig)
    gig["id"] = store.next_id("gig")
    gig["status"] = "open"
    return store.append("gigs", gig, now=now)


def transition(
    store: Store, gig_id: str, to_status: str, now: str | None = None
) -> dict:
    """Status transitions for dispatch flow; recorded by appending a new
    gig snapshot (streams are append-only — history is never rewritten)."""
    if to_status not in STATUSES:
        raise ValueError(f"unknown status {to_status!r}")
    current = latest_gig(store, gig_id)
    if current is None:
        raise KeyError(f"no gig {gig_id}")
    record = dict(current)
    record.pop("seq", None)
    record.pop("ts", None)
    record["status"] = to_status
    return store.append("gigs", record, now=now)


def latest_gig(store: Store, gig_id: str) -> dict | None:
    """The gig's current state = its latest snapshot in the stream."""
    matches = [g for g in store.read_all("gigs") if g.get("id") == gig_id]
    return matches[-1] if matches else None


def assign_worker(
    store: Store, gig_id: str, worker_id: str, now: str | None = None
) -> dict:
    """Record which worker claimed the gig (appended snapshot, never rewrite)."""
    gig = latest_gig(store, gig_id)
    if gig is None:
        raise KeyError(f"no gig {gig_id}")
    record = dict(gig)
    record.pop("seq", None)
    record.pop("ts", None)
    record["worker_id"] = worker_id
    return store.append("gigs", record, now=now)
