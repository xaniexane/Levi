#!/usr/bin/env python3
"""Pomodoro focus timer.

Runs work/break cycles with a live countdown and appends each completed
session to a CSV log. Ctrl-C interrupts gracefully (partial session is
not logged).

Exit codes: 0 = all cycles completed, 130 = interrupted.
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime

DEFAULT_LOG = os.path.expanduser(
    "~/Ultimate-Automation-Suite/Productivity/focus.log")


def countdown(minutes, label):
    total = max(0, int(round(minutes * 60)))
    if total == 0:
        print(f"{label}: skipped (0 minutes)")
        return
    end = time.time() + total
    while True:
        remaining = int(end - time.time())
        if remaining <= 0:
            break
        print(f"\r{label}: {remaining // 60:02d}:{remaining % 60:02d} remaining",
              end="", flush=True)
        time.sleep(1)
    print(f"\r{label}: done{' ' * 30}")


def log_session(log_path, phase, minutes):
    new = not os.path.exists(log_path)
    with open(log_path, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["timestamp", "phase", "minutes"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), phase,
                    round(minutes, 3)])


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Pomodoro focus timer with session logging.")
    ap.add_argument("--work", type=float, default=25,
                    help="work minutes per cycle (default: 25)")
    ap.add_argument("--break", dest="break_mins", type=float, default=5,
                    help="break minutes between cycles (default: 5)")
    ap.add_argument("--cycles", type=int, default=4,
                    help="number of work cycles (default: 4)")
    ap.add_argument("--log", default=DEFAULT_LOG,
                    help="session log CSV path")
    args = ap.parse_args(argv)

    if args.work < 0 or args.break_mins < 0 or args.cycles < 1:
        print("error: --work/--break must be >= 0 and --cycles >= 1",
              file=sys.stderr)
        return 2

    print(f"focus timer: {args.cycles} x {args.work}min work / "
          f"{args.break_mins}min break")
    try:
        for cycle in range(1, args.cycles + 1):
            print(f"--- cycle {cycle}/{args.cycles}: WORK ---")
            countdown(args.work, "work")
            log_session(args.log, "work", args.work)
            if cycle < args.cycles:
                print(f"--- cycle {cycle}/{args.cycles}: BREAK ---")
                countdown(args.break_mins, "break")
                log_session(args.log, "break", args.break_mins)
    except KeyboardInterrupt:
        print("\ninterrupted. partial session not logged.")
        return 130
    print(f"all cycles complete. log: {args.log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
