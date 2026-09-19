"""revival/tosser_scanner.py — local conference bundling for networked exchange.

Studied from: dead-networks-20260916 (report.md [FidoNet echomail social culture]).

Revival of: the FidoNet echomail tosser/scanner pair — the transport fabric
that moved BBS forum traffic across the network.

Why it matters: a BBS is a local island — users post in local conferences.
The scanner watches the local areas and bundles new local messages into
outbound packets for the network uplink; the tosser unpacks inbound packets
and files each message into its matching local area. The BBS software itself
never speaks the network protocol — the tosser/scanner pair is the adapter
between the local board and the wide-area net.

LEVI adaptation:
- ``EchoArea``: a local message store keyed by conference name.
- ``Scanner.scan(node)``: gathers messages posted since the last scan
  watermark in every area and builds an outbound ``Bundle`` addressed to the
  uplink.
- ``Tosser.toss(node, bundle)``: unpacks an inbound bundle, files each message
  into its local area, tracks SEEN-BY lines to avoid routing loops, and drops
  duplicates by message id.
- Loop safety: a message already seen by this node is not re-filed or
  re-forwarded; a duplicate delivery is dropped silently.

Honest limits:
- In-process only; no dialing, no packet archive formats. The "network" is a
  function call between node objects.
- Dupe detection is keyed on sender-supplied message ids; a peer that reuses
  ids can collide. SEEN-BY loop protection assumes honest peers.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class EchoMessage:
    msgid: str
    area: str
    from_user: str
    subject: str
    body: str
    seen_by: Set[str] = field(default_factory=set)
    at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.msgid:
            raise ValueError("msgid must be non-empty")
        if not self.area:
            raise ValueError("area must be non-empty")

    def stamp(self, node_address: str) -> "EchoMessage":
        """Return a copy with this node's address added to SEEN-BY."""
        return EchoMessage(
            msgid=self.msgid,
            area=self.area,
            from_user=self.from_user,
            subject=self.subject,
            body=self.body,
            seen_by=set(self.seen_by) | {node_address},
            at=self.at,
        )


@dataclass
class Bundle:
    """A packet of messages moving from one node to another."""

    sender: str
    recipient: str
    messages: List[EchoMessage] = field(default_factory=list)


class EchoArea:
    """One local conference: an ordered store of filed messages."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.messages: List[EchoMessage] = []

    def file(self, message: EchoMessage) -> None:
        self.messages.append(message)

    def __len__(self) -> int:
        return len(self.messages)


class EchoNode:
    """A BBS-style node: local areas plus scan/toss state."""

    def __init__(self, address: str) -> None:
        if not address:
            raise ValueError("address must be non-empty")
        self.address = address
        self.areas: Dict[str, EchoArea] = {}
        self._scan_watermarks: Dict[str, int] = {}
        self._seen_msgids: Set[str] = set()

    def create_area(self, name: str) -> EchoArea:
        if name in self.areas:
            raise ValueError(f"area {name!r} already exists")
        area = EchoArea(name)
        self.areas[name] = area
        self._scan_watermarks.setdefault(name, 0)
        return area

    def post_local(
        self,
        area: str,
        from_user: str,
        subject: str,
        body: str,
        msgid: Optional[str] = None,
    ) -> EchoMessage:
        """Post a message written by a local user."""
        if area not in self.areas:
            raise KeyError(f"no such area: {area!r}")
        mid = msgid or f"{self.address}:{len(self.areas[area])}:{int(time.time())}"
        message = EchoMessage(
            msgid=mid, area=area, from_user=from_user, subject=subject, body=body
        )
        self.areas[area].file(message)
        return message

    def has_seen_msgid(self, msgid: str) -> bool:
        return msgid in self._seen_msgids

    def mark_msgid(self, msgid: str) -> None:
        self._seen_msgids.add(msgid)


class Scanner:
    """Bundles new local traffic into outbound packets for the uplink."""

    def scan(self, node: EchoNode, uplink: str) -> Bundle:
        """Collect messages posted since the last watermark in each area."""
        bundle = Bundle(sender=node.address, recipient=uplink)
        for area_name, area in node.areas.items():
            watermark = node._scan_watermarks.get(area_name, 0)
            new = area.messages[watermark:]
            bundle.messages.extend(m.stamp(node.address) for m in new)
            node._scan_watermarks[area_name] = len(area.messages)
        return bundle


class Tosser:
    """Unpacks inbound bundles and files messages into local areas."""

    def toss(self, node: EchoNode, bundle: Bundle) -> Tuple[int, int, int]:
        """File bundle messages. Returns (filed, duplicates_dropped, loops_skipped)."""
        filed = duplicates = loops = 0
        for message in bundle.messages:
            if node.has_seen_msgid(message.msgid):
                duplicates += 1
                continue
            if node.address in message.seen_by:
                # This node already handled it — a routing loop; do not re-file.
                loops += 1
                continue
            area = node.areas.get(message.area)
            if area is None:
                # Unknown area: file nowhere rather than inventing one.
                loops += 1
                continue
            area.file(message.stamp(node.address))
            node.mark_msgid(message.msgid)
            filed += 1
        return filed, duplicates, loops


ORIGIN = "levi-revival/tosser-scanner"
