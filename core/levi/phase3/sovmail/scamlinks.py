"""Deterministic scam-link analysis. No cloud reputation lookups, ever.

For each link in a message, flags are pure functions of the message:
- ``punycode``: href host contains an ``xn--`` label.
- ``display_mismatch``: the anchor text looks like a URL but points
  at a different host than the href.
- ``credential_harvest``: credential-bait phrasing in the body next
  to a link (verify/suspended/password + click/login).
- ``ip_host``: the href host is a bare IPv4 address.

``analyze_links`` returns the flag list per link and a total score;
``is_suspicious`` applies the fixed threshold.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

__all__ = ["analyze_links", "is_suspicious", "SCORE_THRESHOLD"]

SCORE_THRESHOLD = 1  # any single flag marks the message suspicious

_HREF_RE = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
_ANCHOR_RE = re.compile(r"<a\b[^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
_URL_TEXT_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)
_IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
_TAG_RE = re.compile(r"<[^>]+>")

_CRED_BAIT = (
    "verify your account",
    "account suspended",
    "password expired",
    "confirm your password",
    "unusual sign-in",
    "security alert",
    "click here to verify",
    "update your payment",
)
_CRED_ACTION = ("login", "sign in", "verify", "click", "confirm", "update")


def _host(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except ValueError:
        return ""


def _links(body: str) -> List[Tuple[str, str]]:
    """(anchor_text, href) pairs; plain-text URLs get their own text."""
    out: List[Tuple[str, str]] = []
    for match in _ANCHOR_RE.finditer(body):
        anchor_html = match.group(1)
        anchor = _TAG_RE.sub("", anchor_html).strip()
        tag = match.group(0)
        href_m = _HREF_RE.search(tag)
        if href_m:
            out.append((anchor, href_m.group(1)))
    plain = _TAG_RE.sub(" ", body)
    for url in _URL_TEXT_RE.findall(plain):
        full = url if url.lower().startswith("http") else "http://" + url
        out.append((url, full))
    return out


def _flags_for(anchor: str, href: str, body_lower: str) -> List[str]:
    flags: List[str] = []
    host = _host(href).lower()
    if "xn--" in host:
        flags.append("punycode")
    if _IP_RE.match(host):
        flags.append("ip_host")
    anchor_lower = anchor.lower()
    if _URL_TEXT_RE.search(anchor):
        anchor_host = _host(
            anchor_lower if anchor_lower.startswith("http") else "http://" + anchor
        ).lower()
        if anchor_host and anchor_host != host:
            flags.append("display_mismatch")
    if any(bait in body_lower for bait in _CRED_BAIT) and any(
        act in body_lower for act in _CRED_ACTION
    ):
        flags.append("credential_harvest")
    return flags


def analyze_links(message: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze every link; return per-link flags and a total score."""
    body = str(message.get("body", ""))
    body_lower = body.lower()
    links = _links(body)
    flagged: List[Dict[str, str]] = []
    for anchor, href in links:
        for flag in _flags_for(anchor, href, body_lower):
            flagged.append({"anchor": anchor[:80], "href": href[:160], "flag": flag})
    return {
        "link_count": len(links),
        "flags": flagged,
        "score": len(flagged),
    }


def is_suspicious(analysis: Dict[str, Any]) -> bool:
    return analysis["score"] >= SCORE_THRESHOLD
