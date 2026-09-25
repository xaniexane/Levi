"""Identity as a first-class wire verb: WRU and the answerback drum.

Studied from: protocols-hunt-20260916-0041/report.md [Find 3 - Telex]

The studied shape: on the telex wire, "WRU" (who are you) is not a
question — it's a control character that *commands* the far-end
machine's answerback drum to physically strike its programmed
identity, and that identity is printed on BOTH ends of the line.

LEVI-native re-expression: stations with programmable answerback
drums, a line simulator where transmitting WRU returns the far-end
drum's strike and logs it on both stations' paper, and plain-text
traffic that carries along the sender's drum code. No real hardware;
the discipline of "identity answered by the machine, not the man" is
the point being kept.

Honest limits: the drum is a fixed string, not electromechanical
hardware; there is no timing, no baud, no line noise — the wire is
a simulator that always delivers unless a station is marked down.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

ORIGIN = "levi-revival/wire-identity"

#: The control word; a station that receives it must answer, not chat.
WRU = "WRU"


class WireError(Exception):
    """Raised for unprogrammed drums, unknown stations, or dead lines."""


@dataclass
class DrumStrike:
    """What got printed where during one wire exchange."""

    line: str
    heard_by: str
    printed: str


@dataclass
class Station:
    """One machine on the wire, with its own programmed answerback."""

    callsign: str
    answerback: str = ""
    paper: List[str] = field(default_factory=list)
    line_up: bool = True

    def program(self, text: str) -> None:
        """Set the answerback drum; must be printable, non-blank, short."""
        text = text.strip()
        if not text:
            raise WireError("answerback drum cannot be blank")
        if len(text) > 60:
            raise WireError("answerback drum is 60 characters max")
        if not all(c.isprintable() for c in text):
            raise WireError("answerback must be printable characters")
        self.answerback = text

    def _print(self, text: str) -> None:
        self.paper.append(text)


class TelexLine:
    """A two-or-more-ended wire. WRU is honored mechanically."""

    def __init__(self, name: str = "line-1") -> None:
        self.name = name
        self._stations: Dict[str, Station] = {}
        self.log: List[DrumStrike] = []

    def attach(self, station: Station) -> None:
        if station.callsign in self._stations:
            raise WireError(f"callsign already on this line: {station.callsign}")
        self._stations[station.callsign] = station

    def station(self, callsign: str) -> Station:
        try:
            return self._stations[callsign]
        except KeyError:
            raise WireError(f"no such station on {self.name}: {callsign}") from None

    def transmit(self, frm: str, to: str, text: str) -> List[DrumStrike]:
        """Send text from one station to another. WRU triggers the drum."""
        sender = self.station(frm)
        target = self.station(to)
        strikes: List[DrumStrike] = []

        def _record(heard_by: str, printed: str) -> None:
            strike = DrumStrike(line=self.name, heard_by=heard_by, printed=printed)
            self.log.append(strike)
            strikes.append(strike)

        if not target.line_up or not sender.line_up:
            raise WireError("line is down for one of the stations")

        for chunk in text.split():
            if chunk == WRU:
                if not target.answerback:
                    raise WireError(f"{to} has no programmed answerback")
                # The drum answers: printed on BOTH ends of the line.
                sender._print(f"[{to} answers] {target.answerback}")
                target._print(f"[WRU from {frm}] {target.answerback}")
                _record(sender.callsign, f"{to}: {target.answerback}")
                _record(target.callsign, f"WRU->{to}: {target.answerback}")
            else:
                target._print(f"{frm}: {chunk}")
                _record(target.callsign, f"{frm}: {chunk}")
        return strikes

    def answerback_of(self, callsign: str) -> str:
        """Ask, politely and explicitly, who a station's machine claims to be."""
        station = self.station(callsign)
        if not station.answerback:
            raise WireError(f"{callsign} has no programmed answerback")
        return station.answerback

    def recent_paper(self, callsign: str, n: int = 10) -> List[str]:
        """Last n lines printed at a station, newest first."""
        return list(reversed(self.station(callsign).paper))[:n]
