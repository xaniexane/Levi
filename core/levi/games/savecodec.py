"""Save codec — progress as a carry-anywhere string (the password-save revival).

The dead ritual: 8/16-bit password saves (Mega Man 2's 5x5 dot grid,
Castlevania's alphanumeric codes). No battery, no server, no account:
progress encoded as a short human-readable string the player could write
on paper, dictate over the phone, or print in a magazine. The password
IS the progress, portable across consoles, cities, decades.

This is the LEVI-native remix, built clean-room from the pattern, not
any original algorithm. Any game state serializes to a printable string:

    MANC-FX7Q-2RKD-9PLM

with a CRC-16 trailer. It sits on top of games/saves.py (the file-based
player-owned save) as the *portable layer*: export a slot to a string,
import a string to a slot.

Honest by design, like the originals:
- LOSSY: it encodes declared milestones (bosses beaten, items held),
  never a full snapshot. It says so in the envelope.
- CHECKSUM IS CORRUPTION-EVIDENCE, not anti-cheat. A mistyped letter
  is caught and reported; a deliberately forged code is a feature,
  not an attack. (Tamper-evidence chains are relay.py's job.)
- No account, no network, no revocation path. The player holds the
  only copy, so nothing can be taken away or subscription-walled.

stdlib only.
"""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any, Dict

SCHEMA = 1
_CHUNK = 4  # readability grouping, like the old grids
_SEP = "-"


class SaveCodecError(Exception):
    """A code that cannot be read — corrupt, mistyped, or foreign."""


class _Usage(Exception):
    """Missing CLI argument; message already printed."""


def _crc16(data: bytes) -> int:
    """CRC-16/CCITT-FALSE. Corruption evidence, not a secret."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _check_game_id(game_id: str) -> str:
    safe = "".join(c for c in game_id if c.isalnum() or c in "-_")
    if not safe or safe != game_id or len(game_id) > 64:
        raise SaveCodecError(
            "game_id must be 1-64 chars of [a-zA-Z0-9-_], got %r" % (game_id,)
        )
    return game_id


def encode(game_id: str, milestones: Dict[str, Any], schema: int = SCHEMA) -> str:
    """Encode declared milestones to a portable string.

    milestones must be JSON-serializable (keep them small: the old
    grids held 24-25 bits, not whole worlds). schema is an integer
    the game bumps when its milestone set changes shape.
    """
    game_id = _check_game_id(game_id)
    if not isinstance(schema, int) or schema < 0:
        raise SaveCodecError("schema must be a non-negative int")
    if not isinstance(milestones, dict):
        raise SaveCodecError("milestones must be a dict")
    try:
        payload = json.dumps(
            {
                "levi_save_code": schema,
                "game": game_id,
                "milestones": milestones,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise SaveCodecError("milestones are not JSON-serializable: %s" % exc)
    blob = payload + _crc16(payload).to_bytes(2, "big")
    b32 = base64.b32encode(blob).decode("ascii").rstrip("=")
    chunks = [b32[i : i + _CHUNK] for i in range(0, len(b32), _CHUNK)]
    return _SEP.join(chunks)


def decode(code: str, expected_game: str | None = None) -> Dict[str, Any]:
    """Decode a portable string back to its envelope.

    Raises SaveCodecError on mistyped/corrupt/foreign codes. If
    expected_game is given, a code for another game is refused.
    Returns {"game": ..., "schema": ..., "milestones": ...}.
    """
    raw = "".join(code.split()).upper().replace(_SEP, "")
    if not raw or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for c in raw):
        raise SaveCodecError(
            "not a save code: use only A-Z and 2-7, e.g. MANC-FX7Q-2RKD"
        )
    pad = "=" * (-len(raw) % 8)
    try:
        blob = base64.b32decode(raw + pad)
    except (binascii.Error, ValueError):
        raise SaveCodecError("not a save code: undecodable characters")
    if len(blob) < 3:
        raise SaveCodecError("not a save code: too short to hold a payload")
    payload, trailer = blob[:-2], int.from_bytes(blob[-2:], "big")
    if _crc16(payload) != trailer:
        raise SaveCodecError(
            "checksum mismatch — a letter was mistyped. "
            "Re-check the code; nothing was decoded."
        )
    try:
        envelope = json.loads(payload.decode("ascii"))
    except (UnicodeDecodeError, ValueError):
        raise SaveCodecError("not a save code: payload is not a save envelope")
    if not isinstance(envelope, dict) or "levi_save_code" not in envelope:
        raise SaveCodecError("not a save code: foreign envelope")
    game = envelope.get("game")
    if expected_game is not None and game != expected_game:
        raise SaveCodecError(
            "this code belongs to game %r, not %r" % (game, expected_game)
        )
    return {
        "game": game,
        "schema": envelope["levi_save_code"],
        "milestones": envelope.get("milestones", {}),
    }


def describe(code: str) -> str:
    """One-line human summary of a code, or the honest failure reason."""
    try:
        env = decode(code)
    except SaveCodecError as exc:
        return "unreadable: %s" % exc
    ms = env["milestones"]
    n = len(ms) if isinstance(ms, dict) else 0
    return "game %r, schema %d, %d milestone(s), checksum OK" % (
        env["game"],
        env["schema"],
        n,
    )


def cmd(args) -> int:
    """argparse entry: code <encode|decode|describe|export-string|import-string> ..."""
    from levi.games.saves import SaveStore, SaveError

    def need(value, what):
        if not value:
            print("code error: %s is required" % what)
            raise _Usage
        return value

    try:
        if args.action == "encode":
            game = need(args.p1, "game")
            milestones = json.loads(args.p2 or "{}")
            print(encode(game, milestones))
        elif args.action == "decode":
            code = need(args.p1, "code")
            env = decode(code, expected_game=args.game)
            print(json.dumps(env, indent=2, sort_keys=True))
        elif args.action == "describe":
            print(describe(need(args.p1, "code")))
        elif args.action == "export-string":
            store = SaveStore()
            game, slot = need(args.p1, "game"), need(args.p2, "slot")
            state = store.load(game, slot)
            print(encode(game, state))
            print("(slot %r exported as a carry-anywhere string)" % slot)
        elif args.action == "import-string":
            store = SaveStore()
            game, slot = need(args.p1, "game"), need(args.p2, "slot")
            env = decode(need(args.p3, "code"), expected_game=game)
            store.save(game, slot, env["milestones"])
            print("imported as %s slot %r" % (game, slot))
        else:
            print("unknown code action %r" % args.action)
            return 2
    except _Usage:
        return 2
    except SaveCodecError as exc:
        print("code error: %s" % exc)
        return 1
    except SaveError as exc:
        print("save error: %s" % exc)
        return 1
    except ValueError as exc:
        print("bad JSON: %s" % exc)
        return 1
    return 0
