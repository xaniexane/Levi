"""Rendering the living state: the prompt block and the constellation.

Two views of the same organism:

* :func:`render_block` — a compact, line-budgeted block prepended to the
  agent prompt so the model *feels* the conversation:
  ``THREADS / ENTITIES / OPEN LOOPS / RECALLED TURNS``.
* :func:`render_constellation` — the flair. A beautiful readout of the
  conversation as a starfield: threads are stars whose brightness is live
  salience, with sparkline trails showing each thread's life, entities as
  satellites, open loops as pending orbits. Rendered with ``levi.ux``
  (graceful plain-text fallback when it is unavailable).
"""

from __future__ import annotations

from typing import List, Optional, Tuple


def render_block(
    state,
    recalled: Optional[List[Tuple[int, float, str]]] = None,
    max_lines: int = 9,
) -> str:
    """Compact prompt block describing live conversational state."""
    lines: List[str] = []
    threads = state.live_threads()
    if threads:
        lines.append(
            "THREADS: "
            + " · ".join(
                "%s(s=%.2f%s)"
                % (
                    t["name"],
                    t["salience"],
                    ", REIGNITED" if t.get("reignited") else "",
                )
                for t in threads[:4]
            )
        )
    ents = state.live_entities()
    if ents:
        lines.append(
            "ENTITIES: "
            + " · ".join("%s(s=%.2f)" % (e["name"], e["salience"]) for e in ents[:5])
        )
    if state.last_resolution:
        pron, ent, turn = state.last_resolution
        lines.append('PRONOUN: "%s" -> %s (turn %d)' % (pron, ent, turn))
    loops = state.open_loops()
    if loops:
        lines.append(
            "OPEN LOOPS: "
            + " · ".join(
                "⏳[%s] %s (t%d)" % (loop["kind"], loop["text"][:60], loop["opened_turn"])
                for loop in loops[:3]
            )
        )
    if recalled:
        turns = getattr(state, "turns", [])
        bits = []
        for idx, score, _ in recalled[:3]:
            if 0 <= idx < len(turns):
                snippet = turns[idx]["text"][:70].replace("\n", " ")
                bits.append('[t%d, r=%.2f] "%s…"' % (idx, score, snippet))
        if bits:
            lines.append("RECALLED TURNS: " + " · ".join(bits))
    return "\n".join(lines[:max_lines])


def _ux():
    try:
        from levi.ux import effects as ux  # type: ignore

        return ux
    except Exception:
        return None


def render_constellation(state) -> str:
    """The conversation as a starfield. Threads are stars; salience is light.

    Returns a string (never prints) so callers choose the sink.
    """
    ux = _ux()
    out: List[str] = []
    if ux:
        out.append(ux.banner("✦ thread-sense", "conversational proprioception"))
    else:
        out.append("=== thread-sense: conversational proprioception ===")

    threads = state.live_threads()
    if threads:
        if ux:
            rows = []
            for t in threads:
                star = (
                    "✦"
                    if t["salience"] >= 0.7
                    else ("✧" if t["salience"] >= 0.35 else "·")
                )
                name = "%s %s" % (star, t["name"])
                if t.get("reignited"):
                    name += "  ⟲ reignited"
                rows.append(
                    [
                        name,
                        ux.meter(t["salience"], 1.0, width=14),
                        ux.sparkline(t.get("history", [t["salience"]])),
                        "t%d" % t["last_turn"],
                    ]
                )
            out.append(ux.Table(["thread", "salience", "life", "last"], rows).render())
        else:
            for t in threads:
                out.append(
                    "  * %s  salience=%.2f  last=t%d%s"
                    % (
                        t["name"],
                        t["salience"],
                        t["last_turn"],
                        "  [REIGNITED]" if t.get("reignited") else "",
                    )
                )
    else:
        out.append("  (no live threads yet — the conversation is still forming)")

    ents = state.live_entities()
    if ents:
        out.append("")
        out.append(
            "satellites: "
            + " · ".join("%s(%.2f)" % (e["name"], e["salience"]) for e in ents[:6])
        )

    loops = state.open_loops()
    if loops:
        out.append("")
        out.append("pending orbits (open loops LEVI owes):")
        for loop in loops:
            out.append(
                "  ⏳ [%s] %s — opened t%d"
                % (loop["kind"], loop["text"][:70], loop["opened_turn"])
            )

    if state.last_resolution:
        pron, ent, turn = state.last_resolution
        out.append("")
        out.append('coreference: "%s" resolved → %s (turn %d)' % (pron, ent, turn))

    if state.facts:
        out.append("")
        out.append("established facts: %d (immune sense armed)" % len(state.facts))

    return "\n".join(out)
