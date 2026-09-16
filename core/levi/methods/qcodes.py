"""Q-codes & prosigns: concise signaling code (encoder/decoder).

History: the radiotelegraph operators' language-independent protocol —
three-letter *Q-codes* (QTH = "my location is…", QRM = "I am being
interfered with") where appending "?" turns a statement into a query, plus
*prosigns* — procedural signals (AA, AR, SK, SOS) with fixed operational
meaning. Born in British maritime service c. 1909, internationally adopted
1912. Still alive in amateur radio; elsewhere absorbed into automated
protocols (TCP, APIs took the procedure-code idea).

In LEVI: Q-code *discipline* for the assistant's own status communication —
a tiny fixed vocabulary of state tokens (working / blocked / needs-input /
done) with the "?" convention for queries, used consistently in every
long-running task, so any job's state reads at a glance without parsing
prose. And a shared prosign set for human teams ("?QRM" = "I'm getting
noise on this thread").

Data below is the standard ITU Q-code set (QRA–QUZ range as used on air)
plus the common prosigns. Meanings are given statement-form; append "?"
for the query form per the 1909 convention.

Honesty: USEFUL PATTERN — a vocabulary discipline, not a protocol; nothing
here transmits anything.
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# The Q-code set (statement form; "?" makes it a query). Standard ITU
# meanings, condensed. This is the QRA–QUZ range from the report.
# ---------------------------------------------------------------------------

Q_CODES: dict[str, str] = {
    "QRA": "the name of my station is …",
    "QRG": "your exact frequency is … kHz",
    "QRH": "your frequency varies",
    "QRI": "the tone of your transmission is …",
    "QRK": "the readability of your signals is … (1–5)",
    "QRL": "I am busy (do not interfere)",
    "QRM": "your transmission is being interfered with",
    "QRN": "I am troubled by static",
    "QRO": "increase transmitter power",
    "QRP": "decrease transmitter power",
    "QRQ": "send faster (… wpm)",
    "QRS": "send more slowly (… wpm)",
    "QRT": "stop sending",
    "QRU": "I have nothing for you",
    "QRV": "I am ready",
    "QRX": "please stand by; I will call you again",
    "QRZ": "you are being called by …",
    "QSA": "the strength of your signals is … (1–5)",
    "QSB": "your signals are fading",
    "QSL": "I acknowledge receipt",
    "QSM": "repeat the last message",
    "QSO": "I can communicate with … direct",
    "QSP": "I will relay to …",
    "QST": "general call to all stations",
    "QSW": "I will transmit on …",
    "QSY": "change to … frequency",
    "QTC": "I have … messages for you",
    "QTH": "my location is …",
    "QTR": "the correct time is …",
    "QTX": "I will keep my station open",
    "QUA": "I have news of …",
    "QUE": "I can speak in … (language)",
    "QUF": "I have received the distress signal",
}

# ---------------------------------------------------------------------------
# Prosigns — procedural signals with fixed operational meaning.
# ---------------------------------------------------------------------------

PROSIGNS: dict[str, str] = {
    "AA": "all after … (repeat all after the indicated word)",
    "AB": "all before … (repeat all before the indicated word)",
    "AR": "end of message",
    "AS": "wait / stand by",
    "BK": "break — invite the other station to transmit",
    "BT": "break / separator between message parts",
    "CL": "closing station",
    "CQ": "calling all stations",
    "DE": "from (this is …)",
    "K": "go ahead — any station may reply",
    "KN": "go ahead — the named station only",
    "R": "received",
    "SK": "end of contact",
    "SOS": "distress",
    "VA": "end of work",
}


class SignalError(Exception):
    """Base class for signaling failures."""


class UnknownSignal(SignalError):
    """The token is neither a known Q-code nor a known prosign."""


@dataclass(frozen=True)
class Signal:
    """A parsed signal token."""

    code: str  # canonical uppercase, without "?"
    kind: str  # "qcode" or "prosign"
    meaning: str
    is_query: bool

    def display(self) -> str:
        q = "?" if self.is_query else ""
        return f"{self.code}{q} — {self.meaning}"


def parse(token: str) -> Signal:
    """Parse ``token`` into a Signal. Trailing "?" marks a query (Q-codes
    only — prosigns take no query form; ``SOS?`` is rejected)."""
    if not isinstance(token, str) or not token.strip():
        raise SignalError("signal token must be a non-empty string")
    raw = token.strip().upper()
    is_query = raw.endswith("?")
    code = raw[:-1] if is_query else raw
    if code in Q_CODES:
        return Signal(code=code, kind="qcode", meaning=Q_CODES[code], is_query=is_query)
    if code in PROSIGNS:
        if is_query:
            raise SignalError(f"prosign {code!r} takes no query form")
        return Signal(code=code, kind="prosign", meaning=PROSIGNS[code], is_query=False)
    raise UnknownSignal(f"unknown signal {token!r}")


def query(code: str) -> str:
    """Format the query form of a Q-code: ``query("QTH")`` -> ``"QTH?"``."""
    sig = parse(code)
    if sig.kind != "qcode":
        raise SignalError(f"{code!r} is a prosign, not a Q-code")
    return f"{sig.code}?"


def describe(code: str) -> str:
    """One-line meaning of a Q-code or prosign."""
    return parse(code).display()


def is_qcode(token: str) -> bool:
    try:
        return parse(token).kind == "qcode"
    except SignalError:
        return False


def status_report(job: str, code: str, note: str = "") -> str:
    """A glanceable job status line in Q-code discipline.

    Example: ``status_report("deep-research", "QRX")``
    -> ``"deep-research: QRX — please stand by; I will call you again"``.
    """
    sig = parse(code)
    line = f"{job}: {sig.code} — {sig.meaning}"
    return f"{line} ({note})" if note else line


__all__ = [
    "Q_CODES",
    "PROSIGNS",
    "SignalError",
    "UnknownSignal",
    "Signal",
    "parse",
    "query",
    "describe",
    "is_qcode",
    "status_report",
]
