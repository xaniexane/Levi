# Learning Sync — LEVI's collective learning, distribution half

The growth loop learns. This is how what one LEVI learns reaches every
other LEVI — batched, versioned, and privacy-gated. Not telepathy:
**updates**.

## The full loop

```
harvest (consent-gated, per key)
  → redact (secrets/PII scrubbed before reflection)
  → reflect (technique-only distillation; cloud content never reaches models)
  → consolidate (learnings → memory, marked shareable or not)
  → PACK (this doc: aggregate shareable learnings into versioned packs)
  → cloud transport (GET /v1/learning/packs/latest, authed)
  → INGEST (verify hash + version ordering, dedupe, merge)
```

Harvest → consolidate is `core/levi/growth/` (`docs/GROWTH.md`).
Pack → ingest is `core/levi/growth/sync.py`.

## The privacy line (binding)

**Only technique travels.** A pack entry is a procedural "when X, do Y"
statement plus aggregate counts. The following are HARD EXCLUDED —
once at consolidation (the `shareable` mark) and again at pack build
(independent re-verification):

- personal facts ("user asked Levi to remember …")
- preferences ("user prefers …")
- corrections (they quote the user's speech)
- verbatim session text of any kind
- anything user-identifiable: key names, user ids, session ids, emails,
  phones, secrets — packs carry only `corroborated_sources` (int) and
  `source_types` (`{"cloud": n, "local": n}`)

Two more structural guarantees:

- **No echo chamber.** Ingested learnings are marked `shareable=False`
  and tagged `collective`. The collective never re-packs what it
  received, so corroboration counts can't inflate by circulating.
- **Consent on both ends.** Contributing is opt-in: cloud-distilled
  learnings pack by default (consent was verified at key creation,
  content redacted pre-reflection); the owner's own local learnings
  pack only with `LEVI_GROWTH_CONTRIBUTE=1`. Receiving is on with
  opt-out: `LEVI_GROWTH_RECEIVE=0` disables ingest.

## Versioning and integrity

- Packs: `learning-pack-<N>.json`, format `levi-learning-pack/1`,
  monotonic integer versions, stored at
  `~/.levi/cloud/learning_packs/` (the publisher's cloud dir).
- Manifest: `manifest.json` pins the pack's SHA-256, computed over the
  **canonical JSON** (sorted keys, compact separators) so publisher and
  receiver agree byte-for-byte.
- Ingest rejects: hash mismatch (tampered), unknown format, non-newer
  version (stale/downgrade), entries that fail the identifier scan.
- Installed packs are recorded at
  `~/.levi/growth/installed_packs.json`; `levi growth pack --pack-list`
  shows them. Pack builds and ingests are journaled in the baby book.

## CLI

- `levi growth pack --build [--min-corroboration N]` — build the next
  versioned pack from shareable learnings. Prints what packed and why
  each excluded learning stayed home.
- `levi growth pack --ingest FILE` — ingest a pack file (offline
  fallback; a sibling `manifest.json` is verified when present).
- `levi growth pack --sync [--server URL] [--api-key KEY]` — pull the
  latest pack from the cloud server and ingest it. Defaults:
  `LEVI_CLOUD_SERVER` / `http://127.0.0.1:8765`,
  `LEVI_API_KEY` / `LEVI_AGENT_TOKEN`.
- `levi growth pack` / `--pack-list` — installed packs.

## Cloud transport

`GET /v1/learning/packs/latest` on the agent server (the same stdlib
server that serves `/v1/agent/*`): requires auth (owner token or API
key, same as every `/v1/` route), metered like other endpoints, returns
`{"manifest": …, "pack": …}` or `{"manifest": null, "pack": null}` when
nothing is published yet. File-based ingest remains the offline path —
no server required.

## Honest limits

- **Aggregation is only as good as the harvest heuristics.** The
  "good outcome" signals (engagement, approval, no corrections) are
  heuristics, not truth. A pack can enshrine a technique that merely
  *looked* successful.
- **Technique-level, not skill-level.** Packs carry "when X, do Y"
  heuristics — they do not transfer capabilities, tools, or model
  weights. A receiving instance still needs a competent provider to
  execute the technique well.
- **Regex redaction is best-effort.** The identifier scan at pack build
  is a second net, not a proof of absence. Unusual phrasings of secrets
  or PII can slip both nets; the design minimizes exposure, it does not
  eliminate it.
- **Corroboration counts are counts, not identities.** "3 independent
  sources" means 3 learnings clustered as near-duplicates — the
  clustering itself is Jaccard ≥ 0.5, a heuristic.
- **Single-machine publisher.** Pack building runs on the publisher's
  machine; there is no multi-publisher merge or conflict resolution
  yet. One publisher per cloud.
