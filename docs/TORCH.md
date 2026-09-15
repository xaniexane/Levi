# Pass the Torch — mentor bundles for a new LEVI

`levi torch` packages what this instance has learned into a **mentor
bundle** — a versioned JSON file a fresh LEVI instance can ingest as
seed. Passing the torch from a grown LEVI to a new one.

```
levi torch create [file]              # package a mentor bundle
levi torch read <file> [--yes]        # preview, then ingest as seed
levi torch sign <file> --by <name> [--note <text>]   # sign the founder's note
```

## Bundle format (`levi-torch`, version 1)

```json
{
  "format": "levi-torch",
  "version": 1,
  "created_at": "<utc iso>",
  "levi_version": "0.9.5",
  "sections": {
    "lifepack": { "...": "the real levi-lifepack export (identity+settings+durable memory)" },
    "curriculum": {
      "lesson_count": 33,
      "topics": ["Organism DNA", "..."],
      "provenance": {"chauncey": 16, "rex": 17},
      "lessons": [ {"id": "...", "topic": "...", "kind": "...", "text": "...", "taught_by": "..."} ]
    },
    "journal_highlights": [
      {"content": "...", "kinds": ["preference"], "corroborated_count": 7,
       "confidence": 0.9, "created_at": "..."}
    ],
    "model_card": {"current": "qwen3-0.6b", "cards": { "...": "lab MODEL_CARDS" }},
    "founders_note": {"note": "<template or signed text>", "signed_by": "", "signed_at": ""}
  }
}
```

**Deliberately not shipped**: secrets/credentials (the lifepack layer
strips them on export), playbook bodies, ephemeral memory, device
state. See `docs/LIFEPACK.md` for the lifepack layer's own rules.

## What a new instance gets

`levi torch read <file> --yes` follows Plan → Preview → Permission →
Execute (preview first; ingest only with `--yes`):

1. **Lifepack import** — identity, settings, durable memory. This
   *reuses* `levi.lifepack` (its preview/confirm discipline, its secret
   filters); nothing is reimplemented.
2. **Curriculum** — the founders' seed teachings load via the
   curriculum loader (`levi growth curriculum load`, idempotent), then
   the bundle's own lessons are consolidated as torch-taught seeds and
   stamped `taught-by: torch`. Lessons already present are corroborated,
   never duplicated.
3. **Learnings as provisional seed facts** — the source's top
   corroborated journal highlights enter with `status: provisional`
   and `taught-by: torch` provenance. Entries the lifepack already
   brought over are *stamped* (tagged `torch-seed`, provenance merged)
   rather than duplicated.
4. **Founder's note** — displayed at the end of ingest, and journaled
   (`kind: "torch-read"`) with what landed.

A clean HOME round-trips: create on the old instance, read into the new
one, and the new LEVI has the curriculum (quizzable via
`levi growth study run`), the learnings (provisional, torch-attributed),
and the founder's note.

## Signing

The bundle ships with an unsigned founder's-note template. Sign before
handing it over:

```
levi torch sign mentor.json --by "Chauncey" --note "Grow well, little one."
```

The note travels in the bundle; `read` prints it on ingest.

## Files

- `core/levi/torch/` — bundle build/read/validate/ingest/sign + `cmd_torch`
- `tests/test_torch.py` — hermetic create → read round-trip into a clean HOME
