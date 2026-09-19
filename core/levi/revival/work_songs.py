"""LEVI's metered coordination: rhythm as a coordination protocol.

Studied from: lost-crafts-20260916 / report.md [Batch 1]
(Work Songs)

The studied mechanism: labor crews kept time to sung verse. The song did
three jobs at once —

* coordination: a shared beat told every hand when to pull, so effort
  landed together instead of scattered;
* structure: call-and-response gave the crew a frame (the leader calls
  the verse, the gang answers the chorus) that could carry instructions
  without anyone stopping work to talk;
* memory: grievances, lore, and the names of the dead lived in the
  verses. The song was the crew's journal.

This module rebuilds that as LEVI's own mechanism. A :class:`BeatGrid`
is the shared clock (beats per minute, bars, beats per bar). A
:class:`WorkSong` is a call-and-response structure over that grid: each
call names a task and the beat offsets on which the crew answers. A
:class:`Gang` schedules work onto the grid, tracks each member's drift
off the beat, and keeps a grievance log — the lore vessel — alongside
the work.

Honest limits: this is a *model* of coordination, not a real-time
system. Beats are logical positions, not wall-clock scheduling; the
"drift" a member accumulates is computed from reported offsets, not
measured. It answers "who is off the beat and by how much," not "move
now." Used honestly, it is a coordination ledger, not a metronome.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


ORIGIN = "levi-revival/work_songs"


# ---------------------------------------------------------------------------
# The beat grid — the shared clock
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BeatGrid:
    """A logical clock: bpm, beats per bar, total bars.

    Positions are beat indices, 0-based: bar * beats_per_bar + beat.
    Time in seconds exists only as an estimate (60/bpm per beat) for
    display — nothing schedules against it.
    """

    bpm: float
    beats_per_bar: int
    bars: int

    def total_beats(self) -> int:
        return self.beats_per_bar * self.bars

    def beat_label(self, beat: int) -> str:
        bar, within = divmod(beat, self.beats_per_bar)
        return f"bar {bar + 1}, beat {within + 1}"

    def seconds_per_beat(self) -> float:
        return 60.0 / self.bpm


# ---------------------------------------------------------------------------
# The work song — call-and-response structure over the grid
# ---------------------------------------------------------------------------


@dataclass
class Verse:
    """One call-and-response verse.

    call: the leader's line (may carry an instruction, e.g. "heave the
    capstan").
    answer_offsets: beat offsets (from the call's beat) on which the crew
    answers with the chorus.
    task: the job the verse organizes, if any.
    """

    call: str
    answer_offsets: List[int]
    task: Optional[str] = None


class WorkSong:
    """A song = an ordered list of verses laid over a BeatGrid."""

    def __init__(self, name: str, grid: BeatGrid) -> None:
        self.name = name
        self.grid = grid
        self.verses: List[Verse] = []

    def add_verse(self, verse: Verse) -> None:
        self.verses.append(verse)

    def plan(self) -> List[Tuple[int, str, str]]:
        """Lay the song onto the grid: (beat, role, text).

        Calls land one verse per bar, starting at beat 0 of each bar;
        answers land at the given offsets. Beats past the grid's end are
        dropped (the song is longer than the shift — an honest truncation,
        reported to the caller).
        """
        events: List[Tuple[int, str, str]] = []
        for i, verse in enumerate(self.verses):
            call_beat = i * self.grid.beats_per_bar
            if call_beat >= self.grid.total_beats():
                break
            events.append((call_beat, "call", verse.call))
            for offset in verse.answer_offsets:
                answer_beat = call_beat + offset
                if 0 <= answer_beat < self.grid.total_beats():
                    events.append((answer_beat, "answer", "chorus"))
        events.sort(key=lambda e: (e[0], 0 if e[1] == "call" else 1))
        return events


# ---------------------------------------------------------------------------
# The gang — who pulls, who drifts, and what gets remembered
# ---------------------------------------------------------------------------


@dataclass
class DriftReading:
    """One reported offset: how early/late a member answered, in beats."""

    member: str
    beat: int
    offset: float  # negative = early, positive = late


class Gang:
    """The crew that works the song.

    Members report when they answered (their own honesty is the load
    bearer). The gang aggregates drift per member, flags chronic
    lateness, and keeps the grievance log — the lore vessel the verses
    carried.
    """

    def __init__(self, name: str, song: WorkSong) -> None:
        self.name = name
        self.song = song
        self.members: List[str] = []
        self._drift: Dict[str, List[float]] = {}
        self.grievances: List[str] = []
        self.chores_done: Dict[str, int] = {}

    def muster(self, member: str) -> None:
        if member not in self.members:
            self.members.append(member)
            self._drift.setdefault(member, [])

    def report_answer(self, member: str, beat: int, offset: float) -> None:
        """Record a member's self-reported offset at a beat."""
        if member not in self.members:
            raise ValueError(f"{member!r} is not mustered in {self.name}")
        self._drift.setdefault(member, []).append(offset)
        self.chores_done[member] = self.chores_done.get(member, 0) + 1

    def mean_drift(self, member: str) -> Optional[float]:
        """Mean beat-offset for a member; None if nothing reported."""
        readings = self._drift.get(member, [])
        if not readings:
            return None
        return sum(readings) / len(readings)

    def off_beat(self, tolerance: float = 0.25) -> List[str]:
        """Members whose mean drift exceeds the tolerance, in beats."""
        return [
            m
            for m in self.members
            if (d := self.mean_drift(m)) is not None and abs(d) > tolerance
        ]

    def sing_grievance(self, line: str) -> None:
        """Add a line to the lore vessel — kept verbatim, never parsed."""
        self.grievances.append(line)

    def roll_call(self) -> List[Tuple[str, Optional[float], int]]:
        """(member, mean_drift, chores_done) for the whole gang."""
        return [
            (m, self.mean_drift(m), self.chores_done.get(m, 0)) for m in self.members
        ]
