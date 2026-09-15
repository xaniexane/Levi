---
skill_id: cyber_detecting_ntlm_relay_with_event_correlation
name: Detecting NTLM Relay with Event Correlation
description: Detect NTLM relay attacks by correlating authentication events across sources.
risk: low
permissions: []
requires_confirmation: false
tags: [active-directory, ntlm, detection]
version: 1.0.0
---
## Purpose

NTLM relay — coercing a machine to authenticate and relaying those credentials to another service — leaves subtle traces no single log captures completely. This playbook shows defenders how to detect relay attacks by correlating Windows authentication events, SMB signing status, and network telemetry into high-confidence detections.

## When to use

- You need detection coverage for NTLM relay (PetitPotam/PrinterBug-class coercion).
- SMB signing is not yet enforced everywhere and you need compensating detection.
- Threat hunting for credential-relay activity after a suspected coercion incident.
- Validating that relay mitigations (signing, EPA) are actually working.

## Prerequisites

- Windows Security logs from DCs and member servers: Event IDs 4624 (logon), 4672 (special privileges), 4648 (explicit credential logon), and 8004/8005 NTLM auditing if enabled.
- SMB signing status inventory: which hosts enforce signing, which don't.
- Network telemetry (Zeek/SMB logs or firewall) showing NTLM authentication flows between internal hosts.
- Knowledge of legitimate NTLM usage in the environment (legacy apps, printers) for baselining.

## Procedure

1. Enable NTLM auditing first. Turn on NTLM operational logging (Applications and Services Logs → Microsoft → Windows → NTLM) and outgoing NTLM auditing via Group Policy. Without this, relayed authentications blend into normal NTLM noise — auditing is the prerequisite for everything below.
2. Detect the coercion precursors. Relay attacks start with authentication coercion: suspicious EFSRPC (PetitPotam), MS-RPRN (PrinterBug), or DFSCoerce RPC calls forcing a target (often a DC) to authenticate to an attacker host. Alert on these RPC patterns from non-admin hosts, especially targeting domain controllers.
3. Correlate the relay chain. The telltale pattern: host A coerced into authenticating to attacker host B, followed by B authenticating to target C using A's identity — visible as 4624 Type 3 logons where the source IP doesn't match the account's normal host, and logon sessions on C attributed to A's computer account originating from B's IP. Build the correlation: coercion RPC → inbound NTLM to B → outbound authenticated session from B to C.
4. Weight by SMB signing gaps. Relay to targets without SMB signing (or without LDAP channel binding/EPA) is the exploitable case. Join relay-pattern alerts with your signing-status inventory — the same pattern against a hardened target is lower priority than against an unsigned legacy server.
5. Investigate with a fixed sequence: identify the coerced host and the coercion RPC, identify the relay target and what the relayed session did (SMB share access? LDAP writes? DCSync attempt?), scope for additional coerced hosts, and assume the relayed account's credentials are compromised. Check for DCSync (Event 4662 on DCs) as the typical relay objective.
6. Drive the mitigations that kill relay: enforce SMB signing everywhere, enable LDAP channel binding and signing, patch coercion vectors, and plan NTLM deprecation where possible. Detection is compensating control — the fix is removing the relay surface.

## Expected outputs

- NTLM auditing enabled via GPO with logs centralized.
- Correlation detections: coercion-RPC → relayed-auth chain, weighted by signing status.
- SMB-signing/LDAP-binding coverage inventory with remediation plan.
- Investigation runbook: coercion identification, relay scoping, credential-reset criteria.

## Pitfalls

- Without NTLM auditing, relayed logons are indistinguishable from normal NTLM — enable it first.
- Legacy applications generate constant NTLM noise; baseline legitimate use before alerting.
- Alerting on coercion RPCs alone fires on some admin tools — correlate the full chain.
- Relay against hardened (signed) targets usually fails; prioritize by target signing status.
- Treating relay detection as the end state instead of driving signing enforcement leaves the hole open.

## References

- Microsoft Learn: NTLM auditing, SMB signing, LDAP channel binding; MITRE ATT&CK T1557.001 (Adversary-in-the-Middle: LLMNR/NBT-NS Poisoning and SMB Relay) — https://attack.mitre.org/techniques/T1557/001/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
