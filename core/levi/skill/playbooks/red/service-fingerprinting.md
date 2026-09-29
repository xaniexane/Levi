---
skill_id: red_service_fingerprinting
name: Service Fingerprinting
description: Identify exact services and versions behind open ports to target vulnerability validation precisely and avoid blind exploitation.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, reconnaissance, fingerprinting]
version: 1.0.0
team: red
tests_blue: cyber_detecting_network_reconnaissance_and_port_scanning
---
# Service Fingerprinting

## Purpose

Turn 'port 443 open' into 'nginx 1.18.0 on Ubuntu with a 2019 OpenSSL'. Precise service
fingerprinting lets later phases test only vulnerabilities that plausibly apply, which
keeps the exercise safe and credible. It also exposes version-disclosure
misconfigurations the blue team should have suppressed.

## When to use

- Immediately after port scanning, before any vulnerability validation.
- When the blue team claims banner obfuscation is in place — verify it.
- To build the version inventory that vulnerability mapping consumes.

## Prerequisites

- Authorization covering the scanned hosts; fingerprinting is active probing.
- Same rate/window constraints as the network scan phase.

## Procedure

1. Run Nmap version detection (`-sV --version-intensity 5`) against all open ports found in
   the scan phase.
2. Manually verify ambiguous results: pull HTTP headers, TLS certificates, SMTP/FTP/SSH
   banners, and SMB dialects by hand.
3. Check for version-disclosure headers (Server, X-Powered-By) and verbose error pages that
   leak stack details.
4. Fingerprint web applications with technology-detection tools and manual inspection
   (cookies, JS bundles, HTML comments).
5. Record exact product + version + OS guess per service in a structured inventory.
6. Map each version to known CVEs (offline database, never live exploit-db queries from the
   range) to build the candidate vulnerability list.
7. Flag information-disclosure findings (verbose banners, debug endpoints) separately —
   they are blue-team hardening gaps even before any exploitation.

## Expected outputs

- Service/version inventory per host with confidence notes.
- Candidate vulnerability map (version → CVE) for the exploitation phase.
- Information-disclosure findings with evidence.

## Pitfalls

- Trusting a single banner — load balancers and WAFs lie; verify behind them where in
  scope.
- Version-intensity 9+ probes can crash fragile services; keep intensity moderate on
  unknown hosts.
- Confusing honeypot banners with real services; note anomalies for the blue team.

## References

- MITRE ATT&CK: Network Service Discovery (T1046).
- OWASP: fingerprinting web application frameworks.

## Blue-team control under test

This playbook validates every version disclosed is a hardening input — their baseline
should suppress banners and their vuln-management should already track these versions.
Paired blue-team counterpart:
`cyber_detecting_network_reconnaissance_and_port_scanning`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
