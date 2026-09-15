---
skill_id: cyber_detecting_golden_ticket_forgery
name: Detecting Golden Ticket Forgery
description: Detect the creation and first use of forged Kerberos tickets with forensic timeline analysis.
risk: info
permissions: []
requires_confirmation: false
tags: [active-directory, kerberos, forensics]
version: 1.0.0
---
## Purpose

Detect golden-ticket forgery itself — the moment of creation and the first fraudulent use — through forensic timeline analysis of KRBTGT access, ticket anomalies, and the attacker's operational pattern. Where the Kerberos-logs playbook covers steady-state detection, this one covers the forgery event and its forensic reconstruction.

## When to use

- Forensic investigation of a suspected KRBTGT compromise.
- Determining when forged tickets were created and first used (scoping the incident window).
- Hunting for forgery tooling artifacts on compromised hosts.
- Validating that forgery-detection controls work (purple-team exercises).

## Prerequisites

- Full AD forensic timeline: DC security logs, KRBTGT-related events, host forensics from suspected attacker workstations.
- Memory/disk images from hosts where forgery tooling may have run (if available).
- Baseline of legitimate KRBTGT and ticket activity.
- Understanding of the Kerberos ticket structure for forensic analysis.

## Procedure

1. **Establish the KRBTGT compromise timeline.** Identify when the KRBTGT hash was stolen: DCSync events, DC compromise indicators, or secretsdump artifacts. The forgery window starts here — no forged ticket predates the hash theft. This timeline anchors the entire investigation.
2. **Find the first anomalous ticket.** Search backward from the detection for the earliest ticket with forgery indicators: non-standard lifetime, RC4 in an AES environment, or privileged PAC claims inconsistent with the account. The first forgery marks the attacker's operational start — everything before it is initial access, everything after is exploitation.
3. **Reconstruct the forgery parameters.** From the anomalous tickets, infer: the ticket lifetime chosen (tool defaults vs. custom), the encryption type, the claimed username and groups, and the target services. These parameters fingerprint the tooling and the attacker's intent — a 10-year ticket for Domain Admins tells a different story than a 10-hour ticket for a service account.
4. **Hunt forgery-tooling artifacts.** On the attacker's likely hosts, look for: credential-dumping tool execution, ticket files (`.kirbi`) on disk, command-line history showing ticket-forging commands, and the source of the KRBTGT hash (memory dump of LSASS on a DC, DCSync logs). The tooling artifacts corroborate the log-based findings.
5. **Map the forged ticket's use.** Trace every service accessed with forged tickets: which hosts, which data, which subsequent actions (lateral movement, persistence creation, data access). Forged tickets grant domain-admin-equivalent access — assume the attacker did everything, and use the logs to prove what they actually did.
6. **Distinguish forgery from legitimate anomalies.** Rule out: clock-skew artifacts (check time synchronization before crying forgery), legitimate administrative tools with unusual ticket parameters, and cross-domain trust ticket quirks. Forensic rigor here prevents false incident declarations — but don't let perfect be the enemy of response when multiple indicators align.
7. **Eradicate and verify.** Reset KRBTGT twice, invalidate all existing tickets domain-wide (forced re-authentication), remove persistence the attacker created with forged access, and then verify: monitor for new anomalous tickets for 30+ days post-reset. A new forgery after double-reset means the attacker re-stole the hash — the investigation isn't over.

## Expected outputs

- A forensic timeline: hash theft → first forgery → ticket use → detection, with tooling artifacts.
- Reconstructed forgery parameters fingerprinting the attacker's methods and intent.
- Double-reset eradication with 30-day post-reset monitoring for re-forgery.

## Pitfalls

- Confusing clock skew with forgery — verify time sync before declaring tickets anomalous.
- Stopping at the first forged ticket — map the full use; the blast radius is what matters.
- Single KRBTGT reset — always twice, with replication between.
- No post-reset monitoring — re-forgery means re-compromise; watch for it.
- Treating tool-default parameters as attacker sophistication — the defaults tell you about the tool, not the operator.

## References

- Microsoft Learn — Kerberos ticket structure, KRBTGT management
- MITRE ATT&CK T1558.001 (Steal or Forge Kerberos Tickets: Golden Ticket)
- SANS / DFIR resources on Kerberos forensic analysis
- NIST SP 800-61 Rev. 2 — forensic investigation methodology
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
