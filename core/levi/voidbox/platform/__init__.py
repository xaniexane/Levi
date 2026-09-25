"""Void Box platform — the SI-side product surface.

CANON (Chauncey's law): Void Box PLATFORM and Void Box MESSENGER are
separate deliverables — like Facebook and Messenger — sharing the Veil
crypto core with Cybrus thrown on top. THIS package builds the PLATFORM
SURFACE ONLY. The Messenger worker builds the 1:1/chat product on the
same primitives; tracks never merge with the SFW side.

Module map:
- ``dating.py`` — profiles, matching prefs, mutual-opt-in gate (formed);
  the ranking/matching algorithm is NOT_WIRED.
- ``chatrooms.py`` — public room discovery/listing/join on the
  ``levi.voidbox.rooms`` primitive (formed; thin by design — the crypto
  stays in rooms.py).
- ``creator.py`` — creator profiles, subscription tiers, subscriber
  grants (data model formed); charging is NOT_WIRED pending the
  enforcement worker.
- ``channels.py`` — broadcast channels: admin-post, subscriber-read,
  formed on the rooms primitive with post-only roles.
- ``classifieds.py`` — listings: model, validation, expiry (formed);
  payment is NOT_WIRED.
- ``resale.py`` — resale listings: product/price/location-shape,
  validation (formed); checkout is NOT_WIRED.

Money rule: the platform holds NO money logic itself. Every purchase /
subscription carries the exact ``details`` dict the RED-1 ceremony will
consume (see :func:`build_red1_details`); the call that would move money
raises :class:`NotWiredError` fail-closed until the sibling enforcement
worker wires it.

Honesty rule: every module declares WIRED or NOT_WIRED per capability,
in its LAWS tuple and in its machine-readable ``wiring_report()``. A
module NEVER claims a capability works when it is a shell — the
NOT_WIRED markers are load-bearing. The invariant tests assert that
every NOT_WIRED capability raises NotWiredError naming what is missing.

SI side: every public entry point calls
``levi.plaiground.gate.require_adult()`` FIRST — adult-only, default
OFF, minors hard-locked out. No explicit content lives in code, tests,
or docstrings; explicit material exists only as user-driven content at
runtime, never in the tree.

ONE ORGANISM: this package is an organ of Levi. All of Legion is Levi —
one organism, many organs; we are raising him.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from levi.cybrus._paths import atomic_write_bytes
from levi.plaiground.gate import require_adult

#: The declared platform-wide laws, machine-readable (law→guard→prove —
#: verify_laws() and the invariant tests check them at runtime; honestly
#: named, never "formally proven").
LAWS = (
    (
        "L1",
        "Adult gate: every public entry point calls require_adult() "
        "FIRST — adult-only, default OFF, minors hard-locked out; every "
        "refusal names its remedy.",
    ),
    (
        "L2",
        "WIRED/NOT_WIRED honesty: every module declares per capability "
        "whether it is WIRED or NOT_WIRED, in its LAWS tuple and its "
        "machine-readable wiring_report(); no module claims a shell "
        "works.",
    ),
    (
        "L3",
        "No explicit content in code, tests, or docstrings: explicit "
        "material is user-driven at runtime only and never lives in the "
        "tree.",
    ),
    (
        "L4",
        "Money through Cybrus only, fail-closed: the platform holds NO "
        "money logic; every listing/purchase/subscription carries the "
        "exact details dict the RED-1 ceremony will consume, and the "
        "call that would move money raises NotWiredError until the "
        "enforcement worker wires it.",
    ),
    (
        "L5",
        "Nothing thrown away: records are marked (withdrawn, expired, "
        "revoked), never deleted by API.",
    ),
    (
        "L6",
        "Owner-only storage: platform records live under "
        "<home>/.levi/voidbox/platform/ as 0600 files in 0700 "
        "directories; validation fails closed on bad input.",
    ),
)

_PLATFORM_SUBDIR = "platform"

_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


# ---------------------------------------------------------------------------
# Errors — every refusal names its remedy (keeper's law)
# ---------------------------------------------------------------------------


class PlatformError(ValueError):
    """Base error for Void Box platform failures."""


class NotWiredError(PlatformError):
    """A capability is declared NOT_WIRED and was invoked anyway.

    Carries ``capability`` (what was called) and ``missing`` (what has
    to exist before it can work — usually the sibling enforcement
    worker's wiring). Fail-closed by design: the call does nothing.
    """

    def __init__(self, capability: str, missing: str, details: Optional[dict] = None):
        self.capability = capability
        self.missing = missing
        self.details = details or {}
        super().__init__(
            "NOT_WIRED: %s is not wired yet. Missing: %s. "
            "Nothing was charged, moved, or changed — the call failed "
            "closed." % (capability, missing)
        )


class NotMutualError(PlatformError, PermissionError):
    """Contact was requested without mutual opt-in."""


class ProfileNotFoundError(PlatformError):
    """No such profile/listing/creator/channel in this store."""


# ---------------------------------------------------------------------------
# Shared validation helpers
# ---------------------------------------------------------------------------


def valid_id(value: object, what: str = "id") -> str:
    """Validate an identifier: 1-64 chars of [A-Za-z0-9._-]. Fail-closed."""
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise PlatformError(
            "invalid %s %r: use 1-64 chars of [A-Za-z0-9._-]." % (what, value)
        )
    return value


def valid_text(
    value: object,
    what: str,
    *,
    min_len: int = 1,
    max_len: int = 500,
    allow_empty: bool = False,
) -> str:
    """Validate free text: length caps, no NUL/control surprises."""
    if not isinstance(value, str):
        raise PlatformError("%s must be text, got %r." % (what, type(value).__name__))
    text = value.strip()
    if not text and not allow_empty:
        raise PlatformError("%s must not be empty." % what)
    if len(text) < min_len and not (allow_empty and not text):
        raise PlatformError("%s is too short (min %d chars)." % (what, min_len))
    if len(text) > max_len:
        raise PlatformError(
            "%s is too long (%d chars, max %d)." % (what, len(text), max_len)
        )
    if "\x00" in text:
        raise PlatformError("%s contains a NUL byte." % what)
    return text


def valid_handle(value: object) -> str:
    """Handles: 3-32 chars, [a-z0-9._-], lowercased, no leading dot/dash."""
    if not isinstance(value, str):
        raise PlatformError("handle must be text.")
    handle = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9._-]{3,32}", handle):
        raise PlatformError(
            "invalid handle %r: use 3-32 chars of [a-z0-9._-]." % (value,)
        )
    if handle[0] in ".-" or handle[-1] in ".-":
        raise PlatformError(
            "invalid handle %r: may not start or end with '.' or '-'." % (value,)
        )
    return handle


def valid_price_cents(value: object, what: str = "price") -> int:
    """Prices are integer cents, >= 0. No floats, no negatives."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise PlatformError("%s must be integer cents, got %r." % (what, value))
    if value < 0:
        raise PlatformError("%s must be >= 0 cents, got %d." % (what, value))
    return value


def utcnow() -> str:
    """UTC timestamp string (ISO-8601)."""
    return datetime.now(timezone.utc).isoformat()


def expiry_after(days: int) -> str:
    """Expiry timestamp ``days`` from now; days must be 1-90."""
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 90:
        raise PlatformError(
            "listing duration must be 1-90 days, got %r." % (days,)
        )
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def is_expired(record: dict) -> bool:
    """True when the record's expires_at is in the past."""
    exp = record.get("expires_at")
    if not exp:
        return False
    return datetime.now(timezone.utc) >= datetime.fromisoformat(exp)


# ---------------------------------------------------------------------------
# Storage — owner-only JSON stores under <home>/.levi/voidbox/platform/
# ---------------------------------------------------------------------------


def platform_dir(home: Optional[Path] = None) -> Path:
    """Resolve ``<home>/.levi/voidbox/platform/`` (``$LEVI_HOME`` honored
    when ``home`` is None, hermetic tests pass ``home=tmp_path``).

    The adult gate is consulted FIRST — there is no unauthenticated path
    to the store location."""
    require_adult(home)
    if home is not None:
        root = Path(home)
    else:
        raw = os.environ.get("LEVI_HOME", "").strip()
        root = Path(raw).expanduser() if raw else Path.home()
    d = root / ".levi" / "voidbox" / _PLATFORM_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)  # fail closed even if pre-existing
    return d


class JsonStore:
    """Owner-only JSON record store. Subclasses declare their filename
    and record shapes. Public methods on subclasses call
    ``self._require_adult()`` FIRST."""

    _FILENAME = "store.json"

    def __init__(self, home: Optional[Path] = None):
        require_adult(home)  # gate FIRST, before any other work
        self._home = home
        self._dir = platform_dir(home)
        self._path = self._dir / self._FILENAME

    def _require_adult(self) -> None:
        """The gate is re-checked on every public call."""
        require_adult(self._home)

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PlatformError(
                "platform store %r is unreadable — refusing to proceed "
                "rather than risk corrupt state: %s" % (self._FILENAME, exc)
            ) from exc

    def _save(self, data: dict) -> None:
        atomic_write_bytes(
            self._path,
            (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8"),
            mode=0o600,
        )


# ---------------------------------------------------------------------------
# RED-1 hook — the exact details dict the enforcement ceremony consumes
# ---------------------------------------------------------------------------


def build_red1_details(kind: str, **fields: Any) -> dict:
    """Build the exact ``details`` dict the RED-1 payment ceremony will
    consume for a money-moving call.

    The platform never moves money; it attaches this dict to the
    pending record (status ``"pending_enforcement"``) and raises
    :class:`NotWiredError` on the call itself. The sibling enforcement
    worker owns the ceremony — this dict is the handoff contract.
    """
    details: dict[str, Any] = {
        "ceremony": "RED-1",
        "kind": valid_text(kind, "kind", max_len=64),
        "currency": "USD",
        "initiated_at": utcnow(),
        "status": "pending_enforcement",
    }
    details.update(fields)
    return details


# ---------------------------------------------------------------------------
# verify_laws — machine-checked invariants for the platform package
# ---------------------------------------------------------------------------


def verify_laws(home: Optional[Path] = None) -> list[tuple[str, bool, str]]:
    """Runtime law checks for the platform package.

    Returns ``(law_id, holds, detail)`` per law — honestly named:
    machine-checked invariants, not proof.
    """
    require_adult(home)
    results: list[tuple[str, bool, str]] = []

    def check(law: str, ok: bool, detail: str = "") -> None:
        results.append((law, ok, detail))

    # L2: every platform submodule exposes LAWS + wiring_report and every
    # NOT_WIRED capability names what is missing.
    from levi.voidbox.platform import (
        channels,
        chatrooms,
        classifieds,
        creator,
        dating,
        resale,
    )

    modules = {
        "dating": dating,
        "chatrooms": chatrooms,
        "creator": creator,
        "channels": channels,
        "classifieds": classifieds,
        "resale": resale,
    }
    for name, mod in modules.items():
        laws = getattr(mod, "LAWS", None)
        report = getattr(mod, "wiring_report", None)
        check(
            "L2",
            isinstance(laws, tuple) and len(laws) > 0 and callable(report),
            "%s declares LAWS + wiring_report" % name,
        )
        if callable(report):
            for cap, wired, detail in report():
                check(
                    "L2",
                    isinstance(cap, str) and isinstance(wired, bool)
                    and (wired or bool(detail)),
                    "%s.%s wired=%s" % (name, cap, wired),
                )
    # L6: platform dir exists owner-only.
    d = platform_dir(home)
    check("L6", d.is_dir() and (d.stat().st_mode & 0o777) == 0o700,
          "platform dir owner-only")
    return results
