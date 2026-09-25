"""Two-way SMS approval loop for the on-device alerter.

Chauncey texts YES <id> / NO <id> from his own number; this loop records the
verdict. It NEVER executes the approved action — execution stays with the
originating operator module. Wired into the alerter drain: an alert item
flagged ``needs_approval`` (with a text-safe category) is texted as
"Reply YES <id> or NO <id>" and registered here.

LAWS (plain words):
  B1 sender lockdown — only texts FROM ``LEVI_ALERT_NUMBER`` (his own
     number) are acted on. Any other sender is ignored, logged, never
     acted on, and never texted back.
  B2 category exclusion — money moves, deletions/destructive actions, and
     anything public are NEVER text-approvable. Such items are texted as
     "needs your word in chat"; no YES/NO is accepted for them, and
     ``request_approval`` refuses them outright.
  B3 no invention — verdicts reference only ids this registry issued.
     Unknown or malformed ids get a "nothing pending" text back.
  B4 expiry auto-deny — pending items expire (default 24h, override with
     ``LEVI_APPROVAL_TTL_HOURS``). Expired items are auto-denied, notified,
     and can never be approved afterwards.
  B5 single verdict — a pending id gets exactly one verdict. Replays and
     duplicates are silently dropped (tracked by message hash).
  B6 records only — this loop marks the registry and the audit log. It
     never executes the underlying action.
  B7 audit trail — every verdict, expiry, and ignored spoof is appended to
     ``~/.levi/device/approvals.log``. The number never appears in any log.
  B8 fail-closed number — no ``LEVI_ALERT_NUMBER`` means nothing is read
     and nothing is sent (exit 2), same as the alerter.
  B9 honest argv — inbound is exactly ``termux-sms-list -l <n>``; outbound
     is exactly ``termux-sms-send -n <number> <text>``.

HONEST LIMIT: SMS sender IDs can be spoofed by carriers. Same-number-only
matching (B1) is a mitigation, not a guarantee — paired with short expiry
(B4), single verdicts (B5), and the audit trail (B7). Money, deletions,
and public actions stay in-chat regardless (B2).

Stdlib only. Entry: ``python3 -m levi.device.approvals --inbox``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# laws (machine-checkable)

LAWS = (
    "B1 sender lockdown: only LEVI_ALERT_NUMBER texts acted on; others "
    "ignored, logged, never answered",
    "B2 category exclusion: money/destructive/public never text-approvable; "
    "request_approval refuses them",
    "B3 no invention: verdicts reference only registry-issued ids",
    "B4 expiry auto-deny: default 24h; expired items denied + notified, "
    "never approvable after",
    "B5 single verdict: one verdict per id; replays silently dropped",
    "B6 records only: registry + audit log marked; actions never executed",
    "B7 audit trail: every verdict/expiry/spoof logged; number never in logs",
    "B8 fail-closed number: no LEVI_ALERT_NUMBER -> nothing read/sent, exit 2",
    "B9 honest argv: termux-sms-list -l <n> in, termux-sms-send -n <n> <t> out",
)

#: Categories that are NEVER text-approvable (B2 — Chauncey's standing law).
EXCLUDED_CATEGORIES = frozenset({"money", "destructive", "public"})

SMS_LIST_BINARY = "termux-sms-list"
SMS_SEND_BINARY = "termux-sms-send"
INBOX_LIMIT = 50
DEFAULT_TTL_HOURS = 24
MAX_BODY_CHARS = 300

_ID_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no I/L/O/0/1
_VERDICT_RE = re.compile(r"(?i)\b(yes|y|approve|approved|no|n|deny|denied)\b")
_ID_RE = re.compile(r"\b(A[A-Z2-9]{5})\b")
_YES_WORDS = {"yes", "y", "approve", "approved"}
# Categories must be simple tokens — a typo'd or sentence-like category
# fails closed to in-chat-only instead of becoming text-approvable.
_SAFE_CAT_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")


def check_laws() -> Dict[str, Any]:
    """Machine proof: exclusion set, id format, and parsers hold."""
    problems: List[str] = []
    for must in ("money", "destructive", "public"):
        if must not in EXCLUDED_CATEGORIES:
            problems.append(f"excluded category {must!r} missing (B2 broken)")
    for safe in ("ops", "info", "reminder"):
        if not is_text_approvable(safe):
            problems.append(f"safe category {safe!r} wrongly excluded")
    if not is_text_approvable("  OPS "):
        problems.append("category normalization broken")
    for bad in ("", "  ", "weird stuff!"):
        if is_text_approvable(bad):
            problems.append(f"category {bad!r} should not be text-approvable")
    seen_ids = {new_id() for _ in range(200)}
    if len(seen_ids) != 200:
        problems.append("id generator collides too often")
    if any(not _ID_RE.fullmatch(i) for i in seen_ids):
        problems.append("generated id fails the inbound id regex")
    # parser spot-checks
    v, i = parse_verdict("YES A7K2Q9 please")
    if v != "yes" or i != "A7K2Q9":
        problems.append("parse_verdict misses 'YES <id>'")
    v, i = parse_verdict("no   aBc123")  # lowercase id must not match
    if v != "no" or i is not None:
        problems.append("parse_verdict accepts malformed id")
    if parse_verdict("hello world") != (None, None):
        problems.append("parse_verdict invents verdicts from chatter")
    if parse_verdict("YES") != ("yes", None):
        problems.append("parse_verdict mishandles bare YES")
    try:
        base = device_dir()
        base.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # noqa: BLE001
        problems.append(f"device dir not writable: {exc}")
    return {"ok": not problems, "laws": list(LAWS), "problems": problems}


# ---------------------------------------------------------------------------
# paths


def home() -> Path:
    return Path(os.environ.get("LEVI_HOME", str(Path.home())))


def device_dir() -> Path:
    return Path(os.environ.get("LEVI_DEVICE_DIR", str(home() / ".levi" / "device")))


def pending_path() -> Path:
    return device_dir() / "approvals_pending.json"


def audit_path() -> Path:
    return device_dir() / "approvals.log"


def seen_path() -> Path:
    return device_dir() / "approvals_seen.jsonl"


def ttl_hours() -> float:
    try:
        return max(0.25, float(os.environ.get("LEVI_APPROVAL_TTL_HOURS", "")))
    except (TypeError, ValueError):
        return float(DEFAULT_TTL_HOURS)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_ts(ts: str) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(ts)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# registry (B3, B5, B6)


class ExcludedCategoryError(ValueError):
    """Category is never text-approvable (B2) — stays in-chat only."""


def normalize_category(category: Any) -> str:
    return str(category or "").strip().lower()


def is_text_approvable(category: Any) -> bool:
    """B2: only explicit, well-formed, non-excluded categories pass.
    Blank, malformed, or excluded categories fail closed to in-chat-only."""
    cat = normalize_category(category)
    return bool(_SAFE_CAT_RE.fullmatch(cat)) and cat not in EXCLUDED_CATEGORIES


def new_id() -> str:
    return "A" + "".join(secrets.choice(_ID_ALPHABET) for _ in range(5))


def load_pending() -> Dict[str, Dict[str, Any]]:
    path = pending_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_pending(pending: Dict[str, Dict[str, Any]]) -> None:
    path = pending_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pending, indent=1), encoding="utf-8")


def request_approval(
    *,
    uid: str,
    title: str,
    source: str,
    category: str,
    body: str = "",
) -> str:
    """Register a pending approval; return its id. B2: excluded or blank
    categories raise ExcludedCategoryError — never registered."""
    cat = normalize_category(category)
    if not is_text_approvable(cat):
        raise ExcludedCategoryError(
            f"category {cat!r} is not text-approvable (in-chat only)"
        )
    pending = load_pending()
    aid = new_id()
    while aid in pending:  # paranoia; 32^5 space, but cheap
        aid = new_id()
    now = datetime.now(timezone.utc)
    pending[aid] = {
        "id": aid,
        "uid": uid,
        "title": title,
        "source": source,
        "category": cat,
        "body": body[:MAX_BODY_CHARS],
        "created": now.isoformat(timespec="seconds"),
        "expires": (now + timedelta(hours=ttl_hours())).isoformat(timespec="seconds"),
        "status": "pending",
    }
    save_pending(pending)
    return aid


def is_expired(rec: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    exp = _parse_ts(rec.get("expires", ""))
    if exp is None:
        return True  # unparseable expiry fails closed: treat as expired
    now = now or datetime.now(timezone.utc)
    return now >= exp


# ---------------------------------------------------------------------------
# audit (B7 — the number never appears)


def audit(verdict: str, rec: Optional[Dict[str, Any]], sender: str = "self",
          note: str = "") -> None:
    """Append one audit line. sender is 'self' or 'other' — never a number."""
    path = audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": _utcnow(),
        "verdict": verdict,
        "sender": sender,
        "id": (rec or {}).get("id", ""),
        "source": (rec or {}).get("source", ""),
        "category": (rec or {}).get("category", ""),
    }
    if note:
        entry["note"] = note
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# inbound parsing (B1, B3)


def normalize_number(raw: Any) -> str:
    digits = re.sub(r"\D", "", str(raw or ""))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]  # US country code
    return digits


def parse_verdict(body: Any) -> Tuple[Optional[str], Optional[str]]:
    """Return ('yes'|'no'|None, id|None). Tolerates extra words; never
    invents — no verdict word or no id-shaped token means None."""
    text = str(body or "")
    m = _VERDICT_RE.search(text)
    verdict = None
    if m:
        verdict = "yes" if m.group(1).lower() in _YES_WORDS else "no"
    i = _ID_RE.search(text)
    return verdict, (i.group(1) if i else None)


def _seen_key(number: str, body: str, date: str) -> str:
    h = hashlib.sha256()
    h.update(f"{number}\n{body}\n{date}".encode("utf-8", "replace"))
    return h.hexdigest()[:32]


def read_seen() -> set:
    path = seen_path()
    if not path.exists():
        return set()
    seen = set()
    with path.open(encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                seen.add(ln)
    return seen


def mark_seen(key: str) -> None:
    path = seen_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(key + "\n")


def read_inbox(limit: int = INBOX_LIMIT) -> List[Dict[str, str]]:
    """Exactly: termux-sms-list -l <n> (B9). Raises TermuxAbsent if the
    binary is missing."""
    if shutil.which(SMS_LIST_BINARY) is None:
        raise TermuxAbsent(f"{SMS_LIST_BINARY} not found")
    proc = subprocess.run(
        [SMS_LIST_BINARY, "-l", str(limit)],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        data = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return []
    out: List[Dict[str, str]] = []
    for rec in data if isinstance(data, list) else []:
        if not isinstance(rec, dict):
            continue
        number = str(rec.get("number") or rec.get("address") or "")
        body = str(rec.get("body") or "")
        if not number:
            continue
        out.append({"number": number, "body": body,
                    "date": str(rec.get("date") or "")})
    return out


class TermuxAbsent(RuntimeError):
    """termux-sms-list missing — console mode only."""


def send_sms(number: str, text: str) -> None:
    """Exactly: termux-sms-send -n <number> <text> (B9)."""
    subprocess.run(
        [SMS_SEND_BINARY, "-n", number, text],
        check=True,
        capture_output=True,
    )


class NoNumberError(RuntimeError):
    """LEVI_ALERT_NUMBER missing — fail closed (B8)."""


def _notify(sender: Callable[[str, str], None], number: str,
            text: str, stats: Dict[str, Any]) -> None:
    sender(number, text)
    stats["texts_sent"] += 1


def sweep_expired(
    number: str,
    *,
    sms_sender: Callable[[str, str], None] = send_sms,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """B4: auto-deny expired pendings, notify, audit. Returns stats."""
    stats: Dict[str, Any] = {"expired": [], "texts_sent": 0}
    pending = load_pending()
    now = now or datetime.now(timezone.utc)
    changed = False
    for aid, rec in list(pending.items()):
        if rec.get("status") != "pending":
            continue
        if is_expired(rec, now):
            rec["status"] = "denied"
            rec["decided"] = _utcnow()
            rec["reason"] = "expired"
            audit("denied", rec, note="expired")
            _notify(sms_sender, number,
                    f"Approval {aid} expired — denied.", stats)
            changed = True
            stats["expired"].append(aid)
    if changed:
        save_pending(pending)
    return stats


def process_inbox(
    number: Optional[str] = None,
    *,
    sms_sender: Callable[[str, str], None] = send_sms,
    list_reader: Callable[[], List[Dict[str, str]]] = read_inbox,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """One inbound pass. B8: raises NoNumberError with no configured number."""
    number = (number if number is not None
              else os.environ.get("LEVI_ALERT_NUMBER", "")).strip()
    if not number:
        raise NoNumberError("number not configured")
    me = normalize_number(number)
    stats: Dict[str, Any] = {
        "approved": [], "denied": [], "ignored_spoof": 0,
        "nothing_pending": 0, "texts_sent": 0,
    }
    # B4 first: expiries are decided before any verdict can land.
    swept = sweep_expired(number, sms_sender=sms_sender, now=now)
    stats["texts_sent"] += swept["texts_sent"]
    pending = load_pending()
    seen = read_seen()
    now = now or datetime.now(timezone.utc)
    changed = False
    for msg in list_reader():
        key = _seen_key(msg["number"], msg["body"], msg["date"])
        if key in seen:
            continue  # B5: replays silently dropped
        mark_seen(key)
        seen.add(key)
        if normalize_number(msg["number"]) != me:
            # B1: not from his number — ignore, log, never answer.
            audit("ignored", None, sender="other", note="sender mismatch")
            stats["ignored_spoof"] += 1
            continue
        verdict, vid = parse_verdict(msg["body"])
        if verdict is None or vid is None:
            continue  # not an approval command — leave his texts alone
        rec = pending.get(vid)
        if rec is None or rec.get("status") != "pending":
            # B3: never issued (or already decided) — say so, once.
            _notify(sms_sender, number,
                    f"Nothing pending for {vid}.", stats)
            stats["nothing_pending"] += 1
            continue
        if normalize_category(rec.get("category")) in EXCLUDED_CATEGORIES:
            # B2 defense-in-depth: should be unregistrable; refuse anyway.
            _notify(sms_sender, number,
                    f"{vid} needs your word in chat.", stats)
            continue
        if is_expired(rec, now):
            rec["status"] = "denied"
            rec["decided"] = _utcnow()
            rec["reason"] = "expired"
            audit("denied", rec, note="expired on verdict")
            _notify(sms_sender, number,
                    f"Approval {vid} expired — denied.", stats)
            changed = True
            continue
        # B5/B6: single verdict, records only — never executes.
        rec["status"] = "approved" if verdict == "yes" else "denied"
        rec["decided"] = _utcnow()
        audit(rec["status"], rec)
        _notify(sms_sender, number,
                f"{rec['status'].capitalize()} {vid}.", stats)
        stats[rec["status"]].append(vid)
        changed = True
    if changed:
        save_pending(pending)
    return stats


# ---------------------------------------------------------------------------
# CLI


def main(argv: Optional[List[str]] = None) -> int:
    argv = argv or sys.argv[1:]
    if "--check-laws" in argv:
        report = check_laws()
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 1
    if "--pending" in argv:
        pending = load_pending()
        for aid, rec in sorted(pending.items()):
            if rec.get("status") == "pending":
                print(f"{aid} [{rec.get('source')}/{rec.get('category')}] "
                      f"{rec.get('title')} expires={rec.get('expires')}")
        return 0
    if "--sweep" in argv or "--inbox" in argv:
        number = os.environ.get("LEVI_ALERT_NUMBER", "").strip()
        if not number:
            print("[approvals] number not configured", file=sys.stderr)  # B8
            return 2
        if "--sweep" in argv and "--inbox" not in argv:
            try:
                stats = sweep_expired(number)
            except TermuxAbsent:
                print("[approvals:console] termux-sms-list missing; "
                      "sweep skipped")
                return 0
            print(f"[approvals] expired={len(stats['expired'])} "
                  f"texts={stats['texts_sent']}")
            return 0
        # --inbox: inbound pass. Inbound is NOT held by quiet hours — the
        # human is awake and texting, so verdicts process immediately.
        try:
            stats = process_inbox(number)
        except TermuxAbsent:
            print("[approvals:console] termux-sms-list missing; "
                  "console mode, nothing processed")
            return 0
        print(f"[approvals] approved={len(stats['approved'])} "
              f"denied={len(stats['denied'])} "
              f"ignored_spoof={stats['ignored_spoof']} "
              f"nothing_pending={stats['nothing_pending']} "
              f"texts={stats['texts_sent']}")
        return 0
    print("usage: python3 -m levi.device.approvals [--inbox|--sweep|--pending|--check-laws]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
