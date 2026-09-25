"""LEVI's procedure-word protocol: language-independent signaling.

Studied from: forgotten-methods-wave3-20260916-0015/report.md
(method #35 Q-Codes & Prosigns + method #36 Radiotelephony Prowords, MERGED)

Two old mechanisms, one shared trick:

* Q-codes split *what you mean* from *how you manage the exchange*: content
  codes carry meaning, and a single rule — append "?" — turns any statement
  into its corresponding question. The protocol rides inside the language.

* Radiotelephony prowords close the loop out loud: the receiver must *prove*
  receipt, and critical content gets read back so the sender can confirm or
  correct it before anyone acts.

This module merges them: an original, self-invented code set (content codes
vs procedure codes, cleanly separated), a "?" query transform, typed
acknowledgments that mean different things — RECEIVED (I heard it) is not
UNDERSTOOD (I grasp it) is not WILL-COMPLY (I will do it) — and a read-back
protocol that closes the loop *in the language itself*: the receiver repeats
critical content, the sender confirms or corrects.

The protocol state machine: a message is only *settled* once its required
acknowledgment (and read-back, for critical content) completes. Anything
else is an open loop, and open loops are reported as such.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

ORIGIN = "levi-revival/prowords"

# ---------------------------------------------------------------------------
# The code set: original LEVI codes, content vs procedure kept separate
# ---------------------------------------------------------------------------


class CodeKind(Enum):
    CONTENT = "content"  # carries meaning about the world
    PROCEDURE = "procedure"  # manages the exchange itself


@dataclass(frozen=True)
class Code:
    token: str
    kind: CodeKind
    meaning: str


# Fifteen original codes. The three-letter form is a shape homage only;
# the meanings are LEVI's own.
CODE_SET: List[Code] = [
    Code("LVA", CodeKind.CONTENT, "station is operating normally"),
    Code("LVB", CodeKind.CONTENT, "station needs assistance"),
    Code("LVC", CodeKind.CONTENT, "message received intact"),
    Code("LVD", CodeKind.CONTENT, "signal quality is poor"),
    Code("LVE", CodeKind.CONTENT, "standing by for further traffic"),
    Code("LVF", CodeKind.CONTENT, "fuel/supply level critical"),
    Code("LVG", CodeKind.CONTENT, "position report follows"),
    Code("LVH", CodeKind.CONTENT, "requesting repeat of last transmission"),
    Code("LVI", CodeKind.CONTENT, "weather is degrading operations"),
    Code("LVJ", CodeKind.CONTENT, "all units report status"),
    Code("ROGER", CodeKind.PROCEDURE, "received, last transmission"),
    Code("WILCO", CodeKind.PROCEDURE, "received, understood, will comply"),
    Code("SAYAGAIN", CodeKind.PROCEDURE, "repeat your last transmission"),
    Code("CORRECT", CodeKind.PROCEDURE, "your read-back is correct"),
    Code("WRONG", CodeKind.PROCEDURE, "your read-back is wrong, correcting"),
]

CODE_TABLE: Dict[str, Code] = {c.token: c for c in CODE_SET}


class UnknownCodeError(Exception):
    """Raised when a token is not in the code set."""


class ProtocolError(Exception):
    """Raised when the exchange rules are violated."""


# ---------------------------------------------------------------------------
# Queries: appending "?" turns any statement into a question
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Statement:
    code: Code
    is_query: bool = False

    def as_query(self) -> "Statement":
        """The ? transform: any statement becomes its corresponding question."""
        return Statement(code=self.code, is_query=True)

    def render(self) -> str:
        return self.code.token + ("?" if self.is_query else "")

    @property
    def meaning(self) -> str:
        base = self.code.meaning
        if self.is_query:
            return f"query: {base}?"
        return base


def parse(raw: str) -> Statement:
    """Parse a token string into a Statement, honoring the ? transform."""
    raw = raw.strip().upper()
    is_query = raw.endswith("?")
    token = raw[:-1] if is_query else raw
    if token not in CODE_TABLE:
        raise UnknownCodeError(f"unknown code: {token!r}")
    return Statement(code=CODE_TABLE[token], is_query=is_query)


# ---------------------------------------------------------------------------
# Typed acknowledgments: RECEIVED ≠ UNDERSTOOD ≠ WILL-COMPLY
# ---------------------------------------------------------------------------


class AckType(Enum):
    RECEIVED = "received"  # I heard the transmission
    UNDERSTOOD = "understood"  # I grasp its meaning
    WILL_COMPLY = "will_comply"  # I will act on it


# Procedure proword that carries each acknowledgment.
ACK_PROWORDS: Dict[AckType, str] = {
    AckType.RECEIVED: "ROGER",
    AckType.UNDERSTOOD: "ROGER UNDERSTOOD",
    AckType.WILL_COMPLY: "WILCO",
}


# ---------------------------------------------------------------------------
# Read-back protocol and the closed loop
# ---------------------------------------------------------------------------


@dataclass
class Exchange:
    """One protocol exchange: a statement, its ack, and its read-back."""

    statement: Statement
    critical: bool = False
    ack: Optional[AckType] = None
    readback: Optional[str] = None  # what the receiver repeated
    settled: bool = False
    corrections: int = 0

    def acknowledge(self, ack: AckType) -> str:
        """Receiver sends a typed acknowledgment. Returns the proword."""
        if self.ack is not None:
            raise ProtocolError("exchange already acknowledged")
        self.ack = ack
        if not self.critical:
            self.settled = True  # non-critical closes on ack alone
        return ACK_PROWORDS[ack]

    def read_back(self, repeated: str) -> str:
        """Receiver repeats critical content; sender confirms or corrects."""
        if not self.critical:
            raise ProtocolError("read-back only applies to critical content")
        if self.ack is None:
            raise ProtocolError("read-back requires acknowledgment first")
        self.readback = repeated
        expected = self.statement.render()
        if repeated.strip().upper() == expected:
            self.settled = True
            return "CORRECT"
        self.corrections += 1
        return "WRONG"

    def correct(self) -> str:
        """Sender issues the correction after a WRONG read-back."""
        if self.readback is None or self.settled:
            raise ProtocolError("nothing to correct")
        return f"WRONG I SAY AGAIN {self.statement.render()}"


class ProwordStation:
    """A station that runs the protocol: send, ack, read-back, audit."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.open: List[Exchange] = []
        self.closed: List[Exchange] = []

    def send(
        self,
        raw: str,
        critical: bool = False,
        query: bool = False,
    ) -> Exchange:
        stmt = parse(raw)
        if query:
            stmt = stmt.as_query()
        ex = Exchange(statement=stmt, critical=critical)
        self.open.append(ex)
        return ex

    def receive_ack(self, ex: Exchange, ack: AckType) -> str:
        proword = ex.acknowledge(ack)
        if ex.settled:
            self._close(ex)
        return proword

    def receive_readback(self, ex: Exchange, repeated: str) -> str:
        result = ex.read_back(repeated)
        if ex.settled:
            self._close(ex)
        return result

    def _close(self, ex: Exchange) -> None:
        if ex in self.open:
            self.open.remove(ex)
        self.closed.append(ex)

    @property
    def open_loops(self) -> List[Exchange]:
        """Every exchange not yet closed. An honest dashboard of loose ends."""
        return list(self.open)


def demo() -> Dict[str, object]:
    station = ProwordStation("levi-1")
    # Ordinary traffic: query transform + typed ack closes the loop.
    q = station.send("LVA", query=True)
    ack_word = station.receive_ack(q, AckType.UNDERSTOOD)
    # Critical traffic: ack, then read-back, then CORRECT.
    crit = station.send("LVF", critical=True)
    station.receive_ack(crit, AckType.WILL_COMPLY)
    verdict = station.receive_readback(crit, "LVF")
    # A wrong read-back gets corrected, not silently accepted.
    crit2 = station.send("LVJ", critical=True)
    station.receive_ack(crit2, AckType.RECEIVED)
    wrong = station.receive_readback(crit2, "LVA")
    correction = crit2.correct()
    return {
        "query_meaning": q.statement.meaning,
        "ack_proword": ack_word,
        "critical_verdict": verdict,
        "wrong_readback_verdict": wrong,
        "correction": correction,
        "open_loops": len(station.open_loops),
        "settled": len(station.closed),
    }


if __name__ == "__main__":
    print(json.dumps(demo(), indent=2))
