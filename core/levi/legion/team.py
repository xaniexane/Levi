"""Tailored team assembly: pick a named crew from the existing
agent/hive population for one business.

Adapter-wrapped: crew seats resolve through
``levi.hive.orchestrate.seats_for`` (lazy import, so the hive layer can
be swapped without touching this module). Nothing here rewrites the
hive — it wraps it.

A Team = named crew (role -> seat) + responsibilities + handoff rules.
Assembly is deterministic: same business profile, same team.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from .product import LegionError

# Operator-contract seam (Chauncey, 2026-09-18): the one-face router
# resolves its crew through the operator registry — any operator
# swappable into any seat by config. Registry is live as of the
# sibling operator track (levi.operator.registry.resolve_for_seat);
# the roster adapter stays the live crew source.
OPERATOR_REGISTRY_PENDING = False


# ---------------------------------------------------------------------------
# Business profile -> needs -> crew roles
# ---------------------------------------------------------------------------


BUSINESS_TYPES = ("restaurant", "salon", "shop", "generic")
SIZES = ("solo", "small", "team")


@dataclass
class BusinessProfile:
    """What the business is and what it needs the Legion crew to cover."""

    business_type: str = "generic"
    size: str = "small"
    needs: List[str] = field(default_factory=list)
    business_name: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if self.business_type not in BUSINESS_TYPES:
            raise LegionError(
                f"business_type must be one of {BUSINESS_TYPES}, "
                f"got {self.business_type!r}"
            )
        if self.size not in SIZES:
            raise LegionError(
                f"size must be one of {SIZES}, got {self.size!r}"
            )
        self.needs = [n for n in (self.needs or []) if n and n.strip()]
        for n in self.needs:
            if n not in NEED_TO_CATEGORY:
                raise LegionError(
                    f"unknown need {n!r} — must be one of "
                    f"{sorted(NEED_TO_CATEGORY)}"
                )


# need -> roster category that carries the crew seat for it
NEED_TO_CATEGORY: Dict[str, str] = {
    "booking": "Productivity",
    "contact": "Communication",
    "hours": "Travel & Local",
    "pricing": "Finance & Money",
    "reviews": "Social & Content",
    "gallery": "Social & Content",
    "social": "Social & Content",
    "catalog": "Shopping & Deals",
    "ordering": "Shopping & Deals",
    "faq": "Learning & Notes",
    "reminders": "Productivity",
    "insights": "System & Device Care",
    "reception": "Communication",
}

# need -> named crew role the customer-facing team uses
NEED_ROLE: Dict[str, str] = {
    "booking": "booker",
    "contact": "receptionist",
    "hours": "receptionist",
    "pricing": "cashier",
    "reviews": "marketer",
    "gallery": "marketer",
    "social": "marketer",
    "catalog": "merchandiser",
    "ordering": "cashier",
    "faq": "librarian",
    "reminders": "booker",
    "insights": "analyst",
    "reception": "receptionist",
}

# role -> what the crew member is responsible for
ROLE_RESPONSIBILITIES: Dict[str, str] = {
    "booker": "takes and confirms appointments/reservations; reschedules",
    "receptionist": "answers contact, hours, location questions; takes messages",
    "cashier": "quotes prices, menus, packages; never moves money",
    "marketer": "handles reviews, social mentions, gallery/portfolio",
    "merchandiser": "answers catalog/product questions; tracks stock notes",
    "librarian": "answers FAQs; quotes policy pages",
    "analyst": "summarizes insights for the owner (reports only, no advice)",
}

# sensible defaults per business type when the profile names no needs
DEFAULT_NEEDS: Dict[str, List[str]] = {
    "restaurant": ["booking", "contact", "pricing", "reviews"],
    "salon": ["booking", "pricing", "gallery", "contact"],
    "shop": ["catalog", "ordering", "contact", "reviews"],
    "generic": ["contact", "faq"],
}


# ---------------------------------------------------------------------------
# Crew adapter — the seam over the hive
# ---------------------------------------------------------------------------


def _seats_for_category(category: str) -> List[str]:
    """Resolve seat keys for a roster category via the hive adapter.

    Lazy import so this module never hard-couples to the hive; a future
    operator registry can replace this seam.
    """
    try:
        from levi.hive.orchestrate import seats_for
    except ImportError as exc:
        raise LegionError(
            f"crew adapter unavailable: hive orchestration not importable ({exc})"
        )
    try:
        return seats_for(category=category)
    except ValueError as exc:
        raise LegionError(f"crew adapter: {exc}")


def resolve_operator_seat(
    seat_key: str, config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Operator-contract seam: resolve one crew seat to an operator name
    through the universal operator registry.

    Uses levi.operator.registry.resolve_for_seat: the registry maps a
    seat to an operator name from config (with sane defaults), which
    honors Chauncey's interchangeable-operators directive — any
    operator, LEVI-native or otherwise, swappable into any seat by
    config. ImportError keeps the seam honest: resolution is reported
    as pending and the roster adapter stays the live path.
    """
    try:
        from levi.operator import registry as _registry
    except ImportError:
        return {
            "seat_key": seat_key,
            "resolved": False,
            "status": "PENDING: levi.operator.registry unavailable — "
                      "crew resolves through the hive/roster adapter",
        }
    try:
        operator_name = _registry.resolve_for_seat(seat_key, config or {})
    except Exception as exc:  # registry must never break team assembly
        return {
            "seat_key": seat_key,
            "resolved": False,
            "status": f"operator registry error ({exc}) — roster adapter stays live",
        }
    return {
        "seat_key": seat_key,
        "resolved": True,
        "operator": operator_name,
        "status": "resolved via levi.operator.registry",
    }


# ---------------------------------------------------------------------------
# Team assembly
# ---------------------------------------------------------------------------


@dataclass
class CrewMember:
    role: str
    seat_key: str
    category: str
    responsibility: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HandoffRule:
    """One handoff rule: when <event>, <from_role> hands to <to_role>."""

    event: str
    from_role: str
    to_role: str
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Team:
    team_id: str
    business_name: str
    business_type: str
    size: str
    face_role: str
    crew: List[CrewMember] = field(default_factory=list)
    handoff_rules: List[HandoffRule] = field(default_factory=list)
    assembled_at: str = ""
    needs_covered: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        raw = asdict(self)
        return raw

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Team":
        data = dict(raw)
        data["crew"] = [
            c if isinstance(c, CrewMember) else CrewMember(**c)
            for c in data.get("crew", [])
        ]
        data["handoff_rules"] = [
            h if isinstance(h, HandoffRule) else HandoffRule(**h)
            for h in data.get("handoff_rules", [])
        ]
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


def assemble_team(profile: BusinessProfile) -> Team:
    """Assemble the tailored team for a business profile.

    Deterministic: seat selection walks the roster in registry order and
    takes the first seat of each needed category (index shifts by one
    per repeated category, so two roles on the same category get
    different seats). Same profile -> same team, always.
    """
    needs = list(profile.needs) or list(DEFAULT_NEEDS[profile.business_type])
    if not needs:
        raise LegionError("profile names no needs and has no defaults")
    category_uses: Dict[str, int] = {}
    crew: List[CrewMember] = []
    seen_roles = set()
    for need in needs:
        category = NEED_TO_CATEGORY[need]
        seats = _seats_for_category(category)
        if not seats:
            raise LegionError(f"no crew seats in category {category!r}")
        idx = category_uses.get(category, 0) % len(seats)
        category_uses[category] = idx + 1
        role = NEED_ROLE[need]
        if role in seen_roles:
            continue  # one seat per role; the need is still covered
        seen_roles.add(role)
        crew.append(
            CrewMember(
                role=role,
                seat_key=seats[idx],
                category=category,
                responsibility=ROLE_RESPONSIBILITIES[role],
            )
        )
    roles = [m.role for m in crew]
    face_role = "receptionist" if "receptionist" in roles else roles[0]
    slug = (profile.business_name or profile.business_type).lower()
    slug = "".join(c if c.isalnum() else "-" for c in slug).strip("-") or "team"
    team_id = f"legion-team-{slug}"
    return Team(
        team_id=team_id,
        business_name=profile.business_name,
        business_type=profile.business_type,
        size=profile.size,
        face_role=face_role,
        crew=crew,
        handoff_rules=_standard_handoffs(roles, face_role),
        assembled_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        needs_covered=needs,
    )


def _standard_handoffs(roles: List[str], face_role: str) -> List[HandoffRule]:
    """The one-face handoff lattice: face triages, crew owns, owner
    catches what the crew can't finish."""
    rules = [
        HandoffRule(
            event="intent the face cannot answer itself",
            from_role=face_role,
            to_role="owning crew role per router",
            note="face routes, never guesses",
        )
    ]
    for role in roles:
        if role == face_role:
            continue
        rules.append(
            HandoffRule(
                event=f"{role} cannot complete a request",
                from_role=role,
                to_role=face_role,
                note="face re-triages or escalates to owner",
            )
        )
    rules.append(
        HandoffRule(
            event="complaint, payment dispute, or anything unsafe",
            from_role=face_role,
            to_role="owner",
            note="never handled by the crew alone",
        )
    )
    return rules
