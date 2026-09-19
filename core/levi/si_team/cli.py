"""`levi si-team` command surface: roster, consult, caps."""

from __future__ import annotations

import argparse
import json

from levi.si_team import counsel, roles, substrate


def _table(rows, headers):
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    lines = ["  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))]
    lines.append("  ".join("-" * w for w in widths))
    for row in rows:
        lines.append("  ".join(c.ljust(widths[i]) for i, c in enumerate(row)))
    return "\n".join(lines)


def cmd_roster(_args) -> int:
    registered = [f"registered:{r}" for r in substrate.registered_roles()]
    rows = []
    for name in roles.role_names():
        charter = roles.ROSTER[name]
        subs = " > ".join(["rules-engine"] + registered)
        rows.append(
            [name, charter.epithet, subs, "SPOTLIGHT" if name == "levi" else "crew"]
        )
    print(_table(rows, ["role", "epithet", "substrates", "billing"]))
    print()
    for name in roles.role_names():
        charter = roles.ROSTER[name]
        print(f"{name.upper()} — {charter.si_line}")
        print(f"  mandate: {charter.mandate}")
    print()
    print(
        "Substrate note: registered probes (register_substrate) > levi.alpha "
        "(alpha only, if importable) > rules-engine. Every consult receipt "
        "names what actually answered."
    )
    return 0


def cmd_consult(args) -> int:
    task = " ".join(args.task)
    receipt = counsel.consult(args.role, task)
    print(f"role:           {receipt.role}")
    print(f"substrate_used: {receipt.substrate_used}")
    print(f"refused:        {receipt.refused}")
    print(f"answer:         {receipt.answer}")
    if receipt.limits:
        print("limits:")
        for limit in receipt.limits:
            print(f"  - {limit}")
    return 0


def cmd_caps(args) -> int:
    report = counsel.capability_report(args.role)
    print(json.dumps(report, indent=2))
    return 0


def cmd_si_team(args) -> int:
    cmd = getattr(args, "si_cmd", None)
    if cmd == "roster":
        return cmd_roster(args)
    if cmd == "consult":
        return cmd_consult(args)
    if cmd == "caps":
        return cmd_caps(args)
    print("usage: levi si-team {roster,consult,caps}")
    return 2


def _add_leaf_commands(cmds) -> None:
    """Add roster/consult/caps to an argparse subparsers action."""
    cmds.add_parser("roster", help="table of roles, charters, substrates")

    consult_p = cmds.add_parser("consult", help="consult a crew role")
    consult_p.add_argument("role", help="levi | alpha | omega | dweller")
    consult_p.add_argument("task", nargs="+", help="the task to consult on")

    caps_p = cmds.add_parser("caps", help="capability report for a role")
    caps_p.add_argument("role", help="levi | alpha | omega | dweller")


def register_si_team_parser(sub) -> None:
    p = sub.add_parser("si-team", help="SI team roster, charters, routing")
    _add_leaf_commands(p.add_subparsers(dest="si_cmd"))


def main(argv=None) -> int:  # for `python -m levi.si_team`
    parser = argparse.ArgumentParser(prog="levi si-team")
    _add_leaf_commands(parser.add_subparsers(dest="si_cmd"))
    args = parser.parse_args(argv)
    return cmd_si_team(args)
