---
skill_id: cyber_b3_cicd_pipeline_abuse_identity_provider_sso_azure_cloud_defined
name: CI/CD Pipeline Abuse Defense for SSO Identity Providers in Azure Cloud (Defined Maturity)
description: "CI/CD Pipeline Abuse defense playbook for SSO Identity Providers in Azure Cloud at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [supply-chain, devops, identity, sso, authentication, cloud, azure, maturity-defined]
version: 1.0.0
---
# CI/CD Pipeline Abuse Defense for SSO Identity Providers in Azure Cloud (Defined Maturity)

## Purpose

Compromised build pipelines inject malicious code into artifacts or exfiltrate secrets from build environments. Pipelines hold production credentials AND ship code — treat them as tier-zero assets. Applies to SSO Identity Providers in Azure Cloud at Defined maturity.

## When to use

- Pipeline runs triggered outside normal commits, modified build scripts, or runners executing unexpected network calls.
- Secrets accessed by pipeline jobs that never needed them, or new pipeline variables containing exfil endpoints.
- Artifacts whose hashes differ from reproducible-build expectations.
- Lens: Best telemetry: authentication logs with MFA detail + app-assignment changes + federation trust changes. Activity Log and Entra sign-in/audit logs streamed to Log Analytics/SIEM; Defender for Cloud alerts.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NSG flow logs and storage analytics for data-plane visibility.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Authentication logs per application (success/failure, MFA method, device, location) and Application assignment and provisioning logs; new SSO integrations; run `# conceptually (IdP APIs differ):` then `idp-cli logs auth --user <upn> --last 7d --format table | head -25`.
3. **Analyze.** Diff the pipeline definition against the last known-good version; identify exactly which jobs were tampered with. Then: Determine which secrets the compromised jobs could read and rotate all of them — assume exposure.
4. **Contain and harden.** Pipeline definitions in version control with required reviews; ephemeral, isolated runners; OIDC-based short-lived credentials instead of stored secrets. Asset layer: Phishing-resistant MFA default, sign-on policies per app risk, session lifetime limits. Environment layer: Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Cleaning the pipeline but shipping artifacts it already poisoned — quarantine recent builds.
- Long-lived cloud credentials stored as pipeline secrets; rotate and replace with OIDC federation.

## References

- MITRE ATT&CK: T1195.002 (Supply Chain: Compromise Software Supply Chain)
- Vendor logging and hardening baselines for SSO Identity Providers; Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
