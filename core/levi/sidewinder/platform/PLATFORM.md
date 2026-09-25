# Course-platform — design notes (in-module, local-only)

The **platform** is the infrastructure that delivers the course. The
COURSE (`../curriculum/`) is the training curriculum — content that
trains agents. The platform is the runtime on top: query, teams, learning
loop. LEVI and its agents consume the platform; the CLI is one surface
today, a web UI can be another later. Stdlib only, no network.

## Layout

- `api.py` — `CoursePlatform`: the query API. Search, get, manual,
  track progressions, learning paths, edition views, team views, the
  growth pipeline as the content engine, the team learning loop.
  Everything (CLI, skills, agents, future web UI) consumes this.
- `cli.py` — `levi sidewinder` and `levi course` CLI surfaces. Thin:
  parse args, call the API, print text.
- `teams.py` — agent teams: named groups with assigned tracks and/or
  editions (`TeamRegistry`, `teams.json`). A team's view = edition union
  (or whole corpus), narrowed to assigned tracks, plus prerequisite
  closure.
- `loop.py` — team learning loop: `harvest` (validate + queue field
  submissions) -> `review_intake` (dry-run report) -> `promote_intake`
  (append validated/deduped to the corpus with provenance stamps). No
  unreviewed writes, ever.
- `teams.json` — declared teams (e.g. `field-crew` on the First
  Responder edition, `build-crew` on the build/create tracks).

## Team scoping

Any query accepts a team context: `levi course improvise --team
field-crew`, or `api.search(..., team="field-crew")`. Teams also get the
learning loop so crews get smarter together — field learnings flow back
into the corpus through the same validated growth machinery, with
provenance stamped on each promoted entry.

## CLI surfaces

- `levi sidewinder <task> [--edition E] [--team TM]`: field-improv answers
- `levi sidewinder teams`: list teams
- `levi sidewinder team-harvest <team> <file.jsonl>` /
  `team-review <team>` / `team-promote <team>`: the learning loop
- `levi course [tracks|editions|<track>|<topic>] [--edition E] [--team TM]`

## Learning engine + life-coach sub-engine

Chauncey's canon: "life coach was sub engine of learning engine."

- `learning_engine/` — the LEARNING ENGINE: the platform's learning layer
  as an explicit engine. Curriculum delivery (search/get/manual,
  progressions, learning paths, edition + team views), the team learning
  loop, and the growth pipeline — the engine that trains agents and teams.
  Wraps `CoursePlatform` additively; the existing query API is untouched.
- `learning_engine/life_coach.py` — the LIFE COACH sub-engine: personal
  refinement tooling. Nested module boundary — owned by the engine,
  reachable only as `engine.life_coach`, never standalone, never a
  platform sibling. Consumes the career packs' team/skill outputs and
  turns them into refine plans (drills from steps, safety checklists from
  stop conditions, prerequisites ordered first) and career refinement
  programs over edition packs. Career refinement first, personal
  refinement as the horizon.
- `CoursePlatform.learning_engine` / `api.refine(...)` — additive wiring.
  The engine delegates all personal-refinement work to its sub-engine.
