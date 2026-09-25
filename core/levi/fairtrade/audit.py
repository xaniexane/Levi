"""Offer auditor: how honest is the trade, really?

An *offer* is a plain dict describing a deal someone (a giant, an app, a
LEVI feature) presents:

    {
        "name": "Free cloud photos!",
        "gives": ["free photo backup"],
        "asks": ["your photo metadata for ad targeting"],
        "hidden": ["kept even after you delete"],
        "exit_cost": "export is lossy; albums stay behind",
        "exit_steps": 8,            # how many steps to leave
        "entry_steps": 1,           # how many steps to join
        "rule_binds_maker": False,  # does the maker's own product obey the rule?
        "manufactures_obligation": True,  # streaks / daily-debt mechanics?
    }

``audit_offer`` returns a report: a 0-100 honesty score, the verdict, the
matched sly-generosity patterns with evidence, and what honest would look
like (the inversion from the catalog).

Scoring is deliberately conservative: it flags risk and admits what it
does not know. Missing fields are treated as unknowns, not as clean.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .trades import PATTERNS


def _text(offer: Dict[str, Any]) -> str:
    parts = [str(offer.get("name", ""))]
    for key in ("gives", "asks", "hidden", "exit_cost"):
        value = offer.get(key)
        if isinstance(value, list):
            parts.extend(str(v) for v in value)
        elif value:
            parts.append(str(value))
    return " ".join(parts).lower()


def _match_patterns(text: str) -> List[Dict[str, Any]]:
    matches = []
    for pattern in PATTERNS:
        signals = [s for s in pattern["signals"] if s in text]
        if len(signals) >= 2:
            matches.append(
                {
                    "pattern_id": pattern["id"],
                    "name": pattern["name"],
                    "evidence": signals,
                    "inversion": pattern["inversion"],
                }
            )
    return matches


def audit_offer(offer: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(offer, dict) or not str(offer.get("name", "")).strip():
        raise ValueError("offer must be a dict with a non-empty 'name'")
    report: Dict[str, Any] = {"name": str(offer["name"]), "findings": []}
    score = 100

    asks = offer.get("asks") or []
    hidden = offer.get("hidden") or []

    # 1. "Nothing asked" is the biggest tell: there is always a cost.
    if not asks and not hidden:
        report["findings"].append(
            {
                "check": "disclosed-cost",
                "result": "fail",
                "detail": (
                    "The offer names no cost. Generosity without a stated "
                    "cost is where sly trades hide — the price is being "
                    "paid somewhere out of sight."
                ),
            }
        )
        score -= 30
    elif asks:
        report["findings"].append(
            {
                "check": "disclosed-cost",
                "result": "pass",
                "detail": "The offer states what it asks for: "
                + ", ".join(str(a) for a in asks),
            }
        )

    # 2. Hidden costs are an outright confession.
    if hidden:
        report["findings"].append(
            {
                "check": "hidden-cost",
                "result": "fail",
                "detail": "The offer admits hidden costs: "
                + ", ".join(str(h) for h in hidden),
            }
        )
        score -= 25

    # 3. Roach-motel asymmetry: exit must be as easy as entry.
    entry = offer.get("entry_steps")
    exit_ = offer.get("exit_steps")
    if isinstance(entry, (int, float)) and isinstance(exit_, (int, float)):
        if exit_ > entry * 2:
            report["findings"].append(
                {
                    "check": "symmetric-friction",
                    "result": "fail",
                    "detail": (
                        "Exit takes %s steps vs %s to enter — friction is "
                        "weaponized against leaving." % (exit_, entry)
                    ),
                }
            )
            score -= 25
        else:
            report["findings"].append(
                {
                    "check": "symmetric-friction",
                    "result": "pass",
                    "detail": "Entry and exit friction are comparable.",
                }
            )
    else:
        report["findings"].append(
            {
                "check": "symmetric-friction",
                "result": "unknown",
                "detail": (
                    "Entry/exit steps not given — cannot verify leaving is "
                    "as easy as joining. Treat with suspicion."
                ),
            }
        )
        score -= 10

    # 4. The rule-maker must obey its own rule.
    binds_maker = offer.get("rule_binds_maker")
    if binds_maker is False:
        report["findings"].append(
            {
                "check": "rule-binds-maker",
                "result": "fail",
                "detail": (
                    "The maker's own product is exempt from the rule it "
                    "imposes on others — asymmetry is the tell of a weapon."
                ),
            }
        )
        score -= 20
    elif binds_maker is True:
        report["findings"].append(
            {
                "check": "rule-binds-maker",
                "result": "pass",
                "detail": "The rule binds the rule-maker too.",
            }
        )
    else:
        report["findings"].append(
            {
                "check": "rule-binds-maker",
                "result": "unknown",
                "detail": "Not stated whether the rule binds the maker.",
            }
        )
        score -= 5

    # 5. Manufactured obligation (streaks, daily debt, FOMO).
    if offer.get("manufactures_obligation"):
        report["findings"].append(
            {
                "check": "obligation-free",
                "result": "fail",
                "detail": (
                    "The offer manufactures obligation — daily debt, "
                    "streaks, or FOMO mechanics that punish a gap."
                ),
            }
        )
        score -= 20
    else:
        report["findings"].append(
            {
                "check": "obligation-free",
                "result": "pass",
                "detail": "No manufactured obligation detected.",
            }
        )

    report["patterns"] = _match_patterns(_text(offer))
    report["score"] = max(0, min(100, score))
    if report["score"] >= 80:
        report["verdict"] = "honest"
    elif report["score"] >= 50:
        report["verdict"] = "sly"
    else:
        report["verdict"] = "predatory"
    return report
