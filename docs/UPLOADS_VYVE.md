# Uploads study — VYVE / LEVI platform drops

**Worker:** uploads worker (VYVE assignment)
**Date:** 2026-09-17
**Sources (originals untouched):**
- `~/workspace/user/files/VYVE_LEVI_PLATFORM-7_25_o80w.zip` (9.3 MB, uploaded 2026-09-17)
- `~/workspace/user/files/LEVI_MASS_CHAT_PROFILES-4.zip` (524 KB, uploaded 2026-09-17)
**Working copies:** `~/workspace/uploads-work/vyve/` (improved in place; stays outside the repo)

The two drops are the same lineage, two revisions: `platform-7_25` is the
broader August build (king package, web consoles, lwp model engine, design
docs); `mass_chat` is the later Grok-led merge (2026-08-26/27 ROUND_LOG)
with the vault seal, build ladder, chat profiles, and template seeds.

## What each upload was, and its state

### VYVE_LEVI_PLATFORM-7_25 (platform drop)
- `king.py` (24 lines) — thin entry stub delegating to `levi.king.cli`. **Stub**, fine as-is.
- `levi_core/` — full lineage core (~70 files): agent, daemon, ei, factory,
  graph (echoverse/mandella/interpenetration), identity, king (cli/control/
  echo/ledger/social/visual/wyrd), lwp (model_engine), memory, persona,
  policy, premium, project (HITL), skill registry, studio.
- `design/lwp-model.html` (37 KB) — interactive L.W.P. model spec page.
  **Study doc, static.**
- `design/LEVI_HYBRID_SYNTHETIC_INTELLIGENCE_V2.md` — hybrid-SI fusion
  architecture: fusion kernel, intelligence genome (routing recipes),
  intelligence marketplace, master operating loop. **Design only, never
  implemented** — the richest unimplemented idea in the drop.
- `source_analysis/hyperdrive/...` — `LEVI_APOTHEOSIS_APEX(1).py` (1344-line
  monolith: soul/personas/glyph UI/memory/music/Termux automation/model
  routing/Echoverse/Mandella/REIM/RIEM/image-gen), `Levi Symbiosis Protocol
  (G1).md` (four machine↔organism couplings, poetic but unimplemented),
  `LEVI_23.4.0_EI.py`, `LEVI_CLI_BEST_23.6.0_AgentWebUpgrade.py`,
  `CONTROLLING_MASTER_PROMPT_LEVI_X_LWP_HYPERDRIVE.md` (2816-line build
  handoff spec — study/analyze only).
- `web_console/` + `web_console_v2/`, `vyve/`, `lwp/`, `docs/`,
  `learning_package/` — consoles, specs, curriculum docs. **Study material.**

### LEVI_MASS_CHAT_PROFILES-4 (mass-chat drop)
- `levi_core/levi/vault/seal.py` — passphrase "seal" for local blobs.
  **Working but DEAD-GRADE crypto**: single SHA-256(passphrase) as key,
  raw XOR stream, no salt, no authentication. Revival-yard candidate.
- `levi_core/levi/meta/ladder.py` — build ladder steps 1–4 with concrete
  checks, text report, readiness %. **Working concept**, no machine output.
- `levi_core/levi/ei/mass_chat.py` — 7 chat profiles (id/label/mode/
  persona/blurb/starters) + honest usability report. **Working, clean.**
  Old registry rhymed profiles with tech-giant UX patterns (not LEVI-law
  compliant — recreated without those echoes).
- `levi_core/templates/*.json` — 4 free marketplace flywheel seeds
  (morning_status, checklist_cli, notes_cli, systems_horror_seed).
  **Working seeds.**
- `tests/test_smoke.py` (718 lines), `tests/test_stress_organism.py`.
  **Working.**
- `ROUND_LOG.md` — 2026-08-26/27 Grok merge journal (42 tests, ladder
  1–4 PASS at the time).

## What I improved (working copies, `~/workspace/uploads-work/vyve/`)

1. `mass_chat/.../levi/vault/seal.py` — **raised, not deleted**: PBKDF2-
   HMAC-SHA256 (260k iters) + random 16-byte salt + HMAC-SHA256
   counter-mode stream + HMAC verify-then-decrypt; Fernet preferred when
   `cryptography` is installed; self-describing `VS1` header; legacy `X1`
   blobs remain readable with the same passphrase and `migrate()` re-seals
   them; dir 0o700 / files 0o600. Verified: roundtrip, tamper detection,
   wrong-passphrase rejection, legacy migration.
2. `mass_chat/.../levi/meta/ladder.py` — added `ladder_json()` machine-
   readable report for automation gates.
3. `mass_chat/.../levi/ei/mass_chat.py` — added `to_dict()`,
   `profiles_json()`, `validate_profiles()` registry health check.
4. Left alone (study only): Apotheosis monolith, controlling master
   prompt, web consoles, design html — analyzed, not ported.

## What got applied LEVI-native (into `~/workspace/levi`)

All recreations, never copies; stdlib-only; tests for every module.

| Module | Source idea | What it is |
|---|---|---|
| `core/levi/lwp/fusion.py` | Hybrid SI V2 §§11–13, 16 (fusion kernel, intelligence genome) | Classify problem → estimate uncertainty → select cheapest-sufficient paradigm mix → compose a governed plan. Weights are routing signals, never sentience claims. |
| `core/levi/lwp/symbiosis.py` | Symbiosis Protocol G1 (four couplings) | Symbiotic Residue Ledger: immutable decision **locks**, **phantom** supersession memory, **compost** failure digestion (growth-loop-shaped corrections), **pollen** style-fingerprint records (offline, no manuscript data). Append-only JSONL. |
| `core/levi/cybrus/seal.py` | vault/seal.py idea, raised | `SealedEnvelope`: lightweight passphrase envelopes for the keeper's private text (distinct from `CredentialVault`'s structured credential store). Fernet preferred; honest stdlib fallback; legacy `X1` read-only migration. Existing cybrus gateway untouched. |
| `core/levi/academy/ladder.py` | meta/ladder.py idea | Generic `BuildLadder`: registered steps, hermetic checks, text report + `ladder_json()` + `readiness_pct()`. Default `kernel_boot` step exercises the new modules. |
| `core/levi/founders/chat_profiles.py` | ei/mass_chat.py + templates/*.json ideas | LEVI-native chat profiles (7, no provider-branding echoes) + session seeds. Registry API, JSON export, `validate()`. |

Tests: `tests/test_lwp_fusion.py`, `tests/test_lwp_symbiosis.py`,
`tests/test_cybrus_seal.py`, `tests/test_academy_ladder.py`,
`tests/test_founders_chat_profiles.py`.

## Honest gaps
- The fusion kernel's paradigm selection is heuristic (keyword
  classification); it routes, it does not understand. Capabilities are
  assumed present unless the caller passes a capability map.
- The stdlib crypto fallback is fallback-grade (documented in-module),
  not AES; Fernet is preferred where `cryptography` exists. Not an HSM.
- The Apotheosis monolith, web consoles, and controlling master prompt
  were studied only — porting them wholesale would duplicate what LEVI
  already has natively (king plane, agent runtime, persona lattice).
- Nothing here has the keeper's review — marked ready-for-review only.
