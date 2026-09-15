---
skill_id: cyber_performing_dns_enumeration_and_zone_transfer
name: DNS Enumeration and Zone Transfer Hardening
description: Assess your DNS exposure to enumeration and zone transfers, and harden authoritative servers.
risk: low
permissions: []
requires_confirmation: false
tags: [dns, assessment, hardening]
version: 1.0.0
---

## Purpose

DNS is a public directory of your infrastructure: hostnames reveal applications, environments, cloud regions, and sometimes internal structure attackers should never see. Zone transfers (AXFR) hand over the entire directory at once, and verbose DNS responses leak more than necessary. This playbook is defensive: test whether your authoritative servers permit zone transfers to unauthorized parties, audit what your DNS exposes, monitor for enumeration, and harden configurations. Testing is limited to domains you own or are authorized to assess.

## When to use

- Auditing DNS security for domains you manage.
- After discovering internal hostnames or infrastructure details in public DNS data.
- Validating a finding that your nameservers allow AXFR.
- Reducing reconnaissance value of your DNS footprint.
- Investigating suspected DNS reconnaissance against your zones.

## Prerequisites

- Authorization covering the domains and nameservers under test.
- List of authoritative nameservers and DNS providers for your zones.
- DNS tooling: `dig`, `host`, `nslookup`, and optionally a DNS enumeration framework for your own domains.
- Access to authoritative server configuration (or the provider console) for remediation.
- DNS query logging (if available) for detecting enumeration patterns.

## Procedure

1. **Test zone transfers from an untrusted vantage point.** For each nameserver, attempt `dig AXFR yourdomain @nameserver`. Any successful transfer to an unauthorized requester is a finding — restrict AXFR to designated secondary servers via ACLs/TSIG immediately. Test all nameservers, not just the primary; secondaries are often misconfigured.
2. **Audit zone contents for exposure.** Review every record in the transferred (or otherwise visible) zone: internal hostnames, management interfaces, staging environments, VPN endpoints, and TXT records containing sensitive data. Each record is a reconnaissance gift — remove or obscure what does not need to be public.
3. **Check for information leakage in responses.** Query for version.bind / version.server (CHAOS class) to see if nameserver software versions are disclosed, test for zone walking on DNSSEC-signed zones (NSEC vs. NSEC3 — NSEC permits full enumeration), and review wildcard records that confirm-or-deny existence.
4. **Harden authoritative configuration.** Restrict AXFR/IXFR to secondaries via IP ACL plus TSIG keys; disable recursion on authoritative servers; minimize version disclosures; prefer NSEC3 with opt-out and salt for DNSSEC zones; and split public/private views so internal hostnames never appear in the public zone.
5. **Reduce the useful footprint.** Remove stale records (decommissioned hosts are still recon value), avoid descriptive internal naming in public zones (`db-primary-prod-east` tells a story), and keep TTLs sensible — very long TTLs preserve your mistakes in caches worldwide.
6. **Monitor for enumeration.** Alert on: AXFR attempts from unauthorized sources (which should now fail, but attempts indicate interest), high-volume subdomain brute-forcing against your nameservers, and certificate-transparency-driven discovery spikes correlating with scanning of your infrastructure.
7. **Verify and document.** Re-test transfers after hardening from multiple vantage points, confirm NSEC3 deployment, and record the hardened configuration as the standard for all zones. Add AXFR-ACL checks to periodic DNS audits.

## Expected outputs

- Zone-transfer test results per nameserver, with remediation of any unauthorized AXFR.
- Zone content audit: exposed internal hostnames and sensitive records removed or justified.
- Hardened authoritative configuration: TSIG/ACL-restricted transfers, no recursion, minimized disclosures.
- DNSSEC enumeration assessment (NSEC3 status) and split-view implementation where needed.
- Monitoring rules for AXFR attempts and subdomain enumeration against your zones.

## Pitfalls

- Fixing the primary nameserver but leaving a secondary open to AXFR — test every authoritative server.
- Using NSEC instead of NSEC3 on signed zones, which permits trivial zone walking.
- Descriptive public hostnames that map your entire infrastructure for attackers.
- Assuming DNS providers "handle it" — verify transfer restrictions in your provider's actual configuration.
- Blocking AXFR but leaving the same data exposed via verbose zone files in public repos or misconfigured APIs.

## References

- RFC 5936 (AXFR), RFC 1995 (IXFR), RFC 5155 (NSEC3)
- NIST SP 800-81, "Secure Domain Name System (DNS) Deployment Guide"
- DNS-OARC guidance on authoritative server operations
- CISA guidance on DNS security
- `dig` manual (BIND) for AXFR testing syntax
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
