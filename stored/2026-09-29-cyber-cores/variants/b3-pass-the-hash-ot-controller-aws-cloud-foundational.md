---
skill_id: cyber_b3_pass_the_hash_ot_controller_aws_cloud_foundational
name: Pass-the-Hash Defense for OT Controllers in AWS Cloud (Foundational Maturity)
description: "Pass-the-Hash defense playbook for OT Controllers in AWS Cloud at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, lateral-movement, ot, ics, critical-infrastructure, cloud, aws, maturity-foundational]
version: 1.0.0
---
# Pass-the-Hash Defense for OT Controllers in AWS Cloud (Foundational Maturity)

## Purpose

Stolen NTLM hashes authenticate without the password ever being cracked. It is invisible to password monitoring because no password is used — defense means killing NTLM where possible and watching for its telltale logon patterns. Applies to OT Controllers in AWS Cloud at Foundational maturity.

## When to use

- 4624 type-3/9 logons using NTLM where Kerberos is expected, especially from workstations to servers with admin accounts.
- Logon sessions with no interactive activity but successful authentication, or the same hash authenticating from multiple hosts simultaneously.
- NTLM audit logs showing authentication for accounts that should be Kerberos-only.
- Lens: Best telemetry: passive OT network monitoring + engineering-workstation logs + change-management records. Organization CloudTrail in all regions, GuardDuty, and VPC flow logs shipped to the security account.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CloudWatch and workload logs centralized; S3 access logging on sensitive buckets.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in OT protocol logs (Modbus/DNP3/OPC) from passive taps — never active-scan OT networks and Engineering workstation access and project-file change logs; run `# PASSIVE ONLY on OT networks — no active scanning:` then `tshark -r /captures/ot-span.pcap -Y 'modbus' -T fields -e frame.time -e modbus.func_code 2>/dev/null | head -20`.
3. **Analyze.** Determine hash source: LSASS dump, SAM extraction, or DCSync — each implies a different prior compromise to remediate. Then: List every host the hash authenticated to; each is a foothold until reimaged or verified clean.
4. **Contain and harden.** Reduce NTLM usage (audit mode first, then restrict), deploy Credential Guard, and use unique local admin passwords (LAPS). Asset layer: Air-gap or data-diode segmentation from IT, unidirectional gateways, strict change control on logic. Environment layer: SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Resetting the password without considering that the attacker may have dumped the NEW hash too if still present.
- Disabling NTLM blindly and breaking legacy apps — audit first, restrict second.

## References

- MITRE ATT&CK: T1550.002 (Lateral Movement: Pass the Hash)
- Vendor logging and hardening baselines for OT Controllers; SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
