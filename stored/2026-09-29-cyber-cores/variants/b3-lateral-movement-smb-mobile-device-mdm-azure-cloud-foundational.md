---
skill_id: cyber_b3_lateral_movement_smb_mobile_device_mdm_azure_cloud_foundational
name: SMB Lateral Movement Defense for Mobile Devices (MDM) in Azure Cloud (Foundational Maturity)
description: "SMB Lateral Movement defense playbook for Mobile Devices (MDM) in Azure Cloud at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, lateral-movement, mobile, mdm, endpoint, cloud, azure, maturity-foundational]
version: 1.0.0
---
# SMB Lateral Movement Defense for Mobile Devices (MDM) in Azure Cloud (Foundational Maturity)

## Purpose

Attackers move host-to-host over SMB using stolen credentials — PsExec-style service creation, admin shares, or WMI. In a flat network, one compromised workstation becomes the whole domain in hours. Applies to Mobile Devices (MDM) in Azure Cloud at Foundational maturity.

## When to use

- SMB sessions from a workstation to many other hosts in a short window, especially to ADMIN$ or C$ shares the user never touches normally.
- Service creation events (7045) with service binaries in ADMIN$\system32, or 4624 type-3 logons with the same account across dozens of hosts.
- EDR process trees showing services.exe spawning cmd/powershell shortly after a remote SMB session.
- Lens: Best telemetry: MDM compliance/app inventory + mobile threat defense alerts + enrollment logs. Activity Log and Entra sign-in/audit logs streamed to Log Analytics/SIEM; Defender for Cloud alerts.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NSG flow logs and storage analytics for data-plane visibility.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in MDM device inventory: OS versions, jailbreak/root detections, installed app lists and Mobile threat defense alerts (malicious apps, network attacks, OS tampering); run `# conceptually (MDM APIs differ):` then `mdm-cli devices list --noncompliant --limit 30`.
3. **Analyze.** Map the movement graph: source host, credential used, target hosts, timestamps — this is the incident's skeleton. Then: Determine which credential enabled it (stolen hash, ticket, or plaintext) to know what must be rotated enterprise-wide.
4. **Contain and harden.** Segment the network (workstation-to-workstation SMB blocked), deploy LAPS for unique local admin passwords, and restrict lateral logon rights via tiered admin model. Asset layer: Enrollment required for corporate data, OS version minimums, jailbreak/root = automatic quarantine. Environment layer: Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Cleaning patient zero while the attacker's beachheads on hosts 3, 7, and 12 remain active.
- Rotating the compromised account's password but not the kerberos tickets/hashes already stolen from it.

## References

- MITRE ATT&CK: T1021.002 (Lateral Movement: SMB/Windows Admin Shares)
- Vendor logging and hardening baselines for Mobile Devices (MDM); Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
