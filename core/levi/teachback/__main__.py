"""``python -m levi.teachback`` — teach-back goal-model CLI.

Local only: reads/writes under the LEVI home (``LEVI_HOME`` or
``~/.levi``).

Commands:
    add ID --statement "..." [--confidence 0.5]
    show                    # current model with confidence
    brief                   # plain-language teach-back brief
    correct ID --correction "..."
    affirm ID
    evidence ID --note "..."
"""

from __future__ import annotations

import argparse
import sys

from .model import TeachbackModel


def _build() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="levi.teachback", description=__doc__.splitlines()[0]
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    ad = sub.add_parser("add", help="add a goal-model statement")
    ad.add_argument("id")
    ad.add_argument("--statement", required=True)
    ad.add_argument("--confidence", type=float, default=0.5)

    sub.add_parser("show", help="show the current model")
    sub.add_parser("brief", help="render the plain-language brief")

    co = sub.add_parser("correct", help="apply a user correction")
    co.add_argument("id")
    co.add_argument("--correction", required=True)

    af = sub.add_parser("affirm", help="confirm a statement is right")
    af.add_argument("id")

    ev = sub.add_parser("evidence", help="log corroborating evidence")
    ev.add_argument("id")
    ev.add_argument("--note", required=True)
    return p


def main(argv=None) -> int:
    args = _build().parse_args(argv)
    m = TeachbackModel()
    if args.cmd == "add":
        try:
            doc = m.add_statement(args.id, args.statement, args.confidence)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"added [{doc['id']}] confidence={doc['confidence']:.2f}")
    elif args.cmd == "show":
        rows = m.model()
        if not rows:
            print("no statements yet")
        for r in rows:
            print(
                f"[{r['id']}] conf={r['confidence']:.2f} "
                f"evidence={r['evidence_count']} corrections={r['corrections']}"
            )
            print(f"    {r['statement']}")
    elif args.cmd == "brief":
        print(m.render_brief())
    elif args.cmd == "correct":
        try:
            doc = m.correct(args.id, args.correction)
        except KeyError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"corrected [{doc['id']}] -> confidence={doc['confidence']:.2f}")
    elif args.cmd == "affirm":
        try:
            doc = m.affirm(args.id)
        except KeyError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"affirmed [{doc['id']}] -> confidence={doc['confidence']:.2f}")
    elif args.cmd == "evidence":
        try:
            doc = m.note_evidence(args.id, args.note)
        except KeyError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(
            f"evidence logged for [{doc['id']}] "
            f"(count={doc['evidence_count']}, confidence={doc['confidence']:.2f})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
