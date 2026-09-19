"""fair_play_charter — machine-checkable honest-design rules for games.

Studied from: games-hunt-20260916-0022/report.md (Find 3 — honest inversion).

The load-bearing idea: honest game design should not be a vibe, it
should be a checklist a machine can run. Instead of trusting a
studio's marketing, you feed the game's declared design into the
charter and get a verdict per rule, with the evidence quoted.

LEVI's take: ``FairPlayCharter`` holds seven rules — no paid
randomness, no streak punishment, no FOMO timers, declared honest
odds, free hints, offline playable, portable progress. Each rule is a
``Rule`` with a ``check(spec)`` function that inspects a plain-dict
game spec (drop tables, timers, monetization flags, expiry policies)
and returns a ``Verdict``: pass/fail plus the exact spec fragment
that decided it. ``evaluate`` runs the whole charter and produces a
report a player can read before installing anything.

Honest limits: the charter checks *declared* design, not shipped
behavior — a game can lie in its spec, and no static check catches
server-side behavior. Treat a passing charter as "designed honestly
on paper", not as proof of honest operation.

This is an original, from-scratch implementation for LEVI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

ORIGIN = "levi-revival/fair-play-charter"


@dataclass
class Verdict:
    """One rule's decision, with the evidence that decided it."""

    rule: str
    passed: bool
    evidence: str
    detail: str = ""


@dataclass
class Rule:
    """A named, checkable honest-design rule."""

    name: str
    description: str
    check: Callable[[Dict[str, Any]], Verdict]

    def run(self, spec: Dict[str, Any]) -> Verdict:
        return self.check(spec)


def _verdict(name: str, passed: bool, evidence: str, detail: str = "") -> Verdict:
    return Verdict(rule=name, passed=passed, evidence=evidence, detail=detail)


def _rule_no_paid_randomness() -> Rule:
    def check(spec: Dict[str, Any]) -> Verdict:
        monet = spec.get("monetization", {})
        random_sales = monet.get("sells_random_outcomes", False)
        if random_sales:
            return _verdict(
                "no_paid_randomness",
                False,
                "monetization.sells_random_outcomes = true",
                "Players can pay for randomized rewards (loot boxes, gacha).",
            )
        return _verdict(
            "no_paid_randomness",
            True,
            "monetization.sells_random_outcomes = false",
        )

    return Rule(
        name="no_paid_randomness",
        description="No money may buy randomized outcomes.",
        check=check,
    )


def _rule_no_streak_punishment() -> Rule:
    def check(spec: Dict[str, Any]) -> Verdict:
        streaks = spec.get("streaks", {})
        if streaks.get("punishes_break", False):
            return _verdict(
                "no_streak_punishment",
                False,
                "streaks.punishes_break = true",
                "Breaking a streak costs the player progress or rewards.",
            )
        return _verdict(
            "no_streak_punishment",
            True,
            "streaks.punishes_break = false",
            "Streaks may celebrate; they never punish.",
        )

    return Rule(
        name="no_streak_punishment",
        description="Missing a day never costs progress.",
        check=check,
    )


def _rule_no_fomo_timers() -> Rule:
    def check(spec: Dict[str, Any]) -> Verdict:
        timers = spec.get("timers", [])
        expiring = [t for t in timers if t.get("expires_content", False)]
        if expiring:
            names = ", ".join(t.get("name", "?") for t in expiring)
            return _verdict(
                "no_fomo_timers",
                False,
                f"timers expiring content: {names}",
                "Limited-time pressure mechanics found.",
            )
        return _verdict("no_fomo_timers", True, "no timers expire content")

    return Rule(
        name="no_fomo_timers",
        description="No countdown that deletes unclaimed content.",
        check=check,
    )


def _rule_honest_odds_declared() -> Rule:
    def check(spec: Dict[str, Any]) -> Verdict:
        drops = spec.get("drop_tables", [])
        undeclared = [
            t.get("name", "?") for t in drops if not t.get("odds_published", False)
        ]
        if undeclared:
            return _verdict(
                "honest_odds_declared",
                False,
                f"drop tables without published odds: {', '.join(undeclared)}",
            )
        if not drops:
            return _verdict(
                "honest_odds_declared",
                True,
                "no randomized drops declared",
                "Nothing random to declare odds for.",
            )
        return _verdict(
            "honest_odds_declared",
            True,
            f"{len(drops)} drop table(s), all odds published",
        )

    return Rule(
        name="honest_odds_declared",
        description="Every random outcome publishes exact odds.",
        check=check,
    )


def _rule_hints_free() -> Rule:
    def check(spec: Dict[str, Any]) -> Verdict:
        hints = spec.get("hints", {})
        if hints.get("costs_money", False) or hints.get(
            "costs_premium_currency", False
        ):
            return _verdict(
                "hints_free",
                False,
                "hints cost money or premium currency",
                "Help is monetized.",
            )
        return _verdict("hints_free", True, "hints are free")

    return Rule(
        name="hints_free",
        description="Help and hints are never sold.",
        check=check,
    )


def _rule_offline_playable() -> Rule:
    def check(spec: Dict[str, Any]) -> Verdict:
        if spec.get("requires_online", False):
            return _verdict(
                "offline_playable",
                False,
                "requires_online = true",
                "Core play needs a server connection.",
            )
        return _verdict("offline_playable", True, "requires_online = false")

    return Rule(
        name="offline_playable",
        description="The game plays fully offline.",
        check=check,
    )


def _rule_progress_portable() -> Rule:
    def check(spec: Dict[str, Any]) -> Verdict:
        saves = spec.get("saves", {})
        if saves.get("exportable", False) and not saves.get("server_revocable", True):
            return _verdict(
                "progress_portable",
                True,
                "saves.exportable = true, saves.server_revocable = false",
            )
        return _verdict(
            "progress_portable",
            False,
            f"saves = {saves!r}",
            "Progress is not player-exportable or can be revoked server-side.",
        )

    return Rule(
        name="progress_portable",
        description="Progress exports to a player-owned file; no remote revoke.",
        check=check,
    )


def default_charter() -> "FairPlayCharter":
    charter = FairPlayCharter()
    for make in (
        _rule_no_paid_randomness,
        _rule_no_streak_punishment,
        _rule_no_fomo_timers,
        _rule_honest_odds_declared,
        _rule_hints_free,
        _rule_offline_playable,
        _rule_progress_portable,
    ):
        charter.add_rule(make())
    return charter


@dataclass
class FairPlayCharter:
    """The seven honest-design rules, run as one machine check."""

    rules: List[Rule] = field(default_factory=list)

    def add_rule(self, rule: Rule) -> None:
        self.rules.append(rule)

    def evaluate(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Run every rule against the spec; return a readable report."""
        verdicts = [rule.run(spec) for rule in self.rules]
        failed = [v for v in verdicts if not v.passed]
        return {
            "game": spec.get("title", "untitled"),
            "passed": not failed,
            "score": f"{len(verdicts) - len(failed)}/{len(verdicts)}",
            "verdicts": [
                {
                    "rule": v.rule,
                    "passed": v.passed,
                    "evidence": v.evidence,
                    "detail": v.detail,
                }
                for v in verdicts
            ],
            "failed_rules": [v.rule for v in failed],
        }
