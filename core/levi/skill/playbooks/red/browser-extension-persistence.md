---
skill_id: red_browser_extension_persistence
name: Browser Extension Persistence Test
description: Test malicious browser extension persistence to validate extension allowlisting and review processes.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, persistence, browser, extensions]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_browser_forensics_with_hindsight
---
# Browser Extension Persistence Test

## Purpose

Browser extensions run with broad permissions and persist across sessions — a malicious
or compromised extension is durable access to everything the user does in the browser.
This test measures extension allowlisting enforcement and the review process for new
extensions.

## When to use

- When the org allows browser extensions without centralized control.
- To validate extension allowlist GPOs actually block unapproved installs.
- As part of the user-workstation persistence phase.

## Prerequisites

- Authorization for extension installation on test workstations.
- Inert extension: canary beacon on install, no data collection.
- Browser inventory: which browsers and extension policies are deployed.

## Procedure

1. Build an inert test extension requesting broad permissions (tabs, cookies) with a canary
   install beacon.
2. Attempt installation via the web store, sideloading, and enterprise policy paths.
3. Record which paths the allowlist blocked and which succeeded.
4. For successful installs, verify persistence across browser restarts and the canary
   beacon.
5. Test whether the EDR or browser management console flagged the new extension.
6. Remove the extension from all test workstations; verify removal.
7. Deliver the extension-control assessment with allowlist policy recommendations.

## Expected outputs

- Per-install-path block/allow matrix.
- Persistence-verification evidence.
- Extension inventory vs. allowlist delta.

## Pitfalls

- Extensions that phone home with real browsing data — inert canary beacons only.
- Testing on users' primary profiles without consent — use test profiles.
- Forgetting mobile browsers if the fleet includes them.

## References

- MITRE ATT&CK: Browser Extensions (T1176).
- Browser enterprise policy documentation (Chrome/Edge extension allowlisting).

## Blue-team control under test

This playbook validates their extension allowlist and review process are under test —
unapproved extensions installing silently is a policy-enforcement failure. Paired blue-
team counterpart: `cyber_analyzing_browser_forensics_with_hindsight`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
