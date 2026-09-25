# LEVI Forge — your local-first code home

LEVI Forge is a code forge (git hosting + collaboration) that lives
entirely on your machine. stdlib-only, no network, no accounts, no
telemetry, no paid anything.

> **Ownership guarantee (binding):** LEVI Forge never transmits your code
> anywhere. There is no telemetry, no training corpus, nothing leaves
> localhost unless **you** push it. Everything works fully offline.

## Why this exists — the additions lens

GitHub is the giant here. Forge recreates the *category* (git hosting +
collaboration) per explicit user order, but its differentiators are the
things GitHub refuses to ship:

1. **One-command full export** — `levi forge export <repo>` dumps
   *everything* (history, issues, PRs, stars, CI logs, contribution graph)
   into a documented open directory that is re-importable anywhere.
   Leaving is a feature, not a threat.
2. **Local-first CI** — pipelines run as subprocesses on your own machine.
   No minute metering, no cloud queue, no vendor lock-in. CI history is
   portable like everything else.
3. **Explicit no-training-data-harvesting stance** — stated in the CLI help
   and here: your code is never transmitted, never scanned, never trained
   on. There is no business model that needs your code, so there is no
   back door.
4. **Fully offline, no account** — every command works with no network and
   no login. `sync`/`publish` exist only when you explicitly ask (stock
   `git push` to any remote you choose).

Monopoly-minus-one: Forge speaks the open git wire protocol, stores repos
as plain bare git repositories, and exports to an open directory format.
Win by being most useful; never by trapping.

## Architecture

```
~/.levi/forge/
  repos/<name>.git/       bare git repos (stock format — copy them, they're yours)
  issues/<name>.jsonl     issues: one JSON object per line
  prs/<name>.jsonl        pull requests: one JSON object per line
  stars.json              starred repos (portable reputation)
  ci/<name>/
    pipeline.json         CI pipeline definition
    runs.jsonl            run records (append)
    runs/<run-id>/        per-run dir: run.json + step-*.log
```

Writes are atomic (temp file + `os.replace`) and owner-only (dirs 0700,
files 0600) — the same discipline as `levi.archive`'s store. JSONL is
append-friendly, diffable, greppable, and human-readable: your data is
never held hostage in a binary blob.

### Design choice: smart-HTTP via stdlib, git does the work

The server (`core/levi/forge/server.py`) implements the HTTP *framing* of
the git smart-HTTP protocol with `http.server` from the stdlib, and shells
out to the stock `git` binary for the pack protocol itself:

- `GET /<name>.git/info/refs?service=git-upload-pack` →
  `git upload-pack --advertise-refs`
- `POST /<name>.git/git-upload-pack` →
  `git upload-pack --stateless-rpc` (request body on stdin)
- same pair for `git-receive-pack`

Why this split:

- **The pack protocol is genuinely hard.** Delta negotiation, pack
  generation, ref updates — reimplementing it would be a bug farm.
  The git binary has two decades of battle-testing; Forge delegates to it.
- **Smart-HTTP is what stock clients already speak.** This is the exact
  protocol `git clone`/`push`/`pull` use against GitHub over HTTPS, so
  every stock git client works against Forge with zero plugins.
- **stdlib-only stays true.** `http.server` + `subprocess` is enough; no
  `git daemon` (different protocol, weaker auth story), no frameworks.
- **The server binds localhost only** (`127.0.0.1`). Anything else is
  refused — code never leaves this machine by accident.

The same server serves a plain-HTML repo browser under `/forge/` (file
tree, README rendering, commit history, issues, PRs, CI). No JS framework,
no build step — HTML is the most portable UI ever shipped.

Pull-request merges use the stock binary too: the bare repo is cloned to a
temp worktree, head is merged into base, and the result is pushed back. A
conflicted merge aborts with the PR left open — Forge reports the conflict
honestly rather than pretending it resolved it.

## CLI surface

```
levi forge serve [--port 8741] [--bind 127.0.0.1]
levi forge repos [create|list|delete] <name> [--desc ...] [--yes] [--json]
levi forge browse <repo> [--rev REV] [--path PATH]
levi forge log <repo> [--rev REV] [--limit N] [--json]
levi forge stat <repo> [--json]
levi forge issue <repo> list|open|show|close|reopen|comment ...
levi forge pr <repo> list|open|show|merge|close ...
levi forge star <repo> [--remove]      /  levi forge stars
levi forge export <repo> [--out DIR]
levi forge import <src-dir> [--name NAME]
levi forge ci <repo> init|show|run|runs
```

`python -m levi.forge ...` works identically. The top-level `levi forge`
dispatch passes arguments straight through to the same parser.

## CI pipeline format

`ci/<name>/pipeline.json`:

```json
{
  "version": 1,
  "name": "default",
  "steps": [
    {"name": "tests", "run": "python -m pytest -q",
     "shell": false, "timeout": 600, "env": {"CI": "1"}}
  ]
}
```

- `run` is split with `shlex` unless `"shell": true`. `shell: true` runs
  your string through the shell — it is your machine and your
  responsibility; Forge does not sandbox steps (documented honestly).
- Every step runs in a **fresh clone** of the repo; each step's combined
  stdout+stderr is captured to `runs/<run-id>/step-NN-<name>.log`.
- All steps run even if an earlier one fails, so logs stay complete; the
  run's `ok` flag is false if any step failed. `levi forge ci run` exits
  nonzero on failure.
- No minute metering, no queue, no cloud. `timeout` defaults to 300s.

## Export format — `forge-export-v1`

`levi forge export <repo> [--out DIR]` creates `DIR` (must not exist):

```
<DIR>/
  FORGE-EXPORT.md    human-readable manifest: what is here, checksums
  meta.json          {"format": "forge-export-v1", "name", "exported_at", ...}
  repo.bundle        complete git history, all refs (`git clone repo.bundle`)
  issues.jsonl       every issue, one JSON object per line
  prs.jsonl          every pull request, one JSON object per line
  stars.json         {"name", "starred": bool, "record": {...}|null}
  contrib.json       [{"date": "YYYY-MM-DD", "author": "...", "commits": n}]
  ci/pipeline.json   CI pipeline definition (if one exists)
  ci/runs.jsonl      CI run records (if any)
  ci/logs/<run>/...  every CI step log
  SHA256SUMS         SHA-256 of every file in the export
```

`levi forge import <DIR> [--name NAME]`:

1. Refuses unless `meta.json` says `forge-export-v1` and `SHA256SUMS`
   exists.
2. Verifies **every checksum** before touching the forge. Any mismatch =
   import refused, nothing written.
3. Rebuilds the bare repo from the bundle (`git fetch` of all refs, HEAD
   pointed at `main` if present else the first branch), restores
   issues/PRs/stars/CI sidecars.
4. Refuses to overwrite an existing repo — no silent clobbering.

Reputation is portable: stars, issues, PRs, and CI history travel with the
export. Leave anytime, take everything, come back whenever.

## What Forge deliberately does NOT do (honest gaps)

- **No multi-user auth.** Forge is single-user local: issues/PRs are
  authored by `local`. Real multi-user collaboration belongs to a later
  increment (signed commits + per-user JSONL authors are the seam).
- **No merge-conflict UI.** A conflicted PR merge aborts and tells you to
  resolve locally — honest, but manual.
- **No webhooks / PR comments from CI.** CI results live in Forge; there
  is no event bus yet.
- **No `sync`/`publish` helper.** Pushing to an outside remote is plain
  stock `git push <remote>` from any clone — deliberately left as stock
  git rather than wrapped.
- **No shallow/clone filtering, no LFS, no submodules special-casing.**
  Stock git handles them over the same protocol; Forge neither helps nor
  hinders.
- **Markdown rendering is a subset** (headings, fenced code, lists,
  quotes, bold/italic/code/links) — enough for READMEs, not a spec.
- **Server is HTTP on localhost, no TLS.** Localhost-only is the security
  model; do not expose the port to a network.

## Cyber boundary

None of this touches the cyber domain. Forge hosts code; it has no
security tooling, offensive or defensive.

## Testing

`tests/test_forge.py` — hermetic (tmp forge home via `LEVI_FORGE_HOME`,
real local `git` binary; skipped gracefully if git is absent). Covers:
home resolution, repo CRUD + name validation, issues lifecycle, PR
open/merge, stars, markdown rendering, smart-HTTP clone+push against a
live localhost server, CI init/run/logs, export/import round-trip with
checksum verification, and CLI entrypoint smoke.
