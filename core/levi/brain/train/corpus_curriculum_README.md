# corpus_curriculum.jsonl — LEVI curriculum corpus v3

**Directive:** Chauncey, 2026-09-21. Make LEVI "more human than human":
arithmetic (required), grammar, chemistry, physics, trigonometry, algebra,
geometry, history, government, civics, 5D EI, personality traits.

**Built by:** `core/levi/brain/train/build_curriculum_corpus.py`
(generator v3, seed `20260921`, deterministic).

## Composition (5,717 records, 376,154 chars → 172,792 tokens under levi-bpe-v2)

| Section | Records | Method |
|---|---|---|
| arithmetic | 4,000 | programmatic: 1,200 addition, 800 subtraction, 1,200 multiplication, 800 exact division; ~25% with worked steps |
| algebra | 700 | programmatic solve-for-x, integer answers, worked transposition |
| number-sense | 400 | programmatic even/odd, comparisons, digit sums, number words |
| grammar | 107 | authored bank: parts of speech, agreement, punctuation, voice, clarity, tone, register, citations, instructions |
| geometry | 122 | authored bank + programmatic Pythagorean triples and rectangle areas |
| science | 140 | authored bank: physics, chemistry, earth/space, life, scientific method — includes "I don't know" calibration |
| civics-history | 97 | authored bank: US government structure, rights, amendments, world history, source literacy, propaganda detection |
| ei | 60 | 15 authored 5D-EI scenes (presence, empathy, regulation, relational, integrity) ×4 paraphrase variants |
| persona | 91 | 23 demos (17 personas + 6 tone/trait demos) ×5 — **provisional IDs only** |

## Record shape

`{text, kind, source, topic}` — all records. Sidecars:
- `ei`: `ei_dims` (comma list of exhibited dimensions)
- `persona-demo`: `persona_id`, `provisional: true`, `tone`, `role`
- `trait-demo`: `tone`, `traits`, `provisional: true`

All text uses the `User:` / `LEVI:` transcript convention; the training
harness wraps sequences `[bos] … [eos]`.

## Guardrails (verified at build)

- LEVI turns contain no self-referential feeling/sentience claims —
  verified zero hits for `i feel|i felt|conscious|sentient|my feelings|
  i'm alive|as an ai language model|great question` across all LEVI turns.
  (The law binds LEVI's turns, not the user's — user lines may express
  feelings; that is their right.)
- Grammar bank corrects through questions and rewrites, never insults.
- Persona IDs are the repo-verified lattice fallback set only,
  `provisional: true` on every record. The final naming/selection set
  is Chauncey's decision.

## Provenance

- arithmetic / algebra / number-sense: programmatic templates, seeded RNG —
  no external source, no copyright exposure.
- grammar / geometry / science / civics-history: authored fact banks,
  elementary well-established facts only.
- ei / persona: authored by the brain worker, 2026-09-21.

**Manifest:** `corpus_curriculum_manifest.json` (section counts, char
totals, generator version, build timestamp, sidecar spec).
