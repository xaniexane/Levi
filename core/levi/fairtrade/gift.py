"""The Gift Ledger: every "free" gift gets a receipt.

The giants price their gifts in silence. The price is never the sticker —
it's the data, the defaults, and the attention the gift moves underneath.
A gift whose price is hidden is not generous; it's a trade that refused
to name itself.

LEVI's honest inversion: no gift ships without a receipt. ``price_of_free``
declares the extraction in plain words and scores the gift's honesty.
A gift that takes nothing scores high. A gift that takes everything and
calls it "free" scores near zero — and the receipt says so, out loud.

Perpetual-hunt provenance: evening hunt 2026-09-24, the "free that wasn't"
vein — Onavo Protect (the free VPN that was Facebook's spyware), the
Windows 10 free-upgrade GWX campaign (the free OS that reprogrammed the
meaning of "cancel"), and the Google Assistant contractor recordings
(the free assistant staffed by hidden humans). Clean-room analysis from
publicly documented mechanics; no proprietary code fetched or copied.

stdlib-only, local-first, no network, no telemetry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# Bait words: "generous" language that hides the absence of a price tag.
# The word "free" is not the problem — a free thing with a full receipt is
# honest. The problem is "free" with no receipt.
BAIT_WORDS = (
    "free",
    "no cost",
    "zero cost",
    "at no charge",
    "complimentary",
    "on the house",
)


# Known extraction shapes, in plain words. A GiftOffer names which of these
# it performs; anything the giver takes that isn't named here (or in
# free-form ``other_extraction``) is an undeclared take.
EXTRACTION_SHAPES = (
    "browsing data",          # which sites/apps you use, for how long
    "app usage data",         # which apps installed, time per app
    "location",               # where the device is
    "messages and photos",    # content on the device
    "voice recordings",       # microphone audio, including misfires
    "contacts and social graph",
    "attention minutes",      # engagement the gift harvests
    "defaults flipped",       # settings the gift changes for you
    "telemetry",              # diagnostics folded into behavior data
    "training data",          # your input used to train the giver's models
)


@dataclass(frozen=True)
class GiftOffer:
    """One "free" gift, stated honestly.

    - ``giver``: who gives it.
    - ``name``: the gift's name.
    - ``gift_pitch``: the giver's own words for the gift (their marketing).
    - ``stated_price``: what the giver says it costs (usually "free").
    - ``extraction``: plain-word list of what the gift takes from the
      recipient. Empty means nothing taken — only when true.
    - ``extraction_unknown``: True when the giver never declared what the
      gift takes. A gift with unknown extraction cannot be scored above a
      floor — the silence is itself the finding.
    - ``declares_nothing_taken``: True when the giver explicitly declares
      the gift takes nothing. Honest only when true; an empty extraction
      list alone is not enough, because silence looks identical to
      nothing.
    - ``targeted_audience``: e.g. "teens 13-17", if the gift hunts a
      specific group.
    - ``consent_reversible``: can the recipient take it back (revoke,
      uninstall, opt out) and keep what they had before?
    """

    giver: str
    name: str
    gift_pitch: str
    stated_price: str = "free"
    extraction: List[str] = field(default_factory=list)
    extraction_unknown: bool = False
    declares_nothing_taken: bool = False
    targeted_audience: str = ""
    consent_reversible: bool = True

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("gift must have a name")
        if not self.giver or not self.giver.strip():
            raise ValueError("gift must name its giver")
        if not self.extraction and not self.extraction_unknown \
                and not self.declares_nothing_taken:
            raise ValueError(
                "gift %r: declare what it takes, declare nothing taken, "
                "or set extraction_unknown=True; a 'free' gift that says "
                "nothing is exactly the pattern this ledger exists to "
                "catch" % self.name
            )


def price_of_free(offer: GiftOffer) -> Dict[str, object]:
    """Price a "free" gift. Returns the receipt data.

    ``honesty_score`` is 0-100, deliberately conservative:
    - starts at 100 (nothing taken)
    - each distinct extraction category costs 12
    - unknown extraction caps the score at 20 — the gift cannot prove
      honesty without a declaration
    - irreversible consent costs 15 more
    - targeting a vulnerable audience (teens named) costs 10 more
    """
    if not isinstance(offer, GiftOffer):
        raise ValueError("price_of_free needs a GiftOffer")
    takes = list(offer.extraction)
    score = 100
    findings: List[str] = []
    if offer.extraction_unknown:
        score = min(score, 20)
        findings.append(
            "extraction undeclared: the giver never said what the gift "
            "takes — the silence is priced as the maximum"
        )
    else:
        score -= 12 * len(takes)
    if not offer.consent_reversible:
        score -= 15
        findings.append(
            "consent is one-way: the gift cannot be taken back or the "
            "defaults it flipped stay flipped"
        )
    if offer.targeted_audience and "teen" in offer.targeted_audience.lower():
        score -= 10
        findings.append(
            "hunts a young audience (%s): poverty or youth is being "
            "priced into the trade" % offer.targeted_audience
        )
    score = max(0, score)
    if score >= 80:
        verdict = "honest gift"
    elif score >= 50:
        verdict = "costly gift — read the receipt before accepting"
    elif score > 20:
        verdict = "a trade wearing a gift's clothes"
    else:
        verdict = "not a gift — an extraction that forgot to charge money"
    return {
        "gift": "%s by %s" % (offer.name, offer.giver),
        "stated_price": offer.stated_price,
        "takes": takes if not offer.extraction_unknown else ["undeclared"],
        "honesty_score": score,
        "verdict": verdict,
        "findings": findings,
    }


def gift_receipt(offer: GiftOffer) -> str:
    """Render the gift's receipt in plain speech, one page, no fine print."""
    priced = price_of_free(offer)
    takes = priced["takes"]
    if takes == ["undeclared"]:
        takes_line = "WHAT IT TAKES: undeclared — the giver never said."
    elif not takes:
        takes_line = "WHAT IT TAKES: nothing."
    else:
        takes_line = "WHAT IT TAKES: " + "; ".join(takes) + "."
    lines = [
        "GIFT RECEIPT",
        "Gift: %s" % priced["gift"],
        "Stated price: %s" % priced["stated_price"],
        "Pitch (their words): %s" % offer.gift_pitch,
        takes_line,
        "Honesty score: %d/100 — %s" % (priced["honesty_score"], priced["verdict"]),
    ]
    for finding in priced["findings"]:
        lines.append("Finding: %s" % finding)
    lines.append("Rule: a gift with no receipt is a bill that hasn't arrived yet.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Seeded catalog: the evening-2026-09-24 "free that wasn't" finds.
# ---------------------------------------------------------------------------

def _seed_catalog() -> List[GiftOffer]:
    return [
        GiftOffer(
            giver="Facebook",
            name="Onavo Protect",
            gift_pitch="a free VPN that protects your data and keeps you safe",
            stated_price="free",
            extraction=[
                "browsing data",
                "app usage data",
                "messages and photos",
            ],
            targeted_audience="teens 13-35 (Project Atlas successor paid teens $20/mo)",
            consent_reversible=False,
        ),
        GiftOffer(
            giver="Microsoft",
            name="Windows 10 free upgrade (GWX campaign)",
            gift_pitch="a free upgrade to Windows 10 for all Windows 7/8.1 users",
            stated_price="free (one year)",
            extraction=[
                "telemetry",
                "defaults flipped",
                "attention minutes",
            ],
            consent_reversible=False,
        ),
        GiftOffer(
            giver="Google",
            name="Google Assistant (contractor review era)",
            gift_pitch="your free AI assistant, always ready to help",
            stated_price="free",
            extraction=[
                "voice recordings",
                "training data",
            ],
            consent_reversible=True,
        ),
    ]


GIFT_CATALOG: List[GiftOffer] = _seed_catalog()


def catalog_ids() -> List[str]:
    return [g.name for g in GIFT_CATALOG]


def get_gift(name: str) -> Optional[GiftOffer]:
    for g in GIFT_CATALOG:
        if g.name == name:
            return g
    return None
