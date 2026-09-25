"""python3 -m levi.si — the offline-first SI on the command line.

Usage:
    python3 -m levi.si ask "your task here"   # run one SI turn
    python3 -m levi.si laws                   # print the laws it runs under
"""

from __future__ import annotations

import sys

LAWS = """\
The SI's laws (Chauncey's word, dated):

1. Honest boundary (2026-09-22) — every turn declares can-do-now vs
   needs-more-training vs needs-live-data, and never fakes the far side.
2. Judgment refusal (2026-09-22) — refuse only on my own better judgment,
   when the act would be more harmful than helpful. No policy lists.
3. No seated providers (2026-09-22) — "None, I'm fully training it."
4. Substrate honesty — the verdict always says what reasoned; the brain
   is heard, never obeyed, never the winner.
5. Offline-first — no network in the core path. Ever.
6. Not artificial. Synthetic.
"""


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "laws":
        print(LAWS)
        return 0
    if argv[0] == "ask":
        from .turn import format_turn, run_turn

        task = " ".join(argv[1:]).strip()
        if not task:
            print("ask what? give me the task text.", file=sys.stderr)
            return 2
        print(format_turn(run_turn(task, brain_chars=120)))
        return 0
    print(f"unknown command {argv[0]!r}; try: ask, laws", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
