"""python -m levi.craft — the guild quarter CLI.

  hallmark strike <file> --maker NAME [--verifier NAME] [--quality Q]
  hallmark verify <file>
  hallmark require <file>            # deny-closed gate
  guild indenture --skill S --apprentice A --master M
  guild practice --skill S --apprentice A --task T [--failed]
  guild promote --skill S --apprentice A --mentor M --signoff TEXT
  guild masterpiece --skill S --journeyman J --artifact PATH --summary TEXT
  guild judge --skill S --journeyman J --verdict accepted|rejected \
      --judges A,B [--sha HEX]
  guild status [--skill S]
  guild hall [--skill S]
  measures list [--system SYS]
  measures convert <value> <from> <to>
  measures describe <unit>
  measures chain-area <square-chains>   # Gunter's decimal trick
  measures seked <rise> <run>           # Egyptian slope-as-ratio
"""

from __future__ import annotations

import argparse
import json
import sys

from levi.craft import guild, hallmark, measures


def _dump(obj) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True, default=str))


def cmd_hallmark(args) -> int:
    if args.op == "strike":
        _dump(
            hallmark.strike_file(
                args.file,
                maker=args.maker,
                verifier=args.verifier or "",
                quality=args.quality,
            )
        )
    elif args.op == "verify":
        mark = hallmark.read_sidecar(args.file)
        if mark is None:
            print("no hallmark struck on %s" % args.file)
            return 1
        with open(args.file, "rb") as fh:
            ok, reason = hallmark.verify(mark, fh.read())
        print(("VALID: " if ok else "INVALID: ") + reason)
        return 0 if ok else 1
    elif args.op == "require":
        try:
            _dump(hallmark.require_hallmarked(args.file))
        except hallmark.UnhallmarkedError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    return 0


def cmd_guild(args) -> int:
    try:
        if args.op == "indenture":
            _dump(guild.indenture(args.skill, args.apprentice, args.master))
        elif args.op == "practice":
            _dump(
                guild.log_practice(
                    args.skill,
                    args.apprentice,
                    args.task,
                    result="failed" if args.failed else "completed",
                )
            )
        elif args.op == "promote":
            _dump(
                guild.promote(
                    args.skill,
                    args.apprentice,
                    mentor=args.mentor,
                    signoff=args.signoff,
                )
            )
        elif args.op == "masterpiece":
            _dump(
                guild.submit_masterpiece(
                    args.skill, args.journeyman, args.artifact, args.summary
                )
            )
        elif args.op == "judge":
            _dump(
                guild.judge_masterpiece(
                    args.skill,
                    args.journeyman,
                    args.verdict,
                    args.judges.split(","),
                    artifact_sha256=args.sha or "",
                )
            )
        elif args.op == "status":
            for rec in guild.status(args.skill):
                print(json.dumps(rec, sort_keys=True))
        elif args.op == "hall":
            for rec in guild.guildhall(args.skill):
                print(json.dumps(rec, sort_keys=True))
    except guild.GuildError as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 2
    return 0


def cmd_measures(args) -> int:
    try:
        if args.op == "list":
            for u in measures.list_units(args.system):
                flag = " [regional variant]" if u.variant else ""
                print(
                    "%-14s %-4s %-10s %s%s" % (u.name, u.symbol, u.system, u.era, flag)
                )
        elif args.op == "convert":
            print(measures.convert(args.value, args.from_unit, args.to_unit))
        elif args.op == "describe":
            _dump(measures.describe(args.unit))
        elif args.op == "chain-area":
            print(measures.chain_area(args.square_chains))
        elif args.op == "seked":
            print(measures.seked(args.rise, args.run))
    except (KeyError, ValueError) as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 2
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="levi.craft")
    sub = ap.add_subparsers(dest="cmd", required=True)

    hm = sub.add_parser("hallmark")
    hm.add_argument("op", choices=["strike", "verify", "require"])
    hm.add_argument("file")
    hm.add_argument("--maker", default="")
    hm.add_argument("--verifier", default="")
    hm.add_argument("--quality", default="standard")

    gd = sub.add_parser("guild")
    gd.add_argument(
        "op",
        choices=[
            "indenture",
            "practice",
            "promote",
            "masterpiece",
            "judge",
            "status",
            "hall",
        ],
    )
    gd.add_argument("--skill", default=None)
    gd.add_argument("--apprentice", default="")
    gd.add_argument("--master", default="")
    gd.add_argument("--journeyman", default="")
    gd.add_argument("--task", default="")
    gd.add_argument("--artifact", default="")
    gd.add_argument("--summary", default="")
    gd.add_argument("--verdict", default="")
    gd.add_argument("--judges", default="")
    gd.add_argument("--sha", default="")
    gd.add_argument("--failed", action="store_true")
    gd.add_argument("--mentor", default="")
    gd.add_argument("--signoff", default="")

    ms = sub.add_parser("measures")
    ms.add_argument(
        "op", choices=["list", "convert", "describe", "chain-area", "seked"]
    )
    ms.add_argument("a", nargs="?")
    ms.add_argument("b", nargs="?")
    ms.add_argument("c", nargs="?")
    ms.add_argument("--system", default=None)

    args = ap.parse_args(argv)
    if args.cmd == "measures":
        if args.op == "convert":
            args.value, args.from_unit, args.to_unit = (float(args.a), args.b, args.c)
        elif args.op == "describe":
            args.unit = args.a
        elif args.op == "chain-area":
            args.square_chains = float(args.a)
        elif args.op == "seked":
            args.rise, args.run = float(args.a), float(args.b)
    return {"hallmark": cmd_hallmark, "guild": cmd_guild, "measures": cmd_measures}[
        args.cmd
    ](args)


if __name__ == "__main__":
    raise SystemExit(main())
