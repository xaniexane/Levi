"""LEVI Commitments — opt-in commitment devices, minus the guilt.

REMIX DELTA: Snapchat's streaks are addiction engineering: loss-framed
copy ("you'll lose your streak!"), paid streak restores, and mechanics
designed to keep you anxious and engaged for ad impressions. LEVI
inverts it: the *same* streak mechanics (check-ins, targets, rest days,
forgiveness) but the user configures every rule, all copy is neutral
and descriptive (see the COPY LAW in commitments.py — no shaming
anywhere), mulligans are configured not sold, and everything lives in a
local JSON file. The giant monetizes your anxiety about the streak; here
the streak is a tool you own, including the right to pause or delete it
with zero penalty copy.

What it adds that the giant refuses: user-configured forgiveness rules,
honest neutral feedback, and mechanics with no monetization hook.
"""

from __future__ import annotations

SHELF = {
    "name": "commitments",
    "summary": (
        "Opt-in commitment devices: user-defined habits with user-set "
        "targets, check-ins, streak counting with configured rest days "
        "and mulligans, neutral copy (no guilt engineering), local store."
    ),
    "items": [
        {
            "id": "habit-define",
            "kind": "command",
            "summary": "Define a habit: target, per-day/week, rest days, mulligans.",
            "invoke": "python -m levi.commitments define NAME [--target N] [--per day|week]",
        },
        {
            "id": "habit-checkin",
            "kind": "command",
            "summary": "Record a check-in (value accumulates for the day).",
            "invoke": "python -m levi.commitments checkin NAME [--value N] [--day YYYY-MM-DD]",
        },
        {
            "id": "habit-mulligan",
            "kind": "command",
            "summary": "Forgive a missed day with a configured mulligan.",
            "invoke": "python -m levi.commitments mulligan NAME [--day YYYY-MM-DD]",
        },
        {
            "id": "habit-status",
            "kind": "command",
            "summary": "Streak, longest run, hit rate, missed periods — neutral report.",
            "invoke": "python -m levi.commitments status [NAME]",
        },
        {
            "id": "habit-pause",
            "kind": "command",
            "summary": "Pause (streak held, not broken) or resume a commitment.",
            "invoke": "python -m levi.commitments pause NAME | resume NAME",
        },
    ],
}
