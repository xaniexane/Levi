"""Right-button stroke commands and rocker gestures: a full command vocabulary with no visible chrome.

Studied from: desktop-casualties-20260916/report.md [1. Opera]

The studied shape: pressing the right mouse button and drawing a
stroke (up/down/left/right, possibly chained) fires a command —
up for a new tab, down to close a tab, left/right for back/forward.
Rocker gestures fire commands from chorded left/right clicks. The
whole command set lives in hand movement, not in buttons or menus.

LEVI-native re-expression: a stroke vocabulary. A **StrokeRecorder**
turns a raw pointer trail into a quantized compass-direction string
(8 directions, segment-compressed). A **GestureVocabulary** maps
direction strings (and rocker chords) to command names, ships with a
sensible default set, and stays open to user-defined bindings.

Operations:

* ``quantize(trail)`` — compress a ``[(x, y), ...]`` trail into a
  direction string such as ``"UR"`` (up then right)
* ``GestureVocabulary()`` — default bindings, ``bind``/``unbind``
  custom strokes, ``match(stroke)`` → command or ``None``
* ``rocker(chord)`` — resolve rocker chords (``"L→R"`` hold-left-tap-right, etc.)
* ``confusable(stroke)`` — list bound strokes one edit away (heuristic
  guard against misfires)

Honest limits: direction quantization is a heuristic — shaky or very
short trails can quantize ambiguously, and ``match`` is exact-match
only on the quantized string. Commands are names to be wired by the
host app; this module never moves the mouse or touches tabs itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import atan2, hypot
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/mouse-gestures"

# 8 compass buckets, clockwise from north.
_COMPASS = ["U", "UR", "R", "DR", "D", "DL", "L", "UL"]

# Default vocabulary: the studied shape's core commands.
DEFAULT_BINDINGS: Dict[str, str] = {
    "U": "new-tab",
    "D": "close-tab",
    "L": "back",
    "R": "forward",
    "UR": "maximize-window",
    "DR": "minimize-window",
    "UL": "restore-window",
    "DL": "duplicate-tab",
    "UD": "reload-page",
    "DU": "reload-page",
    "LR": "undo-close-tab",
    "RL": "undo-close-tab",
    "DUD": "open-history",
    "URD": "open-bookmarks",
}

# Rocker chords: (held_button, tapped_button) → command.
ROCKER_BINDINGS: Dict[Tuple[str, str], str] = {
    ("L", "R"): "back",
    ("R", "L"): "forward",
    ("M", "L"): "close-tab",
    ("M", "R"): "new-tab",
}


def _bucket(dx: float, dy: float) -> Optional[str]:
    """Bucket one delta into a compass direction; screen y grows downward."""
    if hypot(dx, dy) < 8.0:  # dead zone for jitter
        return None
    # Screen coordinates: y down. Map atan2 to "clockwise from north".
    angle = atan2(dx, -dy)  # north = 0, east = +pi/2
    idx = int(round(angle / (3.141592653589793 / 4))) % 8
    return _COMPASS[idx]


def quantize(trail: List[Tuple[float, float]]) -> str:
    """Compress a pointer trail into a direction string like ``"UR"``.

    Consecutive identical buckets collapse; sub-8px jitter segments are
    dropped. Returns ``""`` for trails with no decisive motion.
    """
    if len(trail) < 2:
        return ""
    out: List[str] = []
    for (x0, y0), (x1, y1) in zip(trail, trail[1:], strict=False):
        b = _bucket(x1 - x0, y1 - y0)
        if b is not None and (not out or out[-1] != b):
            out.append(b)
    return "".join(out)


@dataclass
class GestureVocabulary:
    """Maps quantized strokes and rocker chords to command names."""

    bindings: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_BINDINGS))
    rocker_bindings: Dict[Tuple[str, str], str] = field(
        default_factory=lambda: dict(ROCKER_BINDINGS)
    )

    def bind(self, stroke: str, command: str) -> None:
        self.bindings[stroke] = command

    def unbind(self, stroke: str) -> Optional[str]:
        return self.bindings.pop(stroke, None)

    def match(self, stroke: str) -> Optional[str]:
        return self.bindings.get(stroke)

    def recognize(self, trail: List[Tuple[float, float]]) -> Optional[str]:
        """quantize + match in one step."""
        return self.match(quantize(trail))

    def rocker(self, held: str, tapped: str) -> Optional[str]:
        return self.rocker_bindings.get((held, tapped))

    def confusable(self, stroke: str, max_dist: int = 1) -> List[str]:
        """Bound strokes within ``max_dist`` direction-edits of ``stroke``.

        Heuristic aid for avoiding misfire-prone custom bindings.
        """

        def dist(a: str, b: str) -> int:
            # Levenshtein over 2-char direction tokens.
            ta = [a[i : i + 2] for i in range(0, len(a), 2)]
            tb = [b[i : i + 2] for i in range(0, len(b), 2)]
            prev = list(range(len(tb) + 1))
            for x in ta:
                cur = [prev[0] + 1]
                for j, y in enumerate(tb):
                    cur.append(min(prev[j + 1] + 1, cur[j] + 1, prev[j] + (x != y)))
                prev = cur
            return prev[-1]

        return [s for s in self.bindings if s != stroke and dist(s, stroke) <= max_dist]
