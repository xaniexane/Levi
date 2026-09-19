"""One academic application suite on a single transport.

Studied from: dead-networks-20260916 report.md [JANET (UK)].

The mechanism under study: a *complete application suite* — file
transfer, terminal sessions, mail, and job transfer — produced as one
coherent set of protocols over a common transport, instead of four
unrelated tools. Sites carry big-endian names (country first, e.g.
``UK.AC.HATFIELD``); a directory resolves those names to addresses.

Original, from-scratch implementation for LEVI. The "network" is an
in-process transport (dict of inboxes); no sockets, no wall clock.
stdlib-only. No network.

Public surface:
- ``NRSName`` — parse/validate big-endian dotted names; ordering is
  most-significant-label first.
- ``Directory`` — ``register(name, address)``, ``lookup(name)``.
- ``Transport`` — ``send(address, payload)``, ``drain(address)``.
- ``BlueBook`` — chunked file transfer with per-block checksums and
  receiver-driven retransmit.
- ``GreyBook`` — store-and-forward mail; queues per recipient.
- ``GreenBook`` — terminal session: open, send lines, host handler
  answers.
- ``RedBook`` — job submit by id; server runs handler; result fetched.
- ``Suite`` — wires directory + transport + the four books together.

Honest limits: checksums are CRC-ish (zlib), not cryptographic;
delivery is in-process; mail has no relaying between servers.
"""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

ORIGIN = "levi-revival/coloured_books"

_NAME_RE = re.compile(r"^[A-Z0-9]+(\.[A-Z0-9]+)+$")


@dataclass(frozen=True)
class NRSName:
    """A big-endian site name: most significant label first."""

    labels: Tuple[str, ...]

    @classmethod
    def parse(cls, text: str) -> "NRSName":
        upper = text.strip().upper()
        if not _NAME_RE.match(upper):
            raise ValueError(f"bad NRS name: {text!r}")
        return cls(tuple(upper.split(".")))

    def __str__(self) -> str:
        return ".".join(self.labels)

    def parent(self) -> Optional["NRSName"]:
        """Drop the least-significant label (rightmost)."""
        if len(self.labels) < 2:
            return None
        return NRSName(self.labels[:-1])

    def sort_key(self) -> Tuple[str, ...]:
        """Big-endian ordering: compare country first."""
        return self.labels


class Directory:
    """White-pages directory: NRS name -> transport address."""

    def __init__(self) -> None:
        self._table: Dict[NRSName, str] = {}

    def register(self, name: str, address: str) -> NRSName:
        parsed = NRSName.parse(name)
        self._table[parsed] = address
        return parsed

    def lookup(self, name: str) -> str:
        parsed = NRSName.parse(name)
        try:
            return self._table[parsed]
        except KeyError:
            raise KeyError(f"no such site: {name}") from None

    def sites(self) -> List[str]:
        return sorted(
            (str(n) for n in self._table), key=lambda s: NRSName.parse(s).sort_key()
        )


class Transport:
    """The common carrier: addressed inboxes, in-process delivery."""

    def __init__(self) -> None:
        self._inboxes: Dict[str, List[Any]] = {}

    def send(self, address: str, payload: Any) -> None:
        self._inboxes.setdefault(address, []).append(payload)

    def drain(self, address: str) -> List[Any]:
        """Take everything waiting for an address (empties the inbox)."""
        return self._inboxes.pop(address, [])


# ---------------------------------------------------------------------------
# The four books
# ---------------------------------------------------------------------------


@dataclass
class _Block:
    seq: int
    data: bytes
    crc: int


class BlueBook:
    """File transfer: chunked, per-block checksums, receiver-driven repair."""

    BLOCK = 64

    def __init__(self, transport: Transport) -> None:
        self.transport = transport
        self._incoming: Dict[str, Dict[int, bytes]] = {}  # addr -> seq -> data
        self._meta: Dict[str, Tuple[str, int]] = {}  # addr -> (filename, nblocks)

    def send_file(self, address: str, filename: str, data: bytes) -> int:
        """Send a file as blocks; returns block count."""
        nblocks = (len(data) + self.BLOCK - 1) // self.BLOCK or 1
        self.transport.send(address, ("FILE-START", filename, nblocks))
        for seq in range(nblocks):
            chunk = data[seq * self.BLOCK : (seq + 1) * self.BLOCK]
            self.transport.send(address, ("FILE-BLOCK", seq, chunk, zlib.crc32(chunk)))
        return nblocks

    def _ingest(self, address: str) -> None:
        for msg in self.transport.drain(address):
            kind = msg[0]
            if kind == "FILE-START":
                _, filename, nblocks = msg
                self._meta[address] = (filename, nblocks)
                self._incoming[address] = {}
            elif kind == "FILE-BLOCK":
                _, seq, chunk, crc = msg
                if zlib.crc32(chunk) == crc:  # corrupt blocks are dropped
                    self._incoming.setdefault(address, {})[seq] = chunk

    def missing(self, address: str) -> List[int]:
        """Block sequences not yet received intact."""
        self._ingest(address)
        if address not in self._meta:
            return []
        _, nblocks = self._meta[address]
        have = self._incoming.get(address, {})
        return [s for s in range(nblocks) if s not in have]

    def request_retransmit(
        self, from_address: str, address: str, seqs: List[int], data: bytes
    ) -> None:
        """Ask the sender side to re-emit specific blocks (loopback test path)."""
        for seq in seqs:
            chunk = data[seq * self.BLOCK : (seq + 1) * self.BLOCK]
            self.transport.send(address, ("FILE-BLOCK", seq, chunk, zlib.crc32(chunk)))
        # 'from_address' names the original sender for logging parity; unused.

    def receive_file(self, address: str) -> Tuple[str, bytes]:
        """Reassemble when all blocks are present; else raise."""
        missing = self.missing(address)
        if missing:
            raise ValueError(f"incomplete file, missing blocks: {missing}")
        filename, nblocks = self._meta[address]
        blocks = self._incoming[address]
        data = b"".join(blocks[s] for s in range(nblocks))
        del self._meta[address]
        del self._incoming[address]
        return filename, data


@dataclass
class MailMessage:
    sender: str
    recipient: str
    subject: str
    body: str


class GreyBook:
    """Mail: store-and-forward; mail waits until the recipient collects."""

    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def post(self, msg: MailMessage) -> None:
        self.transport.send(f"mail:{msg.recipient}", msg)

    def collect(self, recipient: str) -> List[MailMessage]:
        """Take all queued mail for a recipient."""
        return self.transport.drain(f"mail:{recipient}")


class GreenBook:
    """Terminal sessions: open a session, send lines, host handler answers."""

    def __init__(self, transport: Transport) -> None:
        self.transport = transport
        self._handlers: Dict[str, Callable[[str], str]] = {}

    def serve(self, address: str, handler: Callable[[str], str]) -> None:
        """Register the host-side line handler for an address."""
        self._handlers[address] = handler

    def open(self, address: str) -> "TerminalSession":
        if address not in self._handlers:
            raise KeyError(f"no terminal service at {address}")
        return TerminalSession(address, self._handlers[address])


class TerminalSession:
    def __init__(self, address: str, handler: Callable[[str], str]) -> None:
        self.address = address
        self._handler = handler
        self.transcript: List[Tuple[str, str]] = []

    def send_line(self, line: str) -> str:
        reply = self._handler(line)
        self.transcript.append((line, reply))
        return reply


class RedBook:
    """Job transfer: submit a job spec, fetch the result by id."""

    def __init__(self) -> None:
        self._jobs: Dict[int, Dict[str, Any]] = {}
        self._next_id = 1

    def submit(
        self, spec: Dict[str, Any], runner: Callable[[Dict[str, Any]], Any]
    ) -> int:
        """Run the job through the server-side runner; returns job id."""
        job_id = self._next_id
        self._next_id += 1
        self._jobs[job_id] = {"spec": spec, "result": runner(spec), "done": True}
        return job_id

    def result(self, job_id: int) -> Any:
        try:
            job = self._jobs[job_id]
        except KeyError:
            raise KeyError(f"no such job: {job_id}") from None
        return job["result"]


class Suite:
    """The suite as one object: directory + transport + four books."""

    def __init__(self) -> None:
        self.directory = Directory()
        self.transport = Transport()
        self.blue = BlueBook(self.transport)
        self.grey = GreyBook(self.transport)
        self.green = GreenBook(self.transport)
        self.red = RedBook()

    def add_site(self, name: str, address: str) -> NRSName:
        return self.directory.register(name, address)


def demo() -> Dict[str, Any]:
    suite = Suite()
    suite.add_site("UK.AC.HATFIELD", "hatfield")
    addr = suite.directory.lookup("uk.ac.hatfield")
    suite.blue.send_file(addr, "notes.txt", b"hello janet " * 20)
    filename, data = suite.blue.receive_file(addr)
    suite.grey.post(MailMessage("a@x", "bob", "hi", "hello bob"))
    mail = suite.grey.collect("bob")
    suite.green.serve(addr, lambda line: line.upper())
    sess = suite.green.open(addr)
    echo = sess.send_line("ping")
    job = suite.red.submit({"op": "double", "x": 21}, lambda s: s["x"] * 2)
    return {
        "file": (filename, len(data)),
        "mail": [(m.sender, m.subject) for m in mail],
        "echo": echo,
        "job": suite.red.result(job),
        "sites": suite.directory.sites(),
    }
