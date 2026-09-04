"""
Monotropism integration for LEVI

Theory note (Dinah Murray / autistic cognition literature):
Monotropism models attention as a few deep interest tunnels rather than
broad diffuse sampling. Depth rises when the same topic is reinforced;
forced topic-switches cost regulation. LEVI uses this to bias persona
lenses: tunnel-friendly (philosopher, strategist, observer) vs disruptive
(manic_pixie, chaotic) — and to avoid yanking the user mid-tunnel.
Not a diagnosis engine; an interaction physics for focus load.

Monotropism: attention as a limited set of deep interest tunnels rather than
a broad spotlight. When a human (or LEVI-with-human) is inside a tunnel,
detail density and pattern recognition rise; switching cost is high.

LEVI uses this to:
  1. Detect topic/interest continuity across turns (tunnel state)
  2. Boost persona lenses that suit deep focus (philosopher, strategist,
     creative, observer, hyper_systemizing-friendly stacks)
  3. Reduce intrigue / lateral_leap when tunnel depth is high
     (don't yank the human out of a useful tunnel)
  4. Feed bond affinity so preferred tunnels strengthen over time

Not a diagnosis claim. Operational control surface only.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timezone
import json
import re
import hashlib


DEFAULT_MONO_PATH = Path.home() / ".levi" / "monotropism.json"

# Lenses that thrive inside a deep interest tunnel
_TUNNEL_FRIENDLY = frozenset({
    "philosopher", "strategist", "creative", "observer", "void",
    "reframe", "normal",
})
# Lenses that tend to yank attention sideways (use sparingly in deep tunnel)
_TUNNEL_DISRUPTIVE = frozenset({
    "manic_pixie", "pirate", "drunk", "alien", "conspiracy", "chaotic_good",
})


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]{3,}", (text or "").lower())


def _topic_signature(tokens: List[str], top_n: int = 8) -> str:
    """Stable-ish signature from frequent content words."""
    if not tokens:
        return ""
    freq: Dict[str, int] = {}
    stop = {
        "the", "and", "for", "that", "this", "with", "you", "your", "have",
        "what", "when", "where", "how", "why", "can", "will", "just", "like",
        "from", "they", "them", "been", "were", "are", "was", "not", "but",
    }
    for t in tokens:
        if t in stop:
            continue
        freq[t] = freq.get(t, 0) + 1
    ranked = sorted(freq.items(), key=lambda x: (-x[1], x[0]))[:top_n]
    return "|".join(w for w, _ in ranked)


@dataclass
class InterestTunnel:
    """One active (or recent) monotropic focus."""
    signature: str
    label: str = ""
    depth: float = 0.2          # 0–1 how locked-in
    turns_in: int = 1
    last_tokens: List[str] = field(default_factory=list)
    reinforced: int = 0
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signature": self.signature,
            "label": self.label,
            "depth": round(self.depth, 4),
            "turns_in": self.turns_in,
            "last_tokens": self.last_tokens[:16],
            "reinforced": self.reinforced,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "InterestTunnel":
        return cls(
            signature=d.get("signature") or "",
            label=d.get("label") or "",
            depth=float(d.get("depth", 0.2)),
            turns_in=int(d.get("turns_in", 1)),
            last_tokens=list(d.get("last_tokens") or [])[:16],
            reinforced=int(d.get("reinforced", 0)),
            updated_at=d.get("updated_at") or datetime.now(timezone.utc).isoformat(),
        )


@dataclass
class MonotropismState:
    """Active tunnel + memory of preferred topics (bond-adjacent)."""
    active: Optional[InterestTunnel] = None
    recent: List[InterestTunnel] = field(default_factory=list)  # last few
    topic_affinity: Dict[str, float] = field(default_factory=dict)  # signature -> preference
    switch_cost: float = 0.0  # rises when forced out of a deep tunnel

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active": self.active.to_dict() if self.active else None,
            "recent": [t.to_dict() for t in self.recent[-8:]],
            "topic_affinity": {k: round(v, 4) for k, v in self.topic_affinity.items()},
            "switch_cost": round(self.switch_cost, 4),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MonotropismState":
        active = None
        if d.get("active"):
            active = InterestTunnel.from_dict(d["active"])
        recent = [InterestTunnel.from_dict(x) for x in (d.get("recent") or [])]
        return cls(
            active=active,
            recent=recent,
            topic_affinity=dict(d.get("topic_affinity") or {}),
            switch_cost=float(d.get("switch_cost", 0.0)),
        )


class MonotropismTracker:
    """
    Sense user text → update tunnel depth → emit persona/wit biases.

    Algorithm (per turn):
      tokens = tokenize(user_text)
      sig = topic_signature(tokens)
      if active and overlap(sig, active) high:
          deepen tunnel (depth += step, turns_in += 1)
      elif active and overlap medium:
          maintain with slight decay risk
      else:
          if active.depth high: switch_cost spikes
          park active into recent; open new tunnel (or none)

    Biases emitted:
      persona_bias(pid)  — boost tunnel-friendly when depth high
      wit_bias           — prefer hyper_systemizing / precision; suppress lateral/surreal
      prompt_block()     — instruction for model: stay in tunnel, dense detail OK
    """

    def __init__(self, path: Optional[Path] = None, seed_depth: float = 0.15):
        self.path = Path(path) if path else DEFAULT_MONO_PATH
        self.state = MonotropismState()
        self.seed_depth = seed_depth
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.state = MonotropismState.from_dict(raw)
        except Exception:
            pass

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state.to_dict(), indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def _overlap(sig_a: str, sig_b: str, tokens_a: List[str], tokens_b: List[str]) -> float:
        if not sig_a or not sig_b:
            # token Jaccard fallback
            sa, sb = set(tokens_a), set(tokens_b)
            if not sa or not sb:
                return 0.0
            return len(sa & sb) / max(1, len(sa | sb))
        a = set(sig_a.split("|"))
        b = set(sig_b.split("|"))
        if not a or not b:
            return 0.0
        return len(a & b) / max(1, len(a | b))

    def sense(self, user_text: str) -> MonotropismState:
        tokens = _tokenize(user_text)
        sig = _topic_signature(tokens)
        now = datetime.now(timezone.utc).isoformat()

        if not sig and not tokens:
            # empty turn — mild decay
            if self.state.active:
                self.state.active.depth = max(0.0, self.state.active.depth - 0.04)
            self.state.switch_cost = max(0.0, self.state.switch_cost - 0.05)
            self._persist()
            return self.state

        active = self.state.active
        if active and active.signature:
            ov = self._overlap(sig, active.signature, tokens, active.last_tokens)
            if ov >= 0.25:
                # same tunnel — deepen
                active.depth = min(1.0, active.depth + 0.08 + 0.12 * ov)
                active.turns_in += 1
                active.last_tokens = tokens[:16]
                active.signature = sig or active.signature
                active.updated_at = now
                active.reinforced += 1
                self.state.topic_affinity[active.signature] = min(
                    1.5,
                    self.state.topic_affinity.get(active.signature, 0.0) + 0.06,
                )
                self.state.switch_cost = max(0.0, self.state.switch_cost - 0.08)
            elif ov >= 0.12:
                # related — maintain
                active.depth = min(1.0, active.depth + 0.02)
                active.turns_in += 1
                active.last_tokens = tokens[:16]
                active.updated_at = now
            else:
                # switch
                if active.depth >= 0.45:
                    self.state.switch_cost = min(1.0, self.state.switch_cost + 0.25 + 0.3 * active.depth)
                self.state.recent.append(active)
                self.state.recent = self.state.recent[-8:]
                label = sig.replace("|", " ")[:48] if sig else "untitled"
                self.state.active = InterestTunnel(
                    signature=sig,
                    label=label,
                    depth=self.seed_depth + 0.1 * self.state.topic_affinity.get(sig, 0.0),
                    turns_in=1,
                    last_tokens=tokens[:16],
                    updated_at=now,
                )
        else:
            label = sig.replace("|", " ")[:48] if sig else "untitled"
            self.state.active = InterestTunnel(
                signature=sig,
                label=label,
                depth=self.seed_depth + 0.1 * self.state.topic_affinity.get(sig, 0.0),
                turns_in=1,
                last_tokens=tokens[:16],
                updated_at=now,
            )

        self._persist()
        return self.state

    def persona_bias(self, persona_id: str) -> float:
        """Additive score for nervous/composition (−0.4 .. +0.45)."""
        active = self.state.active
        if not active or active.depth < 0.2:
            return 0.0
        d = active.depth
        if persona_id in _TUNNEL_FRIENDLY:
            return 0.15 + 0.30 * d
        if persona_id in _TUNNEL_DISRUPTIVE:
            return -0.10 - 0.35 * d
        return 0.0

    def wit_preferred(self) -> Dict[str, float]:
        """Style preferences under monotropism."""
        active = self.state.active
        if not active or active.depth < 0.25:
            return {}
        d = active.depth
        return {
            "hyper_systemizing": 0.3 + 0.5 * d,
            "precision_deadpan": 0.2 + 0.3 * d,
            "anti_release": 0.1 + 0.2 * d,
            # suppress attention-yankers in deep tunnel
            "lateral_leap": -0.2 * d,
            "surreal_internal": -0.25 * d,
            "chaotic_self_report": -0.15 * d,
        }

    def prompt_block(self) -> str:
        active = self.state.active
        if not active or active.depth < 0.3:
            return ""
        return (
            f"MONOTROPISM: active interest tunnel depth~{active.depth:.2f}, "
            f"turns_in={active.turns_in}, topic≈'{active.label or active.signature[:40]}'. "
            "Stay inside this tunnel unless the human clearly changes subject. "
            "Dense detail and pattern depth are welcome. "
            "Do not yank attention with unrelated asides, random intrigue, or topic jumps. "
            f"Switch cost currently ~{self.state.switch_cost:.2f} — respect continuity."
        )

    def status(self) -> Dict[str, Any]:
        return self.state.to_dict()

    def format_status(self) -> str:
        a = self.state.active
        lines = ["=== Monotropism ===", ""]
        if a:
            lines.append(f"Active tunnel: {a.label or a.signature[:50]}")
            lines.append(f"  depth={a.depth:.2f}  turns_in={a.turns_in}  reinforced={a.reinforced}")
        else:
            lines.append("Active tunnel: —")
        lines.append(f"Switch cost: {self.state.switch_cost:.2f}")
        if self.state.topic_affinity:
            top = sorted(self.state.topic_affinity.items(), key=lambda x: -x[1])[:5]
            lines.append("Topic affinity:")
            for sig, w in top:
                lines.append(f"  {w:+.2f}  {sig[:60]}")
        return "\n".join(lines)
