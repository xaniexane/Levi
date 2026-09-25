"""Shared branch substrate — Echoverse x Mandella coexistence.

Two organs, one shared substrate (binding design, 2026-08-22):

    Echoverse   — parallel paths; kinds taken | not_taken | wild
                  question: what *could* unfold
    Mandella    — choice under fog; keys A | B | C
                  question: what *should* I pick

Interpenetration (L7): Mandella can *seed* an Echoverse run from the
chosen option; Echoverse can *feed* Mandella constraints from a wild
branch. Neither owns the other.

Controlling prompt (union): both are BOUNDED SIMULATIONS, not literal
timelines (L1).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.echoverse.engine import BOUNDED_MARK, DEFAULT_DIR
from levi.echoverse.laws import BRANCH_KINDS


@dataclass
class Branch:
    """One branch on the shared substrate."""

    id: str
    kind: str  # taken | not_taken | wild (L7)
    label: str
    summary: str
    risk: str = "unknown"  # low | medium | high | unknown
    optionality: float = 0.5  # 0..1

    def __post_init__(self) -> None:
        if self.kind not in BRANCH_KINDS:
            raise ValueError(f"branch kind must be one of {BRANCH_KINDS}, got {self.kind!r}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EchoRun:
    """One bounded multi-path simulation."""

    id: str
    seed: str
    branches: List[Branch]
    insight: str
    mark: str = BOUNDED_MARK  # L1
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "seed": self.seed,
            "branches": [b.to_dict() for b in self.branches],
            "insight": self.insight,
            "mark": self.mark,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    def format(self) -> str:
        lines = [
            f"== Echoverse [{self.id}] ==",
            f"Seed: {self.seed}",
            "",
        ]
        for b in self.branches:
            lines.append(f"[{b.kind}] {b.label}")
            lines.append(f"  {b.summary}")
            lines.append(f"  risk={b.risk} | optionality={b.optionality:.2f}")
            lines.append("")
        lines.append(f"Insight: {self.insight}")
        lines.append(f"_{self.mark}_")
        lines.append("_Echoverse explores space; Mandella forces a stake and remembers refusal._")
        return "\n".join(lines)


class BranchStore:
    """Deterministic-ish branches from seed hash (local, no network). L9."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._runs: Dict[str, EchoRun] = {}
        self._load()

    def _load(self) -> None:
        path = self.data_dir / "runs.json"
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for r in raw.get("runs", []):
                branches = [Branch(**b) for b in r.get("branches", [])]
                run = EchoRun(
                    id=r["id"],
                    seed=r["seed"],
                    branches=branches,
                    insight=r.get("insight", ""),
                    mark=r.get("mark", BOUNDED_MARK),
                    created_at=r.get("created_at", ""),
                    metadata=r.get("metadata", {}),
                )
                self._runs[run.id] = run
        except Exception:
            pass

    def _persist(self) -> None:
        path = self.data_dir / "runs.json"
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "runs": [r.to_dict() for r in self._runs.values()],
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
        tmp.replace(path)

    @staticmethod
    def _h(seed: str, salt: str) -> int:
        return int(hashlib.sha256(f"{seed}|{salt}".encode("utf-8")).hexdigest()[:8], 16)

    def simulate(self, seed: str, cycles: int = 3) -> EchoRun:
        """Bounded multi-path simulation: taken / not_taken / wild."""
        seed = (seed or "silence").strip()
        cycles = max(1, min(int(cycles or 3), 7))
        h = self._h(seed, "root")

        taken_labels = [
            "Commit to the visible path",
            "Ship the smallest reversible step",
            "Follow the constraint already accepted",
        ]
        not_taken = [
            "Defer until one more signal arrives",
            "Hold the line; observe cascade pressure",
            "Refuse the frame; restate the problem",
        ]
        wild = [
            "Invert the goal; optimize for optionality",
            "Compose with an unrelated organ (interpenetration)",
            "Treat failure as RIEM fuel; extract the inverse map",
        ]

        branches = [
            Branch(
                id="br." + uuid.uuid4().hex[:8],
                kind="taken",
                label=taken_labels[h % 3],
                summary=f"Given '{seed[:80]}', the taken path spends current commitment and reduces ambiguity now.",
                risk=["medium", "low", "high"][h % 3],
                optionality=0.35 + (h % 30) / 100,
            ),
            Branch(
                id="br." + uuid.uuid4().hex[:8],
                kind="not_taken",
                label=not_taken[(h // 3) % 3],
                summary="The not-taken path preserves information at the cost of time and possible lock-in elsewhere.",
                risk=["low", "medium", "medium"][(h // 5) % 3],
                optionality=0.55 + (h % 25) / 100,
            ),
            Branch(
                id="br." + uuid.uuid4().hex[:8],
                kind="wild",
                label=wild[(h // 7) % 3],
                summary="Wild branch: high novelty, higher verification burden — useful when the frame itself is the bottleneck.",
                risk=["high", "medium", "high"][(h // 11) % 3],
                optionality=0.7 + (h % 20) / 100,
            ),
        ]

        for i in range(min(cycles, 3)):
            branches[i % 3].summary += f" Cycle note t{i+1}: pressure redistributes under governor."

        insights = [
            "Optionality compounds when reversibility is protected.",
            "The taken path is cheap only if verification is cheap.",
            "Wild branches need circuit-breakers or they become identity.",
            "Cooperation compounds under pressure when roles stay distinct.",
        ]
        insight = insights[h % len(insights)]

        run = EchoRun(
            id="echo." + uuid.uuid4().hex[:10],
            seed=seed,
            branches=branches,
            insight=insight,
            metadata={"cycles": cycles, "lineage": "Echo->Echoverse->LEVI (Grok-built)"},
        )
        self._runs[run.id] = run
        self._persist()
        return run

    def list(self, limit: int = 10) -> List[EchoRun]:
        return sorted(self._runs.values(), key=lambda r: r.created_at, reverse=True)[:limit]

    def get(self, run_id: str) -> Optional[EchoRun]:
        return self._runs.get(run_id)
