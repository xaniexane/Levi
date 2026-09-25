"""The sly-generosity pattern catalog.

Clean-room analyses from first principles (2026-09-16 evening hunt).
Each entry records: the gift as presented, the capture underneath, what
the giant refuses to give, and the honest inversion LEVI ships instead.

No proprietary source was fetched or copied; the facts below are the
publicly documented pattern mechanics.
"""

from __future__ import annotations

from typing import Dict, List, Optional

PATTERNS: List[Dict[str, object]] = [
    {
        "id": "walled-garden-generosity",
        "name": "Walled-garden generosity",
        "exemplar": (
            "Facebook Free Basics / Internet.org (2013-2016): free mobile "
            "access to a curated handful of sites — including Facebook's "
            "own — across 35+ developing countries. India's regulator "
            "(TRAI) banned zero-rating in February 2016; a similar program "
            "was shut down in Egypt."
        ),
        "the_generosity": "Free internet for the unconnected.",
        "the_capture": (
            "The donor draws the map: only their chosen services are free, "
            "so the 'internet' the newcomer meets is the donor's own walled "
            "garden. Philanthropy becomes user acquisition; the gift sets "
            "the boundaries of what the recipient is allowed to want."
        ),
        "what_they_refuse": "Open, neutral access — generosity with no leash.",
        "inversion": (
            "Give without a leash: a generous thing must survive with no "
            "capture attached. If the gift needs a fence to keep paying off, "
            "it was never a gift."
        ),
        "signals": [
            "free",
            "basic",
            "zero-rated",
            "curated",
            "approved",
            "walled",
            "select",
            "partner apps",
            "charity",
            "connecting the unconnected",
        ],
    },
    {
        "id": "asymmetric-rules",
        "name": "Asymmetric rules (privacy as a weapon)",
        "exemplar": (
            "Apple's App Tracking Transparency (from iOS 14.5, 2021): "
            "third-party apps must beg for tracking permission via a "
            "scary prompt, while Apple's own ad system stays exempt — its "
            "Personalized Ads setting is on by default with no such prompt. "
            "France's competition authority fined Apple €150M in 2025 for "
            "the implementation; SMEs lost up to ~37% revenue growth on "
            "Meta-optimized campaigns per a 2025 Hamburg study."
        ),
        "the_generosity": "Privacy for the user.",
        "the_capture": (
            "The rule binds everyone except the rule-maker. A platform that "
            "controls the prompt gets to write the terms of the market: "
            "competitors bleed data while the platform's own first-party "
            "data — exempt from its own rule — becomes more valuable."
        ),
        "what_they_refuse": "Symmetrical rules — one standard that binds the platform too.",
        "inversion": (
            "The rule-maker obeys the rule: any privacy, consent, or data "
            "policy LEVI enforces on others binds LEVI's own components "
            "identically. Asymmetry is the tell of a weapon."
        ),
        "signals": [
            "privacy",
            "transparency",
            "exempt",
            "first-party",
            "our own",
            "platform policy",
            "compliance",
            "except us",
            "opt-in",
        ],
    },
    {
        "id": "roach-motel-funnel",
        "name": "Roach-motel funnel",
        "exemplar": (
            "Amazon Prime enrollment/cancellation (FTC sued June 2023): "
            "checkout buttons that enrolled shoppers without clearly saying "
            "so; a cancellation flow so long Amazon itself codenamed it the "
            "'Iliad Flow' — after a 16,000-line epic. 200M+ members, "
            "$139/yr; the FTC alleged leadership slowed or rejected changes "
            "that would have made leaving easier."
        ),
        "the_generosity": "One-click convenience — try it free, stay for the perks.",
        "the_capture": (
            "Friction is weaponized in one direction: entering is "
            "frictionless (or accidental), exiting is a siege. The product's "
            "retention is not earned by value but manufactured by fatigue — "
            "the customer keeps paying because quitting costs more effort "
            "than another year."
        ),
        "what_they_refuse": "Symmetric friction — leaving as easy as joining.",
        "inversion": (
            "Symmetric friction: any action LEVI makes easy to start must "
            "be equally easy to stop. The exit is tested first; if leaving "
            "is harder than joining, the design is rejected."
        ),
        "signals": [
            "free trial",
            "cancel",
            "subscription",
            "retention",
            "easy to join",
            "one click",
            "opt-out",
            "auto-renew",
            "funnel",
            "maze",
        ],
    },
    {
        "id": "manufactured-social-debt",
        "name": "Manufactured social debt",
        "exemplar": (
            "Snapchat Streaks: a counter rewarding friends who message each "
            "other every single day. A 2023 Antwerp study of 2,483 early "
            "adolescents linked streaks to problematic smartphone use and "
            "FOMO; Egyptian teen research found emotional distress at "
            "losing streaks. The mechanic converts a voluntary friendship "
            "into a daily obligation owed partly to the platform."
        ),
        "the_generosity": "A playful score celebrating your friendships.",
        "the_capture": (
            "Reciprocity and loss aversion — real human wiring — are "
            "repurposed as a retention engine. Missing one day destroys the "
            "number, so the user serves the score instead of the friend; "
            "the 'game' cannot be paused, so a sick day or a holiday "
            "becomes a punishment."
        ),
        "what_they_refuse": "Pausable, forgiving, opt-in play — joy without obligation.",
        "inversion": (
            "Obligation-free play: LEVI never turns voluntary use into a "
            "debt. Streak-like mechanics, where they exist, are pausable, "
            "never punish a gap, and the score belongs to the player — "
            "exportable, erasable, never held hostage."
        ),
        "signals": [
            "streak",
            "daily",
            "don't break",
            "fomo",
            "miss out",
            "score",
            "level",
            "every day",
            "consecutive",
            "obligation",
            "reminder",
        ],
    },
    {
        "id": "bait-and-rug-free-tier",
        "name": "Bait-and-rug free tier",
        "exemplar": (
            "Google Photos (2015-2021): free unlimited 'High quality' "
            "storage for six years, then the rug pulled on 2021-06-01 — "
            "all new uploads count against the shared 15 GB Google Account "
            "quota, with the toll leading to Google One ($1.99/mo/100 GB). "
            "Photos uploaded before the cutoff were grandfathered; the "
            "unlimited era trained users to make Photos their system of "
            "record for their memories first."
        ),
        "the_generosity": "'Free unlimited' — the most generous offer the giant ever made.",
        "the_capture": (
            "The unlimited tier was the anchor: it trained users to upload "
            "everything, making the service the system of record for "
            "people's lives. Once switching costs were maximal — years of "
            "memories searchable only inside the giant's index — the free "
            "tier was withdrawn. The generous era was never the business; "
            "it was a six-year acquisition campaign, and the toll arrives "
            "exactly when leaving is hardest."
        ),
        "what_they_refuse": "To say up front that 'unlimited' is temporary — honest limits in plain numbers.",
        "inversion": (
            "Plain-number limits from day one: if the free tier has a "
            "ceiling, it is printed on the box in numbers, never 'unlimited' "
            "as a lure. And any narrowing is grandfathered — existing "
            "users keep what they were given. See covenant.py."
        ),
        "signals": [
            "unlimited",
            "free forever",
            "grandfather",
            "storage",
            "quota",
            "tier",
            "google one",
            "revoked",
            "no longer free",
        ],
    },
    {
        "id": "cap-the-habit",
        "name": "Cap the habit (tax the dependency)",
        "exemplar": (
            "IFTTT (Sept 2020): after a decade of unlimited user-created "
            "applets (~11M users, ~54M applets), the free tier was capped "
            "at 3 created applets and IFTTT Pro launched at $9.99/mo "
            "(pay-what-you-want floor $1.99 the first year). Users who had "
            "wired their homes through IFTTT had to pick three applets to "
            "keep; the rest went dark. No grandfathering of existing "
            "applet libraries; the company also charges vendors for "
            "platform access — a double toll."
        ),
        "the_generosity": "A decade of free connective tissue for the smart home.",
        "the_capture": (
            "The capture was the habit: users wired doorbells, lights, "
            "and alarms through the service, then the platform taxed the "
            "dependency it had cultivated for free. The free tier was "
            "shrunk into a demo — still called 'free' — while the real "
            "product moved behind the toll. The outrage-priced launch "
            "offer ('set your own price, floor $1.99') converted anger "
            "into subscriptions before the anchor of $9.99 set in."
        ),
        "what_they_refuse": "A free tier that stays proportional to what the user built — the more you depend, the more you owe.",
        "inversion": (
            "The free tier is a covenant, not a demo: limits, if any, are "
            "fixed at signup and can never shrink underneath an existing "
            "user's dependency. Shrink the paid tier's extras instead — "
            "never the free tier's floor."
        ),
        "signals": [
            "free plan",
            "applet",
            "automation",
            "limited to",
            "cap",
            "pro",
            "demo",
            "shrank",
            "pick three",
        ],
    },
    {
        "id": "frozen-generosity",
        "name": "Frozen generosity (the outgrown tier)",
        "exemplar": (
            "Apple iCloud: 5 GB free since Steve Jobs announced it at WWDC "
            "2011 — unchanged for 15 years while iPhone photo/video sizes "
            "exploded and a weekend of footage outgrew it. Full device "
            "backup is iCloud-only: rivals are barred from backing up "
            "'Restricted Files' (settings, apps, app data). Class actions "
            "alleged the frozen tier exists to force upgrades; a 2024 "
            "Ninth Circuit ruling dismissed the deception claim, but suits "
            "persist in the US and UK."
        ),
        "the_generosity": "Free cloud storage with every device.",
        "the_capture": (
            "Generosity by attrition: the free tier never grows while the "
            "data it must hold grows every year. What was headroom in 2011 "
            "is a funnel in 2026. Combined with a mandated own-service "
            "path for full backup, the outgrown tier deposits users into "
            "the $0.99/mo 50 GB tier — itself frozen since 2015. The tier "
            "doesn't need to shrink to capture you; it just needs to stand "
            "still while the world moves."
        ),
        "what_they_refuse": "To let the free floor track the medium — or to open the mandated path to rivals.",
        "inversion": (
            "The free floor grows with the medium: any covenant free tier "
            "commits to rise (or to say honestly why it cannot), and the "
            "maker may never mandate its own paid service as the only path "
            "for a core need."
        ),
        "signals": [
            "free tier",
            "5gb",
            "frozen",
            "unchanged since",
            "backup",
            "mandatory",
            "only option",
            "outgrown",
            "restrict",
        ],
    },
    {
        "id": "engagement-bait-distribution",
        "name": "Engagement-bait distribution (the virality bargain)",
        "exemplar": (
            "TikTok's For You Page (2017-): the most generous distribution "
            "machine ever built — an interest graph, not a social graph, so "
            "a video from an account with zero followers can reach millions. "
            "The price is the complete behavioral graph: watch time, "
            "completions, replays, pauses, likes, comments, shares. TikTok's "
            "own 2020 guidance: 'the best way to curate your For You feed is "
            "to simply use and enjoy the app' — surrender implicit signals, "
            "never declare explicit preferences. The December 2022 'Why this "
            "video' panel names coarse categories ('popular in your region') "
            "but discloses no weights and offers no per-signal control."
        ),
        "the_generosity": "Free virality — anyone can reach everyone.",
        "the_capture": (
            "Distribution is the funnel mouth for the behavioral graph. The "
            "ranking model is never inspectable, its weights never tunable, "
            "and the 'why' is a buried afterthought rather than the primary "
            "interface. Creators optimize for the platform's retention "
            "metric because the alternative — declaring what they actually "
            "want — is not offered. Free reach converts attention into "
            "training data at planetary scale."
        ),
        "what_they_refuse": (
            "Declared rationale and user-controlled ranking — a feed that "
            "says why, in weights you can tune."
        ),
        "inversion": (
            "Every recommendation ships its reasons at declared weights, "
            "tunable by the user, as the primary interface — not a buried "
            "panel. The feed answers 'why am I seeing this' before it is asked."
        ),
        "signals": [
            "for you",
            "viral",
            "discover",
            "personalized",
            "why this",
            "implicit signals",
            "watch time",
            "engagement",
            "algorithm",
            "recommended",
        ],
    },
    {
        "id": "community-graph-hostage",
        "name": "Community-graph hostage (free infrastructure, no exit)",
        "exemplar": (
            "Discord (2015-): unlimited free voice, text, and video for any "
            "community — the most generous hosting offer on the internet. "
            "The capture: a community cannot leave. 'Request My Data' "
            "exports only messages sent by the requesting user; received "
            "messages from other members are excluded, attachment URLs "
            "expire, and there is no first-party community migration path — "
            "no portable server archive (structure, roles, full history, "
            "member graph) any other platform or self-hosted tool can "
            "import. Basic community features sit behind Nitro/Boost "
            "paywalls while the community's history lives under Discord's "
            "terms."
        ),
        "the_generosity": "Free community infrastructure, unlimited.",
        "the_capture": (
            "The generosity is individual; the lock-in is collective. Each "
            "member gets a personal data package, but the community — the "
            "thing with value — has no export artifact. Coordination cost "
            "is the moat: even members who know they are tenants cannot "
            "organize an exit without the infrastructure they would be "
            "leaving. Third-party bots fill the gap partially, which lets "
            "the official export stay individual-only."
        ),
        "what_they_refuse": "Community-portable export — the community leaving together, with everything.",
        "inversion": (
            "Communities export whole: one command, member roster, history, "
            "media, roles, configs — import-grade, not browse-grade. The "
            "gift must survive the community leaving with all of it."
        ),
        "signals": [
            "free server",
            "unlimited",
            "community",
            "boost",
            "nitro",
            "no export",
            "request my data",
            "migrate",
            "stranded",
        ],
    },
    {
        "id": "training-data-toll",
        "name": "Training-data toll (free tools in, model out)",
        "exemplar": (
            "GitHub/Microsoft Copilot (technical preview June 2021, GA June "
            "2022 at $10/mo): free world-class tools — free repos, free VS "
            "Code, free Actions minutes — attracted the code that trained a "
            "paid model, including open-source-licensed code. The November "
            "2022 class action (Doe v. GitHub/Microsoft/OpenAI) alleged "
            "training without license compliance; most claims were dismissed "
            "by June 2024 but breach-of-contract claims proceeded. The "
            "exclusion controls are organization/admin controls on paid "
            "tiers: protection from the toll is sold back to the people who "
            "paid it."
        ),
        "the_generosity": "Free professional tools for every developer.",
        "the_capture": (
            "Two-sided funnel: free tools attract the code; the code trains "
            "the product sold back to the same developers. The contributor "
            "has no after-the-fact opt-out, no standing in the training "
            "decision, and no share of the revenue. Each developer's rational "
            "move (use the free tool, ship faster) is collectively "
            "self-taxing, and no single contributor can negotiate with the "
            "platform hosting the commons."
        ),
        "what_they_refuse": (
            "Free-tier, individual, machine-checkable training consent — "
            "and provenance on what trained what."
        ),
        "inversion": (
            "Consent-first training: every training artifact carries a "
            "machine-checkable consent record (who agreed, scope, "
            "revocability), free for every individual. The brain trains on "
            "its own corpus — never on user data without explicit, "
            "revocable, per-artifact consent."
        ),
        "signals": [
            "free tools",
            "trained on",
            "public code",
            "opt out",
            "copilot",
            "telemetry",
            "consent",
            "training data",
            "fair use",
        ],
    },
    {
        "id": "spyware-as-security",
        "name": "Spyware as security (the free VPN that was the watcher)",
        "exemplar": (
            "Facebook's Onavo Protect (2013-2019): a free VPN marketed as "
            "protecting users' data, routing all mobile traffic through "
            "Facebook's servers. Collected app usage, time-per-app, data "
            "usage, and sites visited. Apple's App Store removed it in "
            "August 2018 for collecting other-apps' data for analytics; "
            "TechCrunch's January 2019 Project Atlas expose showed the "
            "same code in a Facebook Research app that paid teens as young "
            "as 13 up to $20/month for full-device access. Onavo data "
            "reportedly informed the WhatsApp acquisition. Facebook shut "
            "Onavo down February 2019."
        ),
        "the_generosity": "Free security and data protection, on us.",
        "the_capture": (
            "The protector is the watcher: the VPN's job was to see every "
            "packet. 'Protecting your data' meant routing it to Facebook. "
            "The free security tool was a competitive-intelligence sensor, "
            "and when the storefront banned it, the same sensor was "
            "rebranded as 'research' and aimed at cash-strapped teenagers."
        ),
        "what_they_refuse": "Security with no watcher — a VPN that cannot see.",
        "inversion": (
            "The Gift Ledger: every 'free' security gift gets a receipt "
            "naming exactly what it can see. If the security tool needs to "
            "watch you to protect you, it is not security — it is a "
            "subscription to being watched."
        ),
        "signals": [
            "free VPN",
            "protect your data",
            "stay safe",
            "research program",
            "beta testing",
            "gift cards",
            "teens",
        ],
    },
    {
        "id": "free-upgrade-with-fine-print-hammer",
        "name": "The free upgrade that reprogrammed 'cancel'",
        "exemplar": (
            "Microsoft's Windows 10 free-upgrade campaign (2015-2016): a "
            "free one-year upgrade for Windows 7/8.1 users pushed via the "
            "Get Windows 10 (GWX) nagware. Escalation ran from popups, to "
            "recategorizing the upgrade as a 'recommended' update, to "
            "pre-scheduling installs — and, infamously, to reversing the "
            "red X: clicking the corner X, which had always meant cancel, "
            "granted consent. Teri Goldstein, a California travel agent "
            "whose work PC was upgraded without authorization, won $10,000 "
            "in damages; Microsoft declined to appeal. Its CMO later "
            "admitted the campaign 'went too far' at the red-X moment."
        ),
        "the_generosity": "A free new OS, a gift to every user.",
        "the_capture": (
            "Consent itself became the product: the campaign optimized the "
            "consent funnel until the word 'no' pointed at 'yes'. The free "
            "OS then converted the desktop into a storefront — ads in the "
            "Start menu, telemetry tiers, forced updates. The gift was the "
            "delivery vehicle for the capture."
        ),
        "what_they_refuse": "An upgrade that leaves the meaning of 'no' alone.",
        "inversion": (
            "Upgrade consent is a receipt, not a funnel: LEVI changes "
            "nothing — defaults, telemetry, interface — without a "
            "machine-checkable consent record that survives the upgrade "
            "intact. 'No' must mean the same thing after the gift as "
            "before it."
        ),
        "signals": [
            "free upgrade",
            "recommended update",
            "scheduled upgrade",
            "nagscreen",
            "click X to cancel",
            "limited time",
        ],
    },
    {
        "id": "assistant-staffed-by-strangers",
        "name": "The free assistant staffed by hidden humans",
        "exemplar": (
            "Google Assistant contractor review (exposed July 2019): "
            "Belgian broadcaster VRT NWS obtained 1,000+ Assistant audio "
            "clips from a whistleblowing Dutch-language reviewer. Human "
            "contractors routinely listened and transcribed snippets that "
            "included medical discussions, home addresses, and a woman in "
            "distress; 153 clips had been recorded without a clear wake "
            "word. Google admitted ~0.2% of clips were human-reviewed, "
            "paused the practice globally, and Hamburg's data authority "
            "used GDPR Article 66 urgency powers to order a halt — the "
            "first such use since GDPR took effect."
        ),
        "the_generosity": "A free AI that is always listening, ready to help.",
        "the_capture": (
            "'Always listening' had a second audience: contractors told to "
            "'look up every word, address, personal name' in unclear audio — "
            "a de-anonymization workflow, not just transcription. The "
            "privacy policy described the algorithm; the humans were the "
            "unlisted staff. The bargain was never user-algorithm; it was "
            "user-algorithm-plus-unnamed-listeners."
        ),
        "what_they_refuse": "An assistant with no hidden second audience.",
        "inversion": (
            "LEVI's native brain trains on LEVI-authored material and runs "
            "local-first: no contractor, no cloud transcriber, no second "
            "audience. If a human ever must review, the review is named, "
            "scoped, revocable — a consent record, not a secret."
        ),
        "signals": [
            "free assistant",
            "language experts",
            "improve the service",
            "0.2 percent",
            "anonymous",
            "wake word",
            "misfire",
        ],
    },
]


def pattern_ids() -> List[str]:
    return [p["id"] for p in PATTERNS]


def get_pattern(pattern_id: str) -> Optional[Dict[str, object]]:
    for p in PATTERNS:
        if p["id"] == pattern_id:
            return p
    return None
