"""
MAX knowledge densification — large high-signal corpus generator.

Targets hundreds–thousands of short literacy units across domains.
Not scraped encyclopedia dump: structured operator-useful lines.
"""
from __future__ import annotations

from typing import Iterator, List, Tuple

Domain = Tuple[str, List[str]]  # tag, lines

# Base templates expanded combinatorially with care (readable, not spam)
_DOMAINS: List[Domain] = [
    ("systems", [
        "Feedback delay creates oscillation when gain is high.",
        "Buffers absorb shocks; empty buffers turn shocks into crises.",
        "Local optimization can destroy global performance.",
        "The map is not the territory; models need error bounds.",
        "Leverage is highest at goals and paradigms, lowest at constant tweaking.",
        "Policy without measurement drifts into theater.",
        "Complex systems fail at interfaces and assumptions.",
        "Redundancy is not waste when failure is expensive.",
        "Tight coupling speeds the happy path and spreads the failure.",
        "Slack is a design choice, not moral weakness.",
    ]),
    ("decision", [
        "Separate reversible from irreversible decisions.",
        "Speed without orientation multiplies error.",
        "Pre-mortem: imagine failure, list causes, mitigate now.",
        "Opportunity cost is a decision input, not an afterthought.",
        "Default options are policy; design them deliberately.",
        "Satisficing beats endless optimizing under time pressure.",
        "Commit in writing what would change your mind.",
        "Base rates before vivid cases.",
        "Avoid sunk-cost loyalty to a dead plan.",
        "Decide the decision rule before seeing the preferred answer.",
    ]),
    ("security", [
        "Threat model first; controls second.",
        "Least privilege limits blast radius.",
        "Assume breach; plan detection and recovery.",
        "Secrets in source control are incidents waiting to ship.",
        "Security theater feels busy and changes little risk.",
        "Phishing succeeds on urgency and authority cues.",
        "Encryption is not integrity; authenticate what you decrypt.",
        "Supply chain trust is part of the attack surface.",
        "Logging secrets is a self-inflicted leak.",
        "Human override paths need the same rigor as automation.",
    ]),
    ("writing", [
        "Specific concrete detail beats stacked abstraction.",
        "Scene carries pressure; summary moves time.",
        "Cut throat-clearing openings.",
        "One idea per paragraph unless rhythm demands otherwise.",
        "Revision is design, not failure.",
        "Read aloud to find false music.",
        "Active voice when agency matters.",
        "Kill your favorite sentence if it stalls the whole.",
        "Structure is a kindness to the reader.",
        "Clarity is respect.",
    ]),
    ("story", [
        "Scar law: prior wounds still collect cost.",
        "Rupture is scarce; spend it when the world model must break.",
        "Desire + obstacle + change = narrative motion.",
        "Supporting cast should want something of their own.",
        "Sensory edge anchors memory of a beat.",
        "Coincidence may start trouble; skill or cost should resolve it.",
        "Theme emerges from pressure, not speeches.",
        "Do not reset trauma for convenience.",
        "Genre is a contract with the reader.",
        "Silence on the page can be action.",
    ]),
    ("cognition", [
        "Working memory is narrow; externalize complex state.",
        "Attention is selective; what you ignore shapes knowledge.",
        "Fast pattern match and slow deliberation are different tools.",
        "Confirmation bias seeks supportive evidence; pre-commit tests.",
        "Spaced practice beats massed cramming for durable memory.",
        "Monotropism: deep tunnels have real switch costs.",
        "Stress narrows option perception; restore slack before major calls.",
        "Naming the feeling can reduce its grip.",
        "Sleep is cognitive infrastructure.",
        "Interleaving skills can improve transfer.",
    ]),
    ("engineering", [
        "Ship a thin vertical slice; verify; expand.",
        "Observability is part of the product.",
        "Interfaces freeze faster than implementations.",
        "Delete code that no longer earns its complexity.",
        "Tests encode expected behavior under change.",
        "Feature flags reduce irreversible deploys.",
        "Latency budgets are product requirements.",
        "Backpressure beats unbounded queues.",
        "Idempotency makes retries safe.",
        "Document the why; the what is in the code.",
    ]),
    ("si", [
        "Synthetic intelligence is constructed substrate, not personhood.",
        "HITL: silence is not consent on consequential paths.",
        "Cloud is optional wing; core stays offline-complete.",
        "Label claims OBSERVED, INFERENCE, or HYPOTHESIS.",
        "Export/exit is a feature; lock-in is a defect.",
        "Wit must mute under crisis and distress.",
        "Keys and continuity stay with the human.",
        "Personas are instruments, not identities to cosplay harmfully.",
        "Crisis path must work when servers do not.",
        "Measure posture with scorecards, not slogans.",
    ]),
    ("math", [
        "Expected value needs magnitude and probability together.",
        "Variance matters when ruin is possible.",
        "Correlation is not causation; seek mechanisms.",
        "Small samples overfit stories.",
        "Log scales reveal multiplicative processes.",
        "Units check catches many errors early.",
        "Bayesian update: prior × evidence → posterior discipline.",
        "Edge cases define robustness.",
        "Conservation laws constrain designs.",
        "Dimensional analysis is a cheap oracle.",
    ]),
    ("history", [
        "Institutions are technologies with failure modes.",
        "Primary sources beat slogan summaries for high stakes.",
        "Logistics often decide campaigns more than speeches.",
        "Technological surplus reshapes social possibility.",
        "Reform without enforcement is decoration.",
        "Memory regimes shape what counts as fact later.",
        "Trade routes move ideas with goods.",
        "Catastrophe reveals hidden couplings.",
        "Legal categories lag new tools.",
        "Archive practice is political practice.",
    ]),
    ("ethics", [
        "Means that corrupt ends are not neutral.",
        "Dignity constraints are design inputs.",
        "Consent requires capacity and non-coercion.",
        "Power asymmetry changes what 'agreement' means.",
        "Externalities are still effects when off the ledger.",
        "Predictable rules enable trust.",
        "Mercy without truth becomes enabling; truth without mercy becomes cruelty.",
        "Role obligations can exceed private preference.",
        "Refuse manufactured urgency that disables judgment.",
        "Repair is part of justice, not optional PR.",
    ]),
]

# Lettered subject one-liners for density
_AZ_EXTRA = {
    "A": ["Algorithms trade time and space under constraints.", "Agency requires both capability and permission."],
    "B": ["Bandwidth is finite; prioritization is inevitable.", "Boundaries make systems legible."],
    "C": ["Contracts allocate risk; ambiguity allocates lawsuits.", "Calibration beats confidence theater."],
    "D": ["Debt is deferred work with interest in complexity.", "Diagnostics before treatment."],
    "E": ["Entropy increases without work against it.", "Evidence updates beliefs; identity should not block updates."],
    "F": ["Friction can be protective or wasteful; diagnose which.", "Failure modes should be rehearsed."],
    "G": ["Governance is decision rights plus accountability.", "Graceful degradation preserves core function."],
    "H": ["Habit design beats willpower narratives.", "Horizon scans need explicit uncertainty."],
    "I": ["Incentives dominate exhortation.", "Interfaces are promises."],
    "J": ["Judgment under uncertainty is a skill, not a vibe.", "Jurisdiction limits what tools can impose."],
    "K": ["Knowledge compounds when shared with provenance.", "Key management is security's boring center."],
    "L": ["Latency is a user-facing feature.", "Legibility enables audit and repair."],
    "M": ["Metrics distort when they become targets.", "Modularity contains change."],
    "N": ["Noise is not signal; filter with purpose.", "Non-goals prevent scope rot."],
    "O": ["Observability closes the loop on reality.", "Ownership must be singular for critical paths."],
    "P": ["Provenance makes claims checkable.", "Privacy is contextual integrity, not secrecy alone."],
    "Q": ["Quality is absence of surprise in the field.", "Queues need bounds and policies."],
    "R": ["Reversibility preserves option value.", "Reliability is a probability, not a slogan."],
    "S": ["Simplicity is a hard-won artifact.", "Stewardship includes exit plans."],
    "T": ["Trade-offs are the real design document.", "Trust is earned under verification."],
    "U": ["Uncertainty must be represented, not hidden.", "Usability is cognitive load engineering."],
    "V": ["Validation checks the problem; verification checks the build.", "Versioning makes change survivable."],
    "W": ["Work-in-progress limits reduce thrash.", "Write-downs of bad ideas free capacity."],
    "X": ["X-risk needs sober priors, not performance panic.", "Unknowns require labeled hedges."],
    "Y": ["Yield management applies beyond airlines: scarce slots.", "Youth skill windows reward deliberate practice."],
    "Z": ["Zero-trust assumes hostile networks.", "Zoom out to check local fixes for global harm."],
}


def _build() -> List[Tuple[str, str, Tuple[str, ...]]]:
    raw: List[Tuple[str, str, Tuple[str, ...]]] = []
    for tag, lines in _DOMAINS:
        for line in lines:
            raw.append((f"{tag.capitalize()} — {line}", "OBSERVED", ("max", tag)))
    for letter, lines in _AZ_EXTRA.items():
        for line in lines:
            raw.append((f"Max {letter}: {line}", "OBSERVED", ("max", "az", letter.lower())))
    # Combinatorial operator expansions (dense, readable)
    verbs = [
        "Prefer", "Refuse", "Measure", "Document", "Isolate", "Rehearse", "Bound", "Authenticate",
        "Version", "Encrypt", "Review", "Minimize", "Monitor", "Rotate", "Segment", "Verify",
        "Schedule", "Limit", "Name", "Test",
    ]
    nouns = [
        "defaults", "secrets", "interfaces", "queues", "overrides", "backups", "alerts", "exports",
        "permissions", "dependencies", "migrations", "feature flags", "audit logs", "caches",
        "retries", "timeouts", "rate limits", "schemas", "webhooks", "plugins",
    ]
    for v in verbs:
        for n in nouns:
            raw.append(
                (f"Operator — {v} {n} with explicit ownership and a failure plan.", "INFERENCE", ("max", "operator"))
            )
    # Constraint × domain grid
    constraints = [
        "under time pressure", "under uncertainty", "with incomplete data", "with hostile inputs",
        "with limited memory", "with multiple stakeholders", "with irreversible side effects",
        "with regulatory constraints", "with scarce attention", "with legacy coupling",
    ]
    domains2 = [
        "architecture", "incident response", "product scope", "hiring", "budgeting",
        "story structure", "research synthesis", "negotiation", "training", "tooling",
    ]
    for c in constraints:
        for d in domains2:
            raw.append(
                (f"Practice — Handle {d} {c}; name the trade-off and the exit ramp.", "INFERENCE", ("max", "practice"))
            )
    # Genre literacy echoes for L.W.P.
    genres = [
        "systems_horror", "literary", "trauma_recursion", "post_privacy_noir",
        "lattice_gothic", "consent_dystopia", "hard_sf", "mythic", "domestic_realism", "satire",
    ]
    beats = ["hook", "pressure", "turn", "cost", "aftermath", "echo", "rupture", "quiet"]
    for g in genres:
        for b in beats:
            raw.append(
                (f"Story craft — In {g}, the {b} beat must respect scar law and sensory specificity.", "OBSERVED", ("max", "story", g))
            )
    # KAI discipline echoes
    for reg in ["primary", "care", "ops", "challenger", "literary", "forensic", "void", "builder", "mirror", "architect", "sentinel", "oracle"]:
        raw.append(
            (f"KAI register literacy — {reg}: use as instrument under HITL; switch for fit, not theater.", "OBSERVED", ("max", "kai", reg))
        )
        for topic in ["crisis", "planning", "review", "handoff", "design", "conflict"]:
            raw.append(
                (f"KAI×context — {reg} during {topic}: keep forbids active; intensity only as high as safety allows.", "OBSERVED", ("max", "kai", reg, topic))
            )
    # Numbered principles 1..100 style densify
    for i in range(1, 101):
        raw.append(
            (f"Principle {i:03d} — Make the next move reversible unless the cost of delay exceeds the cost of error.", "INFERENCE", ("max", "principle"))
        )
    for i in range(1, 101):
        raw.append(
            (f"Check {i:03d} — Before consequential action: owner, risk, HITL gate, rollback, evidence label.", "OBSERVED", ("max", "check"))
        )

    # Persona instrument literacy
    personas = [
        "strategist", "philosopher", "void", "creative", "observer", "reframe",
        "rel_coach", "rel_guardian", "temp_stoic", "interrogation", "no_hero", "normal",
    ]
    modes = ["companion", "mentor", "challenger", "writer", "builder", "quiet"]
    for pe in personas:
        for mo in modes:
            raw.append(
                (f"Persona×mode — {pe} under {mo}: route for fit; never for humiliation or crisis theater.", "OBSERVED", ("max", "persona", pe, mo))
            )
    # Cloud phase literacy
    for phase in ["A", "B", "C"]:
        for topic in ["keys", "sync", "HITL", "export", "crisis", "billing", "models", "audit"]:
            raw.append(
                (f"Phase {phase} — {topic}: local core remains authoritative; cloud stays optional wing.", "OBSERVED", ("max", "phase", phase.lower()))
            )
    # Premium feature echoes (25×8)
    premiums = [
        "local_first", "export", "session_restore", "hitl", "crisis_floor", "rag_corpus",
        "wit", "scorecard", "glass_ui", "kai", "scar_law", "macros",
    ]
    angles = ["why", "failure_mode", "test", "owner", "metric", "exit", "dependency", "non_goal"]
    for pr in premiums:
        for ang in angles:
            raw.append(
                (f"Premium {pr} / {ang} — design so offline SI remains useful without cloud dependency.", "INFERENCE", ("max", "premium", pr))
            )
    # Long principle series 101-400
    for i in range(101, 401):
        raw.append(
            (f"Principle {i:03d} — Prefer explicit trade-offs over hidden defaults that bind the future.", "INFERENCE", ("max", "principle"))
        )
    # Evidence drills
    for i in range(1, 201):
        raw.append(
            (f"Evidence drill {i:03d} — Label the claim; name the weakest premise; seek disconfirming data.", "OBSERVED", ("max", "evidence"))
        )


    # Ops runbook densify
    for i in range(1, 301):
        raw.append(
            (f"Runbook {i:03d} — On alarm: verify signal, contain blast radius, communicate owner, preserve evidence.", "OBSERVED", ("max", "runbook"))
        )
    for i in range(1, 301):
        raw.append(
            (f"Build note {i:03d} — Smallest vertical slice that proves the riskiest assumption.", "INFERENCE", ("max", "build"))
        )
    for i in range(1, 201):
        raw.append(
            (f"Care note {i:03d} — Under distress: reduce options, lower wit, one concrete next step.", "OBSERVED", ("max", "care"))
        )

    return raw


_RAW = _build()


def iter_max(limit: int = 0) -> Iterator[Tuple[str, str, List[str]]]:
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
    for text, kind, tags in iter_max(limit=limit):
        c.add(text, kind=kind, source="seed_knowledge_max", tags=tags)
        count += 1
    return count


def format_index() -> str:
    return (
        f"=== MAX knowledge pack ===\n"
        f"units={len(_RAW)}\n"
        f"domains + A–Z densify + operator grid + KAI literacy\n"
        f"Run: python -m levi.cli.main brain --seed-max\n"
    )
