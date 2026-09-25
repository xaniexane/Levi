"""hallmark — struck provenance for LEVI artifacts.

From arch-craft-makers-marks-hallmarks (hunt wave-014): since 1260/1300,
goldsmiths struck a tripartite trust chain into the metal — maker's mark
(who made it) + assay-office mark (independent tester) + fineness + date
letter (which assay, when, on whose watch). The radical move: the tester
was also accountable. A fraudulent piece traced back to the assayer's
year. Maker claims and verification were structurally separated.

LEVI's clean-room remix (not a replica): a hallmark sidecar struck onto
any artifact (bytes): maker, verifier, SHA-256, date letter, quality.
Rules:
  - the verifier must differ from the maker (self-verification refused);
  - verification recomputes the hash — detection, not crypto trust theater;
  - consequential flows call require_hallmarked(), which is deny-closed:
    unhallmarked or tampered payloads are refused, never warned past.

Date letters: assay offices cycled letters yearly. LEVI uses its own
20-letter cycle (A..U, no J to avoid confusion) over the Gregorian year —
documented as LEVI-native, not any historical office's cycle.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

SIDECAR_SUFFIX = ".hallmark.json"
_DATE_LETTERS = "ABCDEFGHIKLMNOPQRSTU"  # 20 letters, no J

QUALITY_MARKS = frozenset({"standard", "fine", "select", "ungraded"})


class UnhallmarkedError(ValueError):
    """Raised deny-closed when a payload lacks a valid hallmark."""


def date_letter(year: Optional[int] = None) -> str:
    """LEVI date letter for a year: 20-letter cycle over the Gregorian year."""
    y = year if year is not None else datetime.now(timezone.utc).year
    return _DATE_LETTERS[y % len(_DATE_LETTERS)]


def _fingerprint(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def strike(
    payload: bytes, *, maker: str, verifier: str = "", quality: str = "standard"
) -> Dict[str, str]:
    """Strike a hallmark sidecar onto payload bytes.

    Returns the hallmark dict (also written by write_sidecar).
    Refuses: empty maker, self-verification (verifier == maker),
    unknown quality marks.
    """
    maker = (maker or "").strip()
    verifier = (verifier or "").strip()
    if not maker:
        raise ValueError("maker is required: an anonymous strike is refused")
    if verifier and verifier == maker:
        raise ValueError(
            "self-verification refused: verifier must differ from maker "
            "(maker claims and verification are structurally separated)"
        )
    if quality not in QUALITY_MARKS:
        raise ValueError(
            "unknown quality mark %r; one of %s" % (quality, sorted(QUALITY_MARKS))
        )
    now = datetime.now(timezone.utc)
    return {
        "hallmark": "levi-1",
        "maker": maker,
        "verifier": verifier or "unassayed",
        "sha256": _fingerprint(payload),
        "date_struck": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date_letter": date_letter(now.year),
        "quality": quality,
    }


def verify(hallmark: Dict[str, str], payload: bytes) -> Tuple[bool, str]:
    """Verify a hallmark against payload bytes. Returns (ok, reason)."""
    if not isinstance(hallmark, dict) or hallmark.get("hallmark") != "levi-1":
        return False, "not a LEVI hallmark"
    for field in ("maker", "sha256", "date_struck", "date_letter"):
        if not hallmark.get(field):
            return False, "hallmark missing field %r" % field
    if hallmark["sha256"] != _fingerprint(payload):
        return False, "hash mismatch: payload altered after striking"
    if hallmark.get("verifier", "") == hallmark.get("maker", "") and hallmark.get(
        "verifier"
    ):
        return False, "self-verified strike: verifier equals maker"
    return True, "struck %s by %s (assayed: %s)" % (
        hallmark["date_struck"],
        hallmark["maker"],
        hallmark["verifier"],
    )


def write_sidecar(path: str, hallmark: Dict[str, str]) -> str:
    """Write the hallmark sidecar next to the artifact. Returns sidecar path."""
    sidecar = path + SIDECAR_SUFFIX
    with open(sidecar, "w", encoding="utf-8") as fh:
        json.dump(hallmark, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return sidecar


def read_sidecar(path: str) -> Optional[Dict[str, str]]:
    """Read the sidecar for path, or None if the artifact was never struck."""
    sidecar = path + SIDECAR_SUFFIX
    if not os.path.isfile(sidecar):
        return None
    with open(sidecar, encoding="utf-8") as fh:
        return json.load(fh)


def require_hallmarked(path: str, payload: Optional[bytes] = None) -> Dict[str, str]:
    """Deny-closed gate: return the verified hallmark or raise UnhallmarkedError.

    Consequential flows call this before acting on a record. No warnings,
    no fallbacks — unhallmarked or tampered payloads are refused.
    """
    hallmark = read_sidecar(path)
    if hallmark is None:
        raise UnhallmarkedError("refused: %s carries no hallmark" % path)
    if payload is None:
        with open(path, "rb") as fh:
            payload = fh.read()
    ok, reason = verify(hallmark, payload)
    if not ok:
        raise UnhallmarkedError("refused: %s — %s" % (path, reason))
    return hallmark


def strike_file(
    path: str, *, maker: str, verifier: str = "", quality: str = "standard"
) -> Dict[str, str]:
    """Strike a hallmark onto a file's current bytes; writes the sidecar."""
    with open(path, "rb") as fh:
        payload = fh.read()
    mark = strike(payload, maker=maker, verifier=verifier, quality=quality)
    write_sidecar(path, mark)
    return mark
