"""Vine/Digg — the loop-form and front-page modules, revived.

Two organs from the dead-social autopsy, rebuilt as one constrained
package:

**Vine** — the six-second loop. The original form was setup / twist /
payoff inside six hard seconds, with a seamless loop point where the
end feeds the beginning. This module is a *pure constrained-form
generator* for text/audio scripts: it validates loops and renders
shooting scripts. No video encoding — the constraint is the content.

**Digg** — the front page. Digg's mechanics were digg (up) and bury
(down), both reversible, nothing deleted. The bury already lives on
``ShelfStore`` (``core/levi/shelf/shelf.py``); this module wraps it in
the Digg vocabulary and adds the front-page ranking — it never
reimplements or duplicates the shelf's bury.

LAWS
----
1. **Six seconds is a wall.** A loop whose beats total more than 6.0s
   is refused, never truncated.
2. **The loop must close.** Every loop declares its loop point: the
   beat the end returns to, with a matching cue. An open loop is
   refused.
3. **Bury never deletes.** Digg operations delegate to the shelf;
   bury/unbury round-trips preserve the item byte-for-byte.
4. **Buried items never front-page.** The front page excludes buried
   items; it does not erase them.

stdlib-only, local-first, no network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = [
    "LoopError",
    "Beat",
    "Loop",
    "validate_loop",
    "loop_script",
    "digg",
    "bury",
    "unbury",
    "frontpage",
    "SIX_SECONDS",
]

SIX_SECONDS = 6.0


class LoopError(Exception):
    """A loop form was refused."""


@dataclass
class Beat:
    """One Vine beat: a shot of ``seconds`` with a ``cue`` and a line."""

    cue: str          # what the viewer sees/hears, e.g. "doorbell rings"
    line: str = ""    # spoken/text line (may be empty: silent beats exist)
    seconds: float = 2.0

    def __post_init__(self) -> None:
        if not self.cue.strip():
            raise LoopError("every beat needs a cue")
        if not (0 < self.seconds <= SIX_SECONDS):
            raise LoopError(f"beat length must be in (0, 6], got {self.seconds}")


@dataclass
class Loop:
    """A Vine loop: ordered beats, total <= 6.0s, with a declared loop point.

    ``loop_back_to`` is the index of the beat the ending returns to, and
    ``loop_cue`` is the cue that must match that beat's cue — the
    seamless stitch. (The classic: the last frame *is* the first frame.)
    """

    title: str
    beats: List[Beat] = field(default_factory=list)
    loop_back_to: int = 0
    loop_cue: str = ""

    @property
    def total_seconds(self) -> float:
        return round(sum(b.seconds for b in self.beats), 3)


def validate_loop(loop: Loop) -> List[str]:
    """Check a loop against the form's laws. Empty list = a true loop.

    - has 1..6 beats, each well-formed (enforced by Beat)
    - total <= 6.0s (the wall)
    - loop_back_to is a valid beat index
    - loop_cue matches the target beat's cue (the seamless stitch)
    """
    problems: List[str] = []
    if not loop.title.strip():
        problems.append("loop needs a title")
    if not loop.beats:
        problems.append("loop needs at least one beat")
    if len(loop.beats) > 6:
        problems.append("more than 6 beats is a short film, not a Vine")
    if loop.total_seconds > SIX_SECONDS + 1e-9:
        problems.append(
            f"loop runs {loop.total_seconds}s: six seconds is a wall, not a budget"
        )
    if not (0 <= loop.loop_back_to < len(loop.beats)):
        problems.append(f"loop_back_to={loop.loop_back_to} points at no beat")
    elif loop.loop_cue.strip() != loop.beats[loop.loop_back_to].cue.strip():
        problems.append(
            "loop_cue does not match the target beat's cue: the loop does not close"
        )
    return problems


def make_loop(title: str, beats: List[Beat], loop_back_to: int = 0,
              loop_cue: str = "") -> Loop:
    """Build a loop or raise ``LoopError`` naming every violation."""
    loop = Loop(title=title, beats=list(beats),
                loop_back_to=loop_back_to, loop_cue=loop_cue)
    problems = validate_loop(loop)
    if problems:
        raise LoopError("; ".join(problems))
    return loop


def loop_script(loop: Loop) -> str:
    """Render a loop as a timestamped shooting script (text form)."""
    problems = validate_loop(loop)
    if problems:
        raise LoopError("refusing to script an invalid loop: " + "; ".join(problems))
    lines = [f"VINE: {loop.title} ({loop.total_seconds:.1f}s loop)", ""]
    t = 0.0
    for i, b in enumerate(loop.beats):
        end = t + b.seconds
        marker = "  <-- LOOP POINT" if i == loop.loop_back_to else ""
        lines.append(f"[{t:4.1f}-{end:4.1f}s] {b.cue}{marker}")
        if b.line:
            lines.append(f"             \"{b.line}\"")
        t = end
    lines += ["", f"loop closes: '{loop.loop_cue}' == beat {loop.loop_back_to}'s cue"]
    return "\n".join(lines)


# ------------------------------------------------------------------ Digg


def _shelf():
    from levi.shelf.shelf import ShelfStore

    return ShelfStore()


def digg(item_id: str):
    """Digg it: the positive signal. Delegates to the shelf's star."""
    return _shelf().star(item_id)


def undigg(item_id: str):
    return _shelf().unstar(item_id)


def bury(item_id: str):
    """Bury it: the reversible negative signal. The item survives."""
    return _shelf().bury(item_id)


def unbury(item_id: str):
    return _shelf().unbury(item_id)


def frontpage(limit: int = 20) -> List[Dict[str, Any]]:
    """The Digg front page: starred first, buried never, newest wins ties.

    Returns item dicts in rank order. Buried items are excluded from the
    page — they are not deleted from the shelf.
    """
    store = _shelf()
    items = [i for i in store.list(include_buried=False)]
    items.sort(key=lambda i: (not i.starred, -(i.added_at or 0)))
    return [i.to_dict() for i in items[: max(1, int(limit))]]
