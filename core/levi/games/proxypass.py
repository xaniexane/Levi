"""Proxypass — the Nintendo 3DS StreetPass revival (``levi.games.proxypass``).

The dead mechanism: StreetPass (3DS, 2011). Two sleeping consoles passing
in the street traded Miis, game data, and achievements over local
wireless — no button pressed, no account, no server, no cost. When
Nintendo shut down ALL 3DS/Wii U online services on April 8, 2024,
StreetPass kept working: the shutdown-proof social feature is the one
that never trusted a server.

LEVI's clean-room port (no Nintendo/NetPass/Pretendo code or protocol):

- An **encounter envelope**: a signed, minimal, anonymous hello packet —
  the sender's chosen handle, a small game payload (a challenge, a
  growth note), a timestamp. Nothing else.
- The **transport is a local drop directory** (file drop, shared folder,
  USB sneakernet): ``drop()`` writes a packet file, ``collect()`` reads
  the ones addressed to nobody in particular.
- **Rate limits and blocklists from day one** — anonymity-by-design
  invites griefing, so the receiver enforces both.
- Encounters are **idempotent**: the same packet collected twice is one
  encounter.

Invariants (law -> guard -> prove; the tests are the proof):
1. Anonymous-by-design — a packet carries exactly what its sender chose
   to put in it (handle + payload + timestamps); no device id, no
   account, no ambient identity.
2. No silent forgery — signed packets are verified against the
   receiver's accepted keys; a bad signature is dropped, never
   delivered. Unsigned packets are dropped unless the receiver
   explicitly allows them (and are then flagged ``signed: False``).
3. Rate limits from day one — a handle that exceeds
   ``rate_limit`` encounters per ``window_seconds`` is throttled;
   excess packets are dropped and counted.
4. Blocklists from day one — blocked handles are dropped silently.
5. No cloud, no accounts — the drop directory is the whole network.
6. Idempotent — a packet id is never delivered twice; expired packets
   are dropped, not delivered late.

Honest limit: this is a local-first encounter channel for LEVI devices
(phone, Chromebook, VM) in the sync-storm environment — it is honest
about physics, like the original: sparse encounters where people are
sparse. It proves proximity, not identity.

Stdlib only.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

__all__ = [
    "ProxypassError",
    "Encounter",
    "CollectReport",
    "make_packet",
    "verify_packet",
    "drop",
    "collect",
]

PACKET_SCHEMA = "levi-proxypass/1"
_HANDLE_MAX = 32
_PAYLOAD_MAX = 4096  # bytes of canonical JSON — hello packets stay small
_SEEN_KEEP = 10000


class ProxypassError(Exception):
    """A packet was malformed or the drop directory unusable."""


def _canonical(packet: Dict) -> bytes:
    body = {k: packet[k] for k in sorted(packet) if k != "tag"}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sign(body: bytes, key: str) -> str:
    return hmac.new(key.encode("utf-8"), body, hashlib.sha256).hexdigest()


def make_packet(
    handle: str,
    payload: Dict,
    key: Optional[str] = None,
    ttl_seconds: int = 86400,
    now: Optional[float] = None,
) -> Dict:
    """Build an encounter envelope.

    ``handle`` is the sender's *chosen* name (<= 32 chars) — the only
    identity the packet carries. ``payload`` is a small JSON-able
    document (a game challenge, a growth note). ``key`` is the shared
    circle key; without it the packet is unsigned.
    """
    handle = (handle or "").strip()
    if not handle or len(handle) > _HANDLE_MAX:
        raise ProxypassError("handle required, max %d chars" % _HANDLE_MAX)
    try:
        payload_json = json.dumps(payload, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ProxypassError("payload must be JSON-able (%s)" % exc) from exc
    if len(payload_json.encode("utf-8")) > _PAYLOAD_MAX:
        raise ProxypassError(
            "payload too large (%d > %d bytes) — hello packets stay small"
            % (len(payload_json.encode("utf-8")), _PAYLOAD_MAX)
        )
    if ttl_seconds <= 0:
        raise ProxypassError("ttl_seconds must be positive")
    ts = int(now if now is not None else time.time())
    packet = {
        "schema": PACKET_SCHEMA,
        "packet_id": uuid.uuid4().hex,
        "handle": handle,
        "payload": payload,
        "created_ts": ts,
        "expires_ts": ts + int(ttl_seconds),
    }
    packet["tag"] = _sign(_canonical(packet), key) if key else None
    return packet


def verify_packet(packet: Dict, keys: Sequence[str]) -> Tuple[bool, str]:
    """Check a packet's signature. Returns ``(ok, reason)``.

    Unsigned packets report ``(False, "unsigned")`` — the caller decides
    whether unsigned is acceptable.
    """
    if not isinstance(packet, dict) or packet.get("schema") != PACKET_SCHEMA:
        return False, "bad schema"
    tag = packet.get("tag")
    if not tag:
        return False, "unsigned"
    body = _canonical(packet)
    for key in keys:
        if hmac.compare_digest(_sign(body, key), tag):
            return True, "signed"
    return False, "bad signature"


@dataclass
class Encounter:
    packet_id: str
    handle: str
    payload: Dict
    received_ts: int
    signed: bool


@dataclass
class CollectReport:
    encounters: List[Encounter] = field(default_factory=list)
    dropped: int = 0
    throttled: int = 0
    blocked: int = 0
    expired: int = 0
    bad_signature: int = 0


def _seen_path(dropdir: Path) -> Path:
    return dropdir / ".proxypass-seen.json"


def _load_seen(dropdir: Path) -> Set[str]:
    try:
        raw = json.loads(_seen_path(dropdir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return set(raw) if isinstance(raw, list) else set()


def _save_seen(dropdir: Path, seen: Set[str]) -> None:
    trimmed = sorted(seen)[-_SEEN_KEEP:]
    tmp = dropdir / ".proxypass-seen.json.tmp"
    tmp.write_text(json.dumps(trimmed), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(_seen_path(dropdir))


def _rate_path(dropdir: Path) -> Path:
    return dropdir / ".proxypass-rates.json"


def drop(packet: Dict, dropdir: Path) -> Path:
    """Leave an encounter envelope in the drop directory."""
    if not isinstance(packet, dict) or packet.get("schema") != PACKET_SCHEMA:
        raise ProxypassError("not a proxypass packet")
    dropdir = Path(dropdir)
    dropdir.mkdir(parents=True, exist_ok=True)
    name = "pkt-%s.json" % packet.get("packet_id", uuid.uuid4().hex)
    # The packet id is hex from make_packet; foreign files are read but
    # never executed — still, keep the filename inert.
    safe = "".join(c for c in name if c.isalnum() or c in "-_.")
    target = dropdir / (safe or "pkt.json")
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(packet, sort_keys=True), encoding="utf-8")
    tmp.replace(target)
    return target


def collect(
    dropdir: Path,
    keys: Sequence[str] = (),
    allow_unsigned: bool = False,
    blocklist: Sequence[str] = (),
    rate_limit: int = 10,
    window_seconds: int = 3600,
    now: Optional[float] = None,
) -> CollectReport:
    """Collect encounter envelopes from the drop directory.

    Applies, in order: expiry, blocklist, signature, idempotency, rate
    limit. Returns the encounters plus a count of everything dropped
    and why.
    """
    dropdir = Path(dropdir)
    report = CollectReport()
    if not dropdir.is_dir():
        return report
    ts = int(now if now is not None else time.time())
    blocked = set(blocklist)
    seen = _load_seen(dropdir)
    new_seen = set(seen)

    # Per-handle encounter timestamps inside the window, persisted so
    # the rate limit survives across collect() calls.
    try:
        rates = json.loads(_rate_path(dropdir).read_text(encoding="utf-8"))
        if not isinstance(rates, dict):
            rates = {}
    except (OSError, ValueError):
        rates = {}

    for path in sorted(dropdir.glob("pkt-*.json")):
        try:
            packet = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            report.dropped += 1
            continue
        pid = packet.get("packet_id") if isinstance(packet, dict) else None

        if not isinstance(packet, dict) or not pid:
            report.dropped += 1
            continue
        if ts > int(packet.get("expires_ts", 0)):
            report.expired += 1
            # Expired packets are never deliverable by any receiver, so
            # the drop directory is allowed to forget them.
            try:
                path.unlink()
            except OSError:
                pass
            continue
        handle = str(packet.get("handle", ""))
        if handle in blocked:
            report.blocked += 1
            continue
        ok, reason = verify_packet(packet, keys)
        if not ok:
            if reason == "unsigned" and allow_unsigned:
                signed = False
            else:
                report.bad_signature += 1
                continue
        else:
            signed = True
        if pid in seen:
            continue  # idempotent: already delivered
        stamps = [s for s in rates.get(handle, []) if ts - int(s) < window_seconds]
        if len(stamps) >= rate_limit:
            report.throttled += 1
            continue
        stamps.append(ts)
        rates[handle] = stamps
        new_seen.add(pid)
        report.encounters.append(
            Encounter(
                packet_id=pid,
                handle=handle,
                payload=packet.get("payload") or {},
                received_ts=ts,
                signed=signed,
            )
        )

    _save_seen(dropdir, new_seen)
    try:
        tmp = dropdir / ".proxypass-rates.json.tmp"
        tmp.write_text(json.dumps(rates), encoding="utf-8")
        tmp.replace(_rate_path(dropdir))
    except OSError:
        pass
    return report
