"""Radiotelephony prowords: typed-acknowledgment message discipline.

History: aviation's standardized phraseology (ICAO Annex 10) — prowords
with exact meanings: SAY AGAIN (repeat), WILCO (understood and will
comply), ROGER (received — *never* an answer to a question), READ BACK
(repeat verbatim), UNABLE (cannot comply, reason follows), WORDS TWICE.
"The use of courtesies should be avoided" — every syllable is load-
bearing. The protocol assumes the channel is noisy and the stakes are
fatal, so ambiguity is designed out rather than hoped away. It is not dead
in aviation; it is forgotten *everywhere else* — medicine, management, and
human-AI interaction run on untyped acknowledgments ("ok", "got it"),
which is why instructions evaporate.

In LEVI: the assistant speaks prowords for consequential exchanges. It
ROGERs (receipt only), WILCOs (will comply), AFFIRMs/negatives answers, and
demands READ BACK on anything irreversible ("read back the transfer
amount") before acting. UNABLE is always followed by a reason — enforced
by the type, not by politeness. You get a tiny, learnable discipline that
ends the era of "did it understand me?"

Honesty: USEFUL PATTERN — a linguistic discipline for closing the loop;
it cannot make anyone actually listen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time


PROWORDS: dict[str, str] = {
    "AFFIRM": "yes — that is correct (answers a question)",
    "NEGATIVE": "no — that is not correct (answers a question)",
    "ROGER": "received — receipt only, never an answer to a question",
    "WILCO": "understood and WILL COMPLY",
    "SAY AGAIN": "repeat your last transmission",
    "I SAY AGAIN": "I am repeating on my own initiative",
    "READ BACK": "repeat this message back to me verbatim",
    "CORRECTION": "an error was made; the corrected version follows",
    "UNABLE": "cannot comply (reason follows)",
    "VERIFY": "check the coding/wording with the originator",
    "WORDS TWICE": "communication is difficult; transmit each phrase twice",
    "DISREGARD": "ignore the last transmission",
    "OVER": "my turn is over; a reply is expected",
    "OUT": "conversation is over; no reply expected or desired",
}


class ProwordError(Exception):
    """Base class for proword-discipline violations."""


class ReadbackMismatch(ProwordError):
    """The read-back did not match verbatim — the loop is NOT closed."""


class Ack(Enum):
    """Typed acknowledgments. ROGER != WILCO != AFFIRM, by design."""

    ROGER = "ROGER"
    WILCO = "WILCO"
    AFFIRM = "AFFIRM"
    NEGATIVE = "NEGATIVE"
    UNABLE = "UNABLE"


@dataclass
class Instruction:
    """A consequential instruction awaiting a typed acknowledgment."""

    text: str
    reversible: bool
    issued_at: float = field(default_factory=time.time)
    acknowledged: Ack | None = None
    unable_reason: str = ""
    readback_confirmed: bool = False

    def require_readback(self) -> str:
        """Return the exact text the other party must repeat verbatim."""
        return self.text


class Exchange:
    """A disciplined exchange: typed acks, read-back on irreversible acts."""

    def __init__(self):
        self.log: list[dict] = []

    # -- framing ----------------------------------------------------------
    def frame(self, proword: str, text: str = "") -> str:
        """Format ``PROWORD — text``. Unknown prowords are rejected."""
        key = proword.strip().upper()
        if key not in PROWORDS:
            raise ProwordError(f"unknown proword {proword!r}; use the fixed vocabulary")
        line = key if not text else f"{key} — {text}"
        self.log.append({"proword": key, "text": text, "at": time.time()})
        return line

    def say(self, text: str) -> Instruction:
        """Issue an instruction. ``reversible=False`` arms read-back."""
        if not text or not text.strip():
            raise ValueError("instruction text must be non-empty")
        return Instruction(text=text.strip(), reversible=True)

    def order(self, text: str) -> Instruction:
        """Issue an IRREVERSIBLE instruction: WILCO requires READ BACK first."""
        if not text or not text.strip():
            raise ValueError("instruction text must be non-empty")
        return Instruction(text=text.strip(), reversible=False)

    # -- closing the loop ---------------------------------------------------
    def acknowledge(
        self, instruction: Instruction, ack: Ack, reason: str = ""
    ) -> Instruction:
        """Record a typed acknowledgment.

        Rules (the discipline): UNABLE requires a reason; WILCO on an
        irreversible instruction requires a confirmed read-back first;
        ROGER on a question is a no-op receipt, never an answer.
        """
        if ack is Ack.UNABLE and not reason.strip():
            raise ProwordError("UNABLE must be followed by a reason")
        if (
            ack is Ack.WILCO
            and not instruction.reversible
            and not instruction.readback_confirmed
        ):
            raise ProwordError(
                "irreversible instruction: READ BACK must be confirmed before WILCO"
            )
        instruction.acknowledged = ack
        instruction.unable_reason = reason.strip()
        self.log.append(
            {"proword": ack.value, "text": reason.strip(), "at": time.time()}
        )
        return instruction

    def read_back(self, instruction: Instruction, repeat: str) -> bool:
        """Verify a verbatim repeat. Exact match closes the loop."""
        if repeat.strip() == instruction.text:
            instruction.readback_confirmed = True
            self.log.append(
                {"proword": "READ BACK", "text": "confirmed", "at": time.time()}
            )
            return True
        raise ReadbackMismatch(
            f"read-back {repeat!r} does not match {instruction.text!r}"
        )

    def correct(self, instruction: Instruction, corrected: str) -> Instruction:
        """Issue a CORRECTION: the old instruction is void, the new one stands."""
        if not corrected or not corrected.strip():
            raise ValueError("corrected text must be non-empty")
        self.log.append(
            {
                "proword": "CORRECTION",
                "text": f"{instruction.text!r} -> {corrected.strip()!r}",
                "at": time.time(),
            }
        )
        return Instruction(text=corrected.strip(), reversible=instruction.reversible)


__all__ = [
    "PROWORDS",
    "ProwordError",
    "ReadbackMismatch",
    "Ack",
    "Instruction",
    "Exchange",
]
