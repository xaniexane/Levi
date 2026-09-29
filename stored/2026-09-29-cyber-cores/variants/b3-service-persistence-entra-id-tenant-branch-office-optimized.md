---
skill_id: cyber_b3_service_persistence_entra_id_tenant_branch_office_optimized
name: Malicious Service Persistence Defense for Microsoft Entra ID Tenants in Branch Offices (Optimized Maturity)
description: "Malicious Service Persistence defense playbook for Microsoft Entra ID Tenants in Branch Offices at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, identity, cloud, microsoft, branch, network, maturity-optimized]
version: 1.0.0
---
# Malicious Service Persistence Defense for Microsoft Entra ID Tenants in Branch Offices (Optimized Maturity)

## Purpose

Attackers install or hijack Windows services for SYSTEM-level, reboot-surviving execution. Services are trusted by admins, so malicious ones hide with plausible names — verify the binary, not the display name. Applies to Microsoft Entra ID Tenants in Branch Offices at Optimized maturity.

## When to use

- 7045 (service installed) with ImagePath in user-writable or temp directories, unsigned binaries, or names mimicking legit services.
- Existing service ImagePath changed (7045 with same name, new binary) or service binary replaced on disk.
- Services running as SYSTEM that were recently created and have no vendor documentation or change record.
- Lens: Best telemetry: Entra sign-in + audit logs streamed to Log Analytics/SIEM with 30+ day retention. SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Sign-in logs (interactive, non-interactive, service principal) with risk detections and MFA details and Audit logs: app registrations, consent grants, Conditional Access changes, role assignments; run `# Microsoft Graph (delegated admin): recent risky sign-ins` then `Get-MgAuditLogSignIn -Filter "riskState eq 'atRisk'" -Top 25 | Select-Object CreatedDateTime, UserPrincipalName, IpAddress, @{n='Risk';e={$_.RiskDetail}}`.
3. **Analyze.** Hash and detonate the service binary; check its signature status and first-seen date in threat intel. Then: Review the service account: LocalSystem services have maximum impact — scope accordingly.
4. **Contain and harden.** Alert on all 7045 events; require change tickets for new services and run services as least-privilege virtual accounts. Asset layer: Conditional Access: require phishing-resistant MFA, compliant devices, block legacy auth and risky sign-ins. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Stopping the service without deleting it — it restarts on reboot.
- Missing service DLL hijacking (Services with ServiceDll in writable paths) while hunting only EXE-based services.

## References

- MITRE ATT&CK: T1543.003 (Persistence: Windows Service)
- Vendor logging and hardening baselines for Microsoft Entra ID Tenants; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
