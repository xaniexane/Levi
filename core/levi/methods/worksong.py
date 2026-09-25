"""Work songs: rhythm as coordination protocol and memory vessel.

Origin: sea shanties in call-and-response form synchronized collective
effort — in the halyard shanty "Blow the Man Down" the crew rested during
the leader's call and pulled only on the stressed words of the chorus, so
twenty to thirty verses could pace a long haul. The shanty was strictly
bound to the work context (never sung ashore, never off-duty), keeping the
knowledge situated in the labor itself.

What it is in LEVI: RhythmChunk encodes a procedure as metered verse.
Every line scans to a fixed beat count (one beat per word), lines group
into chunks with a fixed total beat count, and recall walks the chunks in
meter. The tempo marks the work phase: "call" chunks are the leader's
rest, "response" chunks are the crew's pull. ``decode`` refuses any verse
whose lines don't scan — malformed meter raises instead of guessing.

Honesty label: USEFUL PATTERN — metered chunking is a real mnemonic
technique; the call/rest vs response/pull phase mapping is adapted from
the shanty mechanism, not historical law.

Deny-closed inputs: empty step lists, steps that don't scan to the line
meter, step counts that don't fill whole chunks, chunks with the wrong
beat total, and verses with missing or mis-ordered phase markers are all
rejected with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["VerseLine", "VerseChunk", "Verse", "RhythmChunk", "CALL", "RESPONSE"]

CALL = "call"  # the leader's verse: the crew rests
RESPONSE = "response"  # the chorus: the crew pulls on the stressed words


def _require_steps(steps: object) -> list[str]:
    if not isinstance(steps, (list, tuple)) or not steps:
        raise ValueError("steps must be a non-empty list of strings")
    clean: list[str] = []
    for step in steps:
        if not isinstance(step, str) or not step.strip():
            raise ValueError("every step must be a non-empty string")
        clean.append(step.strip())
    return clean


@dataclass
class VerseLine:
    """One metered line: text plus its beat count (one beat per word)."""

    text: str
    beats: int


@dataclass
class VerseChunk:
    """A chunk of lines sharing one work phase: call (rest) or response (pull)."""

    lines: tuple[VerseLine, ...]
    phase: str


@dataclass
class Verse:
    """An encoded procedure: metered chunks, walkable in order."""

    chunks: tuple[VerseChunk, ...]
    beats_per_line: int
    lines_per_chunk: int


class RhythmChunk:
    """Encode procedures as metered verse; recall walks the meter."""

    def __init__(self, beats_per_line: int = 8, lines_per_chunk: int = 4):
        if not isinstance(beats_per_line, int) or beats_per_line < 1:
            raise ValueError("beats_per_line must be a positive integer")
        if not isinstance(lines_per_chunk, int) or lines_per_chunk < 1:
            raise ValueError("lines_per_chunk must be a positive integer")
        self.beats_per_line = beats_per_line
        self.lines_per_chunk = lines_per_chunk

    @property
    def beats_per_chunk(self) -> int:
        """The fixed beat total every chunk must carry."""
        return self.beats_per_line * self.lines_per_chunk

    def _scan(self, step: str) -> VerseLine:
        words = step.split()
        if len(words) != self.beats_per_line:
            raise ValueError(
                f"malformed meter: {step!r} scans to {len(words)} beats, "
                f"line meter requires {self.beats_per_line}"
            )
        return VerseLine(text=step, beats=len(words))

    # -- encoding ----------------------------------------------------------
    def encode(self, steps: list[str]) -> Verse:
        """Turn a step list into metered verse. Steps must fill whole chunks."""
        clean = _require_steps(steps)
        if len(clean) % self.lines_per_chunk != 0:
            raise ValueError(
                f"{len(clean)} steps do not fill whole chunks of "
                f"{self.lines_per_chunk} lines"
            )
        lines = [self._scan(step) for step in clean]
        chunks: list[VerseChunk] = []
        for i in range(0, len(lines), self.lines_per_chunk):
            phase = CALL if (i // self.lines_per_chunk) % 2 == 0 else RESPONSE
            chunks.append(
                VerseChunk(
                    lines=tuple(lines[i : i + self.lines_per_chunk]), phase=phase
                )
            )
        return Verse(
            chunks=tuple(chunks),
            beats_per_line=self.beats_per_line,
            lines_per_chunk=self.lines_per_chunk,
        )

    # -- recall ------------------------------------------------------------
    def _validate(self, verse: Verse) -> None:
        if not isinstance(verse, Verse) or not verse.chunks:
            raise ValueError("verse must hold at least one chunk")
        if verse.beats_per_line < 1 or verse.lines_per_chunk < 1:
            raise ValueError("verse carries an invalid meter")
        for n, chunk in enumerate(verse.chunks):
            expected_phase = CALL if n % 2 == 0 else RESPONSE
            if chunk.phase != expected_phase:
                raise ValueError(
                    f"malformed meter: chunk {n} has phase {chunk.phase!r}, "
                    f"expected {expected_phase!r}"
                )
            if len(chunk.lines) != verse.lines_per_chunk:
                raise ValueError(
                    f"malformed meter: chunk {n} holds {len(chunk.lines)} lines, "
                    f"expected {verse.lines_per_chunk}"
                )
            total = 0
            for line in chunk.lines:
                if not line.text or not line.text.strip():
                    raise ValueError(f"malformed meter: empty line in chunk {n}")
                if line.beats != len(line.text.split()):
                    raise ValueError(
                        f"malformed meter: line {line.text!r} claims {line.beats} "
                        "beats but scans otherwise"
                    )
                if line.beats != verse.beats_per_line:
                    raise ValueError(
                        f"malformed meter: line {line.text!r} scans to "
                        f"{line.beats} beats, verse meter is "
                        f"{verse.beats_per_line}"
                    )
                total += line.beats
            if total != verse.beats_per_line * verse.lines_per_chunk:
                raise ValueError(
                    f"malformed meter: chunk {n} totals {total} beats, "
                    f"chunk meter requires "
                    f"{verse.beats_per_line * verse.lines_per_chunk}"
                )

    def decode(self, verse: Verse) -> list[str]:
        """Walk the meter back to the original steps, exactly."""
        self._validate(verse)
        return [line.text for chunk in verse.chunks for line in chunk.lines]

    def recall(self, verse: Verse) -> list[tuple[str, str, str]]:
        """Recall the verse in meter: (phase, work action, line text) per line."""
        self._validate(verse)
        out: list[tuple[str, str, str]] = []
        for chunk in verse.chunks:
            action = "rest" if chunk.phase == CALL else "pull"
            for line in chunk.lines:
                out.append((chunk.phase, action, line.text))
        return out

    def tempo(self, verse: Verse) -> list[str]:
        """The work phase of each chunk: call (rest) alternating response (pull)."""
        self._validate(verse)
        return [chunk.phase for chunk in verse.chunks]
