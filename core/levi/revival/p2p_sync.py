"""p2p_sync — free encrypted-by-design P2P file sync, no central server.

Studied from: hybrid-cost-cutting-combos-20260916-0006/report.md
[§6 P2P].

Shape studied: Syncthing-style peer-to-peer file sync — encrypted
transport, no central server, no account, no fee; capacity is your own
disks, replacing paid sync tiers.

Mechanism (simulated in-process, no network):
* content addressing: files are split into fixed-size chunks, each
  chunk named by its SHA-256; a manifest lists the chunk hashes plus a
  root hash over them
* Peer: holds a chunk store; computes which chunks it is missing from a
  manifest (want list); receives chunks only after re-hashing them
  (tampered chunks are rejected)
* exchange(): two peers swap missing chunks bidirectionally
* sync_mesh(): run exchange rounds across a peer mesh until every peer
  holds the full manifest or the round budget is spent
* SyncReport: rounds used, bytes transferred, bytes saved by
  deduplication (identical chunks stored once)

Honest limits: the mesh is an in-process simulation of a
content-addressed piece-exchange protocol — it models the *accounting*
(hashes, dedup, transfer volumes), not real sockets, NAT traversal, or
encryption. Transport encryption is declared as a requirement of any
real deployment, not provided here.

This is an original, from-scratch implementation for LEVI.
Not artificial. Synthetic.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, List, Set

ORIGIN = "levi-revival/p2p_sync"

DEFAULT_CHUNK_SIZE = 4096


def hash_chunk(chunk: bytes) -> str:
    return hashlib.sha256(chunk).hexdigest()


def chunk_data(data: bytes, chunk_size: int = DEFAULT_CHUNK_SIZE) -> List[bytes]:
    """Split bytes into fixed-size chunks (last chunk may be short)."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")
    return [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)] or [b""]


@dataclass(frozen=True)
class Manifest:
    """Content address of a file: chunk hashes + root hash."""

    chunk_hashes: List[str]
    root: str
    total_bytes: int

    @property
    def unique_chunks(self) -> Set[str]:
        return set(self.chunk_hashes)


def make_manifest(data: bytes, chunk_size: int = DEFAULT_CHUNK_SIZE) -> Manifest:
    chunks = chunk_data(data, chunk_size)
    hashes = [hash_chunk(c) for c in chunks]
    root = hashlib.sha256("".join(hashes).encode("utf-8")).hexdigest()
    return Manifest(chunk_hashes=hashes, root=root, total_bytes=len(data))


def verify_manifest(manifest: Manifest, store: Dict[str, bytes]) -> bool:
    """True iff every chunk is present, intact, and the root matches."""
    try:
        joined = "".join(manifest.chunk_hashes)
    except TypeError:
        return False
    if hashlib.sha256(joined.encode("utf-8")).hexdigest() != manifest.root:
        return False
    return all(h in store and hash_chunk(store[h]) == h for h in manifest.chunk_hashes)


class Peer:
    """One node in the sync mesh, holding a content-addressed chunk store."""

    def __init__(self, peer_id: str):
        self.peer_id = peer_id
        self.store: Dict[str, bytes] = {}
        self.bytes_received = 0
        self.bytes_sent = 0
        self.rejected = 0

    def ingest(self, data: bytes, chunk_size: int = DEFAULT_CHUNK_SIZE) -> Manifest:
        """Chunk local data into the store; return its manifest."""
        manifest = make_manifest(data, chunk_size)
        for chunk, h in zip(
            chunk_data(data, chunk_size), manifest.chunk_hashes, strict=True
        ):
            self.store.setdefault(h, chunk)
        return manifest

    def want(self, manifest: Manifest) -> Set[str]:
        """Chunk hashes this peer still needs for ``manifest``."""
        return {h for h in manifest.unique_chunks if h not in self.store}

    def offer(self, hashes: Set[str]) -> Dict[str, bytes]:
        """Chunks this peer can supply, for a requester's want list."""
        supplied = {h: self.store[h] for h in hashes if h in self.store}
        self.bytes_sent += sum(len(c) for c in supplied.values())
        return supplied

    def receive(self, chunks: Dict[str, bytes]) -> int:
        """Accept chunks after re-hashing; return count accepted."""
        accepted = 0
        for h, chunk in chunks.items():
            if hash_chunk(chunk) == h:
                if h not in self.store:
                    self.store[h] = chunk
                    self.bytes_received += len(chunk)
                accepted += 1
            else:
                self.rejected += 1
        return accepted

    def exchange(self, other: "Peer", manifest: Manifest) -> int:
        """Bidirectional swap of missing chunks. Returns chunks accepted."""
        accepted = self.receive(other.offer(self.want(manifest)))
        accepted += other.receive(self.offer(other.want(manifest)))
        return accepted

    def has_all(self, manifest: Manifest) -> bool:
        return not self.want(manifest)


@dataclass
class SyncReport:
    rounds: int
    converged: bool
    bytes_transferred: int
    unique_bytes: int

    @property
    def dedup_saved_bytes(self) -> int:
        """Bytes not transferred twice thanks to content addressing."""
        return max(0, self.bytes_transferred - self.unique_bytes)


def sync_mesh(
    peers: List[Peer], manifest: Manifest, max_rounds: int = 64
) -> SyncReport:
    """Run exchange rounds until all peers hold the manifest or budget spent."""
    if not peers:
        raise ValueError("need at least one peer")
    rounds = 0
    while rounds < max_rounds:
        if all(p.has_all(manifest) for p in peers):
            break
        rounds += 1
        for i, peer in enumerate(peers):
            peer.exchange(peers[(i + 1) % len(peers)], manifest)
    transferred = sum(p.bytes_received for p in peers)
    # unique bytes = sum over distinct chunk hashes of their size
    seen: Set[str] = set()
    unique_bytes = 0
    for peer in peers:
        for h, chunk in peer.store.items():
            if h not in seen and h in manifest.unique_chunks:
                seen.add(h)
                unique_bytes += len(chunk)
    return SyncReport(
        rounds=rounds,
        converged=all(p.has_all(manifest) for p in peers),
        bytes_transferred=transferred,
        unique_bytes=unique_bytes,
    )
