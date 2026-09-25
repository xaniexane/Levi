# L.W.P. × Legion Pipeline pairing map

**Date:** 2026-09-21 · **Status:** pairing documentation — no live bridge code.
The loop builds, stages, and queues; **Chauncey decides.** Nothing in this doc
moves a draft across a gate; the gates are his, and `PublishPermissionError` is
the law in code (`core/levi/lwp/machine.py`, `ContentMachine.publish`).

Both machines work the same raw material — language — but on different axes:

| | L.W.P. press line | Legion pipeline |
|---|---|---|
| **Moves** | brief → finished content | concept → sealed edition |
| **Unit** | `ProductionBrief` → `PressRun` | concept brief → cards / packs |
| **Line** | ideation → drafting → revision → polish → publish_ready | 01-creation → 02-factory → 03-nursery → 06-production → 07-campaign |
| **Lanes** | one line, five stages | four lanes (A creatures, B spells/traps, C god tier, D inverses/variants) |
| **Human gates** | `approve()`/`deny()` on rail proposals; `publish_ready` seal approval | his yes/no/rename; his nursery approval; his production sign-off; his explicit account + copy + media approval |
| **Never invents** | (press rails, receipts) | sealed identities (the eleven), intelligence definitions/placements, names |

---

## Direction 1 — pipeline-approved concepts → `ProductionBrief`

An approved concept enters the press as a brief (`levi lwp brief ...`,
`ContentMachine.run_brief`). **Only** concepts whose verdict is on record enter;
denied concepts compost via REIM — they never become briefs.

Field mapping (`ProductionBrief` fields at
`core/levi/lwp/machine.py`, class at line 191):

| Concept-brief element | `ProductionBrief` field | Rule |
|---|---|---|
| concept title | `title` | his rename verbatim when renamed |
| nature + typeline sketch | `brief_text` | prose of the concept; carries the angle |
| lane (A/B/C/D) | `kind` | manuscript/prose for long-form copy; reversible for form exercises; **social** only for 07-campaign copy (press kit, social packs) |
| platform surface | `platform` | social kind only (e.g. the campaign lane) |
| intelligence axis | `angles` | carries the axis as OPEN until he locks INTEL-SPEC; the press never invents a type or placement |
| approved name | `title` / `pov` | renamed names used verbatim; nothing renamed in transit |
| dramatis personae | `cast_size` | manuscript/prose only; in the working tree pending its own commit — draft text is identical with or without |

Kind-to-lane guidance:

- **Lane A (creatures), Lane C (god tier platforms):** `manuscript` / `prose` —
  the beings and the platforms get long-form copy (field-guide entries, nature
  write-ups). Draft assembly is seeded per brief (`seed()`), so identical
  briefs draft identically — the press is deterministic, not inventive.
- **Lane B (spells/traps — organs, engines, daemons):** `prose` — operating
  copy; the press's revision/polish stages tighten it like the nursery's
  originality pass tightens a card.
- **Lane D (inverses/variants):** `prose` — mirror copy stays mirror copy; the
  press never unseals what the sealed law keeps sealed.
- **07-campaign surfaces:** `social` — press-kit blurbs and social packs; but
  "published" in the press means **sealed, receipted, and cleared for a
  publishing surface** — it never posts anywhere. Campaign distribution still
  needs his explicit account + copy + media approval, separately, by hand.

Stage correspondence (the two lines rhyme but don't merge):

| Pipeline stage | Press stage | Shared shape |
|---|---|---|
| 01-creation (drafts only) | ideation (first mind draws angles) | nothing canon; everything proposable |
| 02-factory (build) | drafting (MODERATE risk → first human gate) | his verdict gates the factory; the rail gates the draft |
| 03-nursery (staging + originality pass) | revision + polish (echo tightens, mandella stakes/validates) | both tighten and check against a standard |
| 06-production (final packaging) | publish_ready seal | his sign-off seals the edition; his seal approval seals the run |
| 07-campaign (press + distribution) | `publish()` release | both require his explicit go — and neither is automatic |

The 04-academy / 05-bootcamp stages are **linked, not owned**: their findings
feed back into 01-creation as judgment, never as cards. The same door serves
the press: academy/bootcamp findings may seed future brief angles, but they
never auto-file a brief.

---

## Direction 2 — L.W.P. drafts → 01-creation/ concept briefs

A press run's finished draft can seed a concept brief. The brief file itself is
still drafted deliberately (by hand or by proposal), filed in
`~/workspace/legion-pipeline/01-creation/` as a dated DRAFT, and carries the
full concept-brief anatomy:

- **proposed name** — proposed, awaiting his yes/no/rename (never declared)
- **nature** — the draft's tightened prose may supply this verbatim
- **typeline sketch** — THE ASCENT stage, FANG/HIDE, SHADOW/SOIL/GLOW/TIDE/
  GALE/MYTH, species-word typeline; OPEN where he hasn't ruled
- **intelligence-type axis** — OPEN and extensible until he fills
  INTEL-SPEC-TEMPLATE.md; the RUNBOOK gate holds: nothing in the
  classification lane runs without his specs

Precedent: the six 2026-09-21 briefs (`the-star-role`, `the-entrance`,
`the-brain-voice`, `the-three-stances`, `the-hive`, `the-park-field`) were
hand-drafted from loop journal entries and land exactly here — each cites the
canon line and the loop commit that grounded it, proposes nothing it can't
ground, and sits at DRAFT awaiting his verdict. (Checked 2026-09-21: zero
approvals on record — nothing has moved to 02-factory.)

The reverse feed is also the nursery for rejected press copy: a draft that
fails the press gates but holds a good image may re-enter as a concept angle,
marked compost-fed; a draft denied by him stays denied — compost, not a
second door.

---

## The gates (his, and the loop never crosses one)

1. **01 → 02:** his yes / no / rename. A brief may be *staged* for the factory,
   never moved.
2. **03 → 06:** his approval after the nursery originality pass (no borrowed
   names, stats, designs, or mechanics).
3. **06 → sealed:** his sign-off + final originality check. Everything is
   reversible until production; sealed editions get new editions, not silent
   edits.
4. **07-campaign:** his explicit account + copy + media approval. No exceptions.
5. **Press publish_ready:** his explicit seal approval, recorded through
   `approve()` → `_explicit_approvals`. Without it, `publish()` raises
   `PublishPermissionError` — the permission is the earlier seal approval; the
   rail's own CRITICAL approval grants no new permission (receipt says so).
6. **The sealed law:** the eleven stay sealed — no names, no order. No
   intelligence definitions or placements invented anywhere, in any lane, in
   any stage, by any machine.

## Hard lines for this pairing

- The loop works **both** strands (press + pipeline) and crosses **neither**
  gate. Build it, stage it, queue it — he decides.
- A mapping is not a bridge. If a live bridge between the press store and the
  pipeline is ever wanted, that is a separate queued item with its own review —
  not this document.
- Anything the press invents on its own (phrasing, cadence) stays draft until
  his verdict, same as a loop invention. The honest line runs through both
  machines: report, don't declare.

## Study verdict — Direction-2 + acts pairing (2026-09-23)

**Question:** should the reversible-acts form (`compose_acts` / `act_slots` /
`act_book`, commit `cf85e32a`) — as a chapter-2 form exercise — seed a lane-A
concept brief now?

**Verdict: no brief yet — the form is not the story.**

- A concept brief is a *content* proposal: proposed name, nature, typeline
  sketch, canon grounding, intelligence axis OPEN. The acts machinery is
  *form*: seeded partition of a clause pool into k acts, palindromic visit
  order, flat book order. A form is not a concept — writing the brief now
  would mean inventing the content the form is meant to carry, and content
  belongs to Chauncey (stories, titles, canon are his — the hard line).
- Lane fit is wrong: lane A is the groupings lane (hive/school/pack/herd/
  flock — massings of intelligence forms). The acts are a book's reading
  structure, not a grouping.
- The honest feed path already exists and needs no new machinery: when he
  orders the chapter-2 form exercise, the *finished draft* can feed
  `creation_writer.write_concept_brief` (commit `0b118e47`) exactly like any
  press draft — nature pre-filled from the drafter's own prose, grounding,
  commits, and lane still supplied by the human drafter. The lane decision
  belongs to the drafter, not the loop.
- Until he orders the chapter there is no draft to feed, so there is no
  honest brief. The form stays in the workshop:
  `~/workspace/your_files/reversible-novel/` + `core/levi/lwp/reversible.py`.

Evidence: `tests/test_lwp_reversible_acts.py` + `tests/test_lwp_creation_writer.py`
— 37 passed from zero (2026-09-23). The mechanics and the writer are both
green; the prerequisite is his word, not more code.
