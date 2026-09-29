---
skill_id: cyber_b3_drive_by_download_gcp_project_remote_workforce_managed
name: Drive-By Download Defense for GCP Projects in Remote Workforce (Managed Maturity)
description: "Drive-By Download defense playbook for GCP Projects in Remote Workforce at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [network, malware, cloud, gcp, remote, endpoint, zero-trust, maturity-managed]
version: 1.0.0
---
# Drive-By Download Defense for GCP Projects in Remote Workforce (Managed Maturity)

## Purpose

Visiting a compromised or malicious page silently downloads malware via browser or plugin exploits. Patching and browser isolation remove the opportunity; proxy logs reveal the exposure. Applies to GCP Projects in Remote Workforce at Managed maturity.

## When to use

- Browser spawning unexpected child processes or writing executables to temp/downloads without user download action.
- Proxy logs showing visits to compromised sites followed by executable downloads, often via redirect chains.
- Exploit-kit patterns: rapid plugin version probing, obfuscated JavaScript, then payload fetch.
- Lens: Best telemetry: Cloud Audit Logs (Admin Activity + Data Access) + Security Command Center + VPC flow logs. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Cloud Audit Logs: setIamPolicy, storage.setIamPermissions, compute inserts, and console logons and Security Command Center findings; Forseti/Config Validator drift reports where deployed; run `gcloud logging read 'protoPayload.methodName:"SetIamPolicy"' --limit 20 --format='table(timestamp, protoPayload.authenticationInfo.principalEmail, resourceName)'` then `gcloud scc findings list organizations/$ORG_ID --filter='state="ACTIVE"' --limit 15`.
3. **Analyze.** Reconstruct the redirect chain from proxy logs to identify the compromised page or malvertising source. Then: Determine whether the payload executed: browser process tree and EDR execution events after the download timestamp.
4. **Contain and harden.** Automatic browser and OS patching; remove or sandbox legacy plugins (Java, Flash-era); consider browser isolation for high-risk users. Asset layer: Organization policies: no public buckets, no default SA use, OS Login on; deny unapproved APIs. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Assuming the user 'must have clicked something' — drive-bys need no click, so user interviews mislead.
- Cleaning the endpoint without blocking the compromised site that will re-infect the next visitor.

## References

- MITRE ATT&CK: T1189 (Initial Access: Drive-by Compromise)
- Vendor logging and hardening baselines for GCP Projects; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
