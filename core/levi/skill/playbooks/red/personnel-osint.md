---
skill_id: red_personnel_osint
name: Personnel OSINT for Pretexting
description: Build targeted personnel profiles from public sources to craft believable pretexts for authorized social-engineering tests.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, reconnaissance, osint, social-engineering]
version: 1.0.0
team: red
tests_blue: cyber_building_threat_actor_profile_from_osint
---
# Personnel OSINT for Pretexting

## Purpose

Social-engineering tests succeed or fail on pretext quality, and pretext quality comes
from personnel OSINT: who works where, who reports to whom, what projects they discuss
publicly, what their writing style looks like. This playbook builds those profiles from
public sources only, producing the raw material for authorized phishing and vishing
tests.

## When to use

- Before any authorized phishing, vishing, or physical social-engineering test.
- To identify high-value targets (finance, IT admins, executives) within scope.
- To test whether the org's public footprint makes pretexting trivially easy.

## Prerequisites

- Social-engineering authorization in the ROE: named techniques allowed, target groups,
  and no-go topics (medical, family emergencies).
- Agreement that no pretext will impersonate law enforcement, and no real credentials
  will be harvested beyond proof-of-click.

## Procedure

1. Enumerate in-scope personnel from LinkedIn, company team pages, and conference programs;
   record name, role, manager hints, and tenure.
2. Build org-chart approximations from reporting-line hints in bios ("reports to the CISO",
   team sizes).
3. Collect writing-style samples from public posts and talks for pretext realism (tone,
   jargon, signature blocks).
4. Identify opportune pretexts: new-hire onboarding, IT helpdesk, vendor invoices,
   conference follow-ups — all tied to real public facts.
5. Rank targets by role sensitivity and public exposure; submit the target list for client
   approval before any contact.
6. Document which public sources yielded each profile element — this becomes the blue
   team's awareness-training material.

## Expected outputs

- Approved target list with role sensitivity rankings.
- Pretext dossiers per target: public facts, plausible scenario, approved contact
  method.
- Source map showing which public disclosures enabled each pretext (training input).

## Pitfalls

- Contacting anyone before the target list is approved — the ROE approval is the
  control.
- Using non-public or hacked data sources for profiling; stay strictly public.
- Pretexts that cause real distress (layoffs, emergencies) — banned by any sane ROE;
  keep them boring and professional.

## References

- MITRE ATT&CK: Gather Victim Identity Information (T1589), Phishing (T1566).
- Social-Engineer Framework: OSINT methodology (public).

## Blue-team control under test

This playbook validates the source map doubles as their security-awareness curriculum —
every public disclosure that enabled a pretext is a coaching opportunity, not just a
test setup step. Paired blue-team counterpart:
`cyber_building_threat_actor_profile_from_osint`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
