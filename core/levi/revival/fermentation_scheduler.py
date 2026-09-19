"""fermentation_scheduler — indigo vats: the living corpus, re-digested weekly.

Studied from: lost-crafts-20260916 — report.md [Batch 4]
(Indigo Fermentation Vats).

Load-bearing idea: an indigo vat is a living microbial consortium kept
alive for months by craft skill — the dyer feeds and stirs it on a
rhythm, and neglect kills it. LEVI's take: a corpus of ``VatItem``s
kept alive by a weekly ``digest()`` pass with four stages — dedup
(identical items merged), re-extract (stale extracted notes are
re-read against the item), promote (high-confidence items graduate),
compost (dead items are removed, their husks logged). Each digest is a
feeding: it restores the vat's ``health``; weeks skipped without a
digest let health decay, and a dead vat refuses to yield anything until
re-seeded. Re-extraction and promotion use caller-supplied heuristics —
this module schedules and tracks; it does not pretend to understand.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


ORIGIN = "levi-revival/fermentation-scheduler"

DIGEST_INTERVAL = 7 * 24 * 3600  # one week between feedings, in seconds
HEALTH_PER_DIGEST = 25.0
HEALTH_DECAY_PER_WEEK = 20.0


@dataclass
class VatItem:
    """One body in the vat."""

    id: str
    text: str
    confidence: float = 0.5  # 0.0 .. 1.0; promotion is heuristic
    extractions: List[str] = field(default_factory=list)
    alive: bool = True
    digests_survived: int = 0


@dataclass
class DigestLog:
    """What one weekly digestion did."""

    at: float
    deduped: int
    reextracted: int
    promoted: int
    composted: int


Extractor = Callable[[VatItem], List[str]]  # (item) -> extracted notes
Promoter = Callable[[VatItem], bool]  # (item) -> promote?


class FermentationScheduler:
    """A living corpus, kept alive by weekly re-digestion."""

    def __init__(
        self,
        extractor: Optional[Extractor] = None,
        promoter: Optional[Promoter] = None,
    ) -> None:
        self.items: Dict[str, VatItem] = {}
        self.logs: List[DigestLog] = []
        self.health: float = 100.0
        self.last_digest: Optional[float] = None
        self.extractor = extractor or (lambda item: [])
        self.promoter = promoter or (lambda item: item.confidence >= 0.9)

    # -- feeding the vat --------------------------------------------------------

    def seed(self, text: str, confidence: float = 0.5) -> VatItem:
        """Add a fresh body to the vat."""
        item = VatItem(id=uuid.uuid4().hex[:8], text=text, confidence=confidence)
        self.items[item.id] = item
        return item

    def digest(self, now: Optional[float] = None) -> DigestLog:
        """One weekly re-digestion: dedup, re-extract, promote, compost.

        Feeding restores health. Skipped weeks decay it; a dead vat
        (health 0) refuses to digest until re-seeded and fed.
        """
        ts = now if now is not None else time.time()
        if self.last_digest is not None:
            weeks = max(0.0, (ts - self.last_digest) / DIGEST_INTERVAL)
            self.health = max(0.0, self.health - weeks * HEALTH_DECAY_PER_WEEK)
        if self.health <= 0.0 and self.last_digest is not None:
            raise ValueError("the vat is dead: re-seed and feed before digesting")

        log = DigestLog(at=ts, deduped=0, reextracted=0, promoted=0, composted=0)

        # Stage 1: dedup — merge identical texts, keep the eldest body.
        seen: Dict[str, str] = {}
        for item in list(self.items.values()):
            key = " ".join(item.text.strip().lower().split())
            if key in seen:
                keeper = self.items[seen[key]]
                keeper.confidence = max(keeper.confidence, item.confidence)
                keeper.extractions.extend(item.extractions)
                del self.items[item.id]
                log.deduped += 1
            else:
                seen[key] = item.id

        # Stage 2: re-extract — re-read every surviving body.
        for item in self.items.values():
            new_notes = self.extractor(item)
            if new_notes:
                item.extractions.extend(new_notes)
                log.reextracted += 1

        # Stage 3: promote — high-confidence bodies graduate.
        for item in self.items.values():
            if item.alive and self.promoter(item):
                item.confidence = min(1.0, item.confidence + 0.05)
                log.promoted += 1

        # Stage 4: compost — bodies with no text and no extractions rot away.
        for item in list(self.items.values()):
            if not item.text.strip() and not item.extractions:
                del self.items[item.id]
                log.composted += 1

        for item in self.items.values():
            item.digests_survived += 1

        self.health = min(100.0, self.health + HEALTH_PER_DIGEST)
        self.last_digest = ts
        self.logs.append(log)
        return log

    # -- reading the vat ----------------------------------------------------------

    def living(self) -> List[VatItem]:
        """Surviving bodies, eldest digest-count first."""
        return sorted(self.items.values(), key=lambda i: -i.digests_survived)

    def is_alive(self) -> bool:
        return self.health > 0.0
