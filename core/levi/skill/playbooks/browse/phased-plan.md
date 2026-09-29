---
skill_id: browse.phased_plan
name: Phased Plan 0 to 3
description: The four build phases — what each phase builds, who builds it, and why the order is fixed.
risk: info
permissions: []
requires_confirmation: false
tags: [browse, phases, planning, sequencing]
version: 1.0.0
---

# Phased Plan 0 → 3

The order is load-bearing. Phase 1 cannot be parallelized without
divergence; phase 2 cannot start on an unfrozen API; phase 3 cannot
start on an unproven core.

## Phase 0 — design (DONE)

`docs/BROWSE_LAYER.md` (architect, glyph 🧶). Chauncey rules on the
design before any builder starts. No code ships from the design doc.

## Phase 1 — sequential foundation (1 builder: Builder A)

Plugin API + permissions + page model + pipeline + bundle-card
validation + manifest-diff guard + no-remote-fetch lint. Everything
else hangs off this. Files: `browse/__init__.py`, `browse/plugin.py`,
`browse/permissions.py`, `browse/page.py`, `browse/pipeline.py`,
`browse/bundle_card.py`, `browse/manifest_guard.py`,
`scripts/check_no_remote_fetch.py`. Tests:
`tests/test_browse_plugin.py`, `tests/test_browse_permissions.py`,
`tests/test_browse_pipeline.py`, `tests/test_browse_bundle_card.py`,
`tests/test_browse_manifest_guard.py`.

Phase-1 additions (automation amendment): the permissions catalog
gains `automation_read`, `automation_act`, `credential_generate`,
`credential_fill` (deny-closed; see `browse.plugin_api_contract`);
the grant ledger in `browse/permissions.py` seals at rest via the
`cybrus/veil.py` binding — bound, never reimplemented; no key
material in the browse tree.

## Phase 2 — parallel (4 builders: B, C, D, E)

Against Builder A's **frozen** API. Exclusive file ownership per the
ownership map — no two builders touch the same path.

- **B — privacy:** `browse/shields.py`, `browse/cookies.py`,
  `browse/attrib.py`, `browse/sessions.py` (epoch-ratcheted session
  option for the privacy pipeline, bound to `cybrus/veil.py` —
  forward secrecy via rotation, old epochs destroyed). Tests:
  `tests/test_browse_shields.py`, `tests/test_browse_cookies.py`,
  `tests/test_browse_attrib.py`, `tests/test_browse_sessions.py`.
- **C — vault + tools + credential broker:** `browse/vault.py`,
  `browse/credentials.py` (generate via
  `cybrus/vault.py::generate_password`, store veil-encrypted,
  retrieve via facade autofill; bloodline metering bound to
  `cybrus/broker_meter.py` — entitlement checked before mint),
  `browse/tools/*.py` (qr, reader, capture, translate). Tests:
  `tests/test_browse_vault.py`, `tests/test_browse_credentials.py`,
  `tests/test_browse_tools.py`.
- **D — sync design:** `browse/sync.py` (design + local behavior;
  relay is a spec, not a server). Tests:
  `tests/test_browse_sync.py`.
- **E — automation:** `browse/agent.py` — the agent surface:
  Plan→Preview→Permission→Execute→Verify→Receipt on every
  consequential act; read-only classes (`read_page`,
  `extract_structured`) live, acting classes (`fill_form`,
  `submit_form`, `navigate`, `credential_fill`) refused-by-default
  naming DG-8 until ruled; stdlib heuristics now, native-brain slot
  declared UNVERIFIED-until-proven, no cloud models ever (law 3).
  Tests: `tests/test_browse_agent.py`.

Each builder's tests green independently; one integration pass at the
end (pipeline + one plugin from each builder's surface + a read-only
agent run, end to end). Manifest/warehouse wiring merges mechanically
after the shared index settles — never forced during a hot window.

## Phase 3 — native shell (later, separate toolchain)

Android WebView shell in `apps/levi-android` binding the Python core.
Proof is `./gradlew :app:assembleDebug` plus on-device verification —
unprovable in pytest. Starts only when phases 1–2 are green **and**
Chauncey orders it (decision gate DG-3).

## Why this order

The plugin API is the contract everything else signs. Two builders
writing the contract and its first consumer in parallel produce two
contracts. The foundation is sequential by nature; the leaves are
parallel by nature. Respect the grain.
