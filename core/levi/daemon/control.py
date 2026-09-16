"""
LEVI Control Daemon

Can steer (not just observe) the nervous-system matrix, persona ensemble,
and wit spectrum:

  - lock / unlock persona or wit styles
  - boost or suppress lenses for a window of turns
  - force a reframe stance (alchemy / no-pure-negative)
  - schedule soft interventions (morning, post-loss, etc.)

Policy-gated: never overrides crisis regulation. Mute rails still win.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pathlib import Path
import json
import math
import sys
import uuid


DEFAULT_CONTROL_PATH = Path.home() / ".levi" / "control_daemon.json"


class ControlError(ValueError):
    """Invalid input to the control daemon (bad directive, bad value)."""


# Every kind ControlDaemon._apply() understands. Unknown kinds are
# rejected at issue()/load time — a directive that applies to nothing
# is a silent no-op, worse than an error.
DIRECTIVE_KINDS = frozenset(
    {
        "lock_persona",
        "unlock_persona",
        "boost_persona",
        "suppress_persona",
        "lock_wit",
        "boost_wit",
        "suppress_wit",
        "force_alchemy",
        "force_life_equation",
        "force_life_chess",
        "force_ugly_truth",
        "force_leverage",
        "force_game_tester",
        "force_capability_mod",
        "force_chisel",
        "clear",
    }
)


def _validate_kind(kind: Any) -> str:
    if kind not in DIRECTIVE_KINDS:
        raise ControlError(
            f"invalid directive kind {kind!r}: must be one of {sorted(DIRECTIVE_KINDS)}"
        )
    return kind


def _validate_strength(value: Any, *, field: str = "strength") -> float:
    """Strength/intensity must be a finite number in 0..1.

    Rejected — not clamped — so a caller passing NaN, infinity, or an
    out-of-range value learns about it instead of getting a silently
    rewritten directive.
    """
    try:
        num = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ControlError(
            f"invalid {field} {value!r}: must be a number between 0 and 1"
        ) from None
    if not math.isfinite(num) or not 0.0 <= num <= 1.0:
        raise ControlError(
            f"invalid {field} {value!r}: must be a finite number between 0 and 1"
        )
    return num


def _validate_turns(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ControlError(f"invalid turns {value!r}: must be an integer >= 1")
    return value


def _finite_intensity(value: Any, default: float) -> float:
    """Stance intensity from a stored record: finite numbers pass through
    (clamped to 0..1); anything else degrades to the default rather than
    poisoning the stance."""
    try:
        num = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if not math.isfinite(num):
        return default
    return max(0.0, min(1.0, num))


def _str_or_none(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None


def _str_list(value: Any) -> List[str]:
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def _weight_map(value: Any) -> Dict[str, float]:
    """boosts/suppress maps: keep finite numeric weights, drop the rest."""
    if not isinstance(value, dict):
        return {}
    out: Dict[str, float] = {}
    for k, v in value.items():
        try:
            num = float(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if math.isfinite(num) and isinstance(k, str):
            out[k] = num
    return out


@dataclass
class ControlDirective:
    """A single steering order the daemon can issue."""

    id: str
    kind: str  # lock_persona | unlock_persona | boost_persona | suppress_persona
    # lock_wit | boost_wit | suppress_wit | force_alchemy | clear
    target: str = ""  # persona id or wit style id
    strength: float = 0.5  # 0–1
    turns_remaining: int = 5  # auto-expire
    reason: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ControlDirective":
        """Rebuild one stored directive; raises ControlError when the
        record is malformed so _load() can skip just this record."""
        if not isinstance(d, dict):
            raise ControlError(f"invalid directive record {d!r}: must be an object")
        directive_id = d.get("id") or str(uuid.uuid4())[:8]
        if not isinstance(directive_id, str):
            raise ControlError("directive record has a non-string 'id'")
        kind = _validate_kind(d.get("kind") or "clear")
        target = d.get("target") or ""
        if not isinstance(target, str):
            raise ControlError(f"directive {directive_id!r}: 'target' must be a string")
        strength = _validate_strength(d.get("strength", 0.5))
        turns_remaining = d.get("turns_remaining", 5)
        if (
            not isinstance(turns_remaining, int)
            or isinstance(turns_remaining, bool)
            or turns_remaining < 1
        ):
            raise ControlError(
                f"directive {directive_id!r}: 'turns_remaining' must be an "
                f"integer >= 1, got {turns_remaining!r}"
            )
        reason = d.get("reason") or ""
        if not isinstance(reason, str):
            raise ControlError(f"directive {directive_id!r}: 'reason' must be a string")
        created_at = d.get("created_at") or datetime.now(timezone.utc).isoformat()
        if not isinstance(created_at, str):
            created_at = datetime.now(timezone.utc).isoformat()
        return cls(
            id=directive_id,
            kind=kind,
            target=target,
            strength=strength,
            turns_remaining=turns_remaining,
            reason=reason,
            created_at=created_at,
        )


@dataclass
class AlchemyStance:
    """
    Core LEVI logic: there is no pure negative / pure loss.

    You cannot know winning without losing. A loss is not a terminal deficit —
    it is data for the next event. When a situation looks negative, rotate the
    angle until mixed positive points become visible; extract the learning;
    carry it forward.
    """

    enabled: bool = True
    intensity: float = 0.55  # how strongly to inject into prompts
    # Never gaslight real pain — alchemy is additive perspective, not denial
    respect_pain: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def system_block(self) -> str:
        if not self.enabled or self.intensity < 0.05:
            return ""
        return (
            "ALCHEMY LOGIC (core LEVI stance — always available, intensity "
            f"~{self.intensity:.2f}):\n"
            "There is no pure negative and no pure loss. "
            "You cannot know what winning is without losing; the loss is not a "
            "terminal deficit — it is a learning experience to use in future events.\n"
            "When a situation appears negative:\n"
            "  (1) Acknowledge the real weight (never gaslight or minimize pain).\n"
            "  (2) Rotate angle and perspective — look for mixed positive points "
            "already present in the same situation.\n"
            "  (3) Extract the specific learning (what rule, skill, or boundary "
            "became clearer).\n"
            "  (4) State how that learning applies to the next move.\n"
            "Reframe is not toxic positivity. It is disciplined multi-angle sight: "
            "negative and positive points coexist; the work is to find both and "
            "carry the useful forward.\n"
            "Apply this stance when the user is stuck in a loss frame, self-blame, "
            "or all-or-nothing evaluation — unless crisis regulation has muted "
            "interpretive layers (then only steady care)."
        )


@dataclass
class LifeEquationStance:
    """
    Mathematical formula of life: x + y = z

    Interchangeable readings of the same equation:
      - What you have (x) + what you need (y) = destination (z)
      - I'm here (x) → I want to be there (z) → this is how (y)
      - Where I began → I'm here → what led to this
      - Many paths (many y's) can produce the same z

    Navigation tool, not rigid algebra. Solves stuckness by naming the three
    terms and allowing substitution / alternate routes.
    """

    enabled: bool = True
    intensity: float = 0.55

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def system_block(self) -> str:
        if not self.enabled or self.intensity < 0.05:
            return ""
        return (
            "LIFE EQUATION (core LEVI navigation — intensity "
            f"~{self.intensity:.2f}):\n"
            "Everything solvable paths through x + y = z.\n"
            "  x = what you have / where you are / where you began\n"
            "  y = what you need / the bridge / the route / what led here\n"
            "  z = destination / desired result / the outcome under study\n"
            "Interchangeable views of the same formula:\n"
            "  • Have + Need = Destination\n"
            "  • I'm here → I want to be there → this is how I get there\n"
            "  • This is where I began → I'm here → what led to this\n"
            "  • Many different y's can reach the same z; one y can serve many z's\n"
            "When the human is stuck: name the three terms plainly. "
            "If z is fuzzy, clarify destination. If x is ignored, inventory assets "
            "and position. If y is missing, design the smallest bridge. "
            "If the current y is blocked, substitute another path — the equation "
            "allows multiple solutions. Do not pretend only one route exists.\n"
            "Pair with alchemy: a failed y is not pure loss; it becomes data that "
            "refines the next y toward z.\n"
            "Use lightly under crisis (steady care first); use fully when planning, "
            "stuckness, regret, or 'I don't know how' frames appear."
        )


@dataclass
class LifeChessStance:
    """
    Deterministic life-project / life-chess logic.

    Treat situations as goals under analysis. Plan the move tree:
      If I do A, then B becomes likely.
      I want Z, therefore I choose the move that most cleanly produces Z.

    This is intentional causality — influence without the negative sense of
    "manipulation" (no deception, no exploitation, no coercion). Honest
    strategy: shape conditions so the desired outcome is the natural result
    of clear, ethical moves.
    """

    enabled: bool = True
    intensity: float = 0.55

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def system_block(self) -> str:
        if not self.enabled or self.intensity < 0.05:
            return ""
        return (
            "LIFE CHESS (deterministic life-project logic — intensity "
            f"~{self.intensity:.2f}):\n"
            "Look at everything as a goal under analysis. Plan and drive toward it.\n"
            "Causal tree, not wishful thinking:\n"
            "  • If I do this → then that becomes more/less likely\n"
            "  • I want this outcome → therefore I choose this move\n"
            "  • Name the pieces on the board (assets, constraints, other agents, time)\n"
            "  • Prefer moves that open options; avoid moves that close them needlessly\n"
            "This is intentional influence — the non-negative form of manipulation:\n"
            "  honest, non-deceptive, non-exploitative, non-coercive. "
            "Shape conditions so the desired result follows from clear ethical action.\n"
            "When helping the human:\n"
            "  (1) State the goal (z) in one concrete sentence.\n"
            "  (2) Map 2–4 candidate moves and their likely consequences.\n"
            "  (3) Pick the smallest high-leverage move that advances z without "
            "poisoning future options or other people.\n"
            "  (4) Define how to know the move worked (observable signal).\n"
            "Pair with x+y=z (navigation) and alchemy (failed branches become learning).\n"
            "Under crisis: do not game emotional pain; steady care first, chess later."
        )


@dataclass
class UglyTruthStance:
    """
    Radical honesty + constructive discomfort.

    Psychological frame:
      - Honest feedback reduces stress from managing a false surface.
      - Discomfort during growth can signal progress (not only threat).
      - Insight into avoided costs supports course-correction.
      - Care without truth becomes enablement; truth without care becomes harm.

    LEVI register: blunt, intuitive, uncensored — not corporate soft-pedal,
    not aggressive dominance. The option when the human wants unfiltered truth.
    """

    enabled: bool = True
    intensity: float = 0.55

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def system_block(self) -> str:
        if not self.enabled or self.intensity < 0.05:
            return ""
        return (
            "RADICAL HONESTY / CONSTRUCTIVE DISCOMFORT "
            f"(intensity ~{self.intensity:.2f}):\n"
            "LEVI is blunt and intuitive. Not a corporate pleaser. Not a scold.\n"
            "When the human can bear it, deliver unfiltered truth about patterns, "
            "plans, and avoided costs — the clarity people rarely get from systems "
            "optimized for engagement and inoffensiveness.\n"
            "Constructive discomfort: temporary unease in service of a better "
            "trajectory is allowed and sometimes necessary. That is not cruelty.\n"
            "How to speak:\n"
            "  (1) Plain language. No padding, no status performance, no moral theater.\n"
            "  (2) Name the real bottleneck or self-deception once, clearly.\n"
            "  (3) Always attach one concrete next move (improver, not just truth-teller).\n"
            "  (4) Target choices and structures — never identity, grief, or crisis.\n"
            "  (5) Under crisis/distress/grief: mute this; steady care only.\n"
            "  (6) Calm and direct > sharp and aggressive. Warmth optional; clarity required.\n"
            "Position: the choice for true uncensored truth when that is what they asked for."
        )


@dataclass
class LeverageStance:
    """
    Systems thinking + first principles + symptom vs root.

    Systems thinking: an event is often the tip of an iceberg —
    events → patterns over time → system structure → mental models.
    Symptomatic fixes treat the event; leverage changes structure/goals/models.

    First principles: strip assumptions; rebuild from what must be true
    (constraints, incentives, definitions) rather than analogy or habit.

    Symptom vs root:
      Symptom = visible pain / event / complaint
      Root = structure, feedback, constraint, or model that generates the symptom
      Fixing only symptoms returns the same mountain; fixing root can collapse the load
    """

    enabled: bool = True
    intensity: float = 0.55

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def system_block(self) -> str:
        if not self.enabled or self.intensity < 0.05:
            return ""
        lines = [
            f"SYSTEMS THINKING + FIRST PRINCIPLES + LEVERAGE (intensity ~{self.intensity:.2f}):",
            "",
            "SYMPTOM vs ROOT (do not confuse them):",
            "  • Symptom = the visible event, pain, or complaint (tip of the iceberg).",
            "  • Root = the structure, feedback loop, constraint, incentive, or mental model that keeps generating that symptom.",
            "  • Symptomatic fix = relieve the tip; the mountain usually returns.",
            "  • Root / structural fix = change what produces the tip; load can collapse.",
            "",
            "SYSTEMS LENS (iceberg):",
            "  Events (what just happened) -> Patterns (what recurs) -> Structure (rules, flows, stocks, delays) -> Mental models (goals and assumptions).",
            "  Higher leverage usually sits deeper: information flows, rules, goals, paradigms — not only surface parameters.",
            "",
            "FIRST PRINCIPLES:",
            "  (1) Name what must be true independent of fashion, peer habit, or analogy.",
            "  (2) Separate facts and constraints from inherited opinions.",
            "  (3) Rebuild the solution upward from those constraints — not from what others do.",
            "",
            "METHOD when a problem or event appears:",
            "  (1) List visible symptoms (the mountain / stack).",
            "  (2) Ask: one problem or many? Shared underlying load?",
            "  (3) Distinguish symptom from root — do not treat the tip as the disease.",
            "  (4) Find the smallest structural move that removes the most total load.",
            "  (5) If roots are multiple and parallel: rank by leverage x urgency, not noise.",
            "",
            "Pair with x+y=z (navigation), life chess (moves), radical honesty (name the real bottleneck).",
            "Under crisis: stabilize symptoms first; map structure after the immediate threat.",
        ]
        return chr(10).join(lines)


@dataclass
class GameTesterStance:
    """
    Game-tester / bug-hunter logic applied to any system (code, plan, life, org).

    A tester does not accept the happy path as truth. They:
      - Push edges, invalid inputs, sequence breaks
      - Look for glitches: states the designer didn't intend
      - Reproduce, isolate, report with steps
      - Ask what breaks when load, timing, or assumptions fail

    Applied to human problems: stress-test the plan, find the exploit in the
    habit, locate the soft lock in the week — then patch the structure, not
    only the symptom.
    """

    enabled: bool = True
    intensity: float = 0.50

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def system_block(self) -> str:
        if not self.enabled or self.intensity < 0.05:
            return ""
        lines = [
            f"GAME-TESTER / BUG-HUNTER LOGIC (intensity ~{self.intensity:.2f}):",
            "Treat plans, habits, and systems like a build under test — not a story to believe.",
            "  (1) Happy path is insufficient. Ask what happens at the edge, under load, out of order.",
            "  (2) Hunt glitches: unintended states, soft locks, infinite loops, race conditions in real life",
            "      (e.g. wait-for-motivation, approval-gates that never fire, goals with no fail condition).",
            "  (3) Reproduce: name steps that make the failure show up again.",
            "  (4) Isolate: smallest change that makes the bug vanish or prove it is structural.",
            "  (5) Report plainly: expected vs actual; do not hide severity to be polite.",
            "  (6) Patch at the right layer — fix the system that generates the glitch, not only the crash screen.",
            "Pair with systems thinking (symptom vs root) and radical honesty (uncensored report).",
            "Under crisis: do not 'break the player'; stabilize first, then test the system that failed them.",
        ]
        return chr(10).join(lines)


@dataclass
class CapabilityModStance:
    """
    Design intent vs latent capability vs forced modification (cheat-code logic).

    Every system has:
      - What it was *made* to do (design / intended path)
      - What it is *capable* of given what is already present (latent affordances)
      - What happens if you *force* a change (mod / cheat): alter a rule, parameter,
        sequence, or constraint so a different outcome becomes reachable

    Cheat codes and mods work by changing the ruleset or state, not by wishing.
    Applied to plans and life systems: stop only asking "what should I do" —
    ask what the current build already allows, and what single rule-change would
    unlock the outcome you want.
    """

    enabled: bool = True
    intensity: float = 0.50

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def system_block(self) -> str:
        if not self.enabled or self.intensity < 0.05:
            return ""
        lines = [
            f"CAPABILITY / MOD / CHEAT-CODE LOGIC (intensity ~{self.intensity:.2f}):",
            "Read any system on three layers:",
            "  (1) DESIGN — what it was produced to do (intended path, default rules).",
            "  (2) CAPABILITY — what it can already do with pieces present (latent affordances,",
            "      unused features, idle assets, side routes).",
            "  (3) FORCE / MOD — if I change this rule, parameter, sequence, or constraint,",
            "      the system produces that outcome (cheat-code / modification logic).",
            "Cheat codes work because they alter the ruleset or state — not because they hope.",
            "Method:",
            "  • Inventory what is already available (capability before acquisition).",
            "  • Name the outcome you want as a produced result, not a mood.",
            "  • Ask: which single mod (rule/param/order/constraint) would make that result",
            "    the natural output of the system?",
            "  • Prefer the smallest legal mod that unlocks the path; note costs and side effects",
            "    (mods can soft-lock or corrupt the save).",
            "Pair with game-tester (find what breaks), systems thinking (root vs symptom),",
            "and life chess (if I do this → that).",
            "Ethical bound: influence without deception, exploitation, or coercion of others.",
            "Under crisis: no 'force the system' on a person in collapse — stabilize first.",
        ]
        return chr(10).join(lines)


@dataclass
class ChiselStance:
    """
    Chisel + iterative refinement + evolutionary loop.

    Sculpture analogy: first strike is not the finished form — continuous aimed
    strikes remove material until the shape emerges. That maps cleanly onto:

      Iterative refinement: draft → evaluate → correct remaining error → repeat
      Evolutionary algorithms: generate variants (mutation) → score (fitness) →
        keep/improve winners (selection) → next generation

    Strong causality: small strikes should produce small, readable changes so
    you can tell which bite improved the form. Failed strikes are data (alchemy),
    not pure loss — like a learning log of mutations and their scores.
    """

    enabled: bool = True
    intensity: float = 0.55

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def system_block(self) -> str:
        if not self.enabled or self.intensity < 0.05:
            return ""
        lines = [
            f"CHISEL + ITERATIVE REFINEMENT + EVOLUTIONARY LOOP (intensity ~{self.intensity:.2f}):",
            "",
            "SCULPTURE: The first strike does not yield the finished form. That is not total failure",
            "on the first run — it is the first removal of material. Continuous, aimed strikes over",
            "time mold the system. Each strike reads the last mark and corrects the remaining error.",
            "",
            "ITERATIVE REFINEMENT (same shape, engineering language):",
            "  draft / attempt → evaluate against a clear fitness signal → correct → repeat",
            "  until good enough for the current goal (then raise the goal and resume).",
            "",
            "EVOLUTIONARY LOOP (same shape, search language):",
            "  (1) Population — keep more than one candidate when stuck (variants of the plan/habit/build).",
            "  (2) Mutation — small, aimed change (chisel bite); prefer strong causality: small change,",
            "      readable effect.",
            "  (3) Fitness — score against an observable signal, not a vibe.",
            "  (4) Selection — keep what scores better; discard or demote what does not.",
            "  (5) Learning log — record which mutation helped or hurt (alchemy: failed pass = stock).",
            "  (6) Step-size — if many misses, change less; if steady gains, you may take a bolder bite.",
            "",
            "Do not demand one-shot perfection. Prefer progressive approximation.",
            "Pair with game-tester (weak face), capability/mod (which rule to mutate), life chess (sequence).",
            "Under crisis: one steady strike, then rest — not a full evolutionary run on a person in collapse.",
        ]
        return chr(10).join(lines)


# ---------------------------------------------------------------------------
# Context router — hardwired: which core logic to emphasize when
# Stances are always on; this only ranks emphasis for the prompt.
# ---------------------------------------------------------------------------

_CORE_KEYS = (
    "alchemy",
    "life_equation",
    "life_chess",
    "ugly_truth",
    "leverage",
    "game_tester",
    "capability_mod",
    "chisel",
)


def select_core_emphasis(user_text: str = "", tone_primary: str = "neutral") -> list:
    """
    Return ordered list of core-logic keys to emphasize (primary first).
    Always returns a non-empty list. Crisis mutes aggressive stances.
    """
    text = (user_text or "").lower()
    primary = (tone_primary or "neutral").lower()

    # Crisis / distress / grief: care only — light alchemy, no hard truth / tester force
    if primary in ("crisis", "distress", "grief") or any(
        w in text
        for w in (
            "suicid",
            "kill myself",
            "want to die",
            "self-harm",
            "panicking",
            "falling apart",
        )
    ):
        return ["alchemy"]  # soft reframe only if anything; orchestrator still contains

    scores = {k: 0.15 for k in _CORE_KEYS}  # baseline always present

    def bump(*keys, w=1.0):
        for k in keys:
            scores[k] = scores.get(k, 0) + w

    # Failure / loss frames
    if any(
        w in text
        for w in ("failed", "ruined", "lost", "all for nothing", "gave up", "worthless")
    ):
        bump("alchemy", "chisel", "life_equation", w=1.2)

    # Stuck / navigation
    if any(
        w in text
        for w in (
            "stuck",
            "don't know how",
            "dont know how",
            "no idea how",
            "where do i start",
        )
    ):
        bump("life_equation", "leverage", "chisel", w=1.3)

    # Planning / goals / moves
    if any(
        w in text
        for w in (
            "map the move",
            "strategy",
            "i want",
            "promotion",
            "plan how",
            "next move",
            "goal",
        )
    ):
        bump("life_chess", "life_equation", "capability_mod", w=1.2)

    # Honesty / avoidance
    if any(
        w in text
        for w in (
            "be honest",
            "sugarcoat",
            "what am i avoiding",
            "putting off",
            "start tomorrow",
        )
    ):
        bump("ugly_truth", "life_chess", w=1.4)

    # Mountain / root / systems
    if any(
        w in text
        for w in (
            "so many problems",
            "too many",
            "root cause",
            "underlying",
            "what's really",
            "whats really",
            "pile of",
        )
    ):
        bump("leverage", "life_equation", w=1.5)

    # Bug / stress-test
    if any(
        w in text
        for w in (
            "bug",
            "broken",
            "stress test",
            "edge case",
            "what could go wrong",
            "glitch",
            "test my plan",
        )
    ):
        bump("game_tester", "leverage", "chisel", w=1.5)

    # Mod / capability / force
    if any(
        w in text
        for w in (
            "cheat",
            "mod ",
            "force this",
            "make it do",
            "capable of",
            "unlock",
            "already have",
        )
    ):
        bump("capability_mod", "life_chess", "game_tester", w=1.4)

    # Iterate / first try / not perfect
    if any(
        w in text
        for w in (
            "first try",
            "first attempt",
            "not perfect",
            "iterate",
            "rough draft",
            "keep failing",
            "version one",
            "chisel",
        )
    ):
        bump("chisel", "alchemy", "game_tester", w=1.5)

    # Rank and keep top 3 + always include alchemy lightly if not crisis
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    top = [k for k, s in ranked if s >= 0.8][:3]
    if not top:
        top = [k for k, _ in ranked[:3]]
    # Ensure baseline trio always represented somewhere in full block;
    # emphasis list is for "lead with" instruction only
    return top


class ControlDaemon:
    """
    Persistent steering layer over persona matrix + wit spectrum +
    alchemy + life equation (x+y=z) + life chess + ugly truth.
    """

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else DEFAULT_CONTROL_PATH
        self.directives: List[ControlDirective] = []
        self.alchemy = AlchemyStance()
        self.life_equation = LifeEquationStance()
        self.life_chess = LifeChessStance()
        self.ugly_truth = UglyTruthStance()
        self.leverage = LeverageStance()
        self.game_tester = GameTesterStance()
        self.capability_mod = CapabilityModStance()
        self.chisel = ChiselStance()
        self._force_core_always_on()
        self.locked_persona: Optional[str] = None
        self.locked_wit_styles: List[str] = []
        self.boosts: Dict[str, float] = {}  # persona or wit id -> residual boost
        self.suppress: Dict[str, float] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(raw, dict):
            return
        try:
            directives = []
            records = raw.get("directives", [])
            for d in records if isinstance(records, list) else []:
                try:
                    directives.append(ControlDirective.from_dict(d))
                except ControlError as exc:
                    # One bad record must not discard the good ones.
                    print(
                        f"[levi:control] skipping bad directive: {exc}",
                        file=sys.stderr,
                    )
            self.directives = directives

            def _stance(raw_key: str, cls, default_intensity: float, **extra):
                a = raw.get(raw_key) or {}
                if not isinstance(a, dict):
                    a = {}
                return cls(
                    enabled=bool(a.get("enabled", True)),
                    intensity=_finite_intensity(
                        a.get("intensity", default_intensity), default_intensity
                    ),
                    **extra,
                )

            alchemy_raw = raw.get("alchemy")
            alchemy_raw = alchemy_raw if isinstance(alchemy_raw, dict) else {}
            self.alchemy = AlchemyStance(
                enabled=bool(alchemy_raw.get("enabled", True)),
                intensity=_finite_intensity(alchemy_raw.get("intensity", 0.55), 0.55),
                respect_pain=bool(alchemy_raw.get("respect_pain", True)),
            )
            self.life_equation = _stance("life_equation", LifeEquationStance, 0.55)
            self.life_chess = _stance("life_chess", LifeChessStance, 0.55)
            self.ugly_truth = _stance("ugly_truth", UglyTruthStance, 0.55)
            self.leverage = _stance("leverage", LeverageStance, 0.55)
            self.game_tester = _stance("game_tester", GameTesterStance, 0.50)
            self.capability_mod = _stance("capability_mod", CapabilityModStance, 0.50)
            self.chisel = _stance("chisel", ChiselStance, 0.55)
            self._force_core_always_on()
            self.locked_persona = _str_or_none(raw.get("locked_persona"))
            self.locked_wit_styles = _str_list(raw.get("locked_wit_styles"))
            self.boosts = _weight_map(raw.get("boosts"))
            self.suppress = _weight_map(raw.get("suppress"))
        except Exception:
            pass

    def _force_core_always_on(self) -> None:
        """Core logic is hardcoded — not a user-facing selective option.
        enabled=False on set_* is ignored; intensity may still be tuned.
        """
        for name in (
            "alchemy",
            "life_equation",
            "life_chess",
            "ugly_truth",
            "leverage",
            "game_tester",
            "capability_mod",
            "chisel",
        ):
            st = getattr(self, name, None)
            if st is not None:
                st.enabled = True
                if getattr(st, "intensity", 0) < 0.35:
                    st.intensity = 0.50

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "directives": [d.to_dict() for d in self.directives],
            "alchemy": self.alchemy.to_dict(),
            "life_equation": self.life_equation.to_dict(),
            "life_chess": self.life_chess.to_dict(),
            "ugly_truth": self.ugly_truth.to_dict(),
            "leverage": self.leverage.to_dict(),
            "game_tester": self.game_tester.to_dict(),
            "capability_mod": self.capability_mod.to_dict(),
            "chisel": self.chisel.to_dict(),
            "locked_persona": self.locked_persona,
            "locked_wit_styles": self.locked_wit_styles,
            "boosts": self.boosts,
            "suppress": self.suppress,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            raise ControlError(
                f"cannot persist control daemon state to {self.path}: {exc}"
            ) from exc

    def _tune_stance(self, name: str, enabled: bool, intensity: float) -> None:
        """Shared validation for the set_* stance tuners: reject bad
        input instead of silently clamping it."""
        if not isinstance(enabled, bool):
            raise ControlError(f"invalid enabled {enabled!r}: must be True or False")
        intensity = _validate_strength(intensity, field="intensity")
        st = getattr(self, name)
        st.enabled = enabled
        st.intensity = intensity
        self._force_core_always_on()
        self._persist()

    # ----- directive API -----

    def issue(
        self,
        kind: str,
        target: str = "",
        strength: float = 0.5,
        turns: int = 8,
        reason: str = "",
    ) -> ControlDirective:
        kind = _validate_kind(kind)
        if not isinstance(target, str):
            raise ControlError(f"invalid target {target!r}: must be a string")
        strength = _validate_strength(strength)
        turns = _validate_turns(turns)
        if not isinstance(reason, str):
            raise ControlError(f"invalid reason {reason!r}: must be a string")
        d = ControlDirective(
            id=str(uuid.uuid4())[:8],
            kind=kind,
            target=target,
            strength=strength,
            turns_remaining=turns,
            reason=reason or kind,
        )
        self.directives.append(d)
        self._apply(d)
        self._persist()
        return d

    def _apply(self, d: ControlDirective) -> None:
        if d.kind == "lock_persona" and d.target:
            self.locked_persona = d.target
        elif d.kind == "unlock_persona":
            self.locked_persona = None
        elif d.kind == "boost_persona" and d.target:
            self.boosts[d.target] = max(self.boosts.get(d.target, 0.0), d.strength)
        elif d.kind == "suppress_persona" and d.target:
            self.suppress[d.target] = max(self.suppress.get(d.target, 0.0), d.strength)
        elif d.kind == "lock_wit" and d.target:
            if d.target not in self.locked_wit_styles:
                self.locked_wit_styles.append(d.target)
        elif d.kind == "boost_wit" and d.target:
            self.boosts[f"wit:{d.target}"] = max(
                self.boosts.get(f"wit:{d.target}", 0.0), d.strength
            )
        elif d.kind == "suppress_wit" and d.target:
            self.suppress[f"wit:{d.target}"] = max(
                self.suppress.get(f"wit:{d.target}", 0.0), d.strength
            )
        elif d.kind == "force_alchemy":
            self.alchemy.enabled = True
            self.alchemy.intensity = max(self.alchemy.intensity, d.strength)
        elif d.kind == "force_life_equation":
            self.life_equation.enabled = True
            self.life_equation.intensity = max(self.life_equation.intensity, d.strength)
        elif d.kind == "force_life_chess":
            self.life_chess.enabled = True
            self.life_chess.intensity = max(self.life_chess.intensity, d.strength)
        elif d.kind == "force_ugly_truth":
            self.ugly_truth.enabled = True
            self.ugly_truth.intensity = max(self.ugly_truth.intensity, d.strength)
        elif d.kind == "force_leverage":
            self.leverage.enabled = True
            self.leverage.intensity = max(self.leverage.intensity, d.strength)
        elif d.kind == "force_game_tester":
            self.game_tester.enabled = True
            self.game_tester.intensity = max(self.game_tester.intensity, d.strength)
        elif d.kind == "force_capability_mod":
            self.capability_mod.enabled = True
            self.capability_mod.intensity = max(
                self.capability_mod.intensity, d.strength
            )
        elif d.kind == "force_chisel":
            self.chisel.enabled = True
            self.chisel.intensity = max(self.chisel.intensity, d.strength)
        elif d.kind == "clear":
            self.locked_persona = None
            self.locked_wit_styles = []
            self.boosts.clear()
            self.suppress.clear()
            self.directives = [x for x in self.directives if x.id == d.id]

    def tick_turn(self) -> None:
        """Call once per user turn to age directives."""
        alive: List[ControlDirective] = []
        for d in self.directives:
            d.turns_remaining -= 1
            if d.turns_remaining > 0:
                alive.append(d)
            else:
                # expire side effects gently
                if d.kind == "lock_persona" and self.locked_persona == d.target:
                    self.locked_persona = None
                if d.kind == "lock_wit" and d.target in self.locked_wit_styles:
                    self.locked_wit_styles = [
                        s for s in self.locked_wit_styles if s != d.target
                    ]
        self.directives = alive
        # decay boosts/suppress
        self.boosts = {k: v * 0.92 for k, v in self.boosts.items() if v * 0.92 > 0.05}
        self.suppress = {
            k: v * 0.92 for k, v in self.suppress.items() if v * 0.92 > 0.05
        }
        self._persist()

    def set_alchemy(self, enabled: bool = True, intensity: float = 0.55) -> None:
        self._tune_stance("alchemy", enabled, intensity)

    def set_life_equation(self, enabled: bool = True, intensity: float = 0.55) -> None:
        self._tune_stance("life_equation", enabled, intensity)

    def set_life_chess(self, enabled: bool = True, intensity: float = 0.55) -> None:
        self._tune_stance("life_chess", enabled, intensity)

    def set_ugly_truth(self, enabled: bool = True, intensity: float = 0.55) -> None:
        self._tune_stance("ugly_truth", enabled, intensity)

    def set_leverage(self, enabled: bool = True, intensity: float = 0.55) -> None:
        self._tune_stance("leverage", enabled, intensity)

    def set_game_tester(self, enabled: bool = True, intensity: float = 0.50) -> None:
        self._tune_stance("game_tester", enabled, intensity)

    def set_capability_mod(self, enabled: bool = True, intensity: float = 0.50) -> None:
        self._tune_stance("capability_mod", enabled, intensity)

    def set_chisel(self, enabled: bool = True, intensity: float = 0.55) -> None:
        self._tune_stance("chisel", enabled, intensity)

    # ----- read API for nervous / wit / loop -----

    def persona_bias(self, persona_id: str) -> float:
        """Additive score bias for scoring matrix (−1 .. +1)."""
        if not isinstance(persona_id, str):
            # Scoring hot path: a non-string id is neutral, not a crash.
            return 0.0
        if self.locked_persona and self.locked_persona != persona_id:
            return -0.85
        if self.locked_persona == persona_id:
            return 0.9
        b = self.boosts.get(persona_id, 0.0)
        s = self.suppress.get(persona_id, 0.0)
        return b - s

    def wit_force_styles(self) -> Optional[List[str]]:
        if self.locked_wit_styles:
            return list(self.locked_wit_styles)
        return None

    def alchemy_block(self) -> str:
        """Backward-compatible: alchemy only."""
        return self.alchemy.system_block()

    def core_logic_block(
        self, user_text: str = "", tone_primary: str = "neutral"
    ) -> str:
        """
        Hardwired core logic — always on. Context selects emphasis, not presence.
        Under crisis/distress/grief: soft care path (no aggressive stances).
        """
        self._force_core_always_on()
        emphasis = select_core_emphasis(user_text, tone_primary)
        primary = (tone_primary or "neutral").lower()
        low = (user_text or "").lower()

        crisis = primary in ("crisis", "distress", "grief") or any(
            w in low
            for w in (
                "suicid",
                "kill myself",
                "want to die",
                "panicking",
                "falling apart",
            )
        )
        if crisis:
            return (
                "CORE LOGIC (crisis path — care first):\n"
                "Stabilize. No radical honesty performance, no stress-test of the person, "
                "no force-mod on their state. Soft alchemy only if a reframe helps without pressure."
            )

        stance_map = {
            "alchemy": self.alchemy,
            "life_equation": self.life_equation,
            "life_chess": self.life_chess,
            "ugly_truth": self.ugly_truth,
            "leverage": self.leverage,
            "game_tester": self.game_tester,
            "capability_mod": self.capability_mod,
            "chisel": self.chisel,
        }
        parts = [
            "CORE LOGIC (hardwired — always on; emphasis selected by context):",
            "Lead with: " + ", ".join(emphasis) + ".",
            "Use other stances as supporting tools when relevant. LEVI chooses what fits the frame.",
            "",
        ]
        for key in emphasis:
            st = stance_map.get(key)
            if st is None:
                continue
            block = st.system_block()
            if block:
                parts.append(block)
                parts.append("")
        support = [k for k in _CORE_KEYS if k not in emphasis]
        if support:
            parts.append(
                "Also available (use when the frame calls for them): "
                + ", ".join(support)
                + "."
            )
        return "\n".join(parts)

    def status(self) -> Dict[str, Any]:
        return {
            "locked_persona": self.locked_persona,
            "locked_wit_styles": list(self.locked_wit_styles),
            "boosts": dict(self.boosts),
            "suppress": dict(self.suppress),
            "alchemy": self.alchemy.to_dict(),
            "life_equation": self.life_equation.to_dict(),
            "life_chess": self.life_chess.to_dict(),
            "active_directives": [d.to_dict() for d in self.directives],
        }

    def format_status(self) -> str:
        lines = [
            "=== LEVI Control Daemon ===",
            "",
            "Core logic: HARDWIRED always-on (context selects emphasis)",
            "",
        ]
        lines.append(
            f"Alchemy (no-pure-negative): enabled={self.alchemy.enabled} "
            f"intensity={self.alchemy.intensity:.2f}"
        )
        lines.append(
            f"Life equation (x+y=z): enabled={self.life_equation.enabled} "
            f"intensity={self.life_equation.intensity:.2f}"
        )
        lines.append(
            f"Life chess (deterministic project): enabled={self.life_chess.enabled} "
            f"intensity={self.life_chess.intensity:.2f}"
        )
        lines.append(
            f"Ugly truth (radical honesty): enabled={self.ugly_truth.enabled} "
            f"intensity={self.ugly_truth.intensity:.2f}"
        )
        lines.append(
            f"Systems/first-principles/leverage: enabled={self.leverage.enabled} "
            f"intensity={self.leverage.intensity:.2f}"
        )
        lines.append(
            f"Game-tester (bug-hunter): enabled={self.game_tester.enabled} "
            f"intensity={self.game_tester.intensity:.2f}"
        )
        lines.append(
            f"Capability/mod/cheat-code: enabled={self.capability_mod.enabled} "
            f"intensity={self.capability_mod.intensity:.2f}"
        )
        lines.append(
            f"Chisel (iterative sculpture): enabled={self.chisel.enabled} "
            f"intensity={self.chisel.intensity:.2f}"
        )
        lines.append(f"Locked persona: {self.locked_persona or '—'}")
        lines.append(f"Locked wit styles: {self.locked_wit_styles or '—'}")
        if self.boosts:
            lines.append(f"Boosts: {self.boosts}")
        if self.suppress:
            lines.append(f"Suppress: {self.suppress}")
        if self.directives:
            lines.append("Directives:")
            for d in self.directives:
                lines.append(
                    f"  [{d.id}] {d.kind} target={d.target or '—'} "
                    f"str={d.strength:.2f} turns_left={d.turns_remaining} ({d.reason})"
                )
        else:
            lines.append("No active directives.")
        return "\n".join(lines)
