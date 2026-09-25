"""CLI: python -m levi.growth.levelup

Thin entry point over the level-up layer. Commands:

    award  --entity nanobit --attention 7 --interaction 8 [--intensity 2]
    goal   --quota 11 [--date YYYY-MM-DD]        # plan + materialize the day
    answer --date YYYY-MM-DD --qid <id> --entity nanobit --correct 1 0.5 [--intensity 3]
    status --entity nanobit
    scan   --entity nanobit                      # anti-cheat: detect, no penalties
    penalize --entity nanobit --force            # enforce Chauncey's law
    penalties --entity nanobit                   # penalty + ability + token status

EXP math and level-ups run automatically: every award re-checks for a
threshold crossing and journals kind="level-up" exactly once.
"""

from __future__ import annotations

import argparse
import json
import sys


def cmd_award(args) -> int:
    from levi.growth.levelup import award_reply, entity_total, maybe_level_up

    receipt = award_reply(
        args.entity, args.attention, args.interaction, args.intensity
    )
    up = maybe_level_up(args.entity)
    if args.json:
        print(json.dumps({"receipt": receipt, "level_up": up}, indent=2))
        return 0
    print(
        "+%d EXP -> %s (total %d)"
        % (receipt["exp_delta"], args.entity, receipt["total_exp"])
    )
    if up:
        print("LEVEL UP: %s" % up["blurb"])
    return 0


def cmd_goal(args) -> int:
    from levi.growth.levelup import ensure_goal

    goal = ensure_goal(args.date, args.quota)
    if args.json:
        print(json.dumps(goal, indent=2))
        return 0
    print("goal %s: %d questions" % (goal["date"], goal["quota"]))
    for a in goal["assignments"]:
        mark = "x" if a["status"] == "answered" else " "
        print("  [%s] %s  %s  %s" % (mark, a["id"], a["subject"], a["topic_id"]))
    return 0


def cmd_answer(args) -> int:
    from levi.growth.levelup import answer_question, maybe_level_up

    out = answer_question(
        args.date, args.qid, args.entity, args.correct, args.intensity
    )
    up = maybe_level_up(args.entity)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt": out["receipt"],
                    "goal_complete": out["goal_complete"],
                    "bonus_receipt": out["bonus_receipt"],
                    "level_up": up,
                },
                indent=2,
            )
        )
        return 0
    r = out["receipt"]
    print("+%d EXP -> %s for %s" % (r["exp_delta"], args.entity, args.qid))
    if out["bonus_receipt"]:
        print("+%d EXP daily-complete bonus" % out["bonus_receipt"]["exp_delta"])
    if up:
        print("LEVEL UP: %s" % up["blurb"])
    return 0


def cmd_penalties(args) -> int:
    from levi.growth.levelup import (
        ability_status,
        active_penalties,
        effective_exp,
        entity_total,
        level_for,
        verify_adj,
    )

    total = entity_total(args.entity)
    eff = effective_exp(args.entity)
    ok, errors = verify_adj()
    info = {
        "entity": args.entity,
        "ledger_total": total,
        "effective_exp": eff,
        "level": level_for(eff),
        "adjudication_chain_ok": ok,
        "adjudication_errors": errors,
        "active_penalties": [
            {"seq": p["seq"], "data": p["data"]} for p in active_penalties(args.entity)
        ],
        "abilities": ability_status(args.entity),
    }
    if args.json:
        print(json.dumps(info, indent=2))
        return 0
    print(
        "%s: %d EXP ledger, %d effective, level %d"
        % (args.entity, total, eff, level_for(eff))
    )
    print("adjudication chain: %s" % ("OK" if ok else "BROKEN: %s" % "; ".join(errors)))
    print("active penalties: %d" % len(info["active_penalties"]))
    print("abilities: %s" % ", ".join(info["abilities"]["active"] or ["(none)"]))
    print("earned super tokens: %d" % info["abilities"]["earned_super_tokens"])
    return 0


def cmd_scan(args) -> int:
    from levi.growth.levelup import detect

    f = detect(args.entity)
    if args.json:
        print(json.dumps(f, indent=2))
        return 0
    print("scan %s: chain %s, illicit_exp=%d"
          % (args.entity, "OK" if f["chain_ok"] else "BROKEN", f["illicit_exp"]))
    if f["tampered_span"]:
        print("  tampered span: seqs %d..%d" % f["tampered_span"])
    for fl in f["flags"]:
        print("  flag seq=%s kind=%s: %s (+%d)"
              % (fl["seq"], fl["kind"], fl["reason"], fl["illicit_exp"]))
    for v in f["velocity_days"]:
        print("  velocity %s: total %d > cap %d (excess %d)"
              % (v["date"], v["day_total"], v["cap"], v["excess"]))
    for a in f["acceleration"]:
        print("  acceleration: %s unlocked without level %d"
              % (a["ability_id"], a["level_required"]))
    return 0


def cmd_penalize(args) -> int:
    from levi.growth.levelup import apply_penalty, detect

    f = detect(args.entity)
    if f["illicit_exp"] <= 0 and not f["acceleration"]:
        print("nothing illegitimate found for %s — no penalty" % args.entity)
        return 0
    if not args.force:
        print("refusing: pass --force to enforce the penalty "
              "(illicit_exp=%d)" % f["illicit_exp"])
        return 2
    p = apply_penalty(args.entity, f, note=args.note or "")
    d = p["data"]
    print("penalty seq=%d for %s: confiscated %d EXP, level %d -> %d "
          "(lost %d), revoked %s, tokens %d, review: chauncey-review"
          % (p["seq"], args.entity, d["confiscated_exp"], d["level_before"],
             d["level_after"], d["levels_lost"],
             d["abilities_revoked"] or ["(none)"], d["tokens_confiscated"]))
    return 0


def cmd_status(args) -> int:
    from levi.growth.levelup import entity_total, exp_to_next, verify_chain

    total = entity_total(args.entity)
    lvl, to_next = exp_to_next(total)
    ok, errors = verify_chain()
    if args.json:
        print(
            json.dumps(
                {
                    "entity": args.entity,
                    "total_exp": total,
                    "level": lvl,
                    "exp_to_next": to_next,
                    "chain_ok": ok,
                    "chain_errors": errors,
                },
                indent=2,
            )
        )
        return 0
    print("%s: level %d, %d EXP (%d to next level)" % (args.entity, lvl, total, to_next))
    print("ledger chain: %s" % ("OK" if ok else "BROKEN: %s" % "; ".join(errors)))
    return 0


def main(argv=None) -> int:
    from datetime import date

    ap = argparse.ArgumentParser(prog="levi.growth.levelup")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("award")
    p.add_argument("--entity", default="nanobit")
    p.add_argument("--attention", type=int, required=True)
    p.add_argument("--interaction", type=int, required=True)
    p.add_argument("--intensity", type=int, default=1)
    p.set_defaults(func=cmd_award)

    p = sub.add_parser("goal")
    p.add_argument("--quota", type=int, required=True)
    p.add_argument("--date", default=date.today().isoformat())
    p.set_defaults(func=cmd_goal)

    p = sub.add_parser("answer")
    p.add_argument("--date", required=True)
    p.add_argument("--qid", required=True)
    p.add_argument("--entity", default="nanobit")
    p.add_argument("--correct", type=float, nargs="+", required=True)
    p.add_argument("--intensity", type=int, default=1)
    p.set_defaults(func=cmd_answer)

    p = sub.add_parser("status")
    p.add_argument("--entity", default="nanobit")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("scan")
    p.add_argument("--entity", default="nanobit")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("penalize")
    p.add_argument("--entity", default="nanobit")
    p.add_argument("--force", action="store_true",
                   help="required: enforcement is deliberate, never accidental")
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_penalize)

    p = sub.add_parser("penalties")
    p.add_argument("--entity", default="nanobit")
    p.set_defaults(func=cmd_penalties)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
