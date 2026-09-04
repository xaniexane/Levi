"""
Hyperdrive corpus expansion — modern / enterprise / L.W.P. operational knowledge units.

Loaded via: python -m levi.cli.main brain --seed-expand  OR seed_hyperdrive.seed()
"""
from __future__ import annotations

from typing import Iterator, Tuple

# (text, kind, tags)
UNITS: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    ("LEVI Full Cloud Model: local SSA is oxygen; cloud is optional wings; server never needs plaintext.", "OBSERVED", ("cloud", "model", "invariant")),
    ("Phase A active: offline companion, HITL, L.W.P. story organs, 97 genres, no account required.", "OBSERVED", ("phase", "a")),
    ("Phase B specified: Argon2id CMK at rest; Double Ratchet for sessions; ciphertext-only sync.", "INFERENCE", ("phase", "b", "crypto")),
    ("Phase C planned: teams, billing, hosted UI — still not cloud-owns-keys.", "HYPOTHESIS", ("phase", "c")),
    ("HITL rule: silence is not approval. Consequential actions require explicit gate.", "OBSERVED", ("hitl", "policy")),
    ("Crisis floor: offline companion contains distress; no jokes; name one urgent concrete thing.", "OBSERVED", ("crisis", "companion")),
    ("Story cascade order: Hook → Complication → Midpoint → Darkening → Convergence → Aftermath → Echo → Spiral → Final Cost → Coda.", "OBSERVED", ("story", "lwp")),
    ("Scar law: consequences accrue; wounds do not reset for convenience.", "OBSERVED", ("lwp", "story")),
    ("Wyrd-Rupture: scarce ROM beat (McCarthy/Morrison/Gibson lenses); budget refills with word-band progress.", "OBSERVED", ("lwp", "rupture")),
    ("REIM Parallel Echo: 2–4 tracks; crown commits one into continuity under operator choice.", "OBSERVED", ("lwp", "reim")),
    ("RIEM / deny: rejected scenes leave ghost residue for causal bleed.", "OBSERVED", ("lwp", "riem")),
    ("Gold path target: 80k words; rank progression D3→D4→D5 under sustained output.", "OBSERVED", ("lwp", "gold")),
    ("Chat modes: companion, mentor, challenger, writer, builder, quiet — session persisted under ~/.levi/chat_sessions.", "OBSERVED", ("chat", "companion")),
    ("Persona lattice: 230 entries including core, relationship, temperament, lens, and mood composites.", "OBSERVED", ("persona")),
    ("Nervous system selects persona from stress/anxiety/workload/bond when unlocked.", "OBSERVED", ("nervous", "persona")),
    ("Opportunity Rail: HITL-gated automation cars; never auto customer contact.", "OBSERVED", ("rail", "hitl")),
    ("Mirror Cascade: reverse cross-check fingerprint for plan integrity.", "OBSERVED", ("mirror", "lwp")),
    ("Corpus tags: OBSERVED vs INFERENCE vs HYPOTHESIS — never launder guesses as facts.", "OBSERVED", ("corpus", "evidence")),
    ("Export/exit: life-pack zip always available; no lock-in via ciphertext hostage.", "OBSERVED", ("export", "enterprise")),
    ("Enterprise checklist: HITL, crisis, export, provenance, companion, personas, model, phases, daemon, integrate, contact.", "OBSERVED", ("enterprise")),
    ("Model relay order: local Ollama → optional cloud endpoints → offline synthesizer.", "OBSERVED", ("relay", "model")),
    ("Interpenetration law: every organ needs its other half; Factory under L.W.P. stages.", "OBSERVED", ("symbiosis", "factory")),
    ("Provenance: closed-source LEVI DNA; not a generic wrapper; foreign-brand scan available.", "OBSERVED", ("provenance")),
    ("Story prose offline: genre atmosphere + beat openers + sensory triangle + scar/closing law.", "OBSERVED", ("story", "prose")),
    ("UI local: static/index.html ops surface; static/lwp-model.html literary console; levi serve-ui.", "OBSERVED", ("ui")),
    ("Hyperdrive posture: daily production use valid on operable set; do not wait for 100%.", "INFERENCE", ("hyperdrive", "ops")),
    ("When expanding story, prefer cascade-typed beats over random flourish.", "OBSERVED", ("story", "craft")),
    ("Writer mode chat: literary clarity; offer levi model expand when relevant.", "INFERENCE", ("chat", "writer")),
    ("Builder mode chat: prefer scaffolds, rail dry-runs, next ship step.", "INFERENCE", ("chat", "builder")),
    ("Challenger mode: name the weakest hinge; no false comfort.", "INFERENCE", ("chat", "challenger")),
)


def iter_hyperdrive(limit: int = 0) -> Iterator[Tuple[str, str, list]]:
    n = 0
    for text, kind, tags in UNITS:
        yield text, kind, list(tags)
        n += 1
        if limit and n >= limit:
            return


def seed(limit: int = 0) -> int:
    from levi.brain.corpus import Corpus
    c = Corpus()
    count = 0
    for text, kind, tags in iter_hyperdrive(limit=limit):
        c.add(text, kind=kind, source="seed_hyperdrive", tags=tags)
        count += 1
    return count
