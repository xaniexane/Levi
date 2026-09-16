"""The Cybersyn opsroom method: the algedonic decision-room protocol.

Origin: Chile 1971-73 — Stafford Beer's Cybersyn. Telex data feeds from
factories, statistical monitoring (Cyberstride), and the famous Opsroom: a
hexagonal decision room with seven swivel chairs, wall-sized data displays,
and deliberately *no paper* — designed so managers would confront
real-time signals and decide in the room, with an "algedonic" alert knob
for pain/pleasure signals that bypass normal reporting.

What it is in LEVI: a weekly review rendered as a room. Seven "chairs"
(your roles), each with its ONE critical signal; algedonic alerts for
anomalies that bypass the usual narrative; a forced decision log. The
assistant prepares the room; you sit in it. The design insight survives
the history: the bottleneck isn't data, it's the *decision interface* —
shape the room and you shape the deciding.

Honesty label: INSPIRATIONAL — do not depict Cybersyn as a functioning
real-time national AI. It was a prototype with daily batch data, grand
ambitions, and a famous room. Its value is the *decision-room concept*:
variety attenuated to what a human can grasp, a rhythm that forces
decisions out. Faithful protocol, honest about limits.

Deny-closed inputs: unknown chairs, empty signal names, non-numeric
signal values, and decisions without rationale are rejected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, Union

__all__ = ["CHAIRS", "Signal", "Decision", "OpsRoom"]

# The seven chairs: one per role in the decision rhythm.
CHAIRS: tuple[str, ...] = (
    "operator",     # S1: what did the work do this week?
    "coordinator",  # S2: where did units clash or oscillate?
    "controller",   # S3: are resources where the work is?
    "auditor",      # S3*: what did the direct look reveal?
    "scout",        # S4: what changed outside?
    "steward",      # S5: are we still who we intend to be?
    "chair",        # the decider: what is decided before leaving the room?
)

DateLike = Union[date, str]


@dataclass
class Signal:
    chair: str
    name: str
    value: float
    threshold: Optional[float] = None
    direction: str = "above"  # alert when value goes "above" or "below" threshold
    unit: str = ""


@dataclass
class Decision:
    at: str  # ISO datetime
    chair: str
    decision: str
    rationale: str


class OpsRoom:
    """The decision room: seven chairs, one signal each, algedonic alerts."""

    def __init__(self, name: str = "weekly opsroom"):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("room name must be a non-empty string")
        self.name = name.strip()
        self._signals: dict[str, Signal] = {}
        self._decisions: list[Decision] = []

    # -- seating the room --------------------------------------------------------
    def seat(self, chair: str, signal_name: str, value: float,
             threshold: Optional[float] = None, direction: str = "above",
             unit: str = "") -> Signal:
        """Give a chair its one critical signal (variety attenuation).

        Each chair gets exactly ONE signal — the discipline is the limit.
        """
        if chair not in CHAIRS:
            raise ValueError(f"unknown chair {chair!r}; chairs: {list(CHAIRS)}")
        if not isinstance(signal_name, str) or not signal_name.strip():
            raise ValueError("signal name must be a non-empty string")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"signal value must be numeric, got {value!r}")
        if direction not in ("above", "below"):
            raise ValueError("direction must be 'above' or 'below'")
        if threshold is not None and not isinstance(threshold, (int, float)):
            raise ValueError("threshold must be numeric or None")
        signal = Signal(chair=chair, name=signal_name.strip(), value=float(value),
                        threshold=threshold, direction=direction, unit=unit or "")
        self._signals[chair] = signal
        return signal

    def prepare(self) -> dict:
        """The room, ready: every chair, its signal, its status."""
        room = {}
        for chair in CHAIRS:
            sig = self._signals.get(chair)
            room[chair] = {
                "seated": sig is not None,
                "signal": sig.name if sig else None,
                "value": sig.value if sig else None,
                "unit": sig.unit if sig else "",
                "status": self._signal_status(sig) if sig else "empty chair",
            }
        empty = [c for c in CHAIRS if c not in self._signals]
        return {"room": self.name, "chairs": room, "empty_chairs": empty}

    @staticmethod
    def _signal_status(sig: Signal) -> str:
        if sig.threshold is None:
            return "watching (no threshold)"
        breached = (sig.value > sig.threshold if sig.direction == "above"
                    else sig.value < sig.threshold)
        return "ALGEDONIC" if breached else "nominal"

    # -- the algedonic channel -----------------------------------------------------
    def algedonic(self) -> list[dict]:
        """Pain/pleasure signals: anomalies that bypass normal reporting.

        In the Opsroom the algedonic knob let a factory scream straight to
        the room. Here: any signal past its threshold, with its chair.
        """
        alerts = []
        for chair, sig in self._signals.items():
            if self._signal_status(sig) == "ALGEDONIC":
                alerts.append({
                    "chair": chair,
                    "signal": sig.name,
                    "value": sig.value,
                    "threshold": sig.threshold,
                    "direction": sig.direction,
                    "unit": sig.unit,
                    "cry": f"{sig.name}: {sig.value}{sig.unit} is "
                           f"{sig.direction} threshold {sig.threshold}{sig.unit}",
                })
        return alerts

    # -- the forced decision ---------------------------------------------------------
    def decide(self, chair: str, decision: str, rationale: str) -> Decision:
        """Record a decision before leaving the room. No decision, no adjourn.

        Rationale is mandatory — the room exists to force *reasoned*
        deciding, not vibes.
        """
        if chair not in CHAIRS:
            raise ValueError(f"unknown chair {chair!r}")
        if not isinstance(decision, str) or not decision.strip():
            raise ValueError("decision must be a non-empty string")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError("rationale is mandatory — the room forces reasoned deciding")
        entry = Decision(at=datetime.now().isoformat(timespec="seconds"),
                         chair=chair, decision=decision.strip(),
                         rationale=rationale.strip())
        self._decisions.append(entry)
        return entry

    def decisions(self) -> list[Decision]:
        return list(self._decisions)

    def adjourn(self) -> dict:
        """Close the session: alerts confronted, decisions logged."""
        alerts = self.algedonic()
        return {
            "room": self.name,
            "alerts_raised": len(alerts),
            "alerts": alerts,
            "decisions": len(self._decisions),
            "adjourned": bool(self._decisions) or not alerts,
            "note": ("Adjourned with decisions logged."
                     if self._decisions else
                     "No decisions recorded — the room did not do its job."
                     if alerts else
                     "Quiet week: no alerts, no decisions required."),
        }
