---
skill_id: cyber_b3_wmi_persistence_cicd_runner_gcp_cloud_managed
name: WMI Persistence Defense for CI/CD Runners in GCP Cloud (Managed Maturity)
description: "WMI Persistence defense playbook for CI/CD Runners in GCP Cloud at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, devops, supply-chain, cloud, gcp, maturity-managed]
version: 1.0.0
---
# WMI Persistence Defense for CI/CD Runners in GCP Cloud (Managed Maturity)

## Purpose

WMI event subscriptions trigger payloads on system events (timers, logons) with no visible scheduled task or service. They are fileless, stealthy, and missed by autorun tools that do not enumerate the WMI repository. Applies to CI/CD Runners in GCP Cloud at Managed maturity.

## When to use

- New __EventFilter/__EventConsumer/__FilterToConsumerBinding instances in the WMI repository, especially ActiveScript or CommandLine consumers with encoded commands.
- WmiPrvSE.exe spawning powershell/cmd at odd times, or WMI operational log entries for subscription creation.
- Persistence that survives task/service cleanup — the classic sign the mechanism is WMI-based.
- Lens: Best telemetry: job execution logs + runner registration events + secret-access audit. Cloud Audit Logs (admin + data access) exported to a locked-down logging project.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Security Command Center findings and VPC flow logs centralized.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Job logs with executed commands and exit codes for suspect runs and Runner registration/deregistration events and runner version inventory; run `runner-cli jobs list --status failed --last 7d | head -20` then `runner-cli runners list --format table`.
3. **Analyze.** Enumerate all event subscriptions (Get-WMIObject -Namespace root\subscription) and inspect each consumer's command line. Then: Correlate subscription creation time with the initial compromise to confirm it is attacker-planted, not admin tooling.
4. **Contain and harden.** Alert on WMI subscription creation events; restrict WMI namespace permissions to administrators. Asset layer: Ephemeral isolated runners, OIDC short-lived credentials, no persistent secrets on runners. Environment layer: Organization policies constraining public exposure, API enablement, and service-account key creation.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Declaring a host clean after checking tasks/services/registry but never looking at WMI subscriptions.
- Removing the consumer but leaving the filter and binding, which error silently and get recreated by the implant.

## References

- MITRE ATT&CK: T1047 (Execution: Windows Management Instrumentation)
- Vendor logging and hardening baselines for CI/CD Runners; Organization policies constraining public exposure, API enablement, and service-account key creation.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
