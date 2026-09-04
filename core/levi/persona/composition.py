"""
Persona Composition Graph — interpenetrating ensembles (chameleon LEVI).

Base catalog is finite (~100–200 named lenses). Combinations are effectively
unbounded: primary × secondary × accent under L.W.P. interpenetration, depth-bounded.

Multiple personas can be *active at once* as a stack:
  primary   — dominant voice (~60%)
  secondary — harmonic / contrast (~25%)
  accent    — intrigue or situational spice (~15%)

Bond-aware: over time, successful turns reinforce affinity weights per human.
Regulation still vetoes stacks that would worsen user tone.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timezone
import json
import random
import hashlib

DEFAULT_BOND_PATH = Path.home() / ".levi" / "persona_bond.json"


@dataclass
class PersonaStack:
    primary: str
    secondary: Optional[str] = None
    accent: Optional[str] = None
    weights: Tuple[float, float, float] = (0.60, 0.25, 0.15)
    blend_mode: str = "interpenetrate"  # interpenetrate | sequential | contrast
    intrigue: bool = False
    reason: str = ""

    def members(self) -> List[str]:
        out = [self.primary]
        if self.secondary:
            out.append(self.secondary)
        if self.accent:
            out.append(self.accent)
        return out

    def label(self) -> str:
        parts = [self.primary]
        if self.secondary:
            parts.append(self.secondary)
        if self.accent:
            parts.append(self.accent)
        return " × ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary": self.primary,
            "secondary": self.secondary,
            "accent": self.accent,
            "weights": list(self.weights),
            "blend_mode": self.blend_mode,
            "intrigue": self.intrigue,
            "reason": self.reason,
            "label": self.label(),
        }

    def prompt_block(self, resolve_name) -> str:
        """Text for system prompt describing the multi-lens stack."""
        lines = [
            f"Active persona ensemble (chameleon stack): {self.label()}.",
            f"Blend mode: {self.blend_mode}. Weights primary/secondary/accent = {self.weights}.",
        ]
        if self.primary:
            lines.append(f"Primary (~{int(self.weights[0]*100)}%): {resolve_name(self.primary)}.")
        if self.secondary:
            lines.append(f"Secondary (~{int(self.weights[1]*100)}%): {resolve_name(self.secondary)} — harmonic or foil.")
        if self.accent:
            lines.append(f"Accent (~{int(self.weights[2]*100)}%): {resolve_name(self.accent)} — intrigue/situational.")
        if self.intrigue:
            lines.append("Intrigue flag: allow one unexpected angle without abandoning care or regulation.")
        if self.reason:
            lines.append(f"Why this stack: {self.reason}")
        lines.append("Speak as one mind; do not announce the stack unless asked. Never violate integrity or user regulation.")
        return " ".join(lines)


@dataclass
class BondProfile:
    """Per-user affinity memory — suits them over time."""
    user_key: str = "default"
    affinity: Dict[str, float] = field(default_factory=dict)  # persona_id -> weight
    stack_history: List[str] = field(default_factory=list)
    intrigue_budget: float = 0.35  # residual capacity for surprise
    turns: int = 0
    wit_affinity: Dict[str, float] = field(default_factory=dict)  # style_id -> preference

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BondProfile":
        return cls(
            user_key=d.get("user_key") or "default",
            affinity=dict(d.get("affinity") or {}),
            stack_history=list(d.get("stack_history") or [])[-40:],
            intrigue_budget=float(d.get("intrigue_budget", 0.35)),
            turns=int(d.get("turns", 0)),
            wit_affinity=dict(d.get("wit_affinity") or {}),
        )


class CompositionEngine:
    """
    Builds multi-persona stacks from scored candidates + bond + regulation.
    Interpenetration is combinatorial; depth is bounded (max 3 active).
    """

    def __init__(
        self,
        bond_path: Optional[Path] = None,
        seed: Optional[int] = None,
        intrigue_rate: float = 0.18,
    ):
        self.bond_path = Path(bond_path) if bond_path else DEFAULT_BOND_PATH
        self.rng = random.Random(seed)
        self.intrigue_rate = intrigue_rate
        self.bond = BondProfile()
        self._load_bond()

    def _load_bond(self) -> None:
        if not self.bond_path.exists():
            return
        try:
            raw = json.loads(self.bond_path.read_text(encoding="utf-8"))
            self.bond = BondProfile.from_dict(raw)
        except Exception:
            pass

    def _persist_bond(self) -> None:
        self.bond_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.bond_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.bond.to_dict(), indent=2), encoding="utf-8")
        tmp.replace(self.bond_path)

    def reinforce(self, stack: PersonaStack, amount: float = 0.04) -> None:
        for i, pid in enumerate(stack.members()):
            w = amount * (1.0 if i == 0 else 0.6 if i == 1 else 0.35)
            self.bond.affinity[pid] = max(-0.5, min(1.5, self.bond.affinity.get(pid, 0.0) + w))
        self.bond.stack_history.append(stack.label())
        self.bond.turns += 1
        # Intrigue budget recovers slowly
        self.bond.intrigue_budget = min(1.0, self.bond.intrigue_budget + 0.02)
        self._persist_bond()

    def reinforce_wit(self, styles, amount: float = 0.05) -> None:
        """Bond remembers which wit styles landed well."""
        for i, sid in enumerate(styles or []):
            w = amount * (1.0 if i == 0 else 0.5)
            self.bond.wit_affinity[sid] = max(
                -0.4, min(1.2, self.bond.wit_affinity.get(sid, 0.0) + w)
            )
        self._persist_bond()


    def compose(
        self,
        ranked: List[Tuple[str, float]],
        avoid: Optional[List[str]] = None,
        user_tone: str = "neutral",
        regulation: str = "steady",
    ) -> PersonaStack:
        avoid_set = set(avoid or [])
        # Apply bond affinity to ranking
        adjusted: List[Tuple[str, float]] = []
        for pid, score in ranked:
            if pid in avoid_set:
                continue
            bond_w = self.bond.affinity.get(pid, 0.0)
            adjusted.append((pid, score + 0.25 * bond_w))
        adjusted.sort(key=lambda x: -x[1])
        if not adjusted:
            return PersonaStack(primary="normal", reason="fallback empty ranking")

        primary = adjusted[0][0]
        secondary = adjusted[1][0] if len(adjusted) > 1 else None
        accent = adjusted[2][0] if len(adjusted) > 2 else None

        # Under contain/soften: prefer harmonious secondary, reduce intrigue
        intrigue = False
        blend = "interpenetrate"
        reason = f"top scores under tone={user_tone}"

        if regulation in ("contain", "soften"):
            blend = "interpenetrate"
            # Secondary should be calm if possible
            calm_ids = [p for p, _ in adjusted if p.startswith(("temp_stoic", "temp_phlegmatic", "rel_guardian", "rel_witness", "rel_confidant", "normal", "void", "observer")) or "warm" in p or "clinical" in p]
            if calm_ids:
                secondary = calm_ids[0] if calm_ids[0] != primary else (calm_ids[1] if len(calm_ids) > 1 else secondary)
            accent = None  # no spice in crisis
            reason = f"regulated stack for {user_tone}/{regulation}"
        else:
            # Occasional intrigue: pick a distant accent
            if (
                self.rng.random() < self.intrigue_rate * self.bond.intrigue_budget
                and len(adjusted) > 5
                and regulation in ("steady", "match_light", "uplift")
            ):
                # take from lower ranks for surprise
                pool = [p for p, _ in adjusted[3:12] if p not in avoid_set]
                if pool:
                    accent = self.rng.choice(pool)
                    intrigue = True
                    blend = "contrast"
                    self.bond.intrigue_budget = max(0.05, self.bond.intrigue_budget - 0.12)
                    reason = "bond-fit primary with intrigue accent"

        # Special control personas: if primary is interrogation/no_hero/reframe keep them primary alone or light secondary
        special = {"interrogation", "no_hero", "reframe"}
        if primary in special:
            # allow secondary only if not conflicting special
            if secondary in special:
                secondary = next((p for p, _ in adjusted if p not in special and p != primary), None)
            accent = None
            intrigue = False
            reason = f"special control lens {primary}"

        weights = (0.62, 0.26, 0.12) if secondary and accent else (0.7, 0.3, 0.0) if secondary else (1.0, 0.0, 0.0)
        stack = PersonaStack(
            primary=primary,
            secondary=secondary,
            accent=accent if weights[2] > 0 else None,
            weights=weights,
            blend_mode=blend,
            intrigue=intrigue,
            reason=reason,
        )
        self.reinforce(stack, amount=0.03)
        return stack
