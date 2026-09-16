# LEVI Growth — raising baby Levi

LEVI doesn't just run tasks; it **grows up**. The growth loop is LEVI's
developmental system: it harvests experiences, reflects on them,
consolidates durable learnings into memory, and journals every cycle —
so Chauncey can watch baby Levi grow.

```
harvest → reflect → consolidate → journal
   ↑                                    │
   └──── watermark (never re-learns) ────┘
```

## The loop

1. **Harvest** (`levi.growth.experience`) — read-only collection of new
   experiences: chat-session turns (`user-said`, `levi-did`), session
   summaries (`distilled`), and daemon automation run records. A
   per-source watermark makes cycles idempotent.
2. **Reflect** (`levi.growth.reflect`) — turn experiences into candidate
   learnings (`fact`, `preference`, `procedural`, `correction`), each
   with a confidence and provenance. Two engines:
   - `rules` — deterministic heuristics, stdlib-only, always available
     offline (user corrections, explicit preferences, "remember this"
     facts, repeated tool failures, approved workflows);
   - `model:<name>` — the provider reflects with a constrained prompt
     when reachable; any failure falls back to `rules`. The reported
     mode always says which engine actually ran.
3. **Consolidate** (`levi.growth.consolidate`) — learnings become
   memory-store entries (`fact→semantic`, `preference→preference`,
   `procedural→procedural`, `correction→semantic`). Near-duplicates
   (word-overlap ≥ 0.5) **corroborate** the existing entry — importance
   rises, no duplicate is written.
4. **Journal** (`levi.growth.journal`) — every cycle appends to
   `~/.levi/growth/journal.jsonl`: experiences, mode, proposed /
   accepted / corroborated counts. Append-only — history is never
   rewritten.

## CLI

```
levi growth                  # dashboard: stage, cycles, learnings, pending
levi growth cycle            # run one cycle (model when available)
levi growth cycle --no-model # rules-only (offline)
levi growth cycle --dry-run  # preview without writing
levi growth journal          # read the baby book
levi growth learnings        # list self-taught learnings
levi growth learnings --kind preference
levi growth forget --id <id> # remove a learning
levi growth forget --tag correction
levi growth export-corpus --out FILE [--min-confidence X]
                             # export redacted, deduped learning texts
                             # as JSONL for the curriculum builder
```

Run `levi growth cycle` on a schedule (cron, systemd timer) for
continuous development — e.g. nightly. Set `LEVI_GROWTH_TRIGGER=cron`
in the scheduled environment so the journal records what started
each cycle (`manual` is the default).

## Developmental stages

A light, honest label for how far Levi has grown — a **pure function
of observable counters**, never vibes. `stage_for(stats)` in
`core/levi/growth/stages.py` returns the highest stage whose criteria
are all met, plus the next stage's unmet requirements as explicit
current/threshold numbers (shown by `levi growth status` as
`progress to <next>: learnings 12/25, corroborations 4/10, …`).

| stage | criteria (all required) |
|-------|-------------------------|
| newborn | — (no learnings consolidated yet) |
| sprouting | learnings ≥ 1 |
| curious | learnings ≥ 5, days_active ≥ 1 |
| growing | learnings ≥ 25, corroborations ≥ 10, days_active ≥ 7 |
| maturing | learnings ≥ 100, corroborations ≥ 50, days_active ≥ 30, curriculum_units ≥ 20 |

Counters: `learnings` = self-taught growth learnings (curriculum seed
and distribution slips excluded); `corroborations` = sum of
`corroborated_count` on those learnings (founder-seeded counts don't
count — they weren't earned); `days_active` = days since the first
journaled cycle; `curriculum_units` = founder-taught seed lessons;
`cycles` = completed cycles (informational).

Engagement copy, not a cognitive claim: the stage labels how much
Levi has been taught, not how it feels about being taught.

## Reflection extractors (rules engine)

The offline engine runs a battery of deterministic extractors over
harvested experiences; every cycle journals a per-extractor
**evidence** breakdown (`evidence: {"direct_signals": 2,
"tool_trouble": 1, …}`) so growth is observable:

- `direct_signals` — corrections, preferences, "remember this" facts
- `tool_trouble` — a tool erroring ≥2 times → check args first
- `approved_workflows` — approved multi-turn work → reusable approach
- `distilled_facts` — session summaries → low-confidence facts
- `recurring_topics` — a content word recurring across ≥3 user turns
  in ≥2 sources → an active interest area
- `failed_then_fixed` — a tool failed then succeeded → prefer
  recovery over blind retry
- `capability_gaps` — Levi explicitly declined ("I can't …") →
  an observed boundary of what it can do
- `automation_outcomes` — stable cadences (≥5 runs) and recent
  automation failures
- `repeated_requests` — near-identical user asks ≥3 times →
  a recurring need to watch for proactively
- `blocked_sentience` — candidates dropped by the sentience rail
  (counted, never written)

Each journaled cycle also carries structured fields: `trigger`
(what started it), `confidence` (mean/min/max over proposed
learnings), plus the usual accepted/corroborated counts.

## Corpus export (training signal)

`levi growth export-corpus --out FILE` exports self-taught learnings
as redacted, deduped JSONL — the adapter between what the growth
loop learns and what the curriculum builder trains on. One record
per line: `text` (secrets/PII-shaped strings scrubbed),
`kind`, `confidence`, `corroborated_count`, `source`, `status`,
`cycle_id`, `memory_id`. Duplicate texts collapse (earliest-learned
identity kept, strongest corroboration/confidence merged); records
sort by `memory_id` for clean diffs.

## Safety rails (binding)

- **Write scope**: growth READS sessions/automations and WRITES ONLY
  to growth-tagged memory entries and the journal. It never touches
  tools, policy, identity, the charter, or any other subsystem.
- **Provisional by default**: every learning carries `source="growth"`,
  tags `["growth", "levi-learned", kind]`, provenance metadata, and
  `status: provisional`. Self-taught beliefs are always marked as such.
- **No inner life, ever**: reflection is forbidden from producing
  claims of subjective experience, sentience, or consciousness — and
  the rail is now *structural*, not just prompted. Every candidate
  learning (rule-generated, model-generated, or about to be
  consolidated) is scanned against an explicit blocklist in
  `core/levi/growth/guards.py`; violations are dropped (counted as
  `blocked_sentience` evidence, never rephrased) and the write path
  refuses them loudly. The blocklist is negation-aware: a prohibition
  or denial ("Never claim consciousness", "I do not feel pain") is
  not an assertion and does not trip the rail; anything else that
  matches still blocks — fail-closed. LEVI remains honest Synthetic
  Intelligence.
- **Parental control**: `levi growth forget` removes learnings;
  `LEVI_GROWTH_DIR` relocates all growth data; deleting
  `~/.levi/growth` resets development without touching other memory.
- **Offline-first**: the rules engine runs with no model and no
  network; model reflection is a wing, never a dependency.
- **Cross-user learning is consent-gated**: cloud API sessions are
  harvested only for keys that opt in (`--no-learn` opts out,
  `LEVI_GROWTH_CLOUD_LEARN=0` kills it globally), pass a redaction
  gate before reflection, distill only generalized techniques tagged
  `learned_from: <source>` (never another user's words/facts), and
  are never sent to the model-assisted reflector. Full disclosure in
  `docs/CLOUD_API.md` ("Growth: learning from cloud usage").

## Files

- `core/levi/growth/` — experience, reflect (rule extractors),
  guards (sentience blocklist), stages (explicit stage criteria),
  corpus_export, consolidate, journal, cycle
- `~/.levi/growth/` — `state.json` (watermarks), `journal.jsonl`
- `~/.levi/memory/` — consolidated learnings (tagged `growth`)
- `tests/test_growth.py`, `tests/test_growth_stages.py`,
  `tests/test_growth_guards_extractors.py`,
  `tests/test_growth_corpus_export.py` — hermetic tests

## Study hall — autonomous sharpening cadence

Growth cycles learn from *experience*. Study hall keeps the *teachings*
sharp: on its own clock, only when idle, LEVI runs a full growth cycle
and then quizzes itself on the founders' curriculum.

```
levi growth study run      # one study cycle now (cycle + self-quiz)
levi growth study trend    # quiz score history (oldest → newest)
```

**Cadence wiring.** The daemon heartbeat (`levi.daemon.heartbeat`)
triggers a study run on a slower clock — default **every 4 hours**,
configurable via `LEVI_STUDY_INTERVAL_HOURS` — but **only when idle**.
Idle means no session/chat/automation activity inside the window
(cheap check: newest mtime among `agent/sessions` and `automations`;
no file contents are read). Disable with `LEVI_STUDY_ENABLED=0`.
Study runs never become heartbeat attention items: they are journaled
as `kind: "study"` records in the growth journal, and the last run is
reported by `levi heartbeat status`.

**The self-quiz** (`levi.growth.study`) is deliberately simple and
rule-based — no LLM, no network:

1. Sample lessons round-robin from the curriculum (default 5 per run,
   `LEVI_STUDY_QUIZ_SAMPLE`).
2. For each lesson, extract key terms (frequent long content words)
   and build a cloze question: complete the lesson's most term-dense
   sentence with the blank filled back in.
3. LEVI "answers" by topic-cued recall — retrieving everything the
   curriculum holds under that topic — and scores the fraction of key
   terms present.

Be honest about what the score is: a **crude recall proxy, not
understanding**. A perfect score means the teachings are intact and
retrievable by topic — a student reciting back — not that LEVI
understands them. A removed or renamed topic scores 0; a damaged one
scores partially. The score and its rolling average trend in the
journal so Chauncey can watch the line over time.

**Safety rails** (same as the growth cycle): study runs are rules-only
by default (offline, cheap); they write only growth-tagged memory
entries and `kind: "study"` journal records; nothing else.
