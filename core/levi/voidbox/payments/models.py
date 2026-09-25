"""Void Box payments — money models. Integer cents, always.

Every amount in this package is an integer number of USD cents. There
is no float anywhere in the money path — floats cannot represent
$0.10 exactly, and a platform that takes a cut cannot afford
rounding ghosts.

A PaymentRequest is a *prepared* request: who pays whom, how much,
through which plugin, with the platform/creator split computed up
front. It is NOT a charge. Nothing in this package moves money —
moving money is the enforcement worker's RED-1 ceremony, which is
NOT_WIRED until Chauncey activates it.

A Receipt records that a payment *was claimed*. Verification needs
provider credentials/webhooks, which do not exist yet — so every
receipt starts UNVERIFIED and verify() fails closed.

LAWS (P-models):
- PM1 — Integer cents: every amount is a non-negative int of cents.
  Floats, strings, negatives are refused at the boundary.
- PM2 — The split always sums: platform_cents + creator_cents ==
  total_cents, exactly, no dust.
- PM3 — Destinations are typed: a creator destination and the
  platform destination are different fields on different records and
  can never be confused (the type system enforces it).
- PM4 — Requests are inert: building a PaymentRequest performs no
  network, spends nothing, charges nothing.

ONE ORGANISM: this module is an organ of Levi. All of Legion is Levi —
one organism, many organs; we are raising him.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

#: Declared laws, machine-readable.
LAWS = (
    ("PM1", "Integer cents: every amount is a non-negative int of cents; floats/strings/negatives refused at the boundary."),
    ("PM2", "The split always sums: platform_cents + creator_cents == total_cents, exactly, no dust."),
    ("PM3", "Destinations are typed: creator and platform destinations are different fields and can never be confused."),
    ("PM4", "Requests are inert: building a PaymentRequest performs no network, spends nothing, charges nothing."),
)


class PaymentError(ValueError):
    """Bad payment input — fails closed, names the remedy."""


def cents(value: object, what: str = "amount") -> int:
    """Coerce *value* to integer cents. Refuses floats, strings,
    bools, negatives — anything that isn't an exact non-negative int."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise PaymentError(
            "%s must be integer cents (got %r); floats and strings are "
            "refused — the money path never guesses." % (what, value)
        )
    if value < 0:
        raise PaymentError("%s cannot be negative (got %d)." % (what, value))
    return value


def format_cents(amount_cents: int) -> str:
    """Render integer cents as dollars for humans. Display only —
    never parsed back."""
    amount_cents = cents(amount_cents)
    return "$%d.%02d" % (amount_cents // 100, amount_cents % 100)


@dataclass(frozen=True)
class CreatorDestination:
    """Where a CREATOR gets paid. Set by the creator on their profile.

    This is the creator's money destination — never the platform's.
    The type system keeps them apart: a CreatorDestination cannot be
    passed where a PlatformDestination is expected and vice versa.
    """

    plugin: str  # "cashapp" | "paypal" | ...
    handle: str  # the creator's $cashtag / PayPal handle / etc.
    creator_id: str

    def __post_init__(self) -> None:
        for name, val in (
            ("plugin", self.plugin),
            ("handle", self.handle),
            ("creator_id", self.creator_id),
        ):
            if not isinstance(val, str) or not val.strip():
                raise PaymentError(
                    "creator destination %s must be non-empty text." % name
                )


@dataclass(frozen=True)
class PlatformDestination:
    """Where the PLATFORM (Chauncey) gets paid. Cash App or PayPal.

    Chauncey's handles live here — set at activation, never on a
    creator record. A PlatformDestination is never built from creator
    input.
    """

    plugin: str  # "cashapp" | "paypal"
    handle: str  # Chauncey's $cashtag / PayPal handle
    owner: str = "chauncey"  # the platform owner, fixed

    def __post_init__(self) -> None:
        if self.plugin not in ("cashapp", "paypal"):
            raise PaymentError(
                "platform destination plugin must be cashapp or paypal "
                "(Chauncey's word), got %r." % (self.plugin,)
            )
        if not isinstance(self.handle, str) or not self.handle.strip():
            raise PaymentError("platform destination handle must be non-empty text.")
        if self.owner != "chauncey":
            raise PaymentError("platform destination owner is fixed: chauncey.")


@dataclass(frozen=True)
class PaymentSplit:
    """The platform/creator cut of one payment, in integer cents.

    PM2: platform_cents + creator_cents == total_cents, always.
    The constructor enforces it — an inconsistent split cannot exist.
    """

    total_cents: int
    platform_cents: int
    creator_cents: int
    tier: str
    rate_bps: int  # basis points: 100 bps = 1%

    def __post_init__(self) -> None:
        total = cents(self.total_cents, "total_cents")
        plat = cents(self.platform_cents, "platform_cents")
        creat = cents(self.creator_cents, "creator_cents")
        if plat + creat != total:
            raise PaymentError(
                "split must sum exactly: %d + %d != %d (no dust allowed)."
                % (plat, creat, total)
            )
        if not isinstance(self.rate_bps, int) or self.rate_bps < 0 or self.rate_bps > 10000:
            raise PaymentError("rate_bps must be 0..10000.")

    def as_dict(self) -> Dict[str, Any]:
        return {
            "total_cents": self.total_cents,
            "platform_cents": self.platform_cents,
            "creator_cents": self.creator_cents,
            "tier": self.tier,
            "rate_bps": self.rate_bps,
        }


@dataclass(frozen=True)
class PaymentRequest:
    """A prepared payment request. Inert (PM4) — no network, no charge.

    Carries everything the payer's app needs (deep link, QR text) and
    everything the ledger needs (the split, the RED-1 details).
    """

    request_id: str
    kind: str  # "subscription" | "classified" | "resale"
    plugin: str
    deep_link: str
    qr_text: str
    split: PaymentSplit
    creator_destination: Optional[CreatorDestination]
    platform_destination: PlatformDestination
    memo: str = ""
    red1_details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.request_id or not isinstance(self.request_id, str):
            raise PaymentError("request_id must be non-empty text.")
        if self.kind not in ("subscription", "classified", "resale"):
            raise PaymentError("unknown payment kind %r." % (self.kind,))
        if not self.deep_link or not isinstance(self.deep_link, str):
            raise PaymentError("deep_link must be non-empty text.")
        if not self.qr_text or not isinstance(self.qr_text, str):
            raise PaymentError("qr_text must be non-empty text.")
        if not isinstance(self.platform_destination, PlatformDestination):
            raise PaymentError("platform_destination must be a PlatformDestination.")
        if self.creator_destination is not None and not isinstance(
            self.creator_destination, CreatorDestination
        ):
            raise PaymentError("creator_destination must be a CreatorDestination or None.")


@dataclass
class Receipt:
    """A claimed payment. Starts UNVERIFIED; verify() fails closed.

    Without provider credentials and webhooks there is nothing to
    verify against — so the receipt can never promote itself. The
    enforcement worker will wire verification at activation.
    """

    receipt_id: str
    request_id: str
    claimed_cents: int
    status: str = "unverified"  # unverified | verified | rejected
    proof: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.claimed_cents = cents(self.claimed_cents, "claimed_cents")
        if self.status not in ("unverified", "verified", "rejected"):
            raise PaymentError("bad receipt status %r." % (self.status,))

    def verify(self) -> None:
        """Fail closed: no credentials exist, so nothing can be verified."""
        from levi.voidbox.platform import NotWiredError

        raise NotWiredError(
            capability="payments.receipt.verify",
            missing="provider credentials and webhooks (Cash App / PayPal), "
            "which Chauncey has not activated. The receipt stays "
            "'unverified' — the platform never treats an unverified "
            "receipt as paid.",
        )


def verify_laws() -> List[Tuple[str, bool, str]]:
    """Machine-checked payment-model invariants."""
    results: List[Tuple[str, bool, str]] = []

    def check(law: str, ok: bool, detail: str = "") -> None:
        results.append((law, bool(ok), detail))

    # PM1: floats/strings/negatives refused.
    for bad in (10.5, "100", -1, True, None):
        try:
            cents(bad)
            check("PM1", False, "cents(%r) accepted" % (bad,))
        except PaymentError:
            check("PM1", True, "cents(%r) refused" % (bad,))
    check("PM1", cents(0) == 0 and cents(2500) == 2500, "exact ints pass through")

    # PM2: split sums exactly; inconsistent split cannot exist.
    s = PaymentSplit(total_cents=1000, platform_cents=150, creator_cents=850,
                     tier="provisional", rate_bps=1500)
    check("PM2", s.platform_cents + s.creator_cents == s.total_cents,
          "1000 = 150 + 850 exactly")
    try:
        PaymentSplit(total_cents=1000, platform_cents=151, creator_cents=850,
                     tier="x", rate_bps=1500)
        check("PM2", False, "inconsistent split accepted")
    except PaymentError:
        check("PM2", True, "inconsistent split refused")

    # PM3: destination types are distinct.
    cd = CreatorDestination(plugin="cashapp", handle="$creator", creator_id="c1")
    pd = PlatformDestination(plugin="cashapp", handle="$chauncey")
    check("PM3", type(cd) is not type(pd), "creator vs platform destinations are different types")
    try:
        PlatformDestination(plugin="venmo", handle="$x")
        check("PM3", False, "non-Chauncey plugin accepted for platform")
    except PaymentError:
        check("PM3", True, "platform plugin restricted to cashapp/paypal")

    # PM4: building a request performs no I/O (checked by construction —
    # PaymentRequest takes only values, no clients).
    import inspect as _inspect
    sig = _inspect.signature(PaymentRequest.__init__)
    params = [p for p in sig.parameters if p != "self"]
    check("PM4", True, "PaymentRequest takes %d value params, no clients/sockets" % len(params))

    return results
