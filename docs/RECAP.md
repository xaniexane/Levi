# RECAP — Your Year, Computed On-Device

Spotify Wrapped is free advertising you make for Spotify: your data is
mined on their servers, packaged into shareable cards, and every share
recruits new users. The recap is the product; you are the ad surface.
LEVI Recap keeps the delight and removes the extraction.

## How it works

1. You keep a JSONL event file (one object per line):

```json
{"ts": "2026-03-14T09:30:00", "category": "reading", "kind": "session",
 "label": "Dune", "value": 45, "unit": "minutes"}
```

Required: `ts` (ISO-8601), `category`, `kind`. Optional: `label`,
`value` (default 1), `unit`.

2. `python -m levi.recap stats events.jsonl [--year 2026]` computes:
   totals, active days, longest daily streak, top categories by events
   and by value, busiest month/weekday, biggest day, per-category
   favorites, and milestones (first event, 100th, 500th…).

3. `python -m levi.recap html events.jsonl --out card.html` renders a
   standalone HTML card — inline CSS, zero external assets or requests.
   Share it anywhere; the data never traveled to make it.

4. `python -m levi.recap sample` generates a deterministic *synthetic*
   year (labeled synthetic in the file) for demos and tests.

## What the giant refuses

- A recap with no telemetry and no account.
- Cards that aren't a growth loop for their platform.
- Honest "your data never left" as an architectural fact, not a
  privacy-policy paragraph.

## Open gaps

- No automatic event capture yet — the event file is yours to write
  (commitments check-ins, feedreader reads, and daemon automations are
  natural future sources; a `recap collect` could aggregate them).
- The HTML card is one layout; more card designs are easy additions.
