# Source-Sync Protocol — porting external source repos into LEVI

Standing operational protocol for bringing an external source repository
(private or public) into the LEVI tree. Every source is re-synced the
same way; each item is converted to its correct LEVI-native format per
that source's format map. The registry of sources lives in
`sync/sources.yaml`; each source is an entry with its own item-by-item
format map.

## Binding laws

1. **Rewrite, never copy-paste.** Every ported item is an original
   LEVI-native implementation *inspired by* the source concept. No
   source text is copied into the proprietary tree. This keeps LEVI's
   license clean regardless of the source repo's license.
2. **stdlib-only kernel.** New Python lands in `core/levi/` with no new
   dependencies (repo law — no exceptions without Chauncey's approval).
3. **Privacy-scrubbed public code.** Everything landing in the repo will
   eventually be public: strip ALL PII, secrets, private data, and
   identifying metadata from code, docs, tests, and fixtures. Tests and
   docs use synthetic example data only. Formatting stays consistent —
   `ruff format` is canonical for Python.
4. **Security sweep is mandatory.** Every ported item is swept for
   secrets, hardcoded credentials/hosts, exfiltration, and unsafe
   execution patterns before it lands. Findings block the port.
5. **Defensive-only for security content.** Security material is
   detection/analysis/hardening only. Offensive tooling is never ported.
6. **Local commits only.** A push hold is active until the build waves
   and MEGAZORD-10 unification complete — port commits stay local.
   Nothing is pushed without Chauncey's fresh transient token at the
   end, and each push is verified against `origin/main` afterwards.

## Procedure: first sync

### 1. Register the source

Add an entry to `sync/sources.yaml`:

```yaml
- id: example-source
  repo: xaniexane/example-source
  visibility: private   # or public
  branch: main
  synced_at: "2026-09-15T00:00:00Z"
  commit: <sha that was synced>
  status: active        # active | pending (not yet fetched) | retired
  notes: one-line description
  format_map:
    - source: path/in/source
      target: path/in/levi
      format: rewrite | build | design-port | design-reference | skip
      reason: why this format was chosen
```

`format` values:

| format | Meaning |
|---|---|
| `rewrite` | Reimplement the concept as original LEVI-native code |
| `build` | Source is a stub/empty artifact; build the implied system |
| `design-port` | Port the *design* into a new language/module, not the code |
| `design-reference` | Document the API/surface as a labeled reference only |
| `skip` | Do not port; `reason` is mandatory |

### 2. Fetch (private repos)

Private repos are fetched with a **transient GitHub PAT** supplied by
Chauncey in chat:

- The token is passed via environment variable into a `GIT_ASKPASS`
  helper script; it is never written to a file, never embedded in the
  remote URL, never quoted in logs or reports.
- The helper is **shredded immediately after the clone/fetch**
  (`shred -u`, fallback `rm -f`).
- Verify the remote afterward: `git remote -v` must show no token.
- Clone to scratch space (`~/workspace/.<name>-scratch/`), shallow
  (`--depth 1`). Never clone into `~/workspace/levi`.
- The token is never stored, retained, or reused.

Public repos: plain shallow clone, no credentials.

### 3. Inventory

Full file inventory: tree, sizes, languages, READMEs (read fully).
Binary/office artifacts (e.g. `.xlsx`) are forensically decoded —
sheets, structure, and actual content — and the decode is reported
honestly (an empty template is reported as an empty template, not
padded with invention).

### 4. Security sweep

Grep every text file for: secrets/API keys/tokens/passwords/private
keys, hardcoded URLs/hosts/credentials, exfiltration patterns (data
sent to third-party hosts), `eval`/`exec`/`subprocess`/`os.system`/
`child_process`/`pickle.loads`, obfuscation. Binary artifacts are
checked for macros, external links, and embedded objects. Report
`file:line` for every finding. **Any finding blocks the port until
resolved.**

### 5. Classify

Every item is classified: `benign productivity/tooling`,
`defensive security`, `offensive security`, `docs/plans`, or `unknown`.
Offensive items are never ported. Unknowns are resolved with Chauncey
before porting.

### 6. Convert per the format map

- `rewrite`: original LEVI-native code, honest docstrings, no invented
  behavior, stdlib-only, ruff-formatted.
- `build`: implement the system the artifact implies; mark clearly
  that the source was a stub/template.
- `design-port`: new module embodying the design in the target
  language; no source code copied.
- `design-reference`: a labeled reference doc (endpoint lists, schema
  shapes) — never copied generated code.
- Register skills in `SkillRegistry` where the item is a capability
  (risk-tagged honestly; INFO for read-only/content helpers).
- Wire CLI subcommands following the `levi backup` / `levi jobs`
  pattern (`register_*_parser` + `cmd_*` + dispatch entry).
- Docs: one doc per domain in `docs/`; extend existing docs where the
  item belongs to an existing domain.

### 7. Test

Hermetic tests for every new module (`tests/test_<name>.py`):
no HOME writes (construct with `tmp_path`), no network (local
`http.server` in-thread where HTTP behavior is tested), no
randomness, synthetic data only. Run the new tests plus a broader
suite smoke before committing.

### 8. Commit locally

One commit per source sync, message naming the source and what was
ported. **Do not push** — the push hold is active. Record the synced
commit SHA back into `sync/sources.yaml`.

## Procedure: re-sync (source updated)

1. Re-fetch the source at its new HEAD (same transient-token hygiene
   for private repos).
2. Diff old synced SHA → new HEAD. Only changed items re-enter the
   pipeline; unchanged items are untouched.
3. Re-apply the format map to changed items (rewrite/build/design-port
   conversions are re-done, not merged with generated diffs).
4. Re-run the security sweep on changed items.
5. Re-run the affected tests plus a suite smoke.
6. Commit locally; update `synced_at` and `commit` in
   `sync/sources.yaml`.

## Source-specific notes

- **Omega-Powered-by-Alpha** (entry `omega-powered-by-alpha`): first
  sync 2026-09-15. Empty xlsx → built `core/levi/jobs/`; content
  helper → rewrote `core/levi/king/content_machine.py`; fetch wrapper
  design → `core/levi/plugins/http.py`; generated API client → labeled
  design reference `docs/CREATORLAB_REFERENCE.md`; broken/irrelevant
  files skipped.
- **Levi-ai** (entry `levi-ai`): pending — second private source,
  format map to be defined on inventory after fetch.
