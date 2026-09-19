"""CLI for the founder-level feature/price advisor.

``levi advise feature "Name" --demand 72 --demand-basis "..." --fit 0.8 --cost medium --doctrine 0.9``
``levi advise price --tier entry --giant-price 20 --strategy volume``
"""

from __future__ import annotations

import argparse

from .features import FeatureError, FeatureIdea, advise_feature
from .pricing import PriceError, PricePlan, advise_price


def _register_commands(sub) -> None:
    f = sub.add_parser("feature", help="score a feature idea: build / hold / kill")
    f.add_argument("name", nargs="+", help="the feature idea name")
    f.add_argument(
        "--demand",
        type=float,
        default=None,
        help="analyst-assessed demand composite 0-100 (requires --demand-basis)",
    )
    f.add_argument("--demand-basis", default="", help="why this demand score")
    f.add_argument("--fit", type=float, default=0.5, help="strategic fit 0..1")
    f.add_argument(
        "--cost",
        default="medium",
        choices=("small", "medium", "large"),
        help="build cost tier",
    )
    f.add_argument("--doctrine", type=float, default=0.5, help="doctrine fit 0..1")

    p = sub.add_parser("price", help="advise a price band per the keeper's doctrine")
    p.add_argument(
        "--tier",
        default="entry",
        choices=("entry", "standard", "flagship"),
        help="which tier to price",
    )
    p.add_argument(
        "--giant-price",
        type=float,
        default=None,
        help="the giant's comparable price (USD/mo); band anchors 30-60%% below it",
    )
    p.add_argument(
        "--strategy",
        default="volume",
        choices=("volume", "margin"),
        help="volume (low end) or margin (high end)",
    )
    p.add_argument(
        "--commission",
        type=float,
        default=0.0,
        help="founder commission rate 0..1, labeled separately",
    )


def register_advisor_parser(sub) -> None:
    adv = sub.add_parser(
        "advise", help="founder-level feature/price advisor (all local)"
    )
    cmds = adv.add_subparsers(dest="advise_cmd")
    _register_commands(cmds)


def cmd_advise(args) -> None:
    """Advisor: feature scoring and price bands."""
    cmd = getattr(args, "advise_cmd", None)
    if cmd == "feature":
        idea = FeatureIdea(
            name=" ".join(getattr(args, "name", []) or []),
            demand_composite=getattr(args, "demand", None),
            demand_basis=getattr(args, "demand_basis", ""),
            strategic_fit=getattr(args, "fit", 0.5),
            cost=getattr(args, "cost", "medium"),
            doctrine_fit=getattr(args, "doctrine", 0.5),
        )
        try:
            verdict = advise_feature(idea)
        except FeatureError as exc:
            print(f"feature not scored: {exc}")
            raise SystemExit(2)
        print(f"verdict: {verdict.verdict.upper()}")
        print(f"  oracle alignment: {verdict.alignment:.3f}")
        if verdict.demand_composite is not None:
            print(
                f"  demand: {verdict.demand_composite:.2f} ({verdict.demand_tier})"
            )
        else:
            print("  demand: unassessed")
        for reason in verdict.reasons:
            print(f"  - {reason}")
        return
    if cmd == "price":
        plan = PricePlan(
            tier=getattr(args, "tier", "entry"),
            giant_price=getattr(args, "giant_price", None),
            strategy=getattr(args, "strategy", "volume"),
            founder_commission=getattr(args, "commission", 0.0),
        )
        try:
            advice = advise_price(plan)
        except PriceError as exc:
            print(f"price not advised: {exc}")
            raise SystemExit(2)
        print(f"band: ${advice.low:.2f} - ${advice.high:.2f}/mo")
        print(f"  recommended: ${advice.recommended:.2f}/mo")
        print(f"  seat cap: {advice.seat_cap} (roster law)")
        if advice.commission_line > 0:
            print(f"  founder commission: ${advice.commission_line:.2f}/mo (separate line)")
        for reason in advice.rationale:
            print(f"  - {reason}")
        return
    print("usage: levi advise {feature|price} ...")
    raise SystemExit(2)
