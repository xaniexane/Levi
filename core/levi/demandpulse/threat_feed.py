"""DemandPulse threat-intel publisher — the DemandPulse side of the feed.

When DemandPulse's scans surface threat/scam signals, this module
publishes them as provenance-carrying intel envelopes to Cybrus's
ingestion interface (``levi.cybrus.intel`` — owned by the same FRONT
formation, a different file; this module never edits it).

The pairing CONTRACT (markers, alliance rules A1–A5) belongs to the
teammate-owned ``levi.demand.cybrus_alliance`` module — this file never
duplicates or edits it; it only calls it. The ingestion RULES (what
Cybrus accepts) belong to ``levi.cybrus.intel``.

LAWS (binding — declared first, enforced below, machine-checked by
tests/test_front_feed.py — honestly named invariant checks):
  P1  Never invent. Indicators come ONLY from
      ``cybrus_alliance.extract_threats`` on real scan text. No match,
      no intel — silence, never fabrication.
  P2  Provenance always. Every envelope carries source, published_ts,
      and confidence. The publisher never emits an unprovenanced
      envelope (Cybrus's I1 would refuse it anyway — belt and
      suspenders).
  P3  Never acts. Publishing hands intel to Cybrus; blocking,
      screening, and enforcement decisions are Cybrus's. This module
      never calls gateway, enforce, money, broker, front, or vault —
      there is a test that fails the build if it does.
  P4  Honest delivery. When Cybrus ingestion is unavailable, the call
      returns a ``cybrus_unavailable`` receipt — never a crash, never
      a silent drop claimed as delivered.
  P5  Minimal text, same discipline as the watcher: one sentence,
      truncated to 280 chars. Full bodies are never forwarded.
  P6  No new egress. Stdlib only, zero network.

Stdlib-only. Lazy imports so ``levi.demandpulse`` never hard-depends
on ``levi.demand`` or ``levi.cybrus`` at import time.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

#: Feed source identity stamped on every envelope.
FEED_SOURCE = "demandpulse:threat-feed"


def _alliance():
    """The teammate-owned pairing contract (lazy; never edited here)."""
    try:
        from levi.demand import cybrus_alliance
    except ImportError:
        import importlib.util
        from pathlib import Path

        spec = importlib.util.spec_from_file_location(
            "levi.demand.cybrus_alliance.standalone",
            Path(__file__).resolve().parent.parent
            / "demand"
            / "cybrus_alliance.py",
        )
        if spec is None or spec.loader is None:  # pragma: no cover
            raise ImportError("cybrus_alliance unavailable") from None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    return cybrus_alliance


def _intel():
    """Cybrus ingestion interface (lazy; the pairing target)."""
    try:
        from levi.cybrus import intel
    except ImportError:
        import importlib.util
        from pathlib import Path

        spec = importlib.util.spec_from_file_location(
            "levi.cybrus.intel.standalone",
            Path(__file__).resolve().parent.parent / "cybrus" / "intel.py",
        )
        if spec is None or spec.loader is None:  # pragma: no cover
            raise ImportError("cybrus intel unavailable") from None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    return intel


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_envelopes(
    text: str,
    *,
    confidence: float,
    channel: str = "",
    scan_ref: str = "",
) -> List[Dict[str, Any]]:
    """Build provenanced intel envelopes from scan text (P1/P2/P5).

    Extraction is delegated to the alliance contract — this function
    never matches threats on its own. Empty list when nothing matches:
    silence, not invention. Non-string text is a named ValueError —
    extraction runs on real scan text only (P1).
    """
    if text is None:
        text = ""
    if not isinstance(text, str):
        raise ValueError(
            f"build_envelopes: text must be str, got {type(text).__name__}"
        )
    # Validate confidence BEFORE extraction: bad input is rejected even
    # when the text matches nothing (no silent pass on garbage).
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("confidence must be a number in [0, 1]")
    conf = float(confidence)
    if not (0.0 <= conf <= 1.0):
        raise ValueError("confidence must be a number in [0, 1]")
    alliance = _alliance()
    hits = alliance.extract_threats(text)
    if not hits:
        return []
    published_ts = _utcnow_iso()
    envelopes: List[Dict[str, Any]] = []
    for sentence, markers in hits:
        envelopes.append(
            {
                "indicator_id": uuid.uuid4().hex,
                "kind": "threat_sentence",
                "text": sentence,  # already <= 280 chars by the contract
                "markers": list(markers),
                "source": FEED_SOURCE,
                "channel": channel,
                "scan_ref": scan_ref,
                "published_ts": published_ts,
                "confidence": conf,
            }
        )
    return envelopes


def publish(
    text: str,
    *,
    confidence: float,
    channel: str = "",
    scan_ref: str = "",
) -> Dict[str, Any]:
    """Publish threat intel from scan text. NEVER raises (P4).

    Returns a delivery receipt: how many envelopes were built, how many
    Cybrus accepted, and — when ingestion is unavailable — an honest
    ``cybrus_unavailable`` status rather than a claimed delivery.
    """
    try:
        envelopes = build_envelopes(
            text, confidence=confidence, channel=channel, scan_ref=scan_ref
        )
    except ImportError:
        return {
            "published": 0,
            "accepted": 0,
            "status": "alliance_unavailable",
            "ts": _utcnow_iso(),
        }
    except ValueError as exc:
        # P4 holds for bad input too: bad confidence/text is an honest
        # receipt, never a raised exception out of publish().
        return {
            "published": 0,
            "accepted": 0,
            "status": "invalid_input",
            "detail": str(exc),
            "ts": _utcnow_iso(),
        }
    if not envelopes:
        return {"published": 0, "accepted": 0, "status": "silent", "ts": _utcnow_iso()}
    try:
        intel = _intel()
    except ImportError:
        return {
            "published": len(envelopes),
            "accepted": 0,
            "status": "cybrus_unavailable",
            "ts": _utcnow_iso(),
        }
    accepted = 0
    receipts: List[Dict[str, Any]] = []
    for env in envelopes:
        try:
            rcpt = intel.ingest(env)
        except Exception:  # pragma: no cover - intel.ingest never raises
            rcpt = {"accepted": False, "reason": "ingest-error"}
        receipts.append(rcpt)
        if rcpt.get("accepted"):
            accepted += 1
    return {
        "published": len(envelopes),
        "accepted": accepted,
        "status": "delivered" if accepted == len(envelopes) else "partial",
        "receipts": receipts,
        "ts": _utcnow_iso(),
    }


def describe_posture() -> Dict[str, Any]:
    """Backend posture, honestly reported."""
    return {
        "module": "levi.demandpulse.threat_feed",
        "laws": ["P1", "P2", "P3", "P4", "P5", "P6"],
        "source": FEED_SOURCE,
        "extraction_contract": "levi.demand.cybrus_alliance (teammate-owned)",
        "ingestion_target": "levi.cybrus.intel",
        "proof": "tests/test_front_feed.py (invariant checks, not formal proof)",
    }
