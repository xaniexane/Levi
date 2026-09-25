"""Guest kits — the Nintendo DS Download Play revival (``levi.games.guestplay``).

The dead mechanism: Single-Card Play (Nintendo DS/DSi/3DS, 2004-2014).
The host console held the game card and *broadcast the game itself* over
local wireless; guest consoles received a temporary client that lived in
RAM — power off and it was gone, no license residue. The industry then
standardized the copy-per-player tax: every player buys the game, plus an
account, plus a subscription.

LEVI's clean-room port (no Nintendo protocol cloned, no network at all):

- The host bundles game rules + data + a session token into a signed
  **guest kit** (stdlib ``zipfile`` + ``hmac``).
- A guest opens the kit with the **token** into a **sandboxed session**
  directory. The token is the Bearer <redacted>; possession is the license.
- **Expiry is the clock**: an expired kit never opens.
- The guest's machine **keeps nothing afterward**: closing the session
  removes the session directory.

Invariants (law -> guard -> prove; the tests are the proof):
1. Possession is the license — the token opens the kit; no accounts,
   no network calls, nothing to phone home to.
2. Expiry is the clock — a kit past ``expires_ts`` is refused, always.
3. Tamper-evidence — the HMAC tag is verified *before* any byte of the
   payload is trusted; a wrong token or flipped byte is refused.
4. Sandboxed import — zip-slip guarded; extraction is confined to the
   session directory, which must be empty or absent.
5. No residue — ``GuestSession.close()`` removes the session directory.
6. Honest scope — a kit carries the host's stated rules/data, trimmed
   like the original Download Play clients; it is a guest session,
   not a copy of the game.

Stdlib only. Transport is a shared folder or file drop — the kit is just
bytes; how it moves is the players' business.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import secrets
import shutil
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

__all__ = [
    "GuestPlayError",
    "GuestSession",
    "build_kit",
    "open_kit",
    "KIT_SCHEMA",
]

KIT_SCHEMA = "levi-guest-kit/1"
_SEAL_INFO = b"levi-guestplay-seal-v1"
_TOKEN_BYTES = 24  # 192-bit Bearer <redacted>


class GuestPlayError(Exception):
    """A guest kit was refused: tampered, expired, or misused."""


def _seal_key(token: str) -> bytes:
    return hashlib.sha256(_SEAL_INFO + token.encode("ascii")).digest()


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text.encode("ascii"))


def build_kit(
    game_id: str,
    rules: Dict,
    data: Dict[str, bytes],
    ttl_seconds: int = 3600,
    now: Optional[float] = None,
) -> Tuple[bytes, str]:
    """Build a signed guest kit. Returns ``(kit_bytes, token)``.

    ``game_id`` names the game (e.g. ``"mancala"``), ``rules`` is the
    JSON-able rules document the guest will play by, and ``data`` maps
    archive names to file bytes. The token is the Bearer <redacted> — hand it
    to the guest out-of-band (read it aloud, write it down); the kit
    itself carries no key.
    """
    game_id = (game_id or "").strip()
    if not game_id:
        raise GuestPlayError("game_id required")
    if ttl_seconds <= 0:
        raise GuestPlayError("ttl_seconds must be positive")
    for name in data:
        if not name or name.startswith("/") or ".." in Path(name).parts:
            raise GuestPlayError("unsafe data name %r" % (name,))

    ts = int(now if now is not None else time.time())
    manifest = {
        "schema": KIT_SCHEMA,
        "kit_id": secrets.token_hex(8),
        "game_id": game_id,
        "rules": rules,
        "created_ts": ts,
        "expires_ts": ts + int(ttl_seconds),
        "files": sorted(data.keys()),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        for name in sorted(data.keys()):
            payload = data[name]
            if not isinstance(payload, (bytes, bytearray)):
                raise GuestPlayError("data[%r] must be bytes" % name)
            zf.writestr("data/" + name, bytes(payload))
    sealed = buf.getvalue()

    token = secrets.token_urlsafe(_TOKEN_BYTES)
    tag = hmac.new(_seal_key(token), sealed, hashlib.sha256).hexdigest()
    envelope = {
        "schema": KIT_SCHEMA,
        "sealed": _b64e(sealed),
        "tag": tag,
    }
    return json.dumps(envelope, sort_keys=True).encode("utf-8"), token


def _parse_envelope(kit_bytes: bytes) -> Tuple[bytes, str]:
    try:
        env = json.loads(kit_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise GuestPlayError("kit is not a guest kit (%s)" % exc) from exc
    if not isinstance(env, dict) or env.get("schema") != KIT_SCHEMA:
        raise GuestPlayError("kit is not a guest kit (bad schema)")
    try:
        sealed = _b64d(env["sealed"])
    except (KeyError, ValueError, base64.binascii.Error) as exc:
        raise GuestPlayError("kit payload unreadable (%s)" % exc) from exc
    tag = env.get("tag")
    if not isinstance(tag, str):
        raise GuestPlayError("kit carries no seal tag")
    return sealed, tag


@dataclass
class GuestSession:
    """An opened guest kit: sandboxed, temporary, residue-free."""

    game_id: str
    kit_id: str
    rules: Dict
    path: Path
    files: List[str] = field(default_factory=list)
    expires_ts: int = 0
    _closed: bool = field(default=False, repr=False)

    def read(self, name: str) -> bytes:
        """Read one kit file from the session directory."""
        if self._closed:
            raise GuestPlayError("session is closed")
        if name not in self.files:
            raise GuestPlayError("no such kit file %r" % name)
        target = self.path / "data" / name
        # Belt-and-suspenders: the name came from our own manifest, but
        # never trust a path without resolving it.
        if self.path not in target.resolve().parents:
            raise GuestPlayError("kit file escapes session %r" % name)
        return target.read_bytes()

    def close(self) -> None:
        """End the guest session. The machine keeps nothing afterward."""
        if not self._closed:
            self._closed = True
            shutil.rmtree(self.path, ignore_errors=True)

    def __enter__(self) -> "GuestSession":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def open_kit(
    kit_bytes: bytes,
    token: str,
    session_dir: Path,
    now: Optional[float] = None,
) -> GuestSession:
    """Open a guest kit into ``session_dir``. Verifies, then trusts.

    Raises :class:`GuestPlayError` when the seal is wrong (tampered kit
    or wrong token), the kit is expired, or the session directory is
    not empty/absent.
    """
    sealed, tag = _parse_envelope(kit_bytes)
    if not token:
        raise GuestPlayError("a token is required to open a guest kit")
    try:
        expected = hmac.new(
            _seal_key(token), sealed, hashlib.sha256
        ).hexdigest()
    except (ValueError, TypeError) as exc:
        raise GuestPlayError("unusable token (%s)" % exc) from exc
    if not hmac.compare_digest(expected, tag):
        raise GuestPlayError(
            "seal mismatch — kit tampered or wrong token; refused"
        )

    session_dir = Path(session_dir)
    if session_dir.exists() and any(session_dir.iterdir()):
        raise GuestPlayError(
            "session directory %s is not empty — refusing to unpack "
            "a guest kit over existing files" % session_dir
        )
    session_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(io.BytesIO(sealed)) as zf:
            # Zip-slip guard: every member must stay inside session_dir.
            for info in zf.infolist():
                target = (session_dir / info.filename).resolve()
                base = session_dir.resolve()
                if target != base and base not in target.parents:
                    raise GuestPlayError(
                        "kit member escapes session: %r" % info.filename
                    )
            zf.extractall(session_dir)
        manifest = json.loads(
            (session_dir / "manifest.json").read_text(encoding="utf-8")
        )
    except GuestPlayError:
        shutil.rmtree(session_dir, ignore_errors=True)
        raise
    except (zipfile.BadZipFile, ValueError, OSError) as exc:
        shutil.rmtree(session_dir, ignore_errors=True)
        raise GuestPlayError("kit payload corrupt (%s)" % exc) from exc

    ts = int(now if now is not None else time.time())
    if ts > int(manifest.get("expires_ts", 0)):
        shutil.rmtree(session_dir, ignore_errors=True)
        raise GuestPlayError("guest kit expired — the clock is the license")

    return GuestSession(
        game_id=str(manifest.get("game_id", "")),
        kit_id=str(manifest.get("kit_id", "")),
        rules=manifest.get("rules") or {},
        path=session_dir,
        files=[str(n) for n in manifest.get("files", [])],
        expires_ts=int(manifest.get("expires_ts", 0)),
    )
