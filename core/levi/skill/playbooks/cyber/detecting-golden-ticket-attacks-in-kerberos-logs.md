---
skill_id: cyber_detecting_golden_ticket_attacks_in_kerberos_logs
name: Detecting Golden Ticket Attacks in Kerberos Logs
description: Detect forged Kerberos tickets with lifetime, encryption-type, and PAC-validation anomaly analysis.
risk: info
permissions: []
requires_confirmation: false
tags: [active-directory, kerberos, detection]
version: 1.0.0
---
## Purpose

Detect golden tickets — forged Kerberos TGTs created with the stolen KRBTGT hash — by finding the anomalies forged tickets can't avoid: impossible lifetimes, missing logon events, and PAC inconsistencies. The attacker controls the ticket contents, but not how the ticket looks to a careful observer.

## When to use

- Building Kerberos-threat detection for Active Directory.
- Hunting for domain persistence after a suspected KRBTGT compromise.
- Investigating alerts suggesting forged-ticket use.
- Validating that Kerberos logging captures ticket metadata.

## Prerequisites

- Domain controller Security logs centralized: 4768 (TGT requests), 4769 (service tickets), 4624 (logons), 4672 (special privileges).
- Knowledge of domain Kerberos policy: maximum ticket lifetimes, supported encryption types.
- Baseline of normal ticket lifetimes and renewal patterns.
- Authority to reset KRBTGT (twice) on confirmation.

## Procedure

1. **Ensure ticket metadata is logged.** Verify DCs log 4768/4769 with ticket options, encryption types, and lifetimes. Without ticket details in the logs, golden-ticket detection is guesswork — confirm the fields are present before building detections.
2. **Alert on anomalous ticket lifetimes.** Golden tickets commonly use non-standard lifetimes (e.g. 10 years — the Mimikatz default). Alert on TGT lifetimes exceeding domain policy maximums or deviating wildly from the norm. This is the highest-fidelity golden-ticket signal — legitimate tickets obey policy; forged ones obey the attacker's convenience.
3. **Detect tickets without logons.** A golden ticket grants access without a normal authentication sequence. Alert on: service-ticket use (4769) or privileged access with no corresponding 4768 TGT request on a DC, and 4624 network logons for accounts with no recent interactive or TGT activity. The ticket appears from nowhere — that's the anomaly.
4. **Analyze encryption-type anomalies.** Alert on: RC4-encrypted tickets in environments that normally use AES (golden tickets are often RC4), and ticket encryption inconsistent with the account's supported types. Downgrade to weak crypto for ticket forgery is a detectable choice the attacker makes.
5. **Validate PAC consistency.** Alert on PAC anomalies: privileged group memberships in the PAC that don't match the account's actual groups (the classic golden-ticket privilege claim), and PAC validation failures. Compare ticket-claimed privileges against AD ground truth — the ticket lies, the directory doesn't.
6. **Correlate with the KRBTGT compromise.** Golden tickets require the KRBTGT hash. Hunt backward: DCSync events targeting KRBTGT, DC compromises, and the timeframe of the first anomalous ticket. The ticket detection tells you the compromise exists; the KRBTGT timeline tells you its scope.
7. **Respond with double KRBTGT reset.** On confirmation: reset the KRBTGT account password twice (with replication between resets — one reset leaves the previous hash valid for forged tickets), force re-authentication domain-wide, audit all privileged access during the compromise window, and hunt for additional persistence the attacker established with domain-admin-equivalent access.

## Expected outputs

- Kerberos ticket anomaly detections: lifetime, missing-logon, encryption-type, and PAC-validation.
- KRBTGT compromise timeline correlated with first anomalous ticket.
- Double-reset response procedure with domain-wide re-authentication.

## Pitfalls

- Ticket metadata not logged — verify the fields exist before relying on the detection.
- Alerting on lifetime without knowing domain policy — legitimate policy maximums vary; know yours.
- Single KRBTGT reset — the previous hash remains valid; always reset twice.
- Treating the ticket as the incident — the KRBTGT theft is the compromise; find how it happened.
- Ignoring service-ticket anomalies — golden tickets are often used directly for services, skipping obvious TGT patterns.

## References

- Microsoft Learn — Kerberos logging, KRBTGT reset procedures, Event IDs 4768/4769
- MITRE ATT&CK T1558.001 (Steal or Forge Kerberos Tickets: Golden Ticket)
- NIST SP 800-53 IA-5 / SC-23 (authenticator management, session authenticity)
- SANS / DFIR community guidance on golden-ticket detection queries
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
