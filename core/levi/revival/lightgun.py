"""CRT light-gun hit detection: timing and brightness, not true aiming.

Studied from: dead-game-genres-2026-09-16/report.md [Entries — CRT Light-Gun
Games] (CRT light-gun hit detection: black frame then white hit-boxes drawn
on trigger pull; photodiode reports light-instant: timing/brightness, not
true aiming).

This is an original, from-scratch implementation for LEVI, modeling the
*mechanism* honestly rather than simulating a screen. The real hardware
worked like this: on trigger pull the game blanked the screen to black, then
drew each target's hit-box as a solid white rectangle in its own time slot.
The gun's photodiode reported the instant it saw light. A hit meant "light
arrived during some target's slot" — the gun never knew *where* it was
pointing; it only knew *when* light arrived. There is no aim coordinate in
this module, by design: detection is timing plus a brightness threshold.

``LightGunSession`` models one trigger pull:

- ``configure(targets)``: each target is a ``(target_id, slot_index)`` pair;
  slot 0 draws first, slot 1 second, and so on.
- ``pull_trigger(observations)``: the photodiode's observation log for this
  pull — a list of ``(time_ms, brightness)`` samples. Any sample above the
  brightness threshold inside a slot's window counts as "saw light during
  that slot" and scores a hit on that slot's target.

``LightGunSession`` also computes the slot schedule from display parameters
(``frame_ms``, ``slot_ms``) so the timing windows are explicit, and it can
*synthesize* an expected observation log for a given aimed target — useful
for testing the detector against its own geometry without any real
hardware.

Hit resolution is deliberately dumb, like the hardware: first lit slot
wins; light outside every slot window is ignored (that's the black frame
doing its job); two lit slots resolve to the earlier one.

Public surface:
- ``Target``: ``(target_id, slot)``.
- ``LightGunSession``: ``configure(targets)``, ``slot_windows()``,
  ``pull_trigger(observations)`` -> ``ShotResult``,
  ``synthesize_observations(aimed_target_id, brightness=1.0)``.
- ``ShotResult``: ``hit: bool``, ``target_id: Optional[str]``,
  ``slot: Optional[int]``, ``reason: str``.

Honest limits: no aim coordinates exist anywhere in this module — a hit is
purely "light during a slot". The model assumes the CRT draws slots in
order with no overlap; real phosphor decay and ambient light are folded
into the brightness threshold, not simulated.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


ORIGIN = "levi-revival/lightgun"


class LightGunError(ValueError):
    """Raised for misconfigured sessions or malformed observations."""


@dataclass(frozen=True)
class Target:
    """A shootable thing, identified only by which time slot it draws in."""

    target_id: str
    slot: int


@dataclass(frozen=True)
class ShotResult:
    """The outcome of one trigger pull."""

    hit: bool
    target_id: Optional[str]
    slot: Optional[int]
    reason: str


# (time_ms, brightness) samples from the photodiode during one trigger pull.
Observation = Tuple[float, float]


@dataclass
class LightGunSession:
    """One trigger pull's worth of timing-based hit detection.

    ``frame_ms`` is the display's frame time; ``slot_ms`` is how long each
    target's white box stays up. Slots draw back-to-back starting at t=0
    (the black frame is the implicit "before slots" region).
    """

    frame_ms: float = 16.7
    slot_ms: float = 2.0
    brightness_threshold: float = 0.5
    _targets: List[Target] = field(default_factory=list, init=False)
    _by_slot: Dict[int, Target] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        if self.frame_ms <= 0 or self.slot_ms <= 0:
            raise LightGunError("frame_ms and slot_ms must be positive")
        if self.brightness_threshold < 0:
            raise LightGunError("brightness_threshold cannot be negative")

    # -- setup ---------------------------------------------------------
    def configure(self, targets: List[Target]) -> "LightGunSession":
        if not targets:
            raise LightGunError("need at least one target")
        slots = [t.slot for t in targets]
        if any(s < 0 for s in slots):
            raise LightGunError("slot indices must be >= 0")
        if len(set(slots)) != len(slots):
            raise LightGunError("each target needs its own time slot")
        total = max(slots) * self.slot_ms + self.slot_ms
        if total > self.frame_ms:
            raise LightGunError(
                f"slots need {total:.1f}ms but the frame is {self.frame_ms:.1f}ms"
            )
        self._targets = list(targets)
        self._by_slot = {t.slot: t for t in targets}
        return self

    def slot_windows(self) -> Dict[int, Tuple[float, float]]:
        """slot -> (start_ms, end_ms) when that target's box is white."""
        return {
            t.slot: (t.slot * self.slot_ms, (t.slot + 1) * self.slot_ms)
            for t in self._targets
        }

    # -- detection -----------------------------------------------------
    def pull_trigger(self, observations: List[Observation]) -> ShotResult:
        """Decide the shot from the photodiode's light log.

        First slot window containing an above-threshold sample wins. Light
        outside every window (the black frame) is ignored.
        """
        if not self._targets:
            raise LightGunError("no targets configured")
        windows = self.slot_windows()
        for time_ms, brightness in observations:
            if time_ms < 0:
                raise LightGunError("observation times must be >= 0")
            if brightness < self.brightness_threshold:
                continue  # too dim: ambient noise or phosphor decay
            for slot in sorted(windows):
                start, end = windows[slot]
                if start <= time_ms < end:
                    target = self._by_slot[slot]
                    return ShotResult(
                        hit=True,
                        target_id=target.target_id,
                        slot=slot,
                        reason=(
                            f"light at {time_ms:.2f}ms inside slot {slot} "
                            f"window [{start:.2f}, {end:.2f})"
                        ),
                    )
        return ShotResult(
            hit=False,
            target_id=None,
            slot=None,
            reason="no above-threshold light inside any slot window",
        )

    # -- test helper ---------------------------------------------------
    def synthesize_observations(
        self, aimed_target_id: Optional[str], brightness: float = 1.0
    ) -> List[Observation]:
        """Build the observation log the hardware *would* produce.

        If ``aimed_target_id`` names a configured target, the gun "sees"
        its slot's white box (one bright sample mid-slot, plus dim black-
        frame samples around it). If None, the gun sees only darkness —
        a clean miss. This is a test harness, not a claim about aiming.
        """
        if not self._targets:
            raise LightGunError("no targets configured")
        windows = self.slot_windows()
        obs: List[Observation] = [(0.0, 0.05), (self.frame_ms - 0.1, 0.05)]
        if aimed_target_id is not None:
            match = [t for t in self._targets if t.target_id == aimed_target_id]
            if not match:
                raise LightGunError(f"unknown target {aimed_target_id!r}")
            start, end = windows[match[0].slot]
            obs.append(((start + end) / 2.0, brightness))
        return sorted(obs)
