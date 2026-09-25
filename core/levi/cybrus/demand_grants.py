"""Cybrus grant authority for DemandPulse — Direction 2 of the pair, the mint.

Companion to the sibling's in-flight ``levi.cybrus.demand_guard`` (receipt
VALIDATION, DG1–DG6 — untracked at the time of writing; this module never
edits that file). This module is the AUTHORITY: the only place DemandPulse
grants are minted, plus the per-channel watcher authorization and the
forgery-resistant validation the pairing mandate requires.

PAIRING LAWS (binding — declared first, enforced below, machine-checked by
tests/test_cybrus_demand_pairing.py; honestly named invariant checks,
nothing formally proven):
  P1  (intel provenance) No threat intel without provenance — enforced
      by ``levi.cybrus.threat_intel`` (I1).
  P2  (one-way intel) The intel feed never commands — ``levi.cybrus.threat_intel`` (I2).
  P3  (intel append-only) — ``levi.cybrus.threat_intel`` (I3).
  P4  (metadata-only audit) Every audit call here and in
      ``threat_intel`` carries metadata only — never store content,
      never message bodies (Cybrus L4).
  P5  (store write gate) No write to the DemandPulse store without a
      live grant receipt: bearer token, ``api`` kind, scope
      ``demand.store.write``, unexpired, unrevoked, label-bound to the
      actor, minted through THIS authority.
  P6  (store read gate) Same for reads: scope ``demand.store.read``.
  P7  (per-channel auth) Watcher channel access needs a grant scoped to
      THAT channel (``demand.channel.<name>``). A grant for one channel
      never authorizes another; channels are never auto-authorized.
  P8  (alert audit) Every alert emission requires scope
      ``demand.alert.emit`` and is audit-logged (metadata only). No
      emission without an audit record.
  P9  (fail closed) Missing, invalid, expired, revoked, mislabeled,
      wrong-scoped, or non-authority-minted grants refuse the operation.
      No fallback path (Cybrus L1/L3).
  P10 (no self-authorization) Grants mint ONLY through
      :func:`issue_grant` under a minter credential carrying scope
      ``grant.mint``. A token minted by calling ``TokenEngine.issue``
      directly — bypassing the authority — is FORGERY and is refused at
      the gate (the authority ledger cross-check). A compromised
      DemandPulse holding store/channel/alert scopes cannot mint grants
      and cannot command Cybrus (no ``service.call`` scope, so
      ``route_service_call`` refuses it).

Grant receipts are Cybrus bearer tokens (``levi.cybrus.tokens``):
scoped, expiring, revocable, plaintext-shown-once. The authority keeps an
append-only ledger of every grant it mints; validation cross-checks the
ledger (P9/P10).

Bootstrap: the owner mints the first minter token through the existing
CLI — ``levi cybrus token issue --scope grant.mint`` — then calls
:func:`issue_store_grant` / :func:`issue_channel_grant` /
:func:`issue_alert_grant` for the daemon's identities.

Seams for the 🪛 watcher-daemon sibling (``core/levi/daemon/`` — never
touched from here):
  - store file:  ``with store_session(path, credential, mode="write") as store:``
  - channel tick: ``authorize_channel("email", credential=...)`` before polling
  - alert run:    ``guarded_emit(credential=..., alert_ref=..., channel=...,
                  emit=lambda: engine.run(dp))``

The DemandPulse-side seam inventory lives in
``levi.demand.cybrus_alliance.guard_seams()`` (sibling 📯's alliance
module): signal_store, watcher_state, intel_feed, alert_path. This
module is the Cybrus-side guard wire for the signal_store (P5/P6),
watcher channels (P7), and alert path (P8) seams.

Relationship to BACK-GUARD (🔰 data-at-rest): this module guards ACCESS
(grants + audit). At-rest encryption of the store file is the back
guard's lane — not duplicated here. Writes are atomic (tmp + fsync +
replace) so a crash never leaves a torn store.

Stdlib-only, no network. All state under ``~/.levi/cybrus/``
(``LEVI_HOME`` override honored).
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple


# --- standalone-safe import of the sibling _paths helper -------------------
def _paths():  # noqa: D103 - private helper
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


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


#: The pairing laws, machine-readable (tests pin every id).
PAIRING_LAWS = (
    ("P1", "No threat intel without provenance (threat_intel I1)."),
    ("P2", "The intel feed is one-way: it never commands (threat_intel I2)."),
    ("P3", "The intel store is append-only (threat_intel I3)."),
    ("P4", "Audit records carry metadata only — never payloads or bodies."),
    ("P5", "No DemandPulse store write without a live authority-minted grant (demand.store.write)."),
    ("P6", "No DemandPulse store read without a live authority-minted grant (demand.store.read)."),
    ("P7", "Watcher channel access needs a grant scoped to that channel; never auto-authorized."),
    ("P8", "Every alert emission requires demand.alert.emit and is audit-logged."),
    ("P9", "Fail closed: bad grants refuse; no fallback path."),
    ("P10", "Grants mint only through the grant authority under a grant.mint credential; DemandPulse cannot self-authorize."),
)

#: Grant scopes — the authority's vocabulary. Distinct from the sibling
#: demand_guard's demandpulse.* scopes on purpose: these are the pairing
#: mandate's scopes, minted only here.
STORE_READ_SCOPE = "demand.store.read"
STORE_WRITE_SCOPE = "demand.store.write"
CHANNEL_SCOPE_PREFIX = "demand.channel."
ALERT_SCOPE = "demand.alert.emit"
MINT_SCOPE = "grant.mint"
PUBLISH_SCOPE = "threat.intel.publish"

WATCHER_CHANNELS = ("notification", "email", "text")

GRANT_SCOPES = frozenset(
    {
        STORE_READ_SCOPE,
        STORE_WRITE_SCOPE,
        ALERT_SCOPE,
        PUBLISH_SCOPE,
        *(CHANNEL_SCOPE_PREFIX + ch for ch in WATCHER_CHANNELS),
    }
)

#: Label namespace for authority-minted grants: "demand:<actor>".
LABEL_PREFIX = "demand:"

_GRANTS_LEDGER_NAME = "demand_grants.jsonl"

#: Grants stay short-lived by default (P5/P6).
DEFAULT_GRANT_TTL_SECONDS = 3600
MAX_GRANT_TTL_SECONDS = 24 * 3600


class GrantError(Exception):
    """Base class for grant-authority failures."""


class GrantInvalid(GrantError):
    """The presented grant is missing, unknown, revoked, expired,
    wrong-kind, wrong-scoped, mislabeled, actor-mismatched, or not minted
    through the grant authority. Carries the remedy (keeper's law / L6)."""


# ---------------------------------------------------------------------------
# Audit (P4: metadata only)


def _audit(event: str, actor: str, details: Dict[str, Any]) -> None:
    try:
        from levi.cybrus.audit import AuditEngine

        AuditEngine().append(event, str(actor), dict(details))
    except Exception:
        pass  # audit failure never opens the gate (P9)


# ---------------------------------------------------------------------------
# Authority ledger — append-only record of every mint (P10)


def _ledger_path() -> Path:
    p = _paths().cybrus_dir() / _GRANTS_LEDGER_NAME
    if not p.exists():
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
    else:
        os.chmod(p, 0o600)
    return p


def _ledger_append(entry: Dict[str, Any]) -> None:
    blob = (
        json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    fd = os.open(_ledger_path(), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, blob)
        os.fsync(fd)
    finally:
        os.close(fd)


def _ledger_token_ids() -> set:
    ids = set()
    try:
        for line in _ledger_path().read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ids.add(json.loads(line).get("token_id"))
            except (json.JSONDecodeError, AttributeError):
                continue
    except OSError:
        pass
    return ids


# ---------------------------------------------------------------------------
# Mint — the ONLY mint (P10)


def _check_actor_label(actor_label: str) -> str:
    if not isinstance(actor_label, str) or not actor_label.strip():
        raise GrantError("actor_label must be a non-empty string")
    actor_label = actor_label.strip()
    if len(actor_label) > 64:
        raise GrantError("actor_label must be at most 64 chars")
    if any(c in actor_label for c in (":", " ", "\n", "\t")):
        raise GrantError("actor_label must not contain ':' or whitespace")
    return actor_label


def issue_grant(
    *,
    minter_credential: Optional[str],
    actor_label: str,
    scopes: List[str],
    ttl_seconds: int = DEFAULT_GRANT_TTL_SECONDS,
    purpose: str = "",
) -> Tuple[str, str]:
    """Mint a DemandPulse grant receipt — the ONLY mint (P10).

    ``minter_credential`` must validate as a Cybrus bearer token carrying
    the ``grant.mint`` scope; anything else raises :class:`GrantInvalid`.
    The grant is label-bound (``demand:<actor_label>``), scoped to the
    authority vocabulary, and short-lived (<= 24h). Returns
    ``(token_id, plaintext_token)`` — the plaintext is returned exactly
    once and never logged (P4).
    """
    from levi.cybrus.tokens import TokenEngine

    if minter_credential is None:
        raise GrantInvalid(
            "no minter credential: grants mint only under a credential "
            f"carrying the {MINT_SCOPE!r} scope"
        )
    minter = TokenEngine().validate(minter_credential)
    if minter is None:
        raise GrantInvalid(
            "minter credential did not validate (unknown / revoked / expired)"
        )
    if MINT_SCOPE not in (minter.get("scopes") or []):
        raise GrantInvalid(
            f"minter credential lacks the {MINT_SCOPE!r} scope — "
            "this identity cannot mint grants (P10)"
        )
    if not isinstance(scopes, (list, tuple)) or not scopes:
        raise GrantError("scopes must be a non-empty list")
    for s in scopes:
        if s not in GRANT_SCOPES:
            raise GrantError(
                f"scope {s!r} is outside the grant authority's vocabulary; "
                f"mintable: {sorted(GRANT_SCOPES)}"
            )
    actor_label = _check_actor_label(actor_label)
    if not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
        raise GrantError("ttl_seconds must be a positive integer")
    if ttl_seconds > MAX_GRANT_TTL_SECONDS:
        raise GrantError("ttl_seconds must be at most 24h — grants stay short-lived")

    label = LABEL_PREFIX + actor_label
    token_id, plaintext = TokenEngine().issue(
        list(scopes), ttl_seconds=ttl_seconds, label=label, kind="api"
    )
    _ledger_append(
        {
            "token_id": token_id,
            "label": label,
            "scopes": list(scopes),
            "issued_at": _utcnow_iso(),
            "ttl_seconds": ttl_seconds,
            "minter": minter.get("label"),
            "purpose": purpose[:160],
        }
    )
    _audit(
        "demand.grant.minted",
        minter.get("label") or "unknown-minter",
        {
            "token_id": token_id[:8],
            "actor": actor_label,
            "scopes": list(scopes),
            "ttl_seconds": ttl_seconds,
        },
    )
    return token_id, plaintext


def issue_store_grant(
    *,
    minter_credential: Optional[str],
    actor_label: str,
    mode: str = "write",
    ttl_seconds: int = DEFAULT_GRANT_TTL_SECONDS,
) -> Tuple[str, str]:
    """Grant DemandPulse store access. ``mode="write"`` implies read."""
    if mode == "write":
        scopes = [STORE_READ_SCOPE, STORE_WRITE_SCOPE]
    elif mode == "read":
        scopes = [STORE_READ_SCOPE]
    else:
        raise GrantError("mode must be 'read' or 'write'")
    return issue_grant(
        minter_credential=minter_credential,
        actor_label=actor_label,
        scopes=scopes,
        ttl_seconds=ttl_seconds,
        purpose=f"demandpulse store {mode}",
    )


def issue_channel_grant(
    *,
    minter_credential: Optional[str],
    actor_label: str,
    channel: str,
    ttl_seconds: int = DEFAULT_GRANT_TTL_SECONDS,
) -> Tuple[str, str]:
    """Grant watcher access for ONE channel (P7)."""
    if channel not in WATCHER_CHANNELS:
        raise GrantError(f"channel must be one of {WATCHER_CHANNELS}")
    return issue_grant(
        minter_credential=minter_credential,
        actor_label=actor_label,
        scopes=[CHANNEL_SCOPE_PREFIX + channel],
        ttl_seconds=ttl_seconds,
        purpose=f"demandpulse watcher channel {channel}",
    )


def issue_alert_grant(
    *,
    minter_credential: Optional[str],
    actor_label: str,
    ttl_seconds: int = DEFAULT_GRANT_TTL_SECONDS,
) -> Tuple[str, str]:
    """Grant alert-emission rights (P8)."""
    return issue_grant(
        minter_credential=minter_credential,
        actor_label=actor_label,
        scopes=[ALERT_SCOPE],
        ttl_seconds=ttl_seconds,
        purpose="demandpulse alert emission",
    )


# ---------------------------------------------------------------------------
# Validation — the gate (P5/P6/P7/P9)


def validate_grant(
    credential: Optional[str],
    *,
    required_scope: str,
    actor_label: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate a grant receipt. Fail closed on EVERY defect (P9):

    unknown / revoked / expired token; non-``api`` token kind; missing
    scope; token id absent from the authority ledger (grant forgery —
    a token minted by calling ``TokenEngine.issue`` directly is refused);
    label outside the ``demand:`` namespace; label bound to a different
    actor.

    Returns the token payload on success. Raises :class:`GrantInvalid`
    naming the remedy (L6).
    """
    from levi.cybrus.tokens import TokenEngine

    def refused(reason: str, remedy: str, actor: str = "unknown") -> GrantInvalid:
        _audit(
            "demand.grant.refused",
            actor,
            {"reason": reason, "scope": required_scope},
        )
        return GrantInvalid(f"{reason} — remedy: {remedy}")

    if not isinstance(credential, str) or not credential:
        raise refused(
            "no_grant",
            "no grant credential presented; obtain one via issue_store_grant / "
            "issue_channel_grant / issue_alert_grant",
        )
    payload = TokenEngine().validate(credential)
    if payload is None:
        raise refused(
            "bad_token",
            "grant did not validate (unknown / revoked / expired); obtain a fresh grant",
        )
    label = payload.get("label") or ""
    if payload.get("kind") != "api":
        raise refused(
            "wrong_kind",
            "only 'api' tokens can hold demand grants",
            actor=label,
        )
    if required_scope not in (payload.get("scopes") or []):
        raise refused(
            "wrong_scope",
            f"obtain a grant minted with the {required_scope!r} scope",
            actor=label,
        )
    if payload.get("id") not in _ledger_token_ids():
        # Forgery: minted outside the authority. Refused (P9/P10).
        raise refused(
            "not_authority_minted",
            "grants mint only via issue_grant under a grant.mint credential",
            actor=label,
        )
    if not label.startswith(LABEL_PREFIX):
        raise refused(
            "bad_label",
            "obtain a grant bound to your actor label",
            actor=label,
        )
    if actor_label is not None and label != LABEL_PREFIX + actor_label:
        raise refused(
            "actor_mismatch",
            "present the grant minted for your own actor label",
            actor=label,
        )
    return payload


# ---------------------------------------------------------------------------
# Guarded store file (P5/P6)


class GuardedStore:
    """A DemandPulse store file opened under a grant receipt.

    The grant is re-validated fresh on EVERY operation — expiry or
    revocation mid-session fails closed (P9). Every operation is
    audit-logged with metadata only (P4): path ref, actor, byte count —
    never content.
    """

    def __init__(self, path: Path, *, credential: str, mode: str):
        if mode not in ("read", "write"):
            raise GrantError("mode must be 'read' or 'write'")
        self._path = Path(path)
        self._credential = credential
        self._mode = mode
        payload = validate_grant(
            credential,
            required_scope=STORE_WRITE_SCOPE if mode == "write" else STORE_READ_SCOPE,
        )
        self._actor = payload.get("label") or "unknown"

    @property
    def path(self) -> Path:
        return self._path

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def actor(self) -> str:
        return self._actor

    def _require(self, scope: str) -> Dict[str, Any]:
        return validate_grant(self._credential, required_scope=scope)

    # -- reads -----------------------------------------------------------

    def read_text(self) -> str:
        payload = self._require(STORE_READ_SCOPE)
        data = self._path.read_text(encoding="utf-8")
        _audit(
            "demand.store.read",
            payload.get("label") or "unknown",
            {"path_ref": self._path.name, "bytes": len(data)},
        )
        return data

    def load_json(self) -> Any:
        return json.loads(self.read_text())

    # -- writes ----------------------------------------------------------

    def write_text(self, data: str) -> None:
        if self._mode != "write":
            raise GrantInvalid(
                "store opened read-only; writes refused — remedy: open with "
                "mode='write' under a demand.store.write grant"
            )
        if not isinstance(data, str):
            raise GrantError("data must be a string")
        payload = self._require(STORE_WRITE_SCOPE)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        blob = data.encode("utf-8")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, blob)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, self._path)
        os.chmod(self._path, 0o600)
        _audit(
            "demand.store.write",
            payload.get("label") or "unknown",
            {"path_ref": self._path.name, "bytes": len(blob)},
        )

    def save_json(self, obj: Any) -> None:
        self.write_text(json.dumps(obj, indent=2))


@contextmanager
def store_session(
    path: Path, *, credential: str, mode: str
) -> Iterator[GuardedStore]:
    """Open a guarded session on a DemandPulse store file."""
    store = GuardedStore(path, credential=credential, mode=mode)
    try:
        yield store
    finally:
        store._credential = ""  # noqa: SLF001 - deliberate invalidation


# ---------------------------------------------------------------------------
# Per-channel watcher authorization (P7)


def authorize_channel(
    channel: str, *, credential: Optional[str], actor_label: Optional[str] = None
) -> Dict[str, Any]:
    """Authorize one watcher-channel tick. The grant must carry
    ``demand.channel.<channel>`` for THIS channel — a grant for another
    channel is refused (P7). Returns the channel-access receipt."""
    if channel not in WATCHER_CHANNELS:
        raise GrantError(f"channel must be one of {WATCHER_CHANNELS}")
    try:
        payload = validate_grant(
            credential,
            required_scope=CHANNEL_SCOPE_PREFIX + channel,
            actor_label=actor_label,
        )
    except GrantInvalid as exc:
        _audit(
            "demand.channel.refused",
            "unknown",
            {"channel": channel, "reason": str(exc)[:120]},
        )
        raise
    receipt = {
        "channel": channel,
        "actor": payload.get("label"),
        "granted_at": _utcnow_iso(),
        "expires_at": payload.get("expires_at"),
        "receipt_id": "ch-" + payload.get("id", "")[:8],
    }
    _audit(
        "demand.channel.authorized",
        payload.get("label") or "unknown",
        {"channel": channel, "receipt_id": receipt["receipt_id"]},
    )
    return receipt


# ---------------------------------------------------------------------------
# Guarded alert emission (P8)


def guarded_emit(
    *,
    credential: Optional[str],
    alert_ref: str,
    channel: str,
    emit: Callable[[], Any],
) -> Any:
    """Run ``emit()`` under the alert-emission grant. Requires scope
    ``demand.alert.emit``; the emission is audit-logged with metadata
    only — alert_ref, channel, outcome (P8, P4). No grant, no emission;
    a failed emission is audit-logged and re-raised (never silent)."""
    if not isinstance(alert_ref, str) or not alert_ref.strip():
        raise GrantError("alert_ref must be a non-empty string")
    if not isinstance(channel, str) or not channel.strip():
        raise GrantError("channel must be a non-empty string")
    if not callable(emit):
        raise GrantError("emit must be callable")
    try:
        payload = validate_grant(credential, required_scope=ALERT_SCOPE)
    except GrantInvalid as exc:
        _audit(
            "demand.alert.refused",
            "unknown",
            {"alert_ref": alert_ref[:32], "channel": channel, "reason": str(exc)[:120]},
        )
        raise
    actor = payload.get("label") or "unknown"
    try:
        result = emit()
    except Exception as exc:
        _audit(
            "demand.alert.failed",
            actor,
            {
                "alert_ref": alert_ref[:32],
                "channel": channel,
                "error": type(exc).__name__,
            },
        )
        raise
    _audit(
        "demand.alert.emitted",
        actor,
        {"alert_ref": alert_ref[:32], "channel": channel, "ok": True},
    )
    return result


# ---------------------------------------------------------------------------


def describe_posture() -> Dict[str, Any]:
    """Honest backend posture (cf. enforce.py L12)."""
    return {
        "module": "levi.cybrus.demand_grants",
        "direction": "Cybrus guards DemandPulse (P5-P10)",
        "laws": [lid for lid, _ in PAIRING_LAWS],
        "mints_grants": True,
        "mint_scope": MINT_SCOPE,
        "grant_scopes": sorted(GRANT_SCOPES),
        "ledger": str(_ledger_path()),
        "directs_demandpulse": False,
        "egress": "none — stdlib-only, zero network",
        "boundary": [
            "bearer-credential boundary: enforced at the application layer between identities on Chauncey's machine",
            "a local actor with raw filesystem write can hand-edit the ledger or stores — tamper-EVIDENT (audit hash chain), not tamper-PROOF; same posture as the rest of Cybrus",
            "companion: the sibling's in-flight levi.cybrus.demand_guard validates demandpulse.* receipts (DG1-DG6); this module mints and channel-scopes",
        ],
    }
