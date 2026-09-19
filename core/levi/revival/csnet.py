"""revival/csnet.py — heterogeneous transports under one interface.

Studied from: dead-networks-20260916 (report.md [CSNET]).

Revival of: CSNET — the adapter pattern run at national scale. Dial-up hosts,
X.25 hosts, and ARPANET hosts could not talk to each other directly, so a
common service layer glued them under one addressing and delivery interface,
backed by a name-server white-pages directory.

Why it matters: heterogeneity is the normal state of real networks. Instead
of demanding every endpoint speak the same wire protocol, you put an adapter
at each edge that translates to and from a common envelope, and you keep one
directory that maps human names to (address, transport) pairs. New transports
join by writing one adapter, not by renegotiating the whole net.

LEVI adaptation:
- ``Transport``: the common adapter interface — ``wrap()`` turns a
  (sender, recipient, body) triple into a wire ``Frame``; ``unwrap()``
  turns it back.
- ``DialupTransport`` / ``X25Transport`` / ``ArpanetTransport``: three
  adapters, each with its own addressing scheme and framing quirks.
- ``WhitePages``: the name-server directory — names map to addresses and
  transport kinds; lookups raise on unknown names instead of guessing.
- ``Gateway``: routes a message from the sender's transport to the
  recipient's transport through the common envelope, using WhitePages for
  both ends.

Honest limits:
- Transports are framing models, not real line disciplines: no modems, no
  X.25 virtual circuits, no NCP handshakes. "Transmission" is an in-process
  handoff through the gateway.
- Addresses are validated syntactically per transport, not registered with
  any real authority.
"""

from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class Frame:
    transport: str
    sender_addr: str
    recipient_addr: str
    payload: str
    at: float = field(default_factory=time.time)


class Transport(ABC):
    """Adapter interface: every transport speaks frames at its edges."""

    kind: str = "abstract"
    address_pattern: str = r".+"

    @abstractmethod
    def wrap(self, sender: str, recipient: str, body: str) -> Frame:
        """Translate a common-envelope send into this transport's frame."""

    @abstractmethod
    def unwrap(self, frame: Frame) -> Tuple[str, str, str]:
        """Translate this transport's frame back to (sender, recipient, body)."""

    def valid_address(self, address: str) -> bool:
        return bool(re.fullmatch(self.address_pattern, address))


class DialupTransport(Transport):
    """Store-and-forward over phone lines: addresses are phone numbers."""

    kind = "dialup"
    address_pattern = r"\+\d{7,15}"

    def wrap(self, sender: str, recipient: str, body: str) -> Frame:
        # Dial discipline: the number is dialed, then the payload follows.
        return Frame(
            transport=self.kind,
            sender_addr=sender,
            recipient_addr=recipient,
            payload=f"DIAL {recipient}\n{body}",
        )

    def unwrap(self, frame: Frame) -> Tuple[str, str, str]:
        self._require(frame)
        body = (
            frame.payload.split("\n", 1)[1] if "\n" in frame.payload else frame.payload
        )
        return frame.sender_addr, frame.recipient_addr, body

    def _check(self, *addrs: str) -> None:
        for addr in addrs:
            if not self.valid_address(addr):
                raise ValueError(f"not a dialup address: {addr!r}")

    def _require(self, frame: Frame) -> None:
        if frame.transport != self.kind:
            raise ValueError(f"not a dialup frame: {frame.transport!r}")


class X25Transport(Transport):
    """Packet-switched X.25 style: addresses are numeric DTE addresses."""

    kind = "x25"
    address_pattern = r"\d{6,14}"

    def wrap(self, sender: str, recipient: str, body: str) -> Frame:
        # Virtual-circuit framing: channel id prefixes the payload.
        channel = abs(hash((sender, recipient))) % 4096
        return Frame(
            transport=self.kind,
            sender_addr=sender,
            recipient_addr=recipient,
            payload=f"VC{channel:04d}:{body}",
        )

    def unwrap(self, frame: Frame) -> Tuple[str, str, str]:
        self._require(frame)
        payload = frame.payload
        body = (
            payload.split(":", 1)[1]
            if payload.startswith("VC") and ":" in payload
            else payload
        )
        return frame.sender_addr, frame.recipient_addr, body

    def _check(self, *addrs: str) -> None:
        for addr in addrs:
            if not self.valid_address(addr):
                raise ValueError(f"not an X.25 address: {addr!r}")

    def _require(self, frame: Frame) -> None:
        if frame.transport != self.kind:
            raise ValueError(f"not an X.25 frame: {frame.transport!r}")


class ArpanetTransport(Transport):
    """ARPANET style: host/user addresses with an NCP-ish header."""

    kind = "arpanet"
    address_pattern = r"[a-zA-Z][\w.-]*@[a-zA-Z][\w.-]*"

    def wrap(self, sender: str, recipient: str, body: str) -> Frame:
        return Frame(
            transport=self.kind,
            sender_addr=sender,
            recipient_addr=recipient,
            payload=f"NCP 1.0 {sender}>{recipient}\r\n{body}",
        )

    def unwrap(self, frame: Frame) -> Tuple[str, str, str]:
        self._require(frame)
        payload = frame.payload
        body = payload.split("\r\n", 1)[1] if "\r\n" in payload else payload
        return frame.sender_addr, frame.recipient_addr, body

    def _check(self, *addrs: str) -> None:
        for addr in addrs:
            if not self.valid_address(addr):
                raise ValueError(f"not an ARPANET address: {addr!r}")

    def _require(self, frame: Frame) -> None:
        if frame.transport != self.kind:
            raise ValueError(f"not an ARPANET frame: {frame.transport!r}")


@dataclass
class DirectoryEntry:
    name: str
    address: str
    transport: str


class WhitePages:
    """The name-server directory: names -> (address, transport)."""

    def __init__(self) -> None:
        self._entries: Dict[str, DirectoryEntry] = {}

    def register(self, name: str, address: str, transport: str) -> None:
        if name in self._entries:
            raise ValueError(f"name {name!r} already registered")
        self._entries[name] = DirectoryEntry(
            name=name, address=address, transport=transport
        )

    def lookup(self, name: str) -> DirectoryEntry:
        try:
            return self._entries[name]
        except KeyError:
            raise KeyError(f"no white-pages entry for {name!r}") from None

    def __len__(self) -> int:
        return len(self._entries)


@dataclass
class Delivered:
    recipient: str
    sender: str
    body: str
    via: Tuple[str, str]  # (sender transport, recipient transport)


class Gateway:
    """Routes between heterogeneous transports via the common envelope."""

    def __init__(self, directory: WhitePages) -> None:
        self._directory = directory
        self._transports: Dict[str, Transport] = {}
        self._mailboxes: Dict[str, List[Delivered]] = {}

    def attach_transport(self, transport: Transport) -> None:
        self._transports[transport.kind] = transport

    def send(self, from_name: str, to_name: str, body: str) -> Delivered:
        src = self._directory.lookup(from_name)
        dst = self._directory.lookup(to_name)
        if src.transport not in self._transports:
            raise KeyError(f"no adapter attached for {src.transport!r}")
        if dst.transport not in self._transports:
            raise KeyError(f"no adapter attached for {dst.transport!r}")
        tx_out = self._transports[src.transport]
        tx_in = self._transports[dst.transport]
        if not tx_out.valid_address(src.address):
            raise ValueError(f"bad {src.transport} address: {src.address!r}")
        if not tx_in.valid_address(dst.address):
            raise ValueError(f"bad {dst.transport} address: {dst.address!r}")
        # Edge adapter: common envelope -> sender's wire frame ...
        frame = tx_out.wrap(src.address, dst.address, body)
        sender_addr, recipient_addr, common_body = tx_out.unwrap(frame)
        # ... gateway re-wraps into the recipient's wire frame ...
        in_frame = tx_in.wrap(sender_addr, recipient_addr, common_body)
        s_addr, r_addr, final_body = tx_in.unwrap(in_frame)
        delivered = Delivered(
            recipient=to_name,
            sender=from_name,
            body=final_body,
            via=(src.transport, dst.transport),
        )
        self._mailboxes.setdefault(to_name, []).append(delivered)
        return delivered

    def mailbox(self, name: str) -> List[Delivered]:
        return list(self._mailboxes.get(name, []))


ORIGIN = "levi-revival/csnet"
