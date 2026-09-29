"""Demand adapter — the honest DemandPulse wiring (BUILT-HERE).

The demandpulse/ tree ships no signal/score API (checked 2026-09-23:
no scan/score/surface functions), so nothing here pretends to call one.
Instead Buzz Tunes keeps a structured demand log of REAL recorded
signals — plays, skips, curations, thread joins — at a known path that
DemandPulse senses (scan -> score -> surface). The curation pipeline's
improve phase scores candidates from these real signals only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

DEMAND_FILENAME = "demand.jsonl"


class DemandLog:
    """Append-only record of real listener signals."""

    def __init__(self, store_dir: str | Path) -> None:
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.store_dir / DEMAND_FILENAME

    def record(self, kind: str, track_id: str,
               details: Dict | None = None) -> Dict:
        if kind not in ("play", "skip", "queue", "curate", "thread_join",
                        "complete"):
            raise ValueError(f"unknown demand kind {kind!r}")
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            "track_id": track_id,
            "details": details or {},
        }
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event) + "\n")
        return event

    def events(self) -> List[Dict]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out


def demand_score(track_id: str, events: List[Dict]) -> float:
    """Score from real signals only: plays and completes count up,
    skips count double down. No signal -> 0.0 (never invented)."""
    score = 0.0
    for e in events:
        if e.get("track_id") != track_id:
            continue
        kind = e.get("kind")
        if kind in ("play", "complete"):
            score += 1.0
        elif kind == "skip":
            score -= 2.0
        elif kind in ("queue", "curate"):
            score += 0.5
    return score


def score_candidates(track_ids: List[str], log: DemandLog) -> Dict[str, float]:
    events = log.events()
    return {tid: demand_score(tid, events) for tid in track_ids}
