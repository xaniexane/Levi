"""Historic-canon engine mapping: Chauncey's Omega engines -> Legion pool skills.

SOURCE STATUS — read this first: the ENGINE LIST is HISTORIC CANON per
Chauncey's 2026-09-22 ruling ("Historic cannon"): the engine renderings,
placement maps, the 4×4× structure sheet, and the individual engine
diagrams are his Omega Platform material, canonized as historic canon
that day. The MAPPING JUDGMENTS in this module — mapped/partial/unmapped,
the how-notes, the missing-notes — are OUR provisional analysis, NOT
canon. This module is a mapping layer only: engines on one side, pool
skills on the other, honest links between them. Do NOT write our mapping
judgments into canon files.

LAW-GUARD-PROVE — the engine-map invariants, declared first, enforced
below, proved by tests/test_legion_engine_map.py (never claimed beyond
what the tests check):

E1. every one of the 32 unique engines appears in the map exactly once;
E2. every mapped skill id is a real pool skill id (validated at import —
    a bad id fails loudly, never silently);
E3. unmapped engines are explicitly flagged with a `missing` note —
    never absent, never silently dropped;
E4. coverage_report() numbers are computed from the data, never
    hand-written, and always sum correctly.

HONESTY NOTES:
- A `partial` link means the skill serves a slice of the engine's
  function, not the whole thing — the `how` text says which slice.
- `covered_elsewhere` means the capability exists in the repo but
  outside the pool by design (linked, never duplicated).
- An unmapped engine is a FINDING, not a failure.

NAMING: this module's name, the partial-call judgments, and the
how/missing notes are PROVISIONAL and await Chauncey's word. The ENGINE
DISPLAY NAMES are historic canon (2026-09-22).
"""

from __future__ import annotations

from typing import Any, Dict, List

from .definitions import SKILL_DEFINITIONS

ENGINE_INVARIANTS = (
    "every one of the 32 unique engines appears in the map exactly once",
    "every mapped skill id is a real pool skill id",
    "unmapped engines are explicitly flagged with a missing note, never absent",
    "coverage_report numbers are computed from the data and sum correctly",
)

# Source status of the ENGINE LIST only (the mapping judgments in ENGINE_MAP
# are our provisional analysis, not canon).
ENGINE_SOURCE_STATUS = "historic canon per Chauncey's 2026-09-22 ruling"

# Engine tensor spec — recorded VERBATIM as Chauncey's canon (2026-09-22):
# the 32 engines are 32×64×128 — 32 engines, each a 64×128 matrix,
# 262,144 values total.
# SEMANTICS PENDING: what the 64 and 128 axes represent is his to define.
ENGINE_TENSOR_SHAPE = (32, 64, 128)
ENGINE_TENSOR_TOTAL = 32 * 64 * 128

# One entry per engine. `links` = [{"skill": <real pool id>, "how": <one line>,
# "partial": bool}]. Unmapped entries carry `unmapped: True` + `missing`.
ENGINE_MAP: List[Dict[str, Any]] = [
    # ------------------------------------------------------------------
    # SET 1 — Identity Dimensions
    # ------------------------------------------------------------------
    {
        "engine": "Canon Engine",
        "sets": ["SET 1 — Identity Dimensions"],
        "function": "defines truth, order, and non-physical law",
        "links": [],
        "unmapped": True,
        "missing": (
            "no pool skill defines or maintains non-physical truth/law — "
            "the law skills cover human law (statutes, contracts, "
            "compliance), which is a different thing"
        ),
    },
    {
        "engine": "Founder Alignment Engine",
        "sets": ["SET 1 — Identity Dimensions"],
        "function": "aligns all behavior to founder intent",
        "links": [
            {
                "skill": "legion_goals",
                "how": "founder intent recorded as trackable goals; "
                "alignment means acting toward them",
                "partial": False,
            },
        ],
        "unmapped": False,
    },
    {
        "engine": "System Identity Engine",
        "sets": ["SET 1 — Identity Dimensions"],
        "function": "maintains the platform's internal sense of self",
        "links": [],
        "unmapped": True,
        "missing": (
            "nothing in the pool models or maintains platform selfhood — "
            "memory pruning (forget) curates content, not identity"
        ),
    },
    {
        "engine": "User Identity Engine",
        "sets": ["SET 1 — Identity Dimensions"],
        "function": "manages identity relationships across worlds",
        "links": [],
        "unmapped": True,
        "missing": (
            "no pool skill models user identity or cross-world identity relationships"
        ),
    },
    # ------------------------------------------------------------------
    # SET 2 — Logic Dimensions
    # ------------------------------------------------------------------
    {
        "engine": "Knowledge Engine",
        "sets": ["SET 2 — Logic Dimensions"],
        "function": "stores and structures information",
        "links": [
            {
                "skill": "legion_deep_research",
                "how": "builds structured knowledge from multi-source research",
                "partial": False,
            },
            {
                "skill": "legion_media_library",
                "how": "searchable store of the user's own media",
                "partial": False,
            },
            {
                "skill": "legion_phone_files",
                "how": "searchable index of device files",
                "partial": False,
            },
        ],
        "unmapped": False,
    },
    {
        "engine": "Reasoning Engine",
        "sets": ["SET 2 — Logic Dimensions"],
        "function": "performs inference and decision logic",
        "links": [
            {
                "skill": "legion_design_thinker",
                "how": "structured reasoning frameworks: define, ideate, decide",
                "partial": False,
            },
            {
                "skill": "legion_thought_reframing",
                "how": "evidence-check inference applied to beliefs",
                "partial": False,
            },
            {
                "skill": "legion_competitive_analysis",
                "how": "comparative inference over market data",
                "partial": False,
            },
        ],
        "unmapped": False,
    },
    {
        "engine": "Clarification Protocol",
        "sets": ["SET 2 — Logic Dimensions"],
        "function": "resolves ambiguity and uncertainty",
        "links": [],
        "unmapped": True,
        "missing": (
            "no pool skill performs live structured clarification — "
            "design_thinker's define phase frames problems but does not "
            "run an ambiguity-resolution protocol"
        ),
    },
    {
        "engine": "Structural Logic Engine",
        "sets": ["SET 2 — Logic Dimensions"],
        "function": "maintains internal coherence and rule-consistency",
        "links": [
            {
                "skill": "legion_compliance_checklist",
                "how": "checks a system against its own rules; gap scoring "
                "is coherence measurement",
                "partial": False,
            },
            {
                "skill": "legion_replit_migration_guardrails",
                "how": "guardrails that refuse rule-violating moves outright",
                "partial": False,
            },
        ],
        "unmapped": False,
    },
    # ------------------------------------------------------------------
    # SET 3 — Emotion Dimensions
    # ------------------------------------------------------------------
    {
        "engine": "Emotional Engine",
        "sets": ["SET 3 — Emotion Dimensions"],
        "function": "interprets emotional context",
        "links": [
            {
                "skill": "legion_burnout_gauge",
                "how": "reads emotional/energy signals as state input",
                "partial": False,
            },
            {
                "skill": "legion_mindfulness_practice",
                "how": "protocols selected by the emotional state at hand",
                "partial": False,
            },
        ],
        "unmapped": False,
    },
    {
        "engine": "Tone Engine",
        "sets": ["SET 3 — Emotion Dimensions"],
        "function": "modulates expression and delivery",
        "links": [
            {
                "skill": "legion_action_react",
                "how": "pointed-but-deniable delivery, calibrated to the moment",
                "partial": False,
            },
            {
                "skill": "legion_tts",
                "how": "voice delivery: speaker, pacing, emphasis",
                "partial": False,
            },
        ],
        "unmapped": False,
    },
    {
        "engine": "Humor Engine",
        "sets": ["SET 3 — Emotion Dimensions"],
        "function": "handles levity, timing, and social ease",
        "links": [
            {
                "skill": "legion_action_react",
                "how": "comic timing rides along in sideways responses; no "
                "dedicated humor skill — partial coverage",
                "partial": True,
            },
        ],
        "unmapped": False,
    },
    {
        "engine": "Context Engine",
        "sets": ["SET 3 — Emotion Dimensions"],
        "function": "tracks situational meaning across worlds",
        "links": [
            {
                "skill": "legion_action_react",
                "how": "reads the situation at hand before reacting — "
                "situation reading is the skill's first move",
                "partial": False,
            },
        ],
        "unmapped": False,
    },
    # ------------------------------------------------------------------
    # SET 4 — Action Dimensions
    # ------------------------------------------------------------------
    {
        "engine": "Automation Engine",
        "sets": ["SET 4 — Action Dimensions", "CORE ENGINE STACK"],
        "function": "sequences tasks and routines",
        "note": (
            "dual-listed in the source (SET 4 and CORE STACK) — mapped once. "
            "Canon internals (Automation Engine diagram, 2026-09-22): "
            "Workflow Processor → Logic Module → Routine Generator, with "
            "Real-Time Adaptation feeding an Execution Hub (digital actions, "
            "physical tasks, opportunity paths, feedback loop); multi-step "
            "sequences, conditional logic, real-time routing, stress-aware "
            "automation"
        ),
        "links": [
            {
                "skill": "legion_ai_secretary",
                "how": "schedules, agendas, routines — adjacent to sequencing; "
                "not a workflow runner — partial coverage",
                "partial": True,
            },
        ],
        "unmapped": False,
    },
    {
        "engine": "Task Engine",
        "sets": ["SET 4 — Action Dimensions"],
        "function": "handles discrete actions and steps",
        "links": [
            {
                "skill": "legion_action_react",
                "how": "each reaction is one discrete, calibrated action",
                "partial": False,
            },
        ],
        "unmapped": False,
    },
    {
        "engine": "Physical Integration Engine",
        "sets": ["SET 4 — Action Dimensions"],
        "function": "bridges digital → physical",
        "links": [],
        "unmapped": True,
        "missing": (
            "no pool skill crosses digital→physical — no actuators, "
            "devices, or physical-world bridges exist in the pool"
        ),
    },
    {
        "engine": "Execution Engine",
        "sets": ["SET 4 — Action Dimensions"],
        "function": "performs real-world outputs and effects",
        "links": [
            {
                "skill": "legion_action_react",
                "how": "carries the reaction out — the doing half of read-then-react",
                "partial": False,
            },
        ],
        "unmapped": False,
    },
    # ------------------------------------------------------------------
    # SET 5 — Negative / Shadow Dimensions
    # ------------------------------------------------------------------
    {
        "engine": "Shadow Engine",
        "sets": ["SET 5 — Negative / Shadow Dimensions"],
        "function": "handles hidden, suppressed, or inverse signals",
        "links": [
            {
                "skill": "legion_terms_breakdown",
                "how": "surfaces hidden hostile clauses buried in ToS — a "
                "narrow slice of suppressed-signal work — partial coverage",
                "partial": True,
            },
        ],
        "unmapped": False,
    },
    {
        "engine": "Anti-Structure Engine",
        "sets": ["SET 5 — Negative / Shadow Dimensions"],
        "function": "detects collapse, inversion, or corruption",
        "links": [
            {
                "skill": "legion_burnout_gauge",
                "how": "detects collapse signals in human workload/energy; "
                "not structural or systemic collapse — partial coverage",
                "partial": True,
            },
        ],
        "unmapped": False,
    },
    {
        "engine": "Paradox Engine",
        "sets": ["SET 5 — Negative / Shadow Dimensions"],
        "function": "resolves contradictions and impossible states",
        "links": [
            {
                "skill": "legion_thought_reframing",
                "how": "resolves contradictory cognitions via evidence-check; "
                "not logical paradoxes or impossible system states — "
                "partial coverage",
                "partial": True,
            },
        ],
        "unmapped": False,
    },
    {
        "engine": "Depth Engine",
        "sets": ["SET 5 — Negative / Shadow Dimensions"],
        "function": "manages complexity, recursion, and deep-state layers",
        "links": [],
        "unmapped": True,
        "missing": (
            "no pool skill models recursive deep-state layers or manages "
            "layered complexity"
        ),
    },
    # ------------------------------------------------------------------
    # DIMENSION 21 — The Single Canon Dimension
    # ------------------------------------------------------------------
    {
        "engine": "Canon Plane",
        "sets": ["DIMENSION 21 — The Single Canon Dimension"],
        "function": (
            "the law layer, identity anchor, and non-physical truth — sits "
            "above, below, and through all 20; never physical; never collapses"
        ),
        "links": [],
        "unmapped": True,
        "missing": (
            "by definition never physical — no skill can implement it, only "
            "point at it; nothing in the pool serves as a law/identity "
            "anchor layer"
        ),
    },
    # ------------------------------------------------------------------
    # CORE ENGINE STACK
    # ------------------------------------------------------------------
    {
        "engine": "Teaching Engine",
        "sets": ["CORE ENGINE STACK"],
        "function": "teaches and transfers capability",
        "links": [
            {
                "skill": "legion_flashcard_generator",
                "how": "study guides, quizzes, drills — direct teaching artifacts",
                "partial": False,
            },
            {
                "skill": "legion_interview_prep",
                "how": "mock interviews and behavioral coaching",
                "partial": False,
            },
        ],
        "unmapped": False,
    },
    {
        "engine": "Assistance Engine",
        "sets": ["CORE ENGINE STACK"],
        "function": "assists the user directly",
        "links": [
            {
                "skill": "legion_ai_secretary",
                "how": "drafts, schedules, organizes — the assistance skill, literally",
                "partial": False,
            },
        ],
        "unmapped": False,
    },
    {
        "engine": "Opportunity Engine",
        "sets": ["CORE ENGINE STACK"],
        "function": "finds and develops opportunities",
        "links": [
            {
                "skill": "legion_ai_sdr",
                "how": "finds B2B companies and qualifies leads",
                "partial": False,
            },
            {
                "skill": "legion_business_builder",
                "how": "turns an idea into an opportunity vehicle",
                "partial": False,
            },
        ],
        "unmapped": False,
    },
    {
        "engine": "Demandpulse Engine",
        "sets": ["CORE ENGINE STACK"],
        "function": "DemandPulse scanning and scoring",
        "links": [
            {
                "skill": "legion_competitive_analysis",
                "how": "market scanning and analysis adjacent; not the "
                "scan→score→surface loop — partial coverage",
                "partial": True,
            },
        ],
        "unmapped": False,
    },
    {
        "engine": "Internal Engine",
        "sets": ["CORE ENGINE STACK"],
        "function": (
            "the platform's inner core — canon diagram (2026-09-22) centers "
            "an 'INNER RESILIENCE CORE'; surrounding node labels illegible at "
            "render resolution"
        ),
        "links": [],
        "unmapped": True,
        "missing": (
            "canon gives it an inner-resilience-core diagram, but no pool "
            "skill models or maintains the platform's inner state or "
            "resilience — still unmapped; full functional definition still "
            "needs Chauncey's word"
        ),
    },
    {
        "engine": "World Engine",
        "sets": ["CORE ENGINE STACK"],
        "function": (
            "multi-reality navigation across six worlds — physical (real "
            "space), digital (virtual space), AR (augmented space), internal "
            "(mental space), social (relational space), opportunity "
            "(potential space) — via a Reality Synchronizer and an Identity "
            "Core (canon World Engine diagrams, 2026-09-22)"
        ),
        "links": [],
        "unmapped": True,
        "missing": (
            "the definition is canon, the coverage is absent — no pool skill "
            "performs multi-reality navigation or maintains a reality "
            "synchronizer / identity core across worlds"
        ),
    },
    {
        "engine": "Data Engine",
        "sets": ["CORE ENGINE STACK"],
        "function": "data handling and transformation",
        "links": [
            {
                "skill": "legion_excel_generator",
                "how": "structured data in spreadsheets, formulas, models",
                "partial": False,
            },
            {
                "skill": "legion_file_converter",
                "how": "transforms data across formats",
                "partial": False,
            },
        ],
        "unmapped": False,
    },
    {
        "engine": "Communication Engine",
        "sets": ["CORE ENGINE STACK"],
        "function": "handles communication",
        "links": [
            {
                "skill": "legion_gmail",
                "how": "email: search, read, draft, send",
                "partial": False,
            },
            {
                "skill": "legion_messenger_read",
                "how": "read/search Messenger conversations",
                "partial": False,
            },
            {
                "skill": "legion_tts",
                "how": "spoken delivery of text",
                "partial": False,
            },
        ],
        "unmapped": False,
    },
    {
        "engine": "Creator Engine",
        "sets": ["CORE ENGINE STACK"],
        "function": "creates content and artifacts",
        "links": [
            {
                "skill": "legion_content_machine",
                "how": "posts, newsletters, marketing content",
                "partial": False,
            },
            {
                "skill": "legion_ad_creative",
                "how": "static ad creatives",
                "partial": False,
            },
            {
                "skill": "legion_podcast_generator",
                "how": "podcast scripts plus produced audio",
                "partial": False,
            },
        ],
        "unmapped": False,
    },
    {
        "engine": "Security Engine",
        "sets": ["CORE ENGINE STACK"],
        "function": "security and protection",
        "links": [],
        "unmapped": True,
        "covered_elsewhere": (
            "core/levi/skill/playbooks/cyber — 823 defensive blue-team "
            "playbooks live there; outside the pool by design, linked not "
            "duplicated"
        ),
        "missing": (
            "no pool skill covers security — deliberately: the capability "
            "lives at core/levi/skill/playbooks/cyber (see covered_elsewhere)"
        ),
    },
    {
        "engine": "Successor Engine",
        "sets": ["CORE ENGINE STACK"],
        "function": "(no described function in the source)",
        "links": [],
        "unmapped": True,
        "missing": (
            "no pool skill covers succession, inheritance, or handoff of authority"
        ),
    },
]


# -- fail-loud validation at import (invariants E1–E3) ------------------

_REAL_SKILL_IDS = {d["id"] for d in SKILL_DEFINITIONS}


def _validate() -> None:
    names = [e["engine"] for e in ENGINE_MAP]
    if len(names) != len(set(names)):
        dupes = sorted({n for n in names if names.count(n) > 1})
        raise ValueError(f"engine_map: duplicate engines: {dupes}")
    for entry in ENGINE_MAP:
        if entry["unmapped"]:
            if not entry.get("missing"):
                raise ValueError(
                    f"engine_map: unmapped engine {entry['engine']!r} "
                    "has no `missing` note — never silently drop an engine"
                )
        else:
            if not entry["links"]:
                raise ValueError(
                    f"engine_map: engine {entry['engine']!r} is marked mapped "
                    "but has no links"
                )
        for link in entry["links"]:
            if link["skill"] not in _REAL_SKILL_IDS:
                raise ValueError(
                    f"engine_map: engine {entry['engine']!r} links unknown "
                    f"skill id {link['skill']!r}"
                )


_validate()


# -- API ----------------------------------------------------------------


def engines_for(skill_id: str) -> List[str]:
    """Engine display names the skill serves. Fails loudly on unknown ids."""
    if skill_id not in _REAL_SKILL_IDS:
        raise ValueError(f"engines_for: unknown skill id {skill_id!r}")
    return sorted(
        e["engine"]
        for e in ENGINE_MAP
        for link in e["links"]
        if link["skill"] == skill_id
    )


def skills_for_engine(engine_name: str) -> List[Dict[str, Any]]:
    """The skill links serving one engine. Fails loudly on unknown engines."""
    for entry in ENGINE_MAP:
        if entry["engine"] == engine_name:
            return [
                {
                    "skill": link["skill"],
                    "how": link["how"],
                    "partial": link["partial"],
                }
                for link in entry["links"]
            ]
    raise ValueError(f"skills_for_engine: unknown engine {engine_name!r}")


def unmapped_engines() -> List[Dict[str, Any]]:
    """Every engine with no pool skill — explicitly flagged, never absent."""
    return [
        {
            "engine": e["engine"],
            "sets": list(e["sets"]),
            "function": e["function"],
            "missing": e["missing"],
            **(
                {"covered_elsewhere": e["covered_elsewhere"]}
                if e.get("covered_elsewhere")
                else {}
            ),
        }
        for e in ENGINE_MAP
        if e["unmapped"]
    ]


def coverage_report() -> Dict[str, Any]:
    """Counts computed from the data, never hand-written (invariant E4)."""
    mapped = [e for e in ENGINE_MAP if not e["unmapped"]]
    unmapped = [e for e in ENGINE_MAP if e["unmapped"]]
    partial_only = [
        e for e in mapped if e["links"] and all(link["partial"] for link in e["links"])
    ]
    serving = sorted({link["skill"] for e in mapped for link in e["links"]})
    zero = sorted(_REAL_SKILL_IDS - set(serving))
    return {
        "total_engines": len(ENGINE_MAP),
        "mapped": len(mapped),
        "unmapped": len(unmapped),
        "partial_only": len(partial_only),
        "partial_only_engines": sorted(e["engine"] for e in partial_only),
        "skills_serving_engines": len(serving),
        "skills_serving_zero_engines": zero,
    }
