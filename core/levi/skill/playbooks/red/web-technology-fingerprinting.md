---
skill_id: red_web_technology_fingerprinting
name: Web Technology Fingerprinting
description: Fingerprint web applications' frameworks, CMS, and third-party components to scope application testing and flag outdated stacks.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, reconnaissance, web, fingerprinting]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_web_server_logs_for_intrusion
---
# Web Technology Fingerprinting

## Purpose

Identify the frameworks, CMS platforms, JavaScript libraries, and third-party
integrations behind each in-scope web application. Precise fingerprinting focuses
application testing on the right vulnerability classes and flags end-of-life components
before a single payload is sent.

## When to use

- After subdomain discovery, before web application testing begins.
- When the blue team wants an inventory of their public web stack versions.
- To detect shadow IT: CMS instances nobody in IT recognizes.

## Prerequisites

- Passive-leaning: headers, HTML, JS bundles, and public responses only — no aggressive
  crawling in this phase.
- In-scope application list from the subdomain inventory.

## Procedure

1. Collect HTTP response headers, cookies, HTML meta tags, and JavaScript bundle names for
   each application.
2. Identify CMS/framework signatures (wp-content, Drupal headers, Next.js markers, Laravel
   cookies) and record versions where disclosed.
3. Inventory third-party scripts and integrations (analytics, chat widgets, payment
   processors) — each is supply-chain surface.
4. Check version disclosure against EOL databases; flag end-of-life frameworks as findings
   immediately.
5. Note debug endpoints, exposed .git directories, and backup files visible in responses.
6. Produce the per-application technology inventory with EOL flags and shadow-IT
   candidates.

## Expected outputs

- Per-application technology inventory with versions and confidence.
- EOL/outdated component findings with CVE mapping.
- Shadow-IT candidates (unrecognized CMS instances).

## Pitfalls

- Version guessing from a single header — corroborate with at least two signals.
- Missing single-page apps where the stack hides in JS bundles — inspect the bundles.
- Forgetting mobile API backends that share the same domain — test the API surface too.

## References

- MITRE ATT&CK: Gather Victim Network Information (T1590).
- OWASP: fingerprinting web application frameworks.

## Blue-team control under test

This playbook validates their web-asset inventory and patch program should already
reflect these versions — EOL components found here are patch-management gaps. Paired
blue-team counterpart: `cyber_analyzing_web_server_logs_for_intrusion`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
