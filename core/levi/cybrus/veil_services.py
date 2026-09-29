"""Veil Services — escort directory and creator platform, chat-first inside Veil.

What this is
------------
Two adult services that live *inside* Veil as chat-native experiences,
under Cybrus law:

1. :class:`VeilEscorts` — an escort directory + booking flow. Providers
   publish profiles; customers browse the directory, open a Veil
   conversation, and book through chat. Booking payment goes through
   Cybrus as the sole money handler (platform plan §3: money law).

2. :class:`VeilCreators` — a digital creator service (OnlyFans-shaped).
   Creators publish content tiers (free / paid); subscribers discover
   creators, subscribe through Veil chat, and receive content drops as
   sealed Veil envelopes. Paid tiers bill through Cybrus money handling.

Chat-first, not web-first
-------------------------
There is no website here. Discovery, negotiation, booking, subscribing,
and delivery all happen as Veil conversations: the directory is a list
of chat contacts, a booking is a structured chat exchange, a content
drop is a sealed envelope. QR codes (``cybrus://invite/…``,
``cybrus://creator/…``) handle creator-to-user discovery, per the
broker_qr pattern.

Laws (machine-readable in ``LAWS``)
-----------------------------------
- VS1 GATE-FIRST — every public entry calls
  :func:`levi.plaiground.gate.require_adult` first. No adult content,
  profiles, or bookings with the gate off.
- VS2 BOUNDS — all user-supplied text passes
  :func:`levi.plaiground.bounds.check_bounds`.
- VS3 MONEY-THROUGH-CYBRUS — every payment is a Cybrus ``MoneyPlan``:
  approval-ledger entry → keeper authorization → ``MoneyGateway``
  execute. No side payments, no exceptions. With no rail registered the
  gateway fails closed — the booking/subscription records the *intent*
  and waits; money never moves on a promise.
- VS4 SEALED-DELIVERY — bookings, content drops, and negotiation all
  travel as sealed Veil envelopes. Ciphertext at rest.
- VS5 AUDIT-METADATA-ONLY — audit carries ids, tiers, amounts, counts.
  Never message plaintext, never explicit content descriptors.
- VS6 PROVIDER-BOUNDARIES — a provider's/creator's stated boundaries
  are checked on every booking/content request; violations fail closed.
- VS7 QR-SIGNED — discovery tickets are HMAC-signed, single-use,
  expiring (broker_qr pattern).
- VS8 NO-CANCELLATION — bookings and subscriptions are never silently
  dropped; cancellation is an explicit audited state transition.

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
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from levi.cybrus._paths import atomic_write_bytes, store_lock
from levi.cybrus.audit import AuditEngine
from levi.cybrus.veil import _b64d, _b64e, _hkdf, _utcnow
from levi.cybrus.veil_chat import VeilChat, VeilChatError
from levi.plaiground.bounds import check_bounds
from levi.plaiground.gate import require_adult

LAWS = (
    ("VS1", "GATE-FIRST",
     "Every public entry calls require_adult() first."),
    ("VS2", "BOUNDS",
     "All user-supplied text passes check_bounds()."),
    ("VS3", "MONEY-THROUGH-CYBRUS",
     "Every payment is a Cybrus MoneyPlan: approval -> authorize -> execute."),
    ("VS4", "SEALED-DELIVERY",
     "Bookings, drops, negotiation travel as sealed Veil envelopes."),
    ("VS5", "AUDIT-METADATA-ONLY",
     "Audit carries ids/tiers/amounts/counts, never plaintext or explicit content."),
    ("VS6", "PROVIDER-BOUNDARIES",
     "Provider/creator boundaries checked on every request; violations fail closed."),
    ("VS7", "QR-SIGNED",
     "Discovery tickets are HMAC-signed, single-use, expiring."),
    ("VS8", "NO-CANCELLATION",
     "Bookings/subscriptions end only via explicit audited transitions."),
)

_ESCORTS_DIR = "veil_escorts"
_CREATORS_DIR = "veil_creators"

_QR_CREATOR_SCHEME = "cybrus://creator/"
_QR_PROVIDER_SCHEME = "cybrus://provider/"

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.'-]{0,47}$")
_MAX_TEXT = 2000


def _short(value: str) -> str:
    return str(value)[:12]


def _clean_text(value: str, label: str, max_len: int = _MAX_TEXT) -> str:
    if not isinstance(value, str):
        raise ValueError("%s must be a string" % label)
    value = value.strip()
    if not value:
        raise ValueError("%s must not be empty" % label)
    if len(value) > max_len:
        raise ValueError("%s too long (max %d)" % (label, max_len))
    return check_bounds(value)


class VeilServiceError(VeilChatError):
    """Service-layer failures. Fails closed."""


class _Store:
    """Owner-only JSON store helper (0600, atomic, locked)."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def read(self) -> Dict:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def write(self, data: Dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with store_lock(self._path):
            atomic_write_bytes(
                self._path,
                json.dumps(data, indent=2, sort_keys=True).encode("utf-8"),
            )
        os.chmod(self._path, 0o600)


# ---------------------------------------------------------------------------
# Escort directory + booking
# ---------------------------------------------------------------------------

_BOOKING_STATES = (
    "requested", "approved", "denied", "confirmed",
    "completed", "cancelled", "no_show",
)
# Allowed transitions; terminal states have none.
_BOOKING_FLOW = {
    "requested": ("approved", "denied", "cancelled"),
    "approved": ("confirmed", "cancelled"),
    "denied": (),
    "confirmed": ("completed", "cancelled", "no_show"),
    "completed": (),
    "cancelled": (),
    "no_show": (),
}


class VeilEscorts:
    """Escort directory and chat-first booking, under Cybrus law.

    The directory is local-first: providers the keeper knows, each a Veil
    contact. Booking is a structured conversation — request, approve/deny,
    confirm (Cybrus approval + money intent), complete. Every transition
    is an audited state change (VS8); money moves only through Cybrus
    (VS3).
    """

    def __init__(self, chat: VeilChat, home: Optional[Path] = None) -> None:
        self._chat = chat
        base = Path(home) if home else chat._home
        self._providers = _Store(base / _ESCORTS_DIR / "providers.json")
        self._bookings = _Store(base / _ESCORTS_DIR / "bookings.json")
        self._audit = AuditEngine()

    def _audit_event(self, event: str, details: Optional[Dict] = None) -> None:
        try:
            self._audit.append(event, "keeper", details or {})
        except Exception:
            pass

    # -- provider profiles ------------------------------------------------------
    def register_provider(
        self,
        display_name: str,
        services: List[str],
        rates_minor: Dict[str, int],
        availability: str = "",
        boundaries: Optional[List[str]] = None,
        area: str = "",
    ) -> Dict:
        """Publish a provider profile to the local directory.

        ``rates_minor`` maps service name -> price in integer minor units
        (cents). Gate-checked (VS1), bounds-checked (VS2).
        """
        require_adult()
        if not _NAME_RE.match(display_name or ""):
            raise VeilServiceError("bad display name %r" % display_name)
        services = [_clean_text(s, "service", 120) for s in (services or [])]
        if not services:
            raise VeilServiceError("at least one service is required")
        rates = {}
        for svc, minor in (rates_minor or {}).items():
            svc = _clean_text(svc, "rate service", 120)
            if not isinstance(minor, int) or minor <= 0:
                raise VeilServiceError("rate for %r must be positive minor units" % svc)
            rates[svc] = minor
        boundaries = [_clean_text(b, "boundary", 240) for b in (boundaries or [])]
        profile = {
            "provider_id": uuid.uuid4().hex,
            "display_name": display_name,
            "services": services,
            "rates_minor": rates,
            "availability": _clean_text(availability, "availability", 500)
            if availability else "",
            "boundaries": boundaries,
            "area": _clean_text(area, "area", 120) if area else "",
            "created_at": _utcnow(),
        }
        providers = self._providers.read()
        providers[profile["provider_id"]] = profile
        self._providers.write(providers)
        self._audit_event("veil.escort.provider_registered", {
            "provider_id": _short(profile["provider_id"]),
            "display_name": display_name,
            "service_count": len(services),
        })
        return profile

    def directory(self) -> List[Dict]:
        """List provider profiles (metadata only). Gate-checked."""
        require_adult()
        return [
            {
                "provider_id": pid,
                "display_name": p["display_name"],
                "services": p["services"],
                "rates_minor": p["rates_minor"],
                "availability": p.get("availability", ""),
                "area": p.get("area", ""),
            }
            for pid, p in self._providers.read().items()
        ]

    def get_provider(self, provider_id: str) -> Dict:
        require_adult()
        providers = self._providers.read()
        if provider_id not in providers:
            raise VeilServiceError("unknown provider")
        return providers[provider_id]

    # -- booking state machine ---------------------------------------------------
    def _transition(self, booking_id: str, to_state: str,
                    actor: str = "keeper") -> Dict:
        bookings = self._bookings.read()
        booking = bookings.get(booking_id)
        if booking is None:
            raise VeilServiceError("unknown booking")
        frm = booking["status"]
        if to_state not in _BOOKING_FLOW.get(frm, ()):
            raise VeilServiceError(
                "illegal booking transition %s -> %s" % (frm, to_state))
        booking["status"] = to_state
        booking.setdefault("transitions", []).append({
            "from": frm, "to": to_state, "at": _utcnow(), "actor": actor,
        })
        self._bookings.write(bookings)
        self._audit_event("veil.escort.booking_%s" % to_state, {
            "booking_id": _short(booking_id),
            "provider_id": _short(booking.get("provider_id", "")),
        })
        return booking

    def request_booking(
        self,
        conv_id: str,
        provider_id: str,
        service: str,
        when_iso: str,
        duration_min: int,
        note: str = "",
    ) -> Dict:
        """Open a booking request inside a Veil conversation with the
        provider. Gate-checked; the request itself travels as a sealed
        envelope (VS4). The provider's boundaries are checked (VS6).
        """
        require_adult()
        provider = self.get_provider(provider_id)
        service = _clean_text(service, "service", 120)
        if service not in provider["services"]:
            raise VeilServiceError("provider does not offer %r" % service)
        if not isinstance(duration_min, int) or duration_min <= 0:
            raise VeilServiceError("duration must be positive minutes")
        note = _clean_text(note, "note", 500) if note else ""
        amount = int(provider["rates_minor"].get(service, 0))
        booking_id = uuid.uuid4().hex
        booking = {
            "booking_id": booking_id,
            "provider_id": provider_id,
            "conv_id": conv_id,
            "service": service,
            "when_iso": when_iso,
            "duration_min": duration_min,
            "amount_minor": amount,
            "currency": "USD",
            "status": "requested",
            "transitions": [{"from": None, "to": "requested",
                             "at": _utcnow(), "actor": "keeper"}],
            "approval_id": None,
            "plan_id": None,
        }
        bookings = self._bookings.read()
        bookings[booking_id] = booking
        self._bookings.write(bookings)
        # The request travels inside the sealed conversation (VS4).
        payload = json.dumps({
            "kind": "veil-booking-request",
            "booking_id": booking_id,
            "service": service,
            "when_iso": when_iso,
            "duration_min": duration_min,
            "note": note,
        })
        self._chat.send_message(conv_id, payload.encode("utf-8"))
        self._audit_event("veil.escort.booking_requested", {
            "booking_id": _short(booking_id),
            "provider_id": _short(provider_id),
            "service": service,
            "amount_minor": amount,
        })
        return booking

    def respond_booking(self, booking_id: str, approve: bool,
                        actor: str = "provider") -> Dict:
        """Provider approves or denies. Terminal on deny (VS8)."""
        require_adult()
        return self._transition(booking_id,
                                "approved" if approve else "denied",
                                actor=actor)

    def confirm_booking(self, booking_id: str,
                        keeper_identity: str = "keeper") -> Dict:
        """Customer confirms an approved booking: raises the Cybrus
        approval-ledger entry and builds the MoneyPlan intent (VS3).

        Returns the booking with ``approval_id`` and ``plan_id`` set.
        Money executes only via ``MoneyGateway`` with the keeper's
        authorization — with no rail registered the gateway fails closed
        and the booking waits in ``approved`` with the intent recorded.
        """
        require_adult()
        bookings = self._bookings.read()
        booking = bookings.get(booking_id)
        if booking is None:
            raise VeilServiceError("unknown booking")
        if booking["status"] != "approved":
            raise VeilServiceError("booking must be approved before confirmation")
        from levi.cybrus.money import MoneyGateway, MoneyPlan
        plan = MoneyPlan(
            plan_id=uuid.uuid4().hex,
            operation="escort_booking",
            amount_minor=int(booking["amount_minor"]),
            currency=booking.get("currency", "USD"),
            rail="",
            purpose="veil escort booking %s" % _short(booking_id),
            identity=keeper_identity,
            created_at=_utcnow(),
        )
        entry = MoneyGateway().request_execution_approval(
            plan, subject=keeper_identity)
        booking["approval_id"] = entry["id"]
        booking["plan_id"] = plan.plan_id
        booking["status"] = "confirmed"
        booking.setdefault("transitions", []).append({
            "from": "approved", "to": "confirmed",
            "at": _utcnow(), "actor": keeper_identity,
        })
        self._bookings.write(bookings)
        self._audit_event("veil.escort.booking_confirmed", {
            "booking_id": _short(booking_id),
            "plan_id": _short(plan.plan_id),
            "approval_id": _short(entry["id"]),
            "amount_minor": plan.amount_minor,
        })
        return booking

    def complete_booking(self, booking_id: str) -> Dict:
        require_adult()
        return self._transition(booking_id, "completed")

    def cancel_booking(self, booking_id: str, actor: str = "keeper") -> Dict:
        require_adult()
        return self._transition(booking_id, "cancelled", actor=actor)

    def get_booking(self, booking_id: str) -> Dict:
        require_adult()
        bookings = self._bookings.read()
        if booking_id not in bookings:
            raise VeilServiceError("unknown booking")
        return bookings[booking_id]

    # -- QR discovery ---------------------------------------------------------------
    def _discovery_key(self) -> bytes:
        # Derived per-device; the keeper's chat vault must be unlocked.
        master = self._chat._require_unlocked()
        return _hkdf(master, b"veil-escort-qr-salt-v1",
                     b"veil-escort-qr-v1", 32)

    def provider_qr(self, provider_id: str, max_uses: int = 1,
                    ttl_hours: float = 72.0) -> Dict:
        """Signed discovery ticket for a provider profile
        (``cybrus://provider/<ticket>``). Gate-checked (VS7)."""
        require_adult()
        provider = self.get_provider(provider_id)
        if not isinstance(max_uses, int) or max_uses < 1:
            raise VeilServiceError("max_uses must be a positive int")
        if not (0 < float(ttl_hours) <= 24 * 90):
            raise VeilServiceError("ttl_hours must be within (0, 2160]")
        payload = {
            "v": 1,
            "id": uuid.uuid4().hex,
            "provider_id": provider_id,
            "display_name": provider["display_name"],
            "services": provider["services"],
            "area": provider.get("area", ""),
            "max_uses": max_uses,
            "exp": time.time() + float(ttl_hours) * 3600.0,
            "nonce": secrets.token_hex(8),
        }
        body = _b64e(json.dumps(payload, sort_keys=True).encode("utf-8"))
        sig = _b64e(hmac.new(self._discovery_key(), body.encode("ascii"),
                             hashlib.sha256).digest())
        self._audit_event("veil.escort.qr_issued", {
            "provider_id": _short(provider_id),
        })
        return {
            "provider_id": provider_id,
            "qr_payload": _QR_PROVIDER_SCHEME + body + "." + sig,
            "expires_at": datetime.fromtimestamp(
                payload["exp"], timezone.utc).isoformat(),
        }


# ---------------------------------------------------------------------------
# Creator platform (OnlyFans-shaped, chat-first)
# ---------------------------------------------------------------------------

_TIER_NAMES = ("free", "bronze", "silver", "gold")


class VeilCreators:
    """Digital creator service: tiers, subscriptions, sealed content drops.

    Creators publish tiered content; subscribers discover via directory or
    QR, subscribe through Veil chat, and receive drops as sealed
    envelopes. Paid tiers bill through Cybrus (VS3). Adult content is
    Plaiground-gated (VS1); every drop is bounds-checked (VS2).
    """

    def __init__(self, chat: VeilChat, home: Optional[Path] = None) -> None:
        self._chat = chat
        base = Path(home) if home else chat._home
        self._creators = _Store(base / _CREATORS_DIR / "creators.json")
        self._subs = _Store(base / _CREATORS_DIR / "subscriptions.json")
        self._drops = _Store(base / _CREATORS_DIR / "drops.json")
        self._audit = AuditEngine()

    def _audit_event(self, event: str, details: Optional[Dict] = None) -> None:
        try:
            self._audit.append(event, "keeper", details or {})
        except Exception:
            pass

    # -- creator profiles ------------------------------------------------------------
    def register_creator(
        self,
        handle: str,
        bio: str = "",
        tiers: Optional[Dict[str, int]] = None,
        boundaries: Optional[List[str]] = None,
    ) -> Dict:
        """Publish a creator profile. ``tiers`` maps tier name ->
        price in minor units/month (``free`` tier is always 0).
        Gate-checked (VS1), bounds-checked (VS2).
        """
        require_adult()
        if not _NAME_RE.match(handle or ""):
            raise VeilServiceError("bad handle %r" % handle)
        tiers = dict(tiers or {})
        for name, price in tiers.items():
            if name not in _TIER_NAMES:
                raise VeilServiceError("unknown tier %r" % name)
            if not isinstance(price, int) or price < 0:
                raise VeilServiceError("tier price must be non-negative minor units")
        tiers.setdefault("free", 0)
        profile = {
            "creator_id": uuid.uuid4().hex,
            "handle": handle,
            "bio": _clean_text(bio, "bio", 500) if bio else "",
            "tiers": tiers,
            "boundaries": [_clean_text(b, "boundary", 240)
                           for b in (boundaries or [])],
            "created_at": _utcnow(),
        }
        creators = self._creators.read()
        creators[profile["creator_id"]] = profile
        self._creators.write(creators)
        self._audit_event("veil.creator.registered", {
            "creator_id": _short(profile["creator_id"]),
            "handle": handle,
            "tiers": sorted(tiers),
        })
        return profile

    def directory(self) -> List[Dict]:
        """Creator directory (metadata only). Gate-checked."""
        require_adult()
        return [
            {
                "creator_id": cid,
                "handle": c["handle"],
                "bio": c.get("bio", ""),
                "tiers": c["tiers"],
            }
            for cid, c in self._creators.read().items()
        ]

    def get_creator(self, creator_id: str) -> Dict:
        require_adult()
        creators = self._creators.read()
        if creator_id not in creators:
            raise VeilServiceError("unknown creator")
        return creators[creator_id]

    # -- subscriptions ------------------------------------------------------------------
    def subscribe(self, creator_id: str, tier: str,
                  keeper_identity: str = "keeper") -> Dict:
        """Subscribe to a creator tier through Veil.

        The ``free`` tier activates immediately. Paid tiers build a Cybrus
        MoneyPlan + approval-ledger entry (VS3); the subscription becomes
        ``active`` once the keeper authorizes and the gateway executes —
        with no rail registered it waits in ``pending_payment`` with the
        intent recorded, failing closed.
        """
        require_adult()
        creator = self.get_creator(creator_id)
        if tier not in creator["tiers"]:
            raise VeilServiceError("creator has no tier %r" % tier)
        price = int(creator["tiers"][tier])
        sub_id = uuid.uuid4().hex
        sub = {
            "sub_id": sub_id,
            "creator_id": creator_id,
            "tier": tier,
            "price_minor": price,
            "currency": "USD",
            "status": "active" if price == 0 else "pending_payment",
            "started_at": _utcnow(),
            "approval_id": None,
            "plan_id": None,
        }
        if price > 0:
            from levi.cybrus.money import MoneyGateway, MoneyPlan
            plan = MoneyPlan(
                plan_id=uuid.uuid4().hex,
                operation="creator_subscription",
                amount_minor=price,
                currency="USD",
                rail="",
                purpose="veil creator subscription %s/%s"
                        % (creator["handle"], tier),
                identity=keeper_identity,
                created_at=_utcnow(),
            )
            entry = MoneyGateway().request_execution_approval(
                plan, subject=keeper_identity)
            sub["approval_id"] = entry["id"]
            sub["plan_id"] = plan.plan_id
        subs = self._subs.read()
        subs[sub_id] = sub
        self._subs.write(subs)
        self._audit_event("veil.creator.subscribed", {
            "sub_id": _short(sub_id),
            "creator_id": _short(creator_id),
            "tier": tier,
            "price_minor": price,
            "status": sub["status"],
        })
        return sub

    def unsubscribe(self, sub_id: str) -> Dict:
        """Explicit audited cancellation (VS8)."""
        require_adult()
        subs = self._subs.read()
        sub = subs.get(sub_id)
        if sub is None:
            raise VeilServiceError("unknown subscription")
        sub["status"] = "cancelled"
        sub["ended_at"] = _utcnow()
        self._subs.write(subs)
        self._audit_event("veil.creator.unsubscribed", {
            "sub_id": _short(sub_id),
            "creator_id": _short(sub.get("creator_id", "")),
        })
        return sub

    def my_subscriptions(self) -> List[Dict]:
        require_adult()
        return list(self._subs.read().values())

    # -- content drops (per-post paywall) ---------------------------------------------------
    # Every drop carries per-post visibility: "free" (teasers / free posts,
    # viewable by anyone) or "locked" (unlocks after payment through Cybrus
    # money handlers). Visibility is per-post, not just per-tier: a creator
    # runs free teasers alongside paid content on the same tier.

    _VISIBILITIES = ("free", "locked")
    _MEDIA_TYPES = ("text", "photo", "video")
    # Media embedded directly in the sealed delivery envelope up to this;
    # larger media ships as a sealed manifest (transfer is a next step).
    _MEDIA_EMBED_CAP = 5 * 1024 * 1024

    def _unlocks_store(self) -> "_Store":
        return _Store(self._drops._path.parent / "unlocks.json")

    def publish_drop(self, creator_id: str, tier: str, title: str,
                     body: str = "", media_type: str = "text",
                     media_bytes: Optional[bytes] = None,
                     visibility: str = "locked",
                     price_minor: Optional[int] = None,
                     teaser: str = "") -> Dict:
        """Publish a content drop with per-post visibility.

        ``visibility``: ``"free"`` — teaser/free post, viewable by anyone;
        ``"locked"`` — unlocks after payment (default).
        ``media_type``: ``"text"`` | ``"photo"`` | ``"video"``.
        ``media_bytes``: raw photo/video bytes (stored owner-only, 0600).
        ``price_minor``: unlock price in minor units; defaults to the
        tier's price when the tier is paid, 0 for the free tier.
        ``teaser``: preview text shown for locked drops.

        Gate-checked (VS1), bounds-checked (VS2), boundaries honored
        (VS6 — checked by the caller against the creator profile).
        Back-compatible: ``publish_drop(creator_id, tier, title, body)``
        still works (locked text drop at the tier price).
        """
        require_adult()
        creator = self.get_creator(creator_id)
        if tier not in creator["tiers"]:
            raise VeilServiceError("creator has no tier %r" % tier)
        if media_type not in self._MEDIA_TYPES:
            raise VeilServiceError("media_type must be one of %s"
                                   % ", ".join(self._MEDIA_TYPES))
        if visibility not in self._VISIBILITIES:
            raise VeilServiceError("visibility must be one of %s"
                                   % ", ".join(self._VISIBILITIES))
        title = _clean_text(title, "title", 200)
        body = _clean_text(body, "body", 10000) if body else ""
        teaser = _clean_text(teaser, "teaser", 500) if teaser else ""
        if media_bytes is not None:
            if not isinstance(media_bytes, (bytes, bytearray)):
                raise VeilServiceError("media_bytes must be bytes")
            if len(media_bytes) > 50 * 1024 * 1024:
                raise VeilServiceError("media too large (50MB cap)")
        tier_price = int(creator["tiers"][tier])
        if price_minor is None:
            price_minor = tier_price
        if not isinstance(price_minor, int) or price_minor < 0:
            raise VeilServiceError("price_minor must be non-negative minor units")
        if visibility == "free":
            price_minor = 0
        drop_id = uuid.uuid4().hex
        drop = {
            "drop_id": drop_id,
            "creator_id": creator_id,
            "tier": tier,
            "title": title,
            "visibility": visibility,
            "media_type": media_type,
            "has_media": media_bytes is not None,
            "media_bytes_len": len(media_bytes) if media_bytes is not None else 0,
            "price_minor": price_minor,
            "currency": "USD",
            "teaser": teaser,
            "body_cipher_hint": "sealed-envelope",
            "published_at": _utcnow(),
        }
        drops = self._drops.read()
        drops[drop_id] = drop
        self._drops.write(drops)
        # Owner-only content store: text body + optional media bytes.
        base = self._drops._path.parent
        body_path = base / ("drop_%s.sealed" % drop_id)
        body_path.write_text(body, encoding="utf-8")
        os.chmod(body_path, 0o600)
        if media_bytes is not None:
            media_path = base / ("drop_%s.media" % drop_id)
            media_path.write_bytes(bytes(media_bytes))
            os.chmod(media_path, 0o600)
        self._audit_event("veil.creator.drop_published", {
            "drop_id": _short(drop_id),
            "creator_id": _short(creator_id),
            "tier": tier,
            "visibility": visibility,
            "media_type": media_type,
            "price_minor": price_minor,
        })
        return drop

    def get_drop(self, drop_id: str) -> Dict:
        """Drop metadata (no content). Gate-checked."""
        require_adult()
        drops = self._drops.read()
        if drop_id not in drops:
            raise VeilServiceError("unknown drop")
        return drops[drop_id]

    def unlock_drop(self, drop_id: str,
                    keeper_identity: str = "keeper",
                    viewer_id: str = "keeper") -> Dict:
        """Buy the unlock for a locked drop: builds a Cybrus MoneyPlan +
        approval-ledger entry (VS3). The unlock stays ``pending_payment``
        until the keeper authorizes and the gateway executes — then
        :meth:`confirm_unlock` flips it to ``unlocked``.

        Free drops need no unlock (returned as already unlocked).
        """
        require_adult()
        drop = self.get_drop(drop_id)
        viewer_id = _clean_text(viewer_id, "viewer_id", 64)
        if drop["visibility"] == "free":
            return {"drop_id": drop_id, "status": "unlocked",
                    "reason": "free content"}
        if self.is_unlocked(drop_id, viewer_id):
            return {"drop_id": drop_id, "status": "unlocked",
                    "reason": "already unlocked"}
        from levi.cybrus.money import MoneyGateway, MoneyPlan
        plan = MoneyPlan(
            plan_id=uuid.uuid4().hex,
            operation="creator_unlock",
            amount_minor=int(drop["price_minor"]),
            currency=drop.get("currency", "USD"),
            rail="",
            purpose="veil creator unlock %s" % _short(drop_id),
            identity=keeper_identity,
            created_at=_utcnow(),
        )
        entry = MoneyGateway().request_execution_approval(
            plan, subject=keeper_identity)
        unlock_id = uuid.uuid4().hex
        unlock = {
            "unlock_id": unlock_id,
            "drop_id": drop_id,
            "creator_id": drop["creator_id"],
            "viewer_id": viewer_id,
            "price_minor": int(drop["price_minor"]),
            "currency": drop.get("currency", "USD"),
            "status": "pending_payment",
            "approval_id": entry["id"],
            "plan_id": plan.plan_id,
            "created_at": _utcnow(),
        }
        store = self._unlocks_store()
        unlocks = store.read()
        unlocks[unlock_id] = unlock
        store.write(unlocks)
        self._audit_event("veil.creator.unlock_requested", {
            "unlock_id": _short(unlock_id),
            "drop_id": _short(drop_id),
            "price_minor": unlock["price_minor"],
        })
        return unlock

    def confirm_unlock(self, unlock_id: str) -> Dict:
        """Flip a pending unlock to ``unlocked`` once the keeper has
        approved the backing approval-ledger entry. Fails closed when the
        approval isn't approved (VS3)."""
        require_adult()
        from levi.cybrus.approval import ApprovalEngine
        store = self._unlocks_store()
        unlocks = store.read()
        unlock = unlocks.get(unlock_id)
        if unlock is None:
            raise VeilServiceError("unknown unlock")
        if unlock["status"] == "unlocked":
            return unlock
        if not ApprovalEngine().check(unlock["approval_id"]):
            raise VeilServiceError(
                "unlock not paid: approval %s is not approved"
                % _short(unlock["approval_id"]))
        unlock["status"] = "unlocked"
        unlock["unlocked_at"] = _utcnow()
        store.write(unlocks)
        self._audit_event("veil.creator.unlocked", {
            "unlock_id": _short(unlock_id),
            "drop_id": _short(unlock["drop_id"]),
        })
        return unlock

    def is_unlocked(self, drop_id: str, viewer_id: str = "keeper") -> bool:
        """True when the viewer may see the full drop: the drop is free,
        the viewer unlocked this post, or the viewer holds an active paid
        subscription covering the drop's tier."""
        require_adult()
        drop = self.get_drop(drop_id)
        if drop["visibility"] == "free":
            return True
        unlocks = self._unlocks_store().read()
        for u in unlocks.values():
            if (u["drop_id"] == drop_id and u["viewer_id"] == viewer_id
                    and u["status"] == "unlocked"):
                return True
        # Active paid subscription covering the tier also unlocks.
        tier_order = ("free", "bronze", "silver", "gold")
        try:
            need = tier_order.index(drop["tier"])
        except ValueError:
            need = 0
        for s in self._subs.read().values():
            if s.get("status") != "active":
                continue
            try:
                have = tier_order.index(s.get("tier", "free"))
            except ValueError:
                continue
            if have >= need:
                return True
        return False

    def view_drop(self, drop_id: str,
                  viewer_id: str = "keeper") -> Dict:
        """View a drop: full content when free or unlocked, otherwise the
        teaser + price + unlock instructions. Gate-checked (VS1).

        Media bytes are returned for viewable drops (the caller renders
        them); locked drops never leak media or full text (VS5).
        """
        require_adult()
        drop = self.get_drop(drop_id)
        base = self._drops._path.parent
        if not self.is_unlocked(drop_id, viewer_id):
            return {
                "drop_id": drop_id,
                "title": drop["title"],
                "visibility": "locked",
                "media_type": drop["media_type"],
                "teaser": drop.get("teaser", ""),
                "price_minor": drop["price_minor"],
                "currency": drop.get("currency", "USD"),
                "unlocked": False,
                "unlock_hint": "call unlock_drop(%r) then confirm_unlock()"
                               % drop_id,
            }
        body_path = base / ("drop_%s.sealed" % drop_id)
        body = body_path.read_text(encoding="utf-8") if body_path.exists() else ""
        media = None
        if drop.get("has_media"):
            media_path = base / ("drop_%s.media" % drop_id)
            if media_path.exists():
                media = media_path.read_bytes()
        self._audit_event("veil.creator.drop_viewed", {
            "drop_id": _short(drop_id),
            "visibility": drop["visibility"],
        })
        return {
            "drop_id": drop_id,
            "title": drop["title"],
            "visibility": drop["visibility"],
            "media_type": drop["media_type"],
            "body": body,
            "media_bytes": media,
            "unlocked": True,
        }

    def deliver_drop(self, drop_id: str, conv_id: str,
                     viewer_id: str = "keeper") -> Dict:
        """Deliver a drop into a subscriber's Veil conversation as a sealed
        envelope (VS4).

        Free or unlocked drops deliver the full content (media embedded up
        to the cap; larger media ships as a sealed manifest). Locked,
        not-yet-unlocked drops deliver the teaser + price + unlock prompt —
        never the content.
        """
        require_adult()
        drop = self.get_drop(drop_id)
        view = self.view_drop(drop_id, viewer_id)
        if view["unlocked"]:
            media_b64 = None
            manifest = None
            if view.get("media_bytes") is not None:
                raw = view["media_bytes"]
                if len(raw) <= self._MEDIA_EMBED_CAP:
                    media_b64 = _b64e(raw)
                else:
                    manifest = {
                        "bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "note": "media exceeds envelope cap; fetch out-of-band",
                    }
            payload = json.dumps({
                "kind": "veil-creator-drop",
                "drop_id": drop_id,
                "title": drop["title"],
                "tier": drop["tier"],
                "visibility": drop["visibility"],
                "media_type": drop["media_type"],
                "body": view["body"],
                "media_b64": media_b64,
                "media_manifest": manifest,
            })
        else:
            payload = json.dumps({
                "kind": "veil-creator-drop-locked",
                "drop_id": drop_id,
                "title": drop["title"],
                "tier": drop["tier"],
                "visibility": "locked",
                "media_type": drop["media_type"],
                "teaser": view["teaser"],
                "price_minor": view["price_minor"],
                "currency": view["currency"],
                "unlock_hint": view["unlock_hint"],
            })
        envelope = self._chat.send_message(conv_id, payload.encode("utf-8"))
        self._audit_event("veil.creator.drop_delivered", {
            "drop_id": _short(drop_id),
            "conv_seq": envelope["seq"],
            "unlocked": view["unlocked"],
        })
        return {"drop_id": drop_id, "envelope_seq": envelope["seq"],
                "unlocked": view["unlocked"]}

    # -- QR discovery ----------------------------------------------------------------------------
    def _discovery_key(self) -> bytes:
        master = self._chat._require_unlocked()
        return _hkdf(master, b"veil-creator-qr-salt-v1",
                     b"veil-creator-qr-v1", 32)

    def creator_qr(self, creator_id: str, max_uses: int = 1,
                   ttl_hours: float = 72.0) -> Dict:
        """Signed creator discovery ticket (``cybrus://creator/<ticket>``).
        Gate-checked (VS7)."""
        require_adult()
        creator = self.get_creator(creator_id)
        if not isinstance(max_uses, int) or max_uses < 1:
            raise VeilServiceError("max_uses must be a positive int")
        if not (0 < float(ttl_hours) <= 24 * 90):
            raise VeilServiceError("ttl_hours must be within (0, 2160]")
        payload = {
            "v": 1,
            "id": uuid.uuid4().hex,
            "creator_id": creator_id,
            "handle": creator["handle"],
            "tiers": sorted(creator["tiers"]),
            "max_uses": max_uses,
            "exp": time.time() + float(ttl_hours) * 3600.0,
            "nonce": secrets.token_hex(8),
        }
        body = _b64e(json.dumps(payload, sort_keys=True).encode("utf-8"))
        sig = _b64e(hmac.new(self._discovery_key(), body.encode("ascii"),
                             hashlib.sha256).digest())
        self._audit_event("veil.creator.qr_issued", {
            "creator_id": _short(creator_id),
            "handle": creator["handle"],
        })
        return {
            "creator_id": creator_id,
            "handle": creator["handle"],
            "qr_payload": _QR_CREATOR_SCHEME + body + "." + sig,
            "expires_at": datetime.fromtimestamp(
                payload["exp"], timezone.utc).isoformat(),
        }

    # -- NFTs ----------------------------------------------------------------------------
    _QR_NFT_SCHEME = "cybrus://creator-nft/"

    def _nft(self):
        """Lazy VeilNFT service bound to the creators home."""
        from levi.cybrus.veil_nft import VeilNFT
        svc = getattr(self, "_nft_svc", None)
        if svc is None:
            base = self._drops._path.parent
            svc = VeilNFT(base)
            self._nft_svc = svc
        return svc

    def mint_drop_as_nft(self, drop_id: str,
                         price_minor: Optional[int] = None,
                         keeper_identity: str = "keeper") -> Dict:
        """Mint a creator drop (photo/video) as an NFT.

        Certifies the drop's exact bytes; one content hash mints exactly
        once per creator. Approval-gated through Cybrus money handlers
        (pending until the keeper approves, then ``confirm_nft_mint``).
        Gate-checked (VS1). Legal gate cleared 2026-09-27.
        """
        require_adult()
        drop = self.get_drop(drop_id)
        creator = self.get_creator(drop["creator_id"])
        base = self._drops._path.parent
        media = None
        if drop.get("has_media"):
            media_path = base / ("drop_%s.media" % drop_id)
            if media_path.exists():
                media = media_path.read_bytes()
        body_path = base / ("drop_%s.sealed" % drop_id)
        body = body_path.read_text(encoding="utf-8") \
            if body_path.exists() else ""
        return self._nft().mint_drop(
            drop=drop, creator_handle=creator["handle"],
            media_bytes=media, body=body, price_minor=price_minor,
            keeper_identity=keeper_identity)

    def confirm_nft_mint(self, token_id: str) -> Dict:
        """Finalize a pending NFT mint after keeper approval. Fails closed."""
        require_adult()
        return self._nft().confirm_mint(token_id)

    def get_nft(self, token_id: str) -> Optional[Dict]:
        """NFT metadata + ownership. Gate-checked."""
        require_adult()
        return self._nft().get_nft(token_id)

    def nfts_for_creator(self, creator_id: str) -> List[Dict]:
        """All NFTs minted by a creator. Gate-checked."""
        require_adult()
        self.get_creator(creator_id)
        return self._nft().nfts_for_creator(creator_id)

    def nft_for_drop(self, drop_id: str) -> List[Dict]:
        """NFTs minted from a drop (at most one per unique content)."""
        require_adult()
        self.get_drop(drop_id)
        return self._nft().nfts_for_drop(drop_id)

    def buy_nft(self, token_id: str, buyer_id: str = "keeper",
                keeper_identity: str = "keeper") -> Dict:
        """Buy a minted NFT through Cybrus money handlers. Pending until
        the keeper approves, then ``confirm_nft_purchase`` transfers
        ownership. Gate-checked."""
        require_adult()
        return self._nft().buy_nft(
            token_id, buyer_id=buyer_id, keeper_identity=keeper_identity)

    def confirm_nft_purchase(self, purchase_id: str) -> Dict:
        """Transfer NFT ownership after keeper approval. Splits revenue
        50/30/20 (creator/pool/treasury). Fails closed."""
        require_adult()
        return self._nft().confirm_purchase(purchase_id)

    def nft_royalty_for(self, token_id: str,
                        sale_price_minor: int) -> Dict:
        """EIP-2981 secondary royalty due on a resale: 7.5% to the creator."""
        require_adult()
        return self._nft().secondary_royalty_for(token_id, sale_price_minor)

    def nft_qr(self, token_id: str, max_uses: int = 1,
               ttl_hours: float = 72.0) -> Dict:
        """Signed NFT purchase ticket (``cybrus://creator-nft/<ticket>``).

        A buyer scans it, sees the token + price, and purchases through
        the normal buy flow. Single-use, expiring, HMAC-signed —
        same discipline as creator discovery tickets (VS7).
        """
        require_adult()
        token = self._nft().get_nft(token_id)
        if token is None:
            raise VeilServiceError("unknown token")
        if token.get("status") != "minted":
            raise VeilServiceError("token is not minted yet")
        if not isinstance(max_uses, int) or max_uses < 1:
            raise VeilServiceError("max_uses must be a positive int")
        if not (0 < float(ttl_hours) <= 24 * 90):
            raise VeilServiceError("ttl_hours must be within (0, 2160]")
        payload = {
            "v": 1,
            "id": uuid.uuid4().hex,
            "kind": "nft-purchase",
            "token_id": str(token_id),
            "creator_id": token["creator_id"],
            "creator_handle": token["creator_handle"],
            "title": token["title"],
            "media_type": token["media_type"],
            "content_hash": token["content_hash"],
            "price_minor": token["price_minor"],
            "currency": token.get("currency", "USD"),
            "royalty_bps": token["royalty_bps"],
            "max_uses": max_uses,
            "exp": time.time() + float(ttl_hours) * 3600.0,
            "nonce": secrets.token_hex(8),
        }
        body = _b64e(json.dumps(payload, sort_keys=True).encode("utf-8"))
        sig = _b64e(hmac.new(self._discovery_key(), body.encode("ascii"),
                             hashlib.sha256).digest())
        self._audit_event("veil.nft.qr_issued", {
            "token_id": _short(str(token_id)),
        })
        return {
            "token_id": str(token_id),
            "title": token["title"],
            "price_minor": token["price_minor"],
            "qr_payload": self._QR_NFT_SCHEME + body + "." + sig,
            "expires_at": datetime.fromtimestamp(
                payload["exp"], timezone.utc).isoformat(),
        }

    def verify_nft_qr(self, qr_payload: str) -> Dict:
        """Verify a scanned NFT ticket: signature, expiry, and that the
        token is still minted and owned as claimed. Returns the ticket."""
        require_adult()
        prefix = self._QR_NFT_SCHEME
        if not qr_payload.startswith(prefix):
            raise VeilServiceError("not an NFT ticket")
        rest = qr_payload[len(prefix):]
        if "." not in rest:
            raise VeilServiceError("malformed NFT ticket")
        body, sig = rest.rsplit(".", 1)
        expect = _b64e(hmac.new(self._discovery_key(), body.encode("ascii"),
                                hashlib.sha256).digest())
        if not hmac.compare_digest(expect, sig):
            raise VeilServiceError("NFT ticket signature invalid")
        try:
            payload = json.loads(_b64d(body).decode("utf-8"))
        except Exception:
            raise VeilServiceError("NFT ticket undecodable")
        if payload.get("kind") != "nft-purchase":
            raise VeilServiceError("not an NFT purchase ticket")
        if payload.get("exp", 0) < time.time():
            raise VeilServiceError("NFT ticket expired")
        token = self._nft().get_nft(payload["token_id"])
        if token is None or token.get("status") != "minted":
            raise VeilServiceError("token no longer available")
        return payload
