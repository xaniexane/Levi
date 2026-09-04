"""
General knowledge corpus — subjects, events, inventors, stars, A–Z, and X-domain.

Literacy units for LEVI SI (symbiotic intelligence). Not a substitute for
primary sources; labeled OBSERVED/INFERENCE as appropriate.
"""
from __future__ import annotations

from typing import Iterator, List, Tuple

# (text, kind, tags)
_RAW: List[Tuple[str, str, Tuple[str, ...]]] = []

# ── A–Z subject spines ─────────────────────────────────────────
_AZ_SUBJECTS = {
    "A": ("Astronomy", "Stars, planets, cosmology; observation precedes theory."),
    "B": ("Biology", "Life systems, cells, evolution, ecology — complexity with constraints."),
    "C": ("Chemistry", "Elements, bonds, reactions; the periodic table as a map of possibility."),
    "D": ("Design", "Form follows constraint; good design reduces unnecessary friction."),
    "E": ("Economics", "Incentives, trade-offs, scarcity; models are maps not territory."),
    "F": ("Physics", "Forces, energy, spacetime; laws constrain engineering and story alike."),
    "G": ("Geography", "Place shapes culture, climate, conflict, and trade routes."),
    "H": ("History", "Causal chains of human events; primary sources beat slogans."),
    "I": ("Information", "Bits, signal vs noise, entropy; communication needs shared code."),
    "J": ("Jurisprudence", "Law as negotiated constraint; rights need enforcement design."),
    "K": ("Knowledge", "Epistemology: OBSERVED vs INFERENCE vs HYPOTHESIS — label claims."),
    "L": ("Language", "Meaning, grammar, translation; words shape what can be thought."),
    "M": ("Mathematics", "Proof, structure, quantity; abstraction that travels across domains."),
    "N": ("Neuroscience", "Brain as organ of prediction and control; literacy not diagnosis."),
    "O": ("Optics", "Light, vision, lenses; measurement instruments extend the senses."),
    "P": ("Philosophy", "Clarity about values, mind, knowledge, and the good life."),
    "Q": ("Quantum", "Superposition, measurement, uncertainty — counterintuitive but tested."),
    "R": ("Rhetoric", "Persuasion with honesty; argument structure matters more than volume."),
    "S": ("Systems", "Feedback, leverage, delays; local fixes can create global harm."),
    "T": ("Technology", "Tools amplify intent; governance of tools is part of the tool."),
    "U": ("Universe", "Scale from quark to cosmos; humility scales with distance."),
    "V": ("Value", "What is worth optimizing; metrics can distort the goal."),
    "W": ("Writing", "Structure, voice, revision; clarity is kindness to the reader."),
    "X": ("X-domain / unknowns", "Edge cases, anomalies, research frontiers — label uncertainty."),
    "Y": ("Youth / development", "Learning windows, practice, recovery; growth is nonlinear."),
    "Z": ("Zero / foundations", "Base cases, axioms, first principles before elaborate towers."),
}

for letter, (name, blurb) in _AZ_SUBJECTS.items():
    _RAW.append((
        f"Subject {letter} — {name}: {blurb}",
        "OBSERVED",
        ("knowledge", "subject", letter.lower(), name.lower().split()[0]),
    ))

# ── Famous inventors (sample high-signal) ──────────────────────
_INVENTORS = [
    ("Ada Lovelace", "Early analytical notes on the Analytical Engine; algorithm thinking."),
    ("Alan Turing", "Computation model, wartime codebreaking, foundations of AI thought."),
    ("Marie Curie", "Radioactivity research; two Nobels; laboratory rigor under constraint."),
    ("Nikola Tesla", "AC systems, high-frequency experiments; myth and engineering both."),
    ("Thomas Edison", "Industrial lab model, electric light commercialization, patents."),
    ("Grace Hopper", "Compilers, COBOL influence; made machines more human-addressable."),
    ("Tim Berners-Lee", "World Wide Web protocols; open hypertext on the internet."),
    ("Katherine Johnson", "Orbital mechanics calculations critical to early NASA flights."),
    ("Hedy Lamarr", "Frequency-hopping spread spectrum concept with George Antheil."),
    ("James Watt", "Steam engine efficiency improvements that powered industrial scale."),
    ("Johannes Gutenberg", "Movable-type printing press; mass literacy infrastructure."),
    ("Alexander Graham Bell", "Telephone development; communication distance collapsed."),
    ("Wright brothers", "Controlled powered flight; iterative experiment over theory alone."),
    ("Rosalind Franklin", "X-ray diffraction data central to DNA structure understanding."),
    ("Claude Shannon", "Information theory; bits as the unit of communication."),
]

for name, note in _INVENTORS:
    _RAW.append((
        f"Inventor — {name}: {note}",
        "OBSERVED",
        ("knowledge", "inventor", "history", "technology"),
    ))

# ── Events (civilizational hinges) ─────────────────────────────
_EVENTS = [
    ("Agricultural Revolution", "Settled farming enabled surplus, cities, specialization."),
    ("Axial Age ideas", "Parallel ethical-philosophical traditions across regions."),
    ("Printing revolution", "Books scaled; authority and literacy patterns shifted."),
    ("Scientific Revolution", "Experiment and math as public methods of knowing nature."),
    ("Industrial Revolution", "Energy + machines reorganized labor, cities, climate path."),
    ("World Wars", "Industrial total war; institutions and human rights agendas followed."),
    ("Moon landing 1969", "Systems engineering under extreme constraint; global broadcast."),
    ("Internet public expansion", "Packet networks + web → global publish/subscribe culture."),
    ("Human genome draft", "Biology entered large-scale data; medicine still translating."),
    ("COVID-19 pandemic", "Global shock to health, supply chains, remote work norms."),
]

for title, note in _EVENTS:
    _RAW.append((
        f"Event — {title}: {note}",
        "OBSERVED",
        ("knowledge", "event", "history"),
    ))

# ── Stars / celestial literacy ─────────────────────────────────
_STARS = [
    ("Sun", "G-type star; drives Earth's climate and energy budget."),
    ("Sirius", "Brightest star in the night sky; binary system."),
    ("Betelgeuse", "Red supergiant in Orion; late-stage stellar evolution."),
    ("Polaris", "Near north celestial pole; navigation reference for centuries."),
    ("Vega", "Bright Lyra star; former north star on precession timescale."),
    ("Proxima Centauri", "Nearest known star to the Sun; red dwarf system."),
    ("Rigel", "Blue supergiant in Orion; high luminosity."),
    ("Andromeda Galaxy", "Nearest major galaxy; on a long collision course with Milky Way."),
]

for name, note in _STARS:
    _RAW.append((
        f"Star/celestial — {name}: {note}",
        "OBSERVED",
        ("knowledge", "astronomy", "star"),
    ))

# ── Famous cultural stars (careful, literacy not gossip) ───────
_CULTURE = [
    ("Shakespeare", "Drama and language density that still shapes English narrative craft."),
    ("Beethoven", "Musical form under constraint of deafness; emotional architecture."),
    ("Frida Kahlo", "Self-portraiture as political and bodily testimony."),
    ("Miyamoto Musashi", "Strategy text (Book of Five Rings); practice under pressure."),
    ("Hypatia", "Late antique scholar symbol; science and philosophy under civic stress."),
]

for name, note in _CULTURE:
    _RAW.append((
        f"Cultural figure — {name}: {note}",
        "OBSERVED",
        ("knowledge", "culture", "history"),
    ))

# ── X-domain (unknowns, edge, research) ────────────────────────
_X = [
    ("X — dark matter", "Gravitational effects without luminous counterpart; open physics."),
    ("X — consciousness", "Hard problem remains; report mechanisms carefully, avoid dogma."),
    ("X — AGI timelines", "Forecasts are HYPOTHESIS; separate capability from deployment risk."),
    ("X — origin of life", "Multiple pathways proposed; evidence still incomplete."),
    ("X — quantum gravity", "Unifying GR and quantum theory unfinished."),
    ("X — Fermi paradox", "Absence of clear technosignatures vs vast cosmos — open."),
    ("X — long-term alignment", "SI systems need corrigibility, HITL, and exportable user control."),
]

for title, note in _X:
    _RAW.append((f"{title}: {note}", "HYPOTHESIS", ("knowledge", "x", "frontier", "uncertainty")))

# ── SI framing for LEVI ────────────────────────────────────────
_SI = [
    ("LEVI is SI: synthetic intelligence — constructed local kernel; symbiotic method with human + optional models under HITL.", "OBSERVED", ("si", "levi", "identity")),
    ("SI (synthetic) is not a person-replacement: amplify judgment, hold continuity, refuse silent consequential action.", "OBSERVED", ("si", "policy")),
    ("10/10 cloud model posture: offline-complete core; cloud is encrypted optional wing.", "INFERENCE", ("si", "cloud", "model")),
    ("General knowledge serves conversation and planning; still cite primary sources for decisions.", "OBSERVED", ("knowledge", "policy")),
]

for text, kind, tags in _SI:
    _RAW.append((text, kind, tags))


def iter_knowledge(limit: int = 0) -> Iterator[Tuple[str, str, List[str]]]:
    n = 0
    for text, kind, tags in _RAW:
        yield text, kind, list(tags)
        n += 1
        if limit and n >= limit:
            return


def seed(limit: int = 0) -> int:
    from levi.brain.corpus import Corpus
    c = Corpus()
    count = 0
    for text, kind, tags in iter_knowledge(limit=limit):
        c.add(text, kind=kind, source="seed_knowledge", tags=tags)
        count += 1
    return count


def format_index() -> str:
    lines = [
        "=== General Knowledge Seed (A–Z · events · inventors · stars · X) ===",
        f"units={len(_RAW)}",
        "Subjects A–Z · inventors · civilizational events · celestial · culture · X-frontier · SI framing",
        "Run: python -m levi.cli.main brain --seed-knowledge",
    ]
    return "\n".join(lines)
