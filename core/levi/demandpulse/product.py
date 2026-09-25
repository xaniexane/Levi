"""DemandPulse customer product definition.

The $6/month standalone customer product (Chauncey's word, 2026-09-21).
Single source of truth for the price anchor, the 12% platform cut, the
feature slate (parity + exclusives), and the honest limits that ship in
customer copy.

Honesty rule: every shipped feature cites the module that implements it;
anything not yet built is marked ``planned`` and never claimed. Competitor
prices are secondary-source approximations (see the KFX2 plan teardown) —
the verification caveat ships with every customer-facing price comparison.
"""

from __future__ import annotations

PRODUCT_NAME = "DemandPulse"
PRODUCT_TAGLINE = (
    "Demand sensing that runs on your machine — no cloud, no meter, no tiers."
)
PRODUCT_VERSION = "0.1.0"

# Price anchor — founder's word, 2026-09-21. The charge path for this price
# is STUBBED in payments.py; it stays dark until the owner approves it.
PRICE_MONTHLY = 6.0
PRICE_CURRENCY = "USD"

# KFX2 doctrine PL-05: 12% platform cut on digital products monetized
# on-platform. Named constant — never a magic number.
PLATFORM_CUT = 0.12

# No-free-core doctrine: no free tier that bleeds us; dollar-scale entry.
NO_FREE_TIER = True
ENTRY_TIERS = ("monthly",)  # the only tier that exists

# Competitor price ranges from the KFX2 teardown (secondary sources, NOT
# vendor-verified — the caveat is part of the copy, not a footnote).
COMPETITOR_PRICE_CAVEAT = (
    "Competitor prices below are approximate, drawn from secondary comparison "
    "sources crawled in 2026 (not live vendor pricing pages). Re-verify against "
    "each vendor's current pricing page before quoting them."
)

# Feature slate. ``module`` is the implementing module — the honest column.
# ``status`` is "shipped" or "planned"; "gated" means it needs the owner's
# word (e.g. push/email channels need his setup).
FEATURES = [
    {
        "name": "Zero-config saved-search simplicity",
        "parity_with": "Google Alerts",
        "module": "levi.demandpulse.quickstart",
        "status": "shipped",
        "note": "one command: keywords in, watch alerts installed, digest path out",
    },
    {
        "name": "Polite keyless public-source ingestion",
        "parity_with": "Brand24 source breadth",
        "module": "levi.demand.ingest",
        "status": "shipped",
        "note": "dead source fails to an empty list, never an exception",
    },
    {
        "name": "Cluster / label / score processing",
        "parity_with": "Mention keyword precision",
        "module": "levi.demand.processing",
        "status": "shipped",
        "note": "signals clustered and scored, not keyword-hit counting",
    },
    {
        "name": "Five-factor ScoreCards with basis notes",
        "parity_with": "Brand24 AI interpretation",
        "module": "levi.demand.scoring",
        "status": "shipped",
        "note": "every factor carries a basis note; basis-less cards are rejected",
    },
    {
        "name": "Alert engine: threshold / briefing / watch / reminder",
        "parity_with": "Mention alerts, Brand24 digests",
        "module": "levi.demand.alerts",
        "status": "shipped",
        "note": "dedup by law, quiet hours, console + file outbox",
    },
    {
        "name": "10 workflow alerts (briefings, breakout watch, reminders)",
        "parity_with": "Brand24 automated digests",
        "module": "levi.demand.workflows",
        "status": "shipped",
        "note": "idempotent install into the customer's own alert store",
    },
    {
        "name": "SI-native feed: rank / tier / dedupe / quarantine",
        "parity_with": "Exploding Topics feed",
        "module": "levi.demand.feed",
        "status": "shipped",
        "note": "unprovable items are quarantined, never published",
    },
    {
        "name": "Competitor tracking + upgrade recommender",
        "parity_with": "none — the closed loop is the exclusive",
        "module": "levi.demand.competition",
        "status": "shipped",
        "note": "trend → gap map → labeled upgrade proposal, founder's word gates apply",
    },
    {
        "name": "Authority engine: action classification + refusal",
        "parity_with": "none — advisory-only architecture",
        "module": "levi.demand.authority",
        "status": "shipped",
        "note": "consequential actions refused without the founder's explicit word",
    },
    {
        "name": "Auditable include/exclude keyword filters",
        "parity_with": "Mention Boolean precision",
        "module": "levi.demandpulse.quickstart",
        "status": "shipped",
        "note": "filter sets stored in filters.json — readable back, no query language",
    },
    {
        "name": "Ternary signal states (dormant / gathering / breakout)",
        "parity_with": "none — the skipped third state",
        "module": "levi.demandpulse.ternary",
        "status": "shipped",
        "note": "'gathering' names what binary hot/not dashboards leave invisible",
    },
    {
        "name": "Scout + Verifier twin pass",
        "parity_with": "none — the paired mind",
        "module": "levi.demandpulse.twins",
        "status": "shipped",
        "note": "scout proposes from scans, verifier publishes or quarantines with reasons",
    },
    {
        "name": "Themed briefing renderer (file outbox)",
        "parity_with": "Brand24 reports",
        "module": "levi.demandpulse.briefing",
        "status": "shipped",
        "note": "tiered sections + quarantine appendix + label legend; never emailed by us",
    },
    {
        "name": "Growth-shape classification (regular / peaked / exploding / consistent)",
        "parity_with": "Exploding Topics growth classification",
        "module": "levi.demand.processing",
        "status": "planned",
        "note": "KFX2 phase P2 — not claimed until it ships",
    },
    {
        "name": "Meta-trend roll-up (meta-trend → clusters → signals)",
        "parity_with": "Exploding Topics Meta trends",
        "module": "levi.demand.feed",
        "status": "planned",
        "note": "KFX2 phase P2 — not claimed until it ships",
    },
    {
        "name": "Push / email notification channels",
        "parity_with": "Mention / Brand24 alerts",
        "module": "levi.demand.alerts",
        "status": "gated",
        "note": "declared-but-not-configured; needs the owner's device/mail setup word",
    },
]

# Exclusives — what the competitors don't offer at any tier.
EXCLUSIVES = [
    "The label law: every item graded OBSERVED / INFERENCE / HYPOTHESIS with "
    "a basis note; whatever can't prove a basis is QUARANTINED, never published.",
    "The closed loop: trend → competitive gap map → labeled upgrade proposal "
    "in one module — discovery stops at seeing; we close the loop.",
    "The archive: every scan filed and auditable — against silent misses.",
    "Advisory-only architecture: proposals are HYPOTHESIS and applying "
    "anything needs the founder's explicit word, stated on every proposal.",
    "Zero metering: no mentions/month caps, no tier-gated interpretation "
    "layer, no collection cliff — local physics has no marginal cost.",
]

# Honest limits — ship in customer copy, verbatim. Never trimmed for the sale.
HONEST_LIMITS = [
    "No realtime social firehose: sources are polite keyless public reads; "
    "cadences vary per source and per run.",
    "Scores are HYPOTHESIS — advisory, never a claim about real demand.",
    "Push and email channels are not configured — alerts go to the console "
    "and the file outbox until the owner sets them up.",
    "Growth-shape classification and meta-trend roll-ups are planned, not "
    "shipped — customer copy must not claim them.",
    COMPETITOR_PRICE_CAVEAT,
]


# ---------------------------------------------------------------------------
# HQ Decision 5 — customer copy (APPROVED 2026-09-24, Chauncey's word).
# This is the decided product sheet. product_sheet() returns it VERBATIM —
# every claim cites a shipped module, planned items are never claimed,
# honest limits are printed in, not footnoted away. Do not paraphrase.
# ---------------------------------------------------------------------------
PRODUCT_SHEET_HQ5 = """**DemandPulse — $6/month**

Demand sensing that runs on your machine — no cloud, no meter, no tiers.

You type keywords in. It watches public sources, clusters what it finds,
and scores it on five factors with a written basis for every score. You get
threshold alerts, morning briefings, breakout watches, and reminders — to
your console and a file outbox you own. Anything it can't prove gets
quarantined, never published.

What $6/month buys — everything included, no tiers:
- Saved-search watching: one command, keywords in, alerts installed
- Signal clustering and five-factor score cards, every factor with a basis note
- Alert engine: threshold, briefing, watch, reminder — 10 workflow alerts,
  dedup by law, quiet hours
- Scout + Verifier twin pass: scout proposes, verifier publishes or
  quarantines with reasons
- Ternary signal states — dormant / gathering / breakout. "Gathering" names
  what binary hot-or-not dashboards leave invisible
- Competitor tracking → gap map → labeled upgrade proposals. Advisory only:
  applying anything needs your word, stated on every proposal
- Auditable include/exclude keyword filters — readable back, no query language
- Themed briefing renderer with quarantine appendix and label legend
- The label law: every item graded OBSERVED / INFERENCE / HYPOTHESIS
- Zero metering: no mentions-per-month caps, no tier-gated features

Honest limits:
- Sources are polite public reads, not a realtime firehose; cadences vary.
- Scores are hypotheses — advisory, never a claim about real demand.
- Push and email alerts aren't set up — alerts go to your console and file
  outbox.
- Growth-shape classification and meta-trend roll-ups are on the roadmap,
  not shipped. We don't claim them.

One price: $6/month. No tiers, no free tier, no meter. Pay by Cash App —
$DirectDepositDaemon. Nothing auto-charges, so there's nothing to cancel:
stop paying and access runs out at month's end.

7-day refund: full $6 back, no questions, within 7 days of payment."""


def shipped_features():
    """Features the customer actually gets today."""
    return [f for f in FEATURES if f["status"] == "shipped"]


def planned_features():
    """Features on the roadmap — never claimed as shipped."""
    return [f for f in FEATURES if f["status"] == "planned"]


def monthly_price_line() -> str:
    """The anchor as customer copy."""
    return (
        f"${PRICE_MONTHLY:.0f}/month ({PRICE_CURRENCY}) — no tiers, "
        f"no mention caps, no per-seat metering. (Billing is owner-gated: "
        f"see payments.py.)"
    )


def product_sheet() -> str:
    """The decided customer product sheet — HQ Decision 5, verbatim.

    Approved 2026-09-24 (Chauncey's word). Returned exactly as decided;
    no paraphrase, no trimming.
    """
    return PRODUCT_SHEET_HQ5
