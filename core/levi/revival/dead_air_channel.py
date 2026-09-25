"""Dead-air broadcast channel: data rides the empty hours.

Studied from: dead-networks-20260916/report.md [Keyfax]

The studied shape: overnight TV dead airtime — hours when a broadcast
channel carries nothing — used as a free data channel. Content is
carved into addressed frames, cycled on a repeating carousel, and any
receiver that tunes in during the dead window can reassemble the
payload from the frames it catches.

LEVI-native re-expression: a scheduler that packs payloads into
checksummed frames and lays them across registered dead-air windows
on a repeating carousel, prioritized so urgent payloads appear early
and often. A receiver simulator listens for a stretch of the window
and reports what it could reassemble. No real broadcast hardware here
— this is the *scheduling and framing discipline*, honest about the
fact that receivers only see the windows they actually listen to.

Honest limits: framing is toy checksumming (CRC-ish), not a broadcast
modem; timing is minutes on a clock, not RF; a listener that misses a
frame gets a partial payload, not an error-corrected stream.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


ORIGIN = "levi-revival/dead-air-channel"


def _checksum(data: bytes) -> int:
    """Tiny additive checksum; catches transcription typos, not attacks."""
    return sum(data) & 0xFFFF


@dataclass
class Frame:
    """One addressed chunk of a payload on the carousel."""

    channel: str
    payload_id: str
    seq: int
    total: int
    data: bytes
    priority: int = 0

    def encode(self) -> bytes:
        body = b"|".join(
            [
                self.channel.encode(),
                self.payload_id.encode(),
                str(self.seq).encode(),
                str(self.total).encode(),
                str(self.priority).encode(),
                self.data,
            ]
        )
        return body + b"#" + _checksum(body).to_bytes(2, "big")

    @staticmethod
    def decode(raw: bytes) -> "Frame":
        body, mark = raw.rsplit(b"#", 1)
        if _checksum(body) != int.from_bytes(mark, "big"):
            raise ValueError("frame checksum mismatch")
        channel, pid, seq, total, prio, data = body.split(b"|", 5)
        return Frame(
            channel=channel.decode(),
            payload_id=pid.decode(),
            seq=int(seq),
            total=int(total),
            data=data,
            priority=int(prio),
        )


@dataclass
class DeadAirWindow:
    """A dead-airtime window on one channel: start/end as minutes past midnight."""

    channel: str
    start_min: int
    end_min: int
    frames_per_minute: int = 60

    def __post_init__(self) -> None:
        if not (0 <= self.start_min < self.end_min <= 24 * 60):
            raise ValueError("window must sit inside one day, start before end")

    @property
    def capacity(self) -> int:
        return (self.end_min - self.start_min) * self.frames_per_minute


@dataclass
class Payload:
    payload_id: str
    data: bytes
    priority: int = 0
    frame_size: int = 128


class DeadAirScheduler:
    """Packs payloads into frames and carousels them across dead-air windows."""

    def __init__(self) -> None:
        self.windows: List[DeadAirWindow] = []
        self.payloads: List[Payload] = []

    def add_window(self, window: DeadAirWindow) -> None:
        self.windows.append(window)

    def submit(self, payload: Payload) -> List[Frame]:
        self.payloads.append(payload)
        return self._frames_for(payload)

    def _frames_for(self, payload: Payload) -> List[Frame]:
        chunks = [
            payload.data[i : i + payload.frame_size]
            for i in range(0, max(len(payload.data), 1), payload.frame_size)
        ]
        return [
            Frame(
                channel="",
                payload_id=payload.payload_id,
                seq=seq,
                total=len(chunks),
                data=chunk,
                priority=payload.priority,
            )
            for seq, chunk in enumerate(chunks)
        ]

    def carousel(self) -> List[Frame]:
        """All frames, ordered: higher priority first, then payload id, then seq.

        This is the repeat order — a receiver catching one full cycle of
        the carousel has every payload.
        """
        frames: List[Frame] = []
        for payload in self.payloads:
            frames.extend(self._frames_for(payload))
        frames.sort(key=lambda f: (-f.priority, f.payload_id, f.seq))
        return frames

    def plan(self) -> Dict[str, List[Frame]]:
        """Assign carousel frames to windows, one full cycle per window channel."""
        frames = self.carousel()
        layout: Dict[str, List[Frame]] = {}
        for window in self.windows:
            assigned = [f for f in frames[: window.capacity]]
            for f in assigned:
                f.channel = window.channel
            layout.setdefault(window.channel, []).extend(assigned)
        return layout

    def listen(
        self, channel: str, from_min: int, to_min: int
    ) -> Tuple[Dict[str, bytes], Dict[str, int]]:
        """Simulate a receiver on one channel for a minute range.

        Returns (reassembled payloads, missing frame counts). Partial
        payloads are simply absent — honesty over optimism.
        """
        frames = self.carousel()
        collected: Dict[str, List[Frame]] = {}
        for window in self.windows:
            if window.channel != channel:
                continue
            fpm = window.frames_per_minute
            for i, frame in enumerate(frames[: window.capacity]):
                minute = window.start_min + i // fpm
                if from_min <= minute < to_min:
                    frame.channel = channel
                    collected.setdefault(frame.payload_id, []).append(frame)
        assembled: Dict[str, bytes] = {}
        missing: Dict[str, int] = {}
        for payload in self.payloads:
            got = {f.seq: f for f in collected.get(payload.payload_id, [])}
            expected = self._frame_count(payload)
            missing[payload.payload_id] = expected - len(got)
            if len(got) == expected and expected:
                assembled[payload.payload_id] = b"".join(
                    got[s].data for s in sorted(got)
                )
        return assembled, missing

    def _frame_count(self, payload: Payload) -> int:
        n = max(len(payload.data), 1)
        return (n + payload.frame_size - 1) // payload.frame_size

    def occupancy(self) -> Dict[str, float]:
        """Fraction of each window's capacity the carousel fills."""
        frames = self.carousel()
        report: Dict[str, float] = {}
        for window in self.windows:
            used = min(len(frames), window.capacity)
            report[window.channel] = used / window.capacity if window.capacity else 0.0
        return report
