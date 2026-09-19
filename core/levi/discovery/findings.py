"""Capability discoveries: an append-only JSONL log of what the harness finds.

Every discovery records an anonymized target label, the probe that found
it, a plain-language observation, and exact repro steps — so any finding
can be re-run and either confirmed or retired.

Anonymity is structural, not conventional: :meth:`FindingsLog.record`
REFUSES any target label that is not in one of the anonymized forms::

    op:<operator-name>      -- an operator from a registry
    pack:<pack-name>        -- a genesis/legion pack dict
    dw:<hex>                -- a dynasty wave agent, hash label only

Raw names (dynastic or otherwise) can never enter the log through this
API. Dynasty findings therefore carry labels only — never Section 0
material, never provenance, never raw agent names.

Stdlib only. No network.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional

__all__ = [
    "CapabilityDiscovery",
    "FindingsLog",
    "SIGNIFICANCE_LEVELS",
    "is_anonymized_label",
]

#: Significance ladder. "curiosity" = boundary documented, nothing
#: surprising; "notable" = capability beyond documented scope, or a
#: hardening confirmation worth keeping; "significant" = a robustness
#: or trust gap that needs a fix or a decision.
SIGNIFICANCE_LEVELS: tuple[str, ...] = ("curiosity", "notable", "significant")

#: Anonymized label forms. Dynasty labels are hex digests only.
_LABEL_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"^op:[A-Za-z0-9_.\-]{1,64}$"),
    re.compile(r"^pack:[A-Za-z0-9_.\-]{1,64}$"),
    re.compile(r"^dw:[0-9a-f]{8,64}$"),
)

#: Default log location: inside the discovery package.
DEFAULT_FINDINGS_PATH = Path(__file__).resolve().parent / "findings.jsonl"


def is_anonymized_label(label: object) -> bool:
    """True when the label is in an anonymized ``prefix:value`` form."""
    return isinstance(label, str) and any(p.match(label) for p in _LABEL_PATTERNS)


@dataclass
class CapabilityDiscovery:
    """One recorded discovery: what a probe found, and how to redo it."""

    id: str  # "disc-<UTC timestamp>-<8 hex>"
    target_label: str  # anonymized: op: / pack: / dw:
    probe: str  # "pack/probe-id"
    observation: str  # plain-language: what the target actually did
    repro_steps: str  # exact steps to reproduce
    significance: str  # one of SIGNIFICANCE_LEVELS
    timestamp: str  # ISO-8601 UTC

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CapabilityDiscovery":
        return cls(
            id=str(data.get("id", "")),
            target_label=str(data.get("target_label", "")),
            probe=str(data.get("probe", "")),
            observation=str(data.get("observation", "")),
            repro_steps=str(data.get("repro_steps", "")),
            significance=str(data.get("significance", "curiosity")),
            timestamp=str(data.get("timestamp", "")),
        )


def _new_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"disc-{stamp}-{uuid.uuid4().hex[:8]}"


class FindingsLog:
    """Append-only JSONL log of :class:`CapabilityDiscovery` records.

    The log file is created on first :meth:`record`. Reads tolerate
    blank lines and malformed rows (skipped, never fatal) so one bad
    line cannot corrupt the history.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_FINDINGS_PATH

    def record(
        self,
        *,
        target_label: str,
        probe: str,
        observation: str,
        repro_steps: str,
        significance: str = "curiosity",
    ) -> CapabilityDiscovery:
        """Append one discovery. Raises :class:`ValueError` when the
        label is not anonymized or the significance is unknown —
        fail-closed, so raw names can never enter the log."""
        if not is_anonymized_label(target_label):
            raise ValueError(
                "findings require an anonymized target label "
                f"(op:<name> | pack:<name> | dw:<hex>); got {target_label!r}"
            )
        if significance not in SIGNIFICANCE_LEVELS:
            raise ValueError(
                f"unknown significance {significance!r}; "
                f"must be one of {SIGNIFICANCE_LEVELS}"
            )
        if not observation or not observation.strip():
            raise ValueError("observation must be non-empty")
        if not repro_steps or not repro_steps.strip():
            raise ValueError("repro_steps must be non-empty")
        discovery = CapabilityDiscovery(
            id=_new_id(),
            target_label=target_label,
            probe=str(probe),
            observation=observation.strip(),
            repro_steps=repro_steps.strip(),
            significance=significance,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(discovery.to_dict(), ensure_ascii=False) + "\n")
        return discovery

    def list(
        self,
        *,
        target_label: Optional[str] = None,
        probe: Optional[str] = None,
        significance: Optional[str] = None,
    ) -> List[CapabilityDiscovery]:
        """Read back discoveries, newest last, with optional filters."""
        out: List[CapabilityDiscovery] = []
        if not self.path.exists():
            return out
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue  # a bad row never corrupts the history
            disc = CapabilityDiscovery.from_dict(data)
            if target_label is not None and disc.target_label != target_label:
                continue
            if probe is not None and disc.probe != probe:
                continue
            if significance is not None and disc.significance != significance:
                continue
            out.append(disc)
        return out

    def __iter__(self) -> Iterator[CapabilityDiscovery]:
        return iter(self.list())

    def __len__(self) -> int:
        return len(self.list())
