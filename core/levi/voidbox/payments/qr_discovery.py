"""Void Box QR — discovery and distribution surface.

QR codes are the discovery and distribution surface of Void Box: scan a
code and you land in a discovery feed, install the app, or follow a
creator's referral. This module builds those payloads on top of the
vendored encoder in :mod:`levi.voidbox.payments.qr`.

What a payload carries: ids + a signature. Never content, never
personal data, never amounts (D1). Every payload is tamper-evident:
an HMAC-SHA256 tag (128-bit truncated, stated honestly) over a
versioned domain string, verified with a constant-time compare.
Anything that fails verification is refused by name — never silently
accepted (D2).

The signing key is keeper-held: derived from the passphrase via the
same master-key derivation as the rooms store (scrypt where
available, PBKDF2 fallback), with a dedicated HKDF subkey
``"vb-qr-sign-v1"``. No key material in the clear on disk (D7).

SI side: every public entry calls ``require_adult()`` FIRST — the
Plaiground gate mechanics are untouched, tracks never merge with the
SFW side, and nothing explicit appears in code, tests, or docstrings
(D3).

Distribution URLs are Chauncey's: the download base is unset until he
provides it, and any attempt to resolve a download URL before then is
refused with the remedy named — never invented (D4).

LAWS (D-qr):
- D1 — Discovery/distribution payloads carry ids + signature only:
  never content, never personal data, never amounts.
- D2 — Tamper-evident: 128-bit truncated HMAC-SHA256 tag, constant-time
  verification; tampered payloads refused by name.
- D3 — require_adult() FIRST on every public entry; Plaiground gate
  mechanics untouched.
- D4 — Distribution hosts are Chauncey's: unset -> refused with the
  remedy, never invented.
- D5 — Referral codes are unguessable (96 bits from secrets); the
  attribution ledger is append-only JSONL, feeding the tier-cut
  accounting (who referred whom).
- D6 — Payload-size discipline: every payload fits QR version 4 EC-M
  (62 bytes byte-mode); oversize refused at build time, never
  truncated.
- D7 — Keeper-held signing key: passphrase-derived, memory-only while
  unlocked; nothing keylike on disk in the clear.

ONE ORGANISM: this module is an organ of Levi. All of Legion is Levi —
one organism, many organs; we are raising him.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from levi.cybrus._paths import atomic_write_bytes
from levi.cybrus.veil import _derive_master, _hkdf, _kdf_default, _utcnow
from levi.plaiground.gate import require_adult
from levi.voidbox.payments.qr import QRCode

#: Declared laws, machine-readable.
LAWS = (
    ("D1", "Payloads carry ids + signature only: never content, personal data, or amounts."),
    ("D2", "Tamper-evident: 128-bit truncated HMAC-SHA256, constant-time verify; tampered refused by name."),
    ("D3", "require_adult() FIRST on every public entry; Plaiground mechanics untouched."),
    ("D4", "Distribution hosts are Chauncey's: unset -> refused with remedy, never invented."),
    ("D5", "Referral codes unguessable (96 bits); append-only JSONL attribution ledger for tier-cut accounting."),
    ("D6", "Every payload fits QR v4 EC-M (62 bytes); oversize refused at build, never truncated."),
    ("D7", "Keeper-held signing key: passphrase-derived, memory-only while unlocked."),
)

# Version-4 EC-M byte-mode capacity (see qr.py Q2).
_MAX_PAYLOAD_BYTES = 62

#: Discovery surface name -> one-letter code in the payload.
SURFACES = {
    "dating": "D",
    "creators": "C",
    "chatrooms": "H",
    "classifieds": "K",
    "resale": "R",
    "trending": "T",
    "channels": "X",
    "collection": "F",
}
_SURFACE_BY_CODE = {v: k for k, v in SURFACES.items()}

_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,12}$")
_CHANNEL_RE = re.compile(r"^[A-Za-z0-9._-]{1,8}$")
_CODE_RE = re.compile(r"^[A-Za-z0-9]{12}$")
_TAG_RE = re.compile(r"^[0-9a-f]{32}$")

_SIGN_DOMAIN = "vb-qr-sign-v1"
_TAG_BYTES = 16  # 128-bit truncated HMAC tag, stated in D2.


class QRError(ValueError):
    """Base discovery/distribution QR failure."""


class QRTamperError(QRError):
    """A scanned payload failed signature verification — refused by name."""


class QRDistributionError(QRError):
    """Distribution config missing or invalid (D4)."""


# ---------------------------------------------------------------------------
# Paths — ~/.levi/voidbox/payments/, LEVI_HOME honored like rooms.py
# ---------------------------------------------------------------------------


def voidbox_payments_dir(home: Optional[Path] = None) -> Path:
    """Resolve ``<home>/.levi/voidbox/payments/``. The adult gate is
    consulted first — there is no unauthenticated path to this store."""
    require_adult(home)
    if home is not None:
        root = Path(home)
    else:
        raw = os.environ.get("LEVI_HOME", "").strip()
        root = Path(raw).expanduser() if raw else Path.home()
    d = root / ".levi" / "voidbox" / "payments"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


# ---------------------------------------------------------------------------
# DiscoveryQr — the keeper's QR mint
# ---------------------------------------------------------------------------


class DiscoveryQr:
    """Mint and verify Void Box discovery/distribution QR payloads.

    ``DiscoveryQr(passphrase, home=None)`` — the passphrase derives the
    master key (memory-hard scrypt where available, PBKDF2 fallback,
    pinned per store like veil.py); the signing subkey is HKDF'd off
    it and lives in memory only while unlocked.
    """

    def __init__(self, passphrase: str, home: Optional[Path] = None):
        self._gate_home = home
        self._require_adult()  # D3: FIRST, before any other work
        if not isinstance(passphrase, str) or not passphrase:
            raise QRError("DiscoveryQr needs a non-empty passphrase.")
        store_dir = voidbox_payments_dir(home)
        salt_file = store_dir / "qr-sign.salt"
        if salt_file.exists():
            salt = salt_file.read_bytes()
        else:
            salt = secrets.token_bytes(16)
            atomic_write_bytes(salt_file, salt)
            os.chmod(salt_file, 0o600)
        master = _derive_master(passphrase, salt, _kdf_default())
        self._sign_key = _hkdf(master, salt, _SIGN_DOMAIN.encode("utf-8"), 32)
        master = bytearray(len(master))  # best-effort zeroize
        self._home = home
        self._dir = store_dir

    # -- internals ------------------------------------------------------

    def _require_adult(self) -> None:
        require_adult(self._gate_home)

    def _tag(self, domain: str, body: str) -> str:
        return hmac.new(
            self._sign_key, (domain + ":" + body).encode("utf-8"), hashlib.sha256
        ).hexdigest()[: _TAG_BYTES * 2]

    @staticmethod
    def _check_size(text: str, what: str) -> str:
        # D6: refused at build time, never truncated.
        if len(text.encode("utf-8")) > _MAX_PAYLOAD_BYTES:
            raise QRError(
                "%s payload is %d bytes; the QR surface caps at %d "
                "(v4 EC-M). Shorten the id — it is never truncated."
                % (what, len(text.encode("utf-8")), _MAX_PAYLOAD_BYTES)
            )
        return text

    def lock(self) -> None:
        """Best-effort zeroize of the in-memory signing key."""
        self._sign_key = bytes(len(self._sign_key))

    # -- discovery ------------------------------------------------------

    def discovery_text(self, surface: str, ref_id: str) -> str:
        """Signed deep-link payload for a discovery surface.

        ``surface`` is one of dating, creators, chatrooms, classifieds,
        resale, trending, channels, collection. ``ref_id`` is a short
        feed/cursor handle (1-12 chars) — an id, never content (D1).
        Scanning opens the right discovery view.
        """
        self._require_adult()
        if surface not in SURFACES:
            raise QRError(
                "unknown discovery surface %r: use one of %s."
                % (surface, sorted(SURFACES))
            )
        if not isinstance(ref_id, str) or not _ID_RE.match(ref_id):
            raise QRError(
                "invalid ref_id %r: 1-12 chars of [A-Za-z0-9._-] — an id, "
                "never content (D1)." % (ref_id,)
            )
        code = SURFACES[surface]
        tag = self._tag("vb-disc:v1", code + ":" + ref_id)
        return self._check_size(
            "voidbox://d/%s/%s/%s" % (code, ref_id, tag), "discovery"
        )

    def discovery_qr(self, surface: str, ref_id: str) -> QRCode:
        """QR symbol for a discovery payload."""
        self._require_adult()
        return QRCode(self.discovery_text(surface, ref_id), "M")

    def parse_discovery(self, text: str) -> Tuple[str, str]:
        """Verify a scanned discovery payload -> (surface, ref_id).

        Raises QRTamperError on any mismatch — refused by name (D2).
        """
        self._require_adult()
        parts = text.split("/")
        if len(parts) != 6 or parts[0] != "voidbox:" or parts[1] != "" \
                or parts[2] != "d":
            raise QRTamperError(
                "not a Void Box discovery payload: %r." % (text[:40],)
            )
        _, _, _, code, ref_id, tag = parts
        surface = _SURFACE_BY_CODE.get(code)
        if surface is None or not _ID_RE.match(ref_id) \
                or not _TAG_RE.match(tag):
            raise QRTamperError("malformed discovery payload — refused.")
        want = self._tag("vb-disc:v1", code + ":" + ref_id)
        if not hmac.compare_digest(want, tag):
            raise QRTamperError(
                "discovery payload signature mismatch for surface %r — "
                "tampered or forged, refused." % (surface,)
            )
        return surface, ref_id

    # -- app distribution -------------------------------------------------

    def app_text(self, channel: str) -> str:
        """Signed app-distribution entry payload: ``voidbox://get/<ch>/<tag>``.

        The client resolves this against the configured distribution
        base (Chauncey's — D4). Scanning starts download/onboarding.
        """
        self._require_adult()
        if not isinstance(channel, str) or not _CHANNEL_RE.match(channel):
            raise QRError(
                "invalid channel %r: 1-8 chars of [A-Za-z0-9._-]."
                % (channel,)
            )
        tag = self._tag("vb-get:v1", channel)
        return self._check_size(
            "voidbox://get/%s/%s" % (channel, tag), "app distribution"
        )

    def app_qr(self, channel: str) -> QRCode:
        """QR symbol for app distribution."""
        self._require_adult()
        return QRCode(self.app_text(channel), "M")

    def parse_app(self, text: str) -> str:
        """Verify a scanned app payload -> channel. Tampered -> refused."""
        self._require_adult()
        parts = text.split("/")
        if len(parts) != 5 or parts[0] != "voidbox:" or parts[1] != "" \
                or parts[2] != "get":
            raise QRTamperError("not a Void Box app payload: %r." % (text[:40],))
        _, _, _, channel, tag = parts
        if not _CHANNEL_RE.match(channel) or not _TAG_RE.match(tag):
            raise QRTamperError("malformed app payload — refused.")
        if not hmac.compare_digest(self._tag("vb-get:v1", channel), tag):
            raise QRTamperError(
                "app payload signature mismatch for channel %r — "
                "tampered or forged, refused." % (channel,)
            )
        return channel

    def configure_distribution(self, base_url: str) -> Path:
        """Set Chauncey's distribution base URL (his to provide).

        Stored owner-only (0600) under the payments dir. Passing an
        empty URL clears the config back to unset.
        """
        self._require_adult()
        if not isinstance(base_url, str):
            raise QRDistributionError("distribution base must be a string.")
        base_url = base_url.strip().rstrip("/")
        if base_url and not (
            base_url.startswith("https://") or base_url.startswith("http://")
        ):
            raise QRDistributionError(
                "distribution base %r must be an http(s) URL." % (base_url,)
            )
        cfg_file = self._dir / "distribution.json"
        atomic_write_bytes(
            cfg_file, json.dumps({"base_url": base_url}).encode("utf-8")
        )
        os.chmod(cfg_file, 0o600)
        return cfg_file

    def distribution_base(self) -> str:
        """Chauncey's configured distribution base, or "" when unset."""
        self._require_adult()
        cfg_file = self._dir / "distribution.json"
        if not cfg_file.exists():
            return ""
        try:
            return json.loads(cfg_file.read_text("utf-8")).get("base_url", "")
        except (ValueError, OSError):
            return ""

    def distribution_url(self, channel: str) -> str:
        """Resolve the download URL for a channel.

        Refused with the remedy when Chauncey hasn't provided the base
        — never invented (D4).
        """
        self._require_adult()
        base = self.distribution_base()
        if not base:
            raise QRDistributionError(
                "no distribution base configured: Chauncey provides the "
                "download URL via configure_distribution() — nothing is "
                "invented here."
            )
        if not isinstance(channel, str) or not _CHANNEL_RE.match(channel):
            raise QRError("invalid channel %r." % (channel,))
        return "%s/%s" % (base, channel)

    # -- creator referrals -------------------------------------------------

    def referral_text(self, creator_id: str) -> Tuple[str, str]:
        """Mint a creator referral payload -> (qr_text, code).

        The code is 96 bits from secrets (unguessable, D5); the ledger
        maps code -> creator_id at mint time, so the URI stays short.
        Scanning attributes the install/signup to the creator.
        """
        self._require_adult()
        if not isinstance(creator_id, str) or not _ID_RE.match(creator_id):
            raise QRError(
                "invalid creator_id %r: 1-12 chars of [A-Za-z0-9._-]."
                % (creator_id,)
            )
        code = "".join(
            secrets.choice(
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
            )
            for _ in range(12)
        )
        tag = self._tag("vb-ref:v1", code)
        text = self._check_size("voidbox://r/%s/%s" % (code, tag), "referral")
        self._ledger_append(
            {"kind": "mint", "code": code, "creator_id": creator_id,
             "ts": _utcnow()}
        )
        return text, code

    def referral_qr(self, creator_id: str) -> Tuple[QRCode, str]:
        """QR symbol for a creator referral -> (QRCode, code)."""
        self._require_adult()
        text, code = self.referral_text(creator_id)
        return QRCode(text, "M"), code

    def parse_referral(self, text: str) -> str:
        """Verify a scanned referral payload -> referral code.

        Tampered -> refused by name (D2).
        """
        self._require_adult()
        parts = text.split("/")
        if len(parts) != 5 or parts[0] != "voidbox:" or parts[1] != "" \
                or parts[2] != "r":
            raise QRTamperError("not a Void Box referral payload: %r." % (text[:40],))
        _, _, _, code, tag = parts
        if not _CODE_RE.match(code) or not _TAG_RE.match(tag):
            raise QRTamperError("malformed referral payload — refused.")
        if not hmac.compare_digest(self._tag("vb-ref:v1", code), tag):
            raise QRTamperError(
                "referral payload signature mismatch — tampered or "
                "forged, refused."
            )
        return code

    def _ledger_append(self, record: Dict[str, object]) -> None:
        ledger = self._dir / "referrals.jsonl"
        line = (json.dumps(record, sort_keys=True) + "\n").encode("utf-8")
        with open(ledger, "ab") as fh:
            fh.write(line)
        os.chmod(ledger, 0o600)

    def record_referral(self, code: str, referred_id: str) -> Dict[str, object]:
        """Record that referral *code* converted *referred_id*.

        Feeds the tier-cut accounting: who referred whom (D5).
        """
        self._require_adult()
        if not isinstance(code, str) or not _CODE_RE.match(code):
            raise QRError("invalid referral code %r." % (code,))
        if not isinstance(referred_id, str) or not _ID_RE.match(referred_id):
            raise QRError("invalid referred_id %r." % (referred_id,))
        referrer = self._referrer_for(code)
        if referrer is None:
            raise QRError(
                "unknown referral code: mint it with referral_text() first."
            )
        record = {
            "kind": "convert",
            "code": code,
            "referrer_creator_id": referrer,
            "referred_id": referred_id,
            "ts": _utcnow(),
        }
        self._ledger_append(record)
        return record

    def _referrer_for(self, code: str) -> Optional[str]:
        ledger = self._dir / "referrals.jsonl"
        if not ledger.exists():
            return None
        referrer = None
        with open(ledger, "rb") as fh:
            for raw in fh:
                try:
                    rec = json.loads(raw.decode("utf-8"))
                except ValueError:
                    continue
                if rec.get("code") == code and rec.get("kind") == "mint":
                    referrer = rec.get("creator_id")
        return referrer

    def attributions_for(self, creator_id: str) -> List[Dict[str, object]]:
        """All conversions attributed to *creator_id* — the tier-cut
        accounting reads this (who referred whom, D5)."""
        self._require_adult()
        ledger = self._dir / "referrals.jsonl"
        out: List[Dict[str, object]] = []
        if not ledger.exists():
            return out
        with open(ledger, "rb") as fh:
            for raw in fh:
                try:
                    rec = json.loads(raw.decode("utf-8"))
                except ValueError:
                    continue
                if rec.get("kind") == "convert" \
                        and rec.get("referrer_creator_id") == creator_id:
                    out.append(rec)
        return out

    # -- printable share cards --------------------------------------------

    def share_card(
        self,
        title: str,
        subtitle: str,
        qr_text: str,
        card_format: str = "ascii",
    ) -> str:
        """Printable share card: human-readable label + the QR.

        For listings, rooms, creator profiles — scan the code, read the
        label. The label is display text the minter chose; the QR text
        must be a payload this module (or the payments module) built.
        """
        self._require_adult()
        if not isinstance(title, str) or not title.strip() or len(title) > 48:
            raise QRError("share card needs a title of 1-48 chars.")
        if not isinstance(subtitle, str) or len(subtitle) > 64:
            raise QRError("share card subtitle is at most 64 chars.")
        if not isinstance(qr_text, str) or not qr_text.startswith("voidbox://"):
            raise QRError(
                "share card QR text must be a voidbox:// payload — cards "
                "never wrap arbitrary links."
            )
        qr = QRCode(qr_text, "M")  # Q2/Q3 re-verified at card time
        if card_format == "ascii":
            body = qr.to_ascii(border=1)
        elif card_format == "svg":
            body = qr.to_svg(scale=6, border=2)
        else:
            raise QRError(
                "share card format must be 'ascii' or 'svg', got %r."
                % (card_format,)
            )
        bar = "=" * 40
        return "\n".join(
            [bar, title.strip().center(40), subtitle.strip().center(40),
             bar, body, bar, "scan with Void Box".center(40), bar]
        )


def verify_laws() -> List[Tuple[str, bool, str]]:
    """Machine-checked discovery/distribution QR invariants.

    Runs against a throwaway home with the gate opened the one lawful
    way — never against the real owner record.
    """
    import tempfile

    from levi.plaiground import gate as _gate

    results: List[Tuple[str, bool, str]] = []

    def check(law: str, ok: bool, detail: str = "") -> None:
        results.append((law, bool(ok), detail))

    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        _gate.set_pin("424242", home=home)
        _gate.enable_adult_mode(_gate.CONFIRMATION_PHRASE, "424242", home=home)
        dq = DiscoveryQr("correct horse battery staple voidbox", home=home)

        # D1: ids + signature only — no personal data / amounts in payloads.
        t = dq.discovery_text("creators", "summer25")
        check("D1", t.startswith("voidbox://d/C/summer25/"),
              "discovery payload: %s" % t)
        check("D1", "@" not in t and "$" not in t and "amount" not in t,
              "no personal data or amounts in payload")

        # D2: tamper refused by name.
        tampered = t[:-1] + ("0" if t[-1] != "0" else "1")
        try:
            dq.parse_discovery(tampered)
            check("D2", False, "tampered discovery payload accepted")
        except QRTamperError as e:
            check("D2", "refused" in str(e), "tampered refused: %s" % e)
        # Wrong surface code refused.
        try:
            dq.parse_discovery(t.replace("/C/", "/Z/"))
            check("D2", False, "forged surface code accepted")
        except QRTamperError:
            check("D2", True, "forged surface code refused")

        # D6: oversize refused at build, never truncated.
        try:
            dq.discovery_text("dating", "x" * 13)
            check("D6", False, "13-char ref_id accepted")
        except QRError:
            check("D6", True, "13-char ref_id refused (would exceed 62B)")

        # D4: distribution unset -> refused with remedy.
        try:
            dq.distribution_url("android")
            check("D4", False, "download URL resolved without config")
        except QRDistributionError as e:
            check("D4", "configure_distribution" in str(e),
                  "refused with remedy: %s" % e)
        dq.configure_distribution("https://example.invalid/vb")
        check("D4", dq.distribution_url("android")
              == "https://example.invalid/vb/android",
              "configured base resolves: %s" % dq.distribution_url("android"))

        # D5: referral attribution round-trip.
        text, code = dq.referral_text("creator1")
        check("D5", len(code) == 12 and _CODE_RE.match(code) is not None,
              "unguessable 12-char code")
        rec = dq.record_referral(code, "newuser9")
        check("D5", rec["referrer_creator_id"] == "creator1"
              and rec["referred_id"] == "newuser9",
              "attribution recorded: who referred whom")
        attrs = dq.attributions_for("creator1")
        check("D5", len(attrs) == 1 and attrs[0]["code"] == code,
              "tier-cut accounting can read attributions")

        # D3: locked gate refuses public entries.
        _gate.disable_adult_mode(home=home)
        try:
            dq.discovery_text("dating", "tonight")
            check("D3", False, "discovery minted with gate closed")
        except Exception:
            check("D3", True, "discovery refused with gate closed")

    return results
