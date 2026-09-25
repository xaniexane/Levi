"""Cybrus BACK-guard — the guard on data at rest (🔰 BACK-GUARD mandate).

Chauncey's mandate: Cybrus is his guard on all four sides. BACK is what's
behind him — his data at rest: the encrypted archives, the vault, the
dynasty/IP eyes-only material, backup integrity. NOTHING of his leaves
without a grant.

BACK LAWS (binding — what must always hold):
  B1  No eyes-only byte crosses a copy/export/archive path without an
      explicit back-guard grant (approval-backed, single-use, bound to
      actor+src+dst+purpose, expiring) plus an audit receipt.
      Default: deny.
  B2  Bulk reads of sensitive stores (vault, password material) require
      an explicit approval plus an audit entry. Bulk = more than
      ``BULK_READ_THRESHOLD`` secret reads inside ``BULK_READ_WINDOW``,
      or any whole-store read through the sanctioned bulk path.
  B3  Every backup/archive of vault/envelope material carries a
      hash-chained manifest. Tampering, deletion, or rollback is
      detectable by :meth:`BackupManifest.verify`.
  B4  The eyes-only registry is append-only and conservative: anything
      under a sensitive root that cannot be cleanly classified is
      treated as sensitive; anything matching an eyes-only marker is
      treated as eyes-only.
  B5  The single sanctioned path for data-at-rest egress is
      :func:`request_copy` / :func:`request_archive` /
      :func:`bulk_read_secrets`. Products must not roll their own copy,
      export, or archive tooling around these stores. Every refusal
      names its remedy (keeper's law, L6).
  B6  Cybrus L9/L10 apply: manifests and the audit log only ever grow;
      grants expire but their records remain; removal is not a tool this
      module uses. Policy deny always wins (L3): an explicit
      ``back.copy`` deny rule hard-stops even a grant-backed copy.

What this module does NOT do (honest limits):
  - It cannot stop a process that ignores it and calls ``shutil.copy``
    directly, or a root attacker rewriting files under it. It is the
    sanctioned gate, not a kernel MAC. The residual risk is documented
    in docs/CYBRUS.md alongside the other cybrus residual risks.
  - Single-secret reads (``vault get`` for one entry) remain the vault's
    intended function: they need the master passphrase (the credential
    IS the grant) and are audited by the identity layer. The bulk gate
    (B2) is what catches exfiltration-shaped read patterns.

Stdlib-only, no network. State under ``~/.levi/cybrus/``
(``LEVI_HOME`` override honored), via the shared ``_paths`` helpers.

Proof: tests/test_cybrus_backguard.py — invariant tests, honestly named
(nothing here is formally proven, only machine-checked against B1–B6).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple


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


#: The declared BACK laws, machine-readable (B6: law→guard→prove — the
#: laws live in code, not just prose; tests assert every id is declared).
BACK_LAWS = (
    ("B1", "No eyes-only byte crosses a copy/export/archive path without an explicit back-guard grant plus an audit receipt; default deny."),
    ("B2", "Bulk reads of sensitive stores require an explicit approval plus an audit entry."),
    ("B3", "Every backup/archive of vault/envelope material carries a hash-chained manifest; tampering, deletion, or rollback is detectable by verify()."),
    ("B4", "The eyes-only registry is append-only and conservative: unclassifiable-under-sensitive-root is sensitive; marker match is eyes-only."),
    ("B5", "The single sanctioned path for data-at-rest egress is request_copy/request_archive/bulk_read_secrets; every refusal names its remedy."),
    ("B6", "L9/L10 apply: manifests and audit only ever grow; grants expire but records remain; explicit policy deny always wins (L3)."),
)


def describe_posture() -> Dict:
    """Honest backend posture (L12: honesty over polish)."""
    return {
        "organism": "levi",
        "organ": "levi.cybrus.backguard",
        "mandate": "BACK — data at rest: encrypted archives, vault, dynasty/IP eyes-only, backup integrity",
        "network": "none — stdlib only; this module performs no I/O beyond the local filesystem",
        "state_dir": str(_paths().cybrus_dir()),
        "cannot_stop": [
            "a process that ignores this module and copies files directly",
            "a root attacker rewriting files under the stores",
            "single-secret reads via the vault passphrase (intended function, not egress)",
        ],
        "default_allow": False,  # B1: default deny
        "deny_wins": True,  # B6/L3
        "laws": [lid for lid, _ in BACK_LAWS],
    }


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class BackGuardError(Exception):
    """Base class for BACK-guard failures."""


class BackGuardDenied(BackGuardError):
    """The copy/export/archive was refused. The message always names the
    remedy (keeper's law, L6 / B5)."""


class ApprovalNeeded(BackGuardDenied):
    """A human approval is required before the operation may proceed.

    Carries ``approval_id`` — resumable (forward-motion, L11): approve it,
    then retry the same call.
    """

    def __init__(self, approval_id: str, message: str):
        super().__init__(message)
        self.approval_id = approval_id


class BulkReadDenied(BackGuardDenied):
    """A bulk-read pattern was detected without a grant."""


class ManifestError(BackGuardError):
    """Backup manifest failure: tamper detected, chain broken, or I/O."""


# ---------------------------------------------------------------------------
# Path classification — the eyes-only registry (B4)
# ---------------------------------------------------------------------------

#: Bulk-read gate tuning (B2).
BULK_READ_THRESHOLD = 10
BULK_READ_WINDOW_SECONDS = 300

#: A directory copy/export counts as "bulk" above this file count.
BULK_DIR_FILE_THRESHOLD = 25

#: Back-guard grants live this long.
GRANT_TTL_SECONDS = 900

#: Basename that is always eyes-only, wherever it sits. Chauncey's
#: passwords CSV: NEVER read, opened, or imported by this module — it is
#: matched by name only so the gate can refuse to move it.
_PASSWORDS_CSV_BASENAME = "Google_Passwords.csv"

#: Substrings in a basename that mark eyes-only material.
_EYES_ONLY_NAME_MARKERS = (
    "IP_PROTECTION",
    "ip_protection",
    "eyes-only",
    "eyes_only",
    "EYES_ONLY",
)

#: Suffixes that mark sensitive (encrypted-at-rest) material.
_SENSITIVE_SUFFIXES = (".enc", ".envelope")

#: Substrings in a basename that mark sensitive material.
_SENSITIVE_NAME_MARKERS = (
    "password",
    "passwd",
    "secret",
    "credential",
    "private_key",
)

#: Cloud-sync identifiers, separator-stripped and lowercased (R2): folder
#: names like "GoogleDrive", "Google_Drive", "gdrive", "OneDrivePersonal"
#: or "my-dropbox" must not evade the sync-folder tripwire. Matching is
#: by substring on the normalized part — fail closed.
_CLOUD_SYNC_IDS = (
    "googledrive",
    "onedrive",
    "dropbox",
    "iclouddrive",
    "insync",
    "gdrive",
)

#: Exact-match-only cloud ids: too common as substrings ("megaproject")
#: for substring matching; the normalized part must equal the id.
_CLOUD_SYNC_EXACT_IDS = ("mega",)

#: Default removable/device prefixes. Overridable via
#: ``CYBRUS_REMOVABLE_PREFIXES`` (os.pathsep-separated) for tests.
_DEFAULT_REMOVABLE_PREFIXES = ("/media", "/run/media", "/mnt", "/dev")


def _repo_root() -> Path:
    """Repo root above ``core/levi/cybrus/``."""
    return Path(__file__).resolve().parents[3]


def _extra_eyes_only_roots() -> List[Path]:
    raw = os.environ.get("CYBRUS_EYES_ONLY_ROOTS", "").strip()
    if not raw:
        return []
    return [Path(p).expanduser() for p in raw.split(os.pathsep) if p.strip()]


def _eyes_only_roots() -> List[Path]:
    p = _paths()
    roots = [
        _repo_root() / "core" / "levi" / "dynasty",
        _repo_root() / "core" / "levi" / "genesis",
        p.cybrus_dir() / "vault",
        p.cybrus_dir() / "envelopes",
    ]
    roots.extend(_extra_eyes_only_roots())
    return roots


def _eyes_only_files() -> List[Path]:
    return [_paths().cybrus_dir() / "audit.jsonl"]


def _removable_prefixes() -> Tuple[str, ...]:
    raw = os.environ.get("CYBRUS_REMOVABLE_PREFIXES", "").strip()
    if raw:
        return tuple(p for p in raw.split(os.pathsep) if p.strip())
    return _DEFAULT_REMOVABLE_PREFIXES


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def classify(path) -> str:
    """Classify ``path`` into ``"eyes-only"`` | ``"sensitive"`` | ``"normal"``.

    Conservative (B4): markers are checked before the general sensitive
    rules, and anything under a sensitive root that cannot be cleanly
    classified stays sensitive. Symlinks are resolved before
    classification so a link cannot launder an eyes-only target.
    """
    p = Path(path).expanduser()
    try:
        resolved = p.resolve()
    except OSError:
        resolved = p.absolute()
    name = resolved.name
    lowered = name.lower()

    # -- eyes-only ------------------------------------------------------
    if name == _PASSWORDS_CSV_BASENAME:
        return "eyes-only"
    if any(marker in name for marker in _EYES_ONLY_NAME_MARKERS):
        return "eyes-only"
    for root in _eyes_only_roots():
        try:
            r = root.resolve()
        except OSError:
            r = root.absolute()
        if _is_under(resolved, r):
            return "eyes-only"
    for f in _eyes_only_files():
        try:
            if resolved == f.resolve():
                return "eyes-only"
        except OSError:
            pass

    # -- sensitive ------------------------------------------------------
    cybrus = _paths().cybrus_dir()
    try:
        if _is_under(resolved, cybrus.resolve()):
            return "sensitive"
    except OSError:
        if _is_under(resolved, cybrus.absolute()):
            return "sensitive"
    if resolved.suffix in _SENSITIVE_SUFFIXES:
        return "sensitive"
    if any(marker in lowered for marker in _SENSITIVE_NAME_MARKERS):
        return "sensitive"

    return "normal"


def destination_risk(path) -> str:
    """``"external"`` when ``path`` is exfiltration-shaped (removable
    media, device nodes, cloud-sync folders, remote/URL-style targets),
    else ``"internal"``.

    Cloud-sync detection normalizes each path part (separators stripped,
    lowercased) before matching, so "GoogleDrive", "Google_Drive",
    "gdrive", "OneDrivePersonal" and "my-dropbox" all trip the wire
    (R2). Matching errs closed: an innocent folder containing a sync
    id merely needs a grant for sensitive copies.
    """
    text = os.path.expanduser(str(path))
    lowered = text.lower()
    for prefix in _removable_prefixes():
        if lowered == prefix or lowered.startswith(prefix.rstrip("/") + "/"):
            return "external"
    for part in Path(text).parts:
        norm = re.sub(r"[^a-z0-9]", "", part.lower())
        if not norm:
            continue
        if norm in _CLOUD_SYNC_EXACT_IDS:
            return "external"
        if any(cid in norm for cid in _CLOUD_SYNC_IDS):
            return "external"
    if "://" in text:
        return "external"
    if re.match(r"^[\w.\-]+@[\w.\-]+:", text):
        return "external"
    return "internal"


# ---------------------------------------------------------------------------
# Audit helper (metadata only — L4)
# ---------------------------------------------------------------------------


def _audit(event: str, actor: str, details: Optional[Dict] = None) -> Dict:
    from levi.cybrus.audit import AuditEngine

    return AuditEngine().append(event, str(actor), dict(details or {}))


def _check_actor(actor: str) -> str:
    if not isinstance(actor, str) or not actor.strip():
        raise BackGuardError("actor must be a non-empty string")
    actor = actor.strip()
    if len(actor) > 128:
        raise BackGuardError("actor must be at most 128 chars")
    return actor


def _resolve_source(src) -> Path:
    p = Path(src).expanduser()
    try:
        resolved = p.resolve()
    except OSError as exc:
        raise BackGuardError(f"cannot resolve source path: {exc}") from exc
    if not resolved.exists():
        raise BackGuardError(f"source does not exist: {resolved}")
    return resolved


def _resolve_dest_parent(dst) -> Tuple[Path, Path]:
    """(resolved dst, resolved parent).

    When the final component EXISTS it is resolved as well (R1): a
    symlink as the final path component — dangling or live — must not
    launder the real target past ``destination_risk``. A not-yet-
    existing final component is appended to the resolved parent
    without strict resolution.
    """
    p = Path(dst).expanduser()
    parent = p.parent
    try:
        resolved_parent = parent.resolve()
    except OSError as exc:
        raise BackGuardError(f"cannot resolve destination: {exc}") from exc
    dst_r = resolved_parent / p.name
    try:
        if os.path.lexists(dst_r):
            dst_r = dst_r.resolve()
    except OSError as exc:
        raise BackGuardError(f"cannot resolve destination: {exc}") from exc
    return (dst_r, dst_r.parent)


def _effective_tier(src: Path) -> Tuple[str, bool]:
    """(tier, bulk) for a copy source.

    A directory is judged by its contents as well as its name: any
    eyes-only file inside makes the whole tree eyes-only; any sensitive
    file inside makes it sensitive; more than ``BULK_DIR_FILE_THRESHOLD``
    files makes it bulk. Enumeration is capped (conservative: hitting
    the cap counts as bulk).
    """
    tier = classify(src)
    if not src.is_dir():
        return tier, False
    n = 0
    n_sensitive = 0
    bulk = False
    try:
        for f in src.rglob("*"):
            if not f.is_file():
                continue
            n += 1
            if n > 2000:
                bulk = True
                break
            t = classify(f)
            if t == "eyes-only":
                return "eyes-only", True
            if t == "sensitive":
                n_sensitive += 1
        if n > BULK_DIR_FILE_THRESHOLD:
            bulk = True
    except OSError:
        return "sensitive", True  # cannot enumerate: conservative
    if n_sensitive > 0 and tier == "normal":
        tier = "sensitive"
    if tier == "eyes-only":
        bulk = True
    return tier, bulk


def _is_bulk_source(src: Path) -> bool:
    if src.is_dir():
        _, bulk = _effective_tier(src)
        return bulk
    return False


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Grants — approval-backed, single-use, bound, expiring (B1)
# ---------------------------------------------------------------------------

_GRANTS_STORE = "back_grants"
_GRANTS_GENESIS = "0" * 64


def _grant_canonical(grant: Dict) -> str:
    body = {k: v for k, v in grant.items() if k not in ("prev", "hash")}
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def _grant_hash(prev_hash: str, grant: Dict) -> str:
    return hashlib.sha256(
        (prev_hash + _grant_canonical(grant)).encode("utf-8")
    ).hexdigest()


def _chain_grants(grants: List[Dict]) -> List[Dict]:
    """(Re)chain every grant record. Called on every save under the store
    lock — any mutation (issue, consume, expiry sweep) re-seals the chain."""
    prev = _GRANTS_GENESIS
    for g in grants:
        g["prev"] = prev
        g["hash"] = _grant_hash(prev, g)
        prev = g["hash"]
    return grants


def _verify_grants(grants: List[Dict]) -> bool:
    prev = _GRANTS_GENESIS
    for g in grants:
        if g.get("prev") != prev:
            return False
        if g.get("hash") != _grant_hash(prev, g):
            return False
        prev = g["hash"]
    return True


def _load_grants() -> List[Dict]:
    data = _paths().load_json_store(_paths().store_path(_GRANTS_STORE))
    grants = data if isinstance(data, list) else []
    if grants and not _verify_grants(grants):
        # Tamper-evident, fail closed: a hand-edited grants store (e.g.
        # flipping "used" back to false) refuses ALL grant validation
        # until the operator reviews. The audit log's back.grant.issued
        # / back.copy.completed records are the cross-check.
        _audit(
            "back.grants.tamper_suspect",
            "backguard",
            {"records": len(grants)},
        )
        raise BackGuardError(
            "back-guard grants store failed its integrity check — "
            "refusing all grant operations until the operator reviews "
            f"{_paths().store_path(_GRANTS_STORE)}"
        )
    return grants


def _save_grants(grants: List[Dict]) -> None:
    _paths().save_json_store(
        _paths().store_path(_GRANTS_STORE), _chain_grants(grants)
    )


def _sweep_expired(grants: List[Dict]) -> List[Dict]:
    """Expired grants stay as records (B6/L10) but are marked expired so
    they can never validate."""
    now = _utcnow_iso()
    for g in grants:
        if not g.get("used") and g.get("expires_at", "") < now:
            g["expired"] = True
    return grants


def _mint_grant(
    actor: str,
    src: str,
    dst: str,
    purpose: str,
    approval_id: str,
) -> Dict:
    """Mint a grant record. Caller must hold the grants store lock."""
    issued = datetime.now(timezone.utc)
    grant = {
        "id": "bg-" + uuid.uuid4().hex,
        "actor": actor,
        "src": src,
        "dst": dst,
        "purpose": purpose,
        "approval_id": approval_id[:16] if approval_id else None,
        "issued_at": issued.isoformat(),
        "expires_at": (issued.timestamp() + GRANT_TTL_SECONDS),
        "used": False,
        "used_at": None,
        "expired": False,
    }
    grant["expires_at"] = datetime.fromtimestamp(
        grant["expires_at"], tz=timezone.utc
    ).isoformat()
    return grant


def issue_grant(
    actor: str,
    src,
    dst,
    purpose: str,
    *,
    approval_action: str = "back.copy",
) -> Dict:
    """Mint an explicit back-guard grant, consuming one approved approval.

    The approval (action ``back.copy`` by default, details
    ``{actor, src, dst, purpose, src_tier, dst_risk}``) must already be
    approved — it is consumed atomically here (single-use, L5-style).
    The details must EXACTLY match what ``request_copy`` requested
    (RED-1 grant mint: exact approval matching — a plainer consume
    must not silently drop the tier/risk fields the approver saw).
    Returns the grant record; the plaintext ``id`` (``bg-<hex>``) is
    the bearer.

    Raises :class:`ApprovalNeeded` when no approved approval is waiting
    (carries a fresh-or-reused ``approval_id``), :class:`BackGuardDenied`
    when the policy explicitly denies the grant.
    """
    actor = _check_actor(actor)
    src_r = _resolve_source(src)
    dst_r, _ = _resolve_dest_parent(dst)
    if not isinstance(purpose, str) or not purpose.strip():
        raise BackGuardError("purpose is required (non-empty string)")
    purpose = purpose.strip()

    # Must mirror request_copy's approval-request details exactly:
    # request_copy asks with {actor, src, dst, purpose, src_tier,
    # dst_risk}, so the consume carries the same shape.
    src_tier, _ = _effective_tier(src_r)
    details = {
        "actor": actor,
        "src": str(src_r),
        "dst": str(dst_r),
        "purpose": purpose,
        "src_tier": src_tier,
        "dst_risk": destination_risk(dst_r),
    }

    from levi.cybrus.approval import ApprovalEngine

    approvals = ApprovalEngine()
    approved = approvals.consume_approved(approval_action, details)
    if approved is None:
        raise _need_approval(actor, approval_action, "back.copy", details)

    p = _paths()
    with p.store_lock(p.store_path(_GRANTS_STORE)):
        grants = _sweep_expired(_load_grants())
        grant = _mint_grant(actor, str(src_r), str(dst_r), purpose, approved["id"])
        grants.append(grant)
        _save_grants(grants)

    _audit(
        "back.grant.issued",
        actor,
        {
            "grant_id": grant["id"][:11],
            "src_tier": classify(src_r),
            "dst_risk": destination_risk(dst_r),
            "purpose": purpose,
            "approval_id": approved["id"][:8],
            "expires_at": grant["expires_at"],
        },
    )
    return grant


def _consume_grant(
    grant_id: str, actor: str, src: str, dst: str, purpose: str
) -> Dict:
    """Validate a grant against every binding and consume it atomically.

    Forgery-shaped inputs (unknown id, wrong actor, src/dst/purpose
    mismatch, expired, already used) all fail closed.
    """
    if not isinstance(grant_id, str) or not grant_id.startswith("bg-"):
        raise BackGuardDenied(
            "unknown or malformed back-guard grant "
            "(grants look like 'bg-<hex>' and are issued by issue_grant())"
        )
    p = _paths()
    with p.store_lock(p.store_path(_GRANTS_STORE)):
        grants = _sweep_expired(_load_grants())
        grant = next((g for g in grants if g.get("id") == grant_id), None)
        if grant is None:
            raise BackGuardDenied("unknown back-guard grant id")
        problems = []
        if grant.get("used"):
            problems.append("already used (single-use)")
        if grant.get("expired"):
            problems.append("expired")
        if grant.get("actor") != actor:
            problems.append("actor mismatch")
        if grant.get("src") != src:
            problems.append("source mismatch")
        if grant.get("dst") != dst:
            problems.append("destination mismatch")
        if grant.get("purpose") != purpose:
            problems.append("purpose mismatch")
        if problems:
            raise BackGuardDenied(
                "back-guard grant refused: " + "; ".join(problems)
            )
        grant["used"] = True
        grant["used_at"] = _utcnow_iso()
        _save_grants(grants)
        return dict(grant)


def _match_pending_approval(action: str, details: Dict) -> Optional[Dict]:
    from levi.cybrus.approval import ApprovalEngine
    from levi.cybrus.gateway import CybrusGateway

    entries = ApprovalEngine().list_all()
    return CybrusGateway._match_approval(entries, action, details, "pending")


def _need_approval(
    actor: str, action: str, resource: str, details: Dict
) -> ApprovalNeeded:
    """Raise-path helper: reuse a pending approval or request a new one,
    audit the gate, and raise :class:`ApprovalNeeded` naming the remedy."""
    from levi.cybrus.approval import ApprovalEngine

    approvals = ApprovalEngine()
    pending = _match_pending_approval(action, details)
    entry = (
        pending
        if pending is not None
        else approvals.request_approval(
            action, actor, resource, "critical", details=details
        )
    )
    event = (
        "back.read.approval_required"
        if action == "back.bulk_read"
        else "back.copy.approval_required"
    )
    _audit(
        event,
        actor,
        {
            "action": action,
            "approval_id": entry["id"][:8],
            "src_tier": details.get("src_tier"),
            "dst_risk": details.get("dst_risk"),
            "store": details.get("store"),
        },
    )
    op = "bulk read" if action == "back.bulk_read" else "copy"
    return ApprovalNeeded(
        entry["id"],
        f"back-guard: this {op} needs explicit human approval "
        f"(approval {entry['id'][:8]}): run "
        f"`levi cybrus approve {entry['id'][:8]} --identity <name>`, "
        f"then retry the same {op} call",
    )


# ---------------------------------------------------------------------------
# The data-egress gate: request_copy / request_archive (B1, B5)
# ---------------------------------------------------------------------------


def _policy_allows_back_copy(actor: str) -> None:
    """Explicit policy deny wins (B6/L3). Default-deny-with-no-rule is NOT
    treated as an objection here: the back-guard's own B1 default-deny is
    the primary gate, and it is stricter than the policy default."""
    from levi.cybrus.policy import PolicyEngine

    decision = PolicyEngine().evaluate(actor, "back.copy", "export")
    if decision.decision == "deny" and decision.matched_rule is not None:
        _audit(
            "back.copy.denied",
            actor,
            {"stage": "policy", "reason": decision.reason},
        )
        raise BackGuardDenied(
            f"back-guard: policy denied this copy for {actor}: "
            f"{decision.reason} (L3: deny always wins — no grant can "
            "override it)"
        )


def request_copy(
    actor: str,
    src,
    dst,
    purpose: str,
    *,
    grant_id: Optional[str] = None,
    content_tier: Optional[str] = None,
) -> Dict:
    """The single sanctioned path for copying data at rest (B5).

    Flow: resolve + classify source → destination risk → explicit policy
    deny check (B6/L3) → grant gate for eyes-only sources, sensitive
    sources headed external, or bulk sensitive sources → perform the copy
    → audit receipt (metadata only, L4).

    Normal (non-sensitive) sources headed internal need no grant: they
    are still audited. Everything else fails closed with the remedy
    named.

    ``content_tier``: override for the source classification, used by
    :func:`request_archive` for its staging file — the gate must judge
    the CONTENT's tier, not the staging path's. Callers that lie here
    are ignoring the module, not using it (residual risk, documented).

    Returns a receipt: ``{copied, actor, src, dst, src_tier, dst_risk,
    bytes, sha256, grant_id, ts}``.
    """
    actor = _check_actor(actor)
    if not isinstance(purpose, str) or not purpose.strip():
        raise BackGuardError("purpose is required (non-empty string)")
    purpose = purpose.strip()
    if content_tier is not None and content_tier not in (
        "eyes-only",
        "sensitive",
        "normal",
    ):
        raise BackGuardError(f"unknown content_tier: {content_tier!r}")
    src_r = _resolve_source(src)
    dst_r, dst_parent = _resolve_dest_parent(dst)
    if _is_under(dst_r, src_r) or dst_r == src_r:
        raise BackGuardError("destination must not be inside the source")

    if content_tier is not None:
        src_tier, bulk = content_tier, _is_bulk_source(src_r)
    else:
        src_tier, bulk = _effective_tier(src_r)
    dst_risk = destination_risk(dst_r)

    _policy_allows_back_copy(actor)

    needs_grant = (
        src_tier == "eyes-only"
        or (src_tier == "sensitive" and (dst_risk == "external" or bulk))
    )

    grant: Optional[Dict] = None
    if needs_grant:
        details = {
            "actor": actor,
            "src": str(src_r),
            "dst": str(dst_r),
            "purpose": purpose,
        }
        if grant_id is not None:
            # Explicit grant path: validate every binding, consume once.
            grant = _consume_grant(
                grant_id, actor, str(src_r), str(dst_r), purpose
            )
        else:
            # Approval-backed path: consume one approved approval and
            # mint+consume its grant in a single motion (single-use, L5).
            # The request and the consume carry IDENTICAL details
            # (RED-1 grant mint: exact approval matching — a plainer
            # consume must not silently drop the tier/risk fields the
            # approver saw).
            from levi.cybrus.approval import ApprovalEngine

            approval_details = {
                **details,
                "src_tier": src_tier,
                "dst_risk": dst_risk,
            }
            approved = ApprovalEngine().consume_approved(
                "back.copy", approval_details
            )
            if approved is None:
                raise _need_approval(
                    actor,
                    "back.copy",
                    f"back.copy:{src_tier}",
                    approval_details,
                )
            p = _paths()
            with p.store_lock(p.store_path(_GRANTS_STORE)):
                grants = _sweep_expired(_load_grants())
                grant = _mint_grant(
                    actor, str(src_r), str(dst_r), purpose, approved["id"]
                )
                grant["used"] = True
                grant["used_at"] = _utcnow_iso()
                grants.append(grant)
                _save_grants(grants)
            _audit(
                "back.grant.issued",
                actor,
                {
                    "grant_id": grant["id"][:11],
                    "src_tier": src_tier,
                    "dst_risk": dst_risk,
                    "purpose": purpose,
                    "approval_id": approved["id"][:8],
                    "auto_consumed": True,
                },
            )

    # -- R6: authorize the copy in the audit trail BEFORE any byte
    # moves. B1 demands grant + audit receipt: when the audit trail is
    # down, the copy must not happen at all. (If the post-copy
    # "completed" receipt later fails, the destination is rolled back.)
    _audit(
        "back.copy.authorized",
        actor,
        {
            "src_name": src_r.name,
            "dst_name": dst_r.name,
            "src_tier": src_tier,
            "dst_risk": dst_risk,
            "bulk": bulk,
            "grant_id": (grant["id"][:11] if grant else None),
            "purpose": purpose,
        },
    )

    # -- perform the copy (all gates passed) -----------------------------
    try:
        dst_parent.mkdir(parents=True, exist_ok=True)
        os.chmod(dst_parent, 0o700)
    except OSError as exc:
        raise BackGuardError(f"cannot prepare destination: {exc}") from exc
    try:
        if src_r.is_dir():
            if dst_r.exists():
                raise BackGuardError(
                    f"destination already exists: {dst_r} "
                    "(back-guard never overwrites: pick a fresh path)"
                )
            # R5: bind the moved tree to the classified tree.
            src_pre_hash = _sha256_dir(src_r)
            shutil.copytree(src_r, dst_r, symlinks=False)
            # copytree does not apply our perms; lock the top dir.
            os.chmod(dst_r, 0o700)
            if _sha256_dir(dst_r) != src_pre_hash:
                _rollback_dst(dst_r)
                raise BackGuardDenied(
                    "back-guard: source changed between classification "
                    "and copy (TOCTOU) — copy refused and rolled back"
                )
            size = sum(
                f.stat().st_size for f in dst_r.rglob("*") if f.is_file()
            )
            digest = src_pre_hash
        else:
            if dst_r.exists():
                raise BackGuardDenied(
                    f"destination already exists: {dst_r} "
                    "(back-guard never overwrites: pick a fresh path)"
                )
            # R5: stream from an fd opened now, not from the path.
            src_pre_hash = _sha256_file(src_r)
            _copy_file_bound(src_r, dst_r, src_pre_hash)
            size = dst_r.stat().st_size
            digest = _sha256_file(dst_r)
    except BackGuardError:
        raise
    except OSError as exc:
        raise BackGuardError(f"copy failed: {exc}") from exc

    receipt = {
        "copied": True,
        "actor": actor,
        "src": str(src_r),
        "dst": str(dst_r),
        "src_tier": src_tier,
        "dst_risk": dst_risk,
        "bulk": bulk,
        "bytes": size,
        "sha256": digest,
        "grant_id": (grant["id"][:11] if grant else None),
        "purpose": purpose,
        "ts": _utcnow_iso(),
    }
    try:
        _audit(
            "back.copy.completed",
            actor,
            {
                k: v
                for k, v in receipt.items()
                if k not in ("src", "dst")  # basenames below; full paths stay local
            }
            | {
                "src_name": src_r.name,
                "dst_name": dst_r.name,
                "grant_id": receipt["grant_id"],
            },
        )
    except Exception:
        # R6: the receipt IS the gate — when it cannot be written, the
        # bytes must not remain at the destination.
        _rollback_dst(dst_r)
        raise
    return receipt


def _rollback_dst(dst_r: Path) -> None:
    """Remove a just-copied destination (R5/R6 rollback). Best effort —
    a failed rollback is itself a loud error upstream, never silent."""
    try:
        if dst_r.is_dir() and not dst_r.is_symlink():
            shutil.rmtree(dst_r)
        else:
            dst_r.unlink(missing_ok=True)
    except OSError:
        pass


def _copy_file_bound(src_r: Path, dst_r: Path, pre_hash: str) -> None:
    """Copy one file binding the moved bytes to the classified bytes (R5).

    Streams from a file descriptor opened NOW — not from the path — so
    a swap of the path between classification and copy (TOCTOU) cannot
    change what moves. The stream hash must equal the classify-time
    ``pre_hash`` and the destination must equal the stream; any
    divergence rolls the destination back and fails closed.
    """
    h = hashlib.sha256()
    try:
        with open(src_r, "rb") as fsrc:
            st = os.fstat(fsrc.fileno())
            with open(dst_r, "wb") as fdst:
                for chunk in iter(lambda: fsrc.read(1 << 20), b""):
                    h.update(chunk)
                    fdst.write(chunk)
    except OSError as exc:
        _rollback_dst(dst_r)
        raise BackGuardError(f"copy failed: {exc}") from exc
    stream_hash = h.hexdigest()
    if stream_hash != pre_hash:
        _rollback_dst(dst_r)
        raise BackGuardDenied(
            "back-guard: source changed between classification and "
            "copy (TOCTOU) — copy refused and rolled back"
        )
    if _sha256_file(dst_r) != stream_hash:
        _rollback_dst(dst_r)
        raise BackGuardError("copy integrity check failed")
    os.chmod(dst_r, 0o600)
    try:
        os.utime(dst_r, ns=(st.st_atime_ns, st.st_mtime_ns))
    except OSError:
        pass


def _sha256_dir(root: Path) -> str:
    """Deterministic digest of a directory tree (relative names + bytes)."""
    h = hashlib.sha256()
    for f in sorted(root.rglob("*")):
        if f.is_file():
            rel = f.relative_to(root).as_posix()
            h.update(b"\x00" + rel.encode("utf-8") + b"\x00")
            with open(f, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
    return h.hexdigest()


def request_archive(
    actor: str,
    src,
    archive_path,
    purpose: str,
    *,
    grant_id: Optional[str] = None,
    fmt: str = "gztar",
) -> Dict:
    """Create a compressed archive of ``src`` through the egress gate.

    The archive is created at a staging path, then moved through
    :func:`request_copy` so the SAME grant + audit rules apply (B5: one
    gate, not two). Returns the copy receipt plus ``archive_format``.
    """
    import tarfile

    actor = _check_actor(actor)
    src_r = _resolve_source(src)
    _TAR_MODES = {"gztar": "w:gz", "bztar": "w:bz2", "xztar": "w:xz", "tar": "w:"}
    if fmt not in _TAR_MODES:
        raise BackGuardError(f"unsupported archive format: {fmt!r}")
    # The gate must judge the CONTENT's tier, not the staging file's —
    # classify the real source before staging (B1: no laundering).
    content_tier, _ = _effective_tier(src_r)

    # Stage the archive inside the cybrus dir (owner-only), then move it
    # through the normal copy gate — one gate, not two.
    staging = _paths().cybrus_dir() / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    os.chmod(staging, 0o700)
    tmp = staging / f"archive-{uuid.uuid4().hex}.tmp"
    try:
        with tarfile.open(tmp, _TAR_MODES[fmt]) as tf:
            tf.add(src_r, arcname=src_r.name)
        os.chmod(tmp, 0o600)
        receipt = request_copy(
            actor,
            tmp,
            archive_path,
            purpose,
            grant_id=grant_id,
            content_tier=content_tier,
        )
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    receipt["archive_format"] = fmt
    return receipt


# ---------------------------------------------------------------------------
# The bulk-read gate (B2)
# ---------------------------------------------------------------------------

_READS_STORE = "back_reads"


def _load_reads() -> Dict:
    data = _paths().load_json_store(_paths().store_path(_READS_STORE))
    return data if isinstance(data, dict) else {}


def _save_reads(payload: Dict) -> None:
    _paths().save_json_store(_paths().store_path(_READS_STORE), payload)


class BulkReadGuard:
    """Sliding-window counter that catches exfiltration-shaped read
    patterns against a sensitive store (B2).

    Wrap a read loop: call :meth:`note_read` once per secret read. Past
    ``threshold`` reads inside ``window_seconds``, it raises
    :class:`BulkReadDenied` naming the remedy — the sanctioned
    :func:`bulk_read_secrets` path with an explicit approval.

    The window is checked per-actor AND store-wide (R7): actor names
    are self-asserted, so rotating them does not escape the gate — the
    aggregate window over ALL readers of the store trips regardless.
    Honest limit: the store name is self-asserted too, so store-name
    rotation is the residual escape.
    """

    def __init__(
        self,
        actor: str,
        store: str = "vault",
        threshold: int = BULK_READ_THRESHOLD,
        window_seconds: int = BULK_READ_WINDOW_SECONDS,
    ):
        self.actor = _check_actor(actor)
        self.store = store
        self.threshold = threshold
        self.window_seconds = window_seconds

    def _prune(self, stamps: List[float]) -> List[float]:
        cutoff = datetime.now(timezone.utc).timestamp() - self.window_seconds
        return [t for t in stamps if t > cutoff]

    def reads_in_window(self) -> int:
        p = _paths()
        with p.store_lock(p.store_path(_READS_STORE)):
            data = _load_reads()
            stamps = self._prune(
                data.get(self.actor, {}).get(self.store, [])
            )
            return len(stamps)

    def note_read(self) -> int:
        """Record one read. Returns the window count. Raises
        :class:`BulkReadDenied` past the threshold — per-actor OR
        store-wide (R7): rotating actor names does not escape the gate,
        because the aggregate window over ALL readers of the store
        trips regardless."""
        now = datetime.now(timezone.utc).timestamp()
        p = _paths()
        with p.store_lock(p.store_path(_READS_STORE)):
            data = _load_reads()
            actor_data = data.setdefault(self.actor, {})
            stamps = self._prune(actor_data.get(self.store, []))
            stamps.append(now)
            actor_data[self.store] = stamps
            _save_reads(data)
            count = len(stamps)
            # R7: aggregate every actor name's reads against this store.
            aggregate = sum(
                len(self._prune(store_reads.get(self.store, [])))
                for store_reads in data.values()
                if isinstance(store_reads, dict)
            )
        if count > self.threshold or aggregate > self.threshold:
            _audit(
                "back.read.bulk_denied",
                self.actor,
                {
                    "store": self.store,
                    "reads_in_window": count,
                    "aggregate_reads_in_window": aggregate,
                    "threshold": self.threshold,
                    "window_seconds": self.window_seconds,
                    "action": "store-wide sliding window: actor name "
                    "rotation does not escape this gate",
                },
            )
            raise BulkReadDenied(
                f"back-guard: {count} reads of the {self.store} store inside "
                f"{self.window_seconds}s exceeds the bulk threshold "
                f"({self.threshold}) — bulk reads need an explicit approval: "
                "request approval for action `back.bulk_read`, then call "
                "bulk_read_secrets()"
            )
        return count

    def reset(self) -> None:
        """Clear this actor's window (e.g. after a granted bulk read)."""
        p = _paths()
        with p.store_lock(p.store_path(_READS_STORE)):
            data = _load_reads()
            if self.actor in data:
                data[self.actor].pop(self.store, None)
                _save_reads(data)


def bulk_read_secrets(
    actor: str,
    count: int,
    purpose: str,
    *,
    store: str = "vault",
) -> Dict:
    """The sanctioned bulk-read path (B2): consume one approved
    ``back.bulk_read`` approval, write the audit entry, return the grant
    receipt. The caller still performs the reads itself — this gate is
    authorization + audit, not a data pipe, so secret values never pass
    through it (L4).

    Raises :class:`ApprovalNeeded` (carries ``approval_id``) when no
    approved approval is waiting.
    """
    actor = _check_actor(actor)
    if not isinstance(count, int) or count <= 0:
        raise BackGuardError("count must be a positive integer")
    if not isinstance(purpose, str) or not purpose.strip():
        raise BackGuardError("purpose is required (non-empty string)")
    purpose = purpose.strip()

    details = {
        "actor": actor,
        "store": store,
        "count": count,
        "purpose": purpose,
    }
    from levi.cybrus.approval import ApprovalEngine

    approvals = ApprovalEngine()
    approved = approvals.consume_approved("back.bulk_read", details)
    if approved is None:
        raise _need_approval(
            actor, "back.bulk_read", f"store.{store}", details
        )
    BulkReadGuard(actor, store=store).reset()
    receipt = {
        "granted": True,
        "actor": actor,
        "store": store,
        "count": count,
        "purpose": purpose,
        "approval_id": approved["id"][:8],
        "ts": _utcnow_iso(),
    }
    _audit("back.read.bulk_granted", actor, receipt)
    return receipt


# ---------------------------------------------------------------------------
# Backup manifests — hash-chained integrity for encrypted archives (B3)
# ---------------------------------------------------------------------------

_MANIFEST_NAME = "manifest.jsonl"
#: Sibling file (→ ``manifest.state.json``) holding the truncation
#: anchor ``{"count", "tip_hash"}`` (R3/R4).
_MANIFEST_STATE_NAME = "manifest.state.json"
_GENESIS_PREV = "0" * 64


def _canonical(record: Dict) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"))


def _hash_entry(prev_hash: str, entry: Dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256((prev_hash + _canonical(body)).encode("utf-8")).hexdigest()


class BackupManifest:
    """Hash-chained manifest for a directory of backup archives (B3).

    Each :meth:`seal` records ``{seq, label, name, sha256, size, ts,
    prev, hash}`` where ``hash = sha256(prev + canonical(entry))``.
    :meth:`verify` re-hashes every archive and walks the chain: flipped
    bytes, deleted archives, and tampered manifest lines are all located
    at the exact entry index where the chain breaks. Every seal also
    anchors ``{count, tip_hash}`` in ``manifest.state.json`` beside the
    manifest (R3/R4): ``verify()`` fails closed on a truncated tail or
    a recomputed chain over tampered archives WITHOUT needing an
    externally supplied ``expected_head``. The manifest head hash is
    additionally written to the Cybrus audit log on every seal, so a
    truncated-or-replaced manifest is detectable via ``expected_head``
    too. Honest limit: a writer who can rewrite BOTH the manifest and
    the anchor file can re-anchor a forgery — full protection needs an
    external anchor (same residual as the audit trail, RED-1 L10).
    """

    def __init__(self, directory) -> None:
        self.dir = Path(directory).expanduser()
        self.dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.dir, 0o700)
        self.path = self.dir / _MANIFEST_NAME
        if not self.path.exists():
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
        else:
            os.chmod(self.path, 0o600)

    # -- writing ---------------------------------------------------------

    def _last(self) -> Tuple[str, int]:
        prev, seq = _GENESIS_PREV, -1
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    prev = rec.get("hash", prev)
                    seq = rec.get("seq", seq)
        except OSError:
            pass
        return prev, seq

    def seal(self, archive_path, label: str) -> Dict:
        """Record a backup archive in the chain. Returns the entry."""
        p = Path(archive_path).expanduser()
        try:
            resolved = p.resolve()
        except OSError as exc:
            raise ManifestError(f"cannot resolve archive path: {exc}") from exc
        if not resolved.is_file():
            raise ManifestError(f"archive is not a file: {resolved}")
        if not isinstance(label, str) or not label.strip():
            raise ManifestError("label is required (non-empty string)")
        label = label.strip()

        prev_hash, last_seq = self._last()
        entry = {
            "seq": last_seq + 1,
            "label": label,
            "name": resolved.name,
            "sha256": _sha256_file(resolved),
            "size": resolved.stat().st_size,
            "ts": _utcnow_iso(),
            "prev": prev_hash,
        }
        entry["hash"] = _hash_entry(prev_hash, entry)
        blob = (_canonical(entry) + "\n").encode("utf-8")
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, blob)
            os.fsync(fd)
        finally:
            os.close(fd)
        # R3/R4: anchor the new head beside the append, atomically.
        _paths().save_json_store(
            self.dir / _MANIFEST_STATE_NAME,
            {"count": entry["seq"] + 1, "tip_hash": entry["hash"]},
        )
        _audit(
            "back.manifest.sealed",
            "backguard",
            {
                "label": label,
                "name": resolved.name,
                "sha256": entry["sha256"],
                "size": entry["size"],
                "seq": entry["seq"],
                "head": entry["hash"],
            },
        )
        return dict(entry)

    # -- reading / verifying ---------------------------------------------

    def entries(self, label: Optional[str] = None) -> List[Dict]:
        out = []
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if label is None or rec.get("label") == label:
                        out.append(rec)
        except OSError:
            pass
        return out

    def head(self) -> Optional[str]:
        _, entries = self._read_indexed()
        return entries[-1][1].get("hash") if entries else None

    def _load_anchor(self) -> Optional[Dict]:
        """The ``{"count", "tip_hash"}`` truncation anchor, or ``None``
        when no anchor exists yet (fresh manifest, or legacy manifest
        predating anchors)."""
        try:
            data = _paths().load_json_store(self.dir / _MANIFEST_STATE_NAME)
        except Exception:
            # Corrupt anchor: quarantined by _paths; treat as missing —
            # verify() fails closed on a non-empty manifest.
            return None
        if isinstance(data, dict) and isinstance(data.get("count"), int):
            return data
        return None

    def reanchor(self) -> Dict:
        """Explicit operator escape hatch for legacy manifests predating
        anchors (mirrors the audit-trail and intel reanchor, RED-1 L10).
        Recomputes the truncation anchor from the current manifest after
        verifying internal links and archive hashes; audit-logs its own
        use. Raises :class:`ManifestError` on a broken chain."""
        _, indexed = self._read_indexed()
        expected_prev = _GENESIS_PREV
        expected_seq = 0
        for _, rec in indexed:
            if rec is None or rec.get("seq") != expected_seq:
                raise ManifestError("cannot reanchor: manifest chain broken")
            if rec.get("prev") != expected_prev:
                raise ManifestError("cannot reanchor: manifest chain broken")
            if rec.get("hash") != _hash_entry(expected_prev, rec):
                raise ManifestError("cannot reanchor: manifest chain broken")
            archive = self.dir / rec.get("name", "")
            if (
                not archive.is_file()
                or _sha256_file(archive) != rec.get("sha256")
            ):
                raise ManifestError("cannot reanchor: archive missing or altered")
            expected_prev = rec["hash"]
            expected_seq += 1
        tip = expected_prev
        _paths().save_json_store(
            self.dir / _MANIFEST_STATE_NAME,
            {"count": len(indexed), "tip_hash": tip},
        )
        _audit(
            "back.manifest.reanchored",
            "backguard",
            {"entries": len(indexed)},
        )
        return {"reanchored": True, "entries": len(indexed)}

    def _read_indexed(self) -> Tuple[int, List[Tuple[int, Optional[Dict]]]]:
        indexed: List[Tuple[int, Optional[Dict]]] = []
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    idx = len(indexed)
                    try:
                        indexed.append((idx, json.loads(line)))
                    except json.JSONDecodeError:
                        indexed.append((idx, None))
        except OSError:
            pass
        return len(indexed), indexed

    def verify(self, expected_head: Optional[str] = None) -> Dict:
        """Walk the chain and re-hash every archive.

        Returns ``{ok, first_bad, head, entries, reason}``. ``first_bad``
        is the 0-based manifest index where the chain first breaks (bad
        entry hash, broken link, bad sequence, unparseable line, missing
        or altered archive file). ``expected_head`` detects truncation or
        wholesale manifest replacement against the head hash recorded in
        the audit log at seal time.
        """
        _, indexed = self._read_indexed()
        expected_prev = _GENESIS_PREV
        expected_seq = 0
        first_bad: Optional[int] = None
        reason = "intact"

        for idx, rec in indexed:
            bad: Optional[str] = None
            if rec is None:
                bad = "unparseable manifest line"
            elif rec.get("seq") != expected_seq:
                bad = f"sequence break (want {expected_seq}, got {rec.get('seq')})"
            elif rec.get("prev") != expected_prev:
                bad = "broken prev link"
            elif rec.get("hash") != _hash_entry(expected_prev, rec):
                bad = "entry hash mismatch (manifest tampered)"
            else:
                archive = self.dir / rec.get("name", "")
                if not archive.is_file():
                    bad = f"archive missing: {rec.get('name')}"
                elif _sha256_file(archive) != rec.get("sha256"):
                    bad = f"archive altered: {rec.get('name')}"
            if bad is not None and first_bad is None:
                first_bad = idx
                reason = bad
            if rec is not None:
                expected_prev = rec.get("hash", expected_prev)
                expected_seq = rec.get("seq", expected_seq) + 1

        head = expected_prev if indexed else _GENESIS_PREV
        ok = first_bad is None
        # R3/R4: the truncation anchor detects a truncated tail or a
        # recomputed chain WITHOUT an externally supplied head. A
        # non-empty manifest with no anchor fails closed (legacy
        # predating anchors; use reanchor() explicitly after review).
        if ok:
            anchor = self._load_anchor()
            count = len(indexed)
            if anchor is None and count > 0:
                ok = False
                reason = (
                    "no truncation anchor for a non-empty manifest "
                    "(legacy; reanchor() explicitly after review)"
                )
            elif anchor is not None and (
                anchor.get("count") != count or anchor.get("tip_hash") != head
            ):
                ok = False
                reason = (
                    "truncation anchor mismatch: manifest was truncated "
                    "or rewritten (anchor count/tip does not match)"
                )
        if ok and expected_head is not None and head != expected_head:
            ok = False
            reason = (
                "head mismatch: manifest was truncated or replaced "
                "(expected head does not match)"
            )

        result = {
            "ok": ok,
            "first_bad": first_bad,
            "head": head,
            "entries": len(indexed),
            "reason": reason,
        }
        if not ok:
            _audit(
                "back.manifest.verify_failed",
                "backguard",
                {
                    "first_bad": first_bad,
                    "entries": len(indexed),
                    "reason": reason,
                },
            )
        return result

    def attest_current(self, label: str, path) -> Dict:
        """Rollback check: does the live file at ``path`` match the latest
        manifest entry for ``label``? A mismatch means the live file was
        swapped (e.g. an older vault blob restored) without a new seal."""
        p = Path(path).expanduser()
        try:
            resolved = p.resolve()
        except OSError as exc:
            raise ManifestError(f"cannot resolve path: {exc}") from exc
        if not resolved.is_file():
            raise ManifestError(f"not a file: {resolved}")
        candidates = [e for e in self.entries(label) if e.get("name")]
        if not candidates:
            return {"matches": False, "latest": None, "reason": "no sealed entry for label"}
        latest = max(candidates, key=lambda e: e.get("seq", -1))
        current = _sha256_file(resolved)
        matches = current == latest.get("sha256")
        result = {
            "matches": matches,
            "latest": {
                "seq": latest.get("seq"),
                "name": latest.get("name"),
                "sha256": latest.get("sha256"),
                "ts": latest.get("ts"),
            },
            "current_sha256": current,
        }
        if not matches:
            _audit(
                "back.manifest.rollback_suspect",
                "backguard",
                {
                    "label": label,
                    "name": resolved.name,
                    "expected_sha256": latest.get("sha256"),
                    "current_sha256": current,
                },
            )
        return result
