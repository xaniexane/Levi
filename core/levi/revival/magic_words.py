"""Magic-word composer: typed verbs summon structured widgets.

Studied from: victims-of-giants-20260916-0017 report.md
[Resurrection shortlist #15]

The studied shape: a chat input that understands typed verbs — type
`gif`, `poll`, `dice`, or `remind` and the line turns into a structured
widget (a poll, a dice roll, a reminder) instead of plain text.

LEVI-native re-expression: a small command registry that maps magic
words to widget builders. The composer scans a message, binds the first
recognized verb, parses its arguments with an honest little argument
grammar, and returns a Widget describing what the interface should
render. Argument parsing is rule-based (split on a delimiter, keyword
flags) — a heuristic, labeled as such, not natural-language
understanding.

Honest limits: no network calls — a `gif` widget carries a local
placeholder catalog of tagged items, never a live image search. A
`remind` widget computes the due instant from a relative offset
("in 20m", "tomorrow 9am"); absolute-date parsing is limited to a
small, documented subset.
"""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


ORIGIN = "levi-revival/magic-words"

_MAGIC_WORD_RE = re.compile(r"^/(\w+)\s*(.*)$", re.DOTALL)


@dataclass
class Widget:
    """A structured widget summoned by a magic word."""

    kind: str  # "gif" | "poll" | "dice" | "remind" | "error"
    title: str
    payload: Dict = field(default_factory=dict)
    source_word: str = ""
    raw_args: str = ""


# --- local gif catalog (placeholder, no network) --------------------------
# Each entry is (label, [tags]); a query picks the best tag overlap.
_GIF_CATALOG = [
    ("applause-loop", ["applause", "clap", "cheer", "congrats"]),
    ("facepalm-classic", ["facepalm", "mistake", "oops"]),
    ("excited-cat", ["cat", "excited", "happy"]),
    ("thinking-owl", ["thinking", "hmm", "ponder"]),
    ("slow-clap", ["slow", "sarcastic", "clap"]),
    ("party-popper", ["party", "celebrate", "yes"]),
    ("shrug-shrug", ["shrug", "idk", "whatever"]),
    ("mind-blown", ["wow", "amazing", "mindblown"]),
]


# --- reminder offset grammar (heuristic, documented subset) ---------------
_OFFSET_RE = re.compile(
    r"(?:in\s+)?(?:(?P<days>\d+)\s*d(?:ays?)?\s*)?"
    r"(?:(?P<hours>\d+)\s*h(?:ours?)?\s*)?"
    r"(?:(?P<minutes>\d+)\s*m(?:in(?:utes?)?)?\s*)?$"
)
_ABS_RE = re.compile(
    r"(?P<which>today|tomorrow)\s*(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<ampm>am|pm)?$"
)


def _now() -> float:
    return time.time()


def _parse_dice(arg: str) -> Tuple[int, int, int]:
    """Parse NdM[+-K]. Heuristic: falls back to 1d6."""
    m = re.fullmatch(
        r"\s*(?P<n>\d{1,3})?[dD](?P<m>\d{1,4})(?P<mod>[+-]\d{1,4})?\s*", arg
    )
    n = int(m.group("n")) if m and m.group("n") else 1
    sides = int(m.group("m")) if m else 6
    mod = int(m.group("mod")) if m and m.group("mod") else 0
    return max(1, min(n, 100)), max(2, min(sides, 1000)), mod


def _parse_remind(
    arg: str, now: Optional[float] = None
) -> Tuple[bool, str, Optional[float]]:
    """Return (ok, message, due_epoch). Heuristic subset grammar."""
    now = now if now is not None else _now()
    parts = [p.strip() for p in arg.split(" @ ", 1)]
    text, when = parts[0], (parts[1] if len(parts) == 2 else "")
    if not text:
        return False, "remind needs something to remind you about", None
    if not when:
        when = "in 1h"
    when = when.strip().lower()
    m = _OFFSET_RE.fullmatch(when)
    if m and any(m.group(k) for k in ("days", "hours", "minutes")):
        delta = (
            int(m.group("days") or 0) * 86400
            + int(m.group("hours") or 0) * 3600
            + int(m.group("minutes") or 0) * 60
        )
        return True, text, now + delta
    m = _ABS_RE.fullmatch(when)
    if m:
        import datetime

        hour = int(m.group("hour")) % 12
        if m.group("ampm") == "pm":
            hour += 12
        minute = int(m.group("minute") or 0)
        day = datetime.datetime.fromtimestamp(now).date()
        if m.group("which") == "tomorrow":
            day = day + datetime.timedelta(days=1)
        due = datetime.datetime.combine(day, datetime.time(hour, minute))
        ts = due.timestamp()
        if ts <= now:
            ts += 86400
        return True, text, ts
    return (
        False,
        f"could not understand when: {when!r} (try 'in 20m' or 'tomorrow 9am')",
        None,
    )


def _pick_gif(query: str) -> Tuple[str, List[str]]:
    words = set(re.findall(r"\w+", query.lower()))
    best: Tuple[str, List[str]] = _GIF_CATALOG[0]
    best_score = 0
    for label, tags in _GIF_CATALOG:
        score = len(words & set(tags))
        if score > best_score:
            best, best_score = (label, tags), score
    return best


def _suggest(word: str) -> List[str]:
    words = list(_HANDLERS)
    scored = sorted(words, key=lambda w: (len(set(w) ^ set(word)), w))
    return scored[:3]


def _gif(args: str, rng: random.Random) -> Widget:
    label, tags = _pick_gif(args)
    return Widget(
        kind="gif",
        title=f"gif: {label}",
        payload={
            "catalog_id": label,
            "matched_tags": tags,
            "note": "local placeholder catalog; no network lookup",
        },
        source_word="gif",
        raw_args=args,
    )


def _poll(args: str, rng: random.Random) -> Widget:
    parts = [p.strip() for p in args.split("|")]
    question = parts[0] if parts[0] else "untitled poll"
    options = [p for p in parts[1:] if p]
    if not options:
        return Widget(
            kind="error",
            title="poll needs options",
            payload={"hint": "use: /poll question | option A | option B"},
            source_word="poll",
            raw_args=args,
        )
    return Widget(
        kind="poll",
        title=question,
        payload={
            "options": options,
            "votes": {opt: 0 for opt in options},
            "open": True,
        },
        source_word="poll",
        raw_args=args,
    )


def _dice(args: str, rng: random.Random) -> Widget:
    n, sides, mod = _parse_dice(args or "1d6")
    rolls = [rng.randint(1, sides) for _ in range(n)]
    total = sum(rolls) + mod
    notation = f"{n}d{sides}" + (f"{mod:+d}" if mod else "")
    return Widget(
        kind="dice",
        title=f"rolled {notation}",
        payload={"rolls": rolls, "modifier": mod, "total": total, "notation": notation},
        source_word="dice",
        raw_args=args,
    )


def _remind(args: str, rng: random.Random) -> Widget:
    ok, text, due = _parse_remind(args)
    if not ok:
        return Widget(
            kind="error",
            title="could not set reminder",
            payload={"message": text},
            source_word="remind",
            raw_args=args,
        )
    return Widget(
        kind="remind",
        title=f"reminder: {text}",
        payload={"text": text, "due_epoch": due, "overdue": due <= _now()},
        source_word="remind",
        raw_args=args,
    )


_HANDLERS = {"gif": _gif, "poll": _poll, "dice": _dice, "remind": _remind}


class MagicWordComposer:
    """Scans messages for magic words and builds widgets from them."""

    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)
        self.history: List[Widget] = []

    @property
    def words(self) -> List[str]:
        return sorted(_HANDLERS)

    def compose(self, message: str) -> Optional[Widget]:
        """Return a Widget if the message starts with a magic word."""
        m = _MAGIC_WORD_RE.match(message.strip())
        if not m:
            return None
        word, args = m.group(1).lower(), m.group(2).strip()
        handler = _HANDLERS.get(word)
        if handler is None:
            widget = Widget(
                kind="error",
                title=f"unknown magic word: /{word}",
                payload={"did_you_mean": _suggest(word)},
                source_word=word,
                raw_args=args,
            )
        else:
            widget = handler(args, self._rng)
        self.history.append(widget)
        return widget

    def is_magic(self, message: str) -> bool:
        return bool(_MAGIC_WORD_RE.match(message.strip()))
