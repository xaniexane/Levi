"""Symbiote nudge — "you were working on X, want to continue?"

Reads the dream journal's recent seeds and surfaces the freshest
unfinished thread. A nudge is a suggestion, never an action.
"""

from __future__ import annotations


from levi.dream.journal import DreamJournal


def nudge(journal: DreamJournal | None = None) -> str:
    journal = journal or DreamJournal()
    recent = journal.recent(5)
    if not recent:
        return "Nothing to nudge — no dreams on record yet."
    # freshest dream with a surviving lesson wins
    for entry in reversed(recent):
        lesson = entry.get("lesson")
        if lesson:
            return f"You were dreaming on this: {lesson[:120]}… — want to continue?"
        seed = entry.get("seed", {})
        text = str(seed.get("text", ""))[:100]
        if text:
            return f"Last thread: '{text}…' — want to pick it back up?"
    return "Nothing to nudge — no dreams on record yet."
