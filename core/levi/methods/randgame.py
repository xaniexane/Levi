"""RAND political-military gaming: scenario gaming under divergent models.

History: RAND Corporation's 1950s "Cold War Games" — the first
*political*-military simulations: not just fleets and divisions but
propaganda, psychology, economics, and diplomacy, played by competing
teams. The famous empirical lesson: the mathematics division's
game-theoretic version escalated quickly to nuclear use while the
social-science division's more realistic, emotionally engaging version
produced restraint — *the model's assumptions are the real game*.

The mechanism: *adversarial role-play with divergent models*. Two teams
play the same scenario under different assumptions, and the debrief
compares not who "won" but *which assumptions drove which outcomes*. The
game is an instrument for exposing hidden premises — researchers found
ethical restraint emerging through physical play even where moral language
was officially absent.

In LEVI: the assistant stages RAND-style games for your strategic
decisions. It builds two teams — played by scripted strategies or by you
vs. the AI — operating under *explicitly different models of the world*
(e.g. "customers are rational" vs. "customers are tribal"), runs the
scenario round by round, and debriefs on assumption-divergence: showing
you which of your beliefs is doing the deciding. There is no privileged
ground truth; each team lives inside its own model's world, and the
divergence between the worlds is the finding.

Honesty: USEFUL PATTERN — the epistemology (make assumptions explicit,
compare what they produce) is the load-bearing part; the outcome models
here are sketches you supply, not predictions about the world.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class GameError(Exception):
    """Base class for scenario-gaming failures."""


# ---------------------------------------------------------------------------
# Models, teams, scenarios
# ---------------------------------------------------------------------------


@dataclass
class WorldModel:
    """An explicit model of the world: named assumptions plus a step
    function ``step(state, moves) -> (new_state, notes)``."""

    name: str
    assumptions: list[str] = field(default_factory=list)
    step: Callable[[dict, dict], tuple[dict, list[str]]] | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("model name must be non-empty")
        if self.step is not None and not callable(self.step):
            raise ValueError("model step must be callable")


@dataclass
class Team:
    """A team playing under one world-model with one strategy.

    ``strategy(view, round_no)`` returns the team's move (any JSON-able
    value). ``view`` is the observable state *inside that team's model*.
    """

    name: str
    model: WorldModel
    strategy: Callable[[dict, int], Any]

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("team name must be non-empty")
        if not callable(self.strategy):
            raise ValueError("team strategy must be callable")


@dataclass
class Scenario:
    name: str
    description: str
    rounds: int
    initial_state: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("scenario name must be non-empty")
        if self.rounds < 1:
            raise ValueError("rounds must be >= 1")


# ---------------------------------------------------------------------------
# The game
# ---------------------------------------------------------------------------


class Game:
    """Runs the scenario: each team lives inside its own model's world."""

    def __init__(self, scenario: Scenario, teams: list[Team]):
        if len(teams) < 2:
            raise ValueError("a game needs at least two teams")
        names = [t.name for t in teams]
        if len(set(names)) != len(names):
            raise ValueError("team names must be unique")
        for team in teams:
            if team.model.step is None:
                raise GameError(
                    f"team {team.name!r}: model {team.model.name!r} has no step "
                    "function — assumptions without mechanics are just opinions"
                )
        self.scenario = scenario
        self.teams = teams
        # Per-team world: each team advances inside its OWN model's world.
        self._worlds: dict[str, dict] = {
            t.name: dict(scenario.initial_state) for t in teams
        }
        self.rounds_played: list[dict] = []

    def run(self) -> "Game":
        """Play all rounds. Moves are JSON-able; strategies must be pure
        (deterministic) for the debrief to mean anything."""
        for rnd in range(1, self.scenario.rounds + 1):
            moves: dict[str, Any] = {}
            for team in self.teams:
                try:
                    move = team.strategy(dict(self._worlds[team.name]), rnd)
                except Exception as exc:  # noqa: BLE001 — a frozen team is data
                    raise GameError(
                        f"team {team.name!r} strategy failed on round {rnd}: {exc}"
                    ) from exc
                moves[team.name] = move
            outcomes: dict[str, dict] = {}
            for team in self.teams:
                new_state, notes = team.model.step(
                    dict(self._worlds[team.name]), dict(moves)
                )
                if not isinstance(new_state, dict):
                    raise GameError(
                        f"model {team.model.name!r} must return a dict state"
                    )
                self._worlds[team.name] = new_state
                outcomes[team.name] = {"state": dict(new_state), "notes": notes}
            self.rounds_played.append(
                {
                    "round": rnd,
                    "moves": moves,
                    "outcomes": outcomes,
                    "at": time.time(),
                }
            )
        return self

    # -- structured debrief -----------------------------------------------------
    def debrief(self) -> dict:
        """Compare not who won but which assumptions drove which outcomes.

        For each round, the per-model world states are compared; rounds
        where models diverge are flagged with the assumptions unique to
        each diverging model — the honest, mechanical version of "which of
        your beliefs is doing the deciding".
        """
        team_models = {t.name: t.model for t in self.teams}
        divergences = []
        for record in self.rounds_played:
            states = {name: oc["state"] for name, oc in record["outcomes"].items()}
            names = list(states)
            base, rest = states[names[0]], names[1:]
            for other in rest:
                if states[other] != base:
                    divergences.append(
                        {
                            "round": record["round"],
                            "models": [
                                team_models[names[0]].name,
                                team_models[other].name,
                            ],
                            "differing_keys": sorted(
                                k
                                for k in set(base) | set(states[other])
                                if base.get(k) != states[other].get(k)
                            ),
                            "assumptions_a": team_models[names[0]].assumptions,
                            "assumptions_b": team_models[other].assumptions,
                        }
                    )
        return {
            "scenario": self.scenario.name,
            "teams": [
                {
                    "team": t.name,
                    "model": t.model.name,
                    "assumptions": t.model.assumptions,
                    "final_state": self._worlds[t.name],
                }
                for t in self.teams
            ],
            "rounds": len(self.rounds_played),
            "divergent_rounds": len(divergences),
            "divergences": divergences,
        }

    def summary(self) -> str:
        """One-paragraph honest debrief for the human."""
        d = self.debrief()
        lines = [
            f"scenario {d['scenario']!r}: {d['rounds']} rounds, "
            f"{d['divergent_rounds']} divergent"
        ]
        for team in d["teams"]:
            lines.append(
                f"  team {team['team']!r} under {team['model']!r}: "
                f"{team['final_state']}"
            )
        for div in d["divergences"]:
            lines.append(
                f"  round {div['round']}: {div['models'][0]!r} vs "
                f"{div['models'][1]!r} diverged on {div['differing_keys']}"
            )
        if not d["divergences"]:
            lines.append(
                "  the models agreed everywhere — your assumptions "
                "don't discriminate this scenario"
            )
        return "\n".join(lines)


__all__ = [
    "GameError",
    "WorldModel",
    "Team",
    "Scenario",
    "Game",
]
