"""beats — façade beats: interaction choreography.

Studied from: revival-50-more-20260916-0009/report-part2.md (Section 37).

Load-bearing idea: an interaction is choreographed as narrative beats with
preconditions and effects played over a tension arc; a drama manager
sequences the beats; free-text input is mapped to a small set of discourse
acts that drive the choreography.

LEVI's take: ``Beat`` carries a name, the discourse act it waits for, the
tension band it wants, and the effects it applies (a line to speak, a
tension nudge). ``DramaManager`` holds the arc — an ordered beat list —
and ``step(user_text)`` maps the text to one of LEVI's twelve discourse
acts, finds the next beat whose preconditions hold, plays it, and reports
the line plus the new tension. Nothing real-time: the "drama" is a local
model of turn-taking rhythm, so LEVI can pace an interaction instead of
just answering it.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple


ORIGIN = "levi-revival/beats"


# ---------------------------------------------------------------------------
# Discourse acts — LEVI's own small set (~12)
# ---------------------------------------------------------------------------


class DiscourseAct(str, Enum):
    GREET = "greet"  # hello, hey, good morning
    SMALLTALK = "smalltalk"  # how are you, nice weather
    ASK = "ask"  # a direct question
    OFFER = "offer"  # proposing help or a trade
    PRAISE = "praise"  # compliment, thanks
    JOKE = "joke"  # humor, play
    CHALLENGE = "challenge"  # pushback, disagreement with teeth
    DEFLECT = "deflect"  # dodge, change subject, "never mind"
    AGREE = "agree"  # yes, sounds good
    DISAGREE = "disagree"  # no, not quite
    DECLARE = "declare"  # stating a decision or fact with weight
    FAREWELL = "farewell"  # goodbye, see you later


_ACT_PATTERNS: List[Tuple[DiscourseAct, List[str]]] = [
    (
        DiscourseAct.GREET,
        [
            r"\bhello\b",
            r"\bhey\b",
            r"\bhi\b",
            r"good (morning|evening|afternoon)",
            r"\byo\b",
        ],
    ),
    (
        DiscourseAct.FAREWELL,
        [r"\bbye\b", r"goodbye", r"see you", r"\bgtg\b", r"talk later"],
    ),
    (
        DiscourseAct.SMALLTALK,
        [r"how are you", r"nice weather", r"what'?s up", r"how'?s it going"],
    ),
    (
        DiscourseAct.ASK,
        [r"\?$", r"^(what|why|how|when|where|who|can you|could you|do you)"],
    ),
    (
        DiscourseAct.OFFER,
        [r"\bi can\b", r"want me to", r"shall i", r"let me help", r"\boffer\b"],
    ),
    (
        DiscourseAct.PRAISE,
        [
            r"\bthank",
            r"\bgreat\b",
            r"\bawesome\b",
            r"\bnice\b",
            r"well done",
            r"\blove\b",
        ],
    ),
    (DiscourseAct.JOKE, [r"\bhaha\b", r"\blol\b", r"\bjoke\b", r"\bfunny\b"]),
    (
        DiscourseAct.CHALLENGE,
        [r"prove it", r"are you sure", r"that'?s wrong", r"\bbut\b.*\?", r"challenge"],
    ),
    (
        DiscourseAct.DEFLECT,
        [
            r"never mind",
            r"forget it",
            r"change the subject",
            r"anyway,?",
            r"don'?t worry about",
        ],
    ),
    (
        DiscourseAct.AGREE,
        [r"\byes\b", r"\byeah\b", r"\byep\b", r"sounds good", r"\bagree\b", r"exactly"],
    ),
    (
        DiscourseAct.DISAGREE,
        [r"\bno\b", r"\bnope\b", r"not really", r"\bdisagree\b", r"i don'?t think so"],
    ),
    (
        DiscourseAct.DECLARE,
        [r"^i (will|won'?t|am|have decided)", r"here'?s the thing", r"the fact is"],
    ),
]


def map_act(text: str) -> DiscourseAct:
    """Map free text onto LEVI's twelve discourse acts. First match wins."""
    lowered = text.strip().lower()
    for act, patterns in _ACT_PATTERNS:
        for pat in patterns:
            if re.search(pat, lowered):
                return act
    return DiscourseAct.ASK if "?" in lowered else DiscourseAct.DECLARE


# ---------------------------------------------------------------------------
# Beats and the drama manager
# ---------------------------------------------------------------------------


@dataclass
class Beat:
    """One choreographed moment.

    ``awaits``: the discourse act this beat is waiting for (None = any).
    ``tension_band``: (lo, hi) the tension must sit inside for the beat
    to fire. ``tension_delta``: how playing the beat moves the arc.
    ``line``: what the host says when the beat plays.
    """

    name: str
    line: str
    awaits: Optional[DiscourseAct] = None
    tension_band: Tuple[float, float] = (0.0, 1.0)
    tension_delta: float = 0.0
    once: bool = True


@dataclass
class BeatReport:
    beat_name: str
    act: DiscourseAct
    line: str
    tension: float
    arc_done: bool


class DramaManager:
    """Sequences beats over a tension arc, driven by discourse acts."""

    def __init__(self, beats: List[Beat], tension: float = 0.0) -> None:
        self.beats = list(beats)
        self.tension = tension
        self._played: List[str] = []
        self.transcript: List[Tuple[str, str]] = []  # (speaker, text)

    def step(self, user_text: str, speaker: str = "guest") -> BeatReport:
        """Map the text to a discourse act, play the next eligible beat."""
        act = map_act(user_text)
        self.transcript.append((speaker, user_text))
        beat = self._next_beat(act)
        if beat is None:
            line = self._improvise(act)
            return BeatReport(
                beat_name="(improvise)",
                act=act,
                line=line,
                tension=self.tension,
                arc_done=self._arc_done(),
            )
        self.tension = min(1.0, max(0.0, self.tension + beat.tension_delta))
        if beat.once:
            self._played.append(beat.name)
        self.transcript.append(("host", beat.line))
        return BeatReport(
            beat_name=beat.name,
            act=act,
            line=beat.line,
            tension=self.tension,
            arc_done=self._arc_done(),
        )

    def _next_beat(self, act: DiscourseAct) -> Optional[Beat]:
        for beat in self.beats:
            if beat.once and beat.name in self._played:
                continue
            if beat.awaits is not None and beat.awaits is not act:
                continue
            lo, hi = beat.tension_band
            if not (lo <= self.tension <= hi):
                continue
            return beat
        return None

    def _arc_done(self) -> bool:
        return all(b.name in self._played for b in self.beats if b.once)

    def _improvise(self, act: DiscourseAct) -> str:
        fillers = {
            DiscourseAct.GREET: "Hey. Good to see you — what are we getting into?",
            DiscourseAct.ASK: "Good question. Say more about what you need.",
            DiscourseAct.FAREWELL: "Later. The door's always open.",
        }
        return fillers.get(act, "Mm. Noted — keep going.")

    @property
    def played(self) -> List[str]:
        return list(self._played)


def three_act_arc() -> List[Beat]:
    """A small worked arc: warm-up, rising tension, release."""
    return [
        Beat(
            name="welcome",
            line="Welcome in. Make yourself at home.",
            awaits=DiscourseAct.GREET,
            tension_band=(0.0, 0.3),
            tension_delta=0.1,
        ),
        Beat(
            name="probe",
            line="Alright, let's get specific — what's the real ask?",
            awaits=DiscourseAct.ASK,
            tension_band=(0.0, 0.6),
            tension_delta=0.25,
        ),
        Beat(
            name="crucible",
            line="That one's tricky. Defend it — why this way?",
            awaits=DiscourseAct.DECLARE,
            tension_band=(0.3, 1.0),
            tension_delta=0.2,
        ),
        Beat(
            name="release",
            line="Good. That's settled — well held.",
            awaits=DiscourseAct.AGREE,
            tension_band=(0.3, 1.0),
            tension_delta=-0.5,
        ),
        Beat(
            name="sendoff",
            line="Go build it. You know where to find me.",
            awaits=DiscourseAct.FAREWELL,
            tension_band=(0.0, 1.0),
            tension_delta=-0.2,
        ),
    ]
