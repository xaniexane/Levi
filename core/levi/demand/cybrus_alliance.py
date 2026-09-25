"""DemandPulse <-> Cybrus alliance — DemandPulse's side of the wire.

Chauncey paired them (2026-09-22): DemandPulse's scans feed Cybrus's front
guard (threat/scam signals become screening intel); Cybrus guards
DemandPulse's store, watcher channels, and alert path. This is an alliance,
not a chain of command — DemandPulse keeps its general's standing orders.

Alliance rules, DemandPulse side:
  A1 THREATS ARE NOT DEMAND. A scam/phishing/threat match never becomes a
     DemandPulse signal and never touches scoring. It is routed to
     Cybrus's tamper-evident audit log as screening intel, labeled
     HYPOTHESIS by construction.
  A2 MINIMAL PII, same discipline as the watcher: one sentence, truncated
     to 280 chars. Full bodies are never forwarded.
  A3 NEVER INVENTS: silence when nothing matches. No match, no intel.
  A4 NEVER ACTS: DemandPulse reports intel; blocking, screening, and
     enforcement decisions are Cybrus's. This module never calls gateway,
     enforce, money, or any other Cybrus enforcement path — there is a
     test that fails the build if it does.
  A5 THE GUARD IS THE SWARM'S WIRE. Cybrus-side guarding of DemandPulse's
     store, watcher channels, and alert path is built by the Cybrus
     swarm, not here. This module only exposes the seams
     (``guard_seams`` / ``integrity``) so the guard has a stable,
     documented surface to hook — never built twice.

The Cybrus import is lazy (function-level) so ``levi.demand`` never
hard-depends on ``levi.cybrus`` at import time. When Cybrus is
unavailable the intel feed degrades to an honest ``cybrus_unavailable``
receipt — never a crash, never a silent drop claimed as delivered.

stdlib-only apart from the lazy Cybrus audit import.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Keep in step with the watcher's NEED_TEXT_MAX: one sentence, bounded.
INTEL_TEXT_MAX = 280

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")

# Conservative scam / phishing / threat markers. Deliberately narrow:
# a sentence must contain one of these to become intel. False negatives
# are cheaper than crying wolf to the front guard on every marketing
# email that says "urgent".
_THREAT_MARKERS = (
    "verify your account",
    "account suspended",
    "account locked",
    "account compromised",
    "urgent action required",
    "immediate action required",
    "wire transfer",
    "gift card",
    "pay with crypto",
    "send bitcoin",
    "you've won",
    "you have won",
    "claim your prize",
    "lottery winner",
    "phishing",
    "malware",
    "ransomware",
    "data breach",
    "password expired",
    "password will expire",
    "confirm your identity",
    "login immediately",
    "click here to verify",
    "unusual sign-in",
    "suspicious activity",
)


def threat_markers() -> Tuple[str, ...]:
    """The marker set (importable so tests and the swarm can pin it)."""
    return _THREAT_MARKERS


def extract_threats(
    text: str, markers: Optional[Tuple[str, ...]] = None
) -> List[Tuple[str, List[str]]]:
    """Pull candidate threat/scam sentences out of free text.

    Returns ``[(sentence, [matched markers]), ...]`` — the sentence only,
    truncated to INTEL_TEXT_MAX, never the full body. Empty list when
    nothing matches: silence, not invention. Explicitly not semantic
    understanding, same honesty contract as the watcher's need
    extraction.
    """
    marks = _THREAT_MARKERS if markers is None else markers
    if not text:
        return []
    found: List[Tuple[str, List[str]]] = []
    for sent in _SENT_SPLIT.split(text):
        s = " ".join(sent.split())
        if len(s) < 12:
            continue
        low = s.lower()
        hit = [m for m in marks if m in low]
        if not hit:
            continue
        if low.startswith((">", "on ", "from:", "sent:", "subject:")):
            continue
        found.append((s[:INTEL_TEXT_MAX], hit))
        if len(found) >= 3:
            break
    return found


def _audit_engine():
    """Lazy Cybrus audit engine. Raises RuntimeError when unavailable."""
    try:
        from levi.cybrus.audit import AuditEngine
    except Exception as exc:
        raise RuntimeError(f"cybrus audit unavailable: {exc}") from exc
    return AuditEngine()


def share_intel(
    items: List[Dict[str, Any]],
    audit: Optional[Any] = None,
) -> Dict[str, Any]:
    """Route threat-matching items to Cybrus's front guard as intel.

    ``items``: [{id, text, channel, source?}]. Each threat sentence is
    appended to the Cybrus audit log as event ``demandpulse.threat_intel``
    with actor ``demandpulse`` and kind ``HYPOTHESIS``. Threats never
    enter the DemandPulse signal store (A1).

    ``audit`` is an injectable engine (tests pass a fake); when None the
    real Cybrus AuditEngine is constructed lazily. A missing Cybrus
    yields ``status: "cybrus_unavailable"`` — honest, never a crash.
    """
    receipt: Dict[str, Any] = {
        "items": len(items),
        "threats_found": 0,
        "shared": 0,
        "status": "ok",
    }
    engine = audit
    if engine is None:
        try:
            engine = _audit_engine()
        except RuntimeError as exc:
            receipt["status"] = "cybrus_unavailable"
            receipt["detail"] = str(exc)[:200]
            return receipt
    for item in items:
        text = str(item.get("text") or "")
        channel = str(item.get("channel") or "unknown")
        for sentence, hit in extract_threats(text):
            receipt["threats_found"] += 1
            try:
                engine.append(
                    "demandpulse.threat_intel",
                    "demandpulse",
                    {
                        "kind": "HYPOTHESIS",
                        "channel": channel,
                        "source": str(item.get("source") or item.get("id") or ""),
                        "text": sentence,
                        "markers": hit,
                    },
                )
            except Exception as exc:
                receipt["status"] = "share_failed"
                receipt["detail"] = str(exc)[:200]
                return receipt
            receipt["shared"] += 1
    return receipt


# ---------------------------------------------------------------------------
# Guard seams — what the Cybrus swarm hooks its guard into (A5).
#
# These are DemandPulse-owned surfaces the swarm's guard wire reads and
# verifies. The guard itself (screening, blocking, alerting) lives on the
# Cybrus side and is NOT built here.


def guard_seams() -> List[Dict[str, str]]:
    """Guardable DemandPulse surfaces, for the Cybrus swarm's guard wire."""
    from levi.demand import pulse as _pulse
    from levi.demand import watcher as _watcher

    return [
        {
            "name": "signal_store",
            "path": str(_pulse.DEFAULT),
            "kind": "json-store",
            "note": "DemandPulse signals / opportunities / score cards",
        },
        {
            "name": "watcher_state",
            "path": str(_watcher.state_path()),
            "kind": "watermarks",
            "note": "per-channel watermarks: ids + timestamps only, never bodies",
        },
        {
            "name": "intel_feed",
            "path": "levi.demand.cybrus_alliance.share_intel",
            "kind": "function-seam",
            "note": "threat intel path DemandPulse -> Cybrus audit log",
        },
        {
            "name": "alert_path",
            "path": "levi.demand.alerts",
            "kind": "subsystem",
            "note": "alert creation/evaluation/cadence — guard wire owned "
                    "by the Cybrus swarm; DemandPulse watcher never touches it",
        },
    ]


def integrity() -> Dict[str, Dict[str, Any]]:
    """Check each file-backed seam: exists, parses, has expected shape.

    Returns {seam_name: {ok, detail}}. A missing file is reported, not
    raised — the guard decides what a missing seam means.
    """
    out: Dict[str, Dict[str, Any]] = {}
    for seam in guard_seams():
        if seam["kind"] not in ("json-store", "watermarks"):
            out[seam["name"]] = {"ok": True, "detail": "non-file seam"}
            continue
        path = seam["path"]
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            out[seam["name"]] = {"ok": False, "detail": "missing"}
            continue
        except (json.JSONDecodeError, OSError) as exc:
            out[seam["name"]] = {"ok": False, "detail": f"unreadable: {exc}"[:200]}
            continue
        if not isinstance(data, dict):
            out[seam["name"]] = {"ok": False, "detail": "top level not an object"}
            continue
        if seam["name"] == "signal_store" and not any(
            k in data for k in ("signals", "opportunities", "score_cards")
        ):
            out[seam["name"]] = {"ok": False, "detail": "missing store keys"}
            continue
        if seam["name"] == "watcher_state" and "channels" not in data:
            out[seam["name"]] = {"ok": False, "detail": "missing channels key"}
            continue
        out[seam["name"]] = {"ok": True, "detail": "ok"}
    return out


def alliance_status() -> Dict[str, Any]:
    """One-glance alliance health: seams + Cybrus reachability. Read-only."""
    try:
        _audit_engine()
        cybrus = "reachable"
    except RuntimeError:
        cybrus = "unreachable"
    return {
        "at": datetime.now(timezone.utc).isoformat(),
        "cybrus_audit": cybrus,
        "seams": integrity(),
    }


# ---------------------------------------------------------------------------
# Store mutations under Cybrus audit (alliance wire 1, DemandPulse side).
#
# DemandPulse records its own mutations — signal/opportunity/card writes
# and watcher tick summaries — into Cybrus's tamper-evident audit log.
# This is audit, not grants: grant *enforcement* (requiring Cybrus
# authorization before an action) is the Cybrus swarm's wire on the
# Cybrus side and is NOT built here.


def audit_mutation(event: str, details: Optional[Dict[str, Any]] = None) -> bool:
    """Append one DemandPulse mutation record to the Cybrus audit log.

    Returns True when recorded, False when Cybrus is unavailable or the
    append failed — honest, never a crash, never a silent drop claimed
    as delivered. Callers must not change behavior on False; the audit
    trail is best-effort from this side.
    """
    try:
        engine = _audit_engine()
    except RuntimeError:
        return False
    try:
        engine.append(event, "demandpulse", dict(details or {}))
    except Exception:
        return False
    return True
