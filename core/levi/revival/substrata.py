"""LEVI's substrata: layered reactive control with no central planner.

Studied from: catalog (§18) and ai-si (§1.12) — merged (functional
description only; no historical claims).

The lesson, reborn as LEVI's own: intelligence from the bottom up. The
system is a stack of *competence layers*, each an augmented finite-state
machine that talks straight to sensors and motors. There is no central
control and no shared memory — layers talk only through wires. A higher
layer *suppresses* a lower layer's output wire (its command wins) or
*inhibits* a lower layer's input wire. Every input is a single-item
buffer: a fresh reading overwrites the old one, and reading consumes it,
so stale inputs are impossible *by construction*. You build and test one
layer at a time, bottom-up, and each new layer subsumes the last.

Honesty: LOAD-BEARING, with one stated limit. The "no shared memory"
rule is enforced by design here — layers exchange only ``Command`` and
``Reading`` values through wires; nothing holds a reference to another
layer's internals. The demo world is a tiny grid, not a real robot.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

ORIGIN = "levi-revival/substrata"


# ---------------------------------------------------------------------------
# The only things allowed on a wire
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Reading:
    """A single sensor reading placed into a layer's input buffer."""

    sensor: str
    value: float


@dataclass(frozen=True)
class Command:
    """A motor command a layer wants to issue."""

    motor: str
    action: str
    strength: float = 1.0

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"{self.motor}:{self.action}"


# ---------------------------------------------------------------------------
# Augmented finite-state machines — the competence layers
# ---------------------------------------------------------------------------


class Layer:
    """One competence layer: an AFSM with a single-item input buffer and
    its own private state. Override ``react``."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.state: str = "idle"
        self._inbox: Optional[Reading] = None  # single-item buffer
        self.suppressed_for: int = 0  # suppression countdown, set by wires

    # -- the single-item input buffer --------------------------------------
    def sense(self, reading: Reading) -> None:
        """A fresh reading overwrites whatever was there — stale data
        cannot survive a new sense."""
        self._inbox = reading

    def take(self) -> Optional[Reading]:
        """Consume the buffered reading; the buffer is empty afterwards."""
        reading, self._inbox = self._inbox, None
        return reading

    # -- the machine ---------------------------------------------------------
    def react(self) -> Optional[Command]:
        """One AFSM tick. Return a motor command or None."""
        raise NotImplementedError

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Layer({self.name!r}, state={self.state!r})"


# ---------------------------------------------------------------------------
# The subsumption stack — layers arbitrated by wires, no central control
# ---------------------------------------------------------------------------


@dataclass
class _Wire:
    kind: str  # "suppress" (output) or "inhibit" (input)
    higher: str
    lower: str
    ticks: int


class Substrata:
    """The stack. Layers are listed bottom-up; higher layers may suppress
    or inhibit lower ones through wires. Arbitration is the wires — there
    is no arbiter module."""

    def __init__(self) -> None:
        self.layers: List[Layer] = []  # bottom-up
        self._wires: List[_Wire] = []
        self.trace: List[str] = []  # who issued what, for tests

    def add_layer(self, layer: Layer) -> "Substrata":
        self.layers.append(layer)
        return self

    def suppress(self, higher: str, lower: str, ticks: int = 2) -> "Substrata":
        """When `higher` issues a command, `lower`'s output is replaced for
        `ticks` ticks."""
        self._wires.append(_Wire("suppress", higher, lower, ticks))
        return self

    def inhibit(self, higher: str, lower: str, ticks: int = 2) -> "Substrata":
        """When `higher` issues a command, `lower`'s *input* is gated for
        `ticks` ticks (it senses nothing)."""
        self._wires.append(_Wire("inhibit", higher, lower, ticks))
        return self

    def _by_name(self, name: str) -> Layer:
        for layer in self.layers:
            if layer.name == name:
                return layer
        raise KeyError(f"substrata: no layer {name!r}")  # pragma: no cover

    def tick(self) -> Optional[Command]:
        """One system tick: every layer reacts top-down, then suppression
        wires decide whose output reaches the motors. Returns the issued
        command (or None)."""
        # 1. inhibition: gated layers have their input wire cut — whatever
        #    they sensed is discarded unread
        gated = set()
        for wire in self._wires:
            if wire.kind == "inhibit" and self._by_name(wire.higher).suppressed_for > 0:
                gated.add(wire.lower)

        # 2. every layer reacts (top-down so higher commands are known first);
        #    suppression silences *outputs*, never inputs
        issued: Dict[str, Command] = {}
        for layer in reversed(self.layers):
            if layer.name in gated:
                layer.take()
                continue
            cmd = layer.react()
            if cmd is not None:
                issued[layer.name] = cmd
                self.trace.append(f"{layer.name} -> {cmd}")

        # 3. suppression wires: a commanding higher layer silences the lower
        #    layer's output — immediately, and for `ticks` afterwards
        commanding = set(issued)
        silenced = set()
        for wire in self._wires:
            if wire.kind != "suppress":
                continue
            lower = self._by_name(wire.lower)
            if wire.higher in commanding:
                lower.suppressed_for = max(lower.suppressed_for, wire.ticks)
                silenced.add(wire.lower)
            elif lower.suppressed_for > 0:
                silenced.add(wire.lower)
        for layer in self.layers:
            if layer.suppressed_for > 0:
                layer.suppressed_for -= 1

        # 4. the topmost issued command that wasn't silenced wins
        for layer in reversed(self.layers):
            if layer.name in issued and layer.name not in silenced:
                return issued[layer.name]
        return None


# ---------------------------------------------------------------------------
# Demo layers — avoid subsumes wander subsumes (nothing); seek joins in
# ---------------------------------------------------------------------------


class AvoidLayer(Layer):
    """Competence 0: don't hit things. Bump sensor -> back up and turn."""

    def __init__(self) -> None:
        super().__init__("avoid")
        self.cooldown = 0

    def react(self) -> Optional[Command]:
        reading = self.take()
        if reading and reading.sensor == "bump" and reading.value > 0:
            self.state = "fleeing"
            self.cooldown = 2
            return Command("wheels", "reverse-turn", 1.0)
        if self.cooldown > 0:
            self.cooldown -= 1
            return Command("wheels", "reverse-turn", 1.0)
        self.state = "clear"
        return None


class WanderLayer(Layer):
    """Competence 1: meander. No input needed — a slow alternating drift."""

    def __init__(self) -> None:
        super().__init__("wander")
        self._n = 0

    def react(self) -> Optional[Command]:
        self.take()  # consume anything; wandering needs no sensors
        self._n += 1
        self.state = "drifting"
        return Command("wheels", "veer-left" if self._n % 4 < 2 else "veer-right", 0.3)


class SeekLayer(Layer):
    """Competence 2: head toward the light. Light sensor -> steer at it."""

    def __init__(self) -> None:
        super().__init__("seek")

    def react(self) -> Optional[Command]:
        reading = self.take()
        if reading and reading.sensor == "light":
            self.state = "homing"
            if reading.value > 0.2:
                return Command("wheels", "forward", 0.8)
            if reading.value < -0.2:
                return Command("wheels", "turn-right", 0.6)
            return Command("wheels", "turn-left", 0.6)
        self.state = "idle"
        return None


def demo_stack() -> Substrata:
    """Bottom-up: wander first, then avoid subsumes it, then seek tops it."""
    stack = Substrata()
    stack.add_layer(WanderLayer())
    stack.add_layer(AvoidLayer())
    stack.add_layer(SeekLayer())
    stack.suppress("avoid", "wander", ticks=2)
    stack.suppress("avoid", "seek", ticks=2)
    stack.suppress("seek", "wander", ticks=1)
    return stack


def demo() -> List[str]:
    """A tiny scenario: wander, then a bump (avoid takes over), then the
    bump clears, then light appears (seek homes in over wander)."""
    stack = demo_stack()
    out: List[str] = []
    avoid, seek = stack._by_name("avoid"), stack._by_name("seek")

    for _ in range(2):  # wandering, nothing sensed
        out.append(str(stack.tick() or "coast"))
    avoid.sense(Reading("bump", 1.0))
    for _ in range(3):  # avoid holds the motors through its cooldown
        out.append(str(stack.tick() or "coast"))
    out.append(str(stack.tick() or "coast"))  # quiet tick: suppression lingers
    seek.sense(Reading("light", 0.9))
    out.append(str(stack.tick() or "coast"))  # seek homes, subsuming wander
    return out


if __name__ == "__main__":  # pragma: no cover - demo
    print("\n".join(demo()))
