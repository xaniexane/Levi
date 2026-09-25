"""revival/xmpp_federation.py — open server-to-server federation.

Studied from: dead-networks-20260916 (report.md [Google Talk]).

Revival of: the XMPP server-to-server federation model — any server
worldwide could federate with users on any other server with no prior
agreement, growing the network through openness.

Why it matters: federation is a growth strategy, not just a protocol. When
joining requires no permission, the network's value compounds with every new
server, because every new server's users can reach everyone. The honest
counterpart built here is the open half of that pattern: federate freely,
verify identity, route across domains.

LEVI adaptation:
- ``XmppServer``: hosts local users; keeps rosters (who may message whom)
  and presence state.
- ``FederationDirectory``: maps a domain to its authoritative server
  object — the dialback-style identity check: a server claiming a domain
  must BE the registered server for that domain, or the link is refused.
- ``federate(a, b)``: opens a server-to-server link with no agreement step;
  either side can initiate.
- ``send_message()``: local delivery when both JIDs share a domain,
  cross-server routing when federated; spoofed or unfederated destinations
  are refused with explicit errors.
- Presence propagates across open links to subscribed contacts.

Honest limits:
- Dialback is modeled, not implemented: the directory stands in for DNS +
  a challenge exchange. It proves the shape (claim must match the
  registered authority), not the cryptography.
- In-process only; no XML streams, no TLS. Roster checks are per-server
  allow-lists, not subscription handshakes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class Stanza:
    kind: str  # "message" | "presence"
    from_jid: str
    to_jid: str
    body: str = ""
    at: float = field(default_factory=time.time)


def _domain_of(jid: str) -> str:
    if "@" not in jid:
        raise ValueError(f"not a JID: {jid!r}")
    return jid.split("@", 1)[1]


class FederationError(Exception):
    pass


class FederationDirectory:
    """Authoritative map of domain -> server. The dialback-style trust root."""

    def __init__(self) -> None:
        self._servers: Dict[str, "XmppServer"] = {}

    def register(self, server: "XmppServer") -> None:
        if server.domain in self._servers:
            raise ValueError(f"domain {server.domain!r} already registered")
        self._servers[server.domain] = server

    def authoritative(self, domain: str) -> Optional["XmppServer"]:
        return self._servers.get(domain)


class XmppServer:
    """One federated chat server with local users, rosters, and presence."""

    def __init__(self, domain: str, directory: FederationDirectory) -> None:
        if not domain:
            raise ValueError("domain must be non-empty")
        self.domain = domain
        self._directory = directory
        self.users: Set[str] = set()
        self.rosters: Dict[str, Set[str]] = {}
        self.presence: Dict[str, str] = {}
        self.inbox: Dict[str, List[Stanza]] = {}
        self.peers: Set[str] = set()  # federated domains
        self.refused = 0
        directory.register(self)

    def add_user(self, localpart: str) -> str:
        jid = f"{localpart}@{self.domain}"
        self.users.add(jid)
        self.rosters.setdefault(jid, set())
        self.inbox.setdefault(jid, [])
        self.presence[jid] = "offline"
        return jid

    def allow(self, jid: str, contact_jid: str) -> None:
        """Add contact_jid to jid's roster (may message / see presence)."""
        if jid not in self.users:
            raise KeyError(f"unknown local user: {jid!r}")
        self.rosters[jid].add(contact_jid)

    def federate(self, other_domain: str) -> None:
        """Open a server-to-server link. No agreement required — but the
        other end must genuinely be the authority for its domain."""
        peer = self._directory.authoritative(other_domain)
        if peer is None:
            raise FederationError(f"no authoritative server for {other_domain!r}")
        if peer.domain != other_domain:
            raise FederationError(f"domain claim mismatch for {other_domain!r}")
        self.peers.add(other_domain)

    def send_message(self, from_jid: str, to_jid: str, body: str) -> Stanza:
        from_domain = _domain_of(from_jid)
        to_domain = _domain_of(to_jid)
        if from_domain != self.domain:
            raise FederationError(f"{from_jid!r} is not local to {self.domain!r}")
        if to_jid not in self.users and to_jid not in self.rosters.get(from_jid, set()):
            raise FederationError(f"{to_jid!r} not in {from_jid!r}'s roster")
        stanza = Stanza(kind="message", from_jid=from_jid, to_jid=to_jid, body=body)
        if to_domain == self.domain:
            if to_jid not in self.users:
                raise FederationError(f"unknown local user: {to_jid!r}")
            self.inbox[to_jid].append(stanza)
            return stanza
        # Cross-server: the receiving end verifies us (dialback shape).
        peer = self._directory.authoritative(to_domain)
        if peer is None or to_domain not in self.peers:
            raise FederationError(f"no open federation with {to_domain!r}")
        peer._receive_remote(stanza, claiming_server=self)
        return stanza

    def _receive_remote(self, stanza: Stanza, claiming_server: "XmppServer") -> None:
        claimed = _domain_of(stanza.from_jid)
        authority = self._directory.authoritative(claimed)
        if authority is not claiming_server:
            self.refused += 1
            raise FederationError(f"spoofed sender domain: {claimed!r}")
        if stanza.to_jid not in self.users:
            raise FederationError(f"unknown local user: {stanza.to_jid!r}")
        self.inbox[stanza.to_jid].append(stanza)

    def set_presence(self, jid: str, status: str) -> None:
        if jid not in self.users:
            raise KeyError(f"unknown local user: {jid!r}")
        self.presence[jid] = status
        # Propagate to every federated peer holding a rostered contact.
        for peer_domain in self.peers:
            peer = self._directory.authoritative(peer_domain)
            if peer is None:
                continue
            for contact, roster in peer.rosters.items():
                if jid in roster:
                    note = Stanza(
                        kind="presence", from_jid=jid, to_jid=contact, body=status
                    )
                    peer.inbox[contact].append(note)

    def messages_for(self, jid: str) -> List[Stanza]:
        return [s for s in self.inbox.get(jid, []) if s.kind == "message"]

    def presence_notes_for(self, jid: str) -> List[Stanza]:
        return [s for s in self.inbox.get(jid, []) if s.kind == "presence"]


ORIGIN = "levi-revival/xmpp-federation"
