"""DemandPulse license-key entitlements — owner-operated, fail-closed.

Flow (HQ Decision 4, approved 2026-09-24):
  1. Customer pays $6 manually (Cash App $DirectDepositDaemon; PayPal fallback).
  2. Chauncey confirms the payment in Cash App.
  3. Chauncey runs ``levi demandpulse entitle --email <email> --months 1``
     → append-only record: email, license key ``DP-XXXX-XXXX-XXXX``,
     paid_from, paid_through, payment_ref, status=active. Every issuance
     writes a receipt.
  4. Key delivered to the customer's email.
  5. Customer runs ``demandpulse activate --email <email> --key <key>``.
     Local check: key format valid, status active, paid_through >= today.
     Fail-closed: no record / wrong key / expired = no access.
  6. Renewal: same flow; paid_through extends, key stays the same.
  7. Refund (<= 7 days from payment): status -> revoked, refund logged,
     $6 returned same rail within 3 days (the return itself is manual).

LAWS (invariants — the tests prove each one):
  * Key-format law: every key matches DP-XXXX-XXXX-XXXX over an unambiguous
    alphabet, crypto-random (secrets), unique within the store.
  * Append-only law: records.jsonl is append-only; receipts are write-once.
    Revoke/refund/renew are NEW records; current state is derived from the
    latest record per email. Nothing is edited or deleted, ever.
  * Fail-closed law: check() is active only when a record exists, the key
    matches, status is active, and paid_through >= today. Everything else
    is inactive with a reason.
  * Grace law: 1-7 days past paid_through -> in_grace=True but active=False
    (still fail-closed); past 7 days -> expired.
  * Refund-window law: refund() only within 7 days of paid_from, else
    RefundWindowExpired.
  * Key-stability law: renewing an ACTIVE entitlement keeps the key;
    re-issuing after a revoke mints a new key (a revoked key never revives).
  * Money-separation law: this module never charges and never touches a
    processor — it records owner-confirmed payments only. charge() stays
    dark in payments.py.

THE ENFORCEMENT FLAG (owner gate — read this before touching it):
  ENFORCEMENT_ENABLED = False. All check paths are INFORMATIONAL by default:
  they report the verdict but nothing in the product gates on it.
  require_active_entitlement() implements the enforcing path (raises
  EntitlementRequired) but is NOT wired into any product command.
  Flipping this flag to True needs Chauncey's SEPARATE explicit word —
  deliberately not bundled with the HQ Decision 4 design approval.

Stdlib only.
"""

from __future__ import annotations

import json
import os
import re
import secrets
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# THE ENFORCEMENT FLAG — owner gate. Do NOT flip without Chauncey's separate
# explicit word. When False (default), check()/activate() report the verdict
# but never block the product. When True (his word only), product entry
# points must call require_active_entitlement().
# ---------------------------------------------------------------------------
ENFORCEMENT_ENABLED = False

# Policy constants — HQ Decisions 3/4. Named, never magic numbers.
MONTH_DAYS = 30
GRACE_DAYS = 7
REFUND_DAYS = 7

KEY_PREFIX = "DP"
KEY_GROUPS = 3
KEY_GROUP_LEN = 4
# Unambiguous alphabet: no 0/O, no 1/I.
KEY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
KEY_RE = re.compile(r"^DP-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

STATUS_ACTIVE = "active"
STATUS_REVOKED = "revoked"

EVENT_ISSUED = "issued"
EVENT_RENEWED = "renewed"
EVENT_REVOKED = "revoked"
EVENT_REFUNDED = "refunded"


class EntitlementError(Exception):
    """Base error for entitlement operations (bad input, bad state)."""


class RefundWindowExpired(EntitlementError):
    """Raised when a refund is requested past the 7-day window."""


class EntitlementRequired(EntitlementError):
    """Raised by the enforcing path when access is not permitted.

    Only reachable when ENFORCEMENT_ENABLED is True (owner's word).
    """


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

def store_dir(home: Optional[Path] = None) -> Path:
    """Directory holding records.jsonl + receipts/.

    ``DEMANDPULSE_HOME`` wins (tests, bundles); default is ``~/.demandpulse``.
    The owner-side store is deliberately separate from any product data dir —
    it is the owner's book, not the customer's.
    """
    base = Path(home) if home is not None else None
    if base is None:
        env = os.environ.get("DEMANDPULSE_HOME") or ""
        base = Path(env) if env.strip() else Path.home() / ".demandpulse"
    return base / "entitlements"


def records_path(home: Optional[Path] = None) -> Path:
    return store_dir(home) / "records.jsonl"


def receipts_dir(home: Optional[Path] = None) -> Path:
    return store_dir(home) / "receipts"


def _ensure_store(home: Optional[Path] = None) -> Path:
    d = store_dir(home)
    d.mkdir(parents=True, exist_ok=True)
    receipts_dir(home).mkdir(parents=True, exist_ok=True)
    return d


def read_records(home: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Read every record, oldest first. Strict: a corrupt line raises."""
    path = records_path(home)
    if not path.is_file():
        return []
    records: List[Dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EntitlementError(
                f"corrupt entitlement record at {path}:{lineno}: {exc}"
            ) from exc
        if not isinstance(rec, dict) or "email" not in rec or "seq" not in rec:
            raise EntitlementError(
                f"malformed entitlement record at {path}:{lineno}"
            )
        if not isinstance(rec["seq"], int) or isinstance(rec["seq"], bool):
            raise EntitlementError(
                f"malformed entitlement record at {path}:{lineno}: "
                f"seq must be an int, got {rec['seq']!r}"
            )
        records.append(rec)
    records.sort(key=lambda r: r["seq"])
    return records


def latest_for(records: List[Dict[str, Any]], email: str) -> Optional[Dict[str, Any]]:
    """Newest record for an email (emails stored normalized)."""
    email = normalize_email(email)
    matches = [r for r in records if r.get("email") == email]
    return matches[-1] if matches else None


def _next_seq(records: List[Dict[str, Any]]) -> int:
    return (records[-1]["seq"] + 1) if records else 1


def _write_record(record: Dict[str, Any], home: Optional[Path] = None) -> Dict[str, Any]:
    """Append one record (append-only law) + write its receipt."""
    _ensure_store(home)
    with records_path(home).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    receipt = {
        "receipt_for_seq": record["seq"],
        "event": record["event"],
        "email": record["email"],
        "key": record["key"],
        "paid_from": record["paid_from"],
        "paid_through": record["paid_through"],
        "payment_ref": record.get("payment_ref", ""),
        "status": record["status"],
        "note": record.get("note", ""),
        "recorded_at": record["ts"],
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = re.sub(r"[^a-z0-9]+", "-", record["email"].lower()).strip("-")
    rpath = receipts_dir(home) / f"{stamp}-{record['seq']:06d}-{record['event']}-{slug}.json"
    rpath.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    return record


# ---------------------------------------------------------------------------
# Validation + key generation
# ---------------------------------------------------------------------------

def normalize_email(email: str) -> str:
    """Strip + lowercase. Raises EntitlementError on bad format."""
    if not isinstance(email, str):
        raise EntitlementError(f"email must be a string, got {type(email).__name__}")
    cleaned = email.strip().lower()
    if not EMAIL_RE.match(cleaned):
        raise EntitlementError(f"invalid email address: {email!r}")
    return cleaned


def validate_key_format(key: str) -> str:
    """Strip + uppercase; must match DP-XXXX-XXXX-XXXX. Raises on mismatch."""
    if not isinstance(key, str):
        raise EntitlementError(f"key must be a string, got {type(key).__name__}")
    cleaned = key.strip().upper()
    if not KEY_RE.match(cleaned):
        raise EntitlementError(
            "invalid license key format: expected DP-XXXX-XXXX-XXXX "
            f"(got {key!r})"
        )
    return cleaned


def generate_key(taken: Optional[set] = None) -> str:
    """Mint a fresh DP-XXXX-XXXX-XXXX key, crypto-random, collision-free."""
    taken = taken or set()
    for _ in range(1000):
        groups = [
            "".join(secrets.choice(KEY_ALPHABET) for _ in range(KEY_GROUP_LEN))
            for _ in range(KEY_GROUPS)
        ]
        key = f"{KEY_PREFIX}-{'-'.join(groups)}"
        if key not in taken:
            return key
    raise EntitlementError("could not mint a unique license key (store exhausted?)")


def _validate_months(months: Any) -> int:
    if isinstance(months, bool) or not isinstance(months, int):
        raise EntitlementError(f"months must be an integer >= 1 (got {months!r})")
    if months < 1:
        raise EntitlementError(f"months must be >= 1 (got {months})")
    return months


# ---------------------------------------------------------------------------
# Issue / renew / revoke / refund
# ---------------------------------------------------------------------------

def _new_record(
    seq: int,
    event: str,
    email: str,
    key: str,
    paid_from: str,
    paid_through: str,
    payment_ref: str,
    status: str,
    note: str = "",
) -> Dict[str, Any]:
    return {
        "seq": seq,
        "event": event,
        "email": email,
        "key": key,
        "paid_from": paid_from,
        "paid_through": paid_through,
        "payment_ref": payment_ref,
        "status": status,
        "note": note,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def issue(
    email: str,
    months: int = 1,
    payment_ref: str = "",
    note: str = "",
    home: Optional[Path] = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Issue a key (new customer) or renew (active customer, same key).

    New issuance requires the owner to have confirmed the $6 payment —
    payment_ref should name it (e.g. "cashapp $buyer 2026-09-24").
    Renewal extends paid_through from max(today, current paid_through).
    """
    email = normalize_email(email)
    months = _validate_months(months)
    today = today or date.today()
    records = read_records(home)
    current = latest_for(records, email)
    taken = {r["key"] for r in records if r.get("key")}

    if current is not None and current.get("status") == STATUS_ACTIVE:
        # Renewal: same key, paid_through extends (key-stability law).
        key = current.get("key")
        if not key:
            raise EntitlementError(
                f"active record for {email} has no key — refusing renewal"
            )
        base = max(_parse_date(current.get("paid_through"), where="renewal base"), today)
        event = EVENT_RENEWED
    else:
        # New issuance (or re-issue after revoke: fresh key, old one stays dead).
        key = generate_key(taken)
        base = today
        event = EVENT_ISSUED

    paid_through = (base + timedelta(days=MONTH_DAYS * months)).isoformat()
    record = _new_record(
        seq=_next_seq(records),
        event=event,
        email=email,
        key=key,
        paid_from=today.isoformat(),
        paid_through=paid_through,
        payment_ref=payment_ref,
        status=STATUS_ACTIVE,
        note=note,
    )
    return _write_record(record, home)


def revoke(
    email: str,
    reason: str = "",
    home: Optional[Path] = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Revoke the current entitlement. Record kept; the key stays dead."""
    email = normalize_email(email)
    today = today or date.today()
    records = read_records(home)
    current = latest_for(records, email)
    if current is None:
        raise EntitlementError(f"no entitlement record for {email}")
    if current.get("status") != STATUS_ACTIVE:
        raise EntitlementError(
            f"no active entitlement to revoke for {email} "
            f"(latest status: {current.get('status')})"
        )
    record = _new_record(
        seq=_next_seq(records),
        event=EVENT_REVOKED,
        email=email,
        key=current["key"],
        paid_from=current["paid_from"],
        paid_through=current["paid_through"],
        payment_ref=current.get("payment_ref", ""),
        status=STATUS_REVOKED,
        note=reason or "revoked by owner",
    )
    return _write_record(record, home)


def refund(
    email: str,
    home: Optional[Path] = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Refund within 7 days of payment: status -> revoked, refund logged.

    The $6 return itself is manual (same rail, within 3 days) — this records
    the decision. Past the window, raises RefundWindowExpired: no refund due,
    the month's access was delivered.
    """
    email = normalize_email(email)
    today = today or date.today()
    records = read_records(home)
    current = latest_for(records, email)
    if current is None or current.get("status") != STATUS_ACTIVE:
        raise EntitlementError(f"no active entitlement to refund for {email}")
    paid_from = _parse_date(current.get("paid_from"), where="refund window")
    if (today - paid_from).days > REFUND_DAYS:
        raise RefundWindowExpired(
            f"refund window closed for {email}: paid {current['paid_from']} "
            f"({(today - paid_from).days} days ago > {REFUND_DAYS} days)"
        )
    record = _new_record(
        seq=_next_seq(records),
        event=EVENT_REFUNDED,
        email=email,
        key=current["key"],
        paid_from=current["paid_from"],
        paid_through=current["paid_through"],
        payment_ref=current.get("payment_ref", ""),
        status=STATUS_REVOKED,
        note="refunded in full ($6) within 7-day window; return same rail within 3 days",
    )
    return _write_record(record, home)


def _parse_date(value: Any, where: str = "record") -> date:
    """Parse an ISO date from a record. A bad date is a named
    EntitlementError — never a raw ValueError from fromisoformat."""
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError) as exc:
        raise EntitlementError(
            f"bad date {value!r} in {where}: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Check (fail-closed) + the enforcing path (gated)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CheckResult:
    """Verdict of a license check. Fail-closed: active is False unless
    every condition holds."""

    email: str
    key_match: bool
    active: bool
    in_grace: bool
    status: str
    paid_through: str
    reason: str

    def to_record(self) -> Dict[str, Any]:
        return {
            "email": self.email,
            "key_match": self.key_match,
            "active": self.active,
            "in_grace": self.in_grace,
            "status": self.status,
            "paid_through": self.paid_through,
            "reason": self.reason,
            "enforced": ENFORCEMENT_ENABLED,
        }


def check(
    email: str,
    key: str,
    home: Optional[Path] = None,
    today: Optional[date] = None,
) -> CheckResult:
    """Fail-closed entitlement check against the owner records.

    INFORMATIONAL by default (ENFORCEMENT_ENABLED=False): reports the
    verdict; nothing in the product gates on it until the owner's word.
    """
    email = normalize_email(email)
    try:
        key = validate_key_format(key)
    except EntitlementError:
        return CheckResult(
            email=email, key_match=False, active=False, in_grace=False,
            status="unknown", paid_through="",
            reason="key format invalid",
        )
    today = today or date.today()
    current = latest_for(read_records(home), email)
    if current is None:
        return CheckResult(
            email=email, key_match=False, active=False, in_grace=False,
            status="unknown", paid_through="",
            reason="no entitlement record for this email",
        )
    if current.get("key") != key:
        return CheckResult(
            email=email, key_match=False, active=False, in_grace=False,
            status=current.get("status", "unknown"),
            paid_through=current.get("paid_through", ""),
            reason="key does not match the record",
        )
    if current.get("status") != STATUS_ACTIVE:
        return CheckResult(
            email=email, key_match=True, active=False, in_grace=False,
            status=current.get("status", "unknown"),
            paid_through=current.get("paid_through", ""),
            reason=f"entitlement {current.get('status')}",
        )
    try:
        paid_through = _parse_date(current.get("paid_through"), where="entitlement record")
    except EntitlementError as exc:
        # Fail-closed law: a malformed record can never grant access —
        # inactive with a reason, never a raw KeyError/ValueError.
        return CheckResult(
            email=email, key_match=True, active=False, in_grace=False,
            status=current.get("status", "unknown"),
            paid_through=str(current.get("paid_through", "")),
            reason=f"entitlement record malformed: {exc}",
        )
    if today <= paid_through:
        return CheckResult(
            email=email, key_match=True, active=True, in_grace=False,
            status=STATUS_ACTIVE, paid_through=current["paid_through"],
            reason="active",
        )
    overdue = (today - paid_through).days
    if 1 <= overdue <= GRACE_DAYS:
        return CheckResult(
            email=email, key_match=True, active=False, in_grace=True,
            status=STATUS_ACTIVE, paid_through=current["paid_through"],
            reason=f"in {GRACE_DAYS}-day grace (day {overdue}); renew to restore access",
        )
    return CheckResult(
        email=email, key_match=True, active=False, in_grace=False,
        status=STATUS_ACTIVE, paid_through=current["paid_through"],
        reason="paid month ended and grace lapsed — access paused until renewed",
    )


def require_active_entitlement(
    email: str,
    key: str,
    home: Optional[Path] = None,
    today: Optional[date] = None,
) -> CheckResult:
    """The ENFORCING path: raises EntitlementRequired unless active.

    NOT wired into any product command. Becomes live only when
    ENFORCEMENT_ENABLED is True — which needs Chauncey's separate
    explicit word. Until then, call check() for the informational verdict.
    """
    result = check(email, key, home=home, today=today)
    if not ENFORCEMENT_ENABLED:
        raise EntitlementError(
            "enforcement is not enabled: require_active_entitlement() is "
            "gated on Chauncey's separate explicit word (ENFORCEMENT_ENABLED "
            "is False). Use check() for the informational verdict."
        )
    if not result.active:
        raise EntitlementRequired(
            f"no active entitlement for {email}: {result.reason}"
        )
    return result


def list_entitlements(
    status: str = "all",
    home: Optional[Path] = None,
    today: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """Current state per email, derived from latest records.

    status filter: all | active | grace | expired | revoked.
    """
    status = status.strip().lower()
    if status not in ("all", "active", "grace", "expired", "revoked"):
        raise EntitlementError(
            f"unknown status filter {status!r} "
            "(all|active|grace|expired|revoked)"
        )
    today = today or date.today()
    records = read_records(home)
    emails = sorted({r["email"] for r in records})
    out: List[Dict[str, Any]] = []
    for email in emails:
        current = latest_for(records, email)
        if current is None:
            continue  # cannot happen (emails derived from records); skip, never assert
        if current.get("status") == STATUS_REVOKED:
            state = "revoked"
        else:
            verdict = check(email, current.get("key", ""), home=home, today=today)
            if verdict.active:
                state = "active"
            elif verdict.in_grace:
                state = "grace"
            else:
                state = "expired"
        if status != "all" and state != status:
            continue
        out.append(
            {
                "email": email,
                "key": current.get("key", ""),
                "state": state,
                "paid_from": current.get("paid_from", ""),
                "paid_through": current.get("paid_through", ""),
                "payment_ref": current.get("payment_ref", ""),
                "last_event": current.get("event", ""),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Customer-side activation (ships in the customer bundle)
# ---------------------------------------------------------------------------

def activation_path(home: Optional[Path] = None) -> Path:
    """Where the customer's own activation lives (their machine, their file)."""
    base = Path(home) if home is not None else None
    if base is None:
        env = os.environ.get("DEMANDPULSE_HOME") or ""
        base = Path(env) if env.strip() else Path.home() / ".demandpulse"
    return base / "activation.json"


def validate_activation(
    email: str, key: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Validate + store the customer's email/key on their own machine.

    This checks FORMAT only (the owner's records live with the owner).
    It never grants anything by itself: while ENFORCEMENT_ENABLED is False
    the product runs ungated and this is a stored claim, honestly labeled.
    """
    email = normalize_email(email)
    key = validate_key_format(key)
    path = activation_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "email": email,
        "key": key,
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "enforcement": "informational — product ungated until the owner "
                       "enables enforcement (owner gate)",
    }
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def read_activation(home: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """The stored activation claim, if the customer has activated."""
    path = activation_path(home)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        # ValueError covers JSONDecodeError AND UnicodeDecodeError (bad
        # bytes) — a corrupt claim file reads as no claim, never a crash.
        return None
    return data if isinstance(data, dict) else None
