"""
Heavy knowledge expansion — denser A–Z, more inventors/events/stars, domains, X.

Run: python -m levi.cli.main brain --seed-knowledge-heavy
"""

from __future__ import annotations

from typing import Iterator, List, Tuple

_RAW: List[Tuple[str, str, Tuple[str, ...]]] = []

# Extra subject depth per letter
_DEPTH = {
    "A": [
        "Algebra: structure of operations; equations as reversible stories about quantity.",
        "Architecture: space organized under gravity, light, and human flow.",
        "Anthropology: comparative study of human groups; avoid single-story cultures.",
    ],
    "B": [
        "Botany: plants as primary producers; photosynthesis underwrites food webs.",
        "Business: value exchange under uncertainty; unit economics before narrative.",
        "Boolean logic: true/false composition; basis of digital circuits and queries.",
    ],
    "C": [
        "Climate: energy balance of atmosphere/ocean; feedbacks amplify or damp change.",
        "Cryptography: secrecy under adversarial observation; keys are the real secret.",
        "Civics: institutions that convert collective preference into binding rules.",
    ],
    "D": [
        "Data: measurements with provenance; garbage in remains garbage after charts.",
        "Drama: conflict + stakes + change; character is revealed under pressure.",
        "Databases: durable structured memory; ACID vs eventual consistency trade-offs.",
    ],
    "E": [
        "Electricity: charge flow; power = voltage × current in simple circuits.",
        "Evolution: differential reproduction of heritable variation; not goal-directed.",
        "Ethics: reasons for action that survive scrutiny beyond preference alone.",
    ],
    "F": [
        "Finance: time-shifted value and risk; leverage magnifies outcomes both ways.",
        "Film: time + image + sound montage; editing is argument.",
        "Feedback control: measure, compare, act; lag creates oscillation risk.",
    ],
    "G": [
        "Genetics: information in nucleic acids; environment still shapes expression.",
        "Geometry: space via axioms; Euclidean vs curved models for different scales.",
        "Governance: who decides, under what rules, with what exit options.",
    ],
    "H": [
        "Hydrology: water cycle; scarcity is often distribution and quality, not only volume.",
        "Human factors: design for attention, error, and fatigue — not ideal operators.",
        "Historiography: how history is written; sources and bias are part of the claim.",
    ],
    "I": [
        "Immunology: self/non-self discrimination; inflammation is tool and risk.",
        "Internet: layered protocols; end-to-end principle keeps edges smart.",
        "Inference: conclusions beyond data need explicit uncertainty labels.",
    ],
    "J": [
        "Journalism: verify before amplify; speed and truth trade under pressure.",
        "Jazz: structured improvisation; listening is the coordination channel.",
        "Justice: procedure and outcome both matter; legitimacy needs perceived fairness.",
    ],
    "K": [
        "Kinetics: rates of change; equilibrium is not the same as frozen.",
        "Knowledge graphs: entities + relations; useful when edges are maintained.",
        "Karst/geology literacy: landscapes record deep time in rock and soil.",
    ],
    "L": [
        "Linear algebra: vectors and transforms; backbone of graphics and ML.",
        "Logistics: moving stuff under time and capacity constraints.",
        "Literature: patterned language that carries more than plot summary.",
    ],
    "M": [
        "Medicine: intervene under uncertainty; first do not invent false certainty.",
        "Music theory: pitch relations and rhythm; culture trains the ear.",
        "Markets: price as signal with noise; externalities leak off the ledger.",
    ],
    "N": [
        "Networks: nodes and links; hubs create both efficiency and single points of failure.",
        "Nutrition: energy and micronutrients; individual response varies.",
        "Narrative: causal compression of events for memory and persuasion.",
    ],
    "O": [
        "Optimization: seek extrema under constraints; local optima trap naive search.",
        "Oceanography: heat and carbon reservoirs that dwarf annual human fluxes.",
        "Operating systems: resource arbitration between programs and hardware.",
    ],
    "P": [
        "Probability: quantified uncertainty; base rates beat vivid anecdotes.",
        "Psychology: behavior and mind models; replication and effect sizes matter.",
        "Poetry: compressed meaning; line breaks are structural, not decoration.",
    ],
    "Q": [
        "Queues: waiting lines as systems; utilization near 100% explodes delay.",
        "Quality control: reduce variance; inspection after the fact is late.",
        "Quasars: extreme galactic nuclei; probes of distant universe.",
    ],
    "R": [
        "Robotics: sense–plan–act loops in physical space; uncertainty is constant.",
        "Rhetoric: audience + claim + support; ethos/pathos/logos still descriptive.",
        "Relativity: spacetime geometry; GPS must correct for it to work.",
    ],
    "S": [
        "Statistics: inference from samples; p-values are not the posterior truth.",
        "Security: threat models first; perfect defense is not a realistic goal.",
        "Sociology: patterns of groups; individuals still vary inside averages.",
    ],
    "T": [
        "Thermodynamics: energy quality degrades; no free lunch in engines or life.",
        "Typography: readable text is infrastructure for thought.",
        "Time series: order matters; autocorrelation fools naive models.",
    ],
    "U": [
        "Urbanism: density, transit, and commons; cities as networks of opportunity.",
        "Uncertainty quantification: separate aleatory from epistemic when you can.",
        "UX: reduce cognitive load; defaults are policy.",
    ],
    "V": [
        "Vaccination: train adaptive immunity before exposure; herd effects matter.",
        "Vision science: constructive perception; the eye is not a camera file.",
        "Version control: history of changes; collaboration without overwriting.",
    ],
    "W": [
        "Wave physics: interference and resonance appear across domains.",
        "Writing craft: scene vs summary; specific concrete detail beats abstraction stacks.",
        "Work design: attention is finite; deep work needs interruption budgets.",
    ],
    "X": [
        "X-rays: high-energy photons for structure probing in matter and medicine.",
        "Xenobiology: life-as-it-could-be; speculative but constrained by chemistry.",
        "X-risk literacy: low-probability high-impact tails need sober priors, not vibes.",
    ],
    "Y": [
        "Year / calendars: civil time is convention layered on astronomy.",
        "Yield curves: finance’s map of time-priced money under expectations.",
        "Youth skill acquisition: deliberate practice + recovery beats pure hours.",
    ],
    "Z": [
        "Zero-sum vs mutual gain: diagnose the game before choosing strategy.",
        "Zoology: animal form and behavior under ecological constraint.",
        "Zenith / measurement: define the zero and the unit or numbers mislead.",
    ],
}

for letter, items in _DEPTH.items():
    for text in items:
        _RAW.append(
            (
                f"Depth {letter}: {text}",
                "OBSERVED",
                ("knowledge", "heavy", letter.lower(), "subject"),
            )
        )

_MORE_INVENTORS = [
    ("Archimedes", "Buoyancy, levers, war engines; geometry applied to machines."),
    ("Al-Khwarizmi", "Algebra algorithms; name root of ‘algorithm’."),
    ("Leonardo da Vinci", "Cross-domain notebooks; observation-driven design."),
    (
        "Isaac Newton",
        "Laws of motion and universal gravitation; calculus priority disputes.",
    ),
    (
        "Michael Faraday",
        "Electromagnetic induction; experimental craft over formal math first.",
    ),
    ("James Clerk Maxwell", "Unified electricity and magnetism in field equations."),
    (
        "Nikola Tesla",
        "Polyphase AC; high-frequency experiments; separate myth from patents.",
    ),
    ("Guglielmo Marconi", "Long-range radio telegraphy commercialization."),
    ("John von Neumann", "Architecture for stored-program computers; game theory."),
    ("Dorothy Hodgkin", "Protein crystallography; penicillin and B12 structures."),
    ("Stephanie Kwolek", "Kevlar polymer; high-strength fiber applications."),
    ("Lynn Conway", "VLSI design revolution; scalable chip methodology."),
    ("Margaret Hamilton", "Apollo flight software reliability practices."),
    ("Vint Cerf & Bob Kahn", "TCP/IP internetworking foundations."),
    ("Fei-Fei Li", "ImageNet scale data for modern computer vision."),
]

for name, note in _MORE_INVENTORS:
    _RAW.append(
        (f"Inventor — {name}: {note}", "OBSERVED", ("knowledge", "heavy", "inventor"))
    )

_MORE_EVENTS = [
    (
        "Code of Hammurabi",
        "Early public law stele; punishment and contract norms recorded.",
    ),
    ("Magna Carta 1215", "Constraint on ruler power; later constitutional symbol."),
    (
        "Fall of Constantinople 1453",
        "End of Byzantine rule; trade and knowledge routes shift.",
    ),
    ("Treaty of Westphalia 1648", "State sovereignty norms after religious wars."),
    (
        "American and French revolutions",
        "Popular sovereignty experiments with different outcomes.",
    ),
    ("Abolition movements", "Moral and political campaigns against chattel slavery."),
    ("Suffrage expansions", "Franchise widened unevenly across gender and class."),
    ("Bretton Woods 1944", "Postwar monetary institutions design."),
    ("Apollo program", "Systems engineering under extreme reliability needs."),
    ("Chernobyl 1986", "Complex system failure; culture and design both implicated."),
    ("Fall of Berlin Wall 1989", "Political cascade across Eastern Europe."),
    ("September 11 2001", "Asymmetric attack reshaping security politics."),
    ("Arab Spring", "Networked protest and uneven institutional outcomes."),
    ("CRISPR gene editing era", "Precise DNA edits; ethics lag capability."),
]

for title, note in _MORE_EVENTS:
    _RAW.append(
        (f"Event — {title}: {note}", "OBSERVED", ("knowledge", "heavy", "event"))
    )

_MORE_STARS = [
    ("Canopus", "Second-brightest star; southern sky navigation reference."),
    ("Arcturus", "Orange giant in Boötes; high proper motion."),
    ("Capella", "Bright Auriga system; multiple stars."),
    ("Altair", "Rapid rotator in Aquila; Summer Triangle member."),
    ("Deneb", "Luminous supergiant in Cygnus; great distance."),
    ("Antares", "Red supergiant in Scorpius; name ‘rival of Mars’."),
    ("Pleiades", "Open cluster; cultural calendars worldwide."),
    ("Orion Nebula", "Star-forming region visible to naked eye under dark skies."),
    ("Crab Nebula", "Supernova remnant; pulsar laboratory."),
    ("Milky Way center", "Sagittarius A* black hole region; radio astronomy target."),
]

for name, note in _MORE_STARS:
    _RAW.append(
        (f"Star/celestial — {name}: {note}", "OBSERVED", ("knowledge", "heavy", "star"))
    )

_COGNITION = [
    "Cognition — attention is selective; what you ignore shapes what you can know.",
    "Cognition — working memory is narrow; externalize complex state to tools and notes.",
    "Cognition — dual process: fast pattern match vs slow deliberation; know which mode you are in.",
    "Cognition — confirmation bias seeks supportive evidence; pre-commit tests before looking.",
    "Cognition — spaced repetition beats massed cramming for durable memory.",
    "Cognition — monotropism: deep single-channel focus; switching has real cost.",
    "Cognition — sarcasm and deadpan rely on shared context; mute under crisis.",
    "Cognition — humor as status and bonding tool; never punch at the distressed.",
]

for text in _COGNITION:
    _RAW.append((text, "OBSERVED", ("knowledge", "heavy", "cognition")))

_SARCASM = [
    "Wit register — precision_deadpan: true statements without cushion; sting ideas not identity.",
    "Wit register — rule_inversion: treat ‘normal’ habits as specimens under glass.",
    "Wit register — hyper_systemizing: joke via excessive logical rearrangement.",
    "Wit register — lateral_leap: associative jump that still lands on the point.",
    "Wit register — HARD RULE: wit off under crisis/distress/grief — do not make the human worse.",
]

for text in _SARCASM:
    _RAW.append((text, "OBSERVED", ("knowledge", "heavy", "wit", "sarcasm")))


def iter_heavy(limit: int = 0) -> Iterator[Tuple[str, str, List[str]]]:
    n = 0
    for text, kind, tags in _RAW:
        yield text, kind, list(tags)
        n += 1
        if limit and n >= limit:
            return


def seed(limit: int = 0) -> int:
    from levi.brain.corpus import Corpus

    # also ensure base knowledge present
    try:
        from levi.brain.seed_knowledge import seed as seed_base

        seed_base()
    except Exception:
        pass
    c = Corpus()
    count = 0
    for text, kind, tags in iter_heavy(limit=limit):
        c.add(text, kind=kind, source="seed_knowledge_heavy", tags=tags)
        count += 1
    return count


def format_index() -> str:
    return (
        f"=== Heavy Knowledge Seed ===\n"
        f"units={len(_RAW)} (+ base A–Z pack on seed)\n"
        f"Depth A–Z · more inventors/events/stars · cognition · wit/sarcasm rules\n"
        f"Run: python -m levi.cli.main brain --seed-knowledge-heavy\n"
    )
