# Upload study: levi_consolidated-1.zip

Status: studied, improved, applied LEVI-native. **Ready for keeper review**
(the keeper has not reviewed this; nothing here claims his sign-off).

## What the upload was

`~/workspace/user/files/levi_consolidated-1.zip` (152K, untouched original).
A "hybrid offline-first assistant": FastAPI backend + Vite/React chat
frontend + Docker Compose (backend, Qdrant, Ollama) + optional bare
`llama.cpp/server` backend. Per its own CHANGES.md it consolidates the
~20-file version-20-through-28 pile into one codebase, already cleaned of
the keeper's earlier wilder ideas (multi-account key farming, Cryptex
pay-to-guess, glyph-obfuscation dark pattern, fake "Soulmark"/"E2E"
crypto, always-on background daemons, tier scaffolding) -- the CHANGES
document is unusually honest about what was real and what was theater,
and that honesty is the best thing in the zip.

Components: `main.py` (FastAPI routes), `router.py` (local-first routing,
confidence-based cloud escalation), `privacy.py` (redaction + double
opt-in), `rag.py` (Qdrant + sentence-transformers), `notes.py` (curated
always-on facts, keyword surfaced), `preferences.py` (tone + avoid-notes
from negative feedback), `device_tools.py` (Termux SMS/organize/screen),
`scheduler.py` (cron export + optional LoRA), `db.py` (SQLite
interaction_log), adapters (ollama, llamacpp with keyword lane routing,
two stubs), migrations, three scripts, frontend chat UI.

## State: working scaffold, not production

Ran nothing end-to-end (deps like fastapi/sqlalchemy/qdrant are not
installable in this sandbox), but the code reads as a coherent,
deliberately-designed scaffold with real bugs and gaps, not a dead dump:

**Bugs fixed in the improved copy** (`~/workspace/uploads-work/consolidated/`):
- `notes.py`: `id = len(notes) + 1` reused ids after delete (add 2, delete
  1, add again -> id 2 twice). Now max+1, atomic temp+rename writes,
  empty/overlong rejection, env-overridable path.
- `privacy.py`: the card-run regex used a lazy quantifier that misbehaved
  on spaced/dashed formats; added email + phone patterns; redaction now
  non-raising on non-string input.
- `device_tools.py`: `send_sms` had no number validation or length cap;
  organizer could overwrite and touched dotfiles; screen capture wrote to
  a fixed /tmp path. Now: phone-shape check, 500-char cap, organizer
  skips dotfiles, never overwrites, `dry_run` preview mode.
- `main.py`: deprecated `@app.on_event("startup")` -> `lifespan`; added
  query-param validation on `/device/sms` (1-50).
- `schemas.py`: no input bounds at all -> max_length on every field.
- `scheduler.py` + scripts: hardcoded `/app` paths -> resolve from repo
  root / `ASSISTANT_ROOT` env.
- New: 22 stdlib-only tests (`backend/tests/`), all passing here
  (notes, privacy, device_tools). FastAPI/Qdrant/SQLAlchemy modules have
  no tests -- their deps can't be installed in this environment; the
  Docker path is untested by me.

**Genuinely good ideas** (applied below): the double opt-in gate (standing
setting AND per-request flag), curated always-on notes with keyword
surfacing, and Termux on-device automation that runs only on explicit
trigger -- never on timers. **Deliberately not carried forward**: Qdrant
sentence-transformer RAG (LEVI's own retrieval layers cover this), the
LoRA fine-tune loop (superseded by the native brain program), cloud
adapter stubs, Docker/Ollama scaffolding.

## Applied LEVI-native into the repo

All new code is original LEVI-native recreations (studied the idea,
rebuilt it), stdlib-only, tested, committed locally, never pushed:

1. **`core/levi/dualkey/`** -- dual-key consent gates. The upload's
   `cloud_allowed(a, b)` / `sync_allowed(a, b)` for two actions becomes a
   registry: any consequential action needs its standing key AND its
   per-action request key; every check returns a receipt (gate, keys,
   reason, timestamp) and lands in an audit trail. This is the standing
   Permission step made reusable. Tests: `tests/test_dualkey.py` (9).

2. **`core/levi/pincards/`** -- the keeper's always-on facts. The
   upload's flat notes list, with the LEVI twist: cards are never deleted,
   only retired (the stone never forgets; `purge()` is keeper-only and
   says so); every card carries provenance + scope tags; secret-shaped
   text is *refused at the pin* rather than redacted later, because a
   pinned fact lands in every prompt it matches. Atomic JSON writes,
   env-overridable path. Tests: `tests/test_pincards.py` (10).

3. **`core/levi/companion/`** -- on-device on-demand hands. The upload's
   Termux SMS/organizer/screen tools, hardened: read vs write permission
   classes, `send_sms` requires `confirmed=True` (explicit per-send
   permission, not a standing yes), structured `ToolResult` returns,
   `shutil.which` detection so non-Termux machines fail cleanly, nothing
   on any timer. Tests: `tests/test_companion.py` (9).

Total: 28 new tests, all green; ruff clean.

Not applied: `privacy.py` redaction patterns -- `core/levi/observability/redact.py`
and `core/levi/growth/redact.py` already cover secret/PII scrubbing better
than the upload did (key-naming, secret-shaped values, emails, phones,
cards, SSNs, cloud-experience gates). No duplication added.

## Frontend evaluation (study only -- no frontend code entered the repo)

`App.jsx` was a bare chat box + two privacy checkboxes with no error
handling, no loading state, and no UI for the backend's own `/notes`,
`/preferences`, `/feedback` endpoints. In the improved working copy I
modernized it (esbuild-verified): tabbed chat/notes/preferences, per-call
error surfaces, loading indicator, citations display, tone picker, avoid
list, note add/delete -- all against the existing API. Remaining gaps:
no feedback buttons wired to `/feedback` yet (the avoidance pipeline
exists server-side but the UI never feeds it), no auth on any endpoint,
CORS wide-open (`allow_origins=["*"]` with credentials -- fine for a
local-only dev loop, must not ship facing a network). Recommendation for
the real LEVI console: the tabbed pattern is worth stealing; the privacy
checkboxes per request are the right consent UX and match the dualkey
mechanism above.

## Honest gaps

- The Docker/Compose path, Qdrant RAG, Ollama/llamacpp adapters, and the
  LoRA scripts were reviewed but not executed here -- treat them as
  studied, not verified.
- `preferences.py` (tone/avoid-from-feedback) was a good idea but LEVI's
  persona/memory layers own this space; I did not force a port. If the
  keeper wants the specific "avoid notes from negative feedback" mechanic
  as its own module, that's a follow-up.
- The improved working copy lives outside the repo at
  `~/workspace/uploads-work/consolidated/` by design; the original zip is
  untouched in `~/workspace/user/files/`.
- Nothing pushed. Commits are local only per the standing push hold.

## Commits (local, main)

- `dualkey`: new module + tests
- `pincards`: new module + tests
- `companion`: new module + tests
- this report doc
