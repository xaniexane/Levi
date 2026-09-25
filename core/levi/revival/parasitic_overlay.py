"""Parasitic data overlay: run packets through someone else's idle channels.

Studied from: dead-networks-20260916/report.md [CDPD]

The studied shape: no new spectrum was bought. The system watched a
pool of voice channels, snatched the ones sitting idle, and ran data
packets through them; the moment a voice call needed a channel back,
the data got out of the way. Data is the guest, voice is the landlord.

LEVI-native re-expression: a discrete-event simulation of that
discipline. A channel pool carries a supplied voice-occupancy trace;
an overlay sniffs for channels idle at least a hold threshold, feeds
queued packets through them FIFO, and yields instantly on preemption —
an interrupted packet goes back to the head of the queue. Stats report
goodput, preemptions, and how much idle capacity the overlay actually
harvested.

Honest limits: this models the *scheduling discipline*, not radio —
occupancy is a supplied trace, not measured spectrum; there is no
modulation, no error model, and "yielding" is instant by construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


ORIGIN = "levi-revival/parasitic-overlay"


@dataclass
class Packet:
    packet_id: str
    size: int  # abstract units; one idle channel moves slot_capacity per tick


class ParasiticOverlay:
    """Data rides idle voice channels; voice always wins."""

    def __init__(
        self,
        channel_count: int,
        slot_capacity: int = 4,
        hold_ticks: int = 2,
    ) -> None:
        if channel_count <= 0 or slot_capacity <= 0 or hold_ticks <= 0:
            raise ValueError("counts, capacity and hold must be positive")
        self.channel_count = channel_count
        self.slot_capacity = slot_capacity
        self.hold_ticks = hold_ticks
        self.queue: List[Packet] = []
        self._idle_streak = [0] * channel_count
        # channel index -> [Packet, remaining units]
        self._in_flight: Dict[int, list] = {}
        self.ticks = 0
        self.packets_sent = 0
        self.packets_preempted = 0
        self.data_units_sent = 0
        self.idle_ticks_seen = 0
        self.idle_ticks_used = 0

    def enqueue(self, packet: Packet) -> None:
        if packet.size <= 0:
            raise ValueError("packet size must be positive")
        self.queue.append(packet)

    def tick(self, voice_busy: List[bool]) -> None:
        """Advance one tick. voice_busy[i] = landlord wants channel i."""
        if len(voice_busy) != self.channel_count:
            raise ValueError("voice trace must cover every channel")
        self.ticks += 1
        for i, busy in enumerate(voice_busy):
            if busy:
                self._idle_streak[i] = 0
                if i in self._in_flight:
                    pkt, _remaining = self._in_flight.pop(i)
                    self.queue.insert(0, pkt)  # yield: back to head of queue
                    self.packets_preempted += 1
                continue
            self.idle_ticks_seen += 1
            self._idle_streak[i] += 1
            if self._idle_streak[i] < self.hold_ticks:
                continue  # not idle long enough to trust
            self.idle_ticks_used += 1
            if i not in self._in_flight and self.queue:
                pkt = self.queue.pop(0)
                self._in_flight[i] = [pkt, pkt.size]
            if i in self._in_flight:
                pkt, remaining = self._in_flight[i]
                sent = min(self.slot_capacity, remaining)
                remaining -= sent
                self.data_units_sent += sent
                if remaining <= 0:
                    del self._in_flight[i]
                    self.packets_sent += 1
                else:
                    self._in_flight[i][1] = remaining

    def pending(self) -> int:
        return len(self.queue) + len(self._in_flight)

    def report(self) -> Dict[str, float]:
        harvest = (
            self.idle_ticks_used / self.idle_ticks_seen if self.idle_ticks_seen else 0.0
        )
        return {
            "ticks": float(self.ticks),
            "packets_sent": float(self.packets_sent),
            "packets_preempted": float(self.packets_preempted),
            "data_units_sent": float(self.data_units_sent),
            "idle_harvest_ratio": harvest,
        }
