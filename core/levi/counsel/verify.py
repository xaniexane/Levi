"""Intake verification (the VERIFIER half of the paired mind).

The proposer (``levi.counsel.intake``) produces a candidate; this module
decides its fate under the ternary: ACCEPT / QUARANTINE / REJECT.

* ACCEPT — stored AND indexed. The document has an honest text extraction.
* QUARANTINE — stored but NOT indexed. Held for owner/attorney review:
  encrypted PDFs, text-less documents with no local OCR, OCR output that
  needs eyeballing. Quarantine is the skipped third state between accept
  and reject: nothing is lost, nothing is searchable, nothing is decided
  unilaterally.
* REJECT — not stored, not indexed. Unsupported types, missing files,
  hash drift between proposal and verification (tamper signal), or paths
  that escape the owner's control (symlinks, unreadable files).

Verification re-fingerprints the source at decision time and compares it to
the proposal's fingerprint: a mismatch means the file changed mid-intake,
and the proposal is rejected rather than stored on a stale hash.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from levi.counsel.gates import (
    VERDICT_ACCEPT,
    VERDICT_QUARANTINE,
    VERDICT_REJECT,
)
from levi.counsel.intake import IntakeProposal, sha256_file


@dataclass
class Verification:
    verdict: str
    reason: str
    doc_id: str
    quarantine_causes: List[str] = field(default_factory=list)


def _safe_source(path: Path) -> Optional[str]:
    """Reject paths the vault should never trust. Returns a reason string
    or None when the path is acceptable."""
    if path.is_symlink():
        return "source is a symlink — intake follows no links"
    if not path.exists():
        return "source no longer exists"
    if not path.is_file():
        return "source is not a regular file"
    return None


def verify_proposal(proposal: IntakeProposal) -> Verification:
    """Decide the fate of an intake proposal. Pure decision logic: the only
    I/O is re-reading the source to confirm its fingerprint."""
    doc_id = proposal.doc_id
    extraction = proposal.extraction
    path = Path(proposal.source_path)

    unsafe = _safe_source(path)
    if unsafe is not None:
        return Verification(verdict=VERDICT_REJECT, reason=unsafe, doc_id=doc_id)

    try:
        current_hash = sha256_file(path)
    except OSError as exc:
        return Verification(
            verdict=VERDICT_REJECT,
            reason=f"source unreadable at verification: {exc}",
            doc_id=doc_id,
        )
    if current_hash != proposal.doc_id:
        return Verification(
            verdict=VERDICT_REJECT,
            reason="source changed between proposal and verification "
            "(hash drift) — proposal is stale, nothing stored",
            doc_id=doc_id,
        )

    quality = extraction.quality
    if quality == "ocr-unavailable":
        return Verification(
            verdict=VERDICT_QUARANTINE,
            reason="no text layer and no local OCR tool present: stored "
            "for review, not indexed — cloud OCR is never used",
            doc_id=doc_id,
            quarantine_causes=["no-text-no-ocr"],
        )
    if not extraction.text.strip():
        return Verification(
            verdict=VERDICT_QUARANTINE,
            reason="extraction produced no text: stored for review, not indexed",
            doc_id=doc_id,
            quarantine_causes=["empty-extraction"],
        )
    if quality == "ocr-local":
        return Verification(
            verdict=VERDICT_QUARANTINE,
            reason="local OCR output is error-prone: stored and held for "
            "eyeball review before it becomes searchable",
            doc_id=doc_id,
            quarantine_causes=["ocr-needs-review"],
        )
    if quality == "text-fallback":
        return Verification(
            verdict=VERDICT_ACCEPT,
            reason="accepted with encoding fallback warning recorded",
            doc_id=doc_id,
        )
    return Verification(
        verdict=VERDICT_ACCEPT,
        reason="clean extraction: stored and indexed",
        doc_id=doc_id,
    )
