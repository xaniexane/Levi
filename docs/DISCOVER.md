# DISCOVER — ritualized local discovery

## The giant pattern it inverts

Spotify's Discover Weekly is a ritual people love — but it runs on a
licensed catalog, optimizes for engagement, and steers you into a filter
bubble that serves the platform. The fallen-platforms thesis says the
abandoned agency-enhancing idea IS the feature.

**The remix:** a Discover-Weekly-style digest over your OWN library and
corpus — the Archive, memory exports, any JSONL source. No catalog
license needed. Serendipity is a designed mechanism, not an accident:

- **Seeded randomness** — picks are random by design (the seed is printed
  in the digest; default derives from the week label, so weeks are
  reproducible). Randomness is the point; nothing is engagement-ranked.
- **Anti-filter-bubble diversity rules** — per-kind caps, per-tag caps,
  and an outward bias toward *unseen* items. The opposite of
  collaborative filtering.
- **No-repeat memory** — items picked in the recent window are ineligible.

Every pick carries a `why this is here` line — honest about the
mechanism, never pretending to "know what you'll love".

## The ritual

```
python -m levi.discover init-sample          # starter corpus (labeled sample data)
python -m levi.discover discover --week      # this week's digest
python -m levi.discover discover --week 2026-W38 --source ~/my-corpus.jsonl
python -m levi.discover history --verbose
```

Digests are markdown files at `~/.levi/discover/digests/<week>.md` —
shareable as plain files, no account, no platform. Run it weekly (a cron
line, a Sunday habit — the ritual is yours).

## Item schema

JSONL, one object per line:

```json
{"id": "note-42", "title": "Repairing a 1987 keyboard", "kind": "note",
 "tags": ["repair", "hardware"], "added_at": "2026-06-01",
 "source": "archive", "blurb": "Bolt-modding buckling springs."}
```

Corrupt lines are skipped with a printed warning (never fatal); missing
`id`/`title` fails the line.

## Honest gaps

- "Unseen" means never picked by a digest — not never read by you. The
  ritual can't know what you've actually opened.
- Kind/tag diversity is syntactic (string equality), not semantic — two
  differently-tagged items about the same topic can both appear.
- Weekly cadence is by convention (the `--week` label); nothing schedules
  it for you yet — wire it to the daemon/heartbeat if you want it automatic.
- No feedback loop by design: liking a pick doesn't change future picks.
  That's the anti-engagement-steering guarantee, not a missing feature.
