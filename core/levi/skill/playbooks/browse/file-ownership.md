---
skill_id: browse.file_ownership
name: File Ownership Map
description: Exclusive file ownership for parallel builders — who owns what, and the rules that keep parallel work from colliding.
risk: info
permissions: []
requires_confirmation: false
tags: [browse, ownership, parallel, coordination]
version: 1.0.0
---

# File Ownership Map

Parallel builders do not share files. Ownership is exclusive for the
duration of a phase.

## The map (phase 2)

| Builder | Owns (exclusive) | Tests owned |
|---|---|---|
| A — foundation (phase 1) | `browse/__init__.py`, `browse/plugin.py`, `browse/permissions.py`, `browse/page.py`, `browse/pipeline.py`, `browse/bundle_card.py`, `browse/manifest_guard.py`, `scripts/check_no_remote_fetch.py` | `tests/test_browse_plugin.py`, `tests/test_browse_permissions.py`, `tests/test_browse_pipeline.py`, `tests/test_browse_bundle_card.py`, `tests/test_browse_manifest_guard.py` |
| B — privacy | `browse/shields.py`, `browse/cookies.py`, `browse/attrib.py`, `browse/sessions.py` | `tests/test_browse_shields.py`, `tests/test_browse_cookies.py`, `tests/test_browse_attrib.py`, `tests/test_browse_sessions.py` |
| C — vault + tools + credential broker | `browse/vault.py`, `browse/credentials.py`, `browse/tools/__init__.py`, `browse/tools/qr.py`, `browse/tools/reader.py`, `browse/tools/capture.py`, `browse/tools/translate.py` | `tests/test_browse_vault.py`, `tests/test_browse_credentials.py`, `tests/test_browse_tools.py` |
| D — sync | `browse/sync.py` | `tests/test_browse_sync.py` |
| E — automation | `browse/agent.py` | `tests/test_browse_agent.py` |

## Rules of the road

1. **Exclusive means exclusive.** If your change needs a line in
   someone else's file, you do not edit it — you file the request and
   they make the edit, or it waits. Cross-edits are how hot branches
   catch fire.
2. **Read anyone's committed files freely.** Reading is not owning.
   Only uncommitted in-flight files are off-limits.
3. **Temp-index commits only**, with the glyph trailer, on the exact
   paths you own. Never stage a sibling's path, even if it looks
   abandoned — parked work is Chauncey's to rule on, not yours to sweep.
4. **Each module ships a `MANIFEST_ENTRY` dict** for mechanical merge
   into `interop/manifest.py`. The merge happens after the shared index
   settles — never forced during a hot window, never by hand-editing
   the manifest mid-phase.
5. **API freeze (phase 2):** Builder A's phase-1 API is frozen. If your
   module needs an API change, you write the request with the reason;
   the change lands only with a recorded ruling. Silent drift is how
   platforms get re-narrowed (see the Manifest-V3 lesson).
6. **One builder, one phase, one lane.** A builder finishing early
   helps review siblings' diffs — never starts a second lane's files.

## Shared surfaces

`docs/BROWSE_LAYER.md` (design) and `docs/BROWSE_LAYER_BUILD_PLAN.md`
(plans) are read-only for builders. Corrections go through the
coordinator, not direct edits — the design is Chauncey's ruled
document.
