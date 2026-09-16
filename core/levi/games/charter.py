"""The Fair Play Charter — honest-design rules for every LEVI game.

Born from the games hunt wave (arch-games-predatory-monetization-trades,
arch-games-stadia-vanishing-library): each predatory trade the industry
refuses to give up is inverted here into a machine-checkable rule. A game
that fails the charter is not a LEVI game.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple


# ---------------------------------------------------------------------------
# Manifests
# ---------------------------------------------------------------------------


@dataclass
class GameManifest:
    """A game's declared design. Every field defaults to the honest side."""

    name: str
    # --- the sly trades, all defaulted OFF ---
    has_paid_randomness: bool = False  # loot boxes, gacha, paid RNG
    has_streak_punishment: bool = False  # miss a day, lose your streak
    has_fomo_timers: bool = False  # countdown pressure, limited windows
    has_pay_for_hints: bool = False  # monetized help
    requires_network: bool = False  # always-online requirement
    # --- the honest guarantees, all defaulted ON ---
    progress_portable: bool = True  # saves exportable by the player
    odds_declared: bool = True  # any chance is stated honestly
    hints_free: bool = True  # help is never a purchase
    # --- wave-006: the ownership and transparency trades, defaulted honest ---
    has_time_limited_content: bool = False  # battle-pass FOMO seasons
    has_randomness: bool = False  # the game involves chance at all
    has_audit_hook: bool = False  # an empirical odds audit (prove-the-odds)


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CharterRule:
    id: str
    title: str
    inversion: str  # which sly trade this rule inverts
    check: Callable[[GameManifest], bool] = field(repr=False)

    def passes(self, manifest: GameManifest) -> bool:
        try:
            return bool(self.check(manifest))
        except Exception:
            return False


RULES: Tuple[CharterRule, ...] = (
    CharterRule(
        id="no_paid_randomness",
        title="No paid randomness",
        inversion="Loot boxes / gacha / paid RNG: never sell chance.",
        check=lambda m: not m.has_paid_randomness,
    ),
    CharterRule(
        id="no_streak_punishment",
        title="No streak punishment",
        inversion="Daily-streak engagement bait: missing a day must never "
        "destroy progress or lock the player out.",
        check=lambda m: not m.has_streak_punishment,
    ),
    CharterRule(
        id="no_fomo_timers",
        title="No FOMO timers",
        inversion="Countdown pressure and artificial scarcity windows.",
        check=lambda m: not m.has_fomo_timers,
    ),
    CharterRule(
        id="hints_are_free",
        title="Hints are free",
        inversion="Pay-for-hints in puzzle games: help is a kindness, not a purchase.",
        check=lambda m: m.hints_free and not m.has_pay_for_hints,
    ),
    CharterRule(
        id="offline_playable",
        title="Playable offline",
        inversion="Always-online requirements that turn purchases into "
        "revocable streams (the Stadia vanishing-library trade).",
        check=lambda m: not m.requires_network,
    ),
    CharterRule(
        id="progress_portable",
        title="Progress is portable",
        inversion="Hostage saves: the player can export and keep every "
        "save as their own file, forever.",
        check=lambda m: m.progress_portable,
    ),
    CharterRule(
        id="honest_odds",
        title="Honest odds",
        inversion="Hidden RNG economics: wherever chance exists, the odds "
        "are stated plainly.",
        check=lambda m: m.odds_declared,
    ),
    CharterRule(
        id="no_kill_switch",
        title="No kill switch",
        inversion="The Stadia/OnLive trade: a dead server must never take "
        "the game with it. The game is fully playable offline from local "
        "files, and saves stay player-owned plain text.",
        check=lambda m: not m.requires_network,
    ),
    CharterRule(
        id="no_synthetic_scarcity",
        title="No synthetic scarcity",
        inversion="Battle-pass / FOMO-season trade: time-limited content "
        "that manufactures urgency. Nothing in the game may expire.",
        check=lambda m: not m.has_time_limited_content,
    ),
    CharterRule(
        id="odds_are_public",
        title="Odds are public",
        inversion="The loot-box trade: randomness is only fair when its "
        "odds are declared AND empirically auditable (a prove-the-odds "
        "hook the player can run).",
        check=lambda m: not m.has_randomness or (m.odds_declared and m.has_audit_hook),
    ),
)


# ---------------------------------------------------------------------------
# Checking
# ---------------------------------------------------------------------------


def check_manifest(manifest: GameManifest) -> List[Dict[str, str]]:
    """Return the list of violated rules (empty = the game is fair)."""
    violations = []
    for rule in RULES:
        if not rule.passes(manifest):
            violations.append(
                {
                    "rule": rule.id,
                    "title": rule.title,
                    "inversion": rule.inversion,
                }
            )
    return violations


def is_fair(manifest: GameManifest) -> bool:
    """True when the manifest passes every charter rule."""
    return not check_manifest(manifest)


def charter_text() -> str:
    """Human-readable charter for the CLI and the warehouse shelf."""
    lines = [
        "THE FAIR PLAY CHARTER",
        "Every LEVI game obeys these rules. A game that breaks one is not a LEVI game.",
        "",
    ]
    for i, rule in enumerate(RULES, 1):
        lines.append("%d. %s" % (i, rule.title))
        lines.append("   Inverts: %s" % rule.inversion)
    lines.append("")
    lines.append("Free to produce, free to play, fair by construction.")
    return "\n".join(lines)
