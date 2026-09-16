"""CLI: python -m levi.perpetual pulse|hunt-plan|hunt-record|services

Run from the repo root with ``PYTHONPATH=core`` (or with the package
installed). All state lives under ``~/.levi/perpetual/``.

  pulse                          one-glance proof LEVI never stopped
  hunt-plan                      show the next planned hunt wave
  hunt-record <wave> <findings>   record a completed hunt (findings = JSONL
                                 of ArchiveRecord objects)
  services                       supervision status + crash counts
"""

from __future__ import annotations

import argparse
import json
import sys

from levi.archive.record import ArchiveRecord
from levi.perpetual import hunt, pulse as pulse_mod, supervise


def _home(args) -> str | None:
    return args.home


def cmd_pulse(args) -> int:
    snap = pulse_mod.read_pulse(home=_home(args))
    print(pulse_mod.format_pulse(snap))
    return 0


def cmd_hunt_plan(args) -> int:
    state = hunt.load_state(home=_home(args))
    plan = hunt.plan_next_hunt(state)
    print(plan.describe())
    # Persist the plan so hunt-record can find the wave later.
    existing = next((w for w in state.waves if w.id == plan.wave_id), None)
    if existing is None:
        from datetime import datetime, timezone
        state.waves.append(hunt.HuntWave(
            id=plan.wave_id, theme_id=plan.theme.id,
            planned_at=datetime.now(timezone.utc).isoformat(),
            status="planned",
            notes="deeper vein" if plan.deeper_vein else "",
        ))
        if not state.next_due:
            state.next_due = plan.due
        hunt.save_state(state, home=_home(args))
    return 0


def cmd_hunt_record(args) -> int:
    records = []
    with open(args.findings, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(ArchiveRecord.from_dict(json.loads(line)))
            except ValueError as exc:
                print("findings.jsonl line %d refused: %s" % (lineno, exc),
                      file=sys.stderr)
                return 2
    state = hunt.load_state(home=_home(args))
    try:
        result = hunt.record_hunt(state, args.wave_id, records,
                                  research_slug=args.slug, home=_home(args))
    except ValueError as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


def cmd_services(args) -> int:
    print(json.dumps(supervise.service_overview(home=_home(args)), indent=2))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="levi.perpetual")
    ap.add_argument("--home", default=None,
                    help="override HOME dir (tests/maintenance)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pulse")
    sub.add_parser("hunt-plan")
    rec = sub.add_parser("hunt-record")
    rec.add_argument("wave_id")
    rec.add_argument("findings", help="JSONL of ArchiveRecord objects")
    rec.add_argument("--slug", required=True, help="research_notes/<slug>")
    sub.add_parser("services")
    args = ap.parse_args(argv)
    return {
        "pulse": cmd_pulse,
        "hunt-plan": cmd_hunt_plan,
        "hunt-record": cmd_hunt_record,
        "services": cmd_services,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
