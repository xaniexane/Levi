"""CLI for the Legion bot product.

Thin hook; the real work lives in the legion package. Registered from
core/levi/cli/main.py via register_legion_parser(sub) and dispatched
as cmd_legion — the same minimal-hook pattern as the other modules.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .packs import get_pack, list_packs
from .product import configure
from .sale import (
    issue_license,
    plan_checkout,
    quote_legion,
    split_paper,
)
from .sitelift_link import propose_team
from .team import BusinessProfile, assemble_team


def _home() -> Path:
    base = os.environ.get("LEVI_HOME") or str(Path.home() / ".levi")
    return Path(base).expanduser()


def _configs_path() -> Path:
    d = _home() / "legion"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d / "installs.jsonl"


def _save_install(record: Dict[str, Any]) -> None:
    p = _configs_path()
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    os.chmod(p, 0o600)


# ---------------------------------------------------------------------------
# parser registration (the minimal hook in main.py)
# ---------------------------------------------------------------------------


def register_legion_parser(sub) -> None:
    leg = sub.add_parser(
        "legion",
        help="Legion bot product: configure, assemble crew, packs, paper quotes",
    )
    cmd = leg.add_subparsers(dest="legion_cmd")

    cfg = cmd.add_parser("configure", help="white-label a Legion install")
    cfg.add_argument("--name", required=True, help="business name")
    cfg.add_argument("--face-name", default="", help="face display name")
    cfg.add_argument(
        "--tone",
        default="warm",
        help="warm|professional|playful|direct|concierge",
    )
    cfg.add_argument("--greeting", default="", help="owner-written greeting")
    cfg.add_argument("--color", default="", help="brand color #RRGGBB")
    cfg.add_argument(
        "--type",
        default="generic",
        help="restaurant|salon|shop|generic",
    )
    cfg.add_argument("--vocab", default="", help="comma-separated domain vocabulary")

    tm = cmd.add_parser("team", help="assemble the tailored crew")
    tm.add_argument("--name", default="", help="business name")
    tm.add_argument("--type", default="generic", help="business type")
    tm.add_argument("--size", default="small", help="solo|small|team")
    tm.add_argument(
        "--need", action="append", default=[], help="crew need (repeatable)"
    )
    tm.add_argument("--pack", default="", help="add-on pack to merge needs from")
    tm.add_argument(
        "--sitelift",
        default="",
        help="Site Lift report id (from ~/.levi/services/lifts) to propose the crew from",
    )

    pk = cmd.add_parser("pack", help="show a specialist add-on pack")
    pk.add_argument("name", nargs="?", default="", help="restaurant|salon|shop|generic")
    pk.add_argument("--list", action="store_true", help="list packs")

    q = cmd.add_parser("quote", help="paper quote for a Legion install (moves nothing)")
    q.add_argument("--type", default="generic", help="business type")
    q.add_argument(
        "--pack", action="append", default=[], help="add-on pack (repeatable)"
    )
    q.add_argument(
        "--giant-price",
        type=float,
        default=None,
        help="giant's comparable monthly price, when known",
    )
    q.add_argument("--strategy", default="volume", help="volume|margin")
    q.add_argument("--buyer", default="", help="buyer name (stays blank on paper)")
    q.add_argument("--name", default="", help="business name (issues a paper license)")


# ---------------------------------------------------------------------------
# command dispatch
# ---------------------------------------------------------------------------


def cmd_legion(args) -> Optional[int]:
    """Legion bot product commands."""
    cmd = getattr(args, "legion_cmd", None) or "configure"
    if cmd == "configure":
        return _cmd_configure(args)
    if cmd == "team":
        return _cmd_team(args)
    if cmd == "pack":
        return _cmd_pack(args)
    if cmd == "quote":
        return _cmd_quote(args)
    print(f"unknown legion command: {cmd}")
    return 1


def _cmd_configure(args) -> int:
    colors = {}
    if args.color:
        colors["primary"] = args.color
    try:
        wl = configure(
            args.name,
            face_name=args.face_name,
            tone=args.tone,
            greeting=args.greeting,
            brand_colors=colors,
            domain_vocabulary=[v.strip() for v in args.vocab.split(",") if v.strip()],
            business_type=args.type,
        )
    except Exception as exc:
        print(f"configure refused: {exc}")
        return 1
    record = {"kind": "white-label", **wl.to_dict()}
    _save_install(record)
    print(f"Legion install configured for {wl.business_name}")
    print(f"  face: {wl.face_name} | tone: {wl.tone} | type: {wl.business_type}")
    print("  identity: " + wl.identity_statement)
    return 0


def _cmd_team(args) -> int:
    if args.sitelift:
        from levi.services.site_lift import LiftError, load_report

        try:
            report = load_report(args.sitelift)
        except LiftError as e:
            print(f"no Site Lift report: {e}")
            return 1
        if report is None:
            print(f"no Site Lift report {args.sitelift!r} in ~/.levi/services/lifts")
            return 1
        try:
            proposal = propose_team(
                report,
                business_name=args.name or "",
                business_type=args.type or None,
                size=args.size,
            )
        except Exception as exc:
            print(f"proposal refused: {exc}")
            return 1
        team = proposal["team"]
        print(f"tailored offer from Site Lift {proposal['report_id']}")
        print(
            f"  failed measured checks: {proposal['failed_checks']} "
            f"(unmapped: {len(proposal['unmapped'])})"
        )
        print(
            f"  business type: {proposal['business_type']} "
            f"({proposal['business_type_source']}), suggested pack: {proposal['suggested_pack']}"
        )
    else:
        try:
            profile = BusinessProfile(
                business_type=args.type,
                size=args.size,
                needs=list(args.need),
                business_name=args.name,
            )
        except Exception as exc:
            print(f"profile refused: {exc}")
            return 1
        if args.pack:
            from .packs import merge_pack_into_profile

            try:
                merged = merge_pack_into_profile(profile.__dict__, args.pack)
            except Exception as exc:
                print(f"pack refused: {exc}")
                return 1
            profile = BusinessProfile(
                business_type=profile.business_type,
                size=profile.size,
                needs=merged["needs"],
                business_name=profile.business_name,
            )
        try:
            team = assemble_team(profile).to_dict()
        except Exception as exc:
            print(f"assembly refused: {exc}")
            return 1
        print(f"tailored crew for {profile.business_name or profile.business_type}:")
    print(f"  team {team['team_id']} — face role: {team['face_role']}")
    for m in team["crew"]:
        print(f"  {m['role']:14s} {m['seat_key']:28s} ({m['category']})")
    print(f"  handoffs: {len(team['handoff_rules'])} rules")
    return 0


def _cmd_pack(args) -> int:
    if args.list or not args.name:
        for p in list_packs():
            print(f"  {p['name']:12s} {p['blurb']}")
        return 0
    try:
        pack = get_pack(args.name)
    except Exception as exc:
        print(f"pack refused: {exc}")
        return 1
    print(f"pack: {pack['name']} — {pack['blurb']}")
    print("  vocabulary: " + ", ".join(pack["vocabulary"][:8]) + " ...")
    print(f"  extra crew needs: {', '.join(pack['extra_needs'])}")
    for f in pack["faqs"][:3]:
        print(f"  FAQ: {f['q']}")
    for t in pack["tasks"]:
        print(f"  task: {t['task']} -> {t['owner_role']}")
    for e in pack["escalations"]:
        print(f"  escalation: {e['trigger']} -> {e['to']}")
    return 0


def _cmd_quote(args) -> int:
    try:
        q = quote_legion(
            business_type=args.type,
            packs=args.pack,
            giant_price=args.giant_price,
            strategy=args.strategy,
        )
    except Exception as exc:
        print(f"quote refused: {exc}")
        return 1
    print(f"paper quote {q.quote_id} — ${q.total_usd:,.2f} lifetime, one copy")
    print(
        f"  base: ${q.base_lifetime:,.2f} "
        f"(${q.base_monthly:,.2f}/mo x 24) | packs: {q.packs or 'none'}"
    )
    for line in q.rationale:
        print(f"  - {line}")
    split = split_paper(q.total_usd)
    print(
        f"  70/30 (paper): keeper ${split['keeper_usd']:,.2f} / "
        f"pool ${split['pool_usd']:,.2f}"
    )
    if args.name:
        checkout = plan_checkout(q, buyer=args.buyer)
        print("\ncheckout record (paper):")
        print("  " + checkout.preview.replace("\n", "\n  "))
        lic = issue_license(q, checkout, business_name=args.name, buyer=args.buyer)
        print(
            f"paper license issued: {lic.license_id} — status {lic.status} "
            f"(buyer blank until a real sale)"
        )
    return 0
