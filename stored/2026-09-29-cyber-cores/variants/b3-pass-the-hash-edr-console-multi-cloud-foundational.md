---
skill_id: cyber_b3_pass_the_hash_edr_console_multi_cloud_foundational
name: Pass-the-Hash Defense for EDR Consoles in Multi-Cloud (Foundational Maturity)
description: "Pass-the-Hash defense playbook for EDR Consoles in Multi-Cloud at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, lateral-movement, soc, edr, endpoint, cloud, multi-cloud, maturity-foundational]
version: 1.0.0
---
# Pass-the-Hash Defense for EDR Consoles in Multi-Cloud (Foundational Maturity)

## Purpose

Stolen NTLM hashes authenticate without the password ever being cracked. It is invisible to password monitoring because no password is used — defense means killing NTLM where possible and watching for its telltale logon patterns. Applies to EDR Consoles in Multi-Cloud at Foundational maturity.

## When to use

- 4624 type-3/9 logons using NTLM where Kerberos is expected, especially from workstations to servers with admin accounts.
- Logon sessions with no interactive activity but successful authentication, or the same hash authenticating from multiple hosts simultaneously.
- NTLM audit logs showing authentication for accounts that should be Kerberos-only.
- Lens: Best telemetry: raw process/network telemetry + detection history + sensor health inventory. Cloud-agnostic SIEM normalizing AWS CloudTrail, Azure Activity Log, and GCP Audit Logs into one schema.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CSPM coverage across all clouds with consistent misconfiguration alerting.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Full process trees with command lines, hashes, and network connections for suspect hosts and Detection and response action history (isolations, kills, quarantines); run `# conceptually (EDR APIs differ):` then `edr-cli hunt process --hostname <host> --since 24h --tree`.
3. **Analyze.** Determine hash source: LSASS dump, SAM extraction, or DCSync — each implies a different prior compromise to remediate. Then: List every host the hash authenticated to; each is a foothold until reimaged or verified clean.
4. **Contain and harden.** Reduce NTLM usage (audit mode first, then restrict), deploy Credential Guard, and use unique local admin passwords (LAPS). Asset layer: Tamper protection locked with console-only disable, auto-isolation policies for high-severity detections. Environment layer: Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Resetting the password without considering that the attacker may have dumped the NEW hash too if still present.
- Disabling NTLM blindly and breaking legacy apps — audit first, restrict second.

## References

- MITRE ATT&CK: T1550.002 (Lateral Movement: Pass the Hash)
- Vendor logging and hardening baselines for EDR Consoles; Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
