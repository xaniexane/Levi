"""Echo — taken / not-taken / wild parallel paths (kernel organ).

The one echo / branch-exploration implementation in this tree. A prior
lineage's graph/echoverse.py was correctly rejected at merge time to avoid
a second, competing implementation of the same concept — do not reintroduce
one; extend this module instead.

Explore-space wiring (DNA interpenetration):

Echo is the EXPLORE-SPACE organ: its doctrine is interpenetration across
DNA strips — the three strands of the organism's DNA (levi =
companion/adaptive intelligence, lwp = L.W.P. structural physics, factory =
constructive will). :func:`interpenetrate` crosses patterns between strips
of different strands; :func:`explore_space` runs branch exploration and
interpenetration together. Two binding laws govern this:

- Risk ceiling law: an interpenetration inherits the STRICTEST risk
  ceiling of the two strips crossed (high > medium > low). Crossing
  never dilutes risk.
- Bounded simulation law: :func:`explore_space` caps interpenetration
  output at ``cycles * 4`` records. The cap is documented, not hidden.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List
import hashlib


# ---------------------------------------------------------------------------
# run_echo / format_echo (original branch exploration — unchanged)
# ---------------------------------------------------------------------------


def run_echo(seed: str, cycles: int = 3) -> Dict:
    """Explore taken / not-taken / wild parallel paths for ``seed``.

    Raises ValueError when ``cycles`` is not a non-negative int.
    """
    if not isinstance(seed, str):
        raise ValueError(
            "run_echo: seed must be a string, got %s" % type(seed).__name__
        )
    if isinstance(cycles, bool) or not isinstance(cycles, int) or cycles < 0:
        raise ValueError(
            "run_echo: cycles must be a non-negative int, got %r" % (cycles,)
        )
    s = (seed or "silence").strip()
    h = int(hashlib.sha256(s.encode()).hexdigest()[:8], 16)
    taken = [
        "Commit to the visible path",
        "Ship the smallest reversible step",
        "Follow the constraint already accepted",
    ]
    not_taken = [
        "Defer until one more signal arrives",
        "Hold the line; observe cascade pressure",
        "Refuse the frame; restate the problem",
    ]
    wild = [
        "Invert the goal; optimize for optionality",
        "Compose with an unrelated organ",
        "Treat failure as alchemy fuel; extract the inverse map",
    ]
    branches: List[Dict] = [
        {
            "kind": "taken",
            "label": taken[h % 3],
            "summary": f"Given “{s[:80]}”, spend current commitment; reduce ambiguity now.",
            "risk": "medium",
        },
        {
            "kind": "not_taken",
            "label": not_taken[(h + 1) % 3],
            "summary": "Preserve information; cost is time and possible lock-in elsewhere.",
            "risk": "low",
        },
        {
            "kind": "wild",
            "label": wild[(h + 2) % 3],
            "summary": "High novelty; higher verification burden — useful when the frame is the bottleneck.",
            "risk": "high",
        },
    ]
    for i in range(min(cycles, 3)):
        branches[i % 3]["summary"] += (
            f" Cycle t{i + 1}: pressure redistributes under governor."
        )
    insights = [
        "Optionality compounds when reversibility is protected.",
        "The taken path is cheap only if verification is cheap.",
        "Wild branches need circuit-breakers or they become identity.",
    ]
    return {
        "seed": s,
        "branches": branches,
        "insight": insights[h % 3],
        "organ": "echo",
    }


def format_echo(result: Dict) -> str:
    """Render a :func:`run_echo` result.

    Raises ValueError when ``result`` lacks the expected echo keys (a
    malformed record renders as an explicit error, not a KeyError).
    """
    if not isinstance(result, dict):
        raise ValueError("format_echo: result must be a dict")
    for key in ("seed", "branches", "insight"):
        if key not in result:
            raise ValueError("format_echo: result is missing key %r" % key)
    lines = [f"=== Echo (seed: {str(result['seed'])[:60]}) ===", ""]
    for b in result["branches"]:
        lines.append(f"[{b['kind']}] {b['label']}  risk={b['risk']}")
        lines.append(f"  {b['summary']}")
    lines.append("")
    lines.append(f"Insight: {result['insight']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# DNA strips + interpenetration (explore-space wiring)
# ---------------------------------------------------------------------------

STRANDS = ("levi", "lwp", "factory")
"""The three DNA strands Echo interpenetrates across.

- ``levi``: companion / adaptive intelligence
- ``lwp``: L.W.P. structural physics
- ``factory``: constructive will
"""

RISKS = ("low", "medium", "high")
"""Risk levels, ordered weakest to strictest. Used by the risk ceiling law."""


@dataclass(frozen=True)
class DNAStrip:
    """One named strip of organism DNA carried by Echo.

    ``strand`` is one of the three DNA strands; ``patterns`` are the named
    patterns/ideas the strip carries; ``risk`` is its risk ceiling.
    Malformed strips raise ValueError at construction (fail-closed — a
    corrupt strip never enters an interpenetration).
    """

    id: str
    strand: str
    patterns: List[str]
    risk: str

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError(
                "DNAStrip: id must be a non-empty string, got %r" % (self.id,)
            )
        if self.strand not in STRANDS:
            raise ValueError(
                "DNAStrip: strand must be one of %s, got %r"
                % ("/".join(STRANDS), self.strand)
            )
        if not isinstance(self.patterns, list) or any(
            not isinstance(p, str) or not p.strip() for p in self.patterns
        ):
            raise ValueError(
                "DNAStrip: patterns must be a list of non-empty strings, "
                "got %r" % (self.patterns,)
            )
        if self.risk not in RISKS:
            raise ValueError(
                "DNAStrip: risk must be one of %s, got %r"
                % ("/".join(RISKS), self.risk)
            )


@dataclass(frozen=True)
class Interpenetration:
    """One cross of two patterns from strips of different strands.

    ``strip_a``/``strip_b`` are strip ids, ``fused`` describes the cross,
    and ``risk`` is the inherited risk ceiling (strictest of the two).
    """

    strip_a: str
    strip_b: str
    fused: str
    risk: str


def _risk_ceiling(risk_a: str, risk_b: str) -> str:
    """Return the stricter of two risk levels (high > medium > low)."""
    return RISKS[max(RISKS.index(risk_a), RISKS.index(risk_b))]


def interpenetrate(strips: List[DNAStrip]) -> List[Interpenetration]:
    """Cross patterns across DNA strips of different strands.

    For every ordered pair of strips from DIFFERENT strands, every pattern
    of the first is fused with every pattern of the second. The record's
    risk inherits the strictest risk ceiling of the two strips
    (:func:`_risk_ceiling`) — crossing never dilutes risk.

    Ordering is deterministic: strips sorted by id, patterns sorted within
    each strip, so identical input always yields identical output.

    An empty strip list returns ``[]``; a strip with no patterns
    contributes nothing (no content is invented). Non-DNAStrip entries or
    a non-list input raise ValueError (fail-closed).
    """
    if not isinstance(strips, list):
        raise ValueError(
            "interpenetrate: strips must be a list of DNAStrip, got %s"
            % type(strips).__name__
        )
    for s in strips:
        if not isinstance(s, DNAStrip):
            raise ValueError(
                "interpenetrate: every strip must be a DNAStrip, got %s"
                % type(s).__name__
            )
    records: List[Interpenetration] = []
    ordered = sorted(strips, key=lambda s: s.id)
    for a in ordered:
        for b in ordered:
            if a.strand == b.strand:
                continue  # same strand never combines — no self-echo
            if not a.patterns or not b.patterns:
                continue  # no invented content
            for pa in sorted(a.patterns):
                for pb in sorted(b.patterns):
                    records.append(
                        Interpenetration(
                            strip_a=a.id,
                            strip_b=b.id,
                            fused='"%s" × "%s"' % (pa, pb),
                            risk=_risk_ceiling(a.risk, b.risk),
                        )
                    )
    return records


def explore_space(seed: str, strips: List[DNAStrip], cycles: int = 3) -> Dict:
    """Run branch exploration AND DNA interpenetration together.

    Returns ``{'organ': 'echo', 'seed': ..., 'branches': [...],
    'insight': ..., 'interpenetrations': [...]}``.

    Bounded simulation law: the interpenetration output is capped at
    ``cycles * 4`` records. With many patterns the full cross is computed
    first (deterministic), then truncated to the cap — the bound is
    explicit here, not hidden inside :func:`interpenetrate`.

    Raises ValueError on a non-string seed, a non-non-negative-int
    ``cycles``, or malformed strips.
    """
    base = run_echo(seed, cycles=cycles)
    records = interpenetrate(strips)
    cap = cycles * 4
    base["interpenetrations"] = [asdict(r) for r in records[:cap]]
    return base


def format_interpenetrations(records: List) -> str:
    """Render :func:`interpenetrate` records (or their dict forms).

    Raises ValueError when ``records`` is not a list of interpenetration
    records — a malformed set renders as an explicit error, not a KeyError.
    """
    if not isinstance(records, list):
        raise ValueError("format_interpenetrations: records must be a list")
    normalized: List[Dict] = []
    for r in records:
        if isinstance(r, Interpenetration):
            normalized.append(asdict(r))
        elif isinstance(r, dict):
            for key in ("strip_a", "strip_b", "fused", "risk"):
                if key not in r:
                    raise ValueError(
                        "format_interpenetrations: record missing key %r" % key
                    )
            normalized.append(r)
        else:
            raise ValueError(
                "format_interpenetrations: record must be an Interpenetration "
                "or dict, got %s" % type(r).__name__
            )
    lines = ["=== Echo interpenetrations ===", ""]
    if not normalized:
        lines.append("No interpenetrations (no cross-strand pattern pairs).")
        return "\n".join(lines)
    for r in normalized:
        lines.append("%s × %s  risk=%s" % (r["strip_a"], r["strip_b"], r["risk"]))
        lines.append(f"  {r['fused']}")
    return "\n".join(lines)
