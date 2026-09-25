# L.W.P. — Logan Wyrd Press

The press. Briefs in, finished content out, receipts on everything.

L.W.P. is LEVI's writing engine: the literary tool, the prodigy. It runs
as a production line — five operator seats, each stage gated by the binding
rail (Plan → Preview → Permission → Execute → Verify → Receipt). Nothing
reaches a publishing surface without a human saying so, twice.

## The line

```
ideation → drafting → revision → polish → publish_ready
  alpha      levi       echo      mandella    omega
  (LOW)    (MODERATE)   (LOW)      (LOW)      (HIGH)
```

- **ideation** (alpha, LOW): seats an angle from the brief. Auto-approved.
- **drafting** (levi, MODERATE): drafts under the brief's Direction / Phase /
  Power. **Always halts for a human.**
- **revision** (echo, LOW): dedupes, trims, holds the meaning. Auto-approved.
- **polish** (mandella, LOW): polishes the copy. Auto-approved.
- **publish_ready** (omega, HIGH): seals the dossier. **Always halts for a
  human — and `publish` additionally requires that seal to carry an explicit
  approval.** Deny or skip the gate and publishing raises, always.

Seats are reassignable data; each seat's nature (ai/si/mssi) is read live
from the Founders' Roster at execution time. Reassignments persist in the
press store beside the ledger, so they hold across separate `levi lwp`
invocations; a run keeps the seats it started with. A run that halts with
`needs_attention` (e.g. polish failing a platform spec) is finished — the
line never seals unverified copy, and there is no resume. Re-file the brief
with a fixable spec.

## The console

```bash
# File a brief and start the line
levi lwp brief --title "The Honest Price" --text "..." --kind prose

# See what's waiting on you
levi lwp status

# Approve or deny a gate (human acts — these are the law, not a formality)
levi lwp approve --proposal <id> --note "keeper: draft it"
levi lwp deny --proposal <id> --note "keeper: not this angle"

# Release a sealed run (requires the explicit seal approval)
levi lwp publish --run <id> --note "release"

# Inspect a run, with its final text
levi lwp status --run <id> --text

# See the operator seats
levi lwp seats
```

Brief kinds: `manuscript`, `social`, `prose`, `reversible`.
`--kind social` also takes `--platform` (linkedin, x, …).
`--kind reversible` runs the press itself as the draft: `--target-words`
is read as the number of books (default 3, cap 50).
`--cast N` (1–12, manuscript/prose kinds) asks the press to mint a
dramatis personae of N characters from the L.W.P. character graph at draft
assembly — deterministic, ledger-scoped, carried on the assembly receipt
into the sealed dossier. The draft text is identical with or without a
cast; the cast is additive metadata, never a perturbation.

Runs persist in `~/.levi/lwp_machine/` (ledger + store), so briefing in
one command and approving in the next just works.

## The reversible press

The signature facility. Twenty-six hand-verified word-palindromic clauses —
each reads identically forward and backward at the word level, so *any*
ordering is grammatical prose and order carries the story arc. Fall/return
(full span, both directions), free-directional slices with wraparound, and
spiral center-out paths: every start page in either direction is a story.

```bash
levi lwp press --count 3 --seed 7
```

Prints three verified books, same words, different arcs. The pool is
re-verified before every run; an inadmissible clause halts the press.

## Literary strands: in the line vs. alongside it

The press line itself exercises: the twin-pair organs (Echo×Mandella,
REIM×RIEM), the model engine (Direction/Phase/Power assembly), the
symbiotic ledger (phantoms + compost), the reversible pool, and the king
content helpers. The other literary strands are standalone facilities —
used by other organs, not press stages — and that split is deliberate:

- **character_graph** — wired into the line (2026-09-21): a brief's
  `cast_size` mints the dramatis personae at draft assembly.
  Standalone use continues via `levi characters` and the story fabric.
- **mirror_cascade** — a reverse-pattern cross-check instrument
  (forward/reverse/shadow coils), not a press stage: it analyzes a
  plan or opportunity, and forcing an analysis act into every brief
  would tax work that never asked for it. Reach it via the console
  and the cloud/meta/ei organs that already call it.
- **premium_craft** — story-beat craft (openings, beats, paragraph
  expansion) at the story level, used by `levi.graph.story_fabric`;
  the press assembles drafts at the run level — different altitude.
- **opportunity_rail** — opportunity analysis instrument; not press.
- **fusion** — the intelligence-composition router; meta-level,
  above the press line.
- **living_bible / bible_themes** — canon-fact surfaces feeding the
  model engine's state (bible_facts, bible_scars); already reachable
  through the engine, not a separate line stage.

Nothing here is dead code: each strand has a live caller and a reason
it is not a press stage. If a strand earns a place in the line, it gets
wired with tests like the cast was — never bolted on.

## Honest contract

- Everything is local and deterministic: seeded assembly, the L.W.P. model
  engine's own templates, no model calls, no network.
- `published` means sealed + receipted + cleared for a publishing surface.
  This machine never touches a network.
- Creation drafts are not canon. The line's gates are Chauncey's: no
  approval, no advance — no exceptions.
