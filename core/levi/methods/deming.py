"""Deming's System of Profound Knowledge: the four-lens diagnostic.

Origin: W. Edwards Deming's capstone framework — four interdependent
lenses whose power is in their *interaction*, not any one alone:

1. **Appreciation for a system** — everything is connected; optimize the whole.
2. **Knowledge of variation** — distinguish signal from noise; don't tamper.
3. **Theory of knowledge** — no knowledge without theory; prediction is the test.
4. **Psychology** — people are driven by intrinsic motivation; fear destroys it.

What it is in LEVI: a diagnostic lattice the assistant applies to your
personal systems. It refuses to celebrate or mourn single data points
(variation lens), traces every metric to the system that produced it,
demands a theory before an intervention ("what do you predict will
happen?"), and watches for Goodhart/gaming effects on your own motivation
(psychology lens). Most management failures are three-lens failures.

Honesty label: LOAD-BEARING — the lattice is a concrete discipline. The
variation screening here is a simple mean/band check, honestly labeled as
screening, not a substitute for real statistical process control.

Deny-closed inputs: non-numeric observations, unknown metrics, empty
theories, and unknown psychology risks are rejected with ValueError.
"""

from __future__ import annotations

from math import sqrt
from typing import Optional

__all__ = ["ProfoundKnowledge", "PSYCHOLOGY_RISKS", "MIN_POINTS"]

# Below this many observations the variation lens refuses to judge —
# with thin data, everything looks like a signal.
MIN_POINTS = 8

PSYCHOLOGY_RISKS: dict[str, str] = {
    "streak_punishment": "Punishing broken streaks converts intrinsic drive into fear of the metric.",
    "gaming": "When the metric becomes the target, behavior optimizes for the metric, not the goal (Goodhart).",
    "fear": "Measurement tied to judgment makes people hide data — the system goes blind.",
    "tampering": "Reacting to common-cause variation as if it were a signal makes things worse.",
    "comparison": "Ranking people against each other destroys cooperation the system needs.",
}


class ProfoundKnowledge:
    """The four lenses, applied to your metrics."""

    def __init__(self):
        self._series: dict[str, list[float]] = {}
        self._theories: dict[str, dict] = {}  # metric -> {theory, prediction}
        self._links: list[tuple[str, str, str]] = []  # (a, b, relation)
        self._watches: dict[str, list[str]] = {}  # metric -> psychology risks

    # -- recording -----------------------------------------------------------------
    @staticmethod
    def _metric_name(metric: str) -> str:
        if not isinstance(metric, str) or not metric.strip():
            raise ValueError("metric name must be a non-empty string")
        return metric.strip()

    def observe(self, metric: str, value: float) -> None:
        """Log one observation of a metric (chronological order)."""
        metric = self._metric_name(metric)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"observation must be numeric, got {value!r}")
        self._series.setdefault(metric, []).append(float(value))

    def record_theory(self, metric: str, theory: str, prediction: str) -> None:
        """Knowledge lens: no intervention without a theory and a prediction."""
        metric = self._metric_name(metric)
        if not theory.strip() or not prediction.strip():
            raise ValueError("theory and prediction must both be non-empty")
        self._theories[metric] = {"theory": theory.strip(),
                                  "prediction": prediction.strip()}

    def link(self, metric_a: str, metric_b: str, relation: str) -> None:
        """System lens: these metrics move in a shared system; say how."""
        a, b = self._metric_name(metric_a), self._metric_name(metric_b)
        if a == b:
            raise ValueError("a metric cannot be linked to itself")
        if not relation.strip():
            raise ValueError("relation must be non-empty")
        if (a, b, relation.strip()) not in self._links:
            self._links.append((a, b, relation.strip()))

    def watch_for(self, metric: str, risk: str) -> None:
        """Psychology lens: name the motivational failure mode to watch for."""
        metric = self._metric_name(metric)
        if risk not in PSYCHOLOGY_RISKS:
            raise ValueError(f"unknown risk {risk!r}; known: {sorted(PSYCHOLOGY_RISKS)}")
        self._watches.setdefault(metric, [])
        if risk not in self._watches[metric]:
            self._watches[metric].append(risk)

    # -- the four lenses ---------------------------------------------------------------
    def _variation_lens(self, metric: str) -> dict:
        series = self._series.get(metric, [])
        if len(series) < MIN_POINTS:
            return {"verdict": "insufficient_data",
                    "detail": f"Only {len(series)} observation(s); need {MIN_POINTS}+ "
                              "before distinguishing signal from noise. Do not judge this metric yet."}
        baseline, latest = series[:-1], series[-1]
        mean = sum(baseline) / len(baseline)
        var = sum((x - mean) ** 2 for x in baseline) / len(baseline)
        sd = sqrt(var)
        if sd == 0:
            return {"verdict": "no_variation",
                    "detail": "Baseline is perfectly flat; any movement is a change worth investigating."}
        z = abs(latest - mean) / sd
        if z >= 2:
            return {"verdict": "possible_special_cause",
                    "detail": f"Latest ({latest}) is {z:.1f} SD from the baseline mean "
                              f"({mean:.2f}) — investigate for a special cause before acting."}
        return {"verdict": "common_cause",
                "detail": f"Latest ({latest}) sits within normal variation of the baseline "
                          f"(mean {mean:.2f}, SD {sd:.2f}). Do not tamper — reacting to noise makes it worse."}

    def _system_lens(self, metric: str) -> dict:
        linked = [(b if a == metric else a, rel) for a, b, rel in self._links
                  if a == metric or b == metric]
        return {"linked_metrics": linked,
                "detail": ("No system links recorded — this metric is being read in isolation, "
                           "which is exactly how systems get suboptimized."
                           if not linked else
                           f"Read with: {', '.join(f'{m} ({r})' for m, r in linked)}.")}

    def _knowledge_lens(self, metric: str) -> dict:
        theory = self._theories.get(metric)
        if theory is None:
            return {"verdict": "no_theory",
                    "detail": "No theory recorded. Deming's rule: no knowledge without theory — "
                              "state what you believe and what you predict before intervening."}
        series = self._series.get(metric, [])
        return {"verdict": "theory_recorded",
                "theory": theory["theory"],
                "prediction": theory["prediction"],
                "detail": f"Theory: {theory['theory']} Prediction under test: {theory['prediction']} "
                          f"({len(series)} observations so far)."}

    def _psychology_lens(self, metric: str) -> dict:
        risks = self._watches.get(metric, [])
        return {"watched_risks": risks,
                "detail": ("No psychology risks named — measurement changes the measured; "
                           "name the failure mode with watch_for()."
                           if not risks else
                           " ".join(f"[{r}] {PSYCHOLOGY_RISKS[r]}" for r in risks))}

    def diagnose(self, metric: str) -> dict:
        """Run all four lenses over one metric. The power is the interaction."""
        metric = self._metric_name(metric)
        if metric not in self._series:
            raise ValueError(f"no observations recorded for {metric!r}")
        variation = self._variation_lens(metric)
        system = self._system_lens(metric)
        knowledge = self._knowledge_lens(metric)
        psychology = self._psychology_lens(metric)
        interaction = self._interaction_note(variation, system, knowledge, psychology)
        return {"metric": metric,
                "observations": len(self._series[metric]),
                "variation": variation,
                "system": system,
                "knowledge": knowledge,
                "psychology": psychology,
                "interaction": interaction}

    @staticmethod
    def _interaction_note(variation: dict, system: dict,
                          knowledge: dict, psychology: dict) -> str:
        notes = []
        if variation["verdict"] == "common_cause":
            notes.append("Variation says: don't tamper. Any intervention now fights noise, not cause.")
        if variation["verdict"] == "possible_special_cause":
            notes.append("Variation says: possible special cause — but check the system lens first: "
                         "what moved *with* it?")
        if knowledge["verdict"] == "no_theory":
            notes.append("Knowledge says: you have no theory, so you cannot learn from what happens next. "
                         "Write the prediction down first.")
        if "gaming" in psychology["watched_risks"] or "streak_punishment" in psychology["watched_risks"]:
            notes.append("Psychology says: the measurement itself may be producing the behavior — "
                         "fix the incentive before the process.")
        return " ".join(notes) if notes else "All four lenses quiet: hold course, keep observing."
