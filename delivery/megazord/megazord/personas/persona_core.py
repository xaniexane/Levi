"""
Persona core: base class + registry.
Every persona is defined by a soul_profile + traits dict.
"""

from __future__ import annotations
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import uuid, time

# ── Soul profile (5D Emotional Intelligence) ──────────────────────────────────


@dataclass
class SoulProfile:
    joy: float = 0.0  # -1.0 … +1.0
    trust: float = 0.0
    fear: float = 0.0
    surprise: float = 0.0
    sadness: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return dict(
            joy=self.joy,
            trust=self.trust,
            fear=self.fear,
            surprise=self.surprise,
            sadness=self.sadness,
        )

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> "SoulProfile":
        return cls(**{k: float(v) for k, v in d.items()})

    def nudge(self, **axes) -> "SoulProfile":
        """Return a new SoulProfile with the given axes shifted."""
        d = self.to_dict()
        for k, v in axes.items():
            d[k] = max(-1.0, min(1.0, d.get(k, 0.0) + v))
        return SoulProfile.from_dict(d)

    def dominate(self) -> str:
        """Return the dominant emotional axis."""
        d = self.to_dict()
        return max(d, key=d.get)


# ── Trait flags ──────────────────────────────────────────────────────────────


@dataclass
class PersonaTraits:
    # Behavior toggles
    verbose: bool = False
    cautious: bool = False  # high fear baseline → slow to act
    empathetic: bool = True
    creative: bool = False
    security_first: bool = False
    executor_mode: bool = False  # Alpha-style: just do it
    # Skill flags
    can_write_code: bool = False
    can_compile: bool = False
    can_write_automations: bool = False
    can_orchestrate: bool = False
    can_secure: bool = False
    can_broadcast: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PersonaTraits":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ── Persona ──────────────────────────────────────────────────────────────────


@dataclass
class Persona:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "UNNAMED"
    tagline: str = ""
    soul: SoulProfile = field(default_factory=SoulProfile)
    traits: PersonaTraits = field(default_factory=PersonaTraits)
    memory: List[Dict[str, Any]] = field(default_factory=list)
    created: float = field(default_factory=time.time)

    def think(self, prompt: str) -> Dict[str, Any]:
        """Called on every inbound prompt. Returns a Levi-style thought + decision dict."""
        return {
            "persona_id": self.id,
            "persona_name": self.name,
            "dominant": self.soul.dominate(),
            "soul": self.soul.to_dict(),
            "thought": f"[{self.name}] Processing: {prompt[:80]}",
            "traits": self.traits.to_dict(),
        }

    def react(
        self, context: Dict[str, Any], decision: str, confidence: float = 0.75
    ) -> Dict[str, Any]:
        """Return a soul-adjusted reaction envelope."""
        return {
            "persona_id": self.id,
            "persona_name": self.name,
            "decision": decision,
            "confidence": float(confidence),
            "dominant": self.soul.dominate(),
            "soul": self.soul.to_dict(),
            "context": context,
        }

    def snapshot(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "tagline": self.tagline,
            "soul": self.soul.to_dict(),
            "traits": self.traits.to_dict(),
            "created": self.created,
        }


# ── Registry ─────────────────────────────────────────────────────────────────


class PersonaRegistry:
    """Singleton registry of all known personas."""

    def __init__(self):
        self._personas: Dict[str, Persona] = {}

    def register(self, persona: Persona) -> None:
        self._personas[persona.name.upper()] = persona

    def get(self, name: str) -> Optional[Persona]:
        return self._personas.get(name.upper())

    def all(self) -> List[Persona]:
        return list(self._personas.values())

    def __contains__(self, name: str) -> bool:
        return name.upper() in self._personas


# ── Default registry instance ────────────────────────────────────────────────
DEFAULT_REGISTRY = PersonaRegistry()
