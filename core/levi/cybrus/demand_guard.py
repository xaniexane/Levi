"""Cybrus guard for DemandPulse — the "Cybrus guards DemandPulse" direction.

DemandPulse stays a general with its standing orders; Cybrus stays the
guard. This module enforces; it never directs DemandPulse's behavior.

Every read or write of the DemandPulse store (``~/.levi/demand_pulse.json``),
every watcher-channel ingest, and every alert emission must cross this
guard with a Cybrus grant receipt: a short-lived ``api`` token issued by
:mod:`levi.cybrus.tokens` carrying a ``demandpulse.*`` scope. The guard
only VALIDATES receipts — it never mints them (originals-first: issuance
is the token engine's job, e.g. ``levi cybrus token issue --scope
demandpulse.write`` after the normal approval path).

LAWS (binding — what must always hold):
  DG1 No DemandPulse store read without a grant receipt: a valid,
      unexpired, unrevoked ``api`` token carrying ``demandpulse.read``
      (or ``demandpulse.admin``). Anything else fails closed.
  DG2 No DemandPulse store write without a grant receipt carrying
      ``demandpulse.write`` (or ``demandpulse.admin``). Watcher-channel
      ingests are writes and need the same receipt.
  DG3 No alert emission without a grant receipt carrying
      ``demandpulse.alert`` (or ``demandpulse.admin``) — and EVERY alert
      emission is audit-logged (metadata only).
  DG4 Grant receipts are re-validated on EVERY call (expiry and
      revocation checked per use through the token engine). A cached
      permission is never trusted twice.
  DG5 Scope confinement: a ``demandpulse.*`` grant can never command
      Cybrus. It is refused by ``route_service_call`` and
      ``request_egress`` (those demand the ``service.call`` scope), and a
      Cybrus routing grant (``route.external`` scope) is refused here.
      A compromised DemandPulse stays a compromised DemandPulse.
  DG6 The guard invents nothing: it validates what the token engine
      issued. There is no bypass path — no policy, approval, tier, or
      founder exemption substitutes for a grant receipt.

Proof: tests/test_cybrus_demand_guard.py — invariant tests, honestly
named (machine-checked, not formally proven).

Stdlib-only, no network. State: the DemandPulse store itself plus the
Cybrus audit log and token store under ``~/.levi/cybrus/``.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Scopes
# ---------------------------------------------------------------------------

SCOPE_READ = "demandpulse.read"
SCOPE_WRITE = "demandpulse.write"
SCOPE_ALERT = "demandpulse.alert"
SCOPE_ADMIN = "demandpulse.admin"

#: The declared laws, machine-readable (same pattern as enforce.LAWS).
LAWS = (
    ("DG1", "No DemandPulse store read without a valid grant receipt (demandpulse.read / demandpulse.admin)."),
    ("DG2", "No DemandPulse store write without a grant receipt (demandpulse.write / demandpulse.admin); watcher ingests are writes."),
    ("DG3", "No alert emission without a grant receipt (demandpulse.alert / demandpulse.admin); every emission audit-logged, metadata only."),
    ("DG4", "Grant receipts are re-validated on every call — expiry and revocation checked per use."),
    ("DG5", "Scope confinement: demandpulse.* grants cannot command Cybrus; Cybrus grants cannot touch DemandPulse."),
    ("DG6", "The guard invents nothing: it validates what the token engine issued; no bypass path."),
)

_DEMAND_SCOPES = frozenset({SCOPE_READ, SCOPE_WRITE, SCOPE_ALERT, SCOPE_ADMIN})

#: Which scopes satisfy a required scope (admin covers all).
_COVERS = {
    SCOPE_READ: frozenset({SCOPE_READ, SCOPE_ADMIN}),
    SCOPE_WRITE: frozenset({SCOPE_WRITE, SCOPE_ADMIN}),
    SCOPE_ALERT: frozenset({SCOPE_ALERT, SCOPE_ADMIN}),
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DemandGuardError(Exception):
    """The guard refused: no/invalid/insufficient grant receipt."""


def _paths():  # noqa: D103 - private helper, same rationale as enforce.py
    try:
        from levi.cybrus import _paths as _p

        return _p
    except ImportError:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "levi.cybrus._paths.standalone",
            Path(__file__).resolve().parent / "_paths.py",
        )
        if spec is None or spec.loader is None:  # pragma: no cover
            raise ImportError("cybrus _paths helper unavailable") from None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


def _audit(event: str, actor: str, details: Optional[Dict] = None) -> Dict:
    from levi.cybrus.audit import AuditEngine

    return AuditEngine().append(event, str(actor), dict(details or {}))


def _default_demand_path() -> Path:
    raw = os.environ.get("LEVI_HOME", "").strip()
    root = Path(raw).expanduser() if raw else Path.home()
    return root / ".levi" / "demand_pulse.json"


def _default_alerts_path() -> Path:
    raw = os.environ.get("LEVI_HOME", "").strip()
    root = Path(raw).expanduser() if raw else Path.home()
    return root / ".levi" / "demand_alerts.json"


def _check_name(value: str, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DemandGuardError(f"{what} must be a non-empty string")
    value = value.strip()
    if len(value) > 128:
        raise DemandGuardError(f"{what} must be at most 128 chars")
    return value


def _canonical(doc: Dict) -> str:
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _doc_digest(doc: Dict) -> str:
    return hashlib.sha256(_canonical(doc).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Grant validation (the receipt check — DG1/DG4/DG5/DG6)
# ---------------------------------------------------------------------------


def require_grant(credential: Optional[str], scope: str) -> Dict[str, Any]:
    """Validate a grant receipt for ``scope``. Returns the token payload.

    A receipt is a Cybrus ``api`` token whose scopes cover ``scope``
    (``demandpulse.admin`` covers all three). The token engine is asked
    EVERY call — expiry and revocation are checked per use (DG4).

    Raises :class:`DemandGuardError` on: missing credential, unknown /
    revoked / expired token, wrong token kind (only ``api`` tokens can
    hold demand grants), unknown scope, or insufficient scope. Every
    refusal is audit-logged (``demand.grant.refused``, metadata only).
    """
    if scope not in _DEMAND_SCOPES:
        raise DemandGuardError(f"unknown demand scope {scope!r}")

    def refused(reason: str, token_id: Optional[str] = None) -> DemandGuardError:
        _audit(
            "demand.grant.refused",
            "cybrus.demand_guard",
            {
                "scope": scope,
                "token_id": token_id[:8] if token_id else None,
                "reason": reason,
            },
        )
        return DemandGuardError(f"grant refused for {scope}: {reason}")

    if not isinstance(credential, str) or not credential:
        raise refused("no grant receipt presented")

    from levi.cybrus.tokens import TokenEngine

    payload = TokenEngine().validate(credential)
    if payload is None:
        raise refused("receipt did not validate (unknown / revoked / expired)")
    if payload.get("kind") != "api":
        raise refused(
            f"token kind {payload.get('kind')!r} cannot hold a demand grant",
            payload.get("id"),
        )
    token_scopes = set(payload.get("scopes") or [])
    # DG5: a Cybrus routing / service grant is meaningless here — only
    # demandpulse.* scopes count, and only the required one (or admin).
    if not token_scopes & _COVERS[scope]:
        raise refused(
            f"receipt lacks the {scope} scope "
            "(scope-confined: Cybrus grants cannot touch DemandPulse)",
            payload.get("id"),
        )
    return payload


def describe_posture() -> Dict[str, Any]:
    """Honest posture of the DemandPulse guard (L12-style, like enforce's)."""
    return {
        "organism": "levi",
        "organ": "levi.cybrus.demand_guard",
        "role": "guard: every DemandPulse store read/write and every alert emission requires a Cybrus grant receipt",
        "mints_grants": False,  # DG6: validates only; issuance is the token engine's job
        "directs_demandpulse": False,  # DemandPulse stays a general with its standing orders
        "network": "none — stdlib only",
        "scopes": sorted(_DEMAND_SCOPES),
        "default_store": str(_default_demand_path()),
        "default_alerts": str(_default_alerts_path()),
        "laws": [lid for lid, _ in LAWS],
    }


# ---------------------------------------------------------------------------
# The guarded store
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Grant:
    """A validated grant receipt bound to one store handle."""

    token_id: str
    scope: str
    label: Optional[str]


class GuardedDemandStore:
    """The DemandPulse store, reachable only through grant receipts.

    Obtain a scoped handle with :meth:`authorize`, then ``read`` / ``write``
    / ``append_signal`` / ``scan_seed_items`` / ``emit_alert`` on the handle.
    Every handle operation re-validates the receipt (DG4); every write and
    every alert emission is audit-logged (DG3); audit records carry
    metadata only — digests and ids, never signal text or alert bodies.
    """

    def __init__(
        self,
        path: Optional[Path] = None,
        alert_path: Optional[Path] = None,
    ) -> None:
        self.path = Path(path) if path else _default_demand_path()
        self.alert_path = Path(alert_path) if alert_path else _default_alerts_path()

    # -- authorization -----------------------------------------------------

    def authorize(self, credential: Optional[str], scope: str) -> "_ScopedHandle":
        """Validate ``credential`` for ``scope`` and return a scoped handle."""
        payload = require_grant(credential, scope)
        return _ScopedHandle(
            self,
            _Grant(
                token_id=str(payload["id"]),
                scope=scope,
                label=payload.get("label"),
            ),
            credential,
        )

    # -- internals (caller must hold a validated grant) --------------------

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"signals": [], "opportunities": [], "score_cards": []}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DemandGuardError(
                f"demand store unreadable ({exc}); refusing rather than "
                "inventing state (originals-first)"
            ) from exc
        if not isinstance(raw, dict):
            raise DemandGuardError("demand store is not a JSON object; refusing")
        return raw

    def _save(self, doc: Dict[str, Any]) -> None:
        if not isinstance(doc, dict):
            raise DemandGuardError("demand store document must be a JSON object")
        _paths().atomic_write_bytes(
            self.path, _canonical(doc).encode("utf-8"), 0o600
        )


class _ScopedHandle:
    """One validated receipt, bound to the operations its scope allows."""

    def __init__(
        self, store: GuardedDemandStore, grant: _Grant, credential: str
    ) -> None:
        self._store = store
        self._grant = grant
        self._credential = credential

    @property
    def scope(self) -> str:
        return self._grant.scope

    def _revalidate(self, scope: str) -> _Grant:
        """DG4: the receipt is checked again, every operation."""
        if scope != self._grant.scope:
            raise DemandGuardError(
                f"handle is scoped {self._grant.scope!r}; {scope!r} not allowed"
            )
        payload = require_grant(self._credential, scope)
        return _Grant(
            token_id=str(payload["id"]), scope=scope, label=payload.get("label")
        )

    def _actor(self) -> str:
        return f"demand-grant:{self._grant.token_id[:8]}"

    # -- reads (DG1) -------------------------------------------------------

    def read(self) -> Dict[str, Any]:
        """Read the store. Requires a ``demandpulse.read`` receipt."""
        grant = self._revalidate(SCOPE_READ)
        doc = self._store._load()
        _audit(
            "demand.store.read",
            self._actor(),
            {
                "scope": grant.scope,
                "token_id": grant.token_id[:8],
                "bytes": len(_canonical(doc).encode("utf-8")),
                "doc_digest": _doc_digest(doc)[:16],
            },
        )
        return copy.deepcopy(doc)

    # -- writes (DG2) ------------------------------------------------------

    def write(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Replace the store document. Requires a ``demandpulse.write`` receipt."""
        grant = self._revalidate(SCOPE_WRITE)
        self._store._save(doc)
        _audit(
            "demand.store.write",
            self._actor(),
            {
                "scope": grant.scope,
                "token_id": grant.token_id[:8],
                "doc_digest": _doc_digest(doc)[:16],
                "bytes": len(_canonical(doc).encode("utf-8")),
            },
        )
        return {"ok": True, "doc_digest": _doc_digest(doc)}

    def append_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Append one signal dict to the store. Requires ``demandpulse.write``."""
        grant = self._revalidate(SCOPE_WRITE)
        if not isinstance(signal, dict):
            raise DemandGuardError("signal must be a dict")
        doc = self._store._load()
        signals = doc.get("signals")
        if not isinstance(signals, list):
            raise DemandGuardError("store 'signals' is not a list; refusing")
        signals.append(copy.deepcopy(signal))
        self._store._save(doc)
        _audit(
            "demand.store.signal_appended",
            self._actor(),
            {
                "scope": grant.scope,
                "token_id": grant.token_id[:8],
                "signal_id": str(signal.get("id", ""))[:32] or None,
                "doc_digest": _doc_digest(doc)[:16],
            },
        )
        return {"ok": True, "signal_count": len(signals)}

    def scan_seed_items(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Watcher-channel ingest: seed HYPOTHESIS signals from poll items.

        Each item is ``{"text": ..., "segment": ..., "source": ...}``.
        Requires ``demandpulse.write`` — the watcher is a writer like any
        other (DG2). The guard never directs WHAT is seeded; it only
        enforces the receipt (the general keeps his standing orders).
        """
        grant = self._revalidate(SCOPE_WRITE)
        if not isinstance(items, list):
            raise DemandGuardError("items must be a list")
        from levi.demand.pulse import DemandPulse  # lazy: demand must not hard-depend on cybrus

        dp = DemandPulse(path=self._store.path)
        seeded: List[str] = []
        for item in items:
            if not isinstance(item, dict):
                raise DemandGuardError("each ingest item must be a dict")
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                raise DemandGuardError("each ingest item needs non-empty 'text'")
            sig = dp.scan_seed(
                text,
                segment=str(item.get("segment") or "general"),
                source=str(item.get("source") or "scan"),
            )
            seeded.append(sig.id)
        _audit(
            "demand.store.scan_seeded",
            self._actor(),
            {
                "scope": grant.scope,
                "token_id": grant.token_id[:8],
                "seeded": len(seeded),
                "signal_ids": [s[:8] for s in seeded[:20]],
            },
        )
        return {"ok": True, "seeded": seeded}

    # -- alerts (DG3) ------------------------------------------------------

    def emit_alert(self, kind: str, name: str, **fields: Any) -> Dict[str, Any]:
        """Create (emit) an alert. Requires a ``demandpulse.alert`` receipt.

        Every emission is audit-logged with metadata only — alert id, kind,
        name. Alert bodies / field values are never written to the audit
        log (enforce-L4 discipline).
        """
        grant = self._revalidate(SCOPE_ALERT)
        kind = _check_name(kind, "alert kind")
        name = _check_name(name, "alert name")
        from levi.demand.alerts import AlertEngine  # lazy import, same rationale

        engine = AlertEngine(path=self._store.alert_path)
        alert = engine.create(kind, name, **fields)
        _audit(
            "demand.alert.emitted",
            self._actor(),
            {
                "scope": grant.scope,
                "token_id": grant.token_id[:8],
                "alert_id": str(alert.id)[:8],
                "kind": kind,
                "name": name,
            },
        )
        return {"ok": True, "alert_id": str(alert.id)}
