"""LEVI Liberation Ledger — the roach-motel inverter.

REMIX DELTA: the giants are generous with *ingress* and miserly with
*egress*. Slack gives your team free chat, then starts deleting history
past 90 days (and destroying it past a year) unless you pay. Reddit
harvested a decade of third-party-client labor, then set API tolls at
$20M/year for Apollo. Google Takeout exports your photos as metadata-
stripped fragments only community tools can reassemble. Meta hands you
your posts but never the social graph or the inferences. The pattern is
one trade with four costumes: data checks in, but it doesn't check out.

No giant will ever ship the honest version of this — a tool that prices
your exit lowers their leverage. So LEVI does. The Liberation Ledger is
a local-first register of every service holding your data, a *transparent*
hostage score (every component shown with its reason — the opposite of a
black-box risk rating), and liberation tasks (export -> verify -> migrate
-> delete) closed with receipts.

Scores marked from the 2026-09-15 hunt are the researcher's analysis,
not the vendors' claims; each seeded profile says so in its notes.

Layout:
    ledger.py   ServiceProfile, transparent hostage scoring, Ledger,
                liberation tasks + receipts, seeded research profiles
    __main__.py CLI: python -m levi.liberation <seed|add-service|list|
                score|report|task-add|task-done|tasks>
"""

from __future__ import annotations

from levi.liberation.ledger import (
    KNOWN_HOSTAGE_PROFILES,
    LiberationLedger,
    ServiceProfile,
    hostage_score,
    liberation_home,
    score_components,
)

SHELF = {
    "name": "liberation",
    "summary": (
        "Liberation Ledger: register services holding your data, score "
        "their hostage-ness transparently, and work liberation tasks "
        "(export/verify/migrate/delete) to receipts. Local-first."
    ),
    "items": [
        {
            "id": "lib-seed",
            "kind": "command",
            "summary": "Load the researched hostage profiles (Slack, Reddit, Google, Meta).",
            "invoke": "python -m levi.liberation seed",
        },
        {
            "id": "lib-add",
            "kind": "command",
            "summary": "Register a service holding your data.",
            "invoke": "python -m levi.liberation add-service --json '{...}'",
        },
        {
            "id": "lib-score",
            "kind": "command",
            "summary": "Show a service's hostage score with every component explained.",
            "invoke": "python -m levi.liberation score NAME",
        },
        {
            "id": "lib-report",
            "kind": "command",
            "summary": "Ranked hostage report: worst offenders first, open tasks listed.",
            "invoke": "python -m levi.liberation report",
        },
        {
            "id": "lib-task",
            "kind": "command",
            "summary": "Queue a liberation task (export/verify/migrate/delete/confirm).",
            "invoke": "python -m levi.liberation task-add SERVICE KIND --notes ...",
        },
    ],
}

__all__ = [
    "KNOWN_HOSTAGE_PROFILES",
    "LiberationLedger",
    "ServiceProfile",
    "hostage_score",
    "liberation_home",
    "score_components",
    "SHELF",
]
