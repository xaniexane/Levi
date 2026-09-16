# TEACH — curriculum-ordered training data for the v2 brain

`core/levi/teach/` converts **approved corpora** into clean training
sequences ordered simple → complex, deduped, with versioned manifests.
It is the TEACH worker's half of the brain pipeline; the v2 trainer
(`core/levi/brain/train/v2/`) consumes what `teach prepare` writes.

## Standing policy (hard gate)

**NEWS stays OUT of training weights** (docs/BRAIN_TRAINING.md §6).
Every converter and every prepared run passes
`levi.brain.train.v2.corpus_manager.check_policy`; a news-tagged or
news-path corpus raises `PolicyError` and never reaches a manifest.

## Approved sources

| Source    | Converter output                                        | Tag            |
|-----------|---------------------------------------------------------|----------------|
| `courses` | Chunked full texts from `knowledge/courses/raw/**`     | `courses`      |
| `academy` | Records from `brain/train/corpus_academy.jsonl`         | `academy`      |
| `growth`  | Redacted learnings via `levi.growth.corpus_export`      | `growth`       |
| `seed`    | Growth seed curriculum (`growth/curriculum/lessons`)    | `seed-curriculum` |

| `briefs`    | Subject field guides (`knowledge/courses/briefs/*.md`) | `courses`+`field-guides` |
| `playbooks` | LEVI-original defensive cyber playbooks (`skill/playbooks/cyber/*.md`) | `cyber-playbooks`+`defensive` |

Converters never touch the network. Course texts are chunked
(400 words, 40 overlap) with `[subject · file]` headers; email addresses
are masked by `sanitize_text` (syllabi ship TA addresses — noise for
training, privacy debt for us).

## CLI

```bash
levi teach plan                                  # dry run: stats, stages, mix
levi teach plan --sources courses academy       # subset
levi teach prepare --out runs/t1                # write the bundle
levi teach prepare --out runs/t1 --teachback-fail-under 0.8   # quality gate
levi teach check runs/t1                        # verify bundle integrity
levi teach stats                                 # runs registered in ~/.levi/teach/manifests/
```

`teach check` re-validates a prepared bundle: manifest hashes, curriculum
shape, `train.yaml` validity, and sequence ↔ corpus ↔ curriculum
cross-references. A broken bundle is reported, never an exception.

`teach prepare` writes:

```
<out>/
  corpora/train.jsonl  val.jsonl  test.jsonl     # seeded 90/5/5 splits
  corpora/train.manifest.json | val | test       # corpus_manager manifests
  corpora/source_<name>.manifest.json            # per-source, feeds train.yaml `mix:`
  sequences_train.jsonl | _val | _test           # fixed windows, curriculum
                                                 # order, stage-tagged
  curriculum.json                                # v2 CurriculumManifest
  train.yaml                                     # v2 TrainConfig (relative paths)
  teach.manifest.json                            # versioned teach manifest
```

`train.yaml` validates with `levi.brain.train.v2.config.load_config` and
points the model builder at `levi.brain.train.model_v2:build_model`
(`tokenizer: ""` = the builder provides its own tokenizer). The prepared
teach manifest is copied to `~/.levi/teach/manifests/<name>@<date>.json`
for `teach stats`.

## Teachback verification

Teachback is a **data-side** check, never a capability claim: synthetic
probes (`core/levi/teach/probes.py`: topic + keywords) are matched
against the prepared training texts. A probe is "covered" when ≥50% of
its keywords appear. Reports carry an explicit disclaimer — coverage
means the data *contains* the vocabulary, nothing about what a model
learned.

## Interface assumptions (SCAFFOLD's v2 modules)

- `corpus_manager`: `Doc`, `check_policy`, `dedupe`, `load_jsonl_docs`,
  `build_manifest`, `save_manifest`, `verify_manifest`, `split_docs`,
  `write_split_jsonl`, `PolicyError`, `CorpusManifest`, `FileEntry`.
- `curriculum`: `build_curriculum`, `save_curriculum`, `load_curriculum`,
  `describe_stages` (contiguous stages over the simple→complex order).
- `config`: YAML `train.yaml` validated by `load_config`; model builder
  import path `levi.brain.train.model_v2:build_model`.

If SCAFFOLD renames any of these, the teach tests (`tests/test_teach.py`)
fail loudly at import — that is the contract check.
