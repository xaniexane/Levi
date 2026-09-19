# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Vaultkeeper releases — reproducible builds, deltas, the platform cut.

Three tools, one trust boundary:

- **Release manifests** bind a source tree's hash to its artifact's
  hash: a build is reproducible only when the same sources reproduce
  the same artifact bytes, and the manifest proves it.
- **Delta planner** computes minimal changed-chunk lists between two
  artifact versions so updates ship as deltas; apply_delta
  reconstructs the new bytes exactly, verifying every supplied chunk
  against its recorded hash — a corrupt or swapped chunk fails, never
  a silently-wrong artifact.
- **Platform cut**: paid apps on day one, 12% flat in integer cents,
  the remainder going to the developer. Fail-closed: non-integers,
  negatives, and zero all raise instead of paying wrong.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Tuple

from levi.dynasty.dna import AgentError

__all__ = [
    "ReleaseError",
    "CutError",
    "PLATFORM_CUT_PERCENT",
    "create_release",
    "verify_reproducible",
    "plan_delta",
    "apply_delta",
    "platform_cut",
]


class ReleaseError(AgentError):
    """A release manifest was malformed or failed reproducible
    verification — the artifact cannot be trusted."""


class CutError(AgentError):
    """A payment amount was refused: not an integer, zero, or
    negative. Fail-closed means wrong money never moves."""


#: Flat platform cut, percent.
PLATFORM_CUT_PERCENT = 12

#: Default delta chunk size in bytes.
DEFAULT_CHUNK_SIZE = 4096


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _check_source_files(source_files: Dict[str, bytes]) -> Dict[str, bytes]:
    if not isinstance(source_files, dict) or not source_files:
        raise ReleaseError("source_files must be a non-empty dict of path -> bytes")
    clean: Dict[str, bytes] = {}
    for path, content in source_files.items():
        if not isinstance(path, str) or not path.strip():
            raise ReleaseError("source paths must be non-empty strings")
        if not isinstance(content, (bytes, bytearray)):
            raise ReleaseError(
                f"source file {path!r} must be bytes, got {type(content).__name__}"
            )
        clean[path.strip()] = bytes(content)
    return clean


def _check_artifact(artifact: Any) -> bytes:
    if not isinstance(artifact, (bytes, bytearray)):
        raise ReleaseError(f"artifact must be bytes, got {type(artifact).__name__}")
    return bytes(artifact)


def _tree_hash(clean: Dict[str, bytes]) -> Dict[str, str]:
    """Bind the source tree: each file's hash, then one hash over the
    sorted (path, length, file-hash) bindings. Two different trees
    can never share a tree hash."""
    file_hashes = {path: _sha256(clean[path]) for path in clean}
    bind = b"".join(
        path.encode("utf-8")
        + b"\x00"
        + str(len(clean[path])).encode("ascii")
        + b"\x00"
        + file_hashes[path].encode("ascii")
        for path in sorted(file_hashes)
    )
    return file_hashes, _sha256(bind)


def create_release(source_files: Dict[str, bytes], artifact: bytes) -> Dict[str, Any]:
    """Build a release manifest binding the source-tree hash to the
    artifact hash. Raises :class:`ReleaseError` on malformed inputs."""
    clean = _check_source_files(source_files)
    blob = _check_artifact(artifact)
    file_hashes, tree = _tree_hash(clean)
    return {
        "kind": "levi-release",
        "file_count": len(clean),
        "source_tree_sha256": tree,
        "files": file_hashes,
        "artifact_sha256": _sha256(blob),
        "artifact_len": len(blob),
    }


def verify_reproducible(
    manifest: Dict[str, Any], source_files: Dict[str, bytes], artifact: bytes
) -> bool:
    """True only when the same sources reproduce the same artifact:
    both hashes recomputed and both matching the manifest. Never
    raises on a mismatch — a non-reproducible build simply fails."""
    if not isinstance(manifest, dict):
        raise ReleaseError("manifest must be a dict")
    clean = _check_source_files(source_files)
    blob = _check_artifact(artifact)
    file_hashes, tree = _tree_hash(clean)
    return (
        manifest.get("kind") == "levi-release"
        and manifest.get("source_tree_sha256") == tree
        and manifest.get("artifact_sha256") == _sha256(blob)
        and manifest.get("artifact_len") == len(blob)
        and manifest.get("files") == file_hashes
    )


def _check_chunk_size(chunk_size: int) -> int:
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int):
        raise ReleaseError("chunk_size must be an int")
    if chunk_size <= 0:
        raise ReleaseError("chunk_size must be positive")
    return chunk_size


def _chunks(data: bytes, chunk_size: int) -> List[bytes]:
    return [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]


def plan_delta(
    old: bytes, new: bytes, chunk_size: int = DEFAULT_CHUNK_SIZE
) -> List[Dict[str, Any]]:
    """Plan a delta: the changed chunk indexes plus each changed
    chunk's sha256. Unchanged chunks are never shipped. A chunk
    dropped by truncation gets an entry with an empty sha256 —
    :func:`apply_delta` treats it as a removal."""
    if not isinstance(old, (bytes, bytearray)) or not isinstance(
        new, (bytes, bytearray)
    ):
        raise ReleaseError("plan_delta needs bytes for old and new")
    chunk_size = _check_chunk_size(chunk_size)
    old, new = bytes(old), bytes(new)
    old_chunks, new_chunks = _chunks(old, chunk_size), _chunks(new, chunk_size)
    plan: List[Dict[str, Any]] = []
    for i in range(max(len(old_chunks), len(new_chunks))):
        a = old_chunks[i] if i < len(old_chunks) else None
        b = new_chunks[i] if i < len(new_chunks) else None
        if a != b:
            plan.append({"index": i, "sha256": _sha256(b) if b is not None else ""})
    return plan


def apply_delta(
    old: bytes,
    plan: List[Dict[str, Any]],
    chunks: Dict[int, bytes],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> bytes:
    """Reconstruct ``new`` from ``old`` + the delta plan + changed
    chunk bytes. ``chunk_size`` must match the value used in
    :func:`plan_delta` (default 4096 on both sides).

    Every supplied chunk is hash-checked against the plan before
    placement: corrupt, swapped, or missing chunks raise
    :class:`ReleaseError` instead of yielding a wrong artifact. An
    empty plan returns ``old`` unchanged.
    """
    if not isinstance(old, (bytes, bytearray)):
        raise ReleaseError("apply_delta needs bytes for old")
    if not isinstance(plan, list):
        raise ReleaseError("apply_delta needs a plan list")
    if not isinstance(chunks, dict):
        raise ReleaseError("apply_delta needs a chunks dict")
    old = bytes(old)

    plan_indexes: List[int] = []
    for entry in plan:
        if not isinstance(entry, dict):
            raise ReleaseError("delta plan entries must be dicts")
        idx, digest = entry.get("index"), entry.get("sha256")
        if isinstance(idx, bool) or not isinstance(idx, int) or idx < 0:
            raise ReleaseError(
                f"delta plan index must be a non-negative int, got {idx!r}"
            )
        if not isinstance(digest, str) or (digest != "" and len(digest) != 64):
            raise ReleaseError(f"delta plan chunk {idx} has a bad sha256")
        plan_indexes.append(idx)

    # the changed chunk bytes, hash-verified against the plan.
    # an entry with an empty sha256 is a removal: the new artifact
    # simply has no chunk there — no bytes are supplied.
    placed: Dict[int, bytes] = {}
    removed: set = set()
    for entry in plan:
        idx = entry["index"]
        if entry["sha256"] == "":
            removed.add(idx)
            continue
        if idx not in chunks:
            raise ReleaseError(f"delta plan chunk {idx} was not supplied")
        data = chunks[idx]
        if not isinstance(data, (bytes, bytearray)):
            raise ReleaseError(f"delta chunk {idx} must be bytes")
        data = bytes(data)
        if _sha256(data) != entry["sha256"]:
            raise ReleaseError(f"delta chunk {idx} failed hash verification — corrupt")
        placed[idx] = data

    # any supplied chunk not referenced by the plan is stray
    stray = set(chunks) - set(plan_indexes)
    if stray:
        raise ReleaseError(f"stray delta chunks not in plan: {sorted(stray)}")

    # assemble: walk new's chunk indexes in order. Removal entries
    # contribute nothing; anything past the last plan index matches
    # old only when new is at least as long as old — a truncation
    # lists every dropped chunk as a removal, so the walk ending at
    # the last plan index is exact.
    chunk_size = _check_chunk_size(chunk_size)
    if not plan:
        return old  # identical artifacts: nothing to apply
    grid = _chunks(old, chunk_size)
    last = max(plan_indexes) if plan_indexes else -1
    out = bytearray()
    for i in range(last + 1):
        if i in removed:
            continue
        if i in placed:
            out += placed[i]
        elif i < len(grid):
            out += grid[i]
        else:
            raise ReleaseError(
                f"delta plan chunk {i} missing — no old chunk, no supplied chunk"
            )
    return bytes(out)


def platform_cut(amount_cents: int) -> Tuple[int, int]:
    """The 12% platform cut on a paid app, in integer cents.

    Returns (platform_cents, developer_cents): platform = floor(12%
    of amount), developer = the rest — the remainder always goes to
    the developer. Fail-closed: non-integers (including bools),
    zero, and negatives raise :class:`CutError` — wrong money never
    moves.
    """
    if isinstance(amount_cents, bool) or not isinstance(amount_cents, int):
        raise CutError(
            f"amount must be an int number of cents, got {type(amount_cents).__name__}"
        )
    if amount_cents <= 0:
        raise CutError(f"amount must be positive cents, got {amount_cents}")
    platform = (amount_cents * PLATFORM_CUT_PERCENT) // 100
    return platform, amount_cents - platform
