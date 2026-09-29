---
skill_id: cyber_b3_ad_acl_abuse_vmware_esxi_multi_cloud_foundational
name: Active Directory ACL Abuse Defense for VMware ESXi Hosts in Multi-Cloud (Foundational Maturity)
description: "Active Directory ACL Abuse defense playbook for VMware ESXi Hosts in Multi-Cloud at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, active-directory, virtualization, vmware, cloud, multi-cloud, maturity-foundational]
version: 1.0.0
---
# Active Directory ACL Abuse Defense for VMware ESXi Hosts in Multi-Cloud (Foundational Maturity)

## Purpose

Attackers abuse delegated Active Directory permissions — WriteDacl, GenericAll, ForceChangePassword — to escalate without exploits. These are legitimate rights granted too broadly, so detection means auditing WHO can do WHAT, continuously. Applies to VMware ESXi Hosts in Multi-Cloud at Foundational maturity.

## When to use

- 4662 events showing writes to security descriptors (WriteDacl / WriteOwner) on privileged groups, OUs, or the AdminSDHolder container.
- Password resets (4724) performed by non-helpdesk accounts, or new ACEs granting GenericAll over high-value targets.
- BloodHound-style LDAP enumeration (large object reads) preceding the ACL change — the attacker mapping attack paths.
- Lens: Best telemetry: vCenter tasks/events + ESXi syslog + lockdown-mode audit. Cloud-agnostic SIEM normalizing AWS CloudTrail, Azure Activity Log, and GCP Audit Logs into one schema.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CSPM coverage across all clouds with consistent misconfiguration alerting.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in vCenter tasks and events (VM power ops, snapshot create/delete, host profile changes) and ESXi hostd/vpxa logs and shell-access records; VM .vmx changes; run `esxcli system auditrecords local list | tail -20` then `vim-cmd vmsvc/getallvms 2>/dev/null | head -20`.
3. **Analyze.** Diff the object's ACL before and after: which principal gained which right, and was it granted through nested group membership? Then: Map the attack path the new right enables (e.g., GenericAll on a group -> add self -> Domain Admin) to scope the blast radius.
4. **Contain and harden.** Least-privilege delegation: no GenericAll/WriteDacl outside Domain Admins; regular ACL audits with alerting on changes to protected objects. Asset layer: Lockdown mode on, isolated management network, unique per-host root passwords, MFA on vCenter. Environment layer: Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- One-time ACL cleanup without continuous monitoring — delegation sprawl regrows within months.
- Forgetting nested groups: the dangerous ACE is often three group-nestings away from the attacker.

## References

- MITRE ATT&CK: T1098 (Persistence: Account Manipulation)
- Vendor logging and hardening baselines for VMware ESXi Hosts; Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
