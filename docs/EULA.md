# EULA Linter

LEVI reads the fine print so you don't have to squint at it. `core/levi/eula/`
is a rule-based, offline-first scanner that takes terms-of-service / EULA text
and flags hostile clauses **in plain language**.

## Why

Terms are written to be unreadable on purpose. The linter translates each
hostile pattern into what it actually means for the reader: *"You cannot sue
them in court"*, *"They sell your personal information"*, *"Once you pay, the
money is gone."* No legalese in, no legalese out.

## Usage

```bash
# from the repo root, with PYTHONPATH=core
python -m levi.eula lint --file terms.txt
python -m levi.eula lint --file terms.txt --format json
```

Or from Python:

```python
from levi.eula import lint, summarize

findings = lint(open("terms.txt").read())
print(summarize(findings))  # {"info": 1, "caution": 4, "hostile": 3}
for f in findings:
    print(f["severity"], f["title"])
    print(" ", f["plain_language_flag"])
    print(" ", f["clause_excerpt"])
```

## Output

Each finding carries:

- `rule_id` — stable machine name (e.g. `forced_arbitration`)
- `title` — short human label
- `severity` — one of `info` / `caution` / `hostile`
- `clause_excerpt` — the actual sentence from the terms that triggered the rule
- `plain_language_flag` — what the clause means in ordinary words
- `why_it_matters` — one sentence of context

Findings are sorted worst-first (hostile → caution → info).

## Rule coverage (17 rules)

**Hostile** — clauses that take rights away:
- `forced_arbitration` — no court, private arbitrator only
- `class_action_waiver` — cannot band together with other users
- `unilateral_modification` — they can rewrite the deal anytime; continued use = acceptance
- `data_resale` — your personal information is sold
- `perpetual_content_license` — your uploads stay licensed to them forever

**Caution** — clauses that shift risk onto you:
- `third_party_data_sharing`, `auto_renewal`, `price_change_anytime`,
  `unilateral_termination`, `no_refund`, `indemnification`,
  `liability_cap`, `warranty_disclaimer`, `data_retention`,
  `tracking_surveillance`

**Info** — neutral signals:
- `foreign_jurisdiction` — disputes decided under distant laws
- `effective_date` — positive signal; dated terms are trackable

Rules live in `core/levi/eula/rules.py` as plain data — add patterns without
touching the engine in `linter.py`.

## Design notes

- **Offline-first:** pure regex over stdlib `re`. No network, no models, no
  dependencies. It lints at `python -m` speed on any machine.
- **Excerpts, not black boxes:** every finding quotes the triggering sentence
  so the reader can verify it themselves.
- **Honest limits:** the linter flags *patterns*, not legal conclusions. It does
  not detect hostile terms phrased in novel ways, and it is not legal advice.
  When in doubt, it under-flags rather than over-flags — a clean scan means
  "no known patterns found", not "safe to sign".
- **Survivability:** the linter itself is a survivability catalog entry
  (`eula-linter` in `levi.survivability`) — zero dependencies by design.
