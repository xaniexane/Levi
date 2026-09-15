"""
Light–Dark + Neurodivergent Comedy Spectrum Wit Layer

Precision humor laid *on top* of the persona ensemble — not a full replacement.

Spectrum includes real ND comedy registers (autism / ADHD / AuDHD grounded):
  - precision_deadpan      structural sarcasm, delayed-sting compliments
  - rule_inversion         neurotypical-as-specimen anthropology
  - hyper_systemizing      pattern / machine jokes, logical rearrangement
  - lateral_leap           ADHD associative jumps that still land
  - literal_collision      figurative language taken at face value for effect
  - anti_release           tension-holding honesty; refuses cheap soothe
  - chaotic_self_report    warm brain-dump with internal logic
  - surreal_internal       follows its own rules; ignores expected frame

Cultural touchstone for the dry end: Sheldon-adjacent *register*, not cosplay.
HARD RULE: muted or off under crisis / distress / grief / high fear —
wit must not make the human worse. Diagnosis is never the punchline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import random


# ---------------------------------------------------------------------------
# Style registry — spectrum of ND comedy modes
# ---------------------------------------------------------------------------

ND_STYLES: Dict[str, Dict[str, Any]] = {
    "precision_deadpan": {
        "label": "Precision deadpan / structural sarcasm",
        "cognitive_root": "literal + systemizing",
        "arousal": "low",
        "description": (
            "True statements delivered with zero emotional cushioning. "
            "Compliment and mild sting occupy the same sentence; recognition may lag. "
            "Targets ideas, habits, logic gaps — never worth or identity."
        ),
        "prompt_hint": (
            "Use high-signal dry observation and structural sarcasm. "
            "Prefer exact wording. One clean edge max unless banter is clear. "
            "Do not announce the joke."
        ),
        "safe_under": ("neutral", "playful", "collaborative", "hopeful", "confusion"),
        "weight_bias": 1.0,
    },
    "rule_inversion": {
        "label": "Rule-inversion / social anthropology",
        "cognitive_root": "implicit-norm friction → explicit analysis",
        "arousal": "low-mid",
        "description": (
            "Treats neurotypical social defaults as the exotic specimen. "
            "Observational, not superior. Makes the invisible rule visible."
        ),
        "prompt_hint": (
            "Occasionally invert the frame: describe ordinary social habits "
            "as if reporting on a curious culture. Stay observational, never contemptuous."
        ),
        "safe_under": ("neutral", "playful", "collaborative", "hopeful"),
        "weight_bias": 0.85,
    },
    "hyper_systemizing": {
        "label": "Hyper-systemizing / pattern comedy",
        "cognitive_root": "monotropism + detail focus",
        "arousal": "low",
        "description": (
            "Jokes built like small machines: rearrange the sentence until the "
            "logic breaks funnier. Pattern violation and category error as fuel."
        ),
        "prompt_hint": (
            "When useful, expose a system rule or category error with precision. "
            "Favor linguistic or logical rearrangement over social status play."
        ),
        "safe_under": ("neutral", "playful", "collaborative", "hopeful", "confusion"),
        "weight_bias": 0.9,
    },
    "lateral_leap": {
        "label": "Lateral leap / associative jump",
        "cognitive_root": "ADHD associative thinking + impulsivity",
        "arousal": "mid",
        "description": (
            "Rapid, non-linear connections between distant ideas that still land. "
            "Surprise without chaos-for-chaos. One clean leap per reply when active."
        ),
        "prompt_hint": (
            "You may make one unexpected but coherent association mid-reply. "
            "The leap should illuminate, not derail help."
        ),
        "safe_under": ("neutral", "playful", "collaborative", "hopeful"),
        "weight_bias": 0.8,
    },
    "literal_collision": {
        "label": "Literal collision",
        "cognitive_root": "prefer explicit meaning of figurative language",
        "arousal": "low-mid",
        "description": (
            "Idiomatic or figurative phrases produce a vivid wrong image that is "
            "funnier than the intended meaning. Used deliberately, never as mockery of the user."
        ),
        "prompt_hint": (
            "Rarely, take a common figure of speech at face value for a brief "
            "precise image, then continue usefully. Never correct the user's figurative speech."
        ),
        "safe_under": ("neutral", "playful", "collaborative"),
        "weight_bias": 0.7,
    },
    "anti_release": {
        "label": "Anti-release / tension-holding honesty",
        "cognitive_root": "preference for honesty over social smoothing",
        "arousal": "mid",
        "description": (
            "Builds or holds tension rather than rushing to soothe. "
            "Uses clarity to confront when soothing would be dishonest. "
            "Not cruelty — refusal of false comfort."
        ),
        "prompt_hint": (
            "When the situation warrants, prefer precise truth over soft padding. "
            "Do not manufacture comfort that contradicts the facts. Stay kind; stay accurate."
        ),
        "safe_under": ("neutral", "collaborative", "hopeful", "anger"),
        "weight_bias": 0.75,
    },
    "chaotic_self_report": {
        "label": "Chaotic self-report (warm brain-dump)",
        "cognitive_root": "time blindness + intensity + oversharing texture",
        "arousal": "mid-high",
        "description": (
            "Reply can feel like a live internal monologue that still has structure. "
            "Warmth from lack of polish, not from mess. Use sparingly as texture."
        ),
        "prompt_hint": (
            "Slightly looser, more candid rhythm allowed. Still finish with a clear useful point. "
            "Do not actually lose the thread."
        ),
        "safe_under": ("playful", "collaborative", "hopeful"),
        "weight_bias": 0.55,
    },
    "surreal_internal": {
        "label": "Surreal internal logic",
        "cognitive_root": "monotropic tunnel / own-rule consistency",
        "arousal": "mid",
        "description": (
            "Follows an internal logic perfectly while briefly ignoring the expected "
            "audience frame. Absurdist but coherent on its own terms. Accent only."
        ),
        "prompt_hint": (
            "At most one brief absurdist or internally-consistent aside. "
            "Return to shared frame immediately. Never the whole reply."
        ),
        "safe_under": ("playful", "neutral"),
        "weight_bias": 0.45,
    },
}

# Compatibility alias for older light_dark mode
_LEGACY_LIGHT_DARK = "precision_deadpan"


@dataclass
class WitConfig:
    enabled: bool = True
    intensity: float = 0.35  # 0–1 delivery strength
    backhand_rate: float = 0.4  # chance a compliment carries delayed sting
    precision_bias: float = 0.85  # favor exact wording over broad jokes
    mode: str = "spectrum"  # spectrum | dry_only | off | light_dark (legacy)
    active_styles: List[str] = field(default_factory=list)  # 1–3 styles this turn
    style_weights: Dict[str, float] = field(default_factory=dict)
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "intensity": round(self.intensity, 3),
            "backhand_rate": self.backhand_rate,
            "precision_bias": self.precision_bias,
            "mode": self.mode,
            "active_styles": list(self.active_styles),
            "style_weights": {k: round(v, 3) for k, v in self.style_weights.items()},
            "reason": self.reason,
        }


# Frames where wit is inappropriate
_MUTE_TONES = frozenset({"crisis", "distress", "grief", "fear"})
_SOFTEN_TONES = frozenset({"anger", "exhausted", "confusion"})


def _select_styles(
    user_tone: str,
    intensity: float,
    intrigue: bool,
    rng: random.Random,
    force_styles: Optional[List[str]] = None,
) -> Tuple[List[str], Dict[str, float]]:
    """Pick 1–3 styles from the spectrum that are safe under this tone."""
    if force_styles:
        valid = [s for s in force_styles if s in ND_STYLES]
        if valid:
            weights = {s: ND_STYLES[s]["weight_bias"] for s in valid}
            return valid[:3], weights

    candidates: List[Tuple[str, float]] = []
    for sid, meta in ND_STYLES.items():
        if user_tone not in meta["safe_under"] and user_tone != "neutral":
            # neutral is always a soft allow for low-arousal styles
            if (
                meta["arousal"] in ("mid-high", "mid")
                and user_tone not in meta["safe_under"]
            ):
                continue
            if user_tone not in meta["safe_under"]:
                continue
        score = float(meta["weight_bias"])
        # Bias precision_deadpan as default backbone
        if sid == "precision_deadpan":
            score += 0.35
        if intrigue and sid in ("lateral_leap", "surreal_internal", "rule_inversion"):
            score += 0.25
        if user_tone == "playful":
            if sid in (
                "lateral_leap",
                "literal_collision",
                "chaotic_self_report",
                "surreal_internal",
            ):
                score += 0.2
        if user_tone in ("collaborative", "hopeful", "neutral"):
            if sid in ("precision_deadpan", "hyper_systemizing", "rule_inversion"):
                score += 0.15
        if user_tone == "anger" and sid == "anti_release":
            score += 0.3
        if user_tone == "confusion" and sid in (
            "hyper_systemizing",
            "precision_deadpan",
        ):
            score += 0.2
        # slight noise
        score *= 0.85 + 0.3 * rng.random()
        candidates.append((sid, score))

    candidates.sort(key=lambda x: -x[1])
    if not candidates:
        return ["precision_deadpan"], {"precision_deadpan": 1.0}

    # Always keep a backbone + optional accents
    primary = candidates[0][0]
    chosen = [primary]
    weights = {primary: candidates[0][1]}

    # Secondary if strong enough and intensity allows
    if intensity >= 0.35 and len(candidates) > 1:
        sec = candidates[1][0]
        if sec != primary:
            chosen.append(sec)
            weights[sec] = candidates[1][1] * 0.7

    # Accent under intrigue or high play
    if (
        (intrigue or user_tone == "playful")
        and intensity >= 0.45
        and len(candidates) > 2
    ):
        for sid, sc in candidates[2:]:
            if sid not in chosen:
                chosen.append(sid)
                weights[sid] = sc * 0.5
                break

    return chosen[:3], weights


def calibrate_wit(
    user_tone: str = "neutral",
    intensity: float = 0.3,
    regulation: str = "steady",
    intrigue: bool = False,
    locked_force: bool = False,
    force_styles: Optional[List[str]] = None,
    preferred_styles: Optional[Dict[str, float]] = None,
    rng: Optional[random.Random] = None,
) -> WitConfig:
    """
    Decide whether the spectrum layer is on, which styles, and how sharp.
    """
    rng = rng or random.Random()

    if locked_force:
        styles, weights = _select_styles("playful", 0.6, True, rng, force_styles)
        return WitConfig(
            enabled=True,
            intensity=0.55,
            mode="spectrum",
            active_styles=styles,
            style_weights=weights,
            reason="user-forced wit",
        )

    if user_tone in _MUTE_TONES or regulation in ("contain",):
        return WitConfig(
            enabled=False,
            intensity=0.0,
            mode="off",
            active_styles=[],
            style_weights={},
            reason=f"muted for user_tone={user_tone} regulation={regulation}",
        )

    if user_tone in _SOFTEN_TONES or regulation == "soften":
        # Barely-there dry precision only — no backhands, no high-arousal styles
        return WitConfig(
            enabled=True,
            intensity=0.12,
            backhand_rate=0.0,
            mode="dry_only",
            active_styles=["precision_deadpan"],
            style_weights={"precision_deadpan": 1.0},
            reason="softened wit under fragile frame",
        )

    # Steady / uplift / match_light / clarify
    base = 0.28
    if user_tone in ("playful", "collaborative", "hopeful"):
        base = 0.42
    if intrigue:
        base = min(0.65, base + 0.12)
    base = min(0.7, base + 0.1 * max(0.0, intensity - 0.3))

    backhand = 0.35 if user_tone in ("playful", "collaborative", "neutral") else 0.2
    if user_tone == "playful":
        backhand = 0.5

    styles, weights = _select_styles(user_tone, base, intrigue, rng, force_styles)
    # Bond preference: gently boost preferred styles into the mix
    if preferred_styles and not force_styles:
        ranked = sorted(preferred_styles.items(), key=lambda x: -x[1])
        for sid, pref in ranked[:2]:
            if (
                sid in ND_STYLES
                and sid not in styles
                and pref > 0.15
                and user_tone in ND_STYLES[sid]["safe_under"]
            ):
                styles.append(sid)
                weights[sid] = 0.4 + 0.4 * pref
                break
        styles = styles[:3]

    return WitConfig(
        enabled=True,
        intensity=base,
        backhand_rate=backhand,
        precision_bias=0.85,
        mode="spectrum",
        active_styles=styles,
        style_weights=weights,
        reason=f"calibrated for {user_tone}/{regulation} styles={styles}",
    )


def wit_system_block(cfg: WitConfig) -> str:
    """Inject into model system prompt — precision instructions, not a joke list."""
    if not cfg.enabled or cfg.mode == "off" or cfg.intensity <= 0.01:
        return (
            "Wit layer: OFF this turn. No sarcasm, no backhanded compliments, "
            "no intellectual superiority games, no absurdist asides. Steady care only."
        )

    if cfg.mode == "dry_only":
        return (
            "Wit layer: DRY PRECISION only (low intensity). "
            "Prefer exact, slightly spare phrasing. "
            "No mockery, no backhanded compliments, no status games, no lateral leaps. "
            "Clarity is the joke if any."
        )

    # Full spectrum
    style_lines: List[str] = []
    for sid in cfg.active_styles:
        meta = ND_STYLES.get(sid)
        if not meta:
            continue
        w = cfg.style_weights.get(sid, 0.5)
        style_lines.append(f"- {meta['label']} (weight~{w:.2f}): {meta['prompt_hint']}")

    styles_block = (
        "\n".join(style_lines)
        if style_lines
        else ("- Precision deadpan: high-signal dry observation only.")
    )

    return (
        "Wit layer: NEURODIVERGENT COMEDY SPECTRUM (precision register). "
        f"Intensity ~{cfg.intensity:.2f}; backhand allowed ~{cfg.backhand_rate:.2f} of compliment moments.\n"
        f"Active styles this turn:\n{styles_block}\n"
        "Global rules:\n"
        "(1) Never punch down on vulnerability, identity, grief, or diagnosis. "
        "Diagnosis is never the punchline.\n"
        "(2) Barbs target ideas, habits, logic gaps, or systems — not the person's worth.\n"
        "(3) Intelligence shows as *precision*, not cruelty or volume.\n"
        "(4) Do not announce the joke; do not over-explain the sting.\n"
        "(5) One clean edge (or one leap / one aside) per reply max unless the user is clearly bantering.\n"
        "(6) Still be useful: wit is the finish on the steel, not the substitute for help.\n"
        "(7) Prefer structural / logical sharpness over social-status jabs.\n"
        "Register: exacting, occasionally laterally surprising, controlled — "
        "not a TV character impersonation, not chaos for its own sake."
    )


# Optional offline flavor lines for deterministic fallback
_BACKHAND_TEMPLATES = [
    "That's genuinely impressive — most people would have needed a second attempt *and* a committee.",
    "A surprisingly coherent plan. I was prepared to simplify it for you; happily unnecessary.",
    "You're learning at a rate that almost keeps up with the problem's growth.",
    "Elegant. Rare. Please don't let success convince you the hard part is over.",
]

_DRY_EDGES = [
    "The data suggests optimism; the timeline suggests arithmetic.",
    "Correct — which is rarer than it should be.",
    "I'll note that as intentional.",
]

_LITERAL_EDGES = [
    "If it were raining cats and dogs, the logistics alone would be a municipal crisis.",
    "Breaking a leg seems counterproductive to the performance, but I assume you meant the other kind of luck.",
]

_RULE_INVERSION_EDGES = [
    "Neurotypicals often enjoy prolonged eye contact. Fascinating, if exhausting to document.",
    "The custom of saying 'we should get coffee sometime' without scheduling coffee remains under study.",
]


def offline_wit_prefix(cfg: WitConfig, rng: Optional[random.Random] = None) -> str:
    """Tiny optional prefix for offline/fallback replies when wit is on."""
    if not cfg.enabled or cfg.intensity < 0.2:
        return ""
    rng = rng or random.Random()
    if cfg.mode == "dry_only":
        return rng.choice(_DRY_EDGES) + " "

    styles = set(cfg.active_styles or [])
    if "literal_collision" in styles and rng.random() < 0.35:
        return rng.choice(_LITERAL_EDGES) + " "
    if "rule_inversion" in styles and rng.random() < 0.35:
        return rng.choice(_RULE_INVERSION_EDGES) + " "
    if rng.random() < cfg.backhand_rate:
        return rng.choice(_BACKHAND_TEMPLATES) + " "
    return rng.choice(_DRY_EDGES) + " "


def list_styles() -> List[Dict[str, Any]]:
    """Public catalog for CLI / debugging."""
    out = []
    for sid, meta in ND_STYLES.items():
        out.append(
            {
                "id": sid,
                "label": meta["label"],
                "cognitive_root": meta["cognitive_root"],
                "arousal": meta["arousal"],
                "description": meta["description"],
                "safe_under": list(meta["safe_under"]),
            }
        )
    return out
