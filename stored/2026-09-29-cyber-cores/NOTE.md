# 2026-09-29 recipe-skills: cyber batch-3 compressed to 50 threat cores

## What happened (Chauncey's ruling, 2026-09-29)

The 100,000 combinatorial cyber playbooks (`b3-<threat>-<asset>-<env>-<tier>.md`,
50 threats x 40 assets x 10 envs x 5 maturity tiers) were COMPRESSED to 50
threat-core playbooks (`core-<threat>.md`), per Chauncey's signature recipe:
CURATE (dedupe) -> CONTROLLED COMPRESSION -> pi-digit lottery audit.

Verdict that drove this: the 100k were ~94% pairwise text-similar
multiplication-table volume, not 100,000 independent pieces of knowledge.
Nothing is deleted: all 100,000 files live here in `variants/`.

## What replaced them

`core/levi/skill/playbooks/cyber/core-<slug>.md` (50 files) built by
`core/levi/skill/cyber_gen/build_cores.py`. Each core carries the scenario's
full defensive content (threat intel, detection signals, analysis, hardening,
pitfalls, MITRE) plus an adaptation matrix condensing the 40 asset types, 10
environments, and 5 maturity tiers into applicable guidance.

Coverage proof: pi-digit lottery selected one deterministic b3 sample per
scenario (50/50) and every core was verified to cover its scenario's
variants (see build_cores.py `main`).

## The 823 originals

Untouched. They remain the curated base in `core/levi/skill/playbooks/cyber/`.

## Regeneration

To restore the full 100,000 variants exactly as they were:

    python3 core/levi/skill/cyber_gen/generate.py

The generator is deterministic (seeded, asserted 50x40x10x5 = 100,000).
Then rebuild the loader manifest:

    python3 core/levi/skill/cyber_gen/build_index.py

## Contents here

- `variants/` — all 100,000 original b3-*.md files, byte-identical.
- `NOTE.md` — this file.
