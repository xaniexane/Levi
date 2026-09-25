# COMMITMENTS — Opt-In Commitment Devices

Snapchat's streaks are addiction engineering: loss-framed copy, paid
streak restores, mechanics tuned to keep you anxious and opening the app
for ad impressions. LEVI Commitments keeps the *mechanics* (they work)
and removes the *exploitation*.

## The deal

- **You define everything**: the habit, the target, per-day or per-week,
  rest days per week, mulligans (forgiven misses) per month.
- **Copy law** (binding, enforced by test): every user-facing string is
  neutral and descriptive. A missed day is "no check-in recorded for
  2026-09-14." — never shame, never loss-framed urgency. Pausing holds
  the streak; deleting ends it with zero penalty copy.
- **Mulligans are configured, not sold.** There is no store, no restore
  fee, no premium tier. The forgiveness budget is yours to set.
- **Local only**: `~/.levi/commitments/commitments.json`. No account, no
  leaderboard, no social pressure surface.

## Usage

```bash
python -m levi.commitments define read --target 20 --unit pages --per day \
    --rest-days 1 --mulligans 2 --start 2026-09-01
python -m levi.commitments checkin read --value 20
python -m levi.commitments mulligan read --day 2026-09-14
python -m levi.commitments status            # all commitments, neutral report
python -m levi.commitments pause read        # streak held, not broken
```

Rest days are the last N days of the week (Saturday/Sunday first) and
never break a streak. An in-progress today never breaks the streak
either — only a *completed* missed period does.

## What the giant refuses

- Forgiveness mechanics the user controls (theirs are monetized).
- Neutral copy (theirs is engineered anxiety).
- A habit tool with no engagement loop attached.

## Open gaps

- No reminders/notifications yet (a daemon automation could read the
  store and nudge — deliberately not bundled, so the mechanic never
  becomes a nag surface by default).
- Weekly commitments sum daily check-ins; custom period definitions
  (e.g. "3x per week minimum spacing") are not modeled.
