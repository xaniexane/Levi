"""Open-protocol federation: where the code lives becomes a non-question.

Studied from: github-pattern-hunt-20260916-0018/report.md [Ranked additions 6]

The mechanism: federation is a documented protocol, not a platform.
``FederationNode`` instances speak a versioned JSON envelope protocol
(``describe_protocol`` returns the spec as data), negotiate a common
protocol version on ``handshake``, register each other as remotes, and
``replicate`` ref maps — repo name to head commit — between nodes.
Fast-forward updates apply automatically; diverged refs are flagged for a
human instead of being force-resolved.

Design notes, kept honest:

- This module defines and implements the protocol in-process; it performs
  no network I/O. A transport can carry the envelopes produced by
  ``make_envelope`` and parsed by ``read_envelope`` — the sync rules are
  identical either way.
- "Monopoly-minus-one" is a property of the protocol being open and
  documented, not of this code alone: any node implementing the spec can
  join. ``describe_protocol`` exists so the spec travels with the code.
- Diverged refs are never auto-merged. The audit log records every
  handshake, replication, and divergence for inspection.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/open-federation"

PROTOCOL_NAME = "levi-forge-sync"
SUPPORTED_VERSIONS = (1, 2)


@dataclass
class Envelope:
    """One protocol message: versioned, typed, JSON-serializable."""

    version: int
    kind: str  # hello | refs | refs-request
    payload: Dict
    sent_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(
            {
                "protocol": PROTOCOL_NAME,
                "version": self.version,
                "kind": self.kind,
                "payload": self.payload,
                "sent_at": self.sent_at,
            },
            sort_keys=True,
        )

    @staticmethod
    def from_json(text: str) -> "Envelope":
        doc = json.loads(text)
        if doc.get("protocol") != PROTOCOL_NAME:
            raise ValueError(f"not a {PROTOCOL_NAME} envelope")
        return Envelope(
            version=doc["version"],
            kind=doc["kind"],
            payload=doc["payload"],
            sent_at=doc.get("sent_at", 0.0),
        )


@dataclass
class AuditEntry:
    at: float
    event: str  # handshake | replicate | divergence | register
    detail: str


class FederationNode:
    """One participant in the federation: refs, remotes, and sync rules."""

    def __init__(self, node_id: str, versions: Tuple[int, ...] = SUPPORTED_VERSIONS):
        self.node_id = node_id
        self.versions = tuple(versions)
        self.refs: Dict[str, str] = {}  # repo -> head sha
        self.remotes: Dict[str, "FederationNode"] = {}
        self.negotiated: Dict[str, int] = {}  # remote id -> protocol version
        self.audit: List[AuditEntry] = []
        self._chains: Dict[str, List[str]] = {}  # repo -> commit shas in order

    # -- the documented protocol -----------------------------------------
    @staticmethod
    def describe_protocol() -> Dict:
        """The spec, as data: anyone implementing this can federate."""
        return {
            "protocol": PROTOCOL_NAME,
            "versions": list(SUPPORTED_VERSIONS),
            "envelope": {
                "fields": ["protocol", "version", "kind", "payload", "sent_at"]
            },
            "message_kinds": {
                "hello": "announce node_id + supported versions; reply with negotiated version",
                "refs": "map of repo -> head sha",
                "refs-request": "ask a remote for its current refs",
            },
            "replication_rules": [
                "unknown repo on one side: copy the ref (fast-forward)",
                "same repo, equal heads: nothing to do",
                "same repo, one head is an ancestor of the other: fast-forward to the newer",
                "same repo, neither is an ancestor: DIVERGED — flag, never auto-merge",
            ],
            "ancestry_note": (
                "Ancestry is judged by the commit chains each node holds "
                "(see track_commits). Without shared history, any two "
                "different heads are treated as diverged."
            ),
        }

    def track_commits(self, repo: str, shas_in_order: List[str]) -> None:
        """Record a repo's commit chain so ancestry (and fast-forward) is decidable."""
        self._chains.setdefault(repo, [])
        for sha in shas_in_order:
            if sha not in self._chains[repo]:
                self._chains[repo].append(sha)

    # -- handshake + registry ---------------------------------------------
    def handshake(self, peer: "FederationNode") -> int:
        """Negotiate the highest mutually supported version; register the peer."""
        common = sorted(set(self.versions) & set(peer.versions), reverse=True)
        if not common:
            raise ValueError(
                f"no common protocol version: {self.node_id} has {self.versions}, "
                f"{peer.node_id} has {peer.versions}"
            )
        version = common[0]
        self.negotiated[peer.node_id] = version
        peer.negotiated[self.node_id] = version
        self.remotes[peer.node_id] = peer
        peer.remotes[self.node_id] = self
        self._log("handshake", f"{peer.node_id} negotiated v{version}")
        peer._log("handshake", f"{self.node_id} negotiated v{version}")
        return version

    def make_envelope(
        self, kind: str, payload: Dict, version: int | None = None
    ) -> str:
        return Envelope(
            version=version or max(self.versions), kind=kind, payload=payload
        ).to_json()

    def read_envelope(self, text: str) -> Envelope:
        env = Envelope.from_json(text)
        if env.version not in self.versions:
            raise ValueError(f"unsupported protocol version {env.version}")
        return env

    # -- replication -------------------------------------------------------
    def replicate(self, remote_id: str) -> Dict[str, object]:
        """Exchange refs with a registered remote and converge what converges.

        Symmetric: after a replicate, both nodes fast-forward every ref that
        has a clear newer head. Diverged refs are flagged on both sides and
        left alone — a human resolves those, never the protocol.
        """
        peer = self.remotes.get(remote_id)
        if peer is None:
            raise KeyError(f"unknown remote {remote_id!r}; handshake first")
        fast_forwarded: List[str] = []
        diverged: List[str] = []
        already: List[str] = []

        for repo in sorted(set(self.refs) | set(peer.refs)):
            mine = self.refs.get(repo)
            theirs = peer.refs.get(repo)
            if mine is None:
                self.refs[repo] = theirs  # type: ignore[assignment]
                fast_forwarded.append(repo)
            elif theirs is None:
                peer.refs[repo] = mine
                fast_forwarded.append(repo)
            elif mine == theirs:
                already.append(repo)
            elif self._knows_newer(repo, mine, theirs):
                self.refs[repo] = theirs  # type: ignore[assignment]
                fast_forwarded.append(repo)
            elif self._knows_newer_on(peer, repo, theirs, mine):
                peer.refs[repo] = mine
                fast_forwarded.append(repo)
            else:
                diverged.append(repo)
                self._log(
                    "divergence", f"{repo}: mine {mine[:8]} vs theirs {theirs[:8]}"
                )
                peer._log(
                    "divergence", f"{repo}: mine {mine[:8]} vs theirs {theirs[:8]}"
                )

        self._log(
            "replicate",
            f"{remote_id}: {len(fast_forwarded)} fast-forwarded, "
            f"{len(diverged)} diverged, {len(already)} already current",
        )
        return {
            "remote": remote_id,
            "fast_forwarded": fast_forwarded,
            "diverged": diverged,
            "already_current": already,
        }

    def set_ref(self, repo: str, head: str) -> None:
        self.refs[repo] = head

    # -- internals ----------------------------------------------------------
    def _log(self, event: str, detail: str) -> None:
        self.audit.append(AuditEntry(at=time.time(), event=event, detail=detail))

    def _knows_newer(self, repo: str, maybe_ancestor: str, head: str) -> bool:
        """True if my chains show ``head`` descends from ``maybe_ancestor``."""
        chain = self._chains.get(repo, [])
        return (
            maybe_ancestor in chain
            and head in chain
            and chain.index(maybe_ancestor) < chain.index(head)
        )

    def _knows_newer_on(
        self, peer: "FederationNode", repo: str, their_head: str, my_head: str
    ) -> bool:
        """True if the peer's chains show my head descends from theirs."""
        chain = peer._chains.get(repo, [])
        return (
            their_head in chain
            and my_head in chain
            and chain.index(their_head) < chain.index(my_head)
        )
