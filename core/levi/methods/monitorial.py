"""Monitorial (Bell-Lancaster) instruction: the peer teach-back protocol.

Origin: the early-19th-century mass-schooling hack — one master teaches a
cadre of older pupils (**monitors**), who each drill a small group in turn:
recursive instruction with strict timing, role rotation, signals, and
regrouping by attainment. A single teacher could run a school of hundreds.
(Bell's claims of invention sit against Indian antecedents and competing
Bell/Lancaster accounts.)

What it is in LEVI: the recursion, inverted for *your* learning and bound
to the growth loop. To master X, you must teach it — the assistant plays
a sequence of pupils of increasing sophistication (naive -> sharp ->
hostile), each requiring you to re-explain. Teaching the "monitors" (the
AI personas) is the repetitio. For teams: the assistant trains the first
cohort of monitors, each trains a group, and the AI spot-checks every
branch for drift — the cascade, with fidelity auditing the original
lacked.

Honesty label: INSPIRATIONAL — this is a method for *cheap scale*, and its
history includes real pedagogical and disciplinary abuses. Revive the
recursion (teaching as the learning accelerator; cascade with auditing),
not the regimentation.

PROTOCOL LABEL: this module is a procedure the assistant runs with you
(or across your team), not an autonomous agent.

Deny-closed inputs: unknown pupil levels, rubric scores outside 0-5,
spot-checks of untrained monitors, and duplicate monitor names are
rejected with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

__all__ = ["PUPIL_LEVELS", "TeachBack", "Cascade"]

# The pupils get harder: naive accepts anything, sharp probes, hostile attacks.
PUPIL_LEVELS: tuple[str, ...] = ("naive", "sharp", "hostile")

PUPIL_BRIEFS: dict[str, str] = {
    "naive": "Knows nothing. Reward: plain language, no jargon, correct order of ideas.",
    "sharp": "Knows the basics. Reward: precision, edge cases, 'why' not just 'what'.",
    "hostile": "Knows enough to attack. Reward: steelmanned objections answered, limits admitted.",
}

RUBRIC: tuple[str, ...] = ("completeness", "clarity", "anticipates_objections")


class TeachBack:
    """Explain it to three pupils. Mastery = surviving all three."""

    def __init__(self, topic: str):
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError("topic must be a non-empty string")
        self.topic = topic.strip()
        self._explanations: dict[str, str] = {}
        self._scores: dict[str, dict[str, int]] = {}

    @staticmethod
    def _check_level(level: str) -> str:
        if level not in PUPIL_LEVELS:
            raise ValueError(
                f"unknown pupil level {level!r}; levels: {list(PUPIL_LEVELS)}"
            )
        return level

    def explain(self, level: str, text: str) -> None:
        """Record your explanation to the pupil at ``level``."""
        level = self._check_level(level)
        if not isinstance(text, str) or not text.strip():
            raise ValueError("explanation must be a non-empty string")
        self._explanations[level] = text.strip()

    def assess(
        self, level: str, completeness: int, clarity: int, anticipates_objections: int
    ) -> dict:
        """Score the explanation on the rubric (each 0..5)."""
        level = self._check_level(level)
        if level not in self._explanations:
            raise ValueError(f"no explanation recorded for the {level} pupil yet")
        scores = {
            "completeness": completeness,
            "clarity": clarity,
            "anticipates_objections": anticipates_objections,
        }
        for name, value in scores.items():
            if not isinstance(value, int) or not (0 <= value <= 5):
                raise ValueError(f"{name} must be an int 0..5, got {value!r}")
        self._scores[level] = scores
        return {"level": level, **scores, "mean": round(sum(scores.values()) / 3, 2)}

    def mastery(self) -> dict:
        """Have you taught all three pupils, and how did it go?"""
        per_level = {}
        for level in PUPIL_LEVELS:
            s = self._scores.get(level)
            per_level[level] = {
                "brief": PUPIL_BRIEFS[level],
                "explained": level in self._explanations,
                "assessed": s is not None,
                "mean": round(sum(s.values()) / 3, 2) if s else None,
            }
        means = [p["mean"] for p in per_level.values() if p["mean"] is not None]
        mastered = len(means) == len(PUPIL_LEVELS) and all(m >= 3 for m in means)
        return {
            "topic": self.topic,
            "levels": per_level,
            "mastered": mastered,
            "verdict": (
                "Mastered: the topic survived the naive, the sharp, and the hostile."
                if mastered
                else "Not yet: teach every pupil and score >= 3 on each rubric mean."
            ),
        }


@dataclass
class SpotCheck:
    at: str
    monitor: str
    score: int  # 0..5 fidelity of their teaching
    note: str


class Cascade:
    """The team cascade: train monitors, they train groups, audit the drift."""

    def __init__(self, topic: str):
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError("topic must be a non-empty string")
        self.topic = topic.strip()
        self._monitors: dict[str, dict] = {}  # name -> {trained: bool, groups: [...]}
        self._checks: list[SpotCheck] = []

    def train_monitor(self, name: str) -> None:
        """The assistant trains one monitor to mastery (via disputatio)."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("monitor name must be a non-empty string")
        name = name.strip()
        if name in self._monitors:
            raise ValueError(f"duplicate monitor: {name!r}")
        self._monitors[name] = {"trained": True, "groups": []}

    def assign(self, monitor: str, group: str) -> None:
        """A trained monitor takes a group."""
        if monitor not in self._monitors:
            raise ValueError(f"unknown monitor: {monitor!r} (train them first)")
        if not isinstance(group, str) or not group.strip():
            raise ValueError("group must be a non-empty string")
        group = group.strip()
        if group in self._monitors[monitor]["groups"]:
            raise ValueError(f"group {group!r} already assigned to {monitor!r}")
        self._monitors[monitor]["groups"].append(group)

    def spot_check(self, monitor: str, score: int, note: str = "") -> SpotCheck:
        """Audit fidelity at a cascade branch: is the teaching drifting?"""
        if monitor not in self._monitors:
            raise ValueError(f"unknown monitor: {monitor!r}")
        if not isinstance(score, int) or not (0 <= score <= 5):
            raise ValueError(f"spot-check score must be an int 0..5, got {score!r}")
        check = SpotCheck(
            at=datetime.now().isoformat(timespec="seconds"),
            monitor=monitor,
            score=score,
            note=note or "",
        )
        self._checks.append(check)
        return check

    def drift_report(self) -> dict:
        """Which branches are drifting (mean spot-check < 3)?"""
        by_monitor: dict[str, list[int]] = {}
        for c in self._checks:
            by_monitor.setdefault(c.monitor, []).append(c.score)
        means = {m: round(sum(s) / len(s), 2) for m, s in by_monitor.items()}
        drifting = sorted(m for m, mean in means.items() if mean < 3)
        return {
            "topic": self.topic,
            "monitors": len(self._monitors),
            "groups_covered": sum(len(m["groups"]) for m in self._monitors.values()),
            "spot_checks": len(self._checks),
            "fidelity_means": means,
            "drifting": drifting,
            "verdict": (
                "Cascade healthy."
                if not drifting
                else f"Drift detected in: {', '.join(drifting)} — retrain those branches."
            ),
        }
