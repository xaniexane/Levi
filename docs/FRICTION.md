# FRICTION — the friction log

**Purpose.** One-tap capture of annoyances; a weekly review that
groups them into themes; promotion of themes into real system fixes.
This is the discovery half of the Waymaker law: *where there isn't a
way, LEVI creates one* — and the friction log is where the need for
a way is first noticed.

**Why it exists.** Small annoyances are individually ignorable and
collectively expensive. People don't file tickets for "deploy asks
for my password twice"; they just sigh, twice a day, forever. The
log makes sighing cheap to record and expensive to ignore: capture
takes under a second, and the weekly review turns repetition into
a candidate fix with a count attached.

## Honesty contract

- Grouping is **simple keyword stemming**, documented as such. It
  does not pretend to understand semantics. ("deploy" and
  "deployment" share a stem; "the server is slow" and "latency is
  high" do not group, and the log says so by leaving them alone.)
- Items that share no stem with anything else stay **"ungrouped"** —
  honestly alone, never forced into a theme to make the review look
  tidy. A stem appearing in *every* entry is treated as noise, not a
  theme.
- A candidate is not a fix. Only `promote_to_fix()` with a written,
  non-empty fix note moves an item to the fixes log. "Fixed it" is
  rejected as an explanation.
- Dropping a candidate is recorded, not deleted: the log remembers
  what was considered and declined.

## API

```python
from levi.friction.log import FrictionLog

log = FrictionLog()  # $LEVI_HOME/friction/log.json (else ~/.levi)

e = log.capture("deploy keeps asking for the password twice")  # fast
log.entries(since_days=7)

review = log.weekly_review(since_days=7)  # or weekly_review(min_group=2)
# {"window_days": 7, "n_entries": 5,
#  "candidates": [{"id": "fx-…", "theme": "deploy", "count": 3,
#                  "entry_ids": [...], "examples": [...],
#                  "status": "candidate"}, ...],
#  "ungrouped": [ ... ],   # honestly ungrouped, never forced
#  "note": "2 candidate fix(es); 1 item(s) honestly ungrouped"}

fix = log.promote_to_fix("fx-1a2b3c4d", fix_note="cache the deploy token in the vault")
log.drop_candidate("fx-9z8y7x6w")  # decline, recorded
log.fixes()  # converted fixes log
```

`capture("")` raises `ValueError`. `promote_to_fix` raises
`ValueError` on an empty fix note or an already-decided candidate,
`KeyError` on an unknown id.

## CLI

```bash
python -m levi.friction capture "the linter is slow on save"
python -m levi.friction list [--days 7]
python -m levi.friction review [--days 7] [--json]
python -m levi.friction promote fx-1a2b3c4d --fix-note "cache the deploy token"
python -m levi.friction fixes
```

## Suggested instinct specs

```yaml
# Weekly: if friction was captured, run the review and present candidates.
- id: instinct.friction_review
  fires_on: friction.captured>=3
  cooldown: 604800        # weekly
  max_grade: NOTE
  does: run weekly_review(); list candidates with counts; ask which to promote

# If unpromoted candidates pile up, escalate from nudge to ask.
- id: instinct.friction_backlog
  fires_on: friction.candidates_open>=5
  cooldown: 604800
  max_grade: ASK
  does: list open candidates oldest-first; ask for promote/drop decisions
```

**Storage:** `$LEVI_HOME/friction/log.json` (else `~/.levi`).
**Deps:** stdlib only.
