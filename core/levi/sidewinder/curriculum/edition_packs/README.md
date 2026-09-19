# Edition packs — authoring guide

An **edition** is a named, manifest-driven curriculum pack for a career
field or audience: a selector over the corpus, track emphasis, and
optional pack-specific entries. **First Responder** (`first-responder.json`)
ships first; Chauncey authors the rest. Packs are declarative — no code
changes to add one.

## The manifest

Copy `_template.json` to `<pack-id>.json` (file name must match the pack
`id`). Fields:

| key | required | meaning |
|---|---|---|
| `id` | yes | lowercase slug, e.g. `plumbing-pro` |
| `name` | yes | display name, e.g. `Plumbing Pro` |
| `blurb` | yes | one line: who it's for, what it covers |
| `selector` | yes | filter over the corpus (below) |
| `track_emphasis` | no | tracks listed first in pack views |
| `entries` | no | inline pack-specific entries (full schema) |
| `entries_file` | no | JSONL file of pack-specific entries, path relative to this dir |

### selector

```json
"selector": {
  "domains": ["plumbing"],
  "tracks": ["restore", "improvise"],
  "levels": ["applied"],
  "ids": ["sw-plumbing-001"]
}
```

An entry matches when it satisfies **all** non-empty selector fields
(domains AND tracks AND levels; `ids` always match). At least one selector
field must be non-empty. The pack view then adds the **prerequisite
closure**, so every learning path inside the pack is self-contained.

### pack-specific entries

Entries that only make sense inside the pack (not the general corpus) go
in `entries` (inline) or `entries_file` (JSONL, one full entry per line —
same schema as `../seeds/topics.jsonl`). They are validated exactly like
corpus entries (schema + crisis law), their ids/titles must not collide
with the corpus, and their prerequisites must resolve within the corpus +
the pack.

## Validate

```bash
cd ~/workspace/levi && python3 -c "
import sys; sys.path.insert(0, 'core')
from levi.sidewinder.curriculum.corpus import load_corpus
from levi.sidewinder.curriculum.editions import load_manifests
ms = load_manifests(corpus=load_corpus())
print('packs ok:', sorted(ms))
"
```

Or run the test suite: `python3 tests/test_sidewinder.py` — manifest
schema, entry validation, and dangling-prerequisite checks are covered.

## Pack law

Packs inherit the crisis doctrine: professional help FIRST, always —
improvisation is last resort. Every crisis-domain entry in a pack carries
an explicit call-for-help-first stop condition plus do-not-attempt
conditions. Standard first-aid/wilderness knowledge only.

## Drafts (pack builders)

Career-field drafts live in `../packs/<field>/` (draft entries + draft
manifest), owned by the pack builders — this directory holds SHIPPED
packs only. To validate a draft against the schema and the live corpus:

```bash
python3 -c "
import sys; sys.path.insert(0, 'core')
from pathlib import Path
from levi.sidewinder.curriculum.corpus import load_corpus
from levi.sidewinder.curriculum.editions import load_manifests
ms = load_manifests(path=Path('core/levi/sidewinder/packs/<field>'), corpus=load_corpus())
print('draft ok:', sorted(ms))
"
```

It raises listing every problem (schema, entry validation, dangling
prerequisites, id/title collisions). Promotion, once Chauncey approves
the draft:

1. Move the manifest to `edition_packs/<pack-id>.json` (file name must
   match the pack `id`).
2. Entries: promote general entries into the corpus via
   `levi sidewinder grow` (drop the finished JSONL into
   `seeds/topics.jsonl`), or keep pack-only entries in the manifest's
   `entries` / `entries_file`.
3. Run the suite — manifest validation is covered by tests.
