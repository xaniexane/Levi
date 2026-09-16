# The LEVI Archive — the Smithsonian Module

> "Like Smithsonian became an archive."

LEVI is an apex predator of forgotten tricks, dead software, and buried
methods. The Archive is its **trophy room**: the permanent, curated,
growing collection of everything the hunts bring back — preserved with
provenance, searchable forever. It never closes and never stops growing.

## What lives here

One `ArchiveRecord` per find:

| Field | Meaning |
|---|---|
| `id` | Deterministic: `arch-<report>-<kind>-<title-slug>[-<era-slug>]` |
| `title` / `era` | What it was called, when it lived |
| `kind` | `software` · `method` · `technique` |
| `summary` | The exhibit placard — what it was, in the researcher's words |
| `mechanism` | The ahead-of-its-time mechanism (the load-bearing part) |
| `decline` | The real cause of death/decline (not the myth) |
| `revival_recipe` | How to revive it paired with a modern capability |
| `levi_application` | One concrete local-first AI application |
| `sources` | Research source links (may be empty — see honesty note) |
| `rating` | `load-bearing` · `useful-pattern` · `inspirational` · `unrated` |
| `status` | `dead` · `alive-underused` · `preserved` · `absorbed` · `technique-alive` |
| `skepticism` | Disputed/romanticized history flags — skepticism is first-class |
| `provenance` | `found_date`, `research_slug`, researcher notes (verification basis) |

Validation is strict and deny-closed: a malformed record is refused,
never half-stored. `store.add()` refuses duplicate ids — a conflicting
find gets its own record with its own provenance. **Conflicts coexist;
nothing is silently merged or overwritten.**

## The wings (collections)

Curated groupings, defined by deterministic keyword rules so every
admission is explainable (`collections <wing>` lists the keywords that
admitted each record):

- `memory-arts` — palaces, commonplaces, card systems
- `hypertext` — linking and trails before and beyond the web
- `offline-first` — sync, replication, namespaces assuming disconnection
- `ai-lineage` — expert systems, cognitive architectures, planners
- `analytical-craft` — competing hypotheses, morphological boxes, grids
- `operating-systems` — dead and sidelined OSes and their ideas
- `dead-languages` — programming languages ahead of their time
- `productivity` — dead ways of organizing work
- `communication` — codes, prowords, compression before the internet
- `verification` — how the careful got things right

## CLI

```
python -m levi.archive ingest [--research-root DIR] [--slug SLUG]
python -m levi.archive search <query> [--kind --rating --status --era --limit --json]
python -m levi.archive show <id> [--json]
python -m levi.archive collections [wing]
python -m levi.archive stats
```

State lives at `~/.levi/archive/` (`records.jsonl` + `index.json`),
atomic writes, owner-only permissions.

## Growth convention — the standing rule

**Every research hunt flows into the Archive.** When a hunt finishes:

1. Its report lands at `research_notes/<slug>/report.md` (read-only input —
   the Archive never modifies reports).
2. Run `python -m levi.archive ingest --slug <slug>`.
3. If the report follows one of the three known heading conventions
   (`### N.` bullets, `## N.` numbered fields, `## N.` labeled paragraphs),
   it ingests unchanged. If it uses a new format, add a parser to
   `core/levi/archive/ingest.py` and register it in `REPORTS` — never
   hand-edit records to fit.
4. Verify counts (`stats`), spot-check a record (`show <id>`), commit.

This is the perpetual directive made concrete: LEVI never stops hunting,
and everything it catches is preserved. The Archive is how "everything"
becomes permanent.

## Honesty notes

- The first software batch (30) carries no per-entry source URLs — the
  report didn't include them. Records say so in provenance rather than
  inventing links.
- Status badges for that batch are heuristic (keyword scan for "still
  alive", "absorbed", etc.); each was spot-checked against the report text.
- All research is index-sourced, not live-verified — provenance records
  the verification basis so future curators know what to re-check.
- Wing keywords use word-boundary matching (`ach` ≠ `each`); a wing is a
  lens, not a taxonomy — records may belong to several.
