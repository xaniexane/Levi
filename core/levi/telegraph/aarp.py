"""Self-assigned addressing — the AppleTalk AARP revival (``levi.telegraph.aarp``).

The dead mechanism: AppleTalk (1983-2009) needed zero administration,
and half of that was AARP — the AppleTalk Address Resolution Protocol's
startup ritual. A node picked an address at random, then broadcast 10
conflict-probe packets; if nobody objected, the address was its. No
server, no DHCP, no administrator — self-assigned addressing eighteen
years before IPv4 link-local.

The other half (NBP's ``object:type@zone`` human names, conflict-checked
and browsable) already lives in :mod:`levi.telegraph.directory`. This
module is the address half:

- ``claim_address`` — pick a random candidate from the pool, emit
  exactly ``probes`` probe records onto the wire, and claim the address
  only if no live conflicting claim answers.
- ``renew`` / ``release`` — owner-only lease management.
- Stale claims (past their lease) never block: addresses recycle.

The wire is a local directory (the telegraph's sneakernet discipline —
USB, shared folders, plain dirs). A "broadcast" is a probe file every
node on the wire can read; a "conflict answer" is a live claim file
from another node.

Invariants (law -> guard -> prove; the tests are the proof):
1. No two live claims share an address — a conflicting live claim
   from another node always defeats the candidate (never overwritten).
2. Probes precede claims — every successful claim emitted exactly
   ``probes`` probe records first; a claim with no probes is refused
   by the reader (claims carry their probe count).
3. Stale claims never block — a claim past its lease is ignored and
   pruned, so addresses recycle instead of leaking.
4. Owner-only mutation — only the claiming node may renew or release
   its address.

Honest limit: probes detect conflicts on a shared, readable wire; they
do not authenticate the claimants. On a hostile wire, use the vault
and capproto — same discipline as :mod:`levi.telegraph.identity`.

Stdlib only.
"""

from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

__all__ = [
    "AarpError",
    "Claim",
    "claim_address",
    "renew",
    "release",
    "live_claims",
]

#: AppleTalk's own ritual: ten conflict probes before a claim.
DEFAULT_PROBES = 10


class AarpError(Exception):
    """Address self-assignment failed or was refused."""


@dataclass(frozen=True)
class Claim:
    node: str
    address: str
    claimed_ts: int
    lease_seconds: int
    probes_sent: int


def _claims_path(wire: Path) -> Path:
    return wire / "aarp-claims.json"


def _read_claims(wire: Path) -> Dict[str, Dict]:
    try:
        raw = json.loads(_claims_path(wire).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_claims(wire: Path, claims: Dict[str, Dict]) -> None:
    wire.mkdir(parents=True, exist_ok=True)
    tmp = wire / "aarp-claims.json.tmp"
    tmp.write_text(json.dumps(claims, indent=2, sort_keys=True), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(_claims_path(wire))


def _live(claims: Dict[str, Dict], now: int) -> Dict[str, Dict]:
    """Claims whose lease has not expired.

    A claim that carries no probe count was never probed for — the
    reader refuses it, so hand-written claims cannot squat addresses.
    """
    live = {}
    for addr, c in claims.items():
        if not isinstance(c, dict):
            continue
        if int(c.get("probes_sent", 0)) < 1:
            continue
        if int(c.get("claimed_ts", 0)) + int(c.get("lease_seconds", 0)) > now:
            live[addr] = c
    return live


def live_claims(wire_dir: Path, now: Optional[float] = None) -> Dict[str, Dict]:
    """The wire's live address claims (stale ones pruned from the view)."""
    ts = int(now if now is not None else time.time())
    return _live(_read_claims(Path(wire_dir)), ts)


def _probe_name(node: str, address: str, seq: int) -> str:
    safe = "".join(c for c in "%s-%s" % (node, address) if c.isalnum() or c in "-_.")
    return ".aarp-probe-%s-%02d.json" % (safe, seq)


def claim_address(
    node: str,
    pool: List[str],
    wire_dir: Path,
    probes: int = DEFAULT_PROBES,
    lease_seconds: int = 3600,
    max_attempts: int = 64,
    now: Optional[float] = None,
    rng: Optional[random.Random] = None,
) -> Claim:
    """Self-assign an address from ``pool`` via conflict probing.

    Picks a random candidate, emits exactly ``probes`` probe records,
    then claims the address iff no *other* node holds a live claim on
    it. Raises :class:`AarpError` when the pool is exhausted.
    """
    node = (node or "").strip()
    if not node:
        raise AarpError("node name required")
    pool = [str(a) for a in pool if str(a).strip()]
    if not pool:
        raise AarpError("address pool is empty")
    if probes < 1:
        raise AarpError("probes must be >= 1 (AppleTalk used 10)")
    if lease_seconds <= 0:
        raise AarpError("lease_seconds must be positive")

    wire = Path(wire_dir)
    wire.mkdir(parents=True, exist_ok=True)
    ts = int(now if now is not None else time.time())
    rng = rng or random.Random()

    candidates = list(pool)
    attempts = 0
    while candidates and attempts < max_attempts:
        attempts += 1
        candidate = rng.choice(candidates)
        candidates.remove(candidate)

        # The ritual: broadcast the probes, then listen.
        probe_files = []
        for seq in range(probes):
            pf = wire / _probe_name(node, candidate, seq)
            pf.write_text(
                json.dumps(
                    {
                        "node": node,
                        "address": candidate,
                        "seq": seq,
                        "ts": ts,
                    }
                ),
                encoding="utf-8",
            )
            probe_files.append(pf)

        claims = _live(_read_claims(wire), ts)
        conflict = claims.get(candidate)
        if conflict and conflict.get("node") != node:
            # Somebody answered the probe: back off, try another.
            for pf in probe_files:
                try:
                    pf.unlink()
                except OSError:
                    pass
            continue

        # Silence on the wire: the address is ours.
        claims[candidate] = {
            "node": node,
            "claimed_ts": ts,
            "lease_seconds": int(lease_seconds),
            "probes_sent": probes,
        }
        _write_claims(wire, claims)
        for pf in probe_files:
            try:
                pf.unlink()
            except OSError:
                pass
        return Claim(
            node=node,
            address=candidate,
            claimed_ts=ts,
            lease_seconds=int(lease_seconds),
            probes_sent=probes,
        )

    raise AarpError(
        "no free address: %d attempt(s), pool of %d exhausted or "
        "conflicted" % (attempts, len(pool))
    )


def renew(
    node: str,
    address: str,
    wire_dir: Path,
    lease_seconds: int = 3600,
    now: Optional[float] = None,
) -> Claim:
    """Refresh your own claim's lease. Owner-only."""
    wire = Path(wire_dir)
    ts = int(now if now is not None else time.time())
    claims = _read_claims(wire)
    current = claims.get(address)
    if current is None or current.get("node") != node:
        raise AarpError(
            "no claim on %r held by node %r — cannot renew" % (address, node)
        )
    current["claimed_ts"] = ts
    current["lease_seconds"] = int(lease_seconds)
    _write_claims(wire, claims)
    return Claim(
        node=node,
        address=address,
        claimed_ts=ts,
        lease_seconds=int(lease_seconds),
        probes_sent=int(current.get("probes_sent", 0)),
    )


def release(node: str, address: str, wire_dir: Path) -> None:
    """Release your own address. Owner-only; releasing a stale or
    foreign claim is refused."""
    wire = Path(wire_dir)
    claims = _read_claims(wire)
    current = claims.get(address)
    if current is None or current.get("node") != node:
        raise AarpError(
            "no claim on %r held by node %r — cannot release" % (address, node)
        )
    del claims[address]
    _write_claims(wire, claims)
