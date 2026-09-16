"""Signal grades — the LEVI-native signal plane.

Every daemon, heartbeat, and instinct speaks through four grades:

* ``SILENT``   — nothing is shown. Not a quiet line, not a log whisper:
  genuinely no user-visible output. Used for HEARTBEAT_OK-style pulses.
* ``NUDGE``    — one line in chrome (status bar / CLI line), never chat.
  Example: "focus block ends in 8m".
* ``CARD``     — a tagged daemon card, e.g. ``[warden] DUE: ship page``.
  Cards carry actions (done / snooze / drop).
* ``ESCALATE`` — a card that requires acknowledgment. Reserved for things
  the user explicitly asked to be held accountable for (2x missed locks,
  downed services they depend on).

``route()`` maps a :class:`Signal` to a :class:`Delivery` descriptor:
SILENT always routes to "suppressed entirely" — the plane enforces this,
so a SILENT result can never leak into user-visible output by accident.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SignalGrade(Enum):
    """Ordered signal grades. Values order by intrusiveness."""

    SILENT = 0
    NUDGE = 1
    CARD = 2
    ESCALATE = 3

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name


@dataclass
class Signal:
    """One unit of daemon-to-user communication.

    ``tag`` is the daemon voice, always bracketed: ``[warden]``,
    ``[sentinel]``, ``[heartbeat]``, ``[supervisor]``. ``actions`` are the
    taps the card offers (done / snooze 1h / drop). ``due_now`` marks a
    signal as time-critical enough to pierce focus mute.
    """

    grade: SignalGrade
    tag: str
    title: str
    body: str = ""
    actions: tuple[str, ...] = ()
    requires_ack: bool = False
    due_now: bool = False
    source: str = ""  # instinct id or daemon that produced it

    def __post_init__(self) -> None:
        if not isinstance(self.grade, SignalGrade):
            raise TypeError("grade must be a SignalGrade, got %r" % (self.grade,))
        if not (self.tag.startswith("[") and self.tag.endswith("]")):
            raise ValueError("tag must be bracketed like '[warden]', got %r" % self.tag)
        self.actions = tuple(self.actions)
        if self.grade is SignalGrade.ESCALATE:
            # Escalations are acknowledgments by definition; a caller cannot
            # downgrade this.
            self.requires_ack = True


@dataclass(frozen=True)
class Delivery:
    """Where a signal goes. SILENT always lands on ``delivered=False``."""

    signal: Signal
    delivered: bool
    surface: str  # "none" | "chrome-line" | "card"
    requires_ack: bool

    def render(self) -> str:
        """Render the delivery for its surface. SILENT renders to ""."""
        if not self.delivered:
            return ""
        return render(self.signal)


def route(signal: Signal) -> Delivery:
    """Map a signal to its delivery descriptor.

    SILENT is suppressed entirely — ``delivered=False`` and an empty
    render. This is the honest-silence guarantee: no quiet line, no log
    whisper, nothing the user can see.
    """
    if signal.grade is SignalGrade.SILENT:
        return Delivery(
            signal=signal, delivered=False, surface="none", requires_ack=False
        )
    if signal.grade is SignalGrade.NUDGE:
        return Delivery(
            signal=signal, delivered=True, surface="chrome-line", requires_ack=False
        )
    if signal.grade is SignalGrade.CARD:
        return Delivery(
            signal=signal, delivered=True, surface="card", requires_ack=False
        )
    # ESCALATE
    return Delivery(signal=signal, delivered=True, surface="card", requires_ack=True)


def render(signal: Signal) -> str:
    """Render a signal for its grade. SILENT renders to the empty string."""
    if signal.grade is SignalGrade.SILENT:
        return ""
    if signal.grade is SignalGrade.NUDGE:
        line = "%s %s" % (signal.tag, signal.title)
        if signal.body:
            line += " — %s" % signal.body.splitlines()[0]
        return line
    # CARD / ESCALATE: tagged card.
    lines = ["%s %s" % (signal.tag, signal.title)]
    if signal.body:
        lines.append(signal.body)
    if signal.actions:
        lines.append("actions: " + " / ".join(signal.actions))
    if signal.grade is SignalGrade.ESCALATE:
        lines.append("[ack required — tap to acknowledge]")
    return "\n".join(lines)
