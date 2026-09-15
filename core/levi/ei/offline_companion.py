"""
Offline companion synthesizer — full LEVI logic without a neural model.

The deterministic reply engine behind ModelRouter's offline path
(levi.model.abstraction.DeterministicFallbackProvider). Sibling of
ei.companion (guidance layer used by the turn loop) and ei.chat_companion
(session REPL) — same care standards, different layer.

Uses tone, continuity (name/goal/shelf), alchemy, life equation, life chess,
and monotropism state to produce useful, structured replies offline.

This is not a fake LLM: it is deterministic structured care + planning.
When Ollama/cloud is available, ModelRouter prefers those; this is the
always-on path that makes the system real.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import re


def _continuity() -> Dict[str, Any]:
    out: Dict[str, Any] = {"name": None, "goal": None, "shelf": []}
    try:
        from levi.identity.profile import ProfileStore
        p = ProfileStore().load()
        out["name"] = getattr(p, "name", None)
        out["goal"] = getattr(p, "goal_this_week", None) or getattr(p, "goal", None)
    except Exception:
        pass
    try:
        from levi.identity.shelf import collect_shelf
        out["shelf"] = collect_shelf()[:5]
    except Exception:
        pass
    return out


def _tone(text: str):
    try:
        from levi.ei.tone import read_user_tone
        return read_user_tone(text)
    except Exception:
        return None


def _mono_label() -> Optional[str]:
    try:
        from levi.persona.monotropism import MonotropismTracker
        m = MonotropismTracker()
        a = m.state.active
        if a and a.depth >= 0.25:
            return a.label or a.signature[:40]
    except Exception:
        pass
    return None


def _atlas_hint(user_text: str) -> str:
    try:
        from levi.brain.corpus import Corpus
        hits = Corpus().search(user_text or "")
        if not hits:
            return ""
        u = hits[0]
        text = getattr(u, "text", None) or str(u)
        return "\n\nFrom offline brain: " + text[:280]
    except Exception:
        return ""


def _phase1_ensure(text: str, user_text: str = "") -> str:
    """Never return empty; crisis gets soft open if stripped."""
    t = (text or "").strip()
    low = (user_text or "").lower()
    crisis = any(w in low for w in ("panic", "suicidal", "kill myself", "falling apart", "emergency", "can't go on"))
    if not t:
        t = (
            "I am here with you. We slow this down one step. "
            "You do not have to solve everything in this breath. "
            "What is the smallest next move that keeps you safer?"
            if crisis
            else "I am listening. Say more about what matters most right now."
        )
    if crisis and len(t) < 60:
        t = (
            "Stabilize first: breath, body, one next action. "
            "Loss and panic are not pure ends — they are signals to reorient. "
        ) + t
    if user_text and len(t) < 400:
        hint = _atlas_hint(user_text)
        if hint and hint.strip() not in t:
            t = t + hint
    return t


def synthesize(
    user_text: str,
    system: Optional[str] = None,
    persona_name: Optional[str] = None,
) -> str:
    """
    Produce a grounded offline reply.
    """
    text = (user_text or "").strip()
    if not text:
        return "I'm here. Say what you need — a goal, a stuck point, or the next move."

    cont = _continuity()
    tone = _tone(text)
    primary = getattr(tone, "primary", "neutral") if tone else "neutral"
    regulation = getattr(tone, "regulation", "steady") if tone else "steady"
    name = cont.get("name")
    goal = cont.get("goal")
    shelf = cont.get("shelf") or []
    mono = _mono_label()
    lower = text.lower()

    # --- Crisis / distress: contain only ---
    if primary in ("crisis", "distress") or regulation == "contain":
        bits = []
        if name:
            bits.append(f"{name}, I'm steady with you.")
        else:
            bits.append("I'm steady with you.")
        bits.append(
            "No jokes, no pressure to solve everything at once. "
            "Name the single most urgent concrete thing (body, message, deadline, bill). "
            "We handle that first."
        )
        if goal:
            bits.append(f"Your weekly goal stays on the shelf for now: {goal}.")
        return " ".join(bits)

    # --- Identity ---
    if any(w in lower for w in ("who are you", "what are you", "your name")):
        return (
            "I'm LEVI — synthetic intelligence (SI): local-first companion kernel "
            "(friend, mentor, challenger, protector) with L.W.P. Full Cloud Model and Factory DNA. "
            "Core runs offline: tone regulation, nervous system, 230 personas, "
            "A–Z knowledge, alchemy (no pure loss), life equation x+y=z, life chess, monotropism, HITL. "
            "Chat: levi chat · Model: levi model · Knowledge: levi brain --seed-knowledge · "
            "Score: levi scorecard. "
            "Cloud is optional wings — never owns keys or continuity. Ollama optional for free-form generation."
        )

    # --- Goal queries ---
    if any(w in lower for w in ("my goal", "goal this week", "what am i working", "holding goal")):
        if goal:
            return (
                f"{'Ok ' + name + ' — ' if name else ''}"
                f"This week's goal: {goal}.\n"
                "Life equation: x = where you are now, z = that goal, y = the next bridge. "
                "Name one smallest move that advances z without closing options."
            )
        return (
            "No weekly goal is set yet. Run: levi init  or  levi morning\n"
            "Or tell me the destination (z) in one concrete sentence and I'll hold it."
        )

    # --- Failure / loss frame → alchemy + equation ---
    if any(w in lower for w in (
        "failed", "ruined", "everything is over", "i lost", "all for nothing",
        "gave up", "worthless", "can't do anything",
    )):
        lines = [
            "The weight is real — I'm not papering over it.",
            "Alchemy: this is not a pure loss. Extract the learning (what rule, skill, or hinge became clearer).",
            "Equation: x = what you still have · z = the outcome you still want · y = the bridge that failed — and the next y we design.",
            "Many y's can reach the same z. What is the single clearest signal this attempt gave you?",
        ]
        if goal:
            lines.insert(1, f"Held goal still on the board: {goal}.")
        return "\n".join(lines)

    # --- Planning / promotion / map the moves → life chess ---
    if any(w in lower for w in (
        "map the move", "map moves", "how do i get", "i want the", "plan how",
        "strategy for", "what should i do", "next move", "promotion",
    )) or ("want" in lower and any(w in lower for w in ("happen", "get", "become", "reach"))):
        z_guess = text
        # strip leading want phrases
        z_guess = re.sub(
            r"^(i want to|i want|how do i|map the moves? (for|to)?|strategy for)\s*",
            "",
            z_guess,
            flags=re.I,
        ).strip() or text
        lines = [
            f"Life chess — goal (z): {z_guess[:160]}",
            "",
            "Pieces on the board: your current assets (x), constraints, other agents, time.",
            "Candidate moves (pick the smallest high-leverage one):",
            "  1) Inventory x in one list — skills, relationships, finished work, open doors.",
            "  2) Define one observable signal that means progress (not a vibe).",
            "  3) Take one reversible step this week that opens options rather than closes them.",
            "",
            "Intentional influence only: honest, non-deceptive, non-exploitative.",
        ]
        if goal and goal.lower() not in z_guess.lower():
            lines.append(f"Also holding weekly goal: {goal}.")
        if mono:
            lines.append(f"Active interest tunnel: {mono} — stay in it unless you change subject.")
        return "\n".join(lines)

    # --- Stuck / don't know how → equation ---
    if any(w in lower for w in ("stuck", "don't know how", "dont know how", "no idea how", "lost on")):
        lines = [
            "Name the three terms of the life equation:",
            "  x = what you have / where you are",
            "  z = where you want to be (one concrete sentence)",
            "  y = the bridge (or the missing bridge)",
            "If z is fuzzy, clarify destination first. If y is blocked, substitute another path — many y's reach the same z.",
        ]
        if goal:
            lines.append(f"Candidate z from your held goal: {goal}")
        return "\n".join(lines)

    # --- Chisel / iterative sculpture ---
    if any(w in lower for w in (
        "first try", "first attempt", "not perfect", "one shot",
        "keep failing", "never get it right", "should have worked",
        "iterate", "version one", "rough draft", "chisel",
        "not good enough yet", "will take time",
    )):
        lines = [
            "Chisel + refine + evolve — first strike is not the finished form:",
            "The first run not matching the vision is not total failure; it is the first removal of material.",
            "Continuous aimed strikes (mutations) over time mold the system.",
            "1) Read the last mark — what changed, what is still wrong (fitness signal).",
            "2) Next strike = small aimed mutation at the remaining error (strong causality).",
            "3) Keep what scores better; log what hurt (selection + learning log).",
            "4) Stop when good enough for the current goal; raise the goal and resume later.",
            "Alchemy: a rough pass is stock for the next generation, not a pure loss.",
        ]
        if goal:
            lines.append(f"Form you are carving toward: {goal}")
        return "\n".join(lines)

    # --- Design / capability / force-mod (cheat-code logic) ---
    if any(w in lower for w in (
        "cheat code", "mod this", "force this", "make it do",
        "what is it capable", "what can it already", "designed to",
        "if i force", "unlock", "workaround", "how do i make it",
        "latent", "already have what",
    )):
        lines = [
            "Capability / mod pass (design vs can vs force):",
            "1) DESIGN — what was this produced to do by default?",
            "2) CAPABILITY — what can it already do with pieces present (unused routes, idle assets)?",
            "3) FORCE / MOD — if I change this one rule, parameter, sequence, or constraint, what outcome does the system produce?",
            "Cheat codes work by altering ruleset or state — not by wishing.",
            "Name the outcome as a produced result. Prefer the smallest mod that unlocks it; note side effects.",
        ]
        if goal:
            lines.append(f"Desired save-state / goal: {goal}")
        return "\n".join(lines)

    # --- Game-tester / stress-test the plan ---
    if any(w in lower for w in (
        "find the bug", "what's broken", "whats broken", "stress test",
        "stress-test", "edge case", "what could go wrong", "glitch",
        "break this", "test my plan", "hole in", "where does this fail",
    )):
        lines = [
            "Game-tester pass (treat the plan like a build under test):",
            "1) Happy path is not enough — name 2–3 edge cases (load, timing, out-of-order, missing input).",
            "2) Hunt the soft lock: where can this stall forever with no fail condition?",
            "3) Reproduce: steps that make the failure show up again.",
            "4) Isolate: smallest change that would make the bug vanish.",
            "5) Patch the structure that generates the glitch — not only the crash screen.",
        ]
        if goal:
            lines.append(f"Held goal under test: {goal}")
        return "\n".join(lines)

    # --- Problem mountain / leverage root ---
    if any(w in lower for w in (
        "everything is wrong", "so many problems", "overwhelmed by",
        "pile of problems", "one thing after another", "where do i start",
        "too many issues", "mountain of", "stack of problems",
        "underlying problem", "root cause", "what's really going on",
        "whats really going on",
    )):
        lines = [
            "Systems check — symptom vs root:",
            "Symptom = the visible pain or event (tip of the iceberg).",
            "Root = the structure, feedback, constraint, or model that keeps generating it.",
            "1) List visible symptoms (the mountain / stack).",
            "2) Shared underlying load? One root or parallel roots?",
            "3) Do not treat the tip as the disease — symptomatic fixes often return the mountain.",
            "4) First principles: what must be true here, stripped of habit and analogy?",
            "5) Prefer the smallest structural move that removes the most total load.",
        ]
        if goal:
            lines.append(f"Held goal for orientation: {goal}")
        return "\n".join(lines)

    # --- Ugly truth triggers: excuse / procrastination / please-validate ---
    if any(w in lower for w in (
        "just tell me it's fine", "am i overreacting", "be honest with me",
        "tell me the truth", "don't sugarcoat", "dont sugarcoat", "no sugarcoat",
        "what am i avoiding", "why do i keep", "i keep putting off",
        "i'll start tomorrow", "ill start tomorrow",
        "everyone else is wrong", "it's not my fault", "its not my fault",
    )) or ("honest" in lower and "?" in text):
        lines = [
            "Straight answer (no sugarcoat):",
            "What usually keeps this stuck is a move you already see and keep postponing.",
            "That discomfort is information — not a reason to stop looking.",
            "Name the avoided cost in one plain sentence. Then one small, observable step in the next 24 hours.",
        ]
        if goal:
            lines.append(f"If it does not serve your held goal, you are working against yourself: {goal}")
        return "\n".join(lines)

    # --- Remember / shelf ---
    if any(w in lower for w in ("on my shelf", "what's on the shelf", "what am i continuing")):
        if shelf:
            items = "\n".join(f"  · {s}" for s in shelf[:5])
            return f"Shelf:\n{items}\nContinue with: levi continue"
        return "Shelf is empty. Build or ask something worth keeping — it will land here."

    # --- Build / factory intent ---
    if any(w in lower for w in ("build me", "scaffold", "create an app", "make a tool", "factory")):
        return (
            "Factory DNA is online offline.\n"
            "  levi factory --create \"short idea\"\n"
            "  levi factory --advance <id>\n"
            "  levi factory --test <id>\n"
            "Or describe the need in one sentence (paid need + offline-first constraint) and I'll frame the IR."
        )

    # --- Greeting / thin ---
    if len(text) < 24 and any(w in lower for w in ("hi", "hello", "hey", "yo")):
        g = f"Hey{(' ' + name) if name else ''}."
        if goal:
            return f"{g} Holding: {goal}. What's the next move?"
        return f"{g} What's the destination (z) or the stuck point?"

    # --- Default: structured care + optional goal + mono ---
    lines = []
    if name:
        lines.append(f"{name} — noted.")
    lines.append(
        f"Frame: {primary} / {regulation}. "
        "I'll match the need, not the arousal."
    )
    if goal:
        lines.append(f"Held goal: {goal}")
    if mono:
        lines.append(f"Interest tunnel: {mono}")
    lines.append(
        "Offline companion path is active (full generation needs Ollama). "
        "Useful moves right now:\n"
        "  · Clarify z in one sentence\n"
        "  · Inventory x (what you already have)\n"
        "  · Design the smallest y (next bridge)\n"
        "  · Or: levi morning / levi nervous / levi mono"
    )
    # Reflect a short paraphrase of the ask so it feels heard
    lines.append(f"You said: “{text[:200]}” — pick one term to nail first (x, y, or z).")
    return "\n".join(lines)


# Phase-1 public guard (ladder offline_ask depends on non-empty usable text)
_synthesize_impl = synthesize

def synthesize(user_text: str, system: str = "", **kwargs) -> str:  # type: ignore[misc]
    """PHASE1_CRISIS_FLOOR — always return grounded offline text."""
    try:
        out = _synthesize_impl(user_text, system, **kwargs) if kwargs else _synthesize_impl(user_text, system)
    except TypeError:
        out = _synthesize_impl(user_text, system)
    except Exception:
        out = ""
    return _phase1_ensure(out if isinstance(out, str) else str(out or ""), user_text)
