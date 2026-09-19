"""Legion product definition: the one-face router config and the
white-label config schema with validation.

Canon: one face the customer talks to; the legion (tailored team of
agents) behind it doing the work. The face never wears another
company's brand (no-mask law) and never claims to be LEVI, the full
organism — it is a Legion install, white-labeled per business.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from levi.bot.persona import check_no_mask

PRODUCT_NAME = "Legion bot"

# Face voice options the owner picks at install time. Plain, owner-set
# tone labels — the Legion face never invents a provider voice.
VALID_TONES = ("warm", "professional", "playful", "direct", "concierge")

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


class LegionError(ValueError):
    """Raised when a product config violates the product rules."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# One-face router config
# ---------------------------------------------------------------------------


@dataclass
class FaceRoute:
    """One intent -> crew handoff in the one-face router.

    intent: a short intent label (e.g. "booking").
    match_words: trigger words (lowercased) that route this way.
    role: the crew role that owns the intent.
    escalation: where the face sends it when the crew member can't finish.
    """

    intent: str
    match_words: List[str]
    role: str
    escalation: str = "owner"

    def __post_init__(self) -> None:
        if not self.intent or not self.intent.strip():
            raise LegionError("FaceRoute.intent must be non-empty")
        if not self.role or not self.role.strip():
            raise LegionError("FaceRoute.role must be non-empty")
        self.match_words = [w.lower() for w in (self.match_words or [])]


@dataclass
class RouterConfig:
    """The single conversational face: name, routes, fallbacks.

    The face holds the conversation; every intent it cannot answer
    itself routes to a named crew role. crew_source describes how the
    roles resolve (operator registry when present — PENDING, see
    __init__; otherwise the assembled team seat keys).
    """

    face_name: str
    routes: List[FaceRoute] = field(default_factory=list)
    fallback_response: str = ""
    escalation_target: str = "owner"
    crew_source: str = "team"  # team | operator-registry (PENDING)

    def __post_init__(self) -> None:
        if not self.face_name or not self.face_name.strip():
            raise LegionError("RouterConfig.face_name must be non-empty")
        seen = set()
        for r in self.routes:
            if r.intent in seen:
                raise LegionError(f"duplicate intent in routes: {r.intent!r}")
            seen.add(r.intent)

    def route(self, text: str) -> Optional[FaceRoute]:
        """Route free text to the first matching crew role.

        Keyword match over lowercased text; first intent whose
        match_words hit wins (routes are priority-ordered). Returns None
        when nothing matches — the face then uses fallback_response.
        """
        lowered = (text or "").lower()
        for r in self.routes:
            for w in r.match_words:
                if w and w in lowered:
                    return r
        return None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "RouterConfig":
        data = dict(raw)
        data["routes"] = [
            r if isinstance(r, FaceRoute) else FaceRoute(**r)
            for r in data.get("routes", [])
        ]
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


def build_router(face_name: str, team_roles: List[str]) -> RouterConfig:
    """Build a default one-face router for a named crew.

    Each crew role gets an intent route; the face keeps the greeting,
    identity answers, and small talk; everything else hands off. The
    face's self-description is no-mask-checked: it names the Legion
    install honestly and never borrows another provider's identity.
    """
    roles = [r for r in team_roles if r and r.strip()]
    if not roles:
        raise LegionError("build_router needs at least one crew role")
    intent_words = {
        "booker": ["book", "appointment", "reserve", "schedule", "table"],
        "receptionist": ["contact", "call", "hours", "location", "direction", "phone"],
        "cashier": ["price", "cost", "how much", "menu", "rate", "package"],
        "marketer": ["review", "social", "photo", "gallery", "instagram", "event"],
        "concierge": ["recommend", "special", "offer", "deal"],
    }
    routes = [
        FaceRoute(
            intent=role,
            match_words=intent_words.get(role, [role]),
            role=role,
        )
        for role in roles
    ]
    fallback = (
        f"I'm {face_name} — let me get the right person on the team for that. "
        "Can you say a little more about what you need?"
    )
    violations = check_no_mask(fallback)
    if violations:
        raise LegionError(f"face copy fails no-mask law: {violations}")
    return RouterConfig(
        face_name=face_name,
        routes=routes,
        fallback_response=fallback,
    )


# ---------------------------------------------------------------------------
# White-label config schema
# ---------------------------------------------------------------------------


@dataclass
class WhiteLabel:
    """White-label config for one Legion install.

    The Legion install wears the business's own brand — name, colors,
    greeting, domain vocabulary — never another company's. The identity
    statement is fixed and honest: the bot is a Legion install powered
    by LEVI technology. Dynasty-internal material is never embedded.
    """

    business_name: str
    face_name: str = ""
    tone: str = "warm"
    greeting: str = ""
    brand_colors: Dict[str, str] = field(default_factory=dict)
    domain_vocabulary: List[str] = field(default_factory=list)
    business_type: str = "generic"  # restaurant | salon | shop | generic
    locale: str = "en-US"
    contact: str = ""
    hours: str = ""
    identity_statement: str = (
        "A Legion bot install, powered by LEVI technology."
    )
    configured_at: str = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.business_name or not self.business_name.strip():
            raise LegionError("WhiteLabel.business_name must be non-empty")
        self.business_name = self.business_name.strip()
        if self.tone not in VALID_TONES:
            raise LegionError(
                f"tone must be one of {VALID_TONES}, got {self.tone!r}"
            )
        if self.business_type not in ("restaurant", "salon", "shop", "generic"):
            raise LegionError(
                "business_type must be restaurant|salon|shop|generic, "
                f"got {self.business_type!r}"
            )
        for key, val in self.brand_colors.items():
            if not _HEX_COLOR.match(val or ""):
                raise LegionError(
                    f"brand_colors[{key!r}] must be a #RRGGBB hex, got {val!r}"
                )
        if len(self.greeting) > 280:
            raise LegionError("greeting must be 280 chars or fewer")
        if not self.face_name:
            self.face_name = self.business_name + " assistant"
        # The face copy is the business's brand + the fixed identity
        # statement: check the whole rendered intro for mask violations.
        copy = f"{self.face_name}. {self.identity_statement}"
        violations = check_no_mask(copy)
        if violations:
            raise LegionError(f"white-label copy fails no-mask law: {violations}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "WhiteLabel":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in raw.items() if k in known})


def configure(
    business_name: str,
    *,
    face_name: str = "",
    tone: str = "warm",
    greeting: str = "",
    brand_colors: Optional[Dict[str, str]] = None,
    domain_vocabulary: Optional[List[str]] = None,
    business_type: str = "generic",
    locale: str = "en-US",
    contact: str = "",
    hours: str = "",
) -> WhiteLabel:
    """Configure one white-labeled Legion install. Validates; raises
    LegionError on bad input."""
    return WhiteLabel(
        business_name=business_name,
        face_name=face_name,
        tone=tone,
        greeting=greeting,
        brand_colors=brand_colors or {},
        domain_vocabulary=list(domain_vocabulary or []),
        business_type=business_type,
        locale=locale,
        contact=contact,
        hours=hours,
    )
