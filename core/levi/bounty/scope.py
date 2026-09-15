"""Scope enforcement for the bounty recon pipeline.

The single structural safety rail: every network touch in the pipeline
goes through :func:`check_scope` / :meth:`ScopeStore.check` first. An
out-of-scope target raises :class:`ScopeError` — there is no bypass flag,
no environment override, and no "force" option anywhere in the codebase.

Scoping rule: an enrolled entry ``example.com`` authorizes that domain and
all of its subdomains (``app.example.com``). Enrollment is explicit via
``levi bounty scope add``; nothing is ever auto-enrolled.
"""

from __future__ import annotations

import json
import re
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_PATH = Path.home() / ".levi" / "bounty" / "scope.json"

_HOST_RE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")


class ScopeError(Exception):
    """Raised when a target is not inside an enrolled program scope."""


def _to_ascii(domain: str, raw: object) -> str:
    """Convert a (possibly internationalized) domain to ASCII/punycode.

    Pure encoding — no network, no DNS lookup. Raises ValueError on
    anything the IDNA codec cannot encode (never a traceback from the
    codec itself).
    """
    try:
        return domain.encode("idna").decode("ascii")
    except (UnicodeError, ValueError) as exc:
        raise ValueError(f"not a valid domain: {raw!r} ({exc})") from None


def normalize_domain(raw: str) -> str:
    """Normalize user input to a bare lowercase ASCII domain.

    Strips scheme, userinfo, port, path, query, fragment and trailing dot.
    Internationalized names are converted to punycode via the IDNA codec
    (``münchen.de`` → ``xn--mnchen-3ya.de``) before validation, so IDN
    input is accepted in its canonical ASCII form. IP literals
    (``1.2.3.4``, ``::1``) and malformed input are rejected — this
    function never performs a network call and never raises anything
    but ``ValueError``.
    """
    if not isinstance(raw, str):
        raise ValueError(
            f"not a valid domain: {raw!r} (expected a string, got {type(raw).__name__})"
        )
    t = raw.strip().lower()
    # strip scheme
    if "://" in t:
        t = t.split("://", 1)[1]
    # strip userinfo
    if "@" in t:
        t = t.split("@", 1)[1]
    # strip path/query/fragment
    t = re.split(r"[/?#]", t, maxsplit=1)[0]
    # strip port (but not IPv6 colons — we reject IPs anyway)
    if t.count(":") == 1:
        t = t.split(":", 1)[0]
    t = t.rstrip(".")
    if not t:
        raise ValueError(f"not a valid domain: {raw!r}")
    # IDN → punycode BEFORE the hostname regex (pure encoding, no network)
    t = _to_ascii(t, raw)
    if not _HOST_RE.match(t):
        raise ValueError(f"not a valid domain: {raw!r}")
    return t


def _is_within(candidate: str, enrolled: str) -> bool:
    """True if candidate == enrolled or is a subdomain of enrolled."""
    return candidate == enrolled or candidate.endswith("." + enrolled)


class ScopeStore:
    """Persistent set of enrolled bug-bounty program scopes."""

    def __init__(self, path: Optional[Path] = None):
        if path is not None and not isinstance(path, (str, Path)):
            raise ValueError(
                f"scope path must be a str/Path or None, got {type(path).__name__}"
            )
        self.path = Path(path) if path else DEFAULT_PATH
        self.domains: List[str] = []
        self._load()

    # -- persistence ------------------------------------------------------
    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            doms = raw.get("domains") or []
            self.domains = sorted({normalize_domain(d) for d in doms})
        except Exception as exc:
            # Corrupt scope file: fail CLOSED (nothing enrolled, so the
            # gate refuses everything) and say so loudly instead of
            # silently dropping the hunter's enrolled programs.
            warnings.warn(
                f"bounty scope file {self.path} is unreadable "
                f"({type(exc).__name__}); starting with no enrolled scopes. "
                "Back up or delete the file, then re-enroll with "
                "'levi bounty scope add <domain>'.",
                UserWarning,
                stacklevel=3,
            )
            self.domains = []

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "domains": self.domains,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    # -- management -------------------------------------------------------
    def add(self, raw: str) -> str:
        dom = normalize_domain(raw)
        if dom not in self.domains:
            self.domains.append(dom)
            self.domains.sort()
            self._persist()
        return dom

    def remove(self, raw: str) -> bool:
        dom = normalize_domain(raw)
        if dom in self.domains:
            self.domains.remove(dom)
            self._persist()
            return True
        return False

    def list(self) -> List[str]:
        return list(self.domains)

    # -- the gate ----------------------------------------------------------
    def check(self, raw_target: str) -> str:
        """Return the enrolled scope entry authorizing ``raw_target``.

        Raises ScopeError if the target is outside every enrolled scope.
        The returned scope string is recorded on every finding as its
        authorization evidence.
        """
        target = normalize_domain(raw_target)
        for enrolled in self.domains:
            if _is_within(target, enrolled):
                return enrolled
        enrolled = ", ".join(self.domains) or "(no scopes enrolled)"
        raise ScopeError(
            f"target {target!r} is outside every enrolled scope [{enrolled}]. "
            "Enroll the program scope first: levi bounty scope add <domain>. "
            "There is no override."
        )


def check_scope(raw_target: str, store: Optional[ScopeStore] = None) -> str:
    """Module-level gate used by every pipeline stage."""
    return (store or ScopeStore()).check(raw_target)
