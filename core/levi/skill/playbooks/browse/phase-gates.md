---
skill_id: browse.phase_gates
name: Deterministic Phase Gates
description: The exact boolean conditions that must hold before the next phase starts — no judgment calls, no vibes.
risk: info
permissions: []
requires_confirmation: false
tags: [browse, gates, verification, determinism]
version: 1.0.0
---

# Deterministic Phase Gates

A phase is done when every condition below is true. If one is false,
the phase is not done. "Almost" is not a state.

## Gate 0 → 1 (design → foundation)

- [ ] `docs/BROWSE_LAYER.md` committed.
- [ ] Chauncey ruled on all four open questions (DG-1 thin/full, DG-2
      distribution, DG-3 phase-3 timing, DG-4 name) — rulings recorded,
      not assumed.
- [ ] The two adopted primitives (`custody/exhibit.py`,
      `signals/claim_grade.py`) are ruled adopt-or-set-aside (DG-6).

## Gate 1 → 2 (foundation → parallel)

- [ ] All five phase-1 test files pass: plugin, permissions, pipeline,
      bundle_card, manifest_guard.
- [ ] `ruff check` clean on every file Builder A touched.
- [ ] `ruff format --check` clean on every file Builder A touched.
- [ ] Refusal tests exist and pass for: undeclared capability use,
      missing who-pays card, unknown permission name, unconfirmable
      write op, undeclared network host.
- [ ] Pipeline order test passes: fetch → parse → grade → shield →
      hooks, fail-fast, one plugin's exception fails that plugin only.
- [ ] Permission grant/deny/revoke/expiry tests pass against the 0600
      store contract (scope + expiry + receipts).
- [ ] `scripts/check_no_remote_fetch.py` runs and passes on the tree.
- [ ] `manifest_guard.py` runs as a CI gate (fails on narrowing
      without a recorded ruling — tested with a fixture).
- [ ] The automation permissions exist in the catalog
      (`automation_read`, `automation_act`, `credential_generate`,
      `credential_fill`); ungranted use of each is refused and tested.
- [ ] The grant ledger seals at rest via the `cybrus/veil.py`
      binding: no key material in the browse tree (import-graph
      assertion — veil is the only crypto source), wrong-mode store
      still refuses.
- [ ] The plugin API is declared **frozen** in the phase-1 receipt.
      After this point, API changes need a recorded ruling, not a
      commit message.

## Gate 2 → 3 (parallel → native shell)

- [ ] All phase-2 test files pass independently (B, C, D, E).
- [ ] One integration pass green: pipeline + one plugin from each
      builder's surface + a read-only agent run, end to end.
- [ ] Acting action classes refuse by default naming DG-8 (test
      asserts the refusal names the gate); the confirmation
      machinery is implemented and tested.
- [ ] The credential broker's generation path calls
      `entitlement_check` before mint (tested with a stub meter);
      no secret appears in any plan, preview, receipt, or log
      (assertion on the receipt contents).
- [ ] `ruff check` and `ruff format --check` clean across
      `core/levi/browse/`.
- [ ] No module claims "secure", "private", or "anonymous" as a
      blanket — verified by reading, per the honest-claims playbook.
      The credential broker carries no blanket claim at all
      (crown-jewels rule: graded per-mechanism only until audited).
- [ ] Chauncey orders phase 3 explicitly (DG-3). Green tests do not
      imply permission.

## Gate 3 → done (shell → shipped)

- [ ] `./gradlew :app:assembleDebug` succeeds.
- [ ] On-device verification receipted (the shell binds the real
      core, not a mock).
- [ ] Every security-relevant claim re-graded; anything unaudited
      stays UNVERIFIED in the surface.

## Reading the gates

These gates are the contract between phases. A builder who cannot meet
a gate does not negotiate the gate — they report the blocker. The
gate is deterministic: any reviewer re-running the checklist reaches
the same verdict.
