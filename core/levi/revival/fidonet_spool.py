"""FidoNet-style spool: the nightly Zone Mail Hour.

Studied from: protocols-hunt-20260916-0041/report.md [Find 1 - FidoNet]

The studied shape: pure offline networking. Each node keeps an
outbound spool per destination. Once a night, during the Zone Mail
Hour, the node dials each destination from its nodelist, bundles that
destination's waiting mail into packets, exchanges them, and hangs up.
Two mail flavors: netmail (private, one recipient) and echomail
(public, fanned out to every node carrying the echo area).

LEVI-native re-expression: a nodelist (address -> dial string),
per-destination outbound spools, packet bundling with a header, and a
`mail_hour()` exchange between two nodes that swaps outbound bundles
for every mutual destination and routes echomail into echo areas.
Zone Mail Hour is a method call here, not 3 a.m. — the discipline
(bundle → dial → exchange → file) is the mechanism.

Honest limits: "dialing" is a nodelist lookup, not a modem; the phone
network is two objects calling each other; echomail fan-out is to
nodes the exchange knows about, not a routed flood.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


ORIGIN = "levi-revival/fidonet-spool"


@dataclass
class NodeEntry:
    address: str  # e.g. "1:2/3"
    dial: str
    name: str = ""


@dataclass
class Mail:
    msg_id: str
    sender: str
    recipient: str  # node address for netmail, echo tag for echomail
    subject: str
    body: str
    echomail: bool = False


@dataclass
class BundlePacket:
    """What crosses the wire in one exchange: header + the mail."""

    sender_node: str
    dest_node: str
    mails: List[Mail] = field(default_factory=list)

    def summary(self) -> str:
        kinds = [("echo" if m.echomail else "net") for m in self.mails]
        return f"{self.sender_node}->{self.dest_node}: {len(self.mails)} ({','.join(kinds)})"


class FidoNode:
    """One store-and-forward node with an outbound spool and echo areas."""

    def __init__(self, address: str) -> None:
        self.address = address
        self.nodelist: Dict[str, NodeEntry] = {}
        # outbound spool: destination node address -> waiting mail
        self.spool: Dict[str, List[Mail]] = {}
        self.inbox: List[Mail] = []  # arrived netmail
        self.echo_areas: Dict[str, List[Mail]] = {}  # echo tag -> arrived echomail
        self.carried_echoes: List[str] = []
        self._seq = 0
        self.log: List[str] = []

    def add_nodelist(self, entry: NodeEntry) -> None:
        self.nodelist[entry.address] = entry

    def carry(self, echo_tag: str) -> None:
        if echo_tag not in self.carried_echoes:
            self.carried_echoes.append(echo_tag)
            self.echo_areas.setdefault(echo_tag, [])

    def write_netmail(self, dest_node: str, subject: str, body: str) -> Mail:
        self._seq += 1
        mail = Mail(
            msg_id=f"{self.address}#{self._seq}",
            sender=self.address,
            recipient=dest_node,
            subject=subject,
            body=body,
        )
        self.spool.setdefault(dest_node, []).append(mail)
        return mail

    def write_echomail(self, echo_tag: str, subject: str, body: str) -> Mail:
        self._seq += 1
        mail = Mail(
            msg_id=f"{self.address}#{self._seq}",
            sender=self.address,
            recipient=echo_tag,
            subject=subject,
            body=body,
            echomail=True,
        )
        self.echo_areas.setdefault(echo_tag, []).append(mail)  # local copy
        # fan out to every nodelist node carrying this echo
        for addr in self.nodelist:
            if addr in self._carriers_of(echo_tag):
                self.spool.setdefault(addr, []).append(mail)
        return mail

    def _carriers_of(self, echo_tag: str) -> List[str]:
        # In this model, the node's own knowledge of carriers: every node
        # in its nodelist is assumed to carry echoes this node carries,
        # except itself. Conservative fan-out keeps the simulation honest.
        return [a for a in self.nodelist if a != self.address]

    def bundle_for(self, dest_node: str) -> BundlePacket:
        mails = self.spool.pop(dest_node, [])
        return BundlePacket(sender_node=self.address, dest_node=dest_node, mails=mails)

    def receive(self, packet: BundlePacket) -> None:
        for mail in packet.mails:
            if mail.echomail:
                self.echo_areas.setdefault(mail.recipient, []).append(mail)
                # transit: re-spool to onward carriers (store-and-forward)
                for addr in self._carriers_of(mail.recipient):
                    if addr != packet.sender_node:
                        self.spool.setdefault(addr, []).append(mail)
            else:
                if mail.recipient == self.address:
                    self.inbox.append(mail)
                else:
                    # not for us: hold for onward routing next mail hour
                    self.spool.setdefault(mail.recipient, []).append(mail)
        self.log.append(f"received {packet.summary()}")

    def dial(self, dest_node: str) -> str:
        entry = self.nodelist.get(dest_node)
        if entry is None:
            raise KeyError(f"no nodelist entry for {dest_node!r}")
        return entry.dial

    def mail_hour(self, peer: "FidoNode") -> List[str]:
        """The nightly exchange: dial the peer, swap bundles, file them.

        Returns a log of what happened this hour.
        """
        events: List[str] = []
        dial_string = self.dial(peer.address)
        events.append(f"dial {peer.address} via {dial_string}")
        out_packet = self.bundle_for(peer.address)
        in_packet = peer.bundle_for(self.address)
        events.append(f"send {out_packet.summary()}")
        events.append(f"recv {in_packet.summary()}")
        self.receive(in_packet)
        peer.receive(out_packet)
        return events

    def spool_depth(self) -> Dict[str, int]:
        return {dest: len(mails) for dest, mails in self.spool.items() if mails}
