"""Paired mind for demand sensing: Scout + Verifier.

The 2 among 0s and 1s, applied to the product: two faces of one pass.
Scout PROPOSES signal candidates from raw scan output (the eager face).
Verifier CHECKS each candidate against the label law and either publishes
it or quarantines it with a recorded reason (the honest face).

Nothing reaches a digest without passing the verifier. The quarantine list
is the honesty feature: items that can't prove a basis are held back, never
published, and the reason is always on the record.

Deterministic, stdlib-only, offline. Same input → same verdicts.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

# Hostile-content markers: a candidate carrying these is quarantined, never
# published. Mirrors the engine feed's hostile-marker discipline.
HOSTILE_MARKERS = (
    "<script",
    "javascript:",
    "ignore previous instructions",
    "ignore all previous instructions",
    "system prompt",
    "disregard the above",
)


def _candidate_id(text: str, source: str) -> str:
    digest = hashlib.sha256(f"{source}::{text}".encode("utf-8")).hexdigest()
    return f"cand-{digest[:12]}"


@dataclass(frozen=True)
class Candidate:
    """One scouted signal candidate. Label is always OBSERVED at proposal —
    the verifier may still quarantine it if the basis doesn't hold."""

    cid: str
    text: str
    source: str
    label: str
    basis: str

    def to_record(self) -> Dict[str, Any]:
        return {
            "cid": self.cid,
            "text": self.text,
            "source": self.source,
            "label": self.label,
            "basis": self.basis,
        }


@dataclass(frozen=True)
class TwinVerdict:
    candidate: Candidate
    published: bool
    reason: str

    def to_record(self) -> Dict[str, Any]:
        return {
            "candidate": self.candidate.to_record(),
            "published": self.published,
            "reason": self.reason,
        }


@dataclass
class TwinReport:
    ran_at: str = ""
    published: List[Candidate] = field(default_factory=list)
    quarantined: List[TwinVerdict] = field(default_factory=list)

    def to_record(self) -> Dict[str, Any]:
        return {
            "ran_at": self.ran_at,
            "published": [c.to_record() for c in self.published],
            "quarantined": [v.to_record() for v in self.quarantined],
            "counts": {
                "published": len(self.published),
                "quarantined": len(self.quarantined),
            },
        }


class Scout:
    """The eager face: normalize raw scan signals into labeled candidates.

    Accepts mappings with ``text``/``title``/``need`` and ``source`` keys;
    anything malformed is skipped (never an exception). Every candidate is
    labeled OBSERVED with a basis note naming its source.
    """

    def propose(
        self, raw_signals: Optional[Iterable[Mapping[str, Any]]]
    ) -> List[Candidate]:
        candidates: List[Candidate] = []
        seen: set = set()
        for raw in raw_signals or []:
            if not isinstance(raw, Mapping):
                continue
            text = str(raw.get("text") or raw.get("title") or raw.get("need") or "")
            text = " ".join(text.split())
            source = str(raw.get("source") or "").strip()
            if not text or not source:
                continue  # malformed: skip, the verifier never sees it
            cid = _candidate_id(text, source)
            if cid in seen:
                continue  # same item twice: keep the first, drop the echo
            seen.add(cid)
            candidates.append(
                Candidate(
                    cid=cid,
                    text=text,
                    source=source,
                    label="OBSERVED",
                    basis=f"fetched text from {source}",
                )
            )
        return candidates


class Verifier:
    """The honest face: publish what proves a basis, quarantine the rest.

    Quarantine rules (all recorded on the verdict):
      - empty text → quarantine
      - empty source → quarantine
      - hostile markers in text → quarantine
    Otherwise the candidate is published as-is.
    """

    def verify(
        self, candidates: Optional[Iterable[Candidate]]
    ) -> TwinReport:
        report = TwinReport(ran_at=datetime.now(timezone.utc).isoformat())
        for cand in candidates or []:
            verdict = self._judge(cand)
            if verdict.published:
                report.published.append(cand)
            else:
                report.quarantined.append(verdict)
        return report

    def _judge(self, cand: Candidate) -> TwinVerdict:
        if not cand.text.strip():
            return TwinVerdict(cand, False, "empty text — nothing to publish")
        if not cand.source.strip():
            return TwinVerdict(cand, False, "no source — basis unprovable")
        lowered = cand.text.lower()
        for marker in HOSTILE_MARKERS:
            if marker in lowered:
                return TwinVerdict(
                    cand, False, f"hostile marker {marker!r} — quarantined"
                )
        return TwinVerdict(cand, True, "OBSERVED with named source — basis holds")


def run_twin_pass(
    raw_signals: Optional[Iterable[Mapping[str, Any]]],
    scout: Optional[Scout] = None,
    verifier: Optional[Verifier] = None,
) -> Tuple[TwinReport, List[Candidate]]:
    """One paired pass: scout proposes, verifier judges. Returns (report, proposed)."""
    scout = scout or Scout()
    verifier = verifier or Verifier()
    proposed = scout.propose(raw_signals)
    return verifier.verify(proposed), proposed
