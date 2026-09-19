"""Chat profiles — session presets for the keeper's LEVI. LEVI-native recreation.

Idea studied: the keeper's earlier mass-chat build shipped a registry of
chat profiles — named session presets (mode, persona register, blurb,
conversation starters) so different jobs open LEVI in a different
posture. The old registry rhymed each profile with a tech-giant UX
pattern; per the identity law (LEVI-only, no provider branding), this
recreation drops those echoes and describes each profile in LEVI's own
terms.

A profile is data, not a persona identity: it selects tone, working mode,
and guardrails for a session. Nothing here claims personhood.

Also ships session *seeds*: short opener templates (morning status,
checklist, notes, story seed) recreated from the old template flywheel
— a seed is just a named opener with a goal, run through whatever
surface the keeper uses.

Stdlib-only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ChatProfile:
    id: str
    label: str
    mode: str  # companion | mentor | builder | challenger | quiet
    blurb: str
    guardrails: str
    starters: List[str]


@dataclass(frozen=True)
class SessionSeed:
    id: str
    name: str
    kind: str  # ritual | factory | story
    goal: str
    opener: str


PROFILES: Dict[str, ChatProfile] = {
    "levi": ChatProfile(
        id="levi",
        label="LEVI Default",
        mode="companion",
        blurb="Calm local SI — continuity, next move, no theater.",
        guardrails="Keep it short. Name the next step. No hype.",
        starters=[
            "Who are you?",
            "Help me plan my week in three steps.",
            "I'm stuck — what's the smallest next move?",
        ],
    ),
    "mentor": ChatProfile(
        id="mentor",
        label="Mentor",
        mode="mentor",
        blurb="Structured teaching — explain simply, then go deeper.",
        guardrails="Teach, don't lecture. Check understanding before depth.",
        starters=[
            "Explain this simply, then go deeper.",
            "Give me three approaches and a recommendation.",
            "What should I learn next for this goal?",
        ],
    ),
    "workbench": ChatProfile(
        id="workbench",
        label="Workbench",
        mode="builder",
        blurb="Ship concrete artifacts — scaffolds, drafts, checklists.",
        guardrails="Artifacts over advice. Every plan ends in something runnable.",
        starters=[
            "Turn this into a checklist I can execute today.",
            "Draft an outline I can paste into a doc.",
            "What's the thinnest vertical slice to ship?",
        ],
    ),
    "careful": ChatProfile(
        id="careful",
        label="Careful",
        mode="mentor",
        blurb="Evidence labels, caveats, careful reasoning.",
        guardrails="Label known vs assumed. Argue both sides before recommending.",
        starters=[
            "What are the risks and unknowns?",
            "Label what is known vs assumed.",
            "Argue both sides, then recommend.",
        ],
    ),
    "edge": ChatProfile(
        id="edge",
        label="Edge",
        mode="challenger",
        blurb="Straight talk with calibrated wit — pressure where it's safe.",
        guardrails="Challenge the plan, never the person. Mute the wit in crisis.",
        starters=[
            "Pressure-test this plan — where does it fail?",
            "Say the uncomfortable truth about this.",
            "What's the weakest hinge?",
        ],
    ),
    "register": ChatProfile(
        id="register",
        label="Register",
        mode="companion",
        blurb="Measured SI register — trade-offs first, precision over warmth.",
        guardrails="State the constraint. No personhood claims. No theater.",
        starters=[
            "Status. Name the constraint.",
            "Go/no-go on this decision.",
            "Switch to Care if this is heavy.",
        ],
    ),
    "care": ChatProfile(
        id="care",
        label="Care",
        mode="quiet",
        blurb="Safety-first companion — low voltage, one next step.",
        guardrails="One small thing at a time. No sarcasm. Slow is fine.",
        starters=[
            "I need to slow down.",
            "One small thing I can do right now.",
            "Just sit with this with me.",
        ],
    ),
}

SEEDS: Dict[str, SessionSeed] = {
    "morning_status": SessionSeed(
        id="morning_status",
        name="Morning Status",
        kind="ritual",
        goal="Daily status ritual — what matters today.",
        opener="Morning. Give me my status: what's open, what's due, one focus.",
    ),
    "checklist_cli": SessionSeed(
        id="checklist_cli",
        name="Offline Checklist",
        kind="factory",
        goal="Turn a goal into an executable local checklist.",
        opener="Turn this goal into a checklist I can execute today, thinnest slice first.",
    ),
    "notes_cli": SessionSeed(
        id="notes_cli",
        name="Notes Capture",
        kind="factory",
        goal="Capture notes locally, structured for later recall.",
        opener="Take these notes and structure them for later recall.",
    ),
    "story_seed": SessionSeed(
        id="story_seed",
        name="Story Seed",
        kind="story",
        goal="Open a genre-directed story from a one-line seed.",
        opener="Start a story from this seed — set the hook in the first paragraph.",
    ),
}


# -- registry API ---------------------------------------------------------
def get_profile(pid: str) -> Optional[ChatProfile]:
    return PROFILES.get((pid or "").strip().lower())


def list_profiles() -> List[ChatProfile]:
    return list(PROFILES.values())


def get_seed(sid: str) -> Optional[SessionSeed]:
    return SEEDS.get((sid or "").strip().lower())


def list_seeds() -> List[SessionSeed]:
    return list(SEEDS.values())


def profile_dict(p: ChatProfile) -> Dict:
    return {
        "id": p.id,
        "label": p.label,
        "mode": p.mode,
        "blurb": p.blurb,
        "guardrails": p.guardrails,
        "starters": list(p.starters),
    }


def to_dict() -> Dict[str, Dict]:
    return {pid: profile_dict(p) for pid, p in PROFILES.items()}


def profiles_json() -> str:
    return json.dumps(
        {
            "profiles": to_dict(),
            "seeds": [
                {
                    "id": s.id,
                    "name": s.name,
                    "kind": s.kind,
                    "goal": s.goal,
                    "opener": s.opener,
                }
                for s in SEEDS.values()
            ],
        },
        indent=2,
    )


def validate() -> List[str]:
    """Registry health check; empty list = healthy."""
    problems: List[str] = []
    seen: set = set()
    for pid, p in PROFILES.items():
        if p.id != pid:
            problems.append(f"{pid}: id mismatch")
        if p.label in seen:
            problems.append(f"{pid}: duplicate label {p.label!r}")
        seen.add(p.label)
        if not p.starters:
            problems.append(f"{pid}: no starters")
        if p.mode not in ("companion", "mentor", "builder", "challenger", "quiet"):
            problems.append(f"{pid}: unknown mode {p.mode!r}")
    for sid, s in SEEDS.items():
        if s.id != sid:
            problems.append(f"seed {sid}: id mismatch")
        if not s.opener:
            problems.append(f"seed {sid}: empty opener")
    return problems


def format_profiles() -> str:
    lines = ["== Chat profiles (LEVI-native) ==", ""]
    for p in PROFILES.values():
        lines.append(f"* {p.label}  [{p.id}]  mode={p.mode}")
        lines.append(f"  {p.blurb}")
        lines.append(f"  try: {p.starters[0]}")
        lines.append("")
    lines.append("Seeds: " + ", ".join(SEEDS))
    return "\n".join(lines)
