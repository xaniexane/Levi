# Sidewinder Course — design notes (in-module, local-only)

Chauncey's course: "how to build, create, improve, restore, combine and
improvise anything for anything — a big course just about everything known
to mankind this far, how to fix anything even without proper equipment."

**Course vs platform.** The COURSE is the training curriculum — the
content that trains agents (this package). The PLATFORM
(`../platform/`) is the infrastructure that delivers it: query API, team
scoping, team learning loop. The platform serves LEVI and its agents, and
agent teams as well; the CLI is one surface today, a web UI can be
another later.

## Structure

- **Six tracks** (`TRACKS` in `../__init__.py`): build, create, improve,
  restore, combine, improvise. Every entry carries >= 1 track.
- **Foundations spine** (`corpus/foundations.jsonl`): how things work —
  mechanical advantage, materials, joining, measurement, cutting, safety,
  water, electricity, friction, diagnosis. Level `foundation`, no
  prerequisites.
- **Levels**: foundation -> applied -> mastery. **Prerequisites** are
  entry-id links forming real progressions; `progressions.py` serves them
  in learning order and verifies the graph (no dangling refs, no cycles).
- **Crisis domain** (`corpus/crisis.jsonl`): first-class domain of the
  IMPROVISE track. Non-negotiable law: professional help FIRST, always;
  improvisation is last resort when no help or equipment is coming. Every
  crisis entry's first stop condition calls for professional help and at
  least one states an explicit "do not attempt if..." boundary. Standard
  wilderness/first-aid improvisation only — no DIY surgery, ever.

## Edition packs

An **edition** is a named, manifest-driven curriculum pack for a career
field or audience: a selector (filter over domains/tracks/levels/ids),
track emphasis, and optional pack-specific entries. Manifests live in
`edition_packs/*.json` — declarative, no code changes to add a pack. See
`edition_packs/README.md` for the authoring guide. **First Responder**
(`first-responder.json`) ships first — Chauncey authors the rest
(plumbing, electrical, automotive, carpentry, farming, ...).

A pack's view = selector matches over the corpus + pack entries +
prerequisite closure, so every learning path inside the pack is
self-contained.

## Growth toward thousands

- `corpus/<domain>.jsonl`: sharded data, one entry per line. Shards keep
  the shared branch merge-clean.
- `seeds/planned_titles.txt`: the roadmap — `track | domain | title`
  lines. Add lines to grow the plan.
- `seeds/topics.jsonl`: intake queue for finished entries.
- `levi sidewinder grow [--batch N] [--dry-run]`: validate -> dedup
  (title, then id) -> append to domain shards -> consume processed seeds.
- `levi sidewinder stubs <n>`: emit writer stubs for the next unbuilt
  planned titles. Fill the FILL sections, move to topics.jsonl, grow.
- Teams feed the same pipeline: `team-harvest` -> `team-review` ->
  `team-promote` (platform learning loop; no unreviewed writes).

## Query paths (platform surfaces)

- `levi sidewinder <task> [--domain D] [--track T] [--edition E] [--team TM]`:
  terse Sidewinder answer (mechanism -> improvise -> steps -> stop).
- `levi sidewinder manual|show|doctrine|grow|stubs|teams|team-harvest|team-review|team-promote`
- `levi course [tracks|editions|<track>|<topic>] [--edition E] [--team TM]`:
  curriculum progressions and learning paths; `course editions` lists the
  available packs.
- Skills `sidewinder_doctrine` / `sidewinder_field_manual` (category
  `fieldcraft`, INFO) in the shared SkillRegistry — this is how wave
  agents inheriting the DNA core get the course. The manual skill runs
  through the platform API and accepts edition/team scoping.

## Honest scoping

This is a growing corpus driving toward comprehensive coverage, not a
claim of literal omniscience. Entries ship only when their content is
real: no filler sections, no invented specs. In the crisis domain the bar
is explicit: the method has to be worth betting a life on, or it doesn't
ship.
