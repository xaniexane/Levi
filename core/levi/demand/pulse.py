"""
DemandPulse — demand / gap / opportunity perception (subsystem, not the whole of LEVI).

Three engine families (activated on demand by the daemon, not all-at-once):
  - Demand engines: surface unmet needs
  - Opportunity engines: score serviceability vs cost
  - (Service engines live in income factory)

Outputs are HYPOTHESIS / INFERENCE until verified in corpus as OBSERVED.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime, timezone
import json
import hashlib


DEFAULT = Path.home() / ".levi" / "demand_pulse.json"


@dataclass
class DemandSignal:
    id: str
    need: str
    segment: str = "general"
    evidence: str = ""
    confidence: float = 0.4  # low until observed
    kind: str = "HYPOTHESIS"  # OBSERVED | INFERENCE | HYPOTHESIS
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

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
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def worth(self) -> float:
        # high demand, high serviceability, low cost
        return (self.demand_score * 0.4 + self.serviceability * 0.4 + (1.0 - self.startup_cost) * 0.2)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["worth"] = round(self.worth, 3)
        return d


class DemandPulse:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else DEFAULT
        self.signals: List[DemandSignal] = []
        self.opportunities: List[Opportunity] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.signals = [DemandSignal(**{k: v for k, v in s.items() if k in DemandSignal.__dataclass_fields__}) for s in (raw.get("signals") or [])]
            self.opportunities = []
            for o in raw.get("opportunities") or []:
                self.opportunities.append(Opportunity(**{k: v for k, v in o.items() if k in Opportunity.__dataclass_fields__}))
        except Exception:
            pass

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "signals": [s.to_dict() for s in self.signals[-100:]],
            "opportunities": [o.to_dict() for o in self.opportunities[-100:]],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def scan_seed(self, text: str, segment: str = "general") -> DemandSignal:
        """Register a demand signal from user/context text (not invented market data)."""
        t = (text or "").strip()
        hid = hashlib.sha256(t.encode()).hexdigest()[:8]
        sig = DemandSignal(
            id=hid,
            need=t[:300],
            segment=segment,
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
        opp = Opportunity(
            id=hashlib.sha256(f"{demand_id}{title}".encode()).hexdigest()[:8],
            demand_id=demand_id,
            title=title,
            demand_score=max(0.0, min(1.0, demand_score)),
            serviceability=max(0.0, min(1.0, serviceability)),
            startup_cost=max(0.0, min(1.0, startup_cost)),
            notes=notes,
        )
        self.opportunities.append(opp)
        self._persist()
        return opp

    def top_opportunities(self, n: int = 5) -> List[Opportunity]:
        return sorted(self.opportunities, key=lambda o: -o.worth)[:n]

    def format_status(self) -> str:
        lines = ["=== DemandPulse ===", f"signals={len(self.signals)}  opportunities={len(self.opportunities)}", ""]
        for o in self.top_opportunities(5):
            lines.append(f"  worth={o.worth:.2f}  {o.title}  (cost={o.startup_cost:.2f} svc={o.serviceability:.2f})")
        if not self.opportunities:
            lines.append("  (none — seed with: levi demand --scan \"…\")")
        lines.append("")
        lines.append("Labels are HYPOTHESIS until verified OBSERVED in corpus.")
        return "\n".join(lines)
