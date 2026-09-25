"""Image persistence (A7 salvage: Smalltalk's image, without its death).
WORKING TITLE — naming is Chauncey's, never canon.

A content-addressed, versioned image of the organism's state — snapshots
plus an append-only changes journal — giving crash-proof checkpoints and
byte-exact snapshot-resume. Every image is a file tree, every journal
entry is plain JSON: more transparent than files, not an opaque blob.

- :mod:`.hashing` — sha256 over canonical JSON.
- :mod:`.cycle`   — local cycle stub: the journal's sequence clock until
  the middle team pins the real cycle protocol.
- :mod:`.store`   — :class:`ImageStore`: ``snapshot`` / ``checkpoint`` /
  ``resume`` / ``diff`` / ``verify_chain``, retention-bounded storage.

Module contract: a module registers ``state_view() -> dict`` (JSON-able)
and ``restore_view(dict) -> None``. The image layer serializes, hashes,
and journals; modules never manage their own persistence.

Time discipline: no wall-clock in logic. Journal entries and checkpoint
records carry the logical cycle clock; wall-clock timestamps appear only
inside receipts (and tests never depend on them).

Laws: stdlib-only (hashlib + json); zero network at runtime;
deterministic; no sentience or subjective-experience claims (an image is
a checkpoint, not a soul).
"""

from .cycle import CycleClock
from .hashing import canonical, hash_json, sha256_hex
from .store import ImageRefusal, ImageStore

__all__ = [
    "CycleClock",
    "ImageRefusal",
    "ImageStore",
    "canonical",
    "hash_json",
    "sha256_hex",
]
