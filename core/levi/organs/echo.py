"""Echo — taken / not-taken / wild parallel paths (kernel organ).

The one echo / branch-exploration implementation in this tree. A prior
lineage's graph/echoverse.py was correctly rejected at merge time to avoid
a second, competing implementation of the same concept — do not reintroduce
one; extend this module instead."""

from __future__ import annotations

from typing import Dict, List
import hashlib


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
