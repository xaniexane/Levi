# LEVI Courses — the awesome-courses curriculum

212 real university courses from `prakhar1989/awesome-courses` (MIT OCW, CMU, Stanford, Berkeley…)
ingested into `core/levi/knowledge/courses/`. Everything here is real, nothing is fabricated.

## Coverage (2026-09-15, from coverage.json — exact)

- **212** courses accounted: **144 fetched OK**, **67 dead** (10s timeout / 404 / blocked), **1 skipped-video** (no transcript).
- Every `ok` record points to an existing file in `raw/`.
- `SOURCES.md` (catalog commit `93f2239`) lists the 212 primaries + alternates.

## Per-subject briefs (11)

Auto-generated field guides at `knowledge/courses/briefs/<slug>.md`: start-here recommendations,
recommended course paths, key terms mined from the ingested texts, and per-course coverage status.
Each subject also has a curriculum skill (`course_<slug>`).

| subject | brief |
|---|---|
| `algorithms` | [brief](core/levi/knowledge/courses/briefs/algorithms.md) |
| `artificial-intelligence` | [brief](core/levi/knowledge/courses/briefs/artificial-intelligence.md) |
| `computer-graphics` | [brief](core/levi/knowledge/courses/briefs/computer-graphics.md) |
| `cs-theory` | [brief](core/levi/knowledge/courses/briefs/cs-theory.md) |
| `introduction-to-cs` | [brief](core/levi/knowledge/courses/briefs/introduction-to-cs.md) |
| `machine-learning` | [brief](core/levi/knowledge/courses/briefs/machine-learning.md) |
| `misc` | [brief](core/levi/knowledge/courses/briefs/misc.md) |
| `programming-languages-compilers` | [brief](core/levi/knowledge/courses/briefs/programming-languages-compilers.md) |
| `security` | [brief](core/levi/knowledge/courses/briefs/security.md) |
| `statistics` | [brief](core/levi/knowledge/courses/briefs/statistics.md) |
| `systems` | [brief](core/levi/knowledge/courses/briefs/systems.md) |

## How the agent uses this

- `course_brief` / `course_search` agent tools (ungated, read-only).
- CLI: `levi courses list [--subject]`, `levi courses brief SLUG`, `levi courses coverage`.
- `levi capabilities curriculum-qa` shows the honesty rules for this domain.

## Limits (read before believing)

- **Extractive, not studied**: the agent reads the field guides and course texts at runtime. It has not
  'taken' the courses; it retrieves and quotes.
- **Dead links are dead**: 67 courses never made it in. `levi courses coverage` shows exactly which.
- **Video lectures have no transcripts** — skipped, never transcribed.
- **No credentials**: nothing here grants a certificate, a degree, or a grade.
- Re-run ingestion with `knowledge/courses/ingest.py` to refresh; status rules are deterministic
  (timeout 10s, binary extensions skipped, YouTube skipped-video).

## News lives elsewhere

Current events are in `core/levi/knowledge/news/` (see `docs/NEWS.md`) — dated recall,
never baked into training weights.
