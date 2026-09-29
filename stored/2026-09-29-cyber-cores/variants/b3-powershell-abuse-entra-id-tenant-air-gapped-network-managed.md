---
skill_id: cyber_b3_powershell_abuse_entra_id_tenant_air_gapped_network_managed
name: Malicious PowerShell Abuse Defense for Microsoft Entra ID Tenants in Air-Gapped Networks (Managed Maturity)
description: "Malicious PowerShell Abuse defense playbook for Microsoft Entra ID Tenants in Air-Gapped Networks at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, execution, identity, cloud, microsoft, air-gap, ot, high-security, maturity-managed]
version: 1.0.0
---
# Malicious PowerShell Abuse Defense for Microsoft Entra ID Tenants in Air-Gapped Networks (Managed Maturity)

## Purpose

PowerShell is the attacker's Swiss-army knife: encoded commands, in-memory execution, credential theft, lateral movement. Deep script-block and module logging turns it from a blind spot into one of your richest telemetry sources. Applies to Microsoft Entra ID Tenants in Air-Gapped Networks at Managed maturity.

## When to use

- Event 4104 (script block logging) with encoded commands (-enc/-e), Invoke-Mimikatz/Invoke-Shellcode patterns, or obfuscation (heavy string concatenation, char codes).
- PowerShell spawned by Office, browsers, or WMI with hidden window styles, or AMSI bypass patterns in the script text.
- Module logging showing credential-access or AD-enumeration cmdlets from non-admin workstations.
- Lens: Best telemetry: Entra sign-in + audit logs streamed to Log Analytics/SIEM with 30+ day retention. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Sign-in logs (interactive, non-interactive, service principal) with risk detections and MFA details and Audit logs: app registrations, consent grants, Conditional Access changes, role assignments; run `# Microsoft Graph (delegated admin): recent risky sign-ins` then `Get-MgAuditLogSignIn -Filter "riskState eq 'atRisk'" -Top 25 | Select-Object CreatedDateTime, UserPrincipalName, IpAddress, @{n='Risk';e={$_.RiskDetail}}`.
3. **Analyze.** Decode every obfuscated layer — the final script reveals the true objective (many 'downloaders' are actually ransomware staging). Then: Correlate the PowerShell session with its parent to find the delivery vector (macro, scheduled task, remote session).
4. **Contain and harden.** Enable script-block logging, module logging, and transcription fleet-wide; forward to the SIEM with alerting. Asset layer: Conditional Access: require phishing-resistant MFA, compliant devices, block legacy auth and risky sign-ins. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Logging PowerShell without a SIEM pipeline to analyze it — 4104 events are high-volume and useless unsearched.
- Assuming -noprofile -w hidden is always malicious; admins use it too — baseline first.

## References

- MITRE ATT&CK: T1059.001 (Execution: PowerShell)
- Vendor logging and hardening baselines for Microsoft Entra ID Tenants; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
