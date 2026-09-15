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
```

Run `levi growth cycle` on a schedule (cron, systemd timer) for
continuous development — e.g. nightly.

## Developmental stages

A light, honest label for how far Levi has grown — a pure function of
consolidated learnings (engagement copy, not a cognitive claim):

| learnings | stage |
|-----------|-------|
| 0 | newborn |
| 1+ | sprout |
| 10+ | curious |
| 30+ | growing |
| 100+ | maturing |

## Safety rails (binding)

- **Write scope**: growth READS sessions/automations and WRITES ONLY
  to growth-tagged memory entries and the journal. It never touches
  tools, policy, identity, the charter, or any other subsystem.
- **Provisional by default**: every learning carries `source="growth"`,
  tags `["growth", "levi-learned", kind]`, provenance metadata, and
  `status: provisional`. Self-taught beliefs are always marked as such.
- **No inner life, ever**: reflection is forbidden from producing
  claims of subjective experience, sentience, or consciousness — the
  model prompt enforces it; the rule engine cannot produce such claims
  by construction. LEVI remains honest Synthetic Intelligence.
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

- `core/levi/growth/` — experience, reflect, consolidate, journal, cycle
- `~/.levi/growth/` — `state.json` (watermarks), `journal.jsonl`
- `~/.levi/memory/` — consolidated learnings (tagged `growth`)
- `tests/test_growth.py` — 18 hermetic tests
