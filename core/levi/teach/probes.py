"""Synthetic teachback probe fixtures.

Each probe names a topic taught by an approved corpus and lists the
keywords that *should* appear in prepared training data covering that
topic. Fixtures are synthetic and hand-written (never user data); they
serve the data-side teachback check only.

Honesty note: probes probe *data representation*, not model capability.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Probe:
    id: str
    topic: str
    source: str  # which teach source covers it
    keywords: tuple[str, ...]


PROBES: tuple[Probe, ...] = (
    Probe(
        id="algorithms",
        topic="algorithm design and analysis",
        source="courses",
        keywords=(
            "algorithm",
            "sorting",
            "recursion",
            "graph",
            "complexity",
            "data structure",
            "dynamic programming",
        ),
    ),
    Probe(
        id="machine-learning",
        topic="machine learning fundamentals",
        source="courses",
        keywords=(
            "gradient descent",
            "overfitting",
            "training data",
            "neural network",
            "loss function",
            "regression",
        ),
    ),
    Probe(
        id="operating-systems",
        topic="operating systems concepts",
        source="courses",
        keywords=(
            "process",
            "scheduling",
            "memory management",
            "file system",
            "concurrency",
            "kernel",
        ),
    ),
    Probe(
        id="networking",
        topic="computer networking basics",
        source="courses",
        keywords=(
            "protocol",
            "tcp",
            "packet",
            "routing",
            "bandwidth",
            "latency",
        ),
    ),
    Probe(
        id="security",
        topic="defensive security analysis",
        source="academy",
        keywords=(
            "attack",
            "defend",
            "detection",
            "telemetry",
            "mitre",
            "vulnerability",
        ),
    ),
    Probe(
        id="statistics",
        topic="statistics and probability",
        source="courses",
        keywords=(
            "probability",
            "distribution",
            "variance",
            "hypothesis",
            "regression",
            "sample",
        ),
    ),
    Probe(
        id="programming-languages",
        topic="programming language concepts",
        source="courses",
        keywords=(
            "compiler",
            "syntax",
            "type system",
            "interpreter",
            "semantics",
            "parsing",
        ),
    ),
    Probe(
        id="organism-dna",
        topic="LEVI organism architecture",
        source="seed",
        keywords=(
            "organism",
            "dna",
            "daemon",
            "levi",
            "l.w.p.",
            "factory",
        ),
    ),
    Probe(
        id="growth-loop",
        topic="growth loop and learnings",
        source="growth",
        keywords=(
            "learning",
            "cycle",
            "memory",
            "confidence",
            "reflection",
            "journal",
        ),
    ),
    Probe(
        id="databases",
        topic="databases and data modeling",
        source="courses",
        keywords=(
            "query",
            "index",
            "transaction",
            "schema",
            "normalization",
            "sql",
        ),
    ),
    Probe(
        id="computer-graphics",
        topic="computer graphics",
        source="courses",
        keywords=(
            "rendering",
            "shader",
            "rasterization",
            "geometry",
            "pixel",
            "texture",
        ),
    ),
    Probe(
        id="theory",
        topic="theory of computation",
        source="courses",
        keywords=(
            "turing machine",
            "computability",
            "np-complete",
            "automata",
            "reduction",
            "decidable",
        ),
    ),
    Probe(
        id="field-guides",
        topic="course field guides",
        source="briefs",
        keywords=(
            "start here",
            "topic keywords",
            "all courses",
            "extractive summary",
            "live links",
            "prerequisites",
        ),
    ),
    Probe(
        id="playbooks",
        topic="defensive security playbooks",
        source="playbooks",
        keywords=(
            "playbook",
            "detection",
            "hardening",
            "triage",
            "telemetry",
            "mitre",
            "hunt",
        ),
    ),
)


def probes_for_source(source: str) -> tuple[Probe, ...]:
    """Probes whose ``source`` field matches (e.g. after a partial prepare)."""
    return tuple(p for p in PROBES if p.source == source)
