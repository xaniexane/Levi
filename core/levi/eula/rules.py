"""Hostile-clause rule table for the EULA linter.

Each rule is a plain dict (stdlib, serializable, no magic):
    id                  stable machine name
    title               short human label
    severity            one of "info" | "caution" | "hostile"
    patterns            list of regexes (case-insensitive) matched against the text
    plain_language_flag plain-language explanation shown to the reader
    why_it_matters      one extra sentence of context (optional)
"""

RULES = [
    {
        "id": "forced_arbitration",
        "title": "Forced arbitration",
        "severity": "hostile",
        "patterns": [
            r"\barbitration\b",
            r"waiv\w*\s+(?:your|any)\s+right\s+to\s+(?:a\s+)?trial",
            r"binding\s+arbitration",
        ],
        "plain_language_flag": (
            "You cannot sue them in court. Any dispute goes to a private "
            "arbitrator they chose the rules for."
        ),
        "why_it_matters": "Arbitration favors repeat players (the company) over one-time users.",
    },
    {
        "id": "class_action_waiver",
        "title": "Class-action waiver",
        "severity": "hostile",
        "patterns": [
            r"class\s+action",
            r"collective\s+action",
            r"representative\s+action",
        ],
        "plain_language_flag": (
            "You cannot team up with other users to sue together. Everyone "
            "must fight the company alone, which makes small harms unchallengeable."
        ),
        "why_it_matters": "Class actions are how widespread small-dollar abuse gets corrected.",
    },
    {
        "id": "unilateral_modification",
        "title": "They can change the terms at any time",
        "severity": "hostile",
        "patterns": [
            r"(?:may|can|reserve\s+the\s+right\s+to)\s+(?:modify|change|amend|update)\s+(?:these\s+)?terms?\s+(?:at\s+any\s+time|without\s+notice)",
            r"continued\s+use\s+(?:constitutes|is\s+deemed)\s+(?:acceptance|agreement)",
            r"terms?\s+may\s+be\s+changed\s+at\s+any\s+time",
        ],
        "plain_language_flag": (
            "They can rewrite the deal whenever they want, and just by "
            "keeping the app installed you are treated as agreeing to the new version."
        ),
        "why_it_matters": "The terms you read today may not be the terms that apply tomorrow.",
    },
    {
        "id": "data_resale",
        "title": "Your data is sold",
        "severity": "hostile",
        "patterns": [
            r"sell\w*\s+(?:your|the|user)\s+(?:personal\s+)?(?:information|data)",
            r"monetiz\w*\s+(?:your|user)\s+data",
        ],
        "plain_language_flag": (
            "They sell your personal information or data to other companies. "
            "You are the product being traded."
        ),
        "why_it_matters": "Once sold, your data lives in databases you will never see or control.",
    },
    {
        "id": "perpetual_content_license",
        "title": "Perpetual license to your content",
        "severity": "hostile",
        "patterns": [
            r"perpetual\W+(?:.{0,60}?)irrevocable",
            r"irrevocable\W+(?:.{0,60}?)perpetual",
            r"worldwide\W+royalty[- ]free\W+licen[cs]e",
            r"licen[cs]e\s+to\s+(?:use|reproduce|distribute).{0,40}in\s+perpetuity",
        ],
        "plain_language_flag": (
            "Anything you upload, write, or create stays licensed to them forever, "
            "even if you delete your account. Deleting does not take it back."
        ),
        "why_it_matters": "Your creative work and personal content become a permanent company asset.",
    },
    {
        "id": "third_party_data_sharing",
        "title": "Data shared with third parties",
        "severity": "caution",
        "patterns": [
            r"share\w*\s+(?:your|the|user)\s+(?:personal\s+)?(?:information|data)\s+with\s+third",
            r"disclos\w*\s+(?:your|the|user)\s+(?:personal\s+)?(?:information|data)\s+to\s+third",
            r"third[- ]part\w*\s+(?:partners|advertisers|affiliates)",
        ],
        "plain_language_flag": (
            "Your information is handed to outside companies. Check who they are "
            "and whether you can opt out."
        ),
        "why_it_matters": "Each third party is a new place your data can leak from.",
    },
    {
        "id": "auto_renewal",
        "title": "Auto-renewal trap",
        "severity": "caution",
        "patterns": [
            r"automatically\s+renew\w*",
            r"auto[- ]renew\w*",
            r"recurring\s+(?:billing|charges?|payments?)",
        ],
        "plain_language_flag": (
            "The subscription keeps charging you until you actively cancel. "
            "Write down how to cancel before you sign up."
        ),
        "why_it_matters": "Auto-renewal relies on you forgetting to cancel.",
    },
    {
        "id": "price_change_anytime",
        "title": "They can raise the price anytime",
        "severity": "caution",
        "patterns": [
            r"(?:may|can|reserve\s+the\s+right\s+to)\s+(?:change|increase|modify)\s+(?:the\s+)?(?:price|pricing|fees?|rates?)\s+at\s+any\s+time",
        ],
        "plain_language_flag": (
            "They can raise what you pay whenever they choose. The price you "
            "signed up at is not guaranteed."
        ),
        "why_it_matters": "Budget around a price that can move without your agreement.",
    },
    {
        "id": "unilateral_termination",
        "title": "Account terminated at their discretion",
        "severity": "caution",
        "patterns": [
            r"(?:may|can|reserve\s+the\s+right\s+to)\s+(?:terminate|suspend|disable)\s+(?:your\s+)?account.{0,60}(?:at\s+any\s+time|for\s+any\s+reason|at\s+our\s+(?:sole\s+)?discretion)",
            r"terminate.{0,40}without\s+(?:prior\s+)?notice",
        ],
        "plain_language_flag": (
            "They can cut off your account whenever they decide, possibly without "
            "warning and without giving your data back."
        ),
        "why_it_matters": "If your work or memories live here, keep your own backup.",
    },
    {
        "id": "no_refund",
        "title": "No refunds",
        "severity": "caution",
        "patterns": [
            r"\bno\s+refunds?\b",
            r"non[- ]refundable",
            r"all\s+sales\s+are\s+final",
        ],
        "plain_language_flag": (
            "Once you pay, the money is gone — even if the service is broken, "
            "shut down, or nothing like what was advertised."
        ),
        "why_it_matters": "No-refund terms shift all purchase risk onto you.",
    },
    {
        "id": "indemnification",
        "title": "You pay their legal bills",
        "severity": "caution",
        "patterns": [
            r"indemnify\w*\s+(?:and\s+)?hold\s+harmless",
            r"you\s+agree\s+to\s+defend",
        ],
        "plain_language_flag": (
            "If someone sues them over something connected to your use, you owe "
            "them the legal costs — even when the fight is really about them."
        ),
        "why_it_matters": "This can make you liable for disputes you did not start.",
    },
    {
        "id": "liability_cap",
        "title": "Liability capped near zero",
        "severity": "caution",
        "patterns": [
            r"limitation\s+of\s+liability",
            r"liability\s+(?:shall\s+not\s+exceed|is\s+limited\s+to)",
            r"in\s+no\s+event\s+(?:shall|will)\s+(?:we|the\s+company)\s+be\s+liable",
        ],
        "plain_language_flag": (
            "Even if they seriously harm you through negligence or failure, the "
            "most you can recover is capped — sometimes at the price you paid."
        ),
        "why_it_matters": "Removes most of the financial incentive for them to be careful.",
    },
    {
        "id": "warranty_disclaimer",
        "title": "'As is' — no promises it works",
        "severity": "caution",
        "patterns": [
            r"\bas[\s-]+is\b",
            r"disclaim\w*\s+all\s+warranties",
            r"without\s+warranty\s+of\s+any\s+kind",
        ],
        "plain_language_flag": (
            "They promise nothing about the service working. If it loses your "
            "data, breaks, or is insecure, that is your problem by contract."
        ),
        "why_it_matters": "Common, but worth knowing it strips your consumer rights to a working product.",
    },
    {
        "id": "data_retention",
        "title": "Data kept indefinitely",
        "severity": "caution",
        "patterns": [
            r"retain\w*\s+(?:your|the|user)\s+(?:personal\s+)?(?:information|data)\s+(?:for\s+as\s+long\s+as|indefinitely)",
            r"kept\s+indefinitely",
        ],
        "plain_language_flag": (
            "They keep your data with no stated end date. Deleting your account "
            "may not delete what they collected."
        ),
        "why_it_matters": "The longer data is kept, the more chances it has to leak.",
    },
    {
        "id": "tracking_surveillance",
        "title": "Location / behavior tracking",
        "severity": "caution",
        "patterns": [
            r"precise\s+location",
            r"track\w*\s+your\s+(?:location|movements|browsing)",
            r"collect\w*\s+(?:device|usage)\s+data",
        ],
        "plain_language_flag": (
            "They track where you go or what you do in detail, not just the "
            "basics needed to run the service."
        ),
        "why_it_matters": "Behavioral tracking builds a profile that follows you across services.",
    },
    {
        "id": "foreign_jurisdiction",
        "title": "Disputes heard far away",
        "severity": "info",
        "patterns": [
            r"governed\s+by\s+the\s+laws\s+of",
            r"exclusive\s+jurisdiction",
            r"courts?\s+of\s+(?:the\s+state\s+of|delaware|ireland)",
        ],
        "plain_language_flag": (
            "If you ever dispute anything, it is decided under another place's "
            "laws, possibly far from where you live."
        ),
        "why_it_matters": "Distant jurisdiction raises the cost of standing up for yourself.",
    },
    {
        "id": "effective_date",
        "title": "Has a clear effective date",
        "severity": "info",
        "patterns": [
            r"effective\s+date",
            r"last\s+updated",
        ],
        "plain_language_flag": (
            "The terms carry a version date — a good sign. Compare it against "
            "the version you agreed to before."
        ),
        "why_it_matters": "Dated terms let you track when the deal changed.",
    },
]
