# LEVI Builder

**LEVI's own autonomous multi-agent app builder — a LEVI-native recreation of what Emergent (emergent.sh) does: natural-language description in, complete runnable application out.**

Local-first. Stdlib-only. Free forever.

## What it is

```
levi build "a guestbook app where visitors can sign their name and leave a note"
```

The builder runs a six-stage crew through LEVI's existing agent runtime
(`levi.agent.loop.run_subtask` — the canonical plan→act→observe loop; the
builder never rebuilds the loop):

1. **planner** — description → `BuildSpec` JSON (architecture, entities,
   API routes, pages, features). Falls back to a labeled heuristic spec
   when generation is unavailable.
2. **frontend** — generates the complete `index.html` (inline CSS/JS,
   zero dependencies).
3. **backend** — generates `app/handlers.py` against a strict contract
   (`ROUTES` table; `handler(request, db) -> (status, headers, body)`).
4. **data** — generates `schema.sql` (SQLite).
5. **tester** — generates a JSON test plan of HTTP assertions; the
   pipeline boots the project on **127.0.0.1** (ephemeral port) and runs
   them. Generated server code is executed *only* here, never anywhere
   else.
6. **packager** — writes `README.md`, the `levi-build.json` manifest
   (provenance: spec, stage results, quality notes, smoke results), and
   optionally a one-command export tarball.

Every generated Python file passes quality gates (`levi.builder.quality`):
`py_compile` + AST complexity caps + advisory ruff, and — when the code
council is available — submission through the council's CLI contract
(`levi council build --json --write <tmp> --confirm`). If the council is
missing or errors, the gate degrades to static-only and records the seam
in the report. Nothing is ever a silent pass.

## Stacks

| Stack | Output | Run |
|---|---|---|
| `static` | single `index.html` (+ README) | `python3 -m http.server 8000` |
| `fullstack` | stdlib Python server + SQLite + frontend | `python3 -m app` |

Both run with `python3 -m` and nothing else. No npm, no pip, no accounts,
no cloud, no frameworks.

Fullstack layout:

```
<name>/
  app/__init__.py  app/__main__.py   # `python3 -m app`
  app/server.py                      # ThreadingHTTPServer: static + /api/*
  app/handlers.py                    # ROUTES table (backend stage)
  app/db.py                          # sqlite3 helpers → data/app.db
  app/static/index.html              # frontend stage
  schema.sql                         # data stage
  README.md  levi-build.json         # packager stage
```

## CLI

```
levi build "<description>" [--stack static|fullstack] [--name NAME]
           [--out-dir DIR] [--export] [--quality auto|council|static|off]
           [--preview] [--yes]
```

- `--preview` prints the plan and writes nothing.
- Without `--yes`, the plan prints and you confirm before anything is
  written (Plan → Preview → Permission → Execute → Verify → Receipt).
- `--export` produces a tarball under `<project>/exports/`.

### Wiring it into the CLI

`core/levi/cli/main.py` is owned by other crews; the hookup is three
additions (do not edit it from builder work):

```python
from levi.builder.cli import cmd_build, register_builder_parser   # with the other imports
...
    # >>> LEVI builder — autonomous multi-agent app builder
    register_builder_parser(sub)
    # <<< LEVI builder
...
        # >>> LEVI builder — autonomous multi-agent app builder
        "build": cmd_build,
        # <<< LEVI builder
```

## Differentiators (the additions Emergent refuses)

- **Local-first.** Builds run on your machine through your agent
  runtime — not a cloud queue you wait behind.
- **Free forever.** Stdlib-only output, zero marginal cost to produce.
- **You own it completely.** One-command export (`--export`) to a
  tarball: take it anywhere, keep building with any team, no account,
  no lock-in.
- **No training-data harvesting, explicitly.** Your build descriptions
  are processed locally and are never used to train models. This is
  recorded in every `levi-build.json` manifest under `guarantees`.

## Honest limits (v1)

- **Scaffold scope.** v1 ships `static` and `fullstack` (Python +
  SQLite) scaffolds. No mobile-app output in v1.
- **Quality depends on description precision.** Vague descriptions
  produce generic apps — the planner can only build what you describe.
  The heuristic fallback is labeled as such in the manifest.
- **Generation needs a provider.** With no cloud model keys, the
  default agent generator uses whatever provider the agent runtime
  selects (rules/local) — output will be simple. Add keys to get the
  full multi-model crew.
- **The tester is HTTP-level.** It asserts status codes and body
  substrings on localhost; it is not a full browser or security test.
- **Council gating is best-effort.** The council gate improves the
  backend module when seats are available; with no seats it keeps the
  draft and says so.

## Safety

- Generated projects are inert file trees until *you* run them.
- The builder executes generated server code only for localhost smoke
  tests (127.0.0.1, ephemeral port, killed afterwards).
- Consequential actions follow Plan → Preview → Permission → Execute →
  Verify → Receipt.
