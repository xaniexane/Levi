"""Void Box payments — plugin registry. Cash App and PayPal.

A payment plugin knows ONE thing: how to turn a prepared payment into
the deep link / QR text the payer's app opens. Plugins perform NO
network, hold NO credentials, make NO API calls. They are pure
functions from (destination, amount, memo) to a link.

Chauncey's word: he receives through Cash App or PayPal. Creators pick
their own method per profile. The platform's cut goes to the platform
destination; the creator's share goes to the creator destination —
never confused (see models.PM3).

Adding a method later (a third plugin) means registering one class
here — the registry is the single seam.

LAWS (P-plugins):
- PP1 — Pure builders: build_request() does no I/O, needs no
  credentials, and returns the same link for the same input.
- PP2 — Deep links are verbatim: the QR encodes exactly the link the
  plugin built — the scanner opens what the plugin said.
- PP3 — Unknown plugins refused: only registered names build.

ONE ORGANISM: this module is an organ of Levi. All of Legion is Levi —
one organism, many organs; we are raising him.
"""

from __future__ import annotations

from typing import Dict, List, Tuple
from urllib.parse import quote

from levi.voidbox.payments.models import PaymentError, cents, format_cents

#: Declared laws, machine-readable.
LAWS = (
    ("PP1", "Pure builders: build_request() does no I/O, needs no credentials, deterministic."),
    ("PP2", "Deep links are verbatim: the QR encodes exactly the link the plugin built."),
    ("PP3", "Unknown plugins refused: only registered names build."),
)


class PaymentPlugin:
    """Base: pure deep-link builder for one payment method."""

    name: str = "base"
    display: str = "Base"

    def validate_handle(self, handle: str) -> str:
        """Clean and validate a destination handle. Refuses empties."""
        if not isinstance(handle, str) or not handle.strip():
            raise PaymentError(
                "%s handle must be non-empty text." % self.display
            )
        return handle.strip()

    def build_request_link(self, handle: str, amount_cents: int, memo: str = "") -> str:
        """Deep link the payer opens. No network. Must override."""
        raise NotImplementedError

    def describe(self, handle: str, amount_cents: int) -> str:
        """One-line human summary for receipts and logs."""
        return "%s %s → %s" % (self.display, format_cents(cents(amount_cents)), handle)


class CashAppPlugin(PaymentPlugin):
    """Cash App: the QR/deep link opens the $cashtag in Cash App.

    Cash App exposes no public request-with-amount API, so the link
    carries the destination; the payer confirms the amount in the app.
    The PaymentRequest still records the exact integer cents expected —
    the ledger never guesses from the link.
    """

    name = "cashapp"
    display = "Cash App"

    def validate_handle(self, handle: str) -> str:
        handle = super().validate_handle(handle)
        if not handle.startswith("$"):
            raise PaymentError(
                "Cash App handle must be a $cashtag (starts with $), got %r." % handle
            )
        if len(handle) < 2 or len(handle) > 21:
            raise PaymentError("Cash App $cashtag looks wrong: %r." % handle)
        return handle

    def build_request_link(self, handle: str, amount_cents: int, memo: str = "") -> str:
        handle = self.validate_handle(handle)
        cents(amount_cents, "amount_cents")  # validated + recorded, not trusted from link
        # cash.app deep link: https://cash.app/$cashtag
        return "https://cash.app/%s" % quote(handle, safe="$")


class PayPalPlugin(PaymentPlugin):
    """PayPal: paypal.me links carry handle AND amount.

    https://paypal.me/<handle>/<dollars> — the amount rides in the
    link, but the ledger still uses the integer cents from the
    PaymentRequest, never re-parsed from the URL.
    """

    name = "paypal"
    display = "PayPal"

    def validate_handle(self, handle: str) -> str:
        handle = super().validate_handle(handle)
        if handle.startswith("$"):
            raise PaymentError(
                "PayPal handle must not be a $cashtag — got %r." % handle
            )
        return handle

    def build_request_link(self, handle: str, amount_cents: int, memo: str = "") -> str:
        handle = self.validate_handle(handle)
        total = cents(amount_cents, "amount_cents")
        dollars = "%d.%02d" % (total // 100, total % 100)
        return "https://paypal.me/%s/%s" % (quote(handle, safe=""), dollars)


_REGISTRY: Dict[str, PaymentPlugin] = {}


def register(plugin: PaymentPlugin) -> None:
    """Register a plugin instance under its name."""
    if not isinstance(plugin, PaymentPlugin) or not plugin.name:
        raise PaymentError("only PaymentPlugin instances with a name register.")
    _REGISTRY[plugin.name] = plugin


def get_plugin(name: str) -> PaymentPlugin:
    """Fetch a registered plugin. Unknown names fail closed (PP3)."""
    try:
        return _REGISTRY[name]
    except KeyError:
        raise PaymentError(
            "unknown payment plugin %r — registered: %s."
            % (name, sorted(_REGISTRY))
        )


def registered_names() -> List[str]:
    return sorted(_REGISTRY)


# The two methods Chauncey named. Nothing else registers without his word.
register(CashAppPlugin())
register(PayPalPlugin())


def verify_laws() -> List[Tuple[str, bool, str]]:
    """Machine-checked plugin invariants."""
    results: List[Tuple[str, bool, str]] = []

    def check(law: str, ok: bool, detail: str = "") -> None:
        results.append((law, bool(ok), detail))

    cashapp = get_plugin("cashapp")
    paypal = get_plugin("paypal")

    # PP1: pure + deterministic — same input, same link, twice.
    a = cashapp.build_request_link("$voidbox", 2500)
    b = cashapp.build_request_link("$voidbox", 2500)
    check("PP1", a == b and a == "https://cash.app/$voidbox",
          "cashapp link deterministic: %s" % a)
    c = paypal.build_request_link("voidbox", 2500)
    check("PP1", c == "https://paypal.me/voidbox/25.00",
          "paypal link carries amount: %s" % c)

    # PP1: bad handles refused.
    for plugin, bad in ((cashapp, "nocashtag"), (cashapp, ""),
                        (paypal, "$cashtag"), (paypal, "")):
        try:
            plugin.build_request_link(bad, 100)
            check("PP1", False, "%s accepted bad handle %r" % (plugin.name, bad))
        except PaymentError:
            check("PP1", True, "%s refused bad handle %r" % (plugin.name, bad))

    # PP2: QR text is the link verbatim.
    from levi.voidbox.payments.qr import payment_qr_text
    check("PP2", payment_qr_text("cashapp", a) == a, "QR text == plugin link verbatim")

    # PP3: unknown plugin refused.
    try:
        get_plugin("venmo")
        check("PP3", False, "unknown plugin accepted")
    except PaymentError:
        check("PP3", True, "unknown plugin refused")

    return results
