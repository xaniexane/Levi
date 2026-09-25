"""CLI: python -m levi.fairtrade <patterns|audit|declare|ledger|counter|playbook|brief>

Examples:
  python -m levi.fairtrade patterns
  python -m levi.fairtrade audit '{"name":"Free VPN","gives":["private browsing"],"asks":[],"hidden":["sells traffic logs"],"entry_steps":1,"exit_steps":6}'
  python -m levi.fairtrade declare --name "Fair Trade catalog" --gives "sly-generosity pattern catalog" --asks "nothing; pure archive entry"
  python -m levi.fairtrade ledger
  python -m levi.fairtrade counter roach-motel-funnel
  python -m levi.fairtrade playbook
  python -m levi.fairtrade brief
"""

from __future__ import annotations

import argparse
import json
import sys

from . import audit_offer, declare_trade, get_pattern, pattern_ids, read_ledger
from . import brief as awareness_brief
from . import counterplay as get_counterplay
from . import playbook as full_playbook


def _cmd_patterns(_args: argparse.Namespace) -> int:
    for pid in pattern_ids():
        p = get_pattern(pid)
        print("== %s (%s)" % (p["name"], p["id"]))
        print("  exemplar: %s" % p["exemplar"])
        print("  gift:     %s" % p["the_generosity"])
        print("  capture:  %s" % p["the_capture"])
        print("  refuses:  %s" % p["what_they_refuse"])
        print("  inversion: %s" % p["inversion"])
        print()
    return 0


def _cmd_audit(args: argparse.Namespace) -> int:
    try:
        offer = json.loads(args.offer)
    except (json.JSONDecodeError, TypeError) as exc:
        print("error: offer must be valid JSON: %s" % exc, file=sys.stderr)
        return 2
    try:
        report = audit_offer(offer)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def _cmd_declare(args: argparse.Namespace) -> int:
    record = declare_trade(
        name=args.name,
        gives=args.gives,
        asks=args.asks,
        note=args.note,
    )
    print(json.dumps(record, indent=2, ensure_ascii=False))
    return 0


def _cmd_ledger(_args: argparse.Namespace) -> int:
    entries = read_ledger()
    if not entries:
        print("ledger is empty — no honest trades declared yet.")
        return 0
    for e in entries:
        asks = "; ".join(e["asks"]) if e["asks"] else "(asks nothing)"
        print("[%s] %s" % (e["declared_at"], e["name"]))
        print("  gives: %s" % "; ".join(e["gives"]))
        print("  asks:  %s" % asks)
        if e["note"]:
            print("  note:  %s" % e["note"])
    return 0


def _cmd_counter(args: argparse.Namespace) -> int:
    try:
        cp = get_counterplay(args.pattern_id)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    p = get_pattern(args.pattern_id)
    print("== %s -> LEVI counter-play" % p["name"])
    print("technique: %s" % cp["technique"])
    print("profit:    %s" % cp["profit_engine"])
    print("popular:   %s" % cp["popularity_engine"])
    print("proven by: %s" % cp["levi_proof"])
    return 0


def _cmd_playbook(_args: argparse.Namespace) -> int:
    print(full_playbook(), end="")
    return 0


def _cmd_brief(_args: argparse.Namespace) -> int:
    print(awareness_brief())
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.fairtrade", description="Honest generosity, audited — and exploited."
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("patterns", help="list the sly-generosity pattern catalog")

    p_audit = sub.add_parser("audit", help="audit one offer (JSON)")
    p_audit.add_argument("offer", help="offer as a JSON object")
    p_audit.set_defaults(func=_cmd_audit)

    p_dec = sub.add_parser("declare", help="declare an honest trade to the ledger")
    p_dec.add_argument("--name", required=True)
    p_dec.add_argument("--gives", nargs="+", required=True)
    p_dec.add_argument("--asks", nargs="*", default=[])
    p_dec.add_argument("--note", default="")
    p_dec.set_defaults(func=_cmd_declare)

    p_pat = sub.add_parser("ledger", help="read the honest-trade ledger")
    p_pat.set_defaults(func=_cmd_ledger)
    sub.choices["patterns"].set_defaults(func=_cmd_patterns)

    p_counter = sub.add_parser("counter", help="LEVI's counter-play for one sly trade")
    p_counter.add_argument("pattern_id", help="pattern id from `patterns`")
    p_counter.set_defaults(func=_cmd_counter)

    p_play = sub.add_parser("playbook", help="the full counter-playbook")
    p_play.set_defaults(func=_cmd_playbook)

    p_brief = sub.add_parser("brief", help="compact awareness brief for the agent loop")
    p_brief.set_defaults(func=_cmd_brief)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
