---
skill_id: red_certificate_transparency_mining
name: Certificate Transparency Mining
description: Mine public certificate transparency logs for a target's domains to reveal infrastructure without sending a single packet to the target.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, reconnaissance, certificate-transparency, passive]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_certificate_transparency_for_phishing
---
# Certificate Transparency Mining

## Purpose

Certificate transparency logs are a public, append-only record of every certificate
issued for a domain. Mining them reveals subdomains, internal hostnames accidentally
exposed, cloud front-ends, and partner integrations — entirely passively. It is often
the single highest-yield passive technique available.

## When to use

- During passive recon, before any active phase begins.
- When the ROE restricts active probing but public data mining is allowed.
- To find internal hostnames (vpn-internal, jira-dev) leaked into public certificates.
- To monitor for rogue certificates issued for the org's domains (defensive use too).

## Prerequisites

- Scope limited to the target's domains and obvious variants.
- No target contact occurs, so authorization is for collection and reporting only.

## Procedure

1. Query crt.sh for `%.target.com` and export the full certificate list, including expired
   certificates — old certs reveal retired infrastructure worth checking.
2. Extract every unique dNSName, normalize (strip wildcards), and deduplicate into a
   candidate subdomain list.
3. Repeat against at least one second CT source (Censys, Google's CT search) to catch log-
   sharding gaps.
4. Flag internal-looking names (intranet, vpn, dev, staging, mgmt, backup) and names
   pointing at SaaS/cloud providers.
5. Cross-reference with the passive DNS history to date each name's first and last
   sighting.
6. Deliver the CT-derived inventory to the blue team with a note on which internal names
   should never have been in public certificates.

## Expected outputs

- Deduplicated subdomain/hostname list sourced purely from CT logs.
- Internal-name exposure findings with certificate serials as evidence.
- Historical view: first/last seen dates per name.

## Pitfalls

- CT logs lag issuance by hours — very new certs may be missing; re-query before active
  phases.
- Pre-certificates and duplicates inflate counts; deduplicate on the parsed dNSName set.
- Assuming CT coverage is complete — some private CAs don't log; combine with other
  passive sources.

## References

- MITRE ATT&CK: Search Open Technical Databases — CT logs (T1596.005).
- RFC 6962: Certificate Transparency.

## Blue-team control under test

This playbook validates their certificate inventory and issuance policy should already
track every name found — internal hostnames in public certs are a policy failure to
remediate. Paired blue-team counterpart:
`cyber_analyzing_certificate_transparency_for_phishing`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
