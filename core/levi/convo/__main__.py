"""thread-sense CLI: ``python -m levi.convo demo`` | ``state <session.jsonl>``.

* ``demo`` — a scripted multi-turn conversation. After every turn the
  conversation constellation is printed: watch threads ignite, decay, and
  reignite; pronouns resolve; a promise opens a loop and closes when kept;
  the immune sense flags a contradiction; semantic recall reaches back to
  an early turn instead of reciting the last N.
* ``state`` — read a JSONL session file (``{"speaker": …, "text": …}``
  or ``{"role": …, "text": …}`` per line) and print the constellation.
"""

from __future__ import annotations

import json
import sys

from levi.convo.state import DialogueState
from levi.convo.recall import recall_turns
from levi.convo.guard import check_contradictions
from levi.convo.render import render_block, render_constellation

_DEMO_TURNS = [
    ("user", "I'm migrating our server this weekend, Nginx needs reconfiguring"),
    ("levi", "Got it — the Nginx migration is on my radar. I'll check the drive space before the weekend."),
    ("user", "Also I need a backup plan for the postgres database"),
    ("levi", "For postgres, nightly pg_dump to the backup drive works well."),
    ("user", "back to the server thing — restart it after the config change"),
    ("levi", "Drive space is fine — 42GB free, the migration can proceed."),
    ("user", "does Nginx run on 8080?"),
    ("levi", "Yes — Nginx runs on port 8080."),
    ("user", "what did we decide about postgres?"),
]


def _run_demo() -> int:
    state = DialogueState()
    for speaker, text in _DEMO_TURNS:
        changed = state.update(speaker, text)
        print("┌─ turn %d · %s" % (changed["turn"], speaker))
        print("│  %s" % text)
        print(render_constellation(state))

        # semantic recall: what does *this* turn reach back to?
        if changed["turn"] >= 4:
            recalled = recall_turns(text, state.turns, limit=2)
            if recalled:
                print("  ↩ recall reaches back:")
                for idx, score, _why in recalled:
                    snippet = state.turns[idx]["text"][:80]
                    print('    [t%d r=%.2f] "%s…"' % (idx, score, snippet))

        # immune sense on LEVI's own replies
        if speaker == "levi":
            findings = check_contradictions(text, state.facts[:-1])
            for f in findings:
                print("  ⚠ immune sense: %s" % f["type"])
                print('    reply: "%s"' % f["reply"])
                print('    vs t%d: "%s"' % (f["fact_turn"], f["fact"]))
        print()

    # one deliberate contradiction to show the immune sense firing
    bad = "No — Nginx runs on port 9090."
    findings = check_contradictions(bad, state.facts)
    print("┌─ immune-sense probe")
    print("│  %s" % bad)
    for f in findings:
        print("│  ⚠ flagged: %s (established t%s)" % (f["type"], f["fact_turn"]))
        print('│    vs: "%s"' % f["fact"])
    print()
    print("prompt block the agent would receive:")
    print(render_block(state, recall_turns("postgres", state.turns, limit=2)))
    return 0


def _run_state(path: str) -> int:
    state = DialogueState()
    n = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            speaker = obj.get("speaker") or obj.get("role") or "user"
            text = obj.get("text") or obj.get("content") or ""
            if text:
                state.update(speaker, text)
                n += 1
    print("ingested %d turns from %s" % (n, path))
    print(render_constellation(state))
    print()
    print(render_block(state))
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(__doc__.strip())
        return 0
    if argv[0] == "demo":
        return _run_demo()
    if argv[0] == "state" and len(argv) == 2:
        return _run_state(argv[1])
    print("usage: python -m levi.convo demo | python -m levi.convo state <session.jsonl>",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
