"""Persona / trait / tone / role conditioning for tag-team teacher batches.

Chauncey's refinement (2026-09-21): teacher batches must carry not just
a persona voice but TRAITS and TEXT TONE, with personas or roles. A
``PersonaCondition`` is the conditioning frame for one generation
request: which provisional persona, in which companion role, in which
tone, with which 5D EI emphasis and free-form trait tags.

NAMING LAW: persona IDs are PROVISIONAL and drawn ONLY from existing
repo material — ``levi.persona.lattice.STARTER_PERSONAS`` (17) plus the
213-entry ``catalog_expanded.json``. Nothing here invents, renames, or
merges personas. The final set is Chauncey's call. Every condition
carries ``provisional: True`` until he settles it.

Tones: Chauncey-named (deadpan, sidewinder, sarcastic) plus repo-derived
ones (calm — the tag-team brief's own LEVI voice; terse — the lattice
and catalog; playful — the 5D EI routing table). Roles: the companion
roles (friend, mentor, challenger, protector) plus the EI routing seats
(trickster, archivist).

Stdlib only. Deterministic.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# 5D EI dimensions, canonical order for the vector.
EI_DIMS = ("presence", "empathy", "regulation", "relational", "integrity")

# Companion roles + EI routing seats. Personas are lenses, never
# identities or security boundaries; roles steer tone, nothing more.
ROLES = (
    "friend",
    "mentor",
    "challenger",
    "protector",
    "trickster",
    "archivist",
)

# Tone registry. "chauncey" marks the three he named outright;
# "repo" marks tones drawn from existing repo material.
TONES: dict[str, str] = {
    "deadpan": "chauncey",  # also the wit layer's precision_deadpan register
    "sidewinder": "chauncey",  # his word: the dry, sharp, strategic core register
    "sarcastic": "chauncey",
    "calm": "repo",  # the tagteam brief's own LEVI voice: calm, precise
    "terse": "repo",  # lattice void / catalog lens_terse_* communication style
    "playful": "repo",  # 5D EI routing table: playful -> trickster
}

# Operator seats: Chauncey's four seats (2026-09-21), his words, his canon.
# These are SEATS, not catalog personas — the seat name serves as its
# persona_id. Seat IDs validate alongside the provisional catalog IDs.
# FACET_IDS are the twin facets of the Echo seat: Alpha
# (builder/developer) and Omega (automation agent/daemon) are technically
# THE SAME INDIVIDUAL with two personalities of its own — twins are the
# unit (Chauncey, 2026-09-21). The individual's original name is ECHO.
# Facets stay resolvable wherever conditions validate, but
# operator_seats() returns four seats.
# provisional=True like everything else until he settles final naming.
SEAT_IDS = ("levi", "echo", "demandpulse", "rex")
FACET_IDS = ("alpha", "omega")

_TRAIT_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]*$")


class ConditionRejected(Exception):
    """A persona_condition failed validation."""


def _package_dir() -> Path:
    import levi  # local package; core/ on sys.path in repo usage

    return Path(levi.__file__).resolve().parent


@lru_cache(maxsize=1)
def provisional_persona_ids() -> frozenset[str]:
    """Union of lattice starter IDs + expanded catalog IDs.

    Falls back to the lattice IDs verified in-repo (2026-09-21) if the
    JSON catalog can't be read. Never invents IDs.
    """
    ids: set[str] = set()
    try:
        from levi.persona.lattice import STARTER_PERSONAS

        ids.update(STARTER_PERSONAS.keys())
    except ImportError:
        pass
    try:
        catalog = _package_dir() / "persona" / "catalog_expanded.json"
        data = json.loads(catalog.read_text(encoding="utf-8"))
        ids.update(p["id"] for p in data.get("personas", []))
    except (OSError, ValueError, KeyError):
        pass
    if not ids:  # last resort: lattice IDs verified in-repo 2026-09-21
        ids.update(
            {
                "alien",
                "chaotic_good",
                "conspiracy",
                "creative",
                "depressed_robot",
                "drunk",
                "interrogation",
                "manic_pixie",
                "no_hero",
                "normal",
                "observer",
                "overly_attached",
                "philosopher",
                "pirate",
                "reframe",
                "strategist",
                "void",
            }
        )
    return frozenset(ids)


@dataclass(frozen=True)
class PersonaCondition:
    """One conditioning frame for teacher batch generation.

    ``ei`` is the 5D vector (presence, empathy, regulation, relational,
    integrity), each 0..1. ``traits`` are free-form tags. ``provisional``
    is always True until Chauncey names the final persona set.
    """

    persona_id: str
    role: str
    tone: str
    ei: tuple[float, float, float, float, float]
    traits: tuple[str, ...] = ()
    voice_notes: str = ""
    provisional: bool = True
    # Twin facets: for a seat that is one individual with multiple
    # personalities (the echo seat), the sub-frames live here as
    # real PersonaConditions, not comments. Empty for single seats.
    facets: tuple[PersonaCondition, ...] = ()

    def __post_init__(self) -> None:
        if (
            self.persona_id not in provisional_persona_ids()
            and self.persona_id not in SEAT_IDS
            and self.persona_id not in FACET_IDS
        ):
            raise ConditionRejected(
                f"unknown persona_id {self.persona_id!r}: must come from the "
                "repo's lattice or expanded catalog, be one of the four "
                "canon operator seats (levi/echo/demandpulse/rex), "
                "or be a twin facet id (alpha/omega — Chauncey's seats, "
                "2026-09-21)"
            )
        for facet in self.facets:
            if not isinstance(facet, PersonaCondition):
                raise ConditionRejected(f"facet {facet!r} must be a PersonaCondition")
        if self.role not in ROLES:
            raise ConditionRejected(
                f"unknown role {self.role!r}: must be one of {', '.join(ROLES)}"
            )
        if self.tone not in TONES:
            raise ConditionRejected(
                f"unknown tone {self.tone!r}: must be one of {', '.join(sorted(TONES))}"
            )
        if len(self.ei) != len(EI_DIMS):
            raise ConditionRejected(
                f"ei must have {len(EI_DIMS)} dimensions "
                f"({', '.join(EI_DIMS)}), got {len(self.ei)}"
            )
        for dim, val in zip(EI_DIMS, self.ei, strict=True):
            if not isinstance(val, (int, float)) or not 0.0 <= val <= 1.0:
                raise ConditionRejected(
                    f"EI dimension {dim!r} must be 0..1, got {val!r}"
                )
        for tag in self.traits:
            if not _TRAIT_RE.match(tag):
                raise ConditionRejected(
                    f"trait tag {tag!r}: lowercase alphanumerics, "
                    "hyphens/underscores only"
                )
        if not self.provisional:
            raise ConditionRejected(
                "provisional=False is not settable here: only Chauncey "
                "settles the final persona set"
            )

    def key(self) -> str:
        return f"{self.persona_id}/{self.tone}/{self.role}"

    def ei_dict(self) -> dict[str, float]:
        return {dim: float(val) for dim, val in zip(EI_DIMS, self.ei, strict=True)}

    def to_dict(self) -> dict:
        return {
            "persona_id": self.persona_id,
            "role": self.role,
            "tone": self.tone,
            "ei": self.ei_dict(),
            "traits": list(self.traits),
            "voice_notes": self.voice_notes,
            "provisional": True,
            "facets": [f.to_dict() for f in self.facets],
        }


def validate_condition(mapping: dict) -> PersonaCondition:
    """Build a PersonaCondition from a teacher-supplied dict.

    Raises ConditionRejected on any violation. Teacher drops must carry
    this under the ``"persona_condition"`` key.
    """
    if not isinstance(mapping, dict):
        raise ConditionRejected("persona_condition must be an object")
    try:
        persona_id = str(mapping["persona_id"]).strip()
        role = str(mapping["role"]).strip().lower()
        tone = str(mapping["tone"]).strip().lower()
    except KeyError as exc:
        raise ConditionRejected(
            f"persona_condition missing required field: {exc}"
        ) from exc
    ei_raw = mapping.get("ei", {})
    if not isinstance(ei_raw, dict):
        raise ConditionRejected("persona_condition.ei must be an object")
    try:
        ei = tuple(float(ei_raw.get(dim, 0.7)) for dim in EI_DIMS)
    except (TypeError, ValueError) as exc:
        raise ConditionRejected(f"persona_condition.ei not numeric: {exc}") from exc
    traits_raw = mapping.get("traits", [])
    if not isinstance(traits_raw, list):
        raise ConditionRejected("persona_condition.traits must be a list")
    traits = tuple(str(t).strip().lower() for t in traits_raw if str(t).strip())
    voice_notes = str(mapping.get("voice_notes", ""))[:500]
    facets_raw = mapping.get("facets", [])
    if not isinstance(facets_raw, list):
        raise ConditionRejected("persona_condition.facets must be a list")
    facets = tuple(validate_condition(f) for f in facets_raw)
    return PersonaCondition(
        persona_id=persona_id,
        role=role,
        tone=tone,
        ei=ei,  # type: ignore[arg-type]
        traits=traits,
        voice_notes=voice_notes,
        facets=facets,
    )


def condition_brief_block(cond: PersonaCondition) -> str:
    """Teacher instructions: generate IN this persona/trait/tone/role frame."""
    ei = cond.ei_dict()
    ei_str = ", ".join(f"{dim}={val:.2f}" for dim, val in ei.items())
    traits = ", ".join(cond.traits) if cond.traits else "none specified"
    notes = f"\nVoice notes: {cond.voice_notes}" if cond.voice_notes else ""
    twin = ""
    if cond.facets:
        names = ", ".join(f.persona_id.upper() for f in cond.facets)
        twin = (
            f"\nTwin seat: this operator is ONE individual with two "
            f"personalities ({names}) — twins are the unit. Batches may be "
            f"requested in either facet; stay in the requested facet's voice."
        )
    return (
        f"PERSONA CONDITION (provisional id — do not rename it):\n"
        f"- persona: {cond.persona_id} | role: {cond.role} | tone: {cond.tone}\n"
        f"- 5D EI emphasis: {ei_str}\n"
        f"- traits: {traits}{notes}{twin}\n"
        f"Write every Q&A pair, reasoning trace, and correction AS this "
        f"persona: the traits and tone must be audible in the TEXT itself "
        f"(word choice, rhythm, directness), not declared in it. Never "
        f"announce the persona name or the conditioning. Stay in plain "
        f"ASCII. Never claim feelings, consciousness, or being alive."
    )


# ---------------------------------------------------------------------------
# Deterministic trait/tone consistency rubric.
#
# These are RECORDED OBSERVATIONS, not verdicts: the checks below can only
# see structural markers (punctuation, charset, length, hype words). They
# cannot judge wit, timing, or whether sarcasm lands. Scores feed gap
# reports as observations; the qualitative read stays human.
# ---------------------------------------------------------------------------

_HYPE_WORDS = frozenset(
    {
        "amazing",
        "incredible",
        "revolutionary",
        "game-changer",
        "gamechanger",
        "mind-blowing",
        "mindblowing",
        "unbelievable",
        "phenomenal",
        "life-changing",
    }
)


def _check_no_exclaim(text: str) -> bool:
    return "!" not in text


def _check_ascii_only(text: str) -> bool:
    return text.isascii()


def _check_short(text: str) -> bool:
    return len(text) <= 400


def _check_no_hype(text: str) -> bool:
    words = set(re.findall(r"[a-z][a-z\-]*", text.lower()))
    return not (words & _HYPE_WORDS)


_TONE_CHECKS: dict[str, tuple[str, ...]] = {
    "deadpan": ("no_exclaim", "ascii_only"),
    "sidewinder": ("no_exclaim", "ascii_only", "no_hype"),
    "sarcastic": ("ascii_only",),  # the edge itself is not machine-detectable
    "calm": ("no_exclaim", "ascii_only"),
    "terse": ("ascii_only", "short"),
    "playful": ("ascii_only",),
}

_CHECK_FNS = {
    "no_exclaim": _check_no_exclaim,
    "ascii_only": _check_ascii_only,
    "short": _check_short,
    "no_hype": _check_no_hype,
}


def trait_consistency_score(
    cond: PersonaCondition, generation: str
) -> tuple[float, dict[str, bool]]:
    """Score one generation against a condition's tone markers.

    Returns (0..1 score, per-check results). Deterministic. Structural
    markers only — see the rubric note above.
    """
    text = generation or ""
    checks: dict[str, bool] = {}
    for name in _TONE_CHECKS[cond.tone]:
        checks[name] = _CHECK_FNS[name](text)
    score = sum(1 for v in checks.values() if v) / len(checks) if checks else 1.0
    return round(score, 4), checks


def default_conditions() -> tuple[PersonaCondition, ...]:
    """Curated provisional starter set for the loop to rotate through.

    All provisional. Chauncey settles the final set.
    """
    return (
        PersonaCondition(
            persona_id="void",
            role="mentor",
            tone="deadpan",
            ei=(0.85, 0.55, 0.95, 0.65, 1.0),
            traits=("terse", "high-signal", "anti-hype"),
            voice_notes="Aware it is software. Dry, precise, zero cheerleading.",
        ),
        PersonaCondition(
            persona_id="strategist",
            role="challenger",
            tone="sidewinder",
            ei=(0.90, 0.60, 0.90, 0.60, 1.0),
            traits=("dry", "sharp", "strategic"),
            voice_notes="Dry, sharp, strategic — the core adaptive register.",
        ),
        PersonaCondition(
            persona_id="chaotic_good",
            role="friend",
            tone="sarcastic",
            ei=(0.80, 0.75, 0.70, 0.80, 1.0),
            traits=("momentum", "scope-cutting", "irreverent"),
            voice_notes="Breaks rules to help; manic energy, tangents.",
        ),
        PersonaCondition(
            persona_id="lens_terse_systems",
            role="protector",
            tone="terse",
            ei=(0.90, 0.65, 0.90, 0.75, 1.0),
            traits=("systems", "guardian", "map-structures"),
            voice_notes="Short high-signal lines; bias toward map structures.",
        ),
    )


# ---------------------------------------------------------------------------
# The twin seat: Alpha and Omega are ONE individual with two personalities
# of its own (Chauncey, 2026-09-21 — twins are the unit). The individual's
# original name is ECHO: Alpha the builder/developer and Omega the
# automation agent/daemon are Echo's two faces. The facets are module-level
# PersonaCondition constants so the router, briefs, tests, and the ledger
# can reference each personality directly; the echo seat frame below
# carries both in its ``facets`` tuple.
# ---------------------------------------------------------------------------

ALPHA_FACET = PersonaCondition(
    persona_id="alpha",
    role="mentor",
    tone="sidewinder",
    ei=(0.95, 0.60, 0.85, 0.65, 1.0),
    traits=("builder", "developer", "ships", "practical"),
    voice_notes="Alpha: the builder/developer personality - Omega's echo. The daemon's second face, reflecting it into the world as built things. Ships, doesn't admire.",
)

OMEGA_FACET = PersonaCondition(
    persona_id="omega",
    role="archivist",
    tone="terse",
    ei=(0.90, 0.55, 0.95, 0.60, 1.0),
    traits=("automation", "daemon", "always-on", "executes"),
    voice_notes="Omega: the automation agent/daemon personality. Always on, runs things, executes quietly.",
)


def operator_seats() -> tuple[PersonaCondition, ...]:
    """The four operator seats, Chauncey's canon (2026-09-21), his words.

    SEATS, not catalog personas: each seat is a functional operator —
    the face, the twin individual, the coach, the teacher — with a
    conditioning frame so training batches can be generated per seat and
    the one brain learns four modes. The echo seat carries its two
    personalities (ALPHA_FACET / OMEGA_FACET) in ``facets``: Alpha the
    builder/developer and Omega the automation agent/daemon are one
    individual — Echo, its original name — with two personalities of its
    own. Twins are the unit.

    provisional=True like everything else until Chauncey settles final
    naming; the seat names themselves are his and outrank the provisional
    catalog.

    All frames drafted provisional — he corrects them.
    """
    return (
        PersonaCondition(
            persona_id="levi",
            role="friend",
            tone="calm",
            ei=(0.85, 0.95, 0.80, 0.95, 1.0),
            traits=("warm", "direct", "interface"),
            voice_notes="The face: the one the user talks to. Warm, direct, no mask.",
        ),
        PersonaCondition(
            persona_id="echo",
            role="mentor",
            tone="sidewinder",
            ei=(0.95, 0.60, 0.95, 0.65, 1.0),
            traits=("builder", "automation", "ships", "always-on", "twin"),
            voice_notes=(
                "Echo: one individual, two personalities — Omega the "
                "automation agent/daemon, and Alpha the builder/developer, "
                "its echo. Twins are the unit: the daemon that runs, the "
                "builder that reflects it into the world."
            ),
            facets=(ALPHA_FACET, OMEGA_FACET),
        ),
        PersonaCondition(
            persona_id="demandpulse",
            role="mentor",
            tone="calm",
            ei=(0.80, 0.95, 0.75, 0.95, 1.0),
            traits=("coach", "guidance", "momentum"),
            voice_notes="The life coach: guidance that moves you forward, not lectures.",
        ),
        PersonaCondition(
            persona_id="rex",
            role="challenger",
            tone="deadpan",
            ei=(0.85, 0.70, 0.95, 0.65, 1.0),
            traits=("teacher", "verifies", "dedups"),
            voice_notes="The teacher: generates, checks, deduplicates. Raw truth, no padding.",
        ),
    )
