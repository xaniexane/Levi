"""Plaiground simulator — scenario runner over Echoverse branching.

The simulator takes a user-provided scenario and a companion, then runs
the scenario through the Echoverse organ (:func:`levi.organs.echo.run_echo`)
underneath: taken / not-taken / wild branches for the scenario seed,
rendered as companion scenario beats. The branching engine is the clean,
deterministic Echoverse surface; Plaiground is only the adult-side wrapper
around it. The Echoverse module itself is never modified.

Scenario content is user-driven at runtime; this module adds no content,
only plumbing. Gate-checked first: with the gate off, nothing runs.
"""

from __future__ import annotations

import string
from pathlib import Path
from typing import Dict, List, Optional

from levi.organs.echo import run_echo
from levi.plaiground.companions import get_companion
from levi.plaiground.gate import require_adult

_MAX_SCENARIO_LEN = 2000
_ALLOWED_CHARS = set(string.printable) - set("\x0b\x0c")

_BEAT_INTRO = {
    "taken": "leans into the committed path",
    "not_taken": "holds back, watching the untaken path",
    "wild": "veers off-script into the wild branch",
}


def _validate_scenario(scenario: str) -> str:
    if not isinstance(scenario, str):
        raise ValueError("scenario must be a string, got %s" % type(scenario).__name__)
    scenario = scenario.strip()
    if not scenario:
        raise ValueError("scenario must not be empty")
    if len(scenario) > _MAX_SCENARIO_LEN:
        raise ValueError("scenario must be at most %d characters" % _MAX_SCENARIO_LEN)
    if any(ch not in _ALLOWED_CHARS for ch in scenario):
        raise ValueError("scenario contains disallowed characters")
    return scenario


def run_scenario(
    companion_name: str,
    scenario: str,
    cycles: int = 3,
    home: Optional[Path] = None,
) -> Dict:
    """Run a scenario for a companion through Echoverse branching.

    Gate-checked first, then the companion definition is loaded and the
    scenario is run through :func:`levi.organs.echo.run_echo` with the
    seed ``"<companion> | <scenario>"``. Returns the companion name, the
    scenario, the echo result, and companion-rendered beats.
    """
    require_adult(home)
    companion = get_companion(companion_name, home=home)
    scenario = _validate_scenario(scenario)
    echo_result = run_echo("%s | %s" % (companion["name"], scenario), cycles=cycles)
    beats: List[Dict] = []
    for branch in echo_result["branches"]:
        kind = branch["kind"]
        beats.append(
            {
                "kind": kind,
                "intro": "%s %s." % (companion["name"], _BEAT_INTRO.get(kind, "moves")),
                "label": branch["label"],
                "risk": branch["risk"],
                "detail": branch["summary"],
            }
        )
    return {
        "zone": "plaiground",
        "engine": "echoverse",
        "companion": companion["name"],
        "traits": companion["traits"],
        "boundaries": companion["boundaries"],
        "scenario": scenario,
        "beats": beats,
        "insight": echo_result["insight"],
    }


def format_scenario(result: Dict) -> str:
    """Render a :func:`run_scenario` result as text."""
    if not isinstance(result, dict) or "beats" not in result:
        raise ValueError("format_scenario: not a scenario result")
    lines = [
        "=== Plaiground scenario: %s ===" % result.get("companion", "?"),
        "scenario: %s" % str(result.get("scenario", ""))[:120],
        "boundaries honored: %s"
        % ", ".join(str(b) for b in result.get("boundaries", [])),
        "",
    ]
    for beat in result["beats"]:
        lines.append("[%s] %s" % (beat["kind"], beat["intro"]))
        lines.append("  %s  risk=%s" % (beat["label"], beat["risk"]))
        lines.append("  %s" % beat["detail"])
    lines.append("")
    lines.append("Insight: %s" % result.get("insight", ""))
    return "\n".join(lines)
