---
skill_id: cyber_b3_cicd_pipeline_abuse_saas_application_on_prem_datacenter_defined
name: CI/CD Pipeline Abuse Defense for SaaS Applications in On-Premises Datacenter (Defined Maturity)
description: "CI/CD Pipeline Abuse defense playbook for SaaS Applications in On-Premises Datacenter at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [supply-chain, devops, cloud, saas, identity, on-prem, datacenter, maturity-defined]
version: 1.0.0
---
# CI/CD Pipeline Abuse Defense for SaaS Applications in On-Premises Datacenter (Defined Maturity)

## Purpose

Compromised build pipelines inject malicious code into artifacts or exfiltrate secrets from build environments. Pipelines hold production credentials AND ship code — treat them as tier-zero assets. Applies to SaaS Applications in On-Premises Datacenter at Defined maturity.

## When to use

- Pipeline runs triggered outside normal commits, modified build scripts, or runners executing unexpected network calls.
- Secrets accessed by pipeline jobs that never needed them, or new pipeline variables containing exfil endpoints.
- Artifacts whose hashes differ from reproducible-build expectations.
- Lens: Best telemetry: SaaS audit logs (admin + user activity) streamed to SIEM + SSO logs. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Admin audit log (settings changes, user provisioning, sharing changes) and User activity logs: file access, downloads, external sharing events; run `# conceptually (SaaS APIs differ):` then `saas-cli audit log --category admin --last 7d --format table | head -25`.
3. **Analyze.** Diff the pipeline definition against the last known-good version; identify exactly which jobs were tampered with. Then: Determine which secrets the compromised jobs could read and rotate all of them — assume exposure.
4. **Contain and harden.** Pipeline definitions in version control with required reviews; ephemeral, isolated runners; OIDC-based short-lived credentials instead of stored secrets. Asset layer: SSO with MFA enforced, SCIM provisioning, least-privilege roles, external-sharing restricted. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Cleaning the pipeline but shipping artifacts it already poisoned — quarantine recent builds.
- Long-lived cloud credentials stored as pipeline secrets; rotate and replace with OIDC federation.

## References

- MITRE ATT&CK: T1195.002 (Supply Chain: Compromise Software Supply Chain)
- Vendor logging and hardening baselines for SaaS Applications; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
