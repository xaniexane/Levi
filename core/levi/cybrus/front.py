"""Cybrus FRONT-GUARD — inbound screening for phishing / scam / social-engineering.

Cybrus is Chauncey's guard on all four sides. FRONT owns the incoming
direction: every inbound email, text, and notification is screened HERE,
through Cybrus, BEFORE it reaches Chauncey — before the DemandPulse
watcher's need extraction, before any surfacing, before any agent acts
on it.

LAWS (binding — declared first, enforced below, machine-checked by
tests/test_cybrus_front.py — honestly named invariant checks; nothing
here is formally proven):
  F1  Every inbound message is screened before it reaches any consumer.
      No message passes to the watcher, a feed, or a human without a
      screening receipt. No receipt, no delivery.
  F2  Suspicious verdicts are flagged + quarantined + audit-logged. A
      suspicious message is NEVER silently delivered and NEVER silently
      dropped: every one lands in the append-only quarantine with a
      record of why.
  F3  Clean verdicts pass through with a signed receipt (message ref,
      channel, rule hits, score, verdict, timestamp, receipt hash).
  F4  Screening stores metadata only: rule ids, signal classes, domain
      roots — never payloads, never secrets, never credential values.
  F5  Fail closed. Any screening error (malformed input, undecodable
      bytes, parser exception) yields a QUARANTINE verdict, never
      pass-through. Quarantine escapes are refused, never assumed. If
      the audit trail itself cannot be written, screening refuses
      (raises) rather than returning a verdict with no trail.
  F6  Quarantine is append-only. Nothing leaves quarantine except
      Chauncey's explicit release: founder-tier identity PLUS the
      identity credential (never a bare name). No auto-release
      timers, no TTL purges, no silent expiry.
  F7  No new egress. FRONT performs zero network egress: it never
      fetches URLs, never "checks" links against outside services,
      never replies, never reports upstream. Read-only screening.
  F8  Coverage, not bypass. FRONT enforces through the existing 12
      Cybrus laws (audit via the tamper-evident AuditEngine, append-only
      stores, no deletion of another organ's state). No exceptions to
      the laws, no new egress paths, no silent allow-lists.
  F9  Deterministic scoring. The same message content yields the same
      score and verdict on every run — no randomness, no hidden model.

Relationship to the DemandPulse watcher (sibling 🪛 owns
``core/levi/demand/watcher.py`` — FRONT never touches that file):
  The watcher fetches raw items (gmail_triage/gmail_read, or injected
  device items) and feeds them to ``ingest_items`` / ``poll_email``.
  The integration seam is :func:`screen_items`: call it between fetch
  and ingest. ``screen_items(channel, items)`` returns only CLEAN /
  WARN items for ingest; QUARANTINE items are held with receipts, so
  the watcher can never seed a demand signal from, or surface, an
  unscreened or hostile message. WARN items carry a ``front_warning``
  banner so a flagged message is never silently delivered.

Threat model (what FRONT catches):
  R01 spoofed display name      "PayPal <billing@paypa1.ru>"
  R02 lookalike / confusable domain in From or Reply-To
  R03 credential-harvest phrasing + a link
  R04 urgency + action pressure ("act now or lose access")
  R05 suspicious links (shorteners, IP hosts, punycode, display/href mismatch)
  R06 risky attachments (.exe .zip .js .html ...)
  R07 requests for secrets/PII ("reply with your code")
  R08 authority impersonation (IRS/FBI/police threats)
  R09 prize/advance-fee bait
  R10 Reply-To domain mismatch vs From
  R11 threat intel (advisory: adds score only, never subtracts):
      primary input is the canonical Cybrus intel store via
      intel.get_indicators() (FF1: the feed feeds FRONT); the legacy
      DemandPulse threat-intel file (dp_threat_feed.py) is kept as a
      working fallback — nothing-thrown-away until Chauncey rules the
      three-paths question.
  R99 screening error -> fail closed (F5)

Stdlib-only, no network. State under ``~/.levi/cybrus/`` (``LEVI_HOME``
override honored). Proof: tests/test_cybrus_front.py.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Standalone-safe imports (same pattern as enforce.py / policy.py)


def _cybrus_module(name: str):
    """Import a sibling cybrus module, with a standalone file fallback."""
    try:
        from levi.cybrus import _paths as _p  # noqa: F401

        import importlib

        return importlib.import_module(f"levi.cybrus.{name}")
    except ImportError:
        import importlib.util

        here = Path(__file__).resolve().parent
        spec = importlib.util.spec_from_file_location(
            f"levi.cybrus.{name}.standalone", here / f"{name}.py"
        )
        if spec is None or spec.loader is None:  # pragma: no cover
            raise ImportError(f"cybrus module {name!r} unavailable") from None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


def _paths():
    return _cybrus_module("_paths")


def _audit_engine():
    """An AuditEngine instance (tamper-evident audit log)."""
    return _cybrus_module("audit").AuditEngine()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Declared laws (F8: machine-readable so tests pin every id)


LAWS = (
    ("F1", "Every inbound message is screened before reaching any consumer; no receipt, no delivery."),
    ("F2", "Suspicious verdicts are flagged + quarantined + audit-logged; never silently delivered, never silently dropped."),
    ("F3", "Clean verdicts pass through with a signed receipt."),
    ("F4", "Screening stores metadata only — never payloads, secrets, or credential values."),
    ("F5", "Fail closed: any screening error yields a QUARANTINE verdict, never pass-through; if the audit trail itself cannot be written, screening refuses (raises) rather than proceeding without a trail."),
    ("F6", "Quarantine is append-only; nothing leaves except Chauncey's explicit release — founder-tier identity PLUS the identity credential, never a bare name."),
    ("F7", "No new egress: FRONT performs zero network egress."),
    ("F8", "Coverage, not bypass: enforces through the existing 12 Cybrus laws, no exceptions."),
    ("F9", "Deterministic scoring: same content yields the same score/verdict every run."),
)

CHANNELS = ("email", "text", "notification")

# Verdict thresholds (score 0-100)
QUARANTINE_AT = 60
WARN_AT = 30

_QUARANTINE_NAME = "front_quarantine.jsonl"
_RELEASES_NAME = "front_releases.jsonl"

# --- rule catalog: (rule_id, weight, description) ----------------------------
RULES = (
    ("R01", 35, "spoofed display name: brand in display name with non-brand domain, or bare brand sender-ID (SMS-style)"),
    ("R02", 35, "lookalike/confusable domain in From or Reply-To"),
    ("R03", 30, "credential-harvest phrasing paired with a link or bare-domain destination"),
    ("R04", 15, "urgency + action pressure language"),
    ("R05", 20, "suspicious link: shortener, IP host (any encoding), punycode, userinfo smuggling, display/href mismatch (markdown and HTML)"),
    ("R06", 25, "risky attachment type (incl. macro-enabled Office formats)"),
    ("R07", 30, "requests secrets or PII (codes, SSN, card numbers, passwords)"),
    ("R08", 25, "authority impersonation (IRS/FBI/police/court threats)"),
    ("R09", 25, "prize / advance-fee / inheritance bait with an action"),
    ("R10", 15, "Reply-To domain differs from From domain"),
    ("R11", 30, "threat intel: sender domain or phrasing matches the canonical intel store (primary) or the legacy DemandPulse intel file (fallback)"),
    ("R99", 100, "screening error: fail closed"),
)
_RULE_IDS = {r[0] for r in RULES}
_RULE_WEIGHT = {r[0]: r[1] for r in RULES}


# ---------------------------------------------------------------------------
# Normalization (catches zero-width and confusable tricks)


_ZERO_WIDTH = re.compile(r"[\u200b-\u200d\ufeff\u2060-\u2064]")

# Confusable homoglyphs -> ascii (cyrillic, greek, leet). Deterministic.
_CONFUSABLES = {
    "а": "a", "е": "e", "і": "i", "о": "o", "р": "p", "с": "c", "х": "x",
    "ѕ": "s", "һ": "h", "ј": "j", "ԁ": "d", "ԛ": "q", "ԝ": "w",
    "α": "a", "ε": "e", "ι": "i", "ο": "o", "ρ": "p", "κ": "k", "ν": "v",
    "0": "o", "1": "l", "3": "e", "5": "s", "7": "t", "8": "b", "9": "g",
    "!": "i", "$": "s", "@": "a", "€": "e", "£": "l",
}


def _normalize(text: str) -> str:
    """NFKC + strip zero-width + map confusables. Deterministic."""
    t = unicodedata.normalize("NFKC", text or "")
    t = _ZERO_WIDTH.sub("", t)
    return "".join(_CONFUSABLES.get(ch, ch) for ch in t.lower())


# Brands whose lookalikes we hunt. Levi-original list, kept small and honest:
# these are the world's most phished marks; absence of a brand here means
# FRONT does not claim lookalike detection for it (F8: no silent defaults —
# the limitation is stated, not hidden).
_BRANDS = (
    "paypal", "google", "gmail", "microsoft", "outlook", "apple", "amazon",
    "chase", "bankofamerica", "wellsfargo", "irs", "facebook", "instagram",
    "netflix", "fedex", "ups", "dhl", "usps", "visa", "mastercard",
)


def _registrable(domain: str) -> str:
    """Best-effort registrable part: last two labels. Never raises."""
    labels = [t for t in (domain or "").lower().strip(".").split(".") if t]
    if len(labels) >= 2:
        return ".".join(labels[-2:])
    return ".".join(labels)


def _edit_distance_one(a: str, b: str) -> bool:
    """True when a and b differ by exactly one single-char edit.

    Counts a single adjacent transposition ("paypla" vs "paypal") as one
    edit (Damerau): transposed brand spellings are the classic lookalike
    primitive (G2), and treating them as distance-2 would let the most
    obvious typosquat through.
    """
    if a == b:
        return False
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        diffs = [i for i, (x, y) in enumerate(zip(a, b, strict=True)) if x != y]
        if len(diffs) == 1:
            return True
        if (
            len(diffs) == 2
            and diffs[1] == diffs[0] + 1
            and a[diffs[0]] == b[diffs[1]]
            and a[diffs[1]] == b[diffs[0]]
        ):
            return True
        return False
    # insertion/deletion
    if la < lb:
        a, b = b, a
    i = j = 0
    skipped = False
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
        elif skipped:
            return False
        else:
            skipped = True
            i += 1
    return True


def _idna_decode(domain: str) -> str:
    """Decode punycode labels to unicode (best effort, never raises)."""
    try:
        return domain.encode("ascii").decode("idna")
    except Exception:
        return domain


def _is_lookalike(domain: str) -> Tuple[bool, Optional[str]]:
    """(True, brand) when the domain is a confusable of a protected brand.

    Checks every dot-label of the full domain, not just the registrable
    part: this catches brand+keyword phishing domains
    (micros0ft-support.com, g00gle-verify.com) AND brand-as-subdomain
    impersonation (paypal.evil.com — G3: the brand appears only as a
    subdomain of somebody else's domain). A brand spelled exactly inside
    its OWN registrable name (microsoft-support.com, login.paypal.com)
    is not flagged — that is the owner's own keyword use, not
    impersonation. Near-miss spellings (confusables, transpositions)
    are flagged wherever they appear.
    """
    labels = [t for t in (domain or "").lower().strip(".").split(".") if t]
    if len(labels) < 2:
        return False, None
    sld_idx = len(labels) - 2  # the registrable second-level label
    for idx, label in enumerate(labels):
        name = _idna_decode(label)
        raw_lower = name.lower()
        candidates = {raw_lower}
        candidates.update(t for t in re.split(r"[^a-z0-9]+", raw_lower) if t)
        for raw in candidates:
            norm = _normalize(raw)
            for brand in _BRANDS:
                if norm == brand:
                    if raw == brand and idx == sld_idx:
                        # Exact brand spelling inside its own registrable
                        # name: the owner's own keyword, not impersonation.
                        continue
                    return True, brand
                if (
                    len(norm) >= 5
                    and len(brand) >= 5
                    and _edit_distance_one(norm, brand)
                ):
                    return True, brand
    return False, None


# ---------------------------------------------------------------------------
# Signal patterns


_URGENCY = (
    "act now", "immediate action", "expires", "within 24 hours", "24 hours",
    "account suspended", "account locked", "locked out", "final notice",
    "verify immediately", "urgent", "asap", "limited time", "don't delay",
    "respond immediately", "last chance", "your account will be",
)

_CRED_PHRASES = (
    "sign in", "log in", "login", "verify your account", "verify your password",
    "update your payment", "confirm your identity", "reset your password",
    "validate your account", "re-activate", "reactivate your",
    "security check", "unusual activity",
)

_SECRET_REQUESTS = (
    "ssn", "social security", "reply with your code", "send your code",
    "verification code", "one-time code", "confirm your password",
    "send your password", "your password", "credit card number",
    "card number", "cvv", "bank account", "routing number", "pin number",
)

_AUTHORITY = (
    "irs", "fbi", "federal bureau", "police", "court", "arrest warrant",
    "social security administration", "subpoena", "legal action",
    "sheriff", "department of justice",
)

_PRIZE = (
    "you won", "you've won", "winner", "congratulations", "lottery",
    "inheritance", "claim your prize", "claim your reward", "million dollars",
    "beneficiary",
)

_RISKY_EXTS = frozenset({
    ".exe", ".scr", ".bat", ".cmd", ".js", ".jse", ".vbs", ".vbe", ".ps1",
    ".msi", ".com", ".pif", ".hta", ".html", ".htm", ".zip", ".rar",
    ".7z", ".iso", ".img", ".lnk", ".jar", ".cpl", ".gadget", ".wsf",
    # Macro-enabled Office formats — the classic malicious-attachment vector.
    ".docm", ".dotm", ".xlsm", ".xltm", ".xlsb", ".pptm", ".potm", ".ppsm",
})

_SHORTENERS = frozenset({
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly",
    "rb.gy", "cutt.ly", "s.id", "shorturl.at", "t.ly", "rebrand.ly",
})

_URL_RE = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)", re.IGNORECASE)
_HTML_LINK_RE = re.compile(
    r"<a\s[^>]*?href\s*=\s*[\"'](https?://[^\"'<>\s]+)[\"'][^>]*>(.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_TEXT_DOM_RE = re.compile(r"(?<![\w@-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}", re.IGNORECASE)

# Bare-domain discovery exclusions: common file extensions that _TEXT_DOM_RE
# would otherwise mistake for domains ("see report.pdf"). Documented
# tradeoff: a phish naming a payload "invoice.pdf" as a bare domain is
# missed by discovery — but R06 still catches it as an attachment.
_BARE_DOM_EXCLUDE_EXTS = frozenset({
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv",
    "png", "jpg", "jpeg", "gif", "mp3", "mp4", "zip", "log",
})


def _is_ip_literal(host: str) -> bool:
    """True for IP-literal hosts in any common phisher encoding.

    Dotted quads, decimal (http://2130706433/), hex (http://0x7f000001/),
    and dotted octal. Best effort, never raises.
    """
    h = (host or "").lower().split(":")[0]
    if not h:
        return False
    try:
        if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", h):
            return True
        if h.isdigit() and int(h) <= 0xFFFFFFFF:
            return True
        if re.fullmatch(r"0x[0-9a-f]{1,8}", h):
            return True
        parts = h.split(".")
        if len(parts) == 4 and all(
            re.fullmatch(r"0[0-7]+", p) for p in parts
        ):
            return True
    except (ValueError, OverflowError):
        return False
    return False


def _url_host(url: str) -> str:
    """Host of a URL with any userinfo stripped (never raises)."""
    m = re.match(r"https?://([^/\s:]+)", url, re.IGNORECASE)
    authority = m.group(1) if m else ""
    # Strip userinfo: http://paypal.com@evil.example/ -> evil.example
    if "@" in authority:
        authority = authority.rsplit("@", 1)[1]
    return authority.lower()


def _url_has_userinfo(url: str) -> bool:
    """True when the URL authority carries userinfo (credential smuggling)."""
    m = re.match(r"https?://([^/\s]+)", url, re.IGNORECASE)
    return bool(m) and "@" in m.group(1)


def _discover_urls(subject: str, body: str) -> List[str]:
    """All link destinations: scheme URLs, HTML <a href>, and bare domains.

    Bare scheme-less domains (evil-login.example) are surfaced as
    http:// candidates so R03/R05 see them. Best effort, never raises.
    """
    text = f"{subject}\n{body}"
    found: List[str] = []
    seen_hosts = set()

    def _add(url: str) -> None:
        host = _url_host(url)
        if url and url not in found and host not in seen_hosts:
            found.append(url)
            seen_hosts.add(host)

    for m in _URL_RE.finditer(text):
        _add(m.group(0).rstrip(").,;!?'\""))
    for m in _HTML_LINK_RE.finditer(text):
        _add(m.group(1))
    for m in _TEXT_DOM_RE.finditer(text):
        dom = m.group(0).lower()
        ext = dom.rsplit(".", 1)[-1]
        if ext in _BARE_DOM_EXCLUDE_EXTS:
            continue
        _add(f"http://{dom}")
    return found


def _html_display_mismatch(subject: str, body: str) -> bool:
    """True when an HTML <a> shows one domain but links another."""
    text = f"{subject}\n{body}"
    for m in _HTML_LINK_RE.finditer(text):
        href, inner = m.group(1), m.group(2)
        display = _HTML_TAG_RE.sub("", inner)
        hdom = _registrable(_url_host(href))
        tmatch = _TEXT_DOM_RE.search(display)
        tdom = _registrable(tmatch.group(0)) if tmatch else ""
        if hdom and tdom and tdom != hdom:
            return True
    return False


# ---------------------------------------------------------------------------
# Screening


def _msg_ref(message: Dict[str, Any]) -> str:
    """Stable sha256 identity of a message's screenable content."""
    parts = [
        str(message.get("channel") or ""),
        str(message.get("from") or ""),
        str(message.get("reply_to") or ""),
        str(message.get("subject") or ""),
        str(message.get("body") or ""),
        ",".join(sorted(str(u) for u in (message.get("urls") or []))),
        ",".join(sorted(str(a) for a in (message.get("attachments") or []))),
    ]
    return hashlib.sha256("\x00".join(parts).encode("utf-8", "replace")).hexdigest()


def screen_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Screen one inbound message.

    Fail-closed (F5): any screening error yields a QUARANTINE verdict —
    the function returns a verdict for every input EXCEPT when the
    audit trail itself cannot be written. F2 binds every verdict to an
    audit record; proceeding with a QUARANTINE and no trail would drop
    the law silently, so an unwritable audit log raises instead of
    returning.

    ``message`` keys: id, channel, from, reply_to, subject, body, urls,
    attachments. Missing keys are treated as absent signals, never as
    evidence of cleanliness.

    Returns the screening receipt: message_id, channel, verdict
    (CLEAN|WARN|QUARANTINE), score, rules (hit ids, sorted),
    msg_ref, receipt_hash, ts, and for QUARANTINE a quarantine record.
    """
    try:
        if not isinstance(message, dict):
            # F5: None, a bare string, a list — none of these is a
            # message. A non-message is a screening error, never a clean
            # bill of health (G5/G6): fail closed to R99 quarantine.
            raise TypeError(
                "screen_message() requires a message dict, got %s"
                % type(message).__name__
            )
        return _screen_inner(dict(message))
    except Exception as exc:  # F5: any screening failure quarantines
        receipt = _base_receipt(message if isinstance(message, dict) else {})
        receipt["verdict"] = "QUARANTINE"
        receipt["score"] = 100
        receipt["rules"] = ["R99"]
        receipt["error"] = f"{type(exc).__name__}"
        receipt["receipt_hash"] = _receipt_hash(receipt)
        try:
            _store_quarantine(receipt, {"channel": str((message or {}).get("channel") or "unknown")})
        except Exception:
            # The quarantine store itself is down: the verdict is still
            # returned (screen_message must not swallow the caller's only
            # signal), marked honestly. The audit write below is NOT
            # guarded — F2 fail-closed: no trail, no silent proceed.
            receipt["quarantine_write"] = "failed"
        _audit(receipt)
        return receipt


def _base_receipt(message: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "message_id": str(message.get("id") or ""),
        "channel": str(message.get("channel") or "unknown"),
        "ts": _utcnow_iso(),
        "verdict": "CLEAN",
        "score": 0,
        "rules": [],
        "msg_ref": _msg_ref(message),
    }


def _receipt_hash(receipt: Dict[str, Any]) -> str:
    body = {
        k: receipt[k]
        for k in ("message_id", "channel", "ts", "verdict", "score", "rules",
                  "msg_ref", "intel_digest")
        if k in receipt
    }
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _screen_inner(message: Dict[str, Any]) -> Dict[str, Any]:
    channel = str(message.get("channel") or "unknown")
    if channel not in CHANNELS:
        channel = "unknown"
    sender = str(message.get("from") or "")
    reply_to = str(message.get("reply_to") or "")
    subject = str(message.get("subject") or "")
    body = str(message.get("body") or "")
    urls = [str(u) for u in (message.get("urls") or [])]
    urls += [u for u in _discover_urls(subject, body) if u not in urls]
    attachments = [str(a) for a in (message.get("attachments") or [])]

    norm_body = _normalize(subject + "\n" + body)
    hits: List[str] = []

    # R02/R10 — sender / reply-to domain analysis
    from_addr = sender
    m = re.search(r"<([^<>@\s]+@[^<>@\s]+)>", sender)
    if m:
        from_addr = m.group(1)
    if "@" not in from_addr:
        from_addr = ""
    from_domain = from_addr.split("@")[-1] if "@" in from_addr else ""
    like, _brand = _is_lookalike(from_domain) if from_domain else (False, None)
    if like:
        hits.append("R02")
    rt_domain = reply_to.split("@")[-1] if "@" in reply_to else ""
    if rt_domain and not like:
        like_rt, _ = _is_lookalike(rt_domain)
        if like_rt:
            hits.append("R02")
    if rt_domain and from_domain and _registrable(rt_domain) != _registrable(from_domain):
        hits.append("R10")

    # R01 — display-name brand spoof (email form: "PayPal <x@y.ru>").
    # The display name is squashed (separators removed) before the brand
    # substring check, so "Pay Pal", "Pay-Pal", "P.a.y.P.a.l" cannot
    # evade it (G1) — the same trick mail clients fall for.
    display = sender[: m.start()] if m else ""
    disp_norm = _normalize(display)
    disp_squashed = re.sub(r"[^a-z0-9]", "", disp_norm)
    for brand in _BRANDS:
        if (brand in disp_norm or brand in disp_squashed) and from_domain:
            if _normalize(_registrable(from_domain).split(".")[0]) != brand:
                hits.append("R01")
                break

    # R01 (SMS form) — bare sender-ID with no @-address: on the text
    # channel the sender IS the display name, so a bare protected brand
    # ("PayPal") is brand impersonation by itself.
    if not from_addr and sender.strip() and "R01" not in hits:
        s_norm = _normalize(sender.strip())
        s_tokens = {s_norm} | {t for t in re.split(r"[^a-z0-9]+", s_norm) if t}
        for brand in _BRANDS:
            if any(
                tok == brand or (len(tok) >= 5 and _edit_distance_one(tok, brand))
                for tok in s_tokens
            ):
                hits.append("R01")
                break

    # R04 — urgency + action pressure
    if any(p in norm_body for p in _URGENCY):
        hits.append("R04")

    # R03 — credential harvest phrasing + link
    if urls and any(p in norm_body for p in _CRED_PHRASES):
        hits.append("R03")

    # R05 — suspicious links
    for u in urls:
        host = _url_host(u)
        if not host:
            continue
        if _url_has_userinfo(u):
            # http://paypal.com@evil.example/ — userinfo credential smuggling
            hits.append("R05")
            break
        if host in _SHORTENERS or _registrable(host) in _SHORTENERS:
            hits.append("R05")
            break
        if _is_ip_literal(host):
            hits.append("R05")
            break
        if host.startswith("xn--") or ".xn--" in host:
            hits.append("R05")
            break
    if "R05" not in hits:
        for _text, href in _MD_LINK_RE.findall(subject + "\n" + body):
            hdom = _registrable(_url_host(href))
            tmatch = _TEXT_DOM_RE.search(_text)
            tdom = _registrable(tmatch.group(0)) if tmatch else ""
            if hdom and tdom and tdom != hdom:
                hits.append("R05")
                break
    if "R05" not in hits and _html_display_mismatch(subject, body):
        hits.append("R05")

    # R06 — risky attachments. Trailing dots and whitespace are stripped
    # before the extension check (G4): Windows ignores them ("invoice.exe "
    # executes as invoice.exe), so the gate must judge what the OS will
    # actually run, not the literal string.
    for a in attachments:
        name = a.lower().rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        name = name.strip().rstrip(".")
        ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
        if ext in _RISKY_EXTS:
            hits.append("R06")
            break

    # R07 — secret/PII requests
    if any(p in norm_body for p in _SECRET_REQUESTS):
        hits.append("R07")

    # R08 — authority impersonation
    if any(p in norm_body for p in _AUTHORITY):
        hits.append("R08")

    # R09 — prize bait
    if any(p in norm_body for p in _PRIZE):
        hits.append("R09")

    # R11 — threat intel (FF1). PRIMARY: the canonical Cybrus intel
    # store via intel.get_indicators(); FALLBACK: the legacy DemandPulse
    # intel file (dp_threat_feed.py) — kept working per the
    # nothing-thrown-away law until Chauncey rules the three-paths
    # question. T4/advisory: intel can ADD to the score, never subtract,
    # never force CLEAN. Best-effort and never raising: missing/corrupt
    # intel degrades to "no intel". Fail-closed on malformed intel: bad
    # entries are refused, never guessed — a corrupt store can only ever
    # ADD nothing, so the gate never widens (the screen itself still
    # fails closed per F5/R99).
    intel_digest = None
    try:
        intel = _load_threat_intel()
        if intel:
            intel_digest = (
                str(intel.get("digest") or intel.get("source_digest") or "")[:16]
                or None
            )
            if from_domain and _registrable(from_domain) in (intel.get("domains") or []):
                hits.append("R11")
            if "R11" not in hits:
                kw = [k for k in (intel.get("keywords") or []) if k]
                if kw and any(k in norm_body for k in kw):
                    hits.append("R11")
    except Exception:
        intel_digest = None

    rules = sorted(set(hits))
    score = min(100, sum(_RULE_WEIGHT[r] for r in rules))
    if score >= QUARANTINE_AT:
        verdict = "QUARANTINE"
    elif score >= WARN_AT:
        verdict = "WARN"
    else:
        verdict = "CLEAN"

    receipt = _base_receipt(message)
    receipt["channel"] = channel
    receipt["verdict"] = verdict
    receipt["score"] = score
    receipt["rules"] = rules
    receipt["intel_digest"] = intel_digest  # None when no intel consulted
    receipt["receipt_hash"] = _receipt_hash(receipt)

    if verdict == "QUARANTINE":
        _store_quarantine(receipt, {
            "channel": channel,
            "sender_domain": _registrable(from_domain) if from_domain else "",
            "subject_head": subject[:80],
        })
    _audit(receipt)
    return receipt


# ---------------------------------------------------------------------------
# Quarantine store — append-only, metadata only (F2/F4/F6)


def _store_path(name: str) -> Path:
    d = _paths().cybrus_dir()
    p = d / name
    if not p.exists():
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
    else:
        os.chmod(p, 0o600)
    return p


def _redact_subject(text: str) -> str:
    """Redact credential-shaped values from a subject line (F4).

    Subjects routinely carry one-time codes, PINs, and partial secrets.
    Runs of 4+ digits and password-adjacent assignments are replaced
    before the subject head ever reaches the quarantine store.
    """
    t = text or ""
    t = re.sub(r"\d{4,}", "[#]", t)
    t = re.sub(
        r"(?i)(password|passwd|secret|token|code|pin|ssn)\s*[:=]\s*\S+",
        r"\1: [#]",
        t,
    )
    return t[:80]


def _store_quarantine(receipt: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, Any]:
    """Append one quarantine record. Metadata only — never bodies (F4)."""
    record = {
        "ts": receipt["ts"],
        "msg_ref": receipt["msg_ref"],
        "message_id": receipt["message_id"],
        "channel": meta.get("channel", ""),
        "sender_domain": meta.get("sender_domain", ""),
        "subject_head": _redact_subject(meta.get("subject_head", "")),
        "verdict": "QUARANTINE",
        "score": receipt["score"],
        "rules": list(receipt["rules"]),
        "receipt_hash": receipt["receipt_hash"],
    }
    p = _store_path(_QUARANTINE_NAME)
    blob = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, blob)
        os.fsync(fd)
    finally:
        os.close(fd)
    return record


def quarantine_list() -> List[Dict[str, Any]]:
    """Read the quarantine (metadata records only)."""
    p = _paths().cybrus_dir() / _QUARANTINE_NAME
    out: List[Dict[str, Any]] = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return out


def _verify_founder_credential(identity_store, authorizer: str, credential: Optional[str]) -> None:
    """Founder-tier AND identity-credential check for quarantine release.

    A bare name is not a release authority: the caller must present the
    founder identity's credential (the same password the HITL approval
    flow prompts for), verified constant-time against the stored
    pbkdf2-sha256 hash reference. Missing, empty, or wrong credential ->
    TierError. Nothing about the credential is logged or persisted here.
    """
    from levi.cybrus.identity import TierError

    _cybrus_module("identity").require_founder(identity_store, authorizer)
    if not credential:
        raise TierError(
            "quarantine release requires the founder identity credential, "
            "not just the founder name"
        )
    stored = identity_store.get_credential(authorizer)
    if stored is None or not _cybrus_module("factory").verify_password(
        credential, stored
    ):
        raise TierError("founder credential verification failed")


def release(
    item_ref: str,
    *,
    identity_store=None,
    authorizer: str = "",
    credential: Optional[str] = None,
) -> Dict[str, Any]:
    """Release a quarantined item — Chauncey's explicit release only (F6).

    Requires BOTH the founder-tier identity (``authorizer``) AND that
    identity's credential (``credential``), verified against the stored
    hash — a bare name releases nothing. The release is recorded in an
    append-only release log; the quarantine record itself is never
    mutated (F6, nothing-thrown-away).
    """
    if identity_store is None:
        identity_store = _cybrus_module("identity").IdentityStore()
    _verify_founder_credential(identity_store, authorizer, credential)
    matches = [r for r in quarantine_list() if r.get("msg_ref") == item_ref]
    if not matches:
        raise KeyError(f"no quarantined item with ref {item_ref[:16]}…")
    record = {
        "ts": _utcnow_iso(),
        "msg_ref": item_ref,
        "released_by": authorizer,
        "rule_basis": "F6 explicit founder release",
    }
    p = _store_path(_RELEASES_NAME)
    blob = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, blob)
        os.fsync(fd)
    finally:
        os.close(fd)
    _audit_engine().append(
        "cybrus.front.release", "cybrus-front",
        {"msg_ref": item_ref, "released_by": authorizer, "verdict": "RELEASED"},
    )
    return record


# ---------------------------------------------------------------------------
# Audit (F2/F8: through the tamper-evident AuditEngine; metadata only)


def _audit(receipt: Dict[str, Any]) -> None:
    """Write the screening audit record. Deliberately unguarded.

    F2 binds every verdict to an audit trail. If the trail cannot be
    written, the failure propagates (fail closed) rather than returning
    a verdict with no record — a silently dropped law is worse than a
    loud refusal.
    """
    _audit_engine().append(
        "cybrus.front.screen",
        "cybrus-front",
        {
            "msg_ref": receipt["msg_ref"],
            "message_id": receipt["message_id"],
            "channel": receipt["channel"],
            "verdict": receipt["verdict"],
            "score": receipt["score"],
            "rules": list(receipt["rules"]),
            "receipt_hash": receipt["receipt_hash"],
        },
    )


# ---------------------------------------------------------------------------
# Threat intel — R11's data source.
#
# PRIMARY: the canonical Cybrus intel store (intel.py): indicators
# ingested there are converted here into R11's matching shape.
# FALLBACK: the legacy DemandPulse intel file (dp_threat_feed.py):
# kept as a working fallback per the nothing-thrown-away law; Chauncey
# alone rules the three-paths question (see FF1 receipt).
#
# NEVER raises: missing/corrupt intel -> {} ("no intel"). Fail-closed on
# malformed intel: bad entries are refused, never guessed.


def _indicators_to_r11(indicators: Any) -> Dict[str, Any]:
    """Defensive conversion: intel-store indicators -> R11 matching shape.

    Indicators carry ``markers`` (domain roots, keyword phrases, or both
    mixed — the alliance contract does not separate them). A marker that
    parses as a domain becomes a domain root for sender-domain matching;
    every other non-empty marker becomes a normalized keyword phrase for
    phrasing matching. Non-dict entries, non-string markers, and markers
    over 256 chars are REFUSED, never trusted — bad intel can only ever
    add nothing.
    """
    domains: set = set()
    keywords: set = set()
    ids: List[str] = []
    if not isinstance(indicators, list):
        return {}
    for ind in indicators:
        if not isinstance(ind, dict):
            continue
        iid = ind.get("indicator_id")
        if isinstance(iid, str) and iid:
            ids.append(iid)
        markers = ind.get("markers")
        if not isinstance(markers, (list, tuple)):
            continue
        for m in markers:
            if not isinstance(m, str):
                continue
            mm = m.strip()
            if not mm or len(mm) > 256:
                continue
            if _TEXT_DOM_RE.fullmatch(mm):
                domains.add(_registrable(mm))
            else:
                keywords.add(mm.lower())
    if not domains and not keywords:
        return {}
    digest = hashlib.sha256(
        ("cybrus-intel-store|" + "|".join(sorted(set(ids)))).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "format": "cybrus.intel_indicators/1",
        "domains": sorted(domains),
        "keywords": sorted(keywords),
        "digest": digest,
        "source": "cybrus-intel-store",
    }


def _load_threat_intel() -> Dict[str, Any]:
    """Load FRONT threat intel. NEVER raises: missing/corrupt -> {}.

    Primary: the canonical intel store via ``intel.get_indicators()``
    (FF1: the feed feeds FRONT). Only indicators from the DemandPulse
    publisher namespace are honored (N1): source names are self-asserted
    at ingest (FF5 — no intake authentication), so the R11 consumer
    applies a source routing policy here. Attacker-named sources stay
    inert: they are stored and served by get_indicators, but they never
    influence a verdict. Fallback: the legacy ``dp_threat_feed.load_intel()``
    file. Advisory only (T4): no intel degrades to no additive score;
    the screen itself still fails closed per F5/R99.
    """
    try:
        intel_mod = _cybrus_module("intel")
        indicators = intel_mod.get_indicators()
    except Exception:
        indicators = None
    if indicators:
        trusted = [
            ind for ind in indicators if _trusted_intel_source(ind.get("source"))
        ]
        primary = _indicators_to_r11(trusted) if trusted else {}
        if primary:
            return primary
        # Indicators existed but nothing was usable (or none from a
        # trusted publisher): refuse them and fall through to the legacy
        # fallback rather than guessing.
    try:
        return _cybrus_module("dp_threat_feed").load_intel() or {}
    except Exception:
        return {}


#: Publisher namespaces whose threat intel R11 honors. Source names are
#: self-asserted at ingest — there is no intake authentication (FF5) —
#: so this is a consumer-side routing policy, not authentication. The
#: canonical publisher is ``demandpulse:threat-feed``
#: (core/levi/demandpulse/threat_feed.py).
_TRUSTED_INTEL_SOURCE_PREFIXES = ("demandpulse:",)


def _trusted_intel_source(source: Any) -> bool:
    """True when an intel source belongs to a trusted publisher namespace."""
    s = str(source or "").strip().lower()
    return any(s.startswith(prefix) for prefix in _TRUSTED_INTEL_SOURCE_PREFIXES)


# ---------------------------------------------------------------------------
# Integration seam for the DemandPulse watcher (sibling-owned file)


def _watcher_item_to_message(channel: str, item: Dict[str, Any]) -> Dict[str, Any]:
    """Map the watcher's item shape {id, text, ts?} to a screen message.

    The watcher fetches raw text only; sender-based rules (R01/R02/R10)
    are inert for these items, text-based rules still fire. This is the
    documented reason the sibling should prefer the full
    ``screen_message`` shape once sender metadata is available.
    """
    return {
        "id": str(item.get("id") or ""),
        "channel": channel,
        "from": str(item.get("from") or ""),
        "reply_to": str(item.get("reply_to") or ""),
        "subject": str(item.get("subject") or ""),
        "body": str(item.get("text") or ""),
        "urls": list(item.get("urls") or []),
        "attachments": list(item.get("attachments") or []),
    }


def screen_items(
    channel: str, items: Sequence[Dict[str, Any]]
) -> Dict[str, Any]:
    """Screen a batch of watcher-style items: the integration seam.

    Call between the watcher's fetch step and ``ingest_items`` /
    ``poll_email`` ingest:

        screened = front.screen_items("email", fetched_items)
        receipt = ingest_items(dp, state, "email", screened["clean"])

    Every item gets a screening receipt (F1). QUARANTINE items are held
    back — never passed to ingest (F2). WARN items are passed through
    WITH a ``front_warning`` banner attached so a flagged message is
    never silently delivered (F2/F3). CLEAN items pass unchanged with
    their receipts available.
    """
    if channel not in CHANNELS:
        raise ValueError(f"unknown channel {channel!r}")
    clean: List[Dict[str, Any]] = []
    quarantined: List[Dict[str, Any]] = []
    warned: List[Dict[str, Any]] = []
    receipts: List[Dict[str, Any]] = []
    for item in items:
        receipt = screen_message(_watcher_item_to_message(channel, item or {}))
        receipts.append(receipt)
        if receipt["verdict"] == "QUARANTINE":
            quarantined.append(receipt)
        elif receipt["verdict"] == "WARN":
            flagged = dict(item)
            flagged["front_warning"] = {
                "verdict": "WARN",
                "score": receipt["score"],
                "rules": list(receipt["rules"]),
                "receipt_hash": receipt["receipt_hash"],
                "note": "Flagged by Cybrus FRONT-GUARD: treat links and "
                        "requests in this message with suspicion.",
            }
            clean.append(flagged)
            warned.append(receipt)
        else:
            clean.append(dict(item))
    return {
        "channel": channel,
        "items": len(items),
        "clean": clean,
        "quarantined": quarantined,
        "warned": warned,
        "receipts": receipts,
    }


def describe_posture() -> Dict[str, Any]:
    """Honest backend posture (cf. enforce.py L12)."""
    return {
        "module": "levi.cybrus.front",
        "direction": "FRONT (inbound)",
        "laws": [law_id for law_id, _ in LAWS],
        "rules": [r[0] for r in RULES],
        "thresholds": {"quarantine_at": QUARANTINE_AT, "warn_at": WARN_AT},
        "egress": "none — stdlib-only, zero network",
        "threat_intel": {
            "primary": "levi.cybrus.intel (get_indicators) — FF1",
            "fallback": "levi.cybrus.dp_threat_feed (front_intel.json)",
            "advisory": "adds score only, never subtracts; malformed intel refused",
            "note": "which intel path is canonical beyond FRONT's input is Chauncey's ruling",
        },
        "quarantine": {
            "store": str(_paths().cybrus_dir() / _QUARANTINE_NAME),
            "records": len(quarantine_list()),
            "release": "founder-tier explicit release only (F6)",
        },
        "integration": "call screen_items() between watcher fetch and ingest",
    }
