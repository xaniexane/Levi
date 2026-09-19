"""Natural intelligence classes — genuine types translated from nature.

Ten new intelligence classes, each a REAL mechanism observed in a living
system and translated into agent-usable machinery — not relabeled AI.
Every entry carries its source, the translated mechanism, the organ it
serves (with a defensible mapping), honest limits, and the behavior
module that implements it. Status "genuine" means: the mechanism is
implemented in levi/intelligence/behaviors/ and proven by tests.

Research provenance (web-verified 2026-09-19, rebuilt natively):
- octopus distributed arms: ~500M neurons, two-thirds in the arms;
  arms decide locally, neural ring bypasses the brain (U. Washington).
- bee waggle dance: angle vs. gravity = bearing vs. sun; duration =
  distance (von Frisch, Nobel 1973).
- slime mold: flow-thickened tubes, starved tubes vanish; maze and
  Tokyo-rail solutions with no brain (Nakagaki 2000; Tero 2010).
- cuttlefish: male courts a female on one flank while showing a
  female-mimic pattern to a rival on the other, simultaneously
  (Brown, Macquarie, Biology Letters 2012).
- clonal selection: Burnet 1957 — repertoire, selection, clonal
  expansion, somatic hypermutation, affinity maturation.
- ant stigmergy, corvid tool chains, whale song redundancy, mycelial
  routing, bacterial conjugation: textbook mechanisms, translated.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

#: The ten natural class codes.
NATURAL_CODES: Tuple[str, ...] = (
    "ANT",
    "CRV",
    "BEE",
    "WHL",
    "MYC",
    "SLM",
    "IMM",
    "BCT",
    "OCT",
    "CUT",
)

#: Required fields on every natural class record.
NATURAL_REQUIRED_FIELDS: Tuple[str, ...] = (
    "code",
    "name",
    "source",
    "mechanism",
    "organ",
    "capabilities",
    "limits",
    "behavior",
    "status",
)

#: Organs a natural class may map to. "hatter" is the fifth intelligence
#: organ — first-class standing for the under-credited chaos engine.
NATURAL_ORGANS: Tuple[str, ...] = (
    "echoverse",
    "mandella",
    "reim",
    "riem",
    "hatter",
)

NATURAL_CLASSES: Dict[str, Dict[str, object]] = {
    "ANT": {
        "code": "ANT",
        "name": "Stigmergic Intelligence",
        "source": (
            "Ant colonies: workers deposit pheromone while walking; "
            "pheromone evaporates; workers follow the strongest local "
            "gradient. No ant holds the plan — the trail is the plan."
        ),
        "mechanism": (
            "Shared pheromone field over the task space: deposit on "
            "success, evaporate always, follow uphill. Many dumb walkers "
            "converge on the target under fog."
        ),
        "organ": "mandella",
        "capabilities": [
            "decentralized task allocation with no coordinator",
            "trail reinforcement finds shortest viable routes",
            "evaporation forgets stale commitments automatically",
        ],
        "limits": [
            "needs many walkers; a single ant is useless",
            "converges slowly on first discovery",
            "cannot represent negation or long-term memory",
        ],
        "behavior": "levi.intelligence.behaviors.stigmergy",
        "status": "genuine",
    },
    "CRV": {
        "code": "CRV",
        "name": "Corvid Intelligence",
        "source": (
            "New Caledonian crows: manufacture hooked tools and chain "
            "tool uses — short stick to fetch long stick to fetch food — "
            "planning several steps ahead."
        ),
        "mechanism": (
            "Breadth-first search over (reachable-things, tools-held): "
            "stake the plan on the first tool that unlocks the next step, "
            "before the goal is reachable."
        ),
        "organ": "mandella",
        "capabilities": [
            "multi-step tool chains discovered, not scripted",
            "shortest chain found first (BFS)",
            "explicit unchosen branches = the phantoms",
        ],
        "limits": [
            "needs a correct tool-physics table; garbage in, garbage out",
            "BFS explodes past depth ~6",
            "no learning — plans from scratch every time",
        ],
        "behavior": "levi.intelligence.behaviors.corvid",
        "status": "genuine",
    },
    "BEE": {
        "code": "BEE",
        "name": "Waggle Intelligence",
        "source": (
            "Honeybees: the waggle dance encodes a resource vector — "
            "angle vs. gravity is bearing vs. the sun, waggle duration "
            "is distance, tempo is profitability (von Frisch)."
        ),
        "mechanism": (
            "Symbolic vector codec: direction + distance + quality packed "
            "into one dance; any agent holding the same sun reference "
            "decodes it exactly."
        ),
        "organ": "echoverse",
        "capabilities": [
            "lossless direction/distance/quality broadcast",
            "one dance reaches every follower at once",
            "followers average runs — noise-tolerant by design",
        ],
        "limits": [
            "requires a shared reference frame (the sun)",
            "one-way: dancers don't take questions",
            "encodes vectors only, not reasons",
        ],
        "behavior": "levi.intelligence.behaviors.waggle",
        "status": "genuine",
    },
    "WHL": {
        "code": "WHL",
        "name": "Songline Intelligence",
        "source": (
            "Humpback whales: song carries kilometers through ocean — "
            "low bandwidth, high redundancy, stereotyped units repeated "
            "until the message survives the water."
        ),
        "mechanism": (
            "Repetition-redundant message codec: encode payload as "
            "repeated symbol phrases, decode by majority vote so the "
            "signal survives corruption."
        ),
        "organ": "echoverse",
        "capabilities": [
            "messages survive heavy channel noise",
            "long-range broadcast with no infrastructure",
            "receiver needs no prior handshake",
        ],
        "limits": [
            "bandwidth is tiny — phrases, not essays",
            "redundancy costs 3x the symbols",
            "no secrecy; the whole ocean hears",
        ],
        "behavior": "levi.intelligence.behaviors.songline",
        "status": "genuine",
    },
    "MYC": {
        "code": "MYC",
        "name": "Mycelial Intelligence",
        "source": (
            "Fungal mycelium: decomposes dead matter and routes the "
            "recovered nutrients along gradients to where the network "
            "needs them, rerouting around damage."
        ),
        "mechanism": (
            "Decompose-then-route: dead inputs are broken into reusable "
            "units; flow follows the widest-capacity path; severed links "
            "are bypassed, not mourned."
        ),
        "organ": "reim",
        "capabilities": [
            "turns dead material into reusable nutrient",
            "automatic rerouting around damage",
            "widest-path routing maximizes throughput",
        ],
        "limits": [
            "decomposition is lossy — not everything recycles",
            "routing is greedy, not globally optimal",
            "no memory of what was composted",
        ],
        "behavior": "levi.intelligence.behaviors.mycelium",
        "status": "genuine",
    },
    "SLM": {
        "code": "SLM",
        "name": "Physarum Intelligence",
        "source": (
            "Slime mold Physarum polycephalum: spans food with a tube "
            "network; tubes with flow thicken, starved tubes retract and "
            "vanish — solving mazes and rail networks with no brain."
        ),
        "mechanism": (
            "Flow-reinforced pruning: every foraging pulse thickens used "
            "tubes and decays the rest; dead tubes are composted into a "
            "shorter, tougher network."
        ),
        "organ": "reim",
        "capabilities": [
            "finds near-shortest paths with zero planning",
            "pruning converts failed routes into efficiency",
            "network stays connected under tube loss",
        ],
        "limits": [
            "slow — pulses, not computation",
            "can prune a route that later becomes needed",
            "no representation of WHY a tube worked",
        ],
        "behavior": "levi.intelligence.behaviors.physarum",
        "status": "genuine",
    },
    "IMM": {
        "code": "IMM",
        "name": "Clonal Intelligence",
        "source": (
            "Adaptive immunity (Burnet 1957): a diverse B-cell repertoire "
            "meets an antigen; binders are selected, cloned, and "
            "hypermutated — mutation rate inversely proportional to "
            "affinity — until affinity matures. Winners become memory."
        ),
        "mechanism": (
            "Generate-mutate-select loop: best solutions clone the most "
            "and mutate the least; fresh diversity injected like marrow; "
            "winners promoted to memory."
        ),
        "organ": "riem",
        "capabilities": [
            "affinity (fitness) improves every generation",
            "hypermutation focuses search where it's weakest",
            "memory cells keep winners without re-search",
        ],
        "limits": [
            "needs a trustworthy fitness function",
            "can overfit to one antigen (one problem)",
            "no negative selection here — self-harm possible",
        ],
        "behavior": "levi.intelligence.behaviors.clonal",
        "status": "genuine",
    },
    "BCT": {
        "code": "BCT",
        "name": "Conjugative Intelligence",
        "source": (
            "Bacteria: plasmids — small DNA rings — pass sideways by "
            "direct contact; a useful trait sweeps the population without "
            "waiting for parent-to-child inheritance."
        ),
        "mechanism": (
            "Horizontal solution transfer: top performers donate "
            "solution-fragments to neighbors each round; beneficial "
            "fragments sweep the population in a few rounds."
        ),
        "organ": "riem",
        "capabilities": [
            "good ideas spread sideways in O(rounds), not generations",
            "no central breeder required",
            "plasmid cap keeps genomes from bloating",
        ],
        "limits": [
            "spreads bad plasmids as fast as good ones",
            "needs contact structure — isolated agents learn nothing",
            "fragment splicing can break working genomes",
        ],
        "behavior": "levi.intelligence.behaviors.conjugation",
        "status": "genuine",
    },
    "OCT": {
        "code": "OCT",
        "name": "Octopod Intelligence",
        "source": (
            "Octopus: ~500M neurons, two-thirds in the eight arms; each "
            "arm's nerve cord senses and moves locally, and a neural ring "
            "lets arms coordinate without the brain. Intent is central; "
            "decisions are not."
        ),
        "mechanism": (
            "Federated sub-minds: N arms run local policies in parallel "
            "on local sense data; the center sets intent and holds a veto "
            "— it never issues motor commands."
        ),
        "organ": "hatter",
        "capabilities": [
            "parallel local decisions with zero central bottleneck",
            "arms keep working when the center is busy or cut off",
            "veto preserves coherence without micromanagement",
        ],
        "limits": [
            "arms can work at cross-purposes without veto tuning",
            "no arm sees the whole picture",
            "coordination is emergent, not guaranteed",
        ],
        "behavior": "levi.intelligence.behaviors.octopus",
        "status": "genuine",
    },
    "CUT": {
        "code": "CUT",
        "name": "Cuttlefish Intelligence",
        "source": (
            "Mourning cuttlefish: a male displays courtship pattern to a "
            "female on one flank while simultaneously showing a "
            "female-mimic pattern to a rival male on the other — two "
            "contradictory messages, live, at once."
        ),
        "mechanism": (
            "Paradox holder: two contradictory plans run with "
            "independent confidences; both are acted on until evidence "
            "crosses a resolution threshold. Paradox is a working state."
        ),
        "organ": "hatter",
        "capabilities": [
            "holds contradictions without premature collapse",
            "each flank answers its own audience",
            "resolution is evidence-driven, not forced",
        ],
        "limits": [
            "double the action cost while unresolved",
            "threshold too high = paralysis; too low = flip-flopping",
            "observers see deception even when it's strategy",
        ],
        "behavior": "levi.intelligence.behaviors.cuttlefish",
        "status": "genuine",
    },
}


def get_natural(code: str) -> Dict[str, object]:
    """Return the genuine record for a natural class code (KeyError if
    unknown)."""
    return NATURAL_CLASSES[code]


def is_natural_class(code: str) -> bool:
    """True for the ten genuine natural classes."""
    return code in NATURAL_CLASSES


def natural_for_organ(organ: str) -> List[str]:
    """Codes of natural classes mapped to one organ."""
    return [c for c in NATURAL_CODES if NATURAL_CLASSES[c]["organ"] == organ]
