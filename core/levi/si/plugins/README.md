# levi.si.plugins — the "and more" lane

The open lane for SI-side plugins: music first, everything else after.
A plugin here is two halves that stay honest about what each half does:

- **engine half** (Python, this directory): the real logic — queues,
  curation, synthesis, receipts. Runs in LEVI, stdlib-first, no network.
- **cell half** (`cells/<name>/`): the Hicomb tricombs cell — palette
  commands and in-editor behavior over the waggle bus. No network
  strings, ever (the host's net-pattern scan rejects them).

## Shipped: focus-flow (music)

`focus_flow.py` — `FocusSession`:

- `plan(minutes, mood)` → SI ambience params (via
  `SIEngine.consult("focus-pick")`) + the buzztunes focus queue.
  The queue is **curated order only**: buzztunes searches, curates,
  scores, and receipts the queue; it does not render audio (its own
  engine says so, and the receipt repeats it).
- `render(path, config)` → a real playable 16-bit mono WAV: a locally
  synthesized ambient pad (seeded, deterministic) plus a noise bed.
  The receipt states plainly: *synthesized ambience, not licensed
  music*.

`cells/focus-flow/` — the tricombs cell:

- `tricombs.json`: kind `tool`, needs `["commands"]`.
- `cell.js`: `defineCellPlugin` contract; three palette commands
  (`focus-flow.start/stop/next`) driving an in-cell Web Audio pad.
  Audio is feature-detected — cells run in a Worker and not every host
  exposes `AudioContext` there; when it is missing the cell says so
  instead of faking playback.

## Shipped: google-drive (google)

`google_drive.py` — `DriveSession` (G-laws in `glaws.py`):

- `list(query)` → code/text files on his Drive (scoped search,
  `CODE_QUERY`).
- `pull(file_id, local_path)` / `read_text(file_id)` → download as
  UTF-8 text (1MB cap, undecodable bytes refused, not guessed).
- `push_new(local_path, ...)` / `push_update(file_id, local_path)` →
  upload or replace file content.
- Every transfer returns a `DriveReceipt`
  `{file_id, name, sha256, bytes, ts, direction}`.
- No delete, no trash-empty, no permission changes — those methods do
  not exist (G1). Auth rides the existing connected `hatch_gws_cli`
  session; the plugin never handles tokens (G7).
- CLI: `python3 -m levi.si.plugins.google_drive ls|pull|push`.

`cells/google-drive/` — the tricombs cell:

- `tricombs.json`: kind `tool`, needs `["commands", "editor",
  "fs-write"]`.
- `cell.js`: `defineCellPlugin` contract; `google-drive.stage-active`
  copies the active buffer to `google-drive-outbox/` via fs-write and
  tells the user the exact engine command that completes the push;
  `google-drive.drive-help` shows the command reference. The cell
  never claims Drive IO — the contract has no exec capability.

Publish path (unchanged, existing tooling):

```
python3 core/levi/hicomb/plugin_studio.py test <cell-dir>
python3 core/levi/hicomb/plugin_studio.py publish <cell-dir> --actor owner
```

## Follow-on google lanes (open, unbuilt)

Gmail and other Google services fit the same two-half shape when he
orders them: engine half over `hatch_gws_cli` (gmail/sheets/calendar
subcommands), cell half staging via fs caps. Nothing built until he
says build it.

## Adding the next plugin ("and more")

1. New module `core/levi/si/plugins/<name>.py` — engine half.
   Re-export it from `plugins/__init__.py`.
2. New cell dir `core/levi/si/plugins/cells/<name>/` with
   `tricombs.json` (name, version, title, cell, kind, needs) and the
   entry JS written against `defineCellPlugin(activate)` — see
   `~/workspace/hicomb/public/tricombs/cell-shim.js` for the sealed API
   (`call`, `registerCommand`, `unregisterCommand`, `onCommand`,
   `notify`). Copy no network strings into the cell.
3. Laws check: the engine half names its tiers and limits (L1, L4);
   nothing in either half phones home (L2); failures degrade with an
   honest message (L3).
4. Tests in `tests/test_si_layer.py` (or a new `test_si_plugins.py`):
   property tests for the engine, manifest validation + net-scan for
   the cell via `plugin_studio.test_plugin`.
5. Document it here, one section, plain words.

## Roadmap lane (open, unbuilt)

Ideas Chauncey named that fit this lane when he orders them: more
music kinds (loop lab, session stems), editor-adjacent tools, and any
future plugin kind. Nothing here is built until he says build it —
the lane is open, not filled.
