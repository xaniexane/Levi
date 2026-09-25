"""LEVI sequential solver + cognitive modes.

Original LEVI-native implementation. Concept adapted from the Levi-ai
Stage-1 lineage (source-sync entry ``levi-ai``); no source text copied.

BINDING LAW (from the LEVI charter): cognitive modes and personas are
UX/routing lenses ONLY. They affect presentation — never facts, safety
checks, permissions, or integrity. This module enforces that by
construction: :class:`CognitiveMode` only ever touches text *styling*;
every solver step and every mode switch is a pure function of its
inputs with no access to policy, memory, or tools.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Sequence, Tuple

# ---------------------------------------------------------------------------
# 7-step sequential solver
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SolverStep:
    id: str
    title: str
    prompt: str


SOLVER_STEPS: Tuple[SolverStep, ...] = (
    SolverStep(
        "define",
        "DEFINE",
        "State the goal in one clear sentence. List constraints, knowns, unknowns, and success criteria.",
    ),
    SolverStep(
        "decompose",
        "DECOMPOSE",
        "Break the goal into ordered sub-problems. Note dependencies between them.",
    ),
    SolverStep(
        "plan",
        "PLAN",
        "Choose the sequence of steps and the tools or knowledge each step needs.",
    ),
    SolverStep(
        "execute",
        "EXECUTE",
        "Perform the current step only. Record the actual result, not the hoped-for one.",
    ),
    SolverStep(
        "check",
        "CHECK",
        "Does this step's result match expectation? If not, diagnose this step before continuing.",
    ),
    SolverStep(
        "integrate",
        "INTEGRATE",
        "Combine the verified sub-results and check them against the original goal.",
    ),
    SolverStep(
        "reflect",
        "REFLECT",
        "What worked, what failed, and what should be remembered for next time.",
    ),
)

_SOLVE_RE = re.compile(
    r"step[-\s]?by[-\s]?step|walk me through|solve this|"
    r"how (do|would|can) i|break it down|sequential|show (me )?the steps",
    re.I,
)


def wants_solve(text: str) -> bool:
    """Detect whether the user is asking for step-by-step solving."""
    return bool(_SOLVE_RE.search(str(text or "")))


def get_template() -> List[SolverStep]:
    """Return a copy of the 7-step template."""
    return list(SOLVER_STEPS)


def solve(
    problem: str,
    mode: str = "normal",
    related: Sequence[Tuple[str, str]] = (),
) -> str:
    """Build a guided sequential response for ``problem``.

    ``mode`` selects a presentation lens (see :class:`CognitiveMode`);
    ``related`` is an optional sequence of ``(serial, title)`` knowledge
    references. Pure function — no I/O, no policy access.
    """
    problem = str(problem or "")[:500]
    if not problem.strip():
        raise ValueError("solve: problem must not be empty")
    lens = CognitiveMode.coerce(mode)
    lines = ["## Sequential Problem Solving", f"**Problem:** {problem}", ""]
    if lens is CognitiveMode.ADHD:
        lines.append(
            "_ADHD lens: short steps, one action at a time, checkpoints, low clutter._"
        )
        lines.append("")
        for i, step in enumerate(SOLVER_STEPS, 1):
            lines += [
                f"**{i}. {step.title}**",
                f"→ {step.prompt.split('.')[0]}.",
                "[ ] Done? Then next.",
                "",
            ]
    elif lens is CognitiveMode.DREAM:
        lines.append(
            "_Dream lens: explore alternate paths while staying grounded in the 7-step loop._"
        )
        lines.append("")
        for i, step in enumerate(SOLVER_STEPS, 1):
            lines += [
                f"### {i}. {step.title}",
                step.prompt,
                "_Alternate angle:_ what if we inverted or delayed this step?",
                "",
            ]
    else:
        for i, step in enumerate(SOLVER_STEPS, 1):
            lines += [f"### {i}. {step.title}", step.prompt, ""]
    if related:
        lines += ["---", "**Related knowledge**"]
        lines += [f"- `{serial}` {title}" for serial, title in related[:5]]
        lines.append("")
    lines.append(
        "_Reply with your DEFINE statement (or “next”) to advance one step at a time._"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Cognitive modes — presentation lenses ONLY
# ---------------------------------------------------------------------------


class CognitiveMode(Enum):
    """Presentation/routing lenses. Never facts, safety, permissions, integrity."""

    NORMAL = "normal"
    FOCUS = "focus"
    ADHD = "adhd"
    DAYDREAM = "daydream"
    DREAM = "dream"
    HYPERFOCUS = "hyperfocus"

    @classmethod
    def coerce(cls, mode: str) -> "CognitiveMode":
        try:
            return cls(str(mode or "").lower())
        except ValueError:
            return cls.NORMAL

    def describe(self) -> str:
        return {
            CognitiveMode.NORMAL: "Balanced default",
            CognitiveMode.FOCUS: "Single thread, minimal distraction",
            CognitiveMode.ADHD: "Short steps, one action, checkpoints, low clutter",
            CognitiveMode.DAYDREAM: "Background ideation running",
            CognitiveMode.DREAM: "Alternate-path exploration on answers",
            CognitiveMode.HYPERFOCUS: "Maximum depth on one problem",
        }[self]


class ModeStyler:
    """Applies a cognitive mode to reply *text*.

    The styler receives only the text and the mode — deliberately no
    handle on policy, memory, tools, or permissions, so a mode can never
    alter what LEVI knows, allows, or enforces. Presentation only.
    """

    def __init__(self, mode: str = "normal") -> None:
        self._mode = CognitiveMode.coerce(mode)

    @property
    def mode(self) -> CognitiveMode:
        return self._mode

    def set(self, mode: str) -> CognitiveMode:
        self._mode = CognitiveMode.coerce(mode)
        return self._mode

    def style(self, text: str) -> str:
        """Style ``text`` per the active mode. Pure function."""
        text = str(text or "")
        mode = self._mode
        if mode is CognitiveMode.ADHD:
            parts = [p for p in text.split("\n\n") if p.strip()][:4]
            clipped = [p if len(p) <= 280 else p[:277] + "…" for p in parts]
            return (
                "\n\n".join(clipped)
                + "\n\n_ADHD lens: one chunk at a time. Say “more” for the next._"
            )
        if mode is CognitiveMode.FOCUS:
            return text + "\n\n_Focus lens: staying on the current thread._"
        if mode is CognitiveMode.HYPERFOCUS:
            return (
                "## HyperFocus\n"
                + text
                + "\n\n_HyperFocus lens: deep single-thread pass. Ask “next angle” for another._"
            )
        if mode in (CognitiveMode.DREAM, CognitiveMode.DAYDREAM):
            return (
                text
                + "\n\n_Dream lens: consider the inverted path too — what would doing the opposite reveal?_"
            )
        return text


# ---------------------------------------------------------------------------
# Skill registration
# ---------------------------------------------------------------------------

try:  # pragma: no cover — import-time fallback keeps module import light
    from levi.skill.registry import Skill, SkillRisk

    def _skill_solve(args):
        args = args or {}
        problem = str(args.get("problem") or args.get("text") or "")
        if not problem.strip():
            return "solve needs a problem statement"
        return solve(problem, mode=str(args.get("mode") or "normal"))

    def _skill_style(args):
        args = args or {}
        styler = ModeStyler(str(args.get("mode") or "normal"))
        return styler.style(str(args.get("text") or ""))

    SOLVER_SKILLS = [
        Skill(
            id="agent_solve",
            name="Sequential Solver",
            description="7-step guided problem solving (DEFINE→…→REFLECT); presentation lenses only",
            category="agent",
            risk_level=SkillRisk.INFO,
            handler=_skill_solve,
            tags=["agent", "solver", "reasoning"],
        ),
        Skill(
            id="agent_mode_style",
            name="Cognitive Mode Styler",
            description="Apply a cognitive mode lens to reply text (UX only; never facts/safety/permissions)",
            category="agent",
            risk_level=SkillRisk.INFO,
            handler=_skill_style,
            tags=["agent", "mode", "ux"],
        ),
    ]
except ImportError:  # pragma: no cover
    SOLVER_SKILLS = []  # type: ignore[assignment]
    Skill = object  # type: ignore[assignment,misc]
    SkillRisk = None  # type: ignore[assignment]
