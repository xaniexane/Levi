---
skill_id: cyber_detecting_pass_the_ticket_attacks
name: Detecting Pass-the-Ticket Attacks
description: Detect Pass-the-Ticket Kerberos abuse via ticket anomalies and event correlation.
risk: low
permissions: []
requires_confirmation: false
tags: [active-directory, kerberos, detection]
version: 1.0.0
---
## Purpose

Pass-the-Ticket (PtT) replays stolen Kerberos tickets — including forged golden/silver tickets — to authenticate without passwords. Because Kerberos is the normal authentication protocol, PtT hides in legitimate traffic. This playbook focuses on the ticket anomalies that expose it: lifetime, encryption, and request-pattern deviations in domain controller logs.

## When to use

- Kerberos is your primary auth protocol and you need PtT coverage.
- A golden/silver ticket attack is suspected and you need a hunting procedure.
- SIEM Kerberos rules exist but miss forged-ticket indicators.
- Validating detection after a KRBTGT or service-account compromise.

## Prerequisites

- Domain Controller Security logs: Event IDs 4768 (TGT requested), 4769 (service ticket requested), 4771 (Kerberos pre-auth failure), with ticket options, encryption types, and lifetimes.
- Knowledge of your domain's normal ticket lifetimes and encryption negotiation (Kerberos policy settings).
- KRBTGT password-change history (double-change status) for golden-ticket context.
- Time synchronization across DCs (Kerberos anomalies often involve clock skew).

## Procedure

1. Learn the forged-ticket indicators. Golden tickets (forged TGTs) and silver tickets (forged service tickets) betray themselves through: ticket lifetimes far exceeding domain policy (e.g., 10-year lifetimes), encryption types inconsistent with the account's supported types, tickets presented without a corresponding 4768/4769 request event on any DC (the ticket was never legitimately issued), and PAC anomalies (privilege claims inconsistent with group membership).
2. Alert on lifetime anomalies. Compare ticket lifetimes in 4769/4768 against domain Kerberos policy (default max 10 hours). Tickets with lifetimes dramatically exceeding policy — especially round numbers like years — are the classic golden-ticket signature. This single check catches unsophisticated forgeries reliably.
3. Alert on encryption-type mismatches. If an account negotiates AES normally but a ticket appears with RC4, or the ticket encryption doesn't match what the KDC would issue for that principal, investigate. Attackers forging tickets choose the encryption they can compute — often RC4 with a cracked hash.
4. Hunt for tickets without issuance events. A service ticket used at a server (visible in the server's logs or via 4769 on the DC... for silver tickets there is no 4769 at all) with no corresponding KDC-issued ticket in DC logs indicates forgery. Centralize DC logs and join: every legitimate service ticket should have a 4769; orphans are forged.
5. Correlate with compromise precursors. PtT needs stolen ticket material: look for DCSync (4662), LSASS dumping, or KRBTGT hash exposure preceding the anomalous tickets. A golden ticket implies KRBTGT compromise — which requires double KRBTGT password resets and a full forest-recovery assessment, not just ticket blocking.
6. Respond to ticket forgery at the right scope. Silver ticket: reset the targeted service account's password (invalidates forged service tickets). Golden ticket: double-reset KRBTGT (two resets, allowing replication between), reset all privileged credentials, and hunt for persistence established during the ticket's validity window — which may be years.

## Expected outputs

- PtT detection rules: lifetime anomaly, encryption mismatch, orphan-ticket (no issuance event) hunting.
- Kerberos policy baseline: lifetimes, encryption types, documented per domain.
- Golden-ticket response procedure: KRBTGT double-reset, forest-wide credential reset, historical hunt.
- KRBTGT reset history and ticket-policy documentation.

## Pitfalls

- Sophisticated forgeries mimic policy lifetimes and AES — lifetime checks catch the common case, not APT-grade forgeries.
- Clock skew causes legitimate-looking anomalies; verify NTP health before treating time fields as evidence.
- Silver tickets generate no 4769 — you need server-side or network visibility, not just DC logs.
- A single KRBTGT reset doesn't kill golden tickets (old + new hash both valid during overlap) — always double-reset.
- Treating PtT as an account problem when it's a KRBTGT problem leads to incomplete remediation.

## References

- MITRE ATT&CK T1558.001 (Golden Ticket), T1558.002 (Silver Ticket) — https://attack.mitre.org/techniques/T1558/001/; Microsoft Learn: Kerberos ticket lifetimes, KRBTGT reset guidance
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
