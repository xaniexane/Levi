---
skill_id: browse.eight_laws
name: The Eight Laws
description: The eight declared laws of the browse layer, verbatim — every build decision is checked against them first.
risk: info
permissions: []
requires_confirmation: false
tags: [browse, laws, invariants, law-guard-prove]
version: 1.0.0
---

# The Eight Laws

Laws first, implementation second, proof before commit. These eight are
declared in `docs/BROWSE_LAYER.md` §3 and repeated here so no builder
works from memory. Violating one is a build-breaking defect, not a
style issue.

## 1. Deny-closed plugins

A plugin can do exactly what it declared and was granted. Undeclared
capability use is **refused at the boundary**, not logged-and-allowed.
The refusal is receipted. There is no "warn mode."

## 2. Keeper-held permissions

Grants live in the owner-only 0600 store: per-plugin, per-capability,
with scope and expiry. Every grant, deny, and expiry is receipted.
The ledger may deceive the *surveillant* (spoof or suppress a permission
prompt toward a tracker) — but that deception is **declared to the
user**, never hidden from them. Consent-ledger inversion: honesty points
inward.

## 3. No silent network

A plugin with network capability declares its hosts; anything else is
refused. The pipeline never phones home. A network call that was not
declared is a refusal, not an event.

## 4. Integrity is not truth

Page captures are sealed as custody exhibits. The exhibit proves the
bytes didn't change — never that the page told the truth. The honesty
footer ("INTEGRITY IS NOT TRUTH") is structural, not a comment.

## 5. Signal, not verdict

All heuristic metadata — tracker verdicts, attribution signals — is
claim-graded: OBSERVED / INFERRED / UNVERIFIED. INFERRED always renders
its "signal, not verdict" caveat structurally. Grades never self-upgrade.

## 6. Nothing leaves the device ungranted

Cookies, vault contents, history, and profiles stay local unless the
keeper explicitly grants an export — which is itself a write op
requiring confirmation. Export is never a default.

## 7. No simulated success

A shield that didn't apply says so. A vault that didn't seal says so.
A sync that didn't sync says so. Mirrors the connector honesty
contract: report the actual outcome, never the intended one.

## 8. No remote fetch at runtime

Committed code never pulls a library, font, or asset from a remote host
at runtime — everything vendored or stdlib. Machine-checkable via the
no-remote-fetch lint gate. A dependency fetched from someone else's
server is a phone call home.

## The check

Before any commit touching `core/levi/browse/`, read these eight aloud
against the diff. If one is bent, the diff does not ship.

## Laws 9–11 live next door

The eight above govern the layer. Laws 9–11 — the consequential-act
protocol (Plan→Preview→Permission→Execute→Verify→Receipt), acting
authority per action class, and the credential crown jewels — live in
`browse.agent_laws`. Read both playbooks before touching
`browse/agent.py`, `browse/credentials.py`, or `browse/sessions.py`.
