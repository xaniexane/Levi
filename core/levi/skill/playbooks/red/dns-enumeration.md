---
skill_id: red_dns_enumeration
name: DNS Enumeration
description: Enumerate a target's DNS footprint — zone transfers, record types, and brute-forced names — to map infrastructure the blue team must defend.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, reconnaissance, dns]
version: 1.0.0
team: red
tests_blue: cyber_performing_dns_enumeration_and_zone_transfer
---
# DNS Enumeration

## Purpose

Turn a domain name into an infrastructure map. DNS enumeration attempts zone transfers,
queries every record type, and brute-forces likely hostnames to reveal mail servers, VPN
endpoints, dev systems, and cloud assets. Everything found becomes a candidate target
for later phases — and a finding for the blue team if it was exposed unintentionally.

## When to use

- Early in the active recon phase, after passive collection has defined the domain set.
- When testing whether the organization's DNS servers permit zone transfers (AXFR).
- To discover forgotten dev/staging hostnames that never made it into asset inventory.
- Before phishing tests, to identify mail exchangers and SPF/DKIM/DMARC posture.

## Prerequisites

- Written authorization naming the domains and nameservers in scope.
- Rate limits agreed: DNS brute-forcing can look like a DoS against small authoritative
  servers.

## Procedure

1. Attempt a zone transfer (AXFR) against each authoritative nameserver: `dig axfr
   @ns1.target.com target.com`. Record success or refusal — a successful transfer is
   itself a finding.
2. Query all standard record types (A, AAAA, MX, TXT, SRV, CNAME, NS, SOA) and note TTLs,
   mail exchangers, and TXT records leaking internal tooling.
3. Run DNS brute-forcing with a curated wordlist (subdomains-top1mil style) against the
   domain, throttled to the agreed rate; resolve candidates and fingerprint responses.
4. Probe for DNS zone walking on DNSSEC-signed zones (NSEC enumeration) to recover the full
   zone contents without brute force.
5. Check for subdomain takeover candidates: CNAME records pointing at deprovisioned cloud
   services (S3, Azure, Heroku, GitHub Pages).
6. Validate every discovered hostname: resolve, check HTTP response, and classify (prod,
   dev, forgotten, third-party) before adding it to the target list.
7. Deliver the DNS map to the blue team with each record annotated: expected, forgotten, or
   misconfigured.

## Expected outputs

- Complete DNS record inventory per in-scope domain, including AXFR result.
- List of brute-forced hostnames with classification and HTTP fingerprints.
- Subdomain-takeover candidates with proof of dangling CNAME.

## Pitfalls

- Aggressive brute-forcing tripping the target's rate limits or looking like an attack
  from an unrecognized source — stay inside the agreed rate and source IPs.
- Treating wildcard DNS responses as real hosts; always verify with a canary query.
- Forgetting to test the secondary/hidden nameservers, not just the primaries.

## References

- MITRE ATT&CK: Gather Victim Network Information — DNS (T1590.002).
- OWASP Testing Guide: DNS enumeration.

## Blue-team control under test

This playbook validates their DNS monitoring and asset inventory should account for
every name found — AXFR success or dangling CNAMEs are blue-team misconfigurations to
fix. Paired blue-team counterpart: `cyber_performing_dns_enumeration_and_zone_transfer`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
