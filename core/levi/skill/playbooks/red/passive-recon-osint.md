---
skill_id: red_passive_recon_osint
name: Passive Reconnaissance and OSINT
description: Gather intelligence on a target organization without touching its systems: domains, people, technology stack, and exposure.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, reconnaissance, osint, passive]
version: 1.0.0
team: red
tests_blue: cyber_conducting_external_reconnaissance_with_osint
---
# Passive Reconnaissance and OSINT

## Purpose

Map the target's public footprint before any active testing begins. Passive
reconnaissance collects domains, IP ranges, employee names, technology choices, and
leaked credentials from public sources only — no packets sent to target infrastructure.
The output is the target profile that scopes every later active phase and keeps it
inside authorization.

## When to use

- At the start of any authorized assessment, to define scope from public data before
  active scanning.
- When the rules of engagement forbid active probing and only passive collection is
  allowed.
- To build phishing pretexts and target lists from job postings, social media, and
  conference talks.
- To find credential leaks, exposed documents, and forgotten subdomains the blue team
  should have found first.

## Prerequisites

- Scope document listing which organizations, domains, and brands are in-bounds for
  collection.
- Agreement on what counts as public: search engines, certificate logs, code repos,
  social media — never pretexted access.

## Procedure

1. Enumerate the organization's domain portfolio: start from the primary domain, then pull
   certificate transparency logs (crt.sh) for all certificates issued to the org and its
   variants.
2. Resolve each discovered name passively via public DNS history (SecurityTrails-style
   records, DNSDumpster) — never query the target's nameservers directly in this phase.
3. Harvest employee names, roles, and emails from LinkedIn, conference speaker lists, and
   GitHub org membership; build the target list for later social-engineering tests.
4. Search code repositories (GitHub, GitLab) for the org's name plus secrets keywords;
   record any live API keys, tokens, or internal hostnames — report immediately, do not
   use them.
5. Check breach corpora (HaveIBeenPwned, DeHashed-style sources) for employee credentials
   that password-spraying tests will later validate against policy.
6. Map the technology stack from job postings ("we use Okta, CrowdStrike, Palo Alto"),
   Wappalyzer-style public scans others published, and vendor case studies.
7. Collect all findings into a target profile: domains, IPs (from public BGP/ASN data), key
   personnel, tech stack, and third-party exposure — hand this to the blue team as the
   recon report card.

## Expected outputs

- Target profile document: domains, subdomains, IP ranges, personnel, tech stack.
- List of public exposures (leaked creds, exposed docs, forgotten assets) with
  timestamps.
- Scoped target list for the active phases, each entry tied to an in-scope asset.

## Pitfalls

- Drifting into active probing (port scans, direct DNS queries) during a passive-only
  phase — log every query source.
- Collecting on out-of-scope entities with similar names; verify org affiliation before
  recording.
- Using discovered credentials instead of reporting them — that crosses from recon into
  unauthorized access.

## References

- MITRE ATT&CK: Gather Victim Identity Information (T1589), Search Open Technical
  Databases (T1596).
- OWASP: public OSINT guidance for penetration testing.

## Blue-team control under test

This playbook validates the blue team's own OSINT and exposure monitoring should have
found the same public footprint first — every finding here is a gap in their external
attack-surface management. Paired blue-team counterpart:
`cyber_conducting_external_reconnaissance_with_osint`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
