---
skill_id: cyber_detecting_kerberoasting_attacks
name: Detecting Kerberoasting Attacks
description: Detect and investigate Kerberoasting — offline cracking of service-account tickets — via Windows event logs.
risk: low
permissions: []
requires_confirmation: false
tags: [active-directory, kerberos, detection]
version: 1.0.0
---
## Purpose

Kerberoasting lets any authenticated domain user request a service ticket (TGS) for an account with a Service Principal Name, then crack it offline to recover the account's password — often a privileged service account. This playbook is purely defensive: recognizing the request patterns in domain controller logs, distinguishing them from legitimate ticket traffic, and responding before cracked credentials are reused.

## When to use

- A SIEM rule fires on unusual Ticket-Granting-Service request volume.
- You are hardening Active Directory and need detection coverage for credential-access techniques.
- Threat hunting for stealthy credential theft that leaves no malware on disk.
- After finding a service account with a weak or old password, you want to know if it was already targeted.

## Prerequisites

- Domain Controller Security logs (or forwarded events) with Kerberos service-ticket operations logging enabled; specifically Event ID 4769 (a Kerberos service ticket was requested).
- Centralized log collection from all DCs — Kerberoasting requests can hit any DC.
- An inventory of accounts with SPNs (service accounts) and their privilege levels.
- Baseline knowledge of normal TGS request rates per host/user in your environment.

## Procedure

1. Enable and verify the right logging. Confirm Event ID 4769 is collected from all DCs with the service name, client address, and ticket encryption type fields. Without the encryption type you cannot apply the strongest detection filter.
2. Filter 4769 events for RC4-encrypted tickets. Legitimate modern services negotiate AES; Kerberoasting tools historically request RC4 (encryption type 0x17) because RC4-HMAC tickets are crackable. Alert on 4769 with Ticket Encryption Type 0x17, especially from user workstations rather than servers.
3. Look for enumeration-then-request patterns. Attackers first enumerate SPNs (LDAP queries for servicePrincipalName attributes) and then request many tickets in a short window. Correlate: one user requesting TGS tickets for many distinct service accounts within minutes is the classic signature.
4. Check the client address and account. Requests originating from a user workstation (not a server or admin jump host), under a standard user account rather than SYSTEM or a service account, requesting tickets for high-value SPNs (SQL, HTTP on sensitive servers) deserve immediate investigation.
5. Investigate the requesting host. If the pattern holds, treat the host as compromised: capture memory and EDR telemetry, look for credential-dumping or ticket-request tooling artifacts, and identify patient zero and lateral movement.
6. Force rotation on targeted service accounts. Any service account whose ticket was requested with RC4 should have its password rotated immediately (coordinate with service owners — this can break services) and upgraded to a long, random, managed password; consider group Managed Service Accounts (gMSAs) where possible.
7. Harden to prevent recurrence: audit all SPNs, remove stale ones, enforce AES-only where possible, use gMSAs, and set long random passwords on remaining service accounts.

## Expected outputs

- SIEM detection rule(s) for RC4 TGS requests + enumeration correlation, with tested true/false positive rates.
- Investigation report: requesting host, user, targeted SPNs, timeline, and disposition.
- Service-account inventory with password-rotation status and gMSA migration candidates.
- Hardening actions: stale SPN removals, AES enforcement, privileged-account review.

## Pitfalls

- RC4 tickets also appear in legitimate legacy traffic — baseline before alerting or you will drown in false positives.
- Attackers can request AES tickets too; RC4 filtering catches the common case, not every case. Pair with volume/anomaly detection.
- 4769 volume is enormous in large domains — aggregate by client+user+service and alert on cardinality, not raw events.
- Rotating a service account password without coordinating with the service owner causes outages — plan rotations, don't improvise.
- A single DC's logs are not enough; load-balanced ticket requests spread across DCs, so centralize first.

## References

- MITRE ATT&CK T1558.003 (Steal or Forge Kerberos Tickets: Kerberoasting) — https://attack.mitre.org/techniques/T1558/003/; Microsoft Learn: Kerberos event logging and service ticket operations; NIST SP 800-63B (authenticator management)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
