# The Site Lift — operator's guide

The Site Lift runs a website through five passes so it brings users in,
retains them, intrigues them, procures income, and leaves the site
feature-rich. Two kinds of checks:

- **Measured** — parsed from the site's actual HTML. Never fabricated.
  If the file doesn't contain it, the check fails honestly.
- **Attested** — recorded as performed-by with your notes. The module
  never auto-passes what it cannot measure.

## Quick start

Point it at a directory of the site's HTML files:

```bash
levi service lift ./my-site
```

Output: per-round scores, every failed check with its evidence, a
five-goal tally, and a report id. The report is saved to
`~/.levi/services/lifts/<report_id>.json`.

The five passes:

| pass   | name                  | kind     |
| ------ | --------------------- | -------- |
| round-1 | foundation lift      | measured |
| round-2 | feature lift         | measured |
| sig-a  | interpenetration       | attested |
| sig-b  | absorb / reverse / improve / return | attested |
| round-3 | crown lift           | measured + attested |

The crown round re-runs every foundation/feature check as a regression
and demands per-goal coverage: each goal must pass a threshold of its
measured checks (2, or 1 where only one measured check exists for that
goal).

## Attestations (signatures + showcase)

The measured rounds run on their own. The attested passes need your
word:

```bash
levi service lift ./my-site \
  --graft "sticky booking bar" --gsource "portfolio #12" --gnote "lifted conversions 18%" \
  --compost "autoplay hero video" --clesson "killed mobile load; never again" \
  --absorbed "top competitor booking flow" \
  --reversed "inverted steps: choose time before service" \
  --improved "one-tap rebook for returning clients" \
  --returned "a booking rail that reads like a concierge, not a form" \
  --unreplicable "cadence and copy are ours alone" \
  --showcase "The sharpest booking experience in town."
```

Skip an attestation and that pass fails honestly — the program never
invents one.

## From lift to crew

`--with-team` matches the report to a tailored team pack and assembles
the report+crew offer in one shot:

```bash
levi service lift ./my-site --with-team --pack restaurant
```

Or match a saved report later:

```bash
levi service teams <report-id> [--pack salon] [--no-quote] \
  [--giant-price 1200] [--strategy volume]
```

The Legion side consumes the same reports:

```bash
levi legion team --sitelift <report-id> --name "Sample Bistro" --type restaurant
```

Every failed measured check maps to the crew slot that closes it; the
`face` slot is always included. Unknown check ids are defensive-skipped
in the roster mapper and reported as unmapped in the Legion adapter —
never silently dropped. The quote is paper only (not a charge), via the
`--giant-price` anchor and `--strategy volume|margin`.

## Rules of the road

- A lift reads a **directory** of HTML. A missing directory is an
  error, not an empty site.
- Only `.html`/`.htm` files are parsed; everything else is ignored.
- Reports are JSON — inspect, diff, or re-run them any time with
  `levi.services.site_lift.load_report`.
- The attested passes are only as complete as the attestations you
  supply. When in doubt, the program fails the check and says so.
