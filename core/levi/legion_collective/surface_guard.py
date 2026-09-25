"""Shared-surface guard — the never-surface inventory, enforced in code.

The LEGION plan's Phase 0 requires an inventory of everything that must
NEVER appear in shared surfaces (docs/ published copies, web/, artifacts,
feed posts, your_files/ shared bundles). That inventory itself is
eyes-only (Chauncey + Rex) and is NEVER committed to this repo.

This module enforces a caller-supplied inventory at share time:

    verdict, hits = scan_text(payload, inventory)

Verdicts are the ternary: PASS (clean) / FAIL (deny-pattern hit) /
NEEDS_REVIEW (uncertain — e.g. no inventory supplied, or a review-pattern
hit). Fails closed: when the guard cannot prove a payload clean, it does
not pass it.

A small set of STRUCTURAL deny patterns ships built-in. They are
capability-level and safe to share (private-key blocks, seed-phrase
markers) — never IP, never codenames, never the eyes-only inventory.
"""

from __future__ import annotations

import re

VERDICT_PASS = "pass"
VERDICT_FAIL = "fail"
VERDICT_NEEDS_REVIEW = "needs_review"
VERDICTS = (VERDICT_PASS, VERDICT_FAIL, VERDICT_NEEDS_REVIEW)

# Built-in structural deny patterns. Safe to ship: they describe shapes
# (key blocks, recovery phrases), never anyone's secrets or IP.
STRUCTURAL_DENY = {
    "private_key_block": [r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"],
    "recovery_phrase": [r"seed phrase", r"recovery phrase", r"\bmnemonic\b"],
}

# Review patterns: not a fail, but a human should look before sharing.
STRUCTURAL_REVIEW = {
    "eyes_only_marker": [r"eyes[-\s]?only", r"do not share", r"internal only"],
}


def _compile(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


def scan_text(text: str, inventory: dict | None = None) -> tuple[str, list[dict]]:
    """Scan text against the built-ins plus a caller-supplied eyes-only inventory.

    inventory shape: {"deny": {category: [patterns...]},
                      "review": {category: [patterns...]}}
    Returns (verdict, hits) where each hit is {"category", "pattern", "at"}.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    deny: dict[str, list[str]] = dict(STRUCTURAL_DENY)
    review: dict[str, list[str]] = dict(STRUCTURAL_REVIEW)
    if inventory:
        if not isinstance(inventory, dict):
            raise TypeError("inventory must be a dict or None")
        for category, patterns in (inventory.get("deny") or {}).items():
            deny.setdefault(category, []).extend(patterns)
        for category, patterns in (inventory.get("review") or {}).items():
            review.setdefault(category, []).extend(patterns)

    hits: list[dict] = []
    for category, patterns in deny.items():
        for rx in _compile(patterns):
            for m in rx.finditer(text):
                hits.append(
                    {"category": category, "pattern": rx.pattern, "at": m.start()}
                )
    if hits:
        return VERDICT_FAIL, hits
    for category, patterns in review.items():
        for rx in _compile(patterns):
            for m in rx.finditer(text):
                hits.append(
                    {"category": category, "pattern": rx.pattern, "at": m.start()}
                )
    if hits:
        return VERDICT_NEEDS_REVIEW, hits
    if inventory is None:
        # Fails closed: with no eyes-only inventory supplied we cannot
        # prove the payload clean, so it does not pass.
        return VERDICT_NEEDS_REVIEW, [
            {"category": "no_inventory", "pattern": "", "at": -1}
        ]
    return VERDICT_PASS, []


def scan_mapping(
    mapping: dict, inventory: dict | None = None
) -> tuple[str, list[dict]]:
    """Recursively scan every string in a nested dict/list structure."""
    worst = VERDICT_PASS
    all_hits: list[dict] = []

    def visit(node, path: str) -> None:
        nonlocal worst
        if isinstance(node, str):
            verdict, hits = scan_text(node, inventory)
            for h in hits:
                all_hits.append({"path": path, **h})
            if verdict == VERDICT_FAIL:
                worst = VERDICT_FAIL
            elif verdict == VERDICT_NEEDS_REVIEW and worst == VERDICT_PASS:
                worst = VERDICT_NEEDS_REVIEW
        elif isinstance(node, dict):
            for k, v in node.items():
                visit(v, f"{path}.{k}")
        elif isinstance(node, (list, tuple)):
            for i, v in enumerate(node):
                visit(v, f"{path}[{i}]")

    visit(mapping, "$")
    return worst, all_hits
