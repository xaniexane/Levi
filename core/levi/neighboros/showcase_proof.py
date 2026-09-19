"""Showcase-as-proof — delivered work becomes proof, with consent.

Every delivery auto-generates a showcase draft. Nothing publishes
without the client's explicit consent: ``draft`` → ``consented`` →
``published``. Publication admits the entry to the bounty showcase
(:mod:`levi.bounty.showcase`), whose structural gates still hold —
paid state, Cybrus receipt, executed movement. A consented draft
without a paid bounty stays honestly marked ``consented``
(``pending_paid_bounty``), never faked into the showcase.

Drafts live at ``<LEVI_HOME>/neighboros/showcase_drafts/``, owner-only.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.neighboros import _seal

PENDING_PAID = "pending_paid_bounty"


def _drafts_dir(home: Optional[Path] = None) -> Path:
    d = _seal.pkg_dir(home) / "showcase_drafts"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def _write_json(path: Path, record: Dict[str, Any]) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _utcnow(now: Optional[float] = None) -> str:
    ts = now if now is not None else time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def draft_showcase(offering_id: str, title: str, delivery_summary: str,
                   evidence: Optional[List[str]] = None,
                   home: Optional[Path] = None,
                   now: Optional[float] = None) -> Dict[str, Any]:
    """Auto-generate a showcase draft for a delivery. Status: draft."""
    if not offering_id or not offering_id.strip():
        raise ValueError("offering_id must be non-empty")
    if not title or not title.strip():
        raise ValueError("title must be non-empty")
    draft_id = uuid.uuid4().hex[:12]
    draft = {
        "draft_id": draft_id,
        "offering_id": offering_id,
        "title": title,
        "delivery_summary": str(delivery_summary or ""),
        "evidence": [str(e) for e in (evidence or [])],
        "status": "draft",
        "client_note": "",
        "entry_id": "",
        "publish_detail": "",
        "drafted_at": _utcnow(now),
        "consented_at": "",
        "published_at": "",
    }
    _write_json(_drafts_dir(home) / f"{draft_id}.json", draft)
    return {"draft_id": draft_id, "offering_id": offering_id, "status": "draft"}


def _load(draft_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    path = _drafts_dir(home) / f"{draft_id}.json"
    if not path.exists():
        raise KeyError(f"unknown showcase draft {draft_id!r}")
    return json.loads(path.read_text(encoding="utf-8"))


def get_draft(draft_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    return _load(draft_id, home)


def consent(draft_id: str, client_note: str = "",
            home: Optional[Path] = None,
            now: Optional[float] = None) -> Dict[str, Any]:
    """Record the client's explicit consent to publish. Draft → consented."""
    draft = _load(draft_id, home)
    if draft["status"] != "draft":
        raise ValueError(
            f"draft {draft_id!r} is {draft['status']!r} — only a draft can be consented")
    draft["status"] = "consented"
    draft["client_note"] = str(client_note or "")
    draft["consented_at"] = _utcnow(now)
    _write_json(_drafts_dir(home) / f"{draft_id}.json", draft)
    return {"draft_id": draft_id, "status": "consented"}


def publish(draft_id: str, bounty: Optional[Any] = None,
            home: Optional[Path] = None,
            now: Optional[float] = None) -> Dict[str, Any]:
    """Publish a consented draft to the bounty showcase.

    ``bounty`` is the paid :class:`levi.bounty.hunts.Bounty` the delivery
    rode on. Without one — or if the showcase's structural gates refuse
    it — the draft stays ``consented`` with an honest pending reason.
    """
    from levi.bounty import showcase as _showcase

    draft = _load(draft_id, home)
    if draft["status"] != "consented":
        raise ValueError(
            f"draft {draft_id!r} is {draft['status']!r} — client consent comes first")
    if bounty is None:
        draft["publish_detail"] = PENDING_PAID
        _write_json(_drafts_dir(home) / f"{draft_id}.json", draft)
        return {"draft_id": draft_id, "published": False,
                "status": "consented", "reason": PENDING_PAID}
    try:
        entry = _showcase.admit(bounty)
    except _showcase.ShowcaseRefused as exc:
        draft["publish_detail"] = str(exc)
        _write_json(_drafts_dir(home) / f"{draft_id}.json", draft)
        return {"draft_id": draft_id, "published": False,
                "status": "consented", "reason": str(exc)}
    draft["status"] = "published"
    draft["entry_id"] = entry.entry_id
    draft["published_at"] = _utcnow(now)
    draft["publish_detail"] = "admitted to bounty showcase"
    _write_json(_drafts_dir(home) / f"{draft_id}.json", draft)
    return {"draft_id": draft_id, "published": True, "status": "published",
            "entry_id": entry.entry_id}


def list_drafts(home: Optional[Path] = None,
                status: Optional[str] = None) -> List[Dict[str, Any]]:
    out = []
    for path in sorted(_drafts_dir(home).glob("*.json")):
        draft = json.loads(path.read_text(encoding="utf-8"))
        if status is None or draft["status"] == status:
            out.append(draft)
    return out
