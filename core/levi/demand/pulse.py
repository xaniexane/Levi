"""
DemandPulse — demand / gap / opportunity perception (subsystem, not the whole of LEVI).

Three engine families (activated on demand by the daemon, not all-at-once):
  - Demand engines: surface unmet needs
  - Opportunity engines: score serviceability vs cost
  - (Service engines live in income factory)

Outputs are HYPOTHESIS / INFERENCE until verified in corpus as OBSERVED.
"""

from __future__ import annotations

import hashlib
import json
import math
import warnings
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


from levi.demand.scoring import (
    DEFAULT_THRESHOLD,
    FactorInput,
    ScoreCard,
    rank_cards,
    score_card,
)


DEFAULT = Path.home() / ".levi" / "demand_pulse.json"


@dataclass
class DemandSignal:
    id: str
    need: str
    segment: str = "general"
    evidence: str = ""
    confidence: float = 0.4  # low until observed
    kind: str = "HYPOTHESIS"  # OBSERVED | INFERENCE | HYPOTHESIS
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError(f"signal id must be a non-empty string, got {self.id!r}")
        if not isinstance(self.need, str) or not self.need.strip():
            raise ValueError("signal need must be a non-empty string")
        if not isinstance(self.segment, str) or not self.segment.strip():
            raise ValueError(
                f"signal segment must be a non-empty string, got {self.segment!r}"
            )
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not math.isfinite(self.confidence)
            or not 0.0 <= self.confidence <= 1.0
        ):
            raise ValueError(
                f"signal confidence must be a number in [0, 1], got {self.confidence!r}"
            )
        if self.kind not in ("OBSERVED", "INFERENCE", "HYPOTHESIS"):
            raise ValueError(
                f"signal kind must be OBSERVED/INFERENCE/HYPOTHESIS, got {self.kind!r}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Opportunity:
    id: str
    demand_id: str
    title: str
    demand_score: float
    serviceability: float
    startup_cost: float  # 0–1 abstract (0 = free-first feasible)
    notes: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError(
                f"opportunity id must be a non-empty string, got {self.id!r}"
            )
        if not isinstance(self.demand_id, str) or not self.demand_id.strip():
            raise ValueError(
                f"opportunity demand_id must be a non-empty string, "
                f"got {self.demand_id!r}"
            )
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("opportunity title must be a non-empty string")
        for name in ("demand_score", "serviceability", "startup_cost"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0.0 <= value <= 1.0
            ):
                raise ValueError(
                    f"opportunity {name} must be a number in [0, 1], got {value!r}"
                )

    @property
    def worth(self) -> float:
        # high demand, high serviceability, low cost
        return (
            self.demand_score * 0.4
            + self.serviceability * 0.4
            + (1.0 - self.startup_cost) * 0.2
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["worth"] = round(self.worth, 3)
        return d


class DemandPulse:
    def __init__(self, path: Optional[Path] = None):
        if path is not None and not isinstance(path, (str, Path)):
            raise ValueError(
                f"path must be a str/Path or None, got {type(path).__name__}"
            )
        self.path = Path(path) if path else DEFAULT
        self.signals: List[DemandSignal] = []
        self.opportunities: List[Opportunity] = []
        self.score_cards: List[ScoreCard] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("top level must be an object")
            for kind, cls, attr in (
                ("signals", DemandSignal, "signals"),
                ("opportunities", Opportunity, "opportunities"),
            ):
                items = raw.get(kind) or []
                if not isinstance(items, list):
                    raise ValueError(f"{kind!r} must be a list")
                kept = []
                for s in items:
                    if not isinstance(s, dict):
                        continue
                    try:
                        kept.append(
                            cls(
                                **{
                                    k: v
                                    for k, v in s.items()
                                    if k in cls.__dataclass_fields__
                                }
                            )
                        )
                    except Exception:
                        continue  # one corrupt entry must not kill the rest
                setattr(self, attr, kept)
            self.score_cards = []
            cards = raw.get("score_cards") or []
            if not isinstance(cards, list):
                raise ValueError("'score_cards' must be a list")
            for c in cards:
                try:
                    self.score_cards.append(ScoreCard.from_dict(c))
                except Exception:
                    continue
        except Exception as exc:
            warnings.warn(
                f"demand pulse file {self.path} is unreadable "
                f"({type(exc).__name__}); starting empty. "
                "Back up or delete the file to silence this warning.",
                UserWarning,
                stacklevel=3,
            )
            self.signals = []
            self.opportunities = []
            self.score_cards = []

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "signals": [s.to_dict() for s in self.signals[-100:]],
            "opportunities": [o.to_dict() for o in self.opportunities[-100:]],
            "score_cards": [c.to_dict() for c in self.score_cards[-100:]],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def _check01(self, name: str, value: float) -> float:
        """Public-boundary 0-1 score check: rejects garbage, no silent clamping."""
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError(f"{name} must be a number in [0, 1], got {value!r}")
        value = float(value)
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be in [0, 1], got {value!r}")
        return value

    def scan_seed(self, text: str, segment: str = "general") -> DemandSignal:
        """Register a demand signal from user/context text (not invented market data)."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"text must be a non-empty string, got {text!r}")
        if not isinstance(segment, str) or not segment.strip():
            raise ValueError(f"segment must be a non-empty string, got {segment!r}")
        t = text.strip()
        hid = hashlib.sha256(t.encode()).hexdigest()[:8]
        sig = DemandSignal(
            id=hid,
            need=t[:300],
            segment=segment.strip(),
            evidence="user_or_context_seed",
            confidence=0.35,
            kind="HYPOTHESIS",
        )
        self.signals.append(sig)
        self._persist()
        return sig

    def score_opportunity(
        self,
        demand_id: str,
        title: str,
        demand_score: float = 0.5,
        serviceability: float = 0.5,
        startup_cost: float = 0.3,
        notes: str = "",
    ) -> Opportunity:
        """Score an opportunity; scores must already be on the 0-1 scale.

        Wrong types, non-finite values, and out-of-range numbers are
        all rejected — a public boundary never silently clamps garbage
        into a plausible-looking score.
        """
        if not isinstance(demand_id, str) or not demand_id.strip():
            raise ValueError(f"demand_id must be a non-empty string, got {demand_id!r}")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title must be a non-empty string")
        if not isinstance(notes, str):
            raise ValueError(f"notes must be a string, got {type(notes).__name__}")
        opp = Opportunity(
            id=hashlib.sha256(f"{demand_id}{title}".encode()).hexdigest()[:8],
            demand_id=demand_id.strip(),
            title=title.strip(),
            demand_score=self._check01("demand_score", demand_score),
            serviceability=self._check01("serviceability", serviceability),
            startup_cost=self._check01("startup_cost", startup_cost),
            notes=notes,
        )
        self.opportunities.append(opp)
        self._persist()
        return opp

    def _check_n(self, name: str, n: int) -> int:
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise ValueError(f"{name} must be a positive integer, got {n!r}")
        return n

    def top_opportunities(self, n: int = 5) -> List[Opportunity]:
        n = self._check_n("n", n)
        return sorted(self.opportunities, key=lambda o: -o.worth)[:n]

    def score_five_factor(
        self,
        demand_id: str,
        title: str,
        factors: Dict[str, FactorInput],
        weights: Optional[Dict[str, float]] = None,
        threshold: float = DEFAULT_THRESHOLD,
        notes: str = "",
    ) -> ScoreCard:
        """Score an opportunity on the five-factor model.

        ``factors`` maps each factor name to a FactorScore, a
        ``(value, basis)`` pair, or a ``{"value":.., "basis":..}`` mapping.
        Every factor requires a non-empty basis — the honesty guardrail.
        Pure scoring; the card is then persisted.
        """
        if not isinstance(demand_id, str) or not demand_id.strip():
            raise ValueError(f"demand_id must be a non-empty string, got {demand_id!r}")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title must be a non-empty string")
        card_id = hashlib.sha256(f"{demand_id}{title}ff".encode()).hexdigest()[:8]
        card = score_card(
            card_id, title, factors, weights=weights, threshold=threshold, notes=notes
        )
        self.score_cards.append(card)
        self._persist()
        return card

    def top_score_cards(self, n: int = 5) -> List[ScoreCard]:
        n = self._check_n("n", n)
        return rank_cards(self.score_cards)[:n]

    def format_status(self) -> str:
        lines = [
            "=== DemandPulse ===",
            f"signals={len(self.signals)}  opportunities={len(self.opportunities)}",
            "",
        ]
        for o in self.top_opportunities(5):
            lines.append(
                f"  worth={o.worth:.2f}  {o.title}  (cost={o.startup_cost:.2f} svc={o.serviceability:.2f})"
            )
        if self.score_cards:
            lines.append("")
            lines.append("five-factor score cards:")
            for c in self.top_score_cards(5):
                flag = " ALERT" if c.alert else ""
                lines.append(f"  {c.composite:6.2f} [{c.tier}]{flag}  {c.title}")
        if not self.opportunities and not self.score_cards:
            lines.append('  (none — seed with: levi demand --scan "…")')
        lines.append("")
        lines.append("Labels are HYPOTHESIS until verified OBSERVED in corpus.")
        return "\n".join(lines)
