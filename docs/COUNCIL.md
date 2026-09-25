# LEVI Council — LEVI arguing with itself to get stronger

"Not artificial. Synthetic." The council is three of LEVI's own minds
attempting the same programming task, judged by the same evidence, with
a receipt naming which mind wrote what. No network, no keys, no other
companies' agents inside — all LEVI, all local.

## The minds

| seat | mind | how it works |
|---|---|---|
| `native-brain` | LEVI's own trained brain (`core/levi/brain/`, via `levi.agent.brain_provider`) | Samples the brain for code. The brain is young — its candidates are judged by the gates like everyone else's. Skips gracefully when torch or the trained weights are unavailable. |
| `rules-engine` | The deterministic symbolic mind | Cannot invent algorithms and says so honestly: it generates an API-complete scaffold derived from the tests file. Its strength is **assessment** — deterministic security scans (`eval`/`exec`/`os.system`/`shell=True`/pickle/`input`), error-handling scans, and heuristic review. Always available (stdlib-only). |
| `specialists` | LEVI's specialist personas (`core/levi/agent/specialists.py`) | Routes through the existing specialist registry — the `coding` specialist drafts, a panel of `coding`/`verification`/`security` reviews — with the native brain as the voice behind the persona. No invented personas. Skips gracefully when the brain is unavailable: a persona with no voice stays silent. |

Run `levi council seats` to see which minds are available right now.

## Usage

```sh
# which minds are at the table
levi council seats

# run the council (default: all available minds)
levi council build \
  --task "write a function fib(n) returning the nth Fibonacci number" \
  --tests ./fib_tests.py \
  --properties ./fib_props.py \
  --seats native-brain,rules-engine,specialists \
  --prop-trials 30 --max-mutants 12

# write the winner to disk (explicit confirmation required)
levi council build --task "..." --tests ./t.py \
  --write ./winner.py --confirm
```

Candidate tests contract (`--tests`): a Python file defining `test_*`
functions against an importable `candidate` module. Property file
(`--properties`, optional): a Python file defining `prop_*(rng)`
functions, each taking a `random.Random`; each runs N seeded trials.

## Quality pipeline

In order, for every mind's candidate:

1. **Test-first** — the tests file must define `test_*` functions; a
   candidate with no tests is flagged, not accepted.
2. **Static gates** — syntax, ruff (when installed), cyclomatic
   complexity cap (10), max function length (50 lines). A candidate
   failing here never reaches review; the failure evidence is recorded.
3. **Tests** — executed in a sandboxed subprocess
   (`~/.levi/council/runs/`), scrubbed environment, closed stdin,
   timeout. Any candidate with zero passing tests never reaches review.
4. **Property checks** — `prop_*(rng)` randomized invariants, seeded and
   deterministic. Failure blocks review; absence is skipped, not failed.
5. **Mutation sample** — bounded, deterministic AST mutants: comparison
   flips, boolean-op flips, `not` removal, boolean negation, int ±1. The
   test suite must kill them. Kill rate is **advisory** (a low rate
   indicts the tests, not the candidate) — it never blocks review.
6. **Peer review** — the other minds review each surviving candidate.
   The rules engine contributes deterministic scans; neural minds
   contribute model reviews. Each review scores an explicit checklist:
   `SECURITY:`, `ERROR_HANDLING:`, `EDGE_CASES:` (PASS/FAIL/UNKNOWN with
   a note), parsed into the receipt.
7. **Synthesize** — winner = best test pass rate, then review scores,
   then mutation kill rate. The receipt records every mind's
   contribution, technique evidence, reviews, and provenance.

### Sandbox honesty

The sandbox runs candidates as subprocesses with a scrubbed environment,
closed stdin, and timeouts. That is process isolation, **not**
kernel/seccomp network isolation — treat candidate code as untrusted.

## The receipt

`build` prints a JSON receipt: mind availability (with skip reasons),
every candidate with sha256 and technique evidence, test results, parsed
review checklists, the ranking, the winner, and notes. The winner's
`model` field names the mind — e.g. `specialists/coding via levi-brain
(native)` — so provenance is never ambiguous.

## Maturity honesty

The council is designed for minds at different maturity levels, and the
receipt makes the gap visible instead of hiding it:

- The **native brain** is a tiny model early in training. It will often
  lose to the gates. Every loss is evidence for what to train next —
  that is the point of the argument.
- The **rules engine** will never win on tests (its scaffold raises
  `NotImplementedError` by design), but it is the strictest reviewer at
  the table and the only mind that is always seated.
- The **specialists** are only as strong as the brain voicing them.

As LEVI's brain grows, every neural seat gets stronger — the council is
how LEVI measures that growth, in public, against evidence.
