"""Octopus arms — distributed semi-autonomous control (class OCT, hatter).

Real mechanism: ~500M neurons, two-thirds in the eight arms; each arm's
axial nerve cord processes sensation and initiates movement locally, and
a neural ring lets arms coordinate without the central brain (Gire /
Sivitilli, U. Washington). The brain sets intent; the arms decide the
how. Translated: N sub-minds with local policies run in parallel; the
center issues intent and holds a veto, never micromanagement.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


class Arm:
    """One semi-autonomous sub-mind."""

    def __init__(self, arm_id: int, policy: Callable[[Dict[str, Any]], Any]) -> None:
        self.arm_id = arm_id
        self.policy = policy
        self.vetoed = 0

    def act(self, local_sense: Dict[str, Any]) -> Any:
        """Decide locally, without asking the center."""
        return self.policy(local_sense)


class Octopus:
    """Federation of arms under a light central intent."""

    def __init__(
        self,
        arms: List[Arm],
        veto: Optional[Callable[[int, Any], Optional[Any]]] = None,
    ) -> None:
        self.arms = list(arms)
        self.veto = veto  # (arm_id, proposed) -> replacement or None

    def step(
        self, senses: List[Dict[str, Any]], intent: Optional[str] = None
    ) -> List[Any]:
        """Each arm acts on its own sense; center may veto, not command."""
        actions = []
        for arm, sense in zip(self.arms, senses, strict=True):
            proposed = arm.act(dict(sense, intent=intent))
            if self.veto is not None:
                replacement = self.veto(arm.arm_id, proposed)
                if replacement is not None:
                    arm.vetoed += 1
                    proposed = replacement
            actions.append(proposed)
        return actions
