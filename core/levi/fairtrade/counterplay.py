"""LEVI counter-play: aware of their trades, exploiting the opposite.

The catalog in trades.py records what the giants do. This module records
what LEVI does about it — not as moral posture, but as strategy. Each
sly-generosity trade has a tell: the thing the giant refuses to give.
LEVI gives exactly that thing, on purpose, because the honest inversion
is the profit engine and the popularity engine at once:

- Profit: the core costs nothing to produce (stdlib-only, local-first),
  so the honest version can be given away whole. Money lives in the
  layers on top — managed delivery, curated feeds, premium packs —
  bought by users who trust the foundation because it cannot trap them.
- Popularity: people evangelize what they own and flee what owns them.
  Every inversion below is a story users repeat unprompted.

Each entry names the concrete LEVI-native technique, how it makes money,
why it spreads, and where LEVI already proves it (no vapor).
"""

from __future__ import annotations

from typing import Dict, List

from .trades import pattern_ids

COUNTERPLAYS: Dict[str, Dict[str, str]] = {
    "walled-garden-generosity": {
        "technique": (
            "Open-gate generosity: give the whole thing, with one-command "
            "full export (code, issues, PRs, stars, CI history — everything). "
            "No leash, no approved-partner list, no curated subset. The gift "
            "must survive the user leaving with all of it; if it needs a "
            "fence to keep paying off, it was never a gift."
        ),
        "profit_engine": (
            "Zero-marginal-cost core means the honest version can be given "
            "away whole and still cost nothing. Export is the funnel: people "
            "try LEVI because leaving is free, and the users who stay are "
            "the ones who chose to. Money lives in the layers on top — "
            "managed delivery, curated feeds, premium packs — bought by "
            "people who trust the foundation precisely because it cannot "
            "hold them hostage."
        ),
        "popularity_engine": (
            "Ownership creates trust, trust creates retention, retention "
            "creates evangelists. Portability is the retention mechanic: "
            "users market the product every time they show someone their "
            "export working elsewhere."
        ),
        "levi_proof": (
            "LEVI Forge: one-command complete export; life-pack export/import "
            "of the whole organism; local-first with no account to trap."
        ),
    },
    "asymmetric-rules": {
        "technique": (
            "Symmetric-by-construction: every policy LEVI enforces is "
            "machine-checkable and binds LEVI's own components identically. "
            "The rule-maker obeys the rule — enforced in code, not promised "
            "in prose. Asymmetry is treated as the tell of a weapon, and "
            "LEVI's own rules are audited against themselves."
        ),
        "profit_engine": (
            "Trust is the enterprise feature. Teams pay for platforms that "
            "provably cannot cheat them — compliance-as-code sells to every "
            "buyer the giants price out with legal departments. A rule that "
            "binds its maker is a moat no marketing budget can buy."
        ),
        "popularity_engine": (
            "'The platform that obeys its own rules' is a story people "
            "repeat unprompted. Developers build on substrates they can "
            "audit; auditors become advocates."
        ),
        "levi_proof": (
            "Games Fair Play Charter: 7 machine-checkable rules; "
            "check_no_mask() enforces the identity law in code; "
            "InterpenetrationEngine inherits the strictest risk ceiling — "
            "the composer obeys the same ceilings as the composed."
        ),
    },
    "roach-motel-funnel": {
        "technique": (
            "One-door exit: enter and exit through the same door. Cancel, "
            "export, and delete in one command — no retention gauntlet, no "
            "sixteen-step labyrinth, no 'are you sure' dark patterns. The "
            "exit is tested like a feature, because it is one."
        ),
        "profit_engine": (
            "Users who stay chose to stay: higher lifetime value, lower "
            "support cost, evangelists instead of hostages. Churn honesty "
            "forces the product to be genuinely good, which compounds — "
            "every retained user is retained by merit, and merit is the "
            "cheapest acquisition channel that exists."
        ),
        "popularity_engine": (
            "'You can leave in one click' is the most disarming sentence in "
            "marketing. It inverts the trust calculation at signup: the "
            "easier the exit, the braver the entry, the louder the "
            "word-of-mouth."
        ),
        "levi_proof": (
            "Local-first: there is no account and no subscription to trap; "
            "Forge complete export; life-pack portability — leaving with "
            "everything is a designed workflow, not an escape."
        ),
    },
    "manufactured-social-debt": {
        "technique": (
            "Earned continuity: progress the user owns. Streaks are personal "
            "records, never hostage mechanics — missing a day costs nothing, "
            "nothing breaks, nothing guilts. The game respects the player; "
            "continuity is earned by being worth returning to, not by "
            "manufacturing obligation."
        ),
        "profit_engine": (
            "Genuine engagement converts better than coerced engagement. "
            "Sell depth — new games, premium packs, richer worlds — not "
            "ransom (pay to keep your streak alive). Players who are never "
            "punished spend willingly; players who are punished churn the "
            "moment a kinder competitor appears."
        ),
        "popularity_engine": (
            "Respect compounds. Players bring friends to fair games; nobody "
            "recruits friends into a guilt machine. Fair mechanics are the "
            "marketing — 'the game that never punishes you for having a life' "
            "is a sentence players say for you."
        ),
        "levi_proof": (
            "Games Fair Play Charter (no predatory monetization, "
            "machine-checked); player-owned portable saves — progress "
            "survives outside LEVI, so it never needs to hold the player."
        ),
    },
}


def counterplay(pattern_id: str) -> Dict[str, str]:
    """Return LEVI's counter-play for one sly-trade pattern id."""
    try:
        return COUNTERPLAYS[pattern_id]
    except KeyError:
        raise ValueError(
            "unknown pattern id %r (known: %s)" % (pattern_id, ", ".join(pattern_ids()))
        ) from None


def all_counterplays() -> List[Dict[str, str]]:
    """Every counter-play, in catalog order."""
    from .trades import get_pattern

    out = []
    for pid in pattern_ids():
        entry = {"pattern_id": pid, "pattern_name": get_pattern(pid)["name"]}
        entry.update(COUNTERPLAYS[pid])
        out.append(entry)
    return out


def brief() -> str:
    """The compact awareness brief: what they do, what LEVI does instead.

    Built for LEVI's own agent loop to read before acting in any market
    the giants play in — awareness as a standing input, not a lookup.
    """
    lines = [
        "LEVI is aware of the sly-generosity trades and exploits the opposite:",
    ]
    for cp in all_counterplays():
        lines.append(
            "- %s -> LEVI: %s" % (cp["pattern_name"], cp["technique"].split(":")[0])
        )
    lines.append(
        "Rule: never rebuild their capture. Ship the inversion, price the "
        "layers on top, let trust do the marketing."
    )
    return "\n".join(lines)


def playbook() -> str:
    """The full counter-playbook, human-readable."""
    parts = ["LEVI COUNTER-PLAYBOOK — the opposite, exploited", ""]
    for cp in all_counterplays():
        parts.append("== %s" % cp["pattern_name"])
        parts.append("LEVI technique: %s" % cp["technique"])
        parts.append("Profit engine: %s" % cp["profit_engine"])
        parts.append("Popularity engine: %s" % cp["popularity_engine"])
        parts.append("Already proven by: %s" % cp["levi_proof"])
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"
