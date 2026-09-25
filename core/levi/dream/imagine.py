"""Day-dream imagination loop: LEVI imagines vividly, the user rates it.

Chauncey's build order (2026-09-22, his words — the spec):

  "in chat LEVI imagines vividly what an item may be, we hit thumbs up /
   thumbs down, and if correct (thumbs up) Nanobit uses ASCII compression
   to store it in an indexed corpus or spreadsheet database; the whole
   corpus is glyph-compressed and indexed for offline retrieval."

The loop:

1. ``imagine_vivid(item, seed=None)`` — LEVI imagines the item vividly:
   a structured vivid description plus a deterministic symbolic ASCII
   render block. Pure and deterministic given ``(item, seed)``. Uses the
   dream engine's own ``variate`` machinery (``levi.dream.vary``) for the
   dream-lens lines — originals-first.
2. The user rates the turn thumbs up/down via ``rate_imagination``,
   which records the vote through the honest feedback path
   (``levi.growth.signals.feedback``: ``new_feedback`` /
   ``record_feedback``, target kind ``"turn"``, ref = the imagine turn
   ref). Failures teach the reflect loop, never the corpus — per
   feedback.py's own docstring, a thumbs-down is a preference learning
   ("don't repeat this") that is EXCLUDED from the curated corpus.
3. On thumbs-up, Nanobit's storage face (see ``imagery_corpus``)
   ASCII-compresses the render (zlib + base64 — Chauncey's "asci
   compression": spreadsheet-safe text) and stores it in the indexed
   corpus + CSV spreadsheet export.

The ASCII-art render is SYMBOLIC — a deterministic sigil of the
imagination, not pixels. Real pixel diffusion is a stated future step,
never claimed here.

INVARIANTS (declared, guarded in code, proven in tests):

1. "imagine_vivid is pure" — same (item, seed) always yields the
   identical record, byte for byte.
2. "A thumbs-down never enters the imagery corpus" — only the growth
   loop learns from it.
3. "A thumbs-up stores only with its feedback record linked" — the
   stored record carries the feedback id, or nothing is stored.
4. "rate_imagination refuses to store without a render" — thumbs-up
   with no render is a loud ValueError, never a silent skip.

PROOF (honest): property tests over the invariants in
``tests/test_dream_imagine.py``, not a formal proof.
"""

from __future__ import annotations

import hashlib
import random
import re
from typing import Any, Dict, List, Optional, Tuple

from levi.dream.vary import variate
from levi.growth.signals.feedback import new_feedback, record_feedback

__all__ = [
    "IMAGINE_OPERATOR",
    "imagine_vivid",
    "render_text_of",
    "rate_imagination",
]

#: Operator tag on imagination feedback records.
IMAGINE_OPERATOR = "levi-imagine"

_WORD_RE = re.compile(r"[a-z0-9]+")


def _words(text: str) -> List[str]:
    return _WORD_RE.findall(text.lower())


def _rng_for(item: str, seed: Optional[str]) -> random.Random:
    """Deterministic RNG bound to (item, seed)."""
    digest = hashlib.sha256(
        ("%s::%s" % (seed or "", item)).encode("utf-8")
    ).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


# ---------------------------------------------------------------------------
# vivid description pools (fixed — determinism source, never reordered)
# ---------------------------------------------------------------------------

_FORMS = (
    "a low vessel humming at the edge of hearing",
    "a lattice of thin bright struts",
    "a folded cloth of dusk-colored air",
    "a slow-turning ringed engine",
    "a cluster of nested shells",
    "a tall quiet monolith veined with light",
    "a braided river of color",
    "a seed-pod about to split",
)

_PALETTES = (
    "ember-orange, ash-gray, deep indigo",
    "sea-glass green, bone white, dusk blue",
    "copper, charcoal, sudden gold",
    "violet, slate, pale silver",
    "crimson, umber, candlelight amber",
    "teal, ink-black, phosphor green",
)

_TEXTURES = (
    "hammered metal under a thin film of water",
    "worn leather softened by a hundred hands",
    "frosted glass breathing faintly",
    "woven reed, tight and springy",
    "polished stone warm from the sun",
    "paper-thin layers lifting in a draft",
)

_SCALES = (
    "palm-sized, heavy for its size",
    "doorway-tall, impossibly light",
    "a room you could walk through",
    "fingertip-small, seen through a lens",
    "horizon-wide, felt more than seen",
)

_LIGHTS = (
    "lit from within, the way a lantern is",
    "caught in low raking evening light",
    "under a cold blue noon glare",
    "half in shadow, the lit half glowing",
    "in the flat gray light before rain",
)

_MOTIONS = (
    "perfectly still, holding its breath",
    "turning one slow degree per heartbeat",
    "trembling faintly, like a held note",
    "drifting on a current you cannot see",
    "pulsing in a rhythm just off your own",
)

_CONTEXTS = (
    "in an empty room with one high window",
    "at the edge of a night market, stalls closing",
    "on a workbench scattered with small tools",
    "in a tide pool at low water",
    "at the treeline where the path gives out",
    "on a kitchen table in the small hours",
)


def _dream_lens_lines(item: str) -> List[str]:
    """Two dream-engine lens lines (deterministic — variate is pure)."""
    out: List[str] = []
    for v in variate(item, kinds=["amplify", "transplant"]):
        out.append("dream-lens [%s]: %s" % (v["kind"], v["text"]))
    return out


def _vivid_description(item: str, rng: random.Random) -> Dict[str, Any]:
    words = [w for w in _words(item) if len(w) > 2]
    anchor = words[0] if words else item.strip()[:24]
    form = rng.choice(_FORMS)
    palette = rng.choice(_PALETTES)
    texture = rng.choice(_TEXTURES)
    scale = rng.choice(_SCALES)
    light = rng.choice(_LIGHTS)
    motion = rng.choice(_MOTIONS)
    context = rng.choice(_CONTEXTS)
    lines = [
        "LEVI imagines '%s' as %s — %s." % (item, form, scale),
        "Its palette runs %s; the surface feels like %s." % (palette, texture),
        "It is %s, and it is %s." % (light, motion),
        "You meet it %s." % context,
        "The load-bearing detail: the %s of it is what your eye keeps "
        "returning to — %s." % (anchor, rng.choice(_TEXTURES)),
    ]
    lines.extend(_dream_lens_lines(item))
    return {
        "subject": item,
        "anchor": anchor,
        "form": form,
        "palette": palette,
        "texture": texture,
        "scale": scale,
        "light": light,
        "motion": motion,
        "context": context,
        "lines": lines,
    }


# ---------------------------------------------------------------------------
# deterministic symbolic ASCII render (a sigil, not pixels)
# ---------------------------------------------------------------------------

_RENDER_W, _RENDER_H = 28, 12


def _blank() -> List[List[str]]:
    return [["."] * _RENDER_W for _ in range(_RENDER_H)]


def _plot(grid: List[List[str]], x: int, y: int, ch: str) -> None:
    if 0 <= y < _RENDER_H and 0 <= x < _RENDER_W:
        grid[y][x] = ch


def _draw_orb(grid: List[List[str]], rng: random.Random) -> None:
    cx, cy = rng.randint(6, 21), rng.randint(3, 8)
    rx, ry = rng.randint(3, 6), rng.randint(2, 4)
    for y in range(_RENDER_H):
        for x in range(_RENDER_W):
            d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
            if d <= 0.35:
                _plot(grid, x, y, "O")
            elif d <= 1.0:
                _plot(grid, x, y, "o")


def _draw_diamond(grid: List[List[str]], rng: random.Random) -> None:
    cx, cy = rng.randint(6, 21), rng.randint(3, 8)
    rx, ry = rng.randint(4, 8), rng.randint(2, 4)
    for y in range(_RENDER_H):
        for x in range(_RENDER_W):
            if abs(x - cx) / rx + abs(y - cy) / ry <= 1.0:
                _plot(grid, x, y, "*")


def _draw_wave(grid: List[List[str]], rng: random.Random) -> None:
    import math

    cy, amp = rng.randint(4, 7), rng.uniform(1.0, 2.5)
    phase = rng.uniform(0, 6.28)
    for x in range(_RENDER_W):
        y = int(round(cy + amp * math.sin(x * 0.45 + phase)))
        _plot(grid, x, y, "~")
        _plot(grid, x, y + 1, "-")


def _draw_box(grid: List[List[str]], rng: random.Random) -> None:
    x0, y0 = rng.randint(1, 8), rng.randint(1, 4)
    w, h = rng.randint(8, 14), rng.randint(4, 6)
    for x in range(x0, x0 + w):
        _plot(grid, x, y0, "#")
        _plot(grid, x, y0 + h, "#")
    for y in range(y0, y0 + h + 1):
        _plot(grid, x0, y, "#")
        _plot(grid, x0 + w, y, "#")


_DRAWERS = (_draw_orb, _draw_diamond, _draw_wave, _draw_box)


def _ascii_render(rng: random.Random) -> str:
    grid = _blank()
    # two shapes, deterministic order of drawers
    drawers = list(rng.sample(_DRAWERS, 2))
    for draw in drawers:
        draw(grid, rng)
    # sparse deterministic sparks
    for _ in range(rng.randint(4, 9)):
        _plot(grid, rng.randrange(_RENDER_W), rng.randrange(_RENDER_H), "+")
    return "\n".join("".join(row) for row in grid)


def imagine_vivid(item: str, seed: Optional[str] = None) -> Dict[str, Any]:
    """Imagine ``item`` vividly. Pure: same (item, seed) -> identical record.

    Returns a render record with ``turn_ref`` (the stable reference the
    thumbs up/down lands on), the structured vivid description, the
    symbolic ASCII render block, keywords for the index, and
    ``render_text`` — the canonical text that gets stored on thumbs-up.
    """
    if not isinstance(item, str) or not item.strip():
        raise ValueError("imagine_vivid: item must be a non-empty string")
    item = item.strip()
    if seed is not None and not isinstance(seed, str):
        raise TypeError("imagine_vivid: seed must be str or None")

    rng = _rng_for(item, seed)
    turn_ref = "imagine-" + hashlib.sha256(
        ("%s::%s" % (seed or "", item)).encode("utf-8")
    ).hexdigest()[:12]
    vivid = _vivid_description(item, rng)
    ascii_render = _ascii_render(rng)

    keywords = sorted(
        {
            w
            for w in _words(item)
            if len(w) > 2
        }
        | {
            w
            for w in _words(
                vivid["form"] + " " + vivid["palette"] + " " + vivid["texture"]
            )
            if len(w) > 2
        }
    )

    record = {
        "turn_ref": turn_ref,
        "item": item,
        "seed": seed,
        "vivid": vivid,
        "ascii_render": ascii_render,
        "keywords": keywords,
    }
    record["render_text"] = render_text_of(record)
    return record


def render_text_of(record: Dict[str, Any]) -> str:
    """Canonical storable text of a render record (what gets compressed)."""
    vivid = record["vivid"]
    parts = [
        "IMAGINATION %s" % record["turn_ref"],
        "ITEM: %s" % record["item"],
        "",
        *vivid["lines"],
        "",
        "--- RENDER ---",
        record["ascii_render"],
    ]
    return "\n".join(parts)


def rate_imagination(
    turn_ref: str,
    signal: str,
    *,
    render: Optional[Dict[str, Any]] = None,
    corpus_dir: Optional[str] = None,
    store: Any = None,
    dimension: str = "",
    note: str = "",
    source: str = "user",
) -> Dict[str, Any]:
    """Rate an imagined turn thumbs up/down and route the outcome.

    The vote always flows through the honest feedback path
    (``new_feedback`` + ``record_feedback``, target kind ``"turn"``,
    ref = the imagine turn ref) into the growth loop — so a
    thumbs-down teaches the reflect loop. ONLY a thumbs-up reaches the
    imagery corpus, via Nanobit's storage face
    (``imagery_corpus.store_upvoted``), linked to the feedback record.

    ``store`` is passed to ``record_feedback`` (a growth store, or None
    for the default). ``corpus_dir`` is required for thumbs-up.
    """
    if signal not in ("up", "down"):
        raise ValueError("rate_imagination: signal must be 'up' or 'down'")
    if not turn_ref or not turn_ref.strip():
        raise ValueError("rate_imagination: turn_ref must be non-empty")

    feedback = new_feedback(
        "turn",
        turn_ref,
        signal,
        operator=IMAGINE_OPERATOR,
        seat="chat",
        dimension=dimension,
        note=note,
        source=source,
    )
    consolidation = record_feedback(feedback, store=store)

    corpus_record_id: Optional[str] = None
    if signal == "up":
        if render is None:
            raise ValueError(
                "rate_imagination: thumbs-up requires the render record "
                "(refusing to store without it)"
            )
        if not corpus_dir:
            raise ValueError(
                "rate_imagination: thumbs-up requires corpus_dir "
                "(refusing to store without it)"
            )
        # Late import: imagery_corpus is Nanobit's storage face; keep this
        # module importable even if the corpus half is mid-edit.
        from levi.dream.imagery_corpus import store_upvoted

        corpus_record_id = store_upvoted(render, feedback.id, corpus_dir)
    # thumbs-down: growth loop already has the learning; the corpus is
    # never touched.

    return {
        "feedback_id": feedback.id,
        "signal": signal,
        "consolidation": consolidation,
        "corpus_record_id": corpus_record_id,
    }
