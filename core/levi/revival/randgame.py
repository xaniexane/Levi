"""LEVI's adversarial role-play: divergent world models, traced to outcomes.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #40)

The old mechanism: put teams in the same game but give them *different
models of the world*. Not different information — different *assumptions*:
about how fast things move, what the other side wants, what the terrain
does. The teams play honestly inside their own models. Then comes the part
that matters, the debrief: which assumption drove which outcome? The game
is a machine for making hidden premises visible by watching them collide.

This module implements it:

* ``WorldModel`` — a named set of explicit assumptions (key → claim), each
  with a confidence. Divergent teams literally hold different dicts.
* ``Team`` — plays structured turns of ``Move`` objects, choosing moves by
  consulting its own model (a policy hook; a simple default policy ships).
* ``Game`` — runs the turns. Resolution is a small deterministic engine
  that reads *both* teams' assumptions: the same move succeeds or fails
  depending on which model's numbers the engine is asked to use — and the
  engine records which assumption it consulted for every outcome.
* ``Debrief`` — assumption→outcome tracing: for every assumption, the list
  of outcomes it drove, per team; plus a divergence report showing where
  the two models disagreed and which side of the disagreement won.

The debrief is the product. The game is just how you earn it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

ORIGIN = "levi-revival/randgame"


@dataclass(frozen=True)
class Assumption:
    """One explicit premise of a team's world model."""

    key: str
    claim: str
    confidence: float  # 0.0 - 1.0, stated honestly, not earned

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be 0.0-1.0")


@dataclass
class WorldModel:
    """A team's divergent model of the world: assumptions, out in the open."""

    name: str
    assumptions: Dict[str, Assumption] = field(default_factory=dict)

    def assume(self, key: str, claim: str, confidence: float) -> "WorldModel":
        self.assumptions[key] = Assumption(key, claim, confidence)
        return self

    def get(self, key: str) -> Optional[Assumption]:
        return self.assumptions.get(key)

    def value(self, key: str, default: float = 0.5) -> float:
        """Numeric reading of an assumption for the resolution engine.

        Convention: assumptions whose key starts with a known numeric
        prefix carry their number in the claim's first token, e.g.
        claim "0.8 the fleet arrives in time". Non-numeric claims fall
        back to ``default``.
        """
        a = self.assumptions.get(key)
        if a is None:
            return default
        try:
            return float(a.claim.split()[0])
        except (ValueError, IndexError):
            return default


@dataclass(frozen=True)
class Move:
    """One structured move by a team on its turn."""

    team: str
    action: str  # e.g. "advance", "fortify", "negotiate", "feint"
    target: str  # what/where the action is aimed at
    commitment: int = 1  # resources staked, 1-3

    def __post_init__(self) -> None:
        if not 1 <= self.commitment <= 3:
            raise ValueError("commitment must be 1-3")


@dataclass
class Outcome:
    """What happened, and which assumptions the engine consulted to decide it."""

    turn: int
    move: Move
    success: bool
    detail: str
    consulted: List[Tuple[str, str, str]] = field(default_factory=list)
    # (team, assumption_key, how_it_mattered)


# Default policy: pick the move type the model is most confident about.
def default_policy(team: "Team", turn: int) -> Move:
    prefs = [
        ("advance", "enemy_supply"),
        ("fortify", "home_base"),
        ("negotiate", "neutral_faction"),
        ("feint", "enemy_flank"),
    ]
    # Confidence in the assumption that favors each action.
    weights = {
        "advance": team.model.value("enemy_speed", 0.5),
        "fortify": 1.0 - team.model.value("enemy_speed", 0.5),
        "negotiate": team.model.value("neutral_sympathy", 0.5),
        "feint": team.model.value("enemy_discipline", 0.5),
    }
    action, target = max(prefs, key=lambda p: weights[p[0]])
    commitment = 2 if weights[action] > 0.6 else 1
    return Move(team=team.name, action=action, target=target, commitment=commitment)


@dataclass
class Team:
    name: str
    model: WorldModel
    policy: Callable[["Team", int], Move] = default_policy
    score: int = 0

    def choose(self, turn: int) -> Move:
        return self.policy(self, turn)


class Game:
    """Runs structured turns; the engine consults assumptions to resolve moves."""

    def __init__(self, teams: List[Team], turns: int = 4) -> None:
        if len(teams) < 2:
            raise ValueError("adversarial play needs at least two teams")
        self.teams = {t.name: t for t in teams}
        self.turns = turns
        self.outcomes: List[Outcome] = []
        self.log: List[str] = []

    def _resolve(self, turn: int, move: Move) -> Outcome:
        team = self.teams[move.team]
        consulted: List[Tuple[str, str, str]] = []

        def consult(other_team: str, key: str, role: str) -> float:
            val = self.teams[other_team].model.value(key)
            consulted.append((other_team, key, role))
            return val

        success = False
        if move.action == "advance":
            # Succeeds if own commitment beats the enemy's assumed speed.
            enemy = self._enemy_of(move.team)
            enemy_speed = consult(enemy, "enemy_speed", "advance must outrun it")
            own_push = team.model.value("own_speed", 0.5)
            success = (own_push + 0.15 * move.commitment) > enemy_speed
            detail = f"advance vs enemy_speed={enemy_speed:.2f}"
        elif move.action == "fortify":
            held = team.model.value("terrain_favors_defense", 0.5)
            consult(move.team, "terrain_favors_defense", "fortify leans on it")
            success = held + 0.1 * move.commitment > 0.5
            detail = f"fortify on terrain_favors_defense={held:.2f}"
        elif move.action == "negotiate":
            sympathy = consult(move.team, "neutral_sympathy", "negotiation needs it")
            success = sympathy + 0.1 * move.commitment > 0.55
            detail = f"negotiate with neutral_sympathy={sympathy:.2f}"
        elif move.action == "feint":
            enemy = self._enemy_of(move.team)
            discipline = consult(enemy, "enemy_discipline", "feint must fool it")
            cunning = team.model.value("own_cunning", 0.5)
            success = (cunning + 0.15 * move.commitment) > discipline
            detail = f"feint vs enemy_discipline={discipline:.2f}"
        else:
            detail = f"unknown action {move.action!r}: fails by default"
            consult(move.team, "unknown_action_policy", "no such doctrine")

        if success:
            team.score += move.commitment
        outcome = Outcome(
            turn=turn, move=move, success=success, detail=detail, consulted=consulted
        )
        self.log.append(
            f"turn {turn}: {move.team} {move.action} {move.target} -> "
            f"{'SUCCESS' if success else 'FAIL'} ({detail})"
        )
        return outcome

    def _enemy_of(self, team_name: str) -> str:
        for name in self.teams:
            if name != team_name:
                return name
        raise ValueError("no enemy found")

    def play(self) -> List[Outcome]:
        for turn in range(1, self.turns + 1):
            for team in self.teams.values():
                move = team.choose(turn)
                self.outcomes.append(self._resolve(turn, move))
        return self.outcomes


@dataclass
class Debrief:
    """Assumption→outcome tracing: which premises drove which results."""

    outcomes: List[Outcome]
    teams: Dict[str, Team]

    def trace(self) -> Dict[str, List[Dict[str, object]]]:
        """For each team.assumption, every outcome it was consulted on."""
        traced: Dict[str, List[Dict[str, object]]] = {}
        for o in self.outcomes:
            for team_name, key, role in o.consulted:
                label = f"{team_name}.{key}"
                traced.setdefault(label, []).append(
                    {
                        "turn": o.turn,
                        "move": f"{o.move.team} {o.move.action}",
                        "success": o.success,
                        "role": role,
                    }
                )
        return traced

    def decisive_assumptions(self) -> List[Dict[str, object]]:
        """Assumptions consulted on 2+ outcomes, ranked by win-rate swing."""
        traced = self.trace()
        ranked = []
        for label, uses in traced.items():
            if len(uses) < 2:
                continue
            wins = sum(1 for u in uses if u["success"])
            ranked.append(
                {
                    "assumption": label,
                    "consulted": len(uses),
                    "success_rate": round(wins / len(uses), 2),
                }
            )
        return sorted(ranked, key=lambda r: r["consulted"], reverse=True)

    def divergence_report(self) -> List[Dict[str, object]]:
        """Where the two models hold the same key but disagree on the number."""
        names = list(self.teams)
        report = []
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = self.teams[names[i]], self.teams[names[j]]
                shared = set(a.model.assumptions) & set(b.model.assumptions)
                for key in sorted(shared):
                    va, vb = a.model.value(key), b.model.value(key)
                    if abs(va - vb) >= 0.2:
                        report.append(
                            {
                                "assumption": key,
                                names[i]: va,
                                names[j]: vb,
                                "gap": round(abs(va - vb), 2),
                                "currently_winning": max(
                                    names, key=lambda n: self.teams[n].score
                                ),
                            }
                        )
        return sorted(report, key=lambda r: r["gap"], reverse=True)

    def summary(self) -> Dict[str, object]:
        return {
            "scores": {n: t.score for n, t in self.teams.items()},
            "trace": self.trace(),
            "decisive_assumptions": self.decisive_assumptions(),
            "divergences": self.divergence_report(),
        }


def demo() -> Dict[str, object]:
    red = Team(
        "red",
        WorldModel("red-doctrine")
        .assume("enemy_speed", "0.9 the enemy moves fast", 0.8)
        .assume("own_speed", "0.4 we are slow", 0.7)
        .assume("terrain_favors_defense", "0.8 ground favors the defender", 0.9)
        .assume("neutral_sympathy", "0.3 neutrals distrust us", 0.6)
        .assume("enemy_discipline", "0.8 the enemy holds formation", 0.75)
        .assume("own_cunning", "0.5 we are average tricksters", 0.5),
    )
    blue = Team(
        "blue",
        WorldModel("blue-doctrine")
        .assume("enemy_speed", "0.3 the enemy is sluggish", 0.8)
        .assume("own_speed", "0.8 we are fast", 0.85)
        .assume("terrain_favors_defense", "0.4 ground favors the attacker", 0.6)
        .assume("neutral_sympathy", "0.7 neutrals lean our way", 0.7)
        .assume("enemy_discipline", "0.3 the enemy breaks easily", 0.65)
        .assume("own_cunning", "0.6 we are decent tricksters", 0.6),
    )
    game = Game([red, blue], turns=4)
    game.play()
    debrief = Debrief(game.outcomes, game.teams)
    return debrief.summary()


if __name__ == "__main__":
    print(json.dumps(demo(), indent=2))
