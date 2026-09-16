# LEVI Knowledge Pipeline

How offline knowledge enters LEVI's brain: tiers, the serial scheme,
curation rules, and the expansion pipeline. Knowledge here is
**literacy for the synthetic intelligence** — labeled
OBSERVED / INFERENCE / HYPOTHESIS, never a substitute for primary sources.

## Tiers

| Tier | Name | Shape | Example |
|---|---|---|---|
| L0 | Nano | One compact fact + method + pitfalls, single line | `KB-PROG-2026-A-0008-8` Big-O classes |
| L1–L9 | Derived | Built offline from L10 + nano (summaries, drills, cross-links) | generated, not authored |
| L10 | Canon | Full structured object (facts, principles, procedures, pitfalls, teaching outline) | `KB-PHYS-2026-A-0013-3` von Neumann entropy |

Nano is the ingest tier (fast, dense); L10 is the canon tier (complete,
reviewed). Middle layers are derived mechanically, never hand-written.

## Serial scheme

```
KB-<DOMAIN>-<YYYY>-<ALPHA>-<INSTANCE>-<CHECK>
```

- `DOMAIN`: PROG, MATH, PHYS, CHEM, BIO, LOGIC, REPAIR, ENG, ARCH, EVERY, LIFE, …
- `YYYY`: batch year. `ALPHA`: batch letter. `INSTANCE`: zero-padded counter.
- `CHECK`: check digit. Serials are never reused; contradiction with an
  existing serial blocks ingest.

## Curation rules (binding)

1. **Open sources only**: CC0, CC BY, CC BY-SA, public domain, or clearly
   open educational sources (BIPM, NIST, WHO, OpenStax, Wikipedia CC BY-SA, …).
2. **Never invent facts.** Uncertain → `verification_state: needs_review`,
   facts kept minimal.
3. **Zero duplication/contradiction** with existing serials (exclusion list
   per batch).
4. **Safety topics** (electrical, chemical, medical, first-aid, nutrition,
   structural) carry `EDUCATION ONLY` notes. Knowledge informs; it does not
   replace qualified professionals.
5. **No marketing language**, no closed-license paraphrase.
6. Every entry: `domain`, `title`, `summary`, `core_facts`, `principles`,
   `procedures`, `pitfalls`, `related_serials`, `pattern_tags`, `keywords`,
   `verification_state`, `source_type`, `language`.

## The expansion pipeline (adapted design)

The canon-expansion workflow, adapted from the Levi-ai knowledge design
reference (source-sync entry `levi-ai`):

1. **Author**: produce L10 objects in the exact block structure above,
   honoring the exclusion list and the open-sources-only rule.
2. **Curate**: check serials, dedupe, verify against the exclusion set;
   score the batch 0–100; GO / NO_GO.
3. **Derive**: offline jobs build L9–L0 layers from approved L10 + nano.
4. **Ingest**: entries land in `core/levi/brain/seed_*.py` as
   `(text, kind, tags)` tuples via `seed(limit)`; the brain corpus loads
   them with provenance (`source="seed_<name>"`).

## Organize-daemon rules

- One serial per fact-cluster; related entries link via `related_serials`.
- Tags are lowercase, hyphen-free keywords; every entry carries its tier
  tag (`nano`, `canon`) and batch tag (`stage1`, …).
- Batches append; they never rewrite history. Corrections are new
  entries that supersede, with the old serial noted.

## Current batches

- `seed_stage1` (`core/levi/brain/seed_stage1.py`): 23 nano + 2 quantum
  entries — standard textbook facts (complexity, hash tables, Newton,
  QEC, stoichiometry, logic, LOTO, composition, finance math, computer
  architecture, everyday knowledge, von Neumann entropy, qubits).
  Seed path: `levi brain --seed-stage1` (appends 25 units to the brain
  corpus with `source="seed_stage1"` provenance).
