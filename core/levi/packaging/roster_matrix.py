"""Roster creation matrix: slots x roles x model types.

Chauncey's directive (2026-09-18): model types are a first-class
dimension of the roster creation matrix — every roster slot picks its
mind substrate. This module is the single source of truth for:

  * the valid model types, with HONEST status (no aspirations)
  * the slot catalog for genesis packages, tailored editions, Legion teams
  * resolving a roster spec into validated slot assignments

Nothing here moves money, touches auth, or calls a provider. It is the
grid teams are drawn on, not the engine that runs them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


class RosterError(Exception):
    """Raised when a roster spec names something the matrix cannot honor."""


# ---------------------------------------------------------------------------
# Model types — the mind substrate dimension.
# ---------------------------------------------------------------------------
# Status vocabulary (honest, no vibes):
#   planned    — Chauncey's direction, not built. Cannot be selected for a
#                real roster; asking raises RosterError.
#   auth-gated — built behind the escalation seam, but needs Chauncey's key.
#                Selectable only with explicit authorization recorded.
#   real-weak  — real weights, real answers, honestly weak.
#   real       — real, working, the default.


@dataclass(frozen=True)
class ModelType:
    """One mind substrate a roster slot can be backed by."""

    id: str
    description: str
    status: str
    detail: str


MODEL_TYPES: Dict[str, ModelType] = {
    "own-cloud": ModelType(
        id="own-cloud",
        description="LEVI's own cloud model — Chauncey's long-term direction",
        status="planned",
        detail="not built yet: no weights, no endpoint, no keys. "
        "Roster resolution refuses it until it exists.",
    ),
    "groq": ModelType(
        id="groq",
        description="Groq cloud teacher API — fastest, cheapest per call",
        status="auth-gated",
        detail="escalation seam built; needs Chauncey's Groq API key "
        "in secure storage before any slot may use it.",
    ),
    "gemini": ModelType(
        id="gemini",
        description="Gemini cloud teacher API — generous free tier, strong quality",
        status="auth-gated",
        detail="escalation seam built; needs Chauncey's Google AI Studio key.",
    ),
    "openai": ModelType(
        id="openai",
        description="OpenAI cloud teacher API — the standard, metered from dollar one",
        status="auth-gated",
        detail="escalation seam built; needs Chauncey's OpenAI key.",
    ),
    "xai": ModelType(
        id="xai",
        description="xAI Grok cloud teacher API — the familiar collaborator",
        status="auth-gated",
        detail="escalation seam built; needs Chauncey's xAI key.",
    ),
    "local-brain": ModelType(
        id="local-brain",
        description="LEVI native-brain weights, on this machine",
        status="real-weak",
        detail="weights exist and answer (explicit-only provider), "
        "but honestly weak. Fine for trivial seats, not for the face.",
    ),
    "rules": ModelType(
        id="rules",
        description="Rules engine — the honest local default",
        status="real",
        detail="working today, zero cost, always labeled as rules. "
        "The default mind behind every slot until a better one "
        "is authorized.",
    ),
}

# Status values that may actually back a live slot.
SELECTABLE_STATUSES = ("auth-gated", "real-weak", "real")

#: The model every slot falls back to. Zero cost, always real.
DEFAULT_MODEL = "rules"

#: Authorized teachers, in Chauncey's preferred order. A slot may name one
#: as its upgrade only when authorization is recorded (see resolve_roster).
TEACHER_PREFERENCE = ("groq", "gemini", "openai", "xai")


def model_types() -> List[ModelType]:
    """All model types, in canonical order."""
    return list(MODEL_TYPES.values())


def model_type(model_id: str) -> ModelType:
    """Look up one model type; raises RosterError on unknown id."""
    try:
        return MODEL_TYPES[model_id]
    except KeyError:
        raise RosterError(
            "unknown model type %r — valid: %s" % (model_id, sorted(MODEL_TYPES))
        ) from None


def is_selectable(model_id: str) -> bool:
    """True when the model type may back a live slot (not planned)."""
    return model_type(model_id).status in SELECTABLE_STATUSES


# ---------------------------------------------------------------------------
# Slots — the roster's other axis.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RosterSlot:
    """One seat on the team: a named role with its responsibility."""

    slot_id: str
    role: str
    responsibility: str
    stakes: str  # "low" | "medium" | "high" — guides teacher upgrade advice
    default_model: str = DEFAULT_MODEL


#: Crew roles shared by Legion teams (mirrors legion/team.py NEED_ROLE).
CREW_SLOTS: List[RosterSlot] = [
    RosterSlot("face", "face", "the one face the customer talks to", "high"),
    RosterSlot(
        "booker", "booker", "takes and confirms appointments/reservations", "medium"
    ),
    RosterSlot(
        "receptionist",
        "receptionist",
        "answers contact/hours/location; takes messages",
        "low",
    ),
    RosterSlot(
        "cashier",
        "cashier",
        "quotes prices, menus, packages; never moves money",
        "medium",
    ),
    RosterSlot(
        "marketer", "marketer", "handles reviews, social mentions, gallery", "medium"
    ),
    RosterSlot(
        "merchandiser", "merchandiser", "catalog/product questions; stock notes", "low"
    ),
    RosterSlot("librarian", "librarian", "answers FAQs; quotes policy pages", "low"),
    RosterSlot(
        "analyst",
        "analyst",
        "summarizes insights for the owner (reports only)",
        "medium",
    ),
]

#: Edition slots for tailored genesis editions (government, schools,
#: universities, corporate, tiny business): face + pick-list crew.
EDITION_SLOTS: List[RosterSlot] = [
    RosterSlot(
        "face", "face", "the one face the organization's people talk to", "high"
    ),
    RosterSlot("intake", "intake", "routes requests to the right seat", "medium"),
    RosterSlot(
        "concierge", "concierge", "answers everyday questions for staff/visitors", "low"
    ),
    RosterSlot("scribe", "scribe", "drafts documents, summaries, notices", "medium"),
    RosterSlot("scheduler", "scheduler", "books rooms, shifts, appointments", "medium"),
    RosterSlot(
        "analyst", "analyst", "summarizes reports for leadership (reports only)", "high"
    ),
]

EDITIONS = ("government", "schools", "universities", "corporate", "tiny-business")


def slots_for(kind: str) -> List[RosterSlot]:
    """Slot catalog for a roster kind: 'crew' or 'edition'."""
    if kind == "crew":
        return list(CREW_SLOTS)
    if kind == "edition":
        return list(EDITION_SLOTS)
    raise RosterError("unknown slot kind %r — want 'crew' or 'edition'" % kind)


# ---------------------------------------------------------------------------
# Resolution — spec -> validated assignments.
# ---------------------------------------------------------------------------


@dataclass
class SlotAssignment:
    """One resolved slot: role + the mind backing it + honest status."""

    slot_id: str
    role: str
    model_id: str
    model_status: str
    authorized: bool = False
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "role": self.role,
            "model_id": self.model_id,
            "model_status": self.model_status,
            "authorized": self.authorized,
            "note": self.note,
        }


def resolve_roster(
    kind: str,
    slot_ids: Optional[List[str]] = None,
    model_overrides: Optional[Dict[str, str]] = None,
    authorized_teachers: Optional[List[str]] = None,
) -> List[SlotAssignment]:
    """Resolve a roster spec into validated slot assignments.

    kind: 'crew' (Legion team) or 'edition' (tailored genesis edition).
    slot_ids: which slots to fill (default: all for the kind).
    model_overrides: {slot_id: model_id} — explicit substrate picks.
    authorized_teachers: model ids Chauncey has authorized (key in vault).
        An auth-gated model may only be assigned when listed here;
        anything else raises RosterError instead of pretending.
    """
    catalog = {s.slot_id: s for s in slots_for(kind)}
    if slot_ids is None:
        slot_ids = [s.slot_id for s in catalog.values()]
    overrides = model_overrides or {}
    authorized = set(authorized_teachers or [])

    assignments: List[SlotAssignment] = []
    for slot_id in slot_ids:
        if slot_id not in catalog:
            raise RosterError(
                "unknown slot %r for kind %r — valid: %s"
                % (slot_id, kind, sorted(catalog))
            )
        slot = catalog[slot_id]
        model_id = overrides.get(slot_id, slot.default_model)
        mt = model_type(model_id)  # raises on unknown id

        if mt.status == "planned":
            raise RosterError(
                "slot %r wants model %r, but it is planned — not built. "
                "Pick a real or auth-gated model." % (slot_id, model_id)
            )
        if mt.status == "auth-gated" and model_id not in authorized:
            raise RosterError(
                "slot %r wants auth-gated model %r, but Chauncey has not "
                "authorized it (no key in secure storage). Falling back "
                "to %r, or authorize the teacher." % (slot_id, model_id, DEFAULT_MODEL)
            )

        assignments.append(
            SlotAssignment(
                slot_id=slot_id,
                role=slot.role,
                model_id=model_id,
                model_status=mt.status,
                authorized=mt.status == "auth-gated",
                note=(
                    "teacher upgrade advised for %s-stakes seat" % slot.stakes
                    if slot.stakes in ("medium", "high") and model_id == DEFAULT_MODEL
                    else ""
                ),
            )
        )
    return assignments


def roster_receipt(kind: str, assignments: List[SlotAssignment]) -> Dict[str, Any]:
    """Deterministic summary of a resolved roster — receipt-safe."""
    return {
        "kind": kind,
        "slots": [a.to_dict() for a in assignments],
        "model_mix": {
            mid: sum(1 for a in assignments if a.model_id == mid)
            for mid in sorted({a.model_id for a in assignments})
        },
        "all_real_or_authorized": all(
            a.model_status in ("real", "real-weak")
            or (a.model_status == "auth-gated" and a.authorized)
            for a in assignments
        ),
    }


def advise_upgrades(assignments: List[SlotAssignment]) -> List[Dict[str, str]]:
    """For slots still on rules, name the teacher to authorize — advice only,
    never auto-escalation. The customer sees this; the machine never acts
    on it without Chauncey's word."""
    advice = []
    for a in assignments:
        if a.model_id == DEFAULT_MODEL and a.note:
            advice.append(
                {
                    "slot_id": a.slot_id,
                    "role": a.role,
                    "recommend": TEACHER_PREFERENCE[0],
                    "why": "authorize one teacher key to lift %s-stakes seats" % a.note,
                }
            )
    return advice
