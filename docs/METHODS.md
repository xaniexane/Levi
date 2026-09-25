# METHODS — forgotten human techniques reborn as LEVI works

`core/levi/methods/` — 40 pre-digital methods, each reimplemented from scratch
as LEVI's own stdlib-only, local-first code. Source research:
`~/workspace/research_notes/forgotten-methods-wave3-20260916-0015/report.md`
(entries 1–40, each with mechanism, cause of decline, revival recipe, sources).

The wave-2 top-10 software revivals live in `core/levi/revival/`
(`notes`, `ecco`, `interlisp`, `inferno`, `eros`, `linkbase`, `mumps`,
`goap`, `eurisko`, `groove`) — see `docs/REVIVAL.md` for the first 10 and
the section below for the second 10.

## Standing laws (apply to every module here)

- **Remix law.** Faithful preservation belongs in the Archive. These modules
  are LEVI-native realizations: the load-bearing mechanism taken, improved,
  and made unreplicable — not clones of dead systems. Each wave-2 module
  carries an explicit "Remix delta" in its docstring.
- **Hard-route law.** No paid APIs, no licensed dependencies, no tolls.
  Everything is stdlib-only; sync is transport-agnostic and local;
  persistence is plain JSON under `~/.levi/` (overridable via `LEVI_HOME`).
- **Deny-closed.** Fail-closed validation everywhere; corrupt stores are
  quarantined (`<name>.corrupt-<ts>.json`, raising `CorruptStoreError`),
  never silently absorbed. Nothing phones home.

## The 40 methods

### Memory systems (1–8)

| Module | Source | What it is in LEVI |
|---|---|---|
| `loci` | Method of Loci | Memory palaces: rooms/loci, facts with vivid image-anchors, `walk()` recall scripts, `quiz_round()` spaced tours |
| `llull` | Llull's combinatorial art | Exhaustive idea generation from a primitive alphabet; `generate()` with a caller-supplied `judge` — the machine enumerates, the human decides |
| `bruno` | Bruno's memory wheels | Ring-rotation encoder distinct from Llull: ordered symbol rings, rotation offsets, image-seeds, deterministic seeded decks |
| `pinakes` | Callimachus's Pinakes | Judgment-laden catalog: authenticity flags (authentic/disputed/spurious/unknown), bidirectional crossrefs, `disputed()` audit |
| `tironian` | Tironian notes | Personal shorthand: token→expansion with ambiguity rejection, compounding markers, word-boundary-safe expansion |
| `commonplace` | Commonplace books + Locke's index | Heads + excerpts with provenance, Locke-style dense index, `audit_heads()` proposes merges — never reorganizes |
| `florilegia` | Florilegia | Thematic anthologies; second-hand excerpts must name their source anthology; `needs_verification()` audit |
| `triplebook` | Paciolian triple-book | memoriale → giornale (dual debit/credit) → quaderno; `trial_balance()` flags unbalanced accounts |

### Retrieval systems (9–14)

| Module | Source | What it is in LEVI |
|---|---|---|
| `edgenotch` | Edge-notched (McBee) cards | Document→feature bitmask cards; AND/OR/NOT needle passes; Zatocoding collisions reported by `may_false_drop()` |
| `optical` | Optical-coincidence "peek-a-boo" | Inverted term-cards; `coincide()` ANDs the stack; `view()` renders the light-table grid |
| `uniterm` | Uniterm coordinate indexing | Post-coordinate search with a real boolean parser (AND/OR/NOT, parens, implicit AND, quotes); every search returns a coordination trace |
| `colon` | Ranganathan colon classification | PMEST facets (domain-configurable); `classify()` synthesizes colon numbers, `parse()` round-trips, `pivot()` slices collections |
| `mundaneum` | Otlet's Mundaneum/UDC | UDC-style notation + typed relations (supports/contradicts/extends/exemplifies/about); INSPIRATIONAL — a faithful sketch, contradictions flagged |
| `kardex` | Kardex visible records | One card per entity with a visible status strip; `dashboard()` renders all strips; `flagged()` surfaces red cards |

### Productivity & deliberation (15–25)

| Module | Source | What it is in LEVI |
|---|---|---|
| `tickler` | 43-folder tickler file | File → day/month routing, `distribute_month`, `open_today` resurfaces context bundles, overdue surfacing |
| `ivylee` | Ivy Lee six-task method | ≤6 cap, total-order ranking, `current()` reveals only task #1, out-of-order work refused, `chronic_rollers` report |
| `franklin` | Franklin's moral-perfection ledger | 13-virtue black-spot ledger (public-domain precepts), weekly focus rotation, weekday clustering reports |
| `ach` | Analysis of Competing Hypotheses | Hypothesis×evidence matrix ranked by disconfirmation; diagnosticity, sensitivity analysis, `argue_against` steelman |
| `repertory` | Kelly's repertory grid | Triadic construct elicitation with provenance, 1–7 rating grid, construct analysis, new-option scoring |
| `morphological` | Zwicky's morphological box | Exhaustive enumeration + cross-consistency pruning; fails closed past 200k combos unless `allow_large=True` |
| `triz` | TRIZ contradiction matrix | Full 39 parameters + 40 principles; contradiction data is a **curated 9-cell subset** — `coverage()` reports exactly what's encoded; unencoded pairs return `[]`, never a guess |
| `waterlogic` | de Bono water logic | Flowscapes: consequence-path tracing (cycle-safe), rut detection, dead ends, neglected branches |
| `vsm` | Beer's Viable System Model | S1–S5 + 3* diagnostic: missing systems, coordination/control overhead, recursive `decompose()`, viability verdict |
| `opsroom` | Cybersyn opsroom method | Seven-chair decision room, one signal per chair, algedonic alerts, mandatory-rationale log; INSPIRATIONAL — faithful protocol, honest about limits |
| `deming` | Deming's System of Profound Knowledge | Four-lens diagnostic (variation: refuses judgment under 8 points; systems; theory/prediction; psychology) |

### Pedagogy protocols (26–28) — runnable protocols, clearly labeled

| Module | Source | What it is in LEVI |
|---|---|---|
| `trivium` | Trivium & quadrivium | grammar→logic→rhetoric→quadrivium with hard gates; cross-examination Q&A |
| `ratio` | Ratio Studiorum | praelectio tour, repetitio schedule (1/3/7/14/30) with 0–5 recall marks, disputatio, versioned changelog |
| `monitorial` | Monitorial instruction | Peer teach-back: naive→sharp→hostile pupil sequence, mastery gate, team cascade with fidelity spot-checks; INSPIRATIONAL — recursion revived, regimentation not |

### Verification & labor (29–32)

| Module | Source | What it is in LEVI |
|---|---|---|
| `pecia` | The pecia system | Checksummed parallel-verification discipline for splitting work across agents |
| `duplex` | Nautical Almanac duplex verification | N-version execution: 2+ paths must agree or the result is quarantined |
| `t5` | Los Alamos T-5 pipeline | Staged execution with input checks, per-stage cards, microbatching; failures attributed, never swallowed |
| `therbligs` | Therbligs | 17-element motion-study analysis turned into LEVI's workflow analyzer for agent plans |

### Signaling & protocols (33–38)

| Module | Source | What it is in LEVI |
|---|---|---|
| `pneumatic` | Pneumatic dispatch routing | Store-and-forward capsule routing, tube batching + flush; INSPIRATIONAL — LEVI's information-diet router |
| `codebook` | Commercial telegraph codebooks | Phrase→code compression with edition control; collision refusal; edition-skew made visible |
| `qcodes` | Q-codes & prosigns | Terse status vocabulary: parse/query/describe; unknown signals refused |
| `prowords` | Radiotelephony prowords | Consequential-instruction protocol: read-back confirmation, typed acks (ROGER≠WILCO≠AFFIRM) |
| `chappe` | Chappe semaphore codebook | (page, pos) two-signal phrase compression — LEVI's densest phrase→signal encoding |
| `quipu` | The quipu | Knot-encoded tallies with roll-up accounting and tamper-evident verification; INSPIRATIONAL |

### Adversarial games (39–40)

| Module | Source | What it is in LEVI |
|---|---|---|
| `kriegsspiel` | Kriegsspiel | Umpired adversarial testing: fog of war, order validation, double-blind adjudication — LEVI's red-team harness |
| `randgame` | RAND political-military gaming | Scenario comparator: competing world models, flags exactly where they diverge |

## Wave-2 top 10 (in `core/levi/revival/`)

LEVI-native syntheses, each with an explicit "Remix delta" in its docstring:

| Module | Source | Remix delta |
|---|---|---|
| `notes` | Lotus Notes replication | Notes' replication discipline reimagined as LEVI's local-first memory sync: directory replicas, revision vectors, tombstones, explicit conflicts — no mail/formulas/ACLs |
| `ecco` | Ecco Pro | Ecco's fusion as the memory data model: freeform nodes + typed folders as lenses, mistyped values rejected never coerced — no PIM |
| `interlisp` | Interlisp-D | DWIM correction (always reported, never silent) + Masterscope AST cross-reference over LEVI's own modules — "what depends on this?" before acting |
| `inferno` | Inferno | Per-task mount stacks, shadowing, auto-unmount — composed ON `plan9`, not reimplemented |
| `eros` | EROS/KeyKOS | Factories, coverage-checked attenuation, sealing, meters — built ON `telescript` tokens; the "research flights" sub-agent literally cannot touch email |
| `linkbase` | Hyper-G/Microcosm | Separate bidirectional auto-maintained link layer; trails (`xanadu`) are journeys, linkbases are territory |
| `mumps` | MUMPS | `^person("mom","birthday")` with LEVI's own journal+snapshot recovery; `$DATA`/`$ORDER`/`KILL` semantics; stdlib JSON, no DB engine (hard-route) |
| `goap` | GOAP | A* over preconditions/effects/costs with runtime replanning; says "unreachable" instead of hallucinating |
| `eurisko` | Eurisko | Scorable heuristics with credit assignment wired to the growth loop; historical claims labeled DISPUTED by design |
| `groove` | Groove | Pairwise workspace sync, version vectors, explicit conflicts — local transports only (hard-route: no relay/STUN/TURN) |

## Honest gaps

- `triz` ships a curated 9-cell contradiction subset, not the full 1521-cell
  table; extending it needs verification against a published Altshuller
  matrix — transcribing from memory would risk wrong cells.
- `eurisko` historical claims are disputed (labeled in-module); groove/notes
  have no network layer; `eros` sealing is factory-enforced, not
  cryptographic; `mumps` is single-process with JSON-serializable values
  only; Masterscope is name-based (dynamic calls invisible); GOAP uses a
  0-heuristic (Dijkstra — safe, potentially slow at scale).
- `uniterm` synonym expansion is deliberately caller-provided and reported,
  never hidden. `morphological` fails closed past 200k combos.
- Full-suite runs show 3 pre-existing failures unrelated to this work
  (2× heartbeat time-of-day, 1× finance order-dependent flake).

## Tests

- `tests/test_methods_mem1.py` + `test_methods_mem2.py` — 32 tests (entries 1–14)
- `tests/test_methods_delib2.py` — 75 tests (entries 15–28)
- `tests/test_methods_proto3.py` — 45 tests (entries 29–40)
- `tests/test_revival2.py` — 40 tests (wave-2 top 10)

192/192 passing, hermetic (isolated `LEVI_HOME`, no network, deterministic).
