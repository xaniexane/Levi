"""Adapter seams — compose the forge's recreations, never rewrite them.

The rescue pipeline walks sites on the forge **browser** surface, rebuilds
on the forge **computer** surface, and versions episode changes with the
**code forge** (git). Each adapter lazily imports its sibling module; if a
surface isn't landed yet the adapter raises ``SurfaceUnavailableError``
— honest and loud, never faked.

The NeighborOS gig-dispatch seam lives here too: a remodel is dispatched
work, so an approved plan can be drafted as a gig-shaped record and —
only if ``levi.neighbor.post`` is importable — handed to the real
NeighborOS posting pipeline. Nothing in rescue depends on neighbor
internals; the seam is one function wide.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List

from .intake import require_consent


class SurfaceUnavailableError(RuntimeError):
    """A forge surface the rescue needs isn't landed yet."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# -- browser: the walk surface ------------------------------------------------


def forge_browser(home=None):
    """Open the forge browser surface (lazy import, honest if missing)."""
    try:
        from ..forge.browser import open_browser
    except Exception as exc:
        raise SurfaceUnavailableError("browser surface not landed: %s" % exc) from exc
    return open_browser(home=home)


def walk_invitation(
    home, invitation_id: str, browser=None, max_pages: int = 8
) -> Dict[str, Any]:
    """Walk the invited site inside its scope bounds → WalkContext + receipts.

    Returns ``{"walk": {url: page-record}, "receipts": [...]}``.
    URLs outside the invited scope are refused, and the refusal is on
    the record. Consent is required before the first fetch.
    """
    inv = require_consent(home, invitation_id)
    browser = browser or forge_browser(home)
    walk: Dict[str, Dict[str, Any]] = {}
    receipts: List[Dict[str, Any]] = []
    refused: List[Dict[str, str]] = []
    queue = [inv.site_url]
    seen = set()
    while queue and len(walk) < max_pages:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        if not inv.allows(url):
            refused.append({"url": url, "reason": "outside invited scope"})
            continue
        try:
            page = browser.open(url)
        except Exception as exc:
            refused.append({"url": url, "reason": "fetch failed: %s" % exc})
            continue
        text = getattr(page, "text", "") or ""
        links = getattr(page, "links", []) or []
        walk[url] = {
            "url": url,
            "status": getattr(page, "status", 200),
            "title": getattr(page, "title", "") or "",
            "text": text,
            "links": [
                {"target": (link.get("href") if isinstance(link, dict) else link)}
                for link in links
            ],
            "forms": getattr(page, "forms", []) or [],
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "fetched_at": _now(),
        }
        receipts.append(
            {
                "url": url,
                "status": walk[url]["status"],
                "sha256": walk[url]["sha256"],
                "at": walk[url]["fetched_at"],
                "scripts_dropped": True,  # the browser surface reads served HTML
            }
        )
        for link in links:
            target = link.get("href") if isinstance(link, dict) else link
            if (
                target
                and target.startswith(("http://", "https://"))
                and target not in seen
            ):
                queue.append(target)
    receipts.append({"refused": refused})
    return {"walk": walk, "receipts": receipts}


# -- computer: the rebuild surface --------------------------------------------


def forge_computer(home=None):
    """Open the forge computer surface (lazy import, honest if missing)."""
    try:
        from ..forge.computer import open_machine
    except Exception as exc:
        raise SurfaceUnavailableError("computer surface not landed: %s" % exc) from exc
    return open_machine(home=home)


# -- code forge: versioned episode changes -------------------------------------


def version_episode(episode_dir, message: str) -> Dict[str, Any]:
    """Version the episode's before/after via the code forge (git).

    Falls back to content-addressed copies with an honest note when git
    is unavailable — never pretends to version what it didn't.
    """
    from pathlib import Path

    episode_dir = Path(episode_dir)
    try:
        from ..forge.gitx import git_available, run_git
    except Exception as exc:
        return {"versioned": False, "reason": "code forge unavailable: %s" % exc}
    if not git_available():
        return {"versioned": False, "reason": "git binary not found"}
    try:
        run_git(["init", "-q"], cwd=episode_dir)
        run_git(["add", "-A"], cwd=episode_dir)
        run_git(
            [
                "-c",
                "user.name=rescue",
                "-c",
                "user.email=rescue@levi.local",
                "commit",
                "-qm",
                message,
            ],
            cwd=episode_dir,
        )
        sha = (
            run_git(["rev-parse", "--short", "HEAD"], cwd=episode_dir)
            .stdout.decode()
            .strip()
        )
        return {"versioned": True, "commit": sha}
    except Exception as exc:
        return {"versioned": False, "reason": "git failed: %s" % exc}


# -- NeighborOS gig dispatch: the seam -----------------------------------------


def neighbor_gig_draft(home, plan) -> Dict[str, Any]:
    """Draft a NeighborOS gig-shaped record from an approved rescue plan.

    Portable: if ``levi.neighbor.post`` is importable the draft is passed
    through ``draft_gig`` for the real pipeline; otherwise it returns the
    portable record with ``dispatched=False`` and the reason on record.
    """
    scope_tokens = sorted(
        {
            tok
            for item in plan.items
            for tok in (
                item.check_id.replace("-", " ").split() + item.action.split()[:6]
            )
        }
    )
    severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    estimate = sum(severity_rank.get(i.severity, 1) for i in plan.items) * 25.0
    draft = {
        "title": "Rescue & Remodel: %s" % plan.business,
        "category": "site-rescue",
        "description": "Bar Rescue × Extreme Makeover episode for %s: %d approved "
        "rescue item(s) from audit %s."
        % (plan.business, len(plan.items), plan.audit_id),
        "requester": plan.owner or "rescue-operator",
        "scope_tokens": scope_tokens[:16],
        "estimate": estimate,
        "rescue_plan_id": plan.id,
        "rescue_items": [i.to_dict() for i in plan.items],
        "dispatched": False,
    }
    try:
        from ..neighbor import post as neighbor_post  # noqa
    except Exception as exc:
        draft["dispatch_note"] = "neighbor unavailable: %s" % exc
        return draft
    try:
        gig = neighbor_post.draft_gig(
            title=draft["title"],
            category=draft["category"],
            description=draft["description"],
            requester=draft["requester"],
            requester_contact="via-rescue",
            neighborhood_cell="rescue",
            estimate=draft["estimate"],
        )
        draft["neighbor_draft"] = gig
        draft["dispatched"] = True
        draft["dispatch_note"] = (
            "drafted via levi.neighbor.post.draft_gig — publish still needs "
            "the owner's explicit confirm through preview_gig/publish_gig"
        )
    except Exception as exc:
        draft["dispatch_note"] = "neighbor draft_gig failed: %s" % exc
    return draft


__all__ = [
    "SurfaceUnavailableError",
    "forge_browser",
    "forge_computer",
    "neighbor_gig_draft",
    "version_episode",
    "walk_invitation",
]
