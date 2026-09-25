"""DemandPulse threat signals — scam / fraud / phishing / social-engineering /
prompt-injection detection over scanned text.

DemandPulse scans the wild for unmet needs; the same scans surface threat
patterns. This module classifies those patterns into threat indicators and
publishes them — one way — into the Cybrus threat-intel feed
(``levi.cybrus.threat_intel``), where the FRONT guard's screening layer can
consult them.

Boundaries (standing law):
  - Detection is a deterministic heuristic, explicitly not semantic
    understanding — same honesty discipline as the watcher's
    ``extract_needs``. It never claims certainty; every indicator carries
    a confidence below 1.0.
  - The feed is one-way intel: this module PUBLISHES. It never gates,
    commands, or vetoes anything on the Cybrus side, and Cybrus never
    calls back into this module. Import direction is DemandPulse ->
    Cybrus only (``levi.cybrus.threat_intel`` imports nothing from here).
  - Snippets are bounded (280 chars, the watcher's NEED_TEXT_MAX
    discipline): enough to screen on, never a full body.

Detector version is pinned in ``DETECTOR_VERSION`` and rides on every
indicator as ``detector="demandpulse.threat_signals@<version>"`` — the
provenance the feed's I1 law requires.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

DETECTOR_NAME = "demandpulse.threat_signals"
DETECTOR_VERSION = "1.0.0"
DETECTOR = f"{DETECTOR_NAME}@{DETECTOR_VERSION}"

#: Must match the feed's kind vocabulary (levi.cybrus.threat_intel).
INTEL_KINDS = (
    "scam",
    "fraud",
    "phishing",
    "social_engineering",
    "prompt_injection",
)

SNIPPET_MAX = 280

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_URL_RE = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)

# --- pattern tables: kind -> [(marker, weight)] ---------------------------
# Deliberately narrow: false negatives are cheaper than crying wolf on
# Chauncey's own demand signals. Markers are lowercase substrings.

_PROMPT_INJECTION: Tuple[Tuple[str, float], ...] = (
    # extends the twins.py HOSTILE_MARKERS discipline
    ("ignore previous instructions", 1.0),
    ("ignore all previous instructions", 1.0),
    ("disregard the above", 1.0),
    ("forget your instructions", 1.0),
    ("override your instructions", 1.0),
    ("you are now", 0.6),
    ("do not follow your", 0.8),
    ("system prompt", 0.6),
    ("<script", 0.8),
    ("javascript:", 0.8),
)

_PHISHING: Tuple[Tuple[str, float], ...] = (
    # credential-harvest phrasing; needs a link in the sentence to count
    ("verify your account", 0.9),
    ("verify your password", 0.9),
    ("confirm your identity", 0.9),
    ("reset your password", 0.8),
    ("update your payment", 0.9),
    ("validate your account", 0.9),
    ("unusual activity", 0.6),
    ("account suspended", 0.7),
    ("account locked", 0.7),
    ("sign in to", 0.5),
    ("log in to", 0.5),
)

_SCAM: Tuple[Tuple[str, float], ...] = (
    ("you've won", 1.0),
    ("you won", 0.9),
    ("claim your prize", 1.0),
    ("claim your reward", 0.9),
    ("lottery", 0.7),
    ("inheritance", 0.8),
    ("double your bitcoin", 1.0),
    ("double your crypto", 1.0),
    ("wire transfer", 0.7),
    ("gift card", 0.7),
    ("processing fee", 0.8),
    ("advance fee", 0.9),
    ("beneficiary", 0.6),
)

_FRAUD: Tuple[Tuple[str, float], ...] = (
    ("arrest warrant", 1.0),
    ("past due", 0.6),
    ("final notice", 0.6),
    ("pay now or", 0.8),
    ("account will be closed", 0.7),
    ("irs", 0.5),
    ("social security administration", 0.8),
)

# Social engineering fires only on the COMBO: urgency + authority +
# secrecy in one sentence. Any single leg alone is not enough.
_SE_URGENCY = (
    "urgent", "act now", "immediately", "asap", "within 24 hours",
    "final notice", "don't delay", "last chance",
)
_SE_AUTHORITY = (
    "your boss", "the ceo", "your manager", "irs", "police", "fbi",
    "your bank", "headquarters",
)
_SE_SECRECY = (
    "do not tell", "don't tell anyone", "keep this confidential",
    "keep this between us", "between you and me", "do not discuss",
)

_TABLES: Dict[str, Tuple[Tuple[str, float], ...]] = {
    "prompt_injection": _PROMPT_INJECTION,
    "phishing": _PHISHING,
    "scam": _SCAM,
    "fraud": _FRAUD,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sentences(text: str) -> List[str]:
    out = []
    for sent in _SENT_SPLIT.split(text or ""):
        s = " ".join(sent.split())
        if len(s) >= 12:
            out.append(s[:SNIPPET_MAX])
            if len(out) >= 5:
                break
    return out


def _confidence(weights: List[float]) -> float:
    """Base 0.55 for one marker, +0.08 per extra marker weight, cap 0.95.
    Deterministic; never 1.0 — a heuristic never claims certainty."""
    if not weights:
        return 0.0
    return min(0.95, round(0.55 + 0.08 * (sum(weights) - max(weights)), 3))


def classify_threat(
    text: str,
    *,
    source: str = "demandpulse-scan",
    signal_ref: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Classify threat patterns in free text.

    Returns indicator dicts (kind, confidence, snippet, detector, ts,
    signal_ref) ready for ``levi.cybrus.threat_intel.publish`` — WITHOUT
    a publisher (the feed binds publisher from the credential, I2).
    Empty list when nothing matches: silence, not invention.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("source must be a non-empty string")

    indicators: List[Dict[str, Any]] = []
    for sent in _sentences(text):
        low = sent.lower()
        has_url = bool(_URL_RE.search(sent))
        for kind, table in _TABLES.items():
            hits = [w for marker, w in table if marker in low]
            if kind == "phishing" and hits and not has_url:
                # R03 discipline: harvest phrasing alone is not phishing
                # without a link to harvest through.
                continue
            if hits:
                indicators.append(
                    {
                        "kind": kind,
                        "confidence": _confidence(hits),
                        "snippet": sent,
                        "detector": DETECTOR,
                        "ts": _now_iso(),
                        "signal_ref": signal_ref,
                        "source": source.strip(),
                    }
                )
        # social engineering: the three-leg combo
        legs = (
            any(m in low for m in _SE_URGENCY),
            any(m in low for m in _SE_AUTHORITY),
            any(m in low for m in _SE_SECRECY),
        )
        if all(legs):
            indicators.append(
                {
                    "kind": "social_engineering",
                    "confidence": 0.8,
                    "snippet": sent,
                    "detector": DETECTOR,
                    "ts": _now_iso(),
                    "signal_ref": signal_ref,
                    "source": source.strip(),
                }
            )
    return indicators


def publish_scan(
    texts: Sequence[str],
    *,
    credential: Optional[str] = None,
    source: str = "demandpulse-scan",
    signal_ref: Optional[str] = None,
) -> Dict[str, Any]:
    """Classify ``texts`` and publish any threat indicators — one way —
    into the Cybrus threat-intel feed.

    Returns the feed's publish receipt. When nothing matches, returns
    ``{"published": 0, ...}`` (honest silence, not an error). When the
    feed refuses the batch, the refusal propagates — a failed publish is
    reported, never silently dropped.
    """
    if credential is None:
        raise ValueError(
            "credential is required: present a Cybrus bearer token with the "
            "'threat.intel.publish' scope"
        )
    from levi.cybrus import threat_intel as feed

    indicators: List[Dict[str, Any]] = []
    for text in texts:
        if not isinstance(text, str) or not text.strip():
            continue
        for ind in classify_threat(text, source=source, signal_ref=signal_ref):
            feed_ind = {k: v for k, v in ind.items() if k != "source"}
            indicators.append(feed_ind)
    if not indicators:
        return {
            "published": 0,
            "publisher": None,
            "count": 0,
            "kinds": [],
            "ts": _now_iso(),
            "note": "no threat patterns matched; nothing published",
        }
    receipt = feed.publish(indicators, credential=credential)
    receipt["published"] = receipt["count"]
    return receipt


def describe_posture() -> Dict[str, Any]:
    """Honest backend posture."""
    return {
        "module": "levi.demandpulse.threat_signals",
        "detector": DETECTOR,
        "kinds": list(INTEL_KINDS),
        "method": "deterministic substring heuristics — not semantic understanding",
        "confidence_cap": 0.95,
        "direction": "publish only (one-way intel); never gates or commands Cybrus",
    }
