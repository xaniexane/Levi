"""LEVI counter-play: aware of their trades, exploiting the opposite.

The catalog in trades.py records what the giants do. This module records
what LEVI does about it — not as moral posture, but as strategy. Each
sly-generosity trade has a tell: the thing the giant refuses to give.
LEVI gives exactly that thing, on purpose, because the honest inversion
is the profit engine and the popularity engine at once:

- Profit: the core costs nothing to produce (stdlib-only, local-first),
  so the honest version can be given away whole. Money lives in the
  layers on top — managed delivery, curated feeds, premium packs —
  bought by users who trust the foundation because it cannot trap them.
- Popularity: people evangelize what they own and flee what owns them.
  Every inversion below is a story users repeat unprompted.

Each entry names the concrete LEVI-native technique, how it makes money,
why it spreads, and where LEVI already proves it (no vapor).
"""

from __future__ import annotations

from typing import Dict, List

from .trades import pattern_ids

COUNTERPLAYS: Dict[str, Dict[str, str]] = {
    "walled-garden-generosity": {
        "technique": (
            "Open-gate generosity: give the whole thing, with one-command "
            "full export (code, issues, PRs, stars, CI history — everything). "
            "No leash, no approved-partner list, no curated subset. The gift "
            "must survive the user leaving with all of it; if it needs a "
            "fence to keep paying off, it was never a gift."
        ),
        "profit_engine": (
            "Zero-marginal-cost core means the honest version can be given "
            "away whole and still cost nothing. Export is the funnel: people "
            "try LEVI because leaving is free, and the users who stay are "
            "the ones who chose to. Money lives in the layers on top — "
            "managed delivery, curated feeds, premium packs — bought by "
            "people who trust the foundation precisely because it cannot "
            "hold them hostage."
        ),
        "popularity_engine": (
            "Ownership creates trust, trust creates retention, retention "
            "creates evangelists. Portability is the retention mechanic: "
            "users market the product every time they show someone their "
            "export working elsewhere."
        ),
        "levi_proof": (
            "LEVI Forge: one-command complete export; life-pack export/import "
            "of the whole organism; local-first with no account to trap."
        ),
    },
    "asymmetric-rules": {        "technique": (
            "Symmetric-by-construction: every policy LEVI enforces is "
            "machine-checkable and binds LEVI's own components identically. "
            "The rule-maker obeys the rule — enforced in code, not promised "
            "in prose. Asymmetry is treated as the tell of a weapon, and "
            "LEVI's own rules are audited against themselves."
        ),
        "profit_engine": (
            "Trust is the enterprise feature. Teams pay for platforms that "
            "provably cannot cheat them — compliance-as-code sells to every "
            "buyer the giants price out with legal departments. A rule that "
            "binds its maker is a moat no marketing budget can buy."
        ),
        "popularity_engine": (
            "'The platform that obeys its own rules' is a story people "
            "repeat unprompted. Developers build on substrates they can "
            "audit; auditors become advocates."
        ),
        "levi_proof": (
            "Games Fair Play Charter: 7 machine-checkable rules; "
            "check_no_mask() enforces the identity law in code; "
            "InterpenetrationEngine inherits the strictest risk ceiling — "
            "the composer obeys the same ceilings as the composed."
        ),
    },
    "roach-motel-funnel": {
        "technique": (
            "One-door exit: enter and exit through the same door. Cancel, "
            "export, and delete in one command — no retention gauntlet, no "
            "sixteen-step labyrinth, no 'are you sure' dark patterns. The "
            "exit is tested like a feature, because it is one."
        ),
        "profit_engine": (
            "Users who stay chose to stay: higher lifetime value, lower "
            "support cost, evangelists instead of hostages. Churn honesty "
            "forces the product to be genuinely good, which compounds — "
            "every retained user is retained by merit, and merit is the "
            "cheapest acquisition channel that exists."
        ),
        "popularity_engine": (
            "'You can leave in one click' is the most disarming sentence in "
            "marketing. It inverts the trust calculation at signup: the "
            "easier the exit, the braver the entry, the louder the "
            "word-of-mouth."
        ),
        "levi_proof": (
            "Local-first: there is no account and no subscription to trap; "
            "Forge complete export; life-pack portability — leaving with "
            "everything is a designed workflow, not an escape."
        ),
    },
    "manufactured-social-debt": {
        "technique": (
            "Earned continuity: progress the user owns. Streaks are personal "
            "records, never hostage mechanics — missing a day costs nothing, "
            "nothing breaks, nothing guilts. The game respects the player; "
            "continuity is earned by being worth returning to, not by "
            "manufacturing obligation."
        ),
        "profit_engine": (
            "Genuine engagement converts better than coerced engagement. "
            "Sell depth — new games, premium packs, richer worlds — not "
            "ransom (pay to keep your streak alive). Players who are never "
            "punished spend willingly; players who are punished churn the "
            "moment a kinder competitor appears."
        ),
        "popularity_engine": (
            "Respect compounds. Players bring friends to fair games; nobody "
            "recruits friends into a guilt machine. Fair mechanics are the "
            "marketing — 'the game that never punishes you for having a life' "
            "is a sentence players say for you."
        ),
        "levi_proof": (
            "Games Fair Play Charter (no predatory monetization, "
            "machine-checked); player-owned portable saves — progress "
            "survives outside LEVI, so it never needs to hold the player."
        ),
    },
    "bait-and-rug-free-tier": {
        "technique": (
            "The Free-Tier Covenant: every LEVI free offer is stated in "
            "plain numbers from day one, ships with a written grandfather "
            "clause, and is machine-audited by covenant.py. 'Unlimited' is "
            "banned as a word unless a number stands behind it. Any "
            "narrowing applies to new users only — existing users keep "
            "what they were given, in writing."
        ),
        "profit_engine": (
            "Local-first costs nothing per user, so the covenant costs "
            "nothing to keep: there is no server bill that forces the "
            "rug-pull. Money lives in layers on top — managed delivery, "
            "curated packs — whose price is justified by work, not by "
            "withholding."
        ),
        "popularity_engine": (
            "A published covenant is a story users repeat: 'LEVI wrote down "
            "what it will never do.' Trust earned in writing outlives any "
            "launch-day generosity."
        ),
        "levi_proof": (
            "core/levi/fairtrade/covenant.py: FreeTierCovenant + "
            "audit_covenant, wired into the fairtrade public API — "
            "local-first, stdlib-only, no network."
        ),
    },
    "cap-the-habit": {
        "technique": (
            "Covenant floor, never a demo ceiling: the free tier is a "
            "promise that cannot shrink under existing users' feet. If "
            "economics tighten, LEVI shrinks the paid tier's extras — "
            "never the free tier's floor. Rule counts, automations, and "
            "vault contents are local files: no count exists to gate."
        ),
        "profit_engine": (
            "Local files have no per-rule cost, so there is nothing to "
            "monetize by counting. The habit forms around ownership, not "
            "around a cloud meter — and ownership is what users pay to "
            "extend into managed territory."
        ),
        "popularity_engine": (
            "Users who built their homes on LEVI automation advertise the "
            "fact that no update can take three applets away. Permanence "
            "is the feature IFTTT deleted."
        ),
        "levi_proof": (
            "Automation rules as plain local files (local-first, no "
            "count to gate); covenant.py 'never-list' check rejects any "
            "design that shrinks free capacity under existing users."
        ),
    },
    "frozen-generosity": {
        "technique": (
            "The growing floor: every free tier commits to track the "
            "medium — storage prices fall, device capacity rises, and the "
            "covenant says so in writing. No core need is ever gated behind "
            "the maker's own paid path; the mandated-toll check fails the "
            "design outright."
        ),
        "profit_engine": (
            "A floor that grows with the medium costs nothing extra to "
            "promise when the medium is the user's own disk. The paid "
            "offer then competes on work done (curation, delivery, sync "
            "across devices), not on manufactured scarcity."
        ),
        "popularity_engine": (
            "'Still 5 GB after fifteen years' is the giants' most-quoted "
            "broken promise; LEVI's growing floor is the unbreakable "
            "version of the same headline, inverted."
        ),
        "levi_proof": (
            "covenant.py 'grows-with-medium' and 'no-mandated-toll' "
            "checks (local-first, no network); LEVI vault features state "
            "capacity in the user's own disk numbers, not a fiat tier."
        ),
    },
    "engagement-bait-distribution": {
        "technique": (
            "Declared-rationale feeds: every recommendation LEVI surfaces "
            "carries its reasons at declared, user-tunable weights — the "
            "'why am I seeing this' ledger is the primary interface, not a "
            "buried panel. Signals are named, weights are visible, and the "
            "user can turn any signal down to zero. The feed optimizes for "
            "the user's stated goal, never for retention."
        ),
        "profit_engine": (
            "Attention you can audit is attention advertisers and teams "
            "will pay a premium to reach honestly. Declared rationale turns "
            "the feed into a product with a spec sheet — sponsored or "
            "curated layers sell against declared weights, not dark ones. "
            "Money lives in the layers on top: managed curation, premium "
            "signal packs, goal-tuned ranking — bought because the base "
            "feed provably cannot bait."
        ),
        "popularity_engine": (
            "'The feed that tells you why' is the sentence every "
            "recommendation-engine critic repeats. Users who have been "
            "farmed for watch time evangelize the one feed that shows its "
            "work; every shared rationale screenshot is an ad LEVI never "
            "bought."
        ),
        "levi_proof": (
            "recommender engine: declared signal weights with explanations "
            "on every score; feedlab: 'the contributions ARE the "
            "explanation' (local-first, no network, stdlib-only). The FYP "
            "refuses the rationale ledger; LEVI ships it as the default."
        ),
    },
    "community-graph-hostage": {
        "technique": (
            "Community escrow: one-command whole-community export — member "
            "roster, full history, media, roles and permissions, bot and "
            "webhook configs — as import-grade portable artifacts, not "
            "browse-grade souvenirs. Export is community-portable, not just "
            "individual-portable: the community leaves together, with "
            "everything, and the export is verified by a drill against real "
            "artifacts."
        ),
        "profit_engine": (
            "Communities pay for hosting they can leave — managed "
            "reliability, moderation tooling, and premium archives sell "
            "better when exit is free, because the buyer is choosing rather "
            "than trapped. The export itself is the funnel: communities "
            "migrate in BECAUSE they can migrate out. Money lives in the "
            "layers on top: hosted relays, managed moderation, premium "
            "community analytics — all optional, none load-bearing."
        ),
        "popularity_engine": (
            "'The chat platform you can leave' spreads through every "
            "community that has ever been stranded by a ban or a terms "
            "change. Admins are the evangelists: one admin who exports a "
            "5,000-member server intact tells every other admin."
        ),
        "levi_proof": (
            "liberation Ledger: hostage scoring plus export-task receipts "
            "for every seeded service (local-first); games/sunset.py "
            "SunsetPlan proves the escrow-and-drill ritual in LEVI's own "
            "code; circles/hives keep member state in portable local "
            "stores, never server-side."
        ),
    },
    "training-data-toll": {
        "technique": (
            "Consent-first training: every artifact LEVI trains on carries "
            "a machine-checkable consent record — who agreed, scope, "
            "revocability — free for every individual, never a paid-tier "
            "admin control. The native brain trains on LEVI's own corpus; "
            "user data is never training data without explicit, revocable, "
            "per-artifact consent. Provenance on what trained what is "
            "published, not promised."
        ),
        "profit_engine": (
            "Models with clean provenance sell to everyone the giants "
            "price out of legal risk: teams pay for training they can "
            "defend in diligence. Consent-first is the enterprise feature — "
            "auditable data lineage converts directly into contracts. Money "
            "lives in the layers on top: managed fine-tunes on the user's "
            "own consented data, premium corpora with paid-out provenance, "
            "compliance-as-code reports."
        ),
        "popularity_engine": (
            "'The AI that doesn't train on you' is the sentence that ends "
            "every argument about AI data ethics. Developers who watched "
            "their open-source work become someone else's $10/mo product "
            "become the loudest advocates for the one system that asks "
            "first — and proves it in code."
        ),
        "levi_proof": (
            "Native brain: trained from scratch on LEVI's own corpus "
            "(local-first, stdlib-only); growth loop writes only "
            "growth-tagged local memory, never ships it anywhere; "
            "provenance module tracks artifact origins. The Flow "
            "Declaration (fairtrade/flows.py) makes the training consent "
            "machine-checkable — the declaration the giants refuse."
        ),
    },
    "spyware-as-security": {
        "technique": (
            "Security that cannot see: any LEVI tool that touches traffic "
            "or data is built so surveillance is architecturally impossible "
            "— local-first processing, no telemetry home, and a Gift "
            "Ledger receipt (fairtrade/gift.py) naming exactly what the "
            "tool can observe. If the security needs to watch you to "
            "protect you, it is not security."
        ),
        "profit_engine": (
            "Provable non-surveillance is the enterprise sell: 'the tool "
            "that cannot phone home' wins contracts where the giants' "
            "free tiers lose them on compliance review. Trust, "
            "machine-checked, converts to paid tiers the giants cannot "
            "undercut without abandoning their own capture."
        ),
        "popularity_engine": (
            "'The VPN that can't see you' is a story that travels further "
            "than any ad budget. Privacy you can verify beats privacy you "
            "are promised — every independent audit becomes marketing."
        ),
        "levi_proof": (
            "Gift Ledger receipts name the extraction of every 'free' "
            "thing; the native brain runs local-first with no second "
            "audience; LEVI Forge exports leave nothing behind. LEVI never "
            "ships a sensor disguised as a shield."
        ),
    },
    "free-upgrade-with-fine-print-hammer": {
        "technique": (
            "Upgrade consent as a receipt, not a funnel: every LEVI change "
            "ships a machine-checkable consent record — what defaults "
            "changed, what was added, full reversibility path — that "
            "survives the upgrade byte-identical. 'No' means the same "
            "thing after the gift as before it. The corner X keeps its "
            "meaning forever."
        ),
        "profit_engine": (
            "Reversible upgrades are the retention engine the giants "
            "sacrificed: users who can roll back without penalty trust the "
            "next upgrade, and trusted upgrades compound into paid "
            "tiers. Support costs fall when upgrades stop being ambushes, "
            "and the money the giants spend on consent funnels is money "
            "LEVI never has to spend."
        ),
        "popularity_engine": (
            "'Nothing changes without a receipt' is the headline the "
            "giants can never write. Every reversible, receipted upgrade "
            "is a demo of the opposite of the funnel — users evangelize "
            "the platform that asks."
        ),
        "levi_proof": (
            "The FreeTierCovenant (fairtrade/covenant.py) grandfather "
            "clause: terms can never shrink under existing users. Nothing "
            "in LEVI changes defaults silently; the local-first heartbeat "
            "and growth supervisor give up honestly rather than spinning "
            "forever."
        ),
    },
    "assistant-staffed-by-strangers": {
        "technique": (
            "An assistant with no hidden second audience: LEVI's native "
            "brain trains on LEVI-authored material and runs local-first — "
            "no contractor queue, no cloud transcriber, no unnamed "
            "listeners. If a human ever must review, the review is named, "
            "scoped, and revocable: a consent record, not a secret."
        ),
        "profit_engine": (
            "'No strangers hear you' is the premium tier the giants cannot "
            "honestly sell — their business model is the strangers. "
            "Local-first assistance converts privacy from a cost center "
            "into the product's headline feature."
        ),
        "popularity_engine": (
            "The assistant that can't eavesdrop is the one people put in "
            "bedrooms and boardrooms. Placement follows trust; trust "
            "follows architecture, not policy pages."
        ),
        "levi_proof": (
            "Brain training corpus is LEVI-authored (academy journals, "
            "post-mastery ingest); levi-brain is explicit-only and "
            "local-first; the SI refusal doctrine means judgment-based "
            "refusal with no cloud human in the loop. Your words stay on "
            "your machine."
        ),
    },
}


def counterplay(pattern_id: str) -> Dict[str, str]:
    """Return LEVI's counter-play for one sly-trade pattern id."""
    try:
        return COUNTERPLAYS[pattern_id]
    except KeyError:
        raise ValueError(
            "unknown pattern id %r (known: %s)" % (pattern_id, ", ".join(pattern_ids()))
        ) from None


def all_counterplays() -> List[Dict[str, str]]:
    """Every counter-play, in catalog order."""
    from .trades import get_pattern

    out = []
    for pid in pattern_ids():
        entry = {"pattern_id": pid, "pattern_name": get_pattern(pid)["name"]}
        entry.update(COUNTERPLAYS[pid])
        out.append(entry)
    return out


def brief() -> str:
    """The compact awareness brief: what they do, what LEVI does instead.

    Built for LEVI's own agent loop to read before acting in any market
    the giants play in — awareness as a standing input, not a lookup.
    """
    lines = [
        "LEVI is aware of the sly-generosity trades and exploits the opposite:",
    ]
    for cp in all_counterplays():
        lines.append(
            "- %s -> LEVI: %s" % (cp["pattern_name"], cp["technique"].split(":")[0])
        )
    lines.append(
        "Rule: never rebuild their capture. Ship the inversion, price the "
        "layers on top, let trust do the marketing."
    )
    return "\n".join(lines)


def playbook() -> str:
    """The full counter-playbook, human-readable."""
    parts = ["LEVI COUNTER-PLAYBOOK — the opposite, exploited", ""]
    for cp in all_counterplays():
        parts.append("== %s" % cp["pattern_name"])
        parts.append("LEVI technique: %s" % cp["technique"])
        parts.append("Profit engine: %s" % cp["profit_engine"])
        parts.append("Popularity engine: %s" % cp["popularity_engine"])
        parts.append("Already proven by: %s" % cp["levi_proof"])
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"
