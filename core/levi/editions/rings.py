"""The three rings as distribution architecture.

OPEN CREATIONAL — bare-minimal source: structure + architecture only.
Ships: the edition manifest schema, the roster format, the ring policy,
an edition template. Outside minds run free with ideas, plans, and
integrations. Never ships: agent implementations, curated rosters,
sector workflows, proprietary prompts, weights, the crown jewels.

CLOSED — the diehard developers and the keeper. Full source: the
catalog, the workflows, the 471 agents, everything the open ring
withholds. The crown jewels never leave.

GOVERNMENT — political and security-grade AI and SI. Closed contents
plus the hardening checklist below: hardened, auditable, sovereign.

The boundary is defined as path-prefix rules so any packager, CI gate,
or release script can classify a file mechanically.
"""

from __future__ import annotations

from typing import Tuple

from .manifest import Ring

# -- the file/module boundary, precisely -------------------------------------

OPEN_RING_PATHS: Tuple[str, ...] = (
    "core/levi/editions/schema/",
    "core/levi/editions/DESIGN.md",
    "core/levi/editions/manifest.py",
    "core/levi/editions/rings.py",
    "docs/LEXICON.md",
    "docs/EDITIONS_RING_POLICY.md",
)
"""Everything the open creational ring may carry. Structure and
architecture only: shapes, schemas, templates, policy. No curated
rosters, no workflows, no agent implementations."""

CLOSED_RING_PATHS: Tuple[str, ...] = (
    "core/levi/editions/catalog.py",
    "core/levi/editions/__init__.py",
    "core/levi/automation/",
    "core/levi/bot/",
    "core/levi/si_team/",
)
"""Closed ring additions: the edition catalog, the agent catalog, the
original stack. Full source for diehard developers and the keeper."""

GOVERNMENT_RING_PATHS: Tuple[str, ...] = ("core/levi/editions/government/",)
"""Government ring additions: hardening manifests, sovereign-deployment
profiles, audit exporters. Built atop the closed ring, never instead."""


def ring_for_path(path: str) -> Ring:
    """Classify a repo-relative path into the innermost ring that may
    carry it. Unknown paths default to CLOSED (deny-open)."""
    p = path.lstrip("./")
    for prefix in GOVERNMENT_RING_PATHS:
        if p == prefix.rstrip("/") or p.startswith(prefix):
            return Ring.GOVERNMENT
    for prefix in CLOSED_RING_PATHS:
        if p == prefix.rstrip("/") or p.startswith(prefix):
            return Ring.CLOSED
    for prefix in OPEN_RING_PATHS:
        if p == prefix.rstrip("/") or p.startswith(prefix):
            return Ring.OPEN_CREATIONAL
    return Ring.CLOSED


# -- the government hardening checklist --------------------------------------

GOVERNMENT_HARDENING_CHECKLIST: Tuple[Tuple[str, str], ...] = (
    (
        "reproducible-build",
        "Pinned dependencies and sealed build receipts: the same source "
        "always produces the same artifact. No unpinned fetches anywhere "
        "in the build or run path.",
    ),
    (
        "signed-receipts",
        "Every run seals a signed receipt (Plan→Preview→Permission→"
        "Execute→Verify→Receipt) under the deployer's key. Unsigned runs "
        "do not count as runs.",
    ),
    (
        "audit-trail",
        "Every gate decision is logged append-only and exportable in a "
        "human-readable format. The trail is the product's memory of "
        "itself.",
    ),
    (
        "sovereign-deployment",
        "Self-hosted only. Zero external network calls in the execution "
        "path, verified by an egress test in CI. Air-gap capable.",
    ),
    (
        "data-residency",
        "Residency pinned per deployment and enforced in code, not policy "
        "documents. Retention policy enforced the same way.",
    ),
    (
        "no-training-attestation",
        "The edition never trains on operational data. Enforced in code, "
        "attested in the release notes. This is sold as the feature.",
    ),
    (
        "supply-chain-pins",
        "SHA-256 pinned models and artifacts. A fetch without a pin is a "
        "build failure, not a warning.",
    ),
    (
        "deny-closed-hitl",
        "Human-in-the-loop on all consequential actions; deny-closed "
        "defaults everywhere. Silence is never consent.",
    ),
    (
        "penetration-review",
        "Diehard-developer penetration review before any government-ring "
        "promotion. Findings composted through REIM; the report ships "
        "with the release.",
    ),
    (
        "sovereign-off-switch",
        "The deployer holds an off-switch no update can remove. The "
        "dynasty serves at the sovereign's pleasure.",
    ),
    (
        "provenance-on-everything",
        "Every artifact carries origin and interpenetration signature. "
        "Chain-of-custody honesty: analysis never alters source evidence; "
        "copies are marked as copies.",
    ),
    (
        "personnel-is-process",
        "Clearance handling is the deployer's duty and lives in their "
        "process documentation, never in code. The code refuses to "
        "pretend otherwise.",
    ),
)
"""Twelve gates. A build enters the government ring only when all twelve
are green, reviewed, and recorded. The checklist itself ships in the
open ring — the bar is public; the builds that clear it are not."""
