"""CLI: python -m levi.bridging

Disagreement-bridging legitimacy: add notes, record local ratings, and
query which notes earn cross-camp consensus. Mirrors the future
``levi bridging`` top-level command.
"""

from __future__ import annotations

import argparse
import sys

from levi.bridging.bridging import BridgingError, BridgingStore


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="levi bridging",
        description="Bridging consensus over local ratings — legitimacy without a central moderator.",
    )
    sub = p.add_subparsers(dest="cmd")

    n = sub.add_parser("note", help="add a note (a claim to be rated)")
    n.add_argument("--text", required=True)
    n.add_argument("--id", default=None, help="optional stable id")

    r = sub.add_parser("rate", help="record a rating for a note")
    r.add_argument("--note", required=True, help="note id")
    r.add_argument("--rater", required=True, help="rater id")
    r.add_argument("--value", required=True,
                   help="+1 helpful, -1 not helpful (any float in [-1,1])")

    sub.add_parser("notes", help="list notes with bridging scores and status")

    e = sub.add_parser("explain", help="show the bridging evidence for one note")
    e.add_argument("note_id")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        store = BridgingStore()
    except Exception as exc:  # pragma: no cover - defensive
        print(f"bridging: cannot open state: {exc}", file=sys.stderr)
        return 1

    try:
        if args.cmd == "note":
            note = store.add_note(args.text, note_id=args.id)
            print(f"note [{note.id}]")
        elif args.cmd == "rate":
            try:
                value = float(args.value)
            except ValueError:
                print(f"bridging: --value must be a number in [-1,1], got {args.value!r}",
                      file=sys.stderr)
                return 2
            store.add_rating(args.note, args.rater, value)
            print(f"rated: {args.rater} -> [{args.note[:8]}] = {value:+g}")
        elif args.cmd == "notes":
            print(store.format_notes())
        elif args.cmd == "explain":
            fit = store.fit()
            if args.note_id not in store.notes:
                print(f"bridging: unknown note {args.note_id!r}", file=sys.stderr)
                return 1
            from levi.bridging.bridging import note_status
            st = note_status(args.note_id, fit, store.ratings)
            note = store.notes[args.note_id]
            print(f"note [{note.id}]: {note.text}")
            print(f"  status={st['status']}  helpfulness(β)={st['helpfulness']:+.4f}")
            print(f"  note factor δ={fit.note_factor.get(note.id, 0.0):+.4f} "
                  f"(factional lean; ~0 = cross-camp)")
            print(f"  cross-camp support: {st['cross_camp_support']}")
            print("  raters (latent camp γ):")
            for rater, val in sorted(store.ratings[note.id].items()):
                print(f"    {rater:16s} rating={val:+.1f}  γ={fit.rater_factor.get(rater, 0.0):+.4f}")
        else:
            build_parser().print_help()
            return 2
    except BridgingError as exc:
        print(f"bridging: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
