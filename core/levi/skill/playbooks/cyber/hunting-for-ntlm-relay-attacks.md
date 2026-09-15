---
skill_id: cyber_hunting_for_ntlm_relay_attacks
name: Hunting for NTLM Relay Attacks
description: Detect NTLM relay via authentication anomalies: coerced-auth triggers, relay infrastructure, and SMB/LDAP relay patterns.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, active-directory, lateral-movement]
version: 1.0.0
---
## Purpose

NTLM relay captures Net-NTLM authentication attempts (often coerced from
a victim via printer-bug-class or DFSCoerce-style triggers) and relays
them to a target service to authenticate as the victim. This playbook
covers detecting relay attacks through authentication telemetry,
identifying coercion triggers, and deploying the structural mitigations
(SMB signing, EPA, LDAP channel binding).

## When to use

- Investigating suspected AD lateral movement or privilege escalation
  with no clear credential-theft event.
- After threat intel reports relay tooling (PetitPotam/DFSCoerce-class
  coercion, relay-to-ADCS ESC8) in your sector.
- Validating that SMB signing and LDAP signing/channel-binding
  mitigations are actually effective.
- Proactive hunting for coerced-authentication patterns.

## Prerequisites

- DC and server Security logs: 4624/4625 logons with authentication
  package (NTLM) and logon type, 4648 explicit-credential logons.
- Network telemetry for SMB (445) and LDAP(S) connections.
- Knowledge of which systems enforce SMB signing and LDAP signing/
  channel binding — and which do not.
- EDR process telemetry on potential relay/coercion hosts.

## Procedure

1. **Understand the relay chain.** Relay requires three parts: a
   coercion trigger (forcing a victim to authenticate to the attacker),
   a relay host forwarding the authentication, and a target accepting
   it. Hunt each part: unusual coerced-auth events, relay tooling
   processes, and anomalous NTLM logons on targets.
2. **Hunt coerced authentication.** Look for victims authenticating to
   unexpected hosts: print-spooler or DCOM/RPC-triggered authentications
   from servers to workstations, MS-EFSR/DFSCoerce-class RPC patterns,
   and authentication attempts from DCs to non-DC hosts (DCs should
   rarely authenticate outbound).
3. **Hunt relay-tooling indicators.** On suspected relay hosts, look for
   processes listening on SMB/HTTP(S)/LDAP relay ports, tools with
   SOCKS-like or port-forwarding behavior, and network connections
   bridging victim→attacker→target within short time windows.
4. **Hunt anomalous NTLM logons on targets.** Flag NTLM (not Kerberos)
   network logons to sensitive targets (ADCS, LDAP, SMB on servers)
   from unexpected sources, especially where the source is a
   workstation relaying a privileged account's authentication. NTLM
   logons for accounts that normally use Kerberos deserve scrutiny.
5. **Check relay-to-ADCS specifically.** Relay to Active Directory
   Certificate Services (ESC8) is a top-tier escalation: monitor for
   certificate requests via HTTP enrollment from unusual sources and
   review ADCS logs for requests inconsistent with normal enrollment
   patterns.
6. **Correlate the full chain.** Tie coercion → relay → target logon
   into a timeline: victim authentication to attacker host, followed
   within seconds/minutes by the attacker's authenticated session on
   the target as the victim. The tight timing is the corroborating
   signature.
7. **Contain and scope.** Isolate relay infrastructure, reset
   credentials of relayed accounts, review what the attacker accessed
   as each victim, and check ADCS for fraudulently issued certificates
   (revoke as needed).
8. **Deploy structural mitigations.** Enforce SMB signing everywhere,
   enable LDAP signing and channel binding, require EPA (Extended
   Protection for Authentication) on ADCS HTTP enrollment, disable the
   print spooler on DCs and servers that do not need it, and patch
   coercion vectors. Verify mitigations with a controlled test.

## Expected outputs

- Relay findings: coercion source, relay host, target, and relayed
  accounts with timelines.
- ADCS certificate review with revocation records if applicable.
- Containment and credential-reset records.
- Mitigation verification: signing, EPA, channel-binding status per
  system class.

## Pitfalls

- NTLM is used legitimately by legacy systems — baseline NTLM usage
   before alerting or you will drown in noise.
- Relay can cross from NTLM to LDAP/SMB/HTTP targets — hunt all
   target protocols, not just SMB.
- Coercion triggers look like normal RPC traffic in isolation —
   the victim→unexpected-host authentication pattern is the signal.
- Disabling NTLM entirely breaks legacy applications — phase it with
   auditing (NTLM audit mode) and exceptions.
- Missing the ADCS angle: relay-to-ADCS yields persistent
   certificates — always check certificate issuance in relay cases.

## References

- MITRE ATT&CK: T1557.001 (LLMNR/NBT-NS poisoning — adjacent),
  T1187 (Forced Authentication), T1649 (Steal/Forge Auth Certificates)
- Microsoft Learn: SMB signing, LDAP channel binding, EPA for ADCS
- CISA: guidance on PetitPotam-class mitigations
- Industry research on NTLM relay techniques (defensive summaries)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
