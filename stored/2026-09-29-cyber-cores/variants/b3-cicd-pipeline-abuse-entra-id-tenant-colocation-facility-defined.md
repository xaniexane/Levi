---
skill_id: cyber_b3_cicd_pipeline_abuse_entra_id_tenant_colocation_facility_defined
name: CI/CD Pipeline Abuse Defense for Microsoft Entra ID Tenants in Colocation Facilities (Defined Maturity)
description: "CI/CD Pipeline Abuse defense playbook for Microsoft Entra ID Tenants in Colocation Facilities at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [supply-chain, devops, identity, cloud, microsoft, on-prem, colocation, maturity-defined]
version: 1.0.0
---
# CI/CD Pipeline Abuse Defense for Microsoft Entra ID Tenants in Colocation Facilities (Defined Maturity)

## Purpose

Compromised build pipelines inject malicious code into artifacts or exfiltrate secrets from build environments. Pipelines hold production credentials AND ship code — treat them as tier-zero assets. Applies to Microsoft Entra ID Tenants in Colocation Facilities at Defined maturity.

## When to use

- Pipeline runs triggered outside normal commits, modified build scripts, or runners executing unexpected network calls.
- Secrets accessed by pipeline jobs that never needed them, or new pipeline variables containing exfil endpoints.
- Artifacts whose hashes differ from reproducible-build expectations.
- Lens: Best telemetry: Entra sign-in + audit logs streamed to Log Analytics/SIEM with 30+ day retention. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Sign-in logs (interactive, non-interactive, service principal) with risk detections and MFA details and Audit logs: app registrations, consent grants, Conditional Access changes, role assignments; run `# Microsoft Graph (delegated admin): recent risky sign-ins` then `Get-MgAuditLogSignIn -Filter "riskState eq 'atRisk'" -Top 25 | Select-Object CreatedDateTime, UserPrincipalName, IpAddress, @{n='Risk';e={$_.RiskDetail}}`.
3. **Analyze.** Diff the pipeline definition against the last known-good version; identify exactly which jobs were tampered with. Then: Determine which secrets the compromised jobs could read and rotate all of them — assume exposure.
4. **Contain and harden.** Pipeline definitions in version control with required reviews; ephemeral, isolated runners; OIDC-based short-lived credentials instead of stored secrets. Asset layer: Conditional Access: require phishing-resistant MFA, compliant devices, block legacy auth and risky sign-ins. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Cleaning the pipeline but shipping artifacts it already poisoned — quarantine recent builds.
- Long-lived cloud credentials stored as pipeline secrets; rotate and replace with OIDC federation.

## References

- MITRE ATT&CK: T1195.002 (Supply Chain: Compromise Software Supply Chain)
- Vendor logging and hardening baselines for Microsoft Entra ID Tenants; Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
