"""The free-tier covenant: LEVI's written promise, machine-checkable.

The giants' free tiers taught us three rug-pull shapes (see trades.py):
``bait-and-rug-free-tier`` (Google Photos unlimited, 2015-2021),
``cap-the-habit`` (IFTTT's 3-applet cap, 2020), and ``frozen-generosity``
(Apple's iCloud 5 GB, unchanged since 2011).

LEVI does not ask users to trust a promise in prose. Every LEVI feature
with a free tier ships a ``FreeTierCovenant``: what is free in plain
numbers, what the maker promises never to do, the grandfather clause,
and the export path. ``audit_covenant`` scores the covenant the way
``audit_offer`` scores a giant's offer — the maker obeys its own rule,
or the design is rejected.

stdlib-only, local-first, no network, no telemetry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


# Bait words: "generous" language that hides the absence of numbers.
# A covenant that offers something 'unlimited' or 'free forever' without
# plain numbers is the opening move of a bait-and-rug.
BAIT_WORDS = (
    "unlimited",
    "free forever",
    "forever free",
    "never pay",
    "no limits",
    "limitless",
    "infinite",
)


@dataclass(frozen=True)
class FreeTierCovenant:
    """A declared free-tier promise for one LEVI feature.

    - ``feature``: what the covenant covers.
    - ``free_offers``: what is free, stated in plain numbers
      (e.g. "10,000 automation rules, counted locally").
    - ``never``: things the maker promises never to do
      (e.g. "shrink the free tier under existing users").
    - ``grandfather_clause``: what happens to existing users if terms
      ever change — must name the protection, not gesture at it.
    - ``export_path``: how the user takes their stuff out, in plain words.
    - ``grows_with_medium``: the free floor commits to track the medium
      (storage prices, device capacity) rather than freeze by fiat.
    - ``mandates_own_paid_path``: the maker requires its own paid service
      as the only route for a core need — must be False; if True the
      covenant fails outright.
    """

    feature: str
    free_offers: List[str] = field(default_factory=list)
    never: List[str] = field(default_factory=list)
    grandfather_clause: str = ""
    export_path: str = ""
    grows_with_medium: bool = False
    mandates_own_paid_path: bool = False


def _plain_number(text: str) -> bool:
    """Does the text state a concrete number? Any digit counts."""
    return any(ch.isdigit() for ch in text)


def audit_covenant(covenant: FreeTierCovenant) -> Dict[str, object]:
    """Score a free-tier covenant 0-100. Deliberately conservative."""
    if not isinstance(covenant, FreeTierCovenant):
        raise ValueError("audit_covenant needs a FreeTierCovenant")
    if not covenant.feature.strip():
        raise ValueError("covenant must name a feature")

    report: Dict[str, object] = {
        "feature": covenant.feature,
        "findings": [],
        "related_patterns": [
            "bait-and-rug-free-tier",
            "cap-the-habit",
            "frozen-generosity",
        ],
    }
    findings: List[Dict[str, str]] = report["findings"]  # type: ignore[assignment]
    score = 100

    # 1. The free offer must be stated in plain numbers.
    if not covenant.free_offers:
        findings.append(
            {
                "check": "plain-numbers",
                "result": "fail",
                "detail": (
                    "The covenant names nothing free in concrete terms. "
                    "A free tier with no stated content is a mood, not a promise."
                ),
            }
        )
        score -= 40
    else:
        numbered = [o for o in covenant.free_offers if _plain_number(o)]
        baited = [o for o in covenant.free_offers if not _plain_number(o)]
        if len(numbered) < len(covenant.free_offers):
            findings.append(
                {
                    "check": "plain-numbers",
                    "result": "fail",
                    "detail": (
                        "Some free offers have no plain numbers: "
                        + "; ".join(baited[:3])
                        + ". 'Unlimited' without numbers is the bait half "
                        "of a bait-and-rug."
                    ),
                }
            )
            score -= 30
        bait_hits = [
            w
            for o in covenant.free_offers
            for w in BAIT_WORDS
            if w in o.lower() and not _plain_number(o)
        ]
        if bait_hits:
            findings.append(
                {
                    "check": "bait-words",
                    "result": "fail",
                    "detail": (
                        "Bait words with no numbers attached: "
                        + ", ".join(sorted(set(bait_hits)))
                        + ". Rename the offer in numbers or it is bait."
                    ),
                }
            )
            score -= 20
        if len(numbered) == len(covenant.free_offers):
            findings.append(
                {
                    "check": "plain-numbers",
                    "result": "pass",
                    "detail": "Every free offer is stated in plain numbers.",
                }
            )

    # 2. The maker's 'never' list must exist — a covenant is a boundary.
    if not covenant.never:
        findings.append(
            {
                "check": "never-list",
                "result": "fail",
                "detail": (
                    "The covenant lists nothing the maker promises never "
                    "to do. Without a never-list, the free tier can be "
                    "narrowed silently — this is where IFTTT's applet cap "
                    "would have failed."
                ),
            }
        )
        score -= 20
    else:
        findings.append(
            {
                "check": "never-list",
                "result": "pass",
                "detail": "The maker names %d hard never-dos."
                % len(covenant.never),
            }
        )

    # 3. The grandfather clause must exist and say something concrete.
    if not covenant.grandfather_clause.strip():
        findings.append(
            {
                "check": "grandfather",
                "result": "fail",
                "detail": (
                    "No grandfather clause. If terms ever change, existing "
                    "users have no written protection — retroactive "
                    "narrowing becomes possible by silence."
                ),
            }
        )
        score -= 20
    else:
        findings.append(
            {
                "check": "grandfather",
                "result": "pass",
                "detail": "Grandfather clause: %s"
                % covenant.grandfather_clause.strip()[:120],
            }
        )

    # 4. The user must be able to take everything out.
    if not covenant.export_path.strip():
        findings.append(
            {
                "check": "export-path",
                "result": "fail",
                "detail": (
                    "No export path named. A free tier with no exit is a "
                    "roach motel wearing a gift box — the switching cost "
                    "is the capture Google Photos built for six years."
                ),
            }
        )
        score -= 15
    else:
        findings.append(
            {
                "check": "export-path",
                "result": "pass",
                "detail": "Export path: %s" % covenant.export_path.strip()[:120],
            }
        )

    # 5. The free floor must grow with the medium, not freeze by fiat.
    if not covenant.grows_with_medium:
        findings.append(
            {
                "check": "grows-with-medium",
                "result": "fail",
                "detail": (
                    "No commitment that the free floor tracks the medium. "
                    "A frozen free tier is generosity by attrition — the "
                    "iCloud 5 GB shape. Commit to growth or say honestly "
                    "why the floor cannot move."
                ),
            }
        )
        score -= 25
    else:
        findings.append(
            {
                "check": "grows-with-medium",
                "result": "pass",
                "detail": "Free floor commits to grow with the medium.",
            }
        )

    # 6. The maker may never mandate its own paid path for a core need.
    if covenant.mandates_own_paid_path:
        findings.append(
            {
                "check": "no-mandated-toll",
                "result": "fail",
                "detail": (
                    "The maker mandates its own paid service as the only "
                    "route for a core need — the iCloud-backup shape. "
                    "This fails outright: it is a toll, not a free tier."
                ),
            }
        )
        score -= 40
    else:
        findings.append(
            {
                "check": "no-mandated-toll",
                "result": "pass",
                "detail": "No core need is gated behind the maker's paid path.",
            }
        )

    report["score"] = max(0, min(100, score))
    if report["score"] >= 80:
        report["verdict"] = "honest"
    elif report["score"] >= 50:
        report["verdict"] = "weak"
    else:
        report["verdict"] = "rugpull-risk"
    return report
