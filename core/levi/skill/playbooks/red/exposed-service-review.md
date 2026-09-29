---
skill_id: red_exposed_service_review
name: Exposed Service Review
description: Review the target's internet-exposed services via third-party scan data to find forgotten RDP, databases, and management interfaces.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, reconnaissance, exposure]
version: 1.0.0
team: red
tests_blue: cyber_defending_against_subdomain_enumeration_and_osint_exposure
---
# Exposed Service Review

## Purpose

Use third-party internet scan datasets (the Shodan/Censys model) to review what the
target exposes to the internet — without scanning it yourself. Forgotten RDP, databases,
Elasticsearch, and management interfaces show up here first. This is the cheapest high-
value recon available and entirely passive.

## When to use

- During passive recon, to prioritize which exposed services deserve active testing.
- When the ROE forbids active scanning but third-party data review is allowed.
- Quarterly as a purple-team hygiene check: has the exposure changed?

## Prerequisites

- Scope: the target's netblocks and domains; third-party data only, no direct probing in
  this phase.

## Procedure

1. Query internet-scan datasets for the target's ASN/netblocks; pull banners for all
   exposed services.
2. Filter for high-risk exposures: RDP (3389), SMB (445), databases (3306/5432/27017/6379),
   Elasticsearch (9200), management (22 with default creds hints, 8080, 8443).
3. Check each exposure's banner for default credentials indicators, version disclosure, and
   honeypot signatures.
4. Cross-reference exposures against the blue team's declared internet footprint — anything
   undeclared is a finding.
5. Prioritize the exposure list by exploitability and data sensitivity for the active
   testing phases.
6. Deliver the exposure review with screenshots and first-seen dates from the scan
   datasets.

## Expected outputs

- Prioritized internet-exposure inventory with banners and first-seen dates.
- Undeclared-exposure findings (in scan data but not in the blue team's footprint).
- Targeting priority list for active phases.

## Pitfalls

- Stale scan data — verify critical exposures are still live before building test plans
  on them.
- Honeypots in scan datasets — note them; the blue team may be running deception you
  should account for.
- Confusing CDN/WAF IPs with origin infrastructure.

## References

- MITRE ATT&CK: Gather Victim Network Information (T1590).
- Internet-scan dataset documentation (Shodan/Censys query syntax).

## Blue-team control under test

This playbook validates their external attack-surface program should produce this same
list continuously — any delta is a monitoring gap, not just a finding. Paired blue-team
counterpart: `cyber_defending_against_subdomain_enumeration_and_osint_exposure`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
