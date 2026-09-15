---
skill_id: cyber_relaying_ntlm_for_adcs_esc8
name: Detecting and Hardening Against NTLM Relay to ADCS (ESC8)
description: Detect NTLM relay attacks against AD CS HTTP enrollment and harden certificate services against ESC8.
risk: info
permissions: []
requires_confirmation: false
tags: [active-directory, detection, hardening]
version: 1.0.0
---
## Purpose
ESC8 abuses NTLM relay against Active Directory Certificate Services HTTP enrollment endpoints to mint certificates as other identities. This playbook is defensive: how to determine whether your AD CS deployment is exposed, how to hunt for relay and anomalous certificate issuance, and how to harden enrollment with Extended Protection, signing requirements, and disabled HTTP enrollment where possible. No relay tooling or attack steps are included.

## When to use
- Hardening review of an AD CS deployment.
- Threat hunting after suspected NTLM relay or PetitPotam-style coercion activity.
- After a penetration test flags AD CS as an escalation path.
- Designing certificate services for a new Active Directory forest.

## Prerequisites
- Inventory of AD CS servers, roles (CA, web enrollment), and enrollment endpoints.
- Access to CA logs, Windows Security event logs from DCs and CA servers.
- Authority to change CA and enrollment configuration (coordinate with PKI owners).
- Baseline of normal certificate issuance volume and requester identities.

## Procedure
1. Inventory enrollment interfaces: identify any HTTP (non-TLS) CES/CEP or web enrollment endpoints.
2. Disable HTTP enrollment where business needs allow; require HTTPS with Extended Protection for Authentication on remaining endpoints.
3. Enforce SMB signing and LDAP signing/channel binding domain-wide to shrink relay opportunities.
4. Apply Microsoft's PetitPotam mitigations (KB5005413 guidance) to block authentication coercion paths.
5. Hunt: look for NTLM authentications to CA servers followed by certificate requests (Event IDs 4886/4887) from unusual requesters.
6. Review issued certificates for anomalies: unexpected subject names, lifetime, or templates (especially enrollment-agent or UPN-mismatched certs).
7. Alert on certificate issuance outside change windows or by service accounts that never previously requested certs.
8. Document the hardened configuration and re-audit after any AD CS changes.
9. Audit certificate templates for ESC1/ESC3 misconfigurations in the same review; relay is only one ADCS attack path.
10. Verify that web enrollment (CES/CEP) endpoints are inventoried, including decommissioned-but-running servers.
11. Test Extended Protection settings in a lab CA before enforcing them in production.

## Expected outputs
- AD CS exposure assessment with remediated enrollment configuration.
- Hunt queries for relay-to-CA patterns and anomalous issuance.
- Ongoing monitoring rule for unexpected certificate requests.
- Full ADCS attack-surface inventory (endpoints, templates, permissions).
- Lab validation report for Extended Protection changes.
- Template misconfiguration findings alongside relay hardening.

## Pitfalls
- Disabling HTTP enrollment can break legacy clients; inventory dependencies first.
- EPA misconfiguration causes enrollment outages; test in a lab CA before production.
- Relay leaves subtle traces; absence of logs is not absence of attack if logging was thin.
- Certificate templates are the other half of ADCS risk; review ESC1-ESC7 misconfigurations alongside ESC8.
- Extended Protection can break non-Windows enrollment clients; test client compatibility.
- Decommissioned CA servers are often still online; inventory must be verified, not assumed.
- Focusing only on ESC8 while ESC1 templates remain misconfigured leaves easier paths open.
- NTLM auditing must be enabled before you need it; without it, relay hunts have no data.

## References
- Microsoft Learn: AD CS hardening and KB5005413 (PetitPotam mitigations).
- MITRE ATT&CK: Adversary-in-the-Middle (T1557), Steal or Forge Authentication Certificates (T1649).
- CISA guidance on Active Directory hardening.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
