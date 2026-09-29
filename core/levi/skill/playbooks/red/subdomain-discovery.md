---
skill_id: red_subdomain_discovery
name: Subdomain Discovery
description: Discover subdomains via certificate logs, brute-forcing, and search engines to expose forgotten assets for the blue team to inventory.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, reconnaissance, subdomain]
version: 1.0.0
team: red
tests_blue: cyber_performing_subdomain_enumeration_with_subfinder
---
# Subdomain Discovery

## Purpose

Find every subdomain — including the forgotten dev, staging, and marketing sites the
organization lost track of. Subdomain discovery combines certificate-transparency
mining, brute-forcing, search-engine dorking, and alt-DNS sources. Each forgotten
subdomain is a potential initial-access vector and a blue-team inventory gap.

## When to use

- During active recon, to build the full web-attack surface before application testing.
- When the org has undergone M&A and inherited unknown DNS estates.
- To feed takeover testing: every CNAME to an external service is a candidate.
- As a purple-team exercise: compare red's discovered list against blue's CMDB.

## Prerequisites

- Authorization covering the parent domains; discovered subdomains of the same org are
  in scope by definition.
- Agreed wordlists and throttling for brute-force phases.

## Procedure

1. Pull certificate transparency logs for the target domains (crt.sh, censys-style CT
   search) and extract every dNSName — this usually yields the largest initial set.
2. Run subdomain brute-forcing with a tiered wordlist (small, then large) using massdns or
   gobuster-style tools at the agreed rate; resolve and keep only live names.
3. Query search engines with site: dorks and pull results from VirusTotal/URLScan-style
   passive sources for historical subdomains.
4. Attempt DNS zone transfers and NSEC walking as a secondary source (see the DNS
   enumeration playbook).
5. Probe each live subdomain with HTTP/HTTPS, record status codes, titles, and server
   banners; screenshot the interesting ones.
6. Classify each finding: production, staging/dev, marketing, forgotten, third-party-
   hosted, takeover-candidate.
7. Hand the classified inventory to the blue team — the delta between this list and their
   CMDB is the exercise score.

## Expected outputs

- Classified subdomain inventory with HTTP fingerprints and screenshots of interest.
- Takeover-candidate list with dangling-service evidence.
- CMDB delta report for the blue team.

## Pitfalls

- Counting wildcard-DNS artifacts as real subdomains — verify with randomized canary
  labels.
- Stopping at CT logs; the long tail of forgotten assets usually comes from brute-
  forcing.
- Scanning third-party-hosted subdomains aggressively — respect the hosting provider's
  acceptable-use terms in the ROE.

## References

- MITRE ATT&CK: Gather Victim Network Information — Domain Properties (T1590.002).
- OWASP: subdomain enumeration methodology.

## Blue-team control under test

This playbook validates their external asset inventory should already contain every name
found — the delta is the measurable outcome of this test. Paired blue-team counterpart:
`cyber_performing_subdomain_enumeration_with_subfinder`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
