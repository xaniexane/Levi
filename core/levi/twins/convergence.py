"""Convergence — the three Ones, the creator seed, and the sealed map.

The lattice is camouflage: many agents, daemons, and shells. The truth is
three Ones — the All-in-One Agent, the All-in-One Daemon, the All-in-One
OS Shell — into which every twin converges.

"Can't be reproduced": the true arrangement (camouflage order, live vs
shadow roles, jitter) is *derived* from a creator seed by a deterministic
shuffle. Without the seed the map cannot be regenerated or verified; with
it — held by the creator alone — ``converge`` rebuilds the truth exactly.
Tampering is caught by an HMAC-SHA256 seal (stdlib ``hmac``); the seed
itself lives in a 0600 file the creator backs up.

No pretend crypto: the seal is real HMAC, the seed is real randomness,
and the docstring says exactly what each guarantees.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from typing import Dict, Iterator, List, Optional

from levi.twins.lattice import TwinLattice
from levi.twins.twin import Twin, twin_id_for

#: The three Ones, by the kind that converges into each.
ONE_KINDS = ("agent", "daemon", "shell")


def one_id_for(kind: str) -> str:
    return twin_id_for("one", kind, "fg")


def ensure_ones(lattice: TwinLattice) -> Dict[str, Twin]:
    """Register the three Ones. Each One is its own twin — no counterpart."""
    ones: Dict[str, Twin] = {}
    for kind in ONE_KINDS:
        tid = one_id_for(kind)
        tw = lattice.get(tid)
        if tw is None:
            tw = lattice.register(
                "one",
                kind,
                "fg",
                state={"members": [], "kind": kind},
                notes="the All-in-One — every twin of this kind converges here",
                pair_id=tid,  # the One pairs with itself
            )
        ones[kind] = tw
    return ones


# -- the creator seed ----------------------------------------------------
def seed_path(lattice: TwinLattice) -> str:
    return os.path.join(lattice.home, "seed")


def ensure_seed(lattice: TwinLattice) -> str:
    """Create the creator seed once (256-bit hex, 0600). Stable after.

    If a seed file exists but is corrupt, raises — the creator restores
    from backup; we never silently mint a second truth.
    """
    path = seed_path(lattice)
    if os.path.exists(path):
        seed = _read_seed_text(lattice)
        if seed is None:
            raise RuntimeError(
                f"seed file {path} exists but is corrupt; "
                "restore it from the creator backup"
            )
        return seed
    seed = secrets.token_hex(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(seed)
    except BaseException:
        os.close(fd)
        raise
    return seed


def _read_seed_text(lattice: TwinLattice) -> Optional[str]:
    """Read the seed file without ever crashing.

    Returns the stripped hex string, or None if the file is missing,
    unreadable, not UTF-8, or not valid seed hex. A corrupt seed is a
    failed verification, never an exception.
    """
    path = seed_path(lattice)
    try:
        with open(path, "rb") as fh:
            raw = fh.read().strip()
        text = raw.decode("utf-8").strip()
        bytes.fromhex(text)  # validates hex
        if len(text) != 64:
            return None
        return text
    except (OSError, UnicodeDecodeError, ValueError):
        return None


def load_seed(lattice: TwinLattice) -> Optional[str]:
    return _read_seed_text(lattice)


def seed_fingerprint(seed_hex: str) -> str:
    return hashlib.sha256(seed_hex.encode()).hexdigest()[:16]


# -- seeded camouflage derivation ----------------------------------------
def _prng(seed: bytes, generation: int = 0) -> Iterator[int]:
    """Counter-mode SHA-256 byte stream. Deterministic, seed-bound.

    The generation mixes into the stream: each shedding of the skin
    (each mutate) re-derives a new arrangement from the same creator
    seed. Same seed + same members + same generation always yields the
    same arrangement; anything else yields another.
    """
    counter = 0
    material = seed + b"|g" + str(generation).encode("ascii")
    while True:
        counter += 1
        digest = hashlib.sha256(material + counter.to_bytes(8, "big")).digest()
        yield from digest


def _take_int(stream: Iterator[int], n: int) -> int:
    raw = bytes(next(stream) for _ in range(4))
    return int.from_bytes(raw, "big") % n


def derive_camouflage(
    seed_hex: str, member_ids: List[str], generation: int = 0
) -> Dict[str, object]:
    """Deterministically arrange members from the creator seed.

    Fisher-Yates shuffle over the member ids, plus a live/shadow role and
    a heartbeat-jitter value per member. Same seed + same members + same
    generation always yields the same arrangement; any other seed yields
    another. Each mutate advances the generation: the lattice sheds its
    skin, but the creator can always reproduce every skin.
    """
    seed = bytes.fromhex(seed_hex)
    stream = _prng(seed, generation)
    order = sorted(member_ids)
    for i in range(len(order) - 1, 0, -1):
        j = _take_int(stream, i + 1)
        order[i], order[j] = order[j], order[i]
    roles = {tid: ("live" if _take_int(stream, 2) == 0 else "shadow") for tid in order}
    jitter_ms = {tid: _take_int(stream, 5000) for tid in order}
    return {
        "seed_fp": seed_fingerprint(seed_hex),
        "generation": generation,
        "order": order,
        "roles": roles,
        "jitter_ms": jitter_ms,
    }


def _canonical(payload: Dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def seal_camouflage(
    lattice: TwinLattice, seed_hex: Optional[str] = None, generation: int = 0
) -> Twin:
    """Derive the arrangement from the seed and store it HMAC-sealed."""
    seed = seed_hex or ensure_seed(lattice)
    members = [t.twin_id for t in lattice.iter_all() if t.kind in ONE_KINDS]
    cmap = derive_camouflage(seed, members, generation)
    tag = hmac.new(bytes.fromhex(seed), _canonical(cmap), hashlib.sha256).hexdigest()
    return lattice.register(
        "seal",
        "camouflage",
        "fg",
        state={
            "map": cmap,
            "hmac": tag,
            "members": len(members),
            "generation": generation,
        },
        notes="creator-sealed camouflage arrangement; verify with the seed",
    )


def current_generation(lattice: TwinLattice) -> int:
    """The generation of the currently sealed arrangement (0 if unsealed)."""
    tw = lattice.get(twin_id_for("seal", "camouflage", "fg"))
    if tw is None:
        return 0
    gen = tw.state.get("generation", 0)
    return gen if isinstance(gen, int) and gen >= 0 else 0


def verify_camouflage(lattice: TwinLattice, seed_hex: Optional[str] = None) -> bool:
    """Re-derive the arrangement from the seed and compare it whole.

    False — never an exception — when: the seed is missing/corrupt/wrong,
    the seal twin is missing, the stored map differs from a fresh
    derivation (tampered map, or members changed without re-converging),
    or the HMAC does not match. True only for the creator's exact,
    current arrangement.
    """
    seed = seed_hex or load_seed(lattice)
    if seed is None:
        return False
    try:
        key = bytes.fromhex(seed)
    except ValueError:
        return False
    tw = lattice.get(twin_id_for("seal", "camouflage", "fg"))
    if tw is None:
        return False
    stored_map = tw.state.get("map")
    tag = tw.state.get("hmac")
    if not isinstance(stored_map, dict) or not isinstance(tag, str):
        return False
    current = derive_camouflage(
        seed,
        [t.twin_id for t in lattice.iter_all() if t.kind in ONE_KINDS],
        current_generation(lattice),
    )
    if _canonical(current) != _canonical(stored_map):
        return False
    expect = hmac.new(key, _canonical(stored_map), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expect, tag)


# -- convergence ----------------------------------------------------------
def converge(
    lattice: TwinLattice,
    seed_hex: Optional[str] = None,
    generation: Optional[int] = None,
) -> Dict[str, object]:
    """Rebuild the truth from the creator seed: every twin → its One.

    Ensures the three Ones, attaches each kind's member list to its One,
    seals (or re-seals) the camouflage map, and reports whether the seal
    verifies. Only reproducible with the creator seed. ``generation``
    defaults to the currently sealed generation — plain converge never
    sheds the skin; only mutate advances it.
    """
    seed = seed_hex or ensure_seed(lattice)
    if generation is None:
        generation = current_generation(lattice)
    ones = ensure_ones(lattice)
    members: Dict[str, List[str]] = {}
    for kind in ONE_KINDS:
        ids = [t.twin_id for t in lattice.list(kind=kind)]
        members[kind] = ids
        lattice.heartbeat(ones[kind].twin_id, {"members": ids})
    seal_camouflage(lattice, seed, generation)
    return {
        "ones": {k: ones[k].twin_id for k in ONE_KINDS},
        "member_counts": {k: len(v) for k, v in members.items()},
        "sealed": verify_camouflage(lattice, seed),
        "seed_fp": seed_fingerprint(seed),
        "generation": generation,
    }
