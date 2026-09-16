"""Stage-1 nano knowledge — compact textbook-fact literacy units.

23 nano entries + 2 quantum entries adapted from the Levi-ai Stage-1
lineage (source-sync entry ``levi-ai``): standard textbook facts only
(Big-O, hash tables, Newton, LOTO, CPR, SI units, von Neumann entropy,
qubits, …). Rewritten as LEVI literacy units; no source text copied.

Serial scheme: KB-DOMAIN-YYYY-A-INSTANCE-CHECK. Entries marked
EDUCATION ONLY where the topic is safety/medical/first-aid.
"""

from __future__ import annotations

from typing import List, Tuple

# (text, kind, tags)
_RAW: List[Tuple[str, str, Tuple[str, ...]]] = [
    (
        "KB-PROG-2026-A-0008-8 [Programming] Big-O classes O(1), O(log n), O(n), "
        "O(n log n), O(n²), O(2ⁿ): asymptotic upper bound on growth. Method: "
        "identify the dominant operation, count it, drop constants. Pitfalls: "
        "confusing O with Theta; miscounting nested independent loops.",
        "OBSERVED",
        ("programming", "complexity", "asymptotic", "algorithms", "stage1", "nano"),
    ),
    (
        "KB-PROG-2026-A-0009-9 [Programming] Hash-table collisions are resolved "
        "by chaining or open addressing; control the load factor α and resize. "
        "Method: hash → resolve → resize. Pitfalls: poor hash function causing "
        "clustering; unbounded load factor.",
        "OBSERVED",
        ("programming", "hash", "collision", "load-factor", "stage1", "nano"),
    ),
    (
        "KB-MATH-2026-A-0009-9 [Mathematics] Matrix product (AB)ᵢⱼ = Σₖ AᵢₖBₖⱼ; "
        "identity matrix I; multiplication is not commutative. Method: verify "
        "dimensions → dot product → check against I. Pitfalls: incompatible "
        "shapes; assuming commutativity.",
        "OBSERVED",
        ("mathematics", "matrix", "linear-algebra", "identity", "stage1", "nano"),
    ),
    (
        "KB-MATH-2026-A-0010-0 [Mathematics] Derivative = lim h→0 [f(x+h)−f(x)]/h; "
        "power, sum, product, and chain rules. Method: difference quotient → "
        "limit → apply rules. Pitfalls: differentiating at discontinuities; "
        "forgetting the chain rule.",
        "OBSERVED",
        ("mathematics", "derivative", "calculus", "rate", "stage1", "nano"),
    ),
    (
        "KB-PHYS-2026-A-0015-5 [Physics] ΣF = ma; draw free-body diagrams; "
        "weight = mg; work in inertial frames. Method: diagram → components → "
        "ΣFx = max. Pitfalls: applying action-reaction to the same body; "
        "confusing mass with weight.",
        "OBSERVED",
        ("physics", "newton", "force", "acceleration", "stage1", "nano"),
    ),
    (
        "KB-PHYS-2026-A-0016-6 [Physics] Quantum error correction uses "
        "stabilizer codes (e.g. surface code): syndrome → decode → correct, "
        "threshold near 1%. Method: encode → measure stabilizers → decode → "
        "Pauli frame. Pitfalls: classical majority-vote intuition; ignoring "
        "leakage.",
        "OBSERVED",
        ("physics", "qec", "stabilizer", "surface-code", "stage1", "nano"),
    ),
    (
        "KB-CHEM-2026-A-0008-8 [Chemistry] A mole is N_A entities; n = m/M; "
        "mole ratios come from the balanced equation. Method: balance → "
        "mass-to-mole → ratio → desired quantity. Pitfalls: unbalanced "
        "equations; treating atomic mass as unitless.",
        "OBSERVED",
        ("chemistry", "mole", "avogadro", "stoichiometry", "stage1", "nano"),
    ),
    (
        "KB-LOGIC-2026-A-0006-6 [Logic] Truth tables have 2ⁿ rows; equivalence "
        "means identical tables; De Morgan's laws; p→q equals ¬p∨q. Method: "
        "list rows → evaluate columns → compare. Pitfalls: material vs causal "
        "'if'; missing a row.",
        "OBSERVED",
        ("logic", "truth-table", "equivalence", "propositional", "stage1", "nano"),
    ),
    (
        "KB-REPAIR-2026-A-0010-0 [Repair] LOTO = isolate + lock + tag + verify "
        "zero energy; every worker uses a personal lock. Method: identify → "
        "notify → isolate → lock → verify → work. Pitfalls: assuming one "
        "disconnect is enough; removing another worker's lock. "
        "EDUCATION ONLY: not a substitute for qualified electrical training.",
        "OBSERVED",
        ("repair", "loto", "energy-isolation", "safety", "stage1", "nano"),
    ),
    (
        "KB-ENG-2026-A-0007-7 [English] A topic sentence states the paragraph's "
        "main idea; unity means every sentence supports it. Method: write topic "
        "→ list support → order → cut off-topic sentences. Pitfalls: vague "
        "topic; two ideas in one paragraph.",
        "OBSERVED",
        ("english", "paragraph", "topic-sentence", "unity", "stage1", "nano"),
    ),
    (
        "KB-LIFE-2026-A-0001-1 [LifeSkills] Compound interest A = P(1+r/n)^(nt); "
        "Rule of 72 estimates doubling time; compare via APY. Method: identify "
        "P, r, n, t → compute. Pitfalls: nominal rate vs APY; ignoring inflation.",
        "OBSERVED",
        ("life", "compound-interest", "apy", "finance", "stage1", "nano"),
    ),
    (
        "KB-ARCH-2026-A-0001-1 [ComputerArchitecture] Von Neumann = stored "
        "program; CPU = ALU + control unit + registers; fetch-decode-execute "
        "cycle; the bus is the bottleneck. Method: PC → fetch → decode → ALU → "
        "writeback. Pitfalls: confusing with Harvard architecture.",
        "OBSERVED",
        ("architecture", "von-neumann", "cpu", "instruction-cycle", "stage1", "nano"),
    ),
    (
        "KB-ARCH-2026-A-0002-2 [ComputerArchitecture] Cache levels L1/L2/L3; "
        "temporal + spatial locality; misses are compulsory, capacity, or "
        "conflict. Method: address → tag/index/offset → hit/miss. Pitfalls: "
        "thrashing; false sharing.",
        "OBSERVED",
        ("architecture", "cache", "locality", "miss-rate", "stage1", "nano"),
    ),
    (
        "KB-ARCH-2026-A-0003-3 [ComputerArchitecture] Pipeline stages "
        "IF-ID-EX-MEM-WB; hazards handled by forwarding, stalls, prediction; "
        "instruction-level parallelism. Method: balance stages → detect hazards "
        "→ forward. Pitfalls: deep-pipeline mispredict penalties.",
        "OBSERVED",
        ("architecture", "pipeline", "ilp", "hazard", "stage1", "nano"),
    ),
    (
        "KB-EVERY-2026-A-0001-1 [EverydayKnowledge] SI base units m/kg/s/A/K/mol/cd; "
        "1 in = 25.4 mm; 1 lb ≈ 0.4536 kg; °C = (°F−32)×5/9. Method: identify "
        "quantity → multiply by factor → check unit. Pitfalls: mixing US and "
        "Imperial; forgetting the temperature offset.",
        "OBSERVED",
        ("everyday", "si", "conversion", "metric", "stage1", "nano"),
    ),
    (
        "KB-EVERY-2026-A-0002-2 [EverydayKnowledge] Macros: carbs/protein 4 kcal/g, "
        "fat 9 kcal/g; energy balance Δ = intake − expenditure. Method: estimate "
        "TDEE → track → adjust. Pitfalls: hidden cooking oils; reading too much "
        "into short-term scale noise.",
        "OBSERVED",
        ("everyday", "macronutrient", "calorie", "energy-balance", "stage1", "nano"),
    ),
    (
        "KB-EVERY-2026-A-0003-3 [EverydayKnowledge] DRSABC = Danger, Response, "
        "Send for help, Airway, Breathing, CPR; adult ratio 30:2. Method: scene "
        "safe → response → call → airway → breathe → CPR. Pitfalls: delaying the "
        "call; weak compressions. EDUCATION ONLY: get certified first-aid "
        "training; this is not medical advice.",
        "OBSERVED",
        ("everyday", "first-aid", "cpr", "drsabc", "stage1", "nano"),
    ),
    (
        "KB-EVERY-2026-A-0004-4 [EverydayKnowledge] Eisenhower matrix: Q1 do, "
        "Q2 schedule, Q3 delegate, Q4 eliminate; progress lives in Q2. Method: "
        "list → score → place → act. Pitfalls: labeling everything urgent; "
        "neglecting Q2.",
        "OBSERVED",
        ("everyday", "eisenhower", "prioritisation", "time", "stage1", "nano"),
    ),
    (
        "KB-EVERY-2026-A-0005-5 [EverydayKnowledge] Hand hygiene: 20–40 s soap or "
        "≥60% alcohol; WHO 5 Moments. Method: choose product → cover all "
        "surfaces → full duration → dry. Pitfalls: missed surfaces; gloves "
        "without hygiene. EDUCATION ONLY: follow local health guidance.",
        "OBSERVED",
        ("everyday", "hand-hygiene", "infection", "soap", "stage1", "nano"),
    ),
    (
        "KB-EVERY-2026-A-0006-6 [EverydayKnowledge] Latitude −90…+90, longitude "
        "−180…+180; 15° ≈ 1 hour; UTC offsets. Method: read (lat, lon) → "
        "hemisphere → time offset. Pitfalls: swapping lat/lon; irregular zones.",
        "OBSERVED",
        ("everyday", "latitude", "longitude", "time-zone", "stage1", "nano"),
    ),
    (
        "KB-EVERY-2026-A-0007-7 [EverydayKnowledge] Metric history: 1790s France "
        "origins; 1875 Metre Convention; 1960 SI; 1983 light-based metre; 2019 "
        "constant-based definitions. Method: trace definition → CGPM → fixed "
        "constant. Pitfalls: artefact-era assumptions; pre-2019 kilogram.",
        "OBSERVED",
        ("everyday", "metric", "si-history", "bipm", "stage1", "nano"),
    ),
    (
        "KB-EVERY-2026-A-0008-8 [EverydayKnowledge] Imperial = 1824 UK; "
        "US customary = pre-1824 English units; 1959 yard/pound fixed exactly in "
        "SI; the gallon differs between systems. Method: identify system → apply "
        "1959 factor. Pitfalls: gallon ambiguity; survey foot.",
        "OBSERVED",
        ("everyday", "imperial", "us-customary", "yard-pound", "stage1", "nano"),
    ),
    (
        "KB-EVERY-2026-A-0009-9 [EverydayKnowledge] Metrication: global SI "
        "adoption; US voluntary; UK partial; dual labelling common. Method: "
        "check legal context → sector → prefer SI. Pitfalls: assuming zero "
        "traditional-unit use; omitting units.",
        "OBSERVED",
        ("everyday", "metrication", "dual-units", "policy", "stage1", "nano"),
    ),
    (
        "KB-PHYS-2026-A-0013-3 [Physics] Von Neumann entropy S = −Tr(ρ ln ρ), "
        "introduced 1927 with the density-matrix formalism; S = 0 iff the state "
        "is pure. Method: construct ρ → eigenvalues/trace → interpret. "
        "Pitfalls: applying classical entropy intuition directly; claiming "
        "unitary evolution changes S (it does not).",
        "OBSERVED",
        ("physics", "entropy", "density-matrix", "purity", "stage1", "nano"),
    ),
    (
        "KB-PHYS-2026-A-0014-4 [Physics] Qubit = α|0⟩ + β|1⟩; superposition + "
        "entanglement + gates + measurement. Method: init → gates → measure → "
        "statistics. Pitfalls: 'both at once' in a classical sense; ignoring "
        "decoherence.",
        "OBSERVED",
        ("physics", "qubit", "superposition", "entanglement", "stage1", "nano"),
    ),
]


def seed(limit: int = 0) -> int:
    """Add Stage-1 nano entries to the brain corpus. Returns count added."""
    from levi.brain.corpus import Corpus

    c = Corpus()
    n = 0
    for text, kind, tags in _RAW:
        c.add(text, kind=kind, source="seed_stage1", tags=list(tags))
        n += 1
        if limit and n >= limit:
            break
    return n


def format_index() -> str:
    """One-line-per-entry index of serials and domains."""
    lines = []
    for text, _kind, _tags in _RAW:
        serial = text.split(" ", 1)[0]
        domain = text.split("[", 1)[1].split("]", 1)[0] if "[" in text else "?"
        lines.append(f"{serial}  {domain}")
    return "\n".join(lines)
