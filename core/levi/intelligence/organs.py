"""Organ -> intelligence mapping for the genuine classes.

Five intelligence-organs: the four branching organs (echoverse, mandella,
reim, riem) plus hatter — the chaos-routing engine, given first-class
standing here equal to the other four, as the keeper ordered.

Note: this maps INTELLIGENCES to organs. It does not touch the deny-closed
organ dispatch registry (levi.organs.registry) — "hatter" is an
intelligence-organ here, not a new dispatch entry point.

Mapping doctrine (defensible, not decorative):
- echoverse (branch exploration / signaling): classes that broadcast and
  explore in parallel — BEE (vector broadcast), WHL (long-range protocol).
- mandella (stake under fog + phantoms): classes that commit under
  uncertainty — ANT (pheromone stakes), CRV (tool-plan stakes).
- reim (failure composting): classes that turn the dead/failed into
  resource — MYC (decomposer), SLM (tube pruning).
- riem (compost -> genome): classes that promote winners into lasting
  form — IMM (memory cells), BCT (plasmid sweep).
- hatter (chaos routing / paradox): classes that refuse one center —
  OCT (federated arms), CUT (contradictory flanks).
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from levi.intelligence.natural import NATURAL_CLASSES

#: organ -> [(class code, one-line justification)]
ORGAN_INTELLIGENCE: Dict[str, List[Tuple[str, str]]] = {
    "echoverse": [
        ("BEE", "waggle dance broadcasts explored branches to the hive"),
        ("WHL", "songline carries branch reports across long distance"),
    ],
    "mandella": [
        ("ANT", "pheromone trails are stakes placed under fog"),
        ("CRV", "tool chains stake a multi-step plan before it pays off"),
    ],
    "reim": [
        ("MYC", "decomposer: dead matter composted into reusable nutrient"),
        ("SLM", "starved tubes pruned; failure becomes network efficiency"),
    ],
    "riem": [
        ("IMM", "affinity winners promoted into memory — genome kept"),
        ("BCT", "winning plasmids swept sideways into the shared pool"),
    ],
    "hatter": [
        ("OCT", "eight semi-minds, no center — diagonal control"),
        ("CUT", "two contradictory displays live — the paradox holder"),
    ],
}

INTELLIGENCE_ORGANS: Tuple[str, ...] = (
    "echoverse",
    "mandella",
    "reim",
    "riem",
    "hatter",
)


def intelligences_for(organ: str) -> List[Tuple[str, str]]:
    """(code, justification) pairs for one organ. KeyError if unknown."""
    return list(ORGAN_INTELLIGENCE[organ])


def organ_of(code: str) -> str:
    """The organ a genuine class serves. KeyError if unknown code."""
    rec = NATURAL_CLASSES[code]
    organ = rec["organ"]
    assert isinstance(organ, str)
    return organ


def all_mappings() -> Dict[str, List[Tuple[str, str]]]:
    """The full organ -> intelligences map (copy)."""
    return {o: list(v) for o, v in ORGAN_INTELLIGENCE.items()}
