---
skill_id: cyber_implementing_anti_ransomware_group_policy
name: Implementing Anti-Ransomware Group Policy
description: Deploy ransomware-resistant Windows baselines via Group Policy: ASR rules, execution controls, RDP hardening, and recovery protections.
risk: low
permissions: []
requires_confirmation: false
tags: [ransomware, windows, group-policy]
version: 1.0.0
---
## Purpose

Group Policy is the fleet-scale lever for ransomware resistance on
Windows: it can block the execution paths ransomware needs, harden
remote access, and protect recovery options — before an incident. This
playbook covers the GPO control set that most reduces ransomware blast
radius, with safe rollout practices.

## When to use

- Building ransomware readiness across a Windows fleet.
- After ransomware tabletop exercises revealed control gaps.
- Remediating post-incident findings at fleet scale.
- Meeting cyber-insurance or regulatory ransomware-control
  expectations.

## Prerequisites

- Domain GPO administration rights and change control.
- Pilot OUs for staged rollout with rollback capability.
- Application inventory to assess execution-control impact.
- Tested offline backups (policy complements, never replaces,
  recovery capability).

## Procedure

1. **Deploy Attack Surface Reduction rules.** Enable Defender ASR
   rules in block mode via GPO after an audit-mode pilot: block
   executable content from email/webmail, block Office macro child
   processes, block process creation from PSExec/WMI, block
   credential stealing from LSASS, and block persistence via WMI
   events. These directly break ransomware tooling chains.
2. **Control script and macro execution.** Set Office macro policy
   (block macros from the internet / signed-only per risk), enforce
   PowerShell Constrained Language Mode via WDAC or policy, and
   consider AppLocker/WDAC allow-listing for high-risk endpoints.
3. **Harden remote access.** Restrict RDP via GPO: Network Level
   Authentication required, RDP limited to management subnets through
   host firewall rules, idle/session timeouts, and (critically) no
   internet-exposed RDP — enforce via firewall, not just policy.
   Disable LLMNR/NetBIOS name resolution to complicate lateral
   discovery.
4. **Protect recovery options.** Via policy: prevent users from
   disabling Defender/tamper protection, restrict who can stop backup
   services or modify shadow storage, and ensure recovery partitions
   and backup agents cannot be disabled by non-admins.
5. **Limit lateral movement primitives.** Disable SMBv1, require SMB
   signing, restrict local administrator credential reuse (LAPS for
   unique local admin passwords), and limit remote registry and
   unnecessary remote services.
6. **Enforce auditing for ransomware precursors.** Ensure GPO enables
   the audit subcategories that feed ransomware detections: process
   creation with command line, scheduled-task and service creation,
   PowerShell logging, and Defender operational logs.
7. **Roll out in rings.** Pilot each policy area in a test OU, measure
   application and workflow breakage, tune exclusions deliberately
   (documented, time-bound), then expand ring by ring with pauses.
8. **Validate with adversary emulation.** After rollout, run
   ransomware-technique emulation (atomic-style tests or purple-team)
   to verify the policies actually block the chains — policy applied
   is not policy effective until tested.

## Expected outputs

- GPO baselines for ASR, execution control, RDP, and recovery
  protection, version-controlled.
- Pilot validation and ring-rollout records with exclusions
  documented.
- Emulation test results proving control effectiveness.
- Monitoring for policy-tampering and exclusion expiry.

## Pitfalls

- ASR rules in block mode without an audit pilot break legitimate
   applications — always pilot in audit mode first.
- Exclusions that swallow the rule — overly broad ASR exclusions
   negate the control; keep them narrow and time-bound.
- GPO without enforcement verification — use RSOP/GPResult sampling
   to confirm policies actually apply.
- Forgetting non-domain-joined or remote hosts — extend equivalent
   controls via MDM for off-domain endpoints.
- Policy is not backup — no GPO set substitutes for tested,
   offline, immutable backups.

## References

- Microsoft Learn: Attack Surface Reduction rules reference; Group
  Policy security baselines
- CISA: #StopRansomware guidance and advisories
- NIST SP 800-53: ransomware-relevant control families
- CIS Windows benchmarks (policy-aligned controls)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
