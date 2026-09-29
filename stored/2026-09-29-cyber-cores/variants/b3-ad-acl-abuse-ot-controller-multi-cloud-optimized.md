---
skill_id: cyber_b3_ad_acl_abuse_ot_controller_multi_cloud_optimized
name: Active Directory ACL Abuse Defense for OT Controllers in Multi-Cloud (Optimized Maturity)
description: "Active Directory ACL Abuse defense playbook for OT Controllers in Multi-Cloud at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, active-directory, ot, ics, critical-infrastructure, cloud, multi-cloud, maturity-optimized]
version: 1.0.0
---
# Active Directory ACL Abuse Defense for OT Controllers in Multi-Cloud (Optimized Maturity)

## Purpose

Attackers abuse delegated Active Directory permissions — WriteDacl, GenericAll, ForceChangePassword — to escalate without exploits. These are legitimate rights granted too broadly, so detection means auditing WHO can do WHAT, continuously. Applies to OT Controllers in Multi-Cloud at Optimized maturity.

## When to use

- 4662 events showing writes to security descriptors (WriteDacl / WriteOwner) on privileged groups, OUs, or the AdminSDHolder container.
- Password resets (4724) performed by non-helpdesk accounts, or new ACEs granting GenericAll over high-value targets.
- BloodHound-style LDAP enumeration (large object reads) preceding the ACL change — the attacker mapping attack paths.
- Lens: Best telemetry: passive OT network monitoring + engineering-workstation logs + change-management records. Cloud-agnostic SIEM normalizing AWS CloudTrail, Azure Activity Log, and GCP Audit Logs into one schema.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CSPM coverage across all clouds with consistent misconfiguration alerting.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in OT protocol logs (Modbus/DNP3/OPC) from passive taps — never active-scan OT networks and Engineering workstation access and project-file change logs; run `# PASSIVE ONLY on OT networks — no active scanning:` then `tshark -r /captures/ot-span.pcap -Y 'modbus' -T fields -e frame.time -e modbus.func_code 2>/dev/null | head -20`.
3. **Analyze.** Diff the object's ACL before and after: which principal gained which right, and was it granted through nested group membership? Then: Map the attack path the new right enables (e.g., GenericAll on a group -> add self -> Domain Admin) to scope the blast radius.
4. **Contain and harden.** Least-privilege delegation: no GenericAll/WriteDacl outside Domain Admins; regular ACL audits with alerting on changes to protected objects. Asset layer: Air-gap or data-diode segmentation from IT, unidirectional gateways, strict change control on logic. Environment layer: Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- One-time ACL cleanup without continuous monitoring — delegation sprawl regrows within months.
- Forgetting nested groups: the dangerous ACE is often three group-nestings away from the attacker.

## References

- MITRE ATT&CK: T1098 (Persistence: Account Manipulation)
- Vendor logging and hardening baselines for OT Controllers; Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
