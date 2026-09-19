"""CLI for the 48-law strategy engine.

``levi strategy consult "..."`` — project a situation through the 48 laws.
``levi strategy laws`` — list all 48 laws.
``levi strategy law <id>`` — show one law, forward and reverse.
"""

from __future__ import annotations

import argparse

from . import ENGINE, apply, consult, return_to_sender


def _register_commands(sub) -> None:
    c = sub.add_parser("consult", help="project a situation through the 48 laws")
    c.add_argument("situation", help="describe the situation in plain words")
    c.add_argument("--top", type=int, default=5, help="how many laws to surface")
    sub.add_parser("laws", help="list all 48 laws")
    one = sub.add_parser("law", help="show one law, forward and reverse")
    one.add_argument("id", type=int, help="law number 1-48")

    pr = sub.add_parser("project", help="run the 5-3-5 lookahead on a situation")
    pr.add_argument("situation", help="describe the situation in plain words")
    pr.add_argument("--depth", type=int, default=5, help="steps ahead (3-7, default 5)")
    pr.add_argument("--domain", default=None, help="life area to weight (e.g. money, health)")

    rf = sub.add_parser("reflect", help="return-to-sender: reflect an attack cleanly")
    rf.add_argument("attack", help="describe the attack/provocation")


def register_strategy_parser(sub) -> None:
    st = sub.add_parser("strategy", help="the 48 forward/reverse strategy laws")
    cmds = st.add_subparsers(dest="strategy_cmd")
    _register_commands(cmds)


def _fmt_reading(rd) -> str:
    law = rd.law
    lines = [f"[Law {law.id:02d}] {law.name}  (stance: {rd.stance}, score {rd.score:.0f})",
             f"  Doctrine: {law.doctrine}"]
    if rd.stance in ("forward", "both"):
        lines.append(f"  FORWARD: {law.forward}")
    if rd.stance in ("reverse", "both"):
        lines.append(f"  REVERSE: {law.reverse}")
    lines.append(f"  Constraints: {'; '.join(law.constraints)}")
    return "\n".join(lines)


def _fmt_step(s) -> str:
    return (f"  [{s.n}] Law {s.law_id:02d} {s.law_name} ({s.stance}, cost: {s.cost_tier})\n"
            f"      Move: {s.move}\n"
            f"      Price: {s.price}")


def _fmt_reflection(rf) -> str:
    lines = ["RETURN-TO-SENDER", f"  Reflected: {rf.reflected}",
             f"  Your move: {rf.your_move}", "  Not this:"]
    lines.extend(f"    - {n}" for n in rf.not_this)
    return "\n".join(lines)


def cmd_strategy(args) -> int:
    cmd = getattr(args, "strategy_cmd", None)
    if cmd == "consult":
        readings = consult(args.situation, top=args.top)
        if not readings:
            print("No law bears on that situation — say more.")
            return 0
        print(f"Situation: {args.situation}\n")
        for rd in readings:
            print(_fmt_reading(rd))
            print()
        return 0
    if cmd == "laws":
        for law in ENGINE.laws:
            print(law.brief())
        return 0
    if cmd == "law":
        try:
            law = ENGINE.get(args.id)
        except KeyError:
            print(f"No law {args.id} — the 48 run 1-48.")
            return 1
        print(f"[Law {law.id:02d}] {law.name}\nDoctrine: {law.doctrine}\n")
        print(f"FORWARD: {law.forward}\n")
        print(f"REVERSE: {law.reverse}\n")
        print("Constraints:")
        for c in law.constraints:
            print(f"  - {c}")
        print(f"Signals: {', '.join(law.signals)}")
        return 0
    if cmd == "project":
        res = apply(args.situation, domain=args.domain)
        proj = res.projection
        if res.reflection is not None:
            print(">>> RETURN-TO-SENDER (attack detected) <<<\n")
            print(_fmt_reflection(res.reflection))
            print()
        print(f"Situation: {args.situation}\n")
        print("--- 5 STEPS AHEAD ---")
        for s in proj.steps5:
            print(_fmt_step(s))
        print("--- LOCK THE 3 ---")
        for s in proj.locked3:
            print(f"  LOCK [{s.n}] Law {s.law_id:02d} {s.law_name} ({s.stance})")
        print("--- NEXT 5 MAPPED ---")
        for s in proj.next5:
            print(_fmt_step(s))
        print(f"EFFICIENT PICK: {proj.efficient_pick}")
        return 0
    if cmd == "reflect":
        print(_fmt_reflection(return_to_sender(args.attack)))
        return 0
    print("usage: levi strategy {consult|project|reflect|laws|law}")
    return 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="levi-strategy")
    sub = p.add_subparsers(dest="strategy_cmd")
    _register_commands(sub)
    args = p.parse_args(argv)
    return cmd_strategy(args)


if __name__ == "__main__":
    raise SystemExit(main())
