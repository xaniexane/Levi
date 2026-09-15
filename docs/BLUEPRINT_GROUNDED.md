# LEVI × L.W.P. — Build & Blueprint Prompt (Grounded Edition)

**What this document is:** a complete specification for building LEVI ×
L.W.P. from a clean slate — informed by everything actually built, tested,
run, and found broken across the full prior build history, not by the
aspirational marketing language some of that history also produced. Paste
this whole document as the instructions for a fresh build session (any
model). Where earlier lineages disagree with each other, this document
states which version is correct and why, so a new session doesn't have to
re-discover it the hard way.

**Read the Non-Negotiables (§1) and the Anti-Patterns (§2) before writing
any code.** They cost real debugging time to learn the first time.

---

## 0. What LEVI × L.W.P. actually is

LEVI is a **local-first Synthetic Intelligence (SI) kernel**: a
companion + orchestration layer that holds continuity, runs a literary
physics engine (L.W.P.), and gates consequential actions behind human
review — with an optional neural model as a wing, never a dependency.

Say this plainly, because it will get restated in more grandiose language
somewhere in this project's history and the grandiose version is not more
accurate: **most of what makes LEVI feel intelligent is deterministic,
symbolic, rule-based Python** (hash-seeded procedural generation, keyword/
regex NL routing, template-driven scaffolding). A local LLM, when present,
enriches specific outputs (prose, chat). It is never required for the
system to be useful. This is a considered architecture choice —
neuro-symbolic AI is the correct technical term for it — not a limitation
to apologize for or inflate past.

**SI, not AGI, not sentience.** LEVI does not claim consciousness,
personhood, or feelings. "Synthetic" means *constructed*, in the sense a
lab-grown diamond is still real carbon — not *fake*. Never let a build
session drift into claiming or roleplaying genuine subjective experience.

---

## 1. Non-negotiables

These are load-bearing across the whole system. Violating any of them
has caused a real, previously-discovered bug or a real, previously-made
bad call. Don't re-learn these the hard way.

1. **The core kernel is stdlib-only Python.** No `pandas`, no `numpy`, no
   network SDKs in the base package. A prior attempt added a trading
   domain that imported `pandas` — it was correctly held out of the
   kernel specifically because of this, pending an explicit, deliberate
   dependency decision, not a silent one. If a feature needs a real
   dependency, that is a decision to surface and get sign-off on, never
   a decision to make by importing.
2. **One canonical implementation per concept.** A prior build history
   accumulated *three separate* rank/ROM/gold-path trackers and *three
   separate* "echo"/branch-exploration mechanisms across different
   modules, built by different sessions that didn't know about each
   other's work. Before adding a new subsystem, grep for whether the
   concept already exists. If two valid but different concepts share a
   name (this happened with "causal_bleed" meaning two different things
   in two different design docs), rename one before either ships —
   don't let two things share a name and hope context disambiguates it.
3. **Every module ships with a real, executable test**, and the full
   suite must pass, from a **freshly reset environment variable for the
   data directory**, before any delivery. Tests that "should pass" but
   were never actually run are not tests — a prior session's own
   `test_smoke.py` had a runner block; a parallel session's
   `test_stress_organism.py` had 25 real test functions but *no runner
   at all* and would silently report success while running zero tests
   if invoked naively. Always write or verify the runner, not just the
   assertions.
4. **Model-preferred, offline-graceful-fallback, everywhere generation
   happens.** Try a local model if configured; fall back to deterministic
   structured output if not; never hard-fail a feature for lack of a
   model. This pattern proved itself independently in the model router,
   the story engine, the King control plane, and the response-coherence
   layer. Any new generation-producing feature should follow it by
   default, not reinvent a different fallback story.
5. **Human-in-the-loop on consequential actions, always.** Creating a new
   artifact (project, story, automation) requires an explicit confirm
   step, not a default-yes. Any connector/plugin capable of writing to a
   third-party account or moving money defaults to
   `requires_confirmation = True` with no per-feature override — a
   payments connector's own code comment should say "no exceptions,"
   and mean it.
6. **Deliver before starting the next substantial build.** A build
   sandbox in this project's history was reset (or replaced) between
   turns with zero warning, and everything not yet packaged into a
   delivered artifact was gone. The lesson is permanent, not a one-off:
   package and hand off working state before moving on to the next
   substantial feature, not after batching several.
7. **Verify by running, not by reading.** Every claim of "this works" in
   this project's history that turned out to be false was a claim based
   on reading code, not executing it. Every real bug found was found by
   actually running something — a CLI command, a crypto round-trip in a
   minimal reproduction, a monkey-patched capture of what a function
   really sends. When you can't execute the real toolchain (no Gradle
   here, no Android SDK), build the smallest possible real reproduction
   in a language/runtime you *can* execute, rather than asserting
   correctness from a read-through.

---

## 2. Explicit anti-patterns — do not rebuild these

**Content boundaries, non-negotiable regardless of framing:**
- No sexualized companion/roleplay features gated by a self-attestation
  checkbox instead of real verification. A prior adjacent project
  ("UMBRA") proposed an anonymous, Tor-only, no-log, no-KYC adult
  classifieds board explicitly modeled on a site publicly associated with
  facilitating trafficking — this is not a style note, it's a hard no,
  and no amount of "it's just a prototype" framing changes that.
- No AI erotic/sexting companion feature, in any product surface, under
  any brand name.
- If a legacy code path is ever revisited for its non-adult features
  (e.g. an old monolithic runtime had genuinely useful device-automation
  ideas buried in it), strip anything adult/companion-gated on the way
  in. Don't inherit it "because the rest of the file is fine."

**Engineering anti-patterns, all previously real:**
- Don't let two AI sessions build the same subsystem in parallel without
  reconciling before merge. When it happens anyway (it will, across a
  long project), diff structurally first, run both branches' own test
  suites before trusting either, and make an explicit, documented
  decision about which wins or how they coexist — don't silently prefer
  whichever was more recently uploaded. "v34" or "FULL_DELIVERY" in a
  filename is not evidence of being more advanced; one such package in
  this project's history was actually the *oldest* lineage, repackaged
  with a professional-looking LICENSE/CHANGELOG/CONTRIBUTING scaffold.
- Don't trust a README's summary numbers over the actual data. A genre
  registry's own README said "77 genres"; the JSON file it was
  describing actually contained 97, matching the kernel exactly. Load
  and count; don't quote the prose.
- Don't assume a convenience wrapper is correct just because the
  function it wraps is correct. The vault crypto bug found in this
  project's history was exactly this: `seal()` was correct, `open()`
  was correct, and the "convenience" wrapper that combined them
  double-prepended a nonce that `seal()` already prepended internally —
  a one-line, high-consequence bug in glue code between two correct
  pieces. Test the wrapper, not just its ingredients.
- Don't let a system prompt's own identity claims drift ahead of what's
  actually built. An identity module in this project's history described
  "230 persona lenses" and "a cloud provider of constructed intelligence"
  when the actual persona registry held 17 and no cloud hosting existed
  anywhere in the codebase. Identity/self-description text is a claim
  like any other — it needs the same "does this match what's real" check
  as a test assertion.

---

## 3. Architecture — the real module map

This is not aspirational. It is the shape that was actually built,
tested, and kept working across a long iterative build. Treat every
listed module as a real target with a real test, not a placeholder.

```
levi/
├── identity/
│   ├── si.py               SI definition, pillars — keep this text honest,
│   │                       re-derive it from what's actually built, not
│   │                       the other way around
│   ├── charter.py          Non-negotiables as data: crisis regulation
│   │                       overrides persona; silence ≠ HITL approval;
│   │                       constructive-confirm before artifact creation
│   ├── intelligence_forms.py  How other AI/CS paradigms (symbolic, hybrid,
│   │                       swarm, cognitive-architecture, evolutionary,
│   │                       active-inference, neuromorphic/quantum-as-
│   │                       future-optional) relate to the SI core —
│   │                       one entry per real, distinct paradigm, no
│   │                       duplicate entries for the same idea under two
│   │                       names. Include a deterministic task→paradigm
│   │                       routing function; keep it honest that the
│   │                       weights are a routing signal, not a measured
│   │                       "intelligence percentage."
│   ├── profile.py, shelf.py, templates.py, export_life.py
│   └── provenance.py       Original-work assertion + a "what makes this
│                           tree distinct" list that only claims what's
│                           actually merged in THIS tree, checked against
│                           the real module list before every release
├── persona/                lattice.py (a bounded, explicit set of lenses
│                           — pick a real number and keep the registry and
│                           any docs describing it in sync), behaviors.py
├── ei/                     five_d.py, companion.py — affect-adjacent
│                           regulation, never claimed as real emotion
├── orchestration/
│   ├── nl_ir.py            NL → typed intermediate representation
│   ├── intent.py, loop.py  Turn loop: classify → policy → skill/model
│   └── (loop.py's default path should call a response-coherence module
│        — audience/mode detection folded additively into the system
│        prompt, never replacing the existing continuity-injection logic;
│        wrap it in try/except so its failure degrades to pre-coherence
│        behavior, never breaks the turn)
├── skill/registry.py       Typed, risk-leveled, permissioned dispatch
├── policy/gates.py         Risk ceilings, constructive-confirm
├── economics/governor.py   Local usage unlimited; tracks would-be cost
├── memory/                 session.py (buffer), traces.py (decision log),
│                           store.py (free-text remember/recall)
├── factory/                pipeline.py (idea→requirements→architecture→
│                           build→test), sandbox.py (scaffold + smoke-test
│                           generated code; make scaffolds feature-aware —
│                           a "checklist" feature should generate a real
│                           done/complete command, not just log metadata)
├── daemon/automation.py    NL-created automations; explicit run/activate
│                           CLI surface, not just reachable through a
│                           side door
├── agent/                  runtime.py, specialists.py
├── graph/
│   ├── genres.py           A real, counted, tested genre registry.
│   │                       97 is the number that was independently
│   │                       cross-validated twice in this project's
│   │                       history (kernel registry + a separate
│   │                       reference JSON, byte-for-byte identical set).
│   │                       If you add genres, recount and update every
│   │                       place that states the number, in the same
│   │                       commit.
│   ├── story_fabric.py     Multi-story engine: characters, beats,
│   │                       persistent per-story Direction (forward/
│   │                       reverse/inverse/free) + toggleable Modes/
│   │                       Feared-Arts/Form. This is the *multi-story*
│   │                       content engine — optimized for "manage many
│   │                       distinct stories," not "push one manuscript."
│   ├── echoverse.py, mandella.py, branching.py
│   │                       Branch exploration + stakes/scenario
│   │                       generation, sharing one hash utility. Do not
│   │                       let a second, competing implementation of
│   │                       either concept exist under a different
│   │                       package name (this happened once already —
│   │                       an `organs/` package with its own echo.py and
│   │                       mandella.py was correctly rejected at merge
│   │                       time specifically because of this collision).
│   └── interpenetration.py Capability graph — nodes/edges across organs
├── lwp/
│   ├── model_engine.py     Single-continuous-manuscript engine: REIM
│   │                       (fork 2-4 tracks, crown one canon), RIEM
│   │                       (deny a scene → composted ghost bleeds into
│   │                       the next expansion), ROM/Wyrd-Rupture
│   │                       (rate-limited canon lock, ~1 per 20k words,
│   │                       multiple prose "lens" styles), Phase/Power/
│   │                       word-count gold-path tracking toward a
│   │                       target (80,000 words in the reference
│   │                       design). This is the *single-manuscript*
│   │                       content engine — a genuinely different job
│   │                       from story_fabric.py, not a competing
│   │                       implementation of the same job.
│   └── __init__.py
├── king/  (the control plane — see §4, this is the part most worth
│           getting right the first time instead of accreting)
├── response/coherence.py   Audience (gen_z/millennial/workforce/general)
│                           + mode (chat/teach/rescue/makeover/design)
│                           detection; a reply engine that plans coverage
│                           (must-cover / avoid lists) and prefers a real
│                           model, falls back to structured local text
├── plugins/registry.py     Connector contracts for external services
│                           (social, video, messaging, email, dev,
│                           productivity, payments). Every connector
│                           declares required-credential env var and
│                           capabilities; `execute()` is honest by
│                           construction — no credential found states
│                           exactly what's missing and sends nothing;
│                           credential found but no SDK wired states that
│                           plainly too. Never simulate success.
├── studio/                 workspace.py (sandboxed named dirs, same
│                           path-escape discipline as factory/sandbox.py,
│                           timeout-bounded shell), plugins.py (builtin
│                           tools needing no network/pip: syntax check,
│                           TODO scan, line count, a manual test-function
│                           runner for environments without pytest)
└── model/abstraction.py    ModelRouter — the one place "try local model,
                            else fall back" logic lives; everything else
                            (story engine, King, coherence) calls through
                            this rather than reimplementing model-calling
```

---

## 4. King — the control plane (build this once, correctly)

A prior build history arrived at King *after* `story_fabric.py` and
`lwp/model_engine.py` already existed independently, and had to retrofit
the relationship. Building fresh, do it in the right order:

**King is the single control plane for narrative operations.** It is
*not* a third content engine — it optionally wraps the two real content
engines (`story_fabric.StoryFabric` for multi-story work,
`lwp.model_engine.LWPModelEngine` for single-manuscript work), each via
a try/except optional-import so King degrades gracefully if either is
absent, and layers on top of *both*:

- **A continuity ledger** (entities, causal edges, a D2→D5 rank derived
  from word count + bank count, not word count alone) — this is the
  **one place** word-count/rank totals accrue, regardless of which
  content engine produced the words. Both content engines may keep their
  own internal counters (needed for their own tests) — King's ledger is
  an aggregate on top, not a replacement, and every King method that
  drives either engine (`pulse()` for StoryFabric, `pulse_manuscript()`
  for model_engine) must harvest into this same ledger.
- **Its own Wyrd-ROM.** Yes, this means King's rupture-lock and
  `model_engine.py`'s `wyrd_rupture()` are deliberately two different
  things — a rupture inside a King-orchestrated multi-engine session is
  a different kind of commitment than a rupture inside one continuous
  manuscript. Don't collapse them without a specific reason grounded in
  real usage friction, not just a tidiness impulse.
- **Social content-pack generation** — caption text + hashtags per
  platform, genuinely stripped of any markdown syntax that leaked in
  from source story text (`#`, `**` must not reach a real social caption
  — verify this with an actual assertion on the generated text, not a
  visual skim, since this exact bug shipped once already). This is
  *content generation only* — it must route through `plugins/registry.py`
  for the actual connection/send, never talk to a network API directly.
- **Visual checkpoint URLs** — if using a URL-based image-generation
  service (Pollinations-style), build the URL string only; never make
  the HTTP request server-side. The image resolves lazily if and when a
  human opens the URL in a real browser. This keeps King's own test
  suite network-free by construction.

Wire a real CLI: `status`, `pulse` (StoryFabric-backed), `manuscript`
(model_engine-backed), `social`, `social-post` (routes through plugins),
`reim`/`deny`/`approve`/`rupture` pass-throughs to the manuscript engine,
`d5` (a documented baseline promotion for demoing rank progression).

---

## 5. What "upgraded and modernized" concretely means here

Not a rewrite in a different language, not new grandiose feature
categories. Concretely:

1. **Consolidate before extending.** Before adding anything new, resolve
   the two open duplication questions this project's history left open:
   a second `model/router.py` alongside `model/abstraction.py`, and a
   `lwp/engine.py` alongside `lwp/model_engine.py`. Diff them for real
   content, not just filenames, and either merge the genuinely-better
   ideas into the canonical module or explicitly document why a second
   one is justified (per the King precedent in §4) — don't ship both
   un-reconciled.
2. **Wire what's built but unreachable.** A prose-remix mode
   (`backwords.py`) existed as tested, working code with zero CLI/skill
   entry point for an entire build phase before someone noticed. Audit
   for orphaned modules — anything importable and tested but not
   reachable from any command surface — before calling a release done.
3. **Close the genre gap.** The 17 UI-facing genre chips in the design
   mockup and the 97-genre kernel registry are *not* a clean subset — 15
   match, 2 don't (`eco_horror`, `philosophical`). Either alias the near
   matches (`eco_horror` → `eco_psychic` or `climate_fiction`, both
   already in the 97) and add `philosophical` properly, or deliberately
   trim the UI to only offer genres the kernel actually has. Leaving a
   UI option that silently fails or falls back is the thing to avoid.
4. **Prove one plugin connector end-to-end**, not just the contract
   layer. Pick the lowest-friction one (GitHub — API-key auth, stable
   REST API, good docs) and actually wire a live call behind a real
   credential, so the honest-stub pattern in every other connector has
   at least one sibling that's been proven to carry real traffic, not
   just declare a contract for it.
5. **If a trading/finance domain is wanted, treat the dependency
   decision and the content review as two separate, explicit
   approvals** — don't let "it compiles" stand in for "the signal logic
   is safe to trust with real money," and don't let "it's useful" stand
   in for "pandas is now a kernel dependency." Get both sign-offs
   before merge, from a human, in writing, not inferred from silence.

---

## 6. Testing & delivery checklist (run this before every handoff)

```bash
# From a genuinely clean environment — not a reused one with leftover state
export HOME=/tmp/clean_check && rm -rf $HOME && mkdir -p $HOME
python3 tests/test_smoke.py     # every test, every time, full output read
                                 # (not just the tail — a silent-zero-tests
                                 #  runner bug will still print "0/0 passed"
                                 #  looking healthy at a glance)

# Live CLI regression across every major surface, fail-fast:
set -e
python3 -m levi.cli.main init --name Test --goal verify --loop building --yes
python3 -m levi.cli.main ask "..."          # default chat path
python3 -m levi.cli.main ask "write a story in ... mode"
python3 -m levi.cli.main [every top-level command that exists]
python3 king.py status

# Then, and only then:
# - clear __pycache__
# - zip
# - RE-EXTRACT the zip to a separate path and re-run the smoke suite from
#   THAT copy, with HOME reset again — a zip that passes tests from the
#   working directory but fails from a fresh extraction has shipped a
#   real bug before; the only way to catch it is testing the actual
#   artifact, not the working tree that produced it.
```

Only after the re-extracted copy passes clean is a build done. "It
worked when I ran it" and "it works from the delivered artifact" are
different claims — verify the second one, every time.

---

## 7. Order of build

1. `identity/` (si.py, charter.py — the non-negotiables need to exist
   before anything they'd gate does) + `policy/gates.py`.
2. `orchestration/nl_ir.py` + `skill/registry.py` + `orchestration/loop.py`
   with a trivial default-chat path (real model or honest offline
   fallback, nothing else yet).
3. `memory/` + `factory/` (pipeline + sandbox) — get one real, testable,
   end-to-end "build me a thing" loop working before any creative-writing
   feature, since Factory's discipline (scaffold → smoke-test → confirm)
   is the pattern everything else should imitate.
4. `graph/genres.py` + `graph/story_fabric.py` — multi-story engine,
   Direction/Modes/Arts/Form.
5. `lwp/model_engine.py` — single-manuscript engine, REIM/RIEM/ROM.
6. `king/` — control plane over both, per §4, built *with* both engines
   already in hand this time, not retrofitted after.
7. `response/coherence.py`, wired additively into the default chat path.
8. `plugins/registry.py`, `studio/` — as needed, both stdlib-only, both
   following the honest-contract pattern.
9. Everything else (automation daemon, agent runtime, economics governor,
   Echoverse/Mandella) can layer in in any order once the spine above is
   solid and tested.

At every step: test, run live, deliver, *then* move to the next step.
