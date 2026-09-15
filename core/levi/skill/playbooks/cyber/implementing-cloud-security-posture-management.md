---
skill_id: cyber_implementing_cloud_security_posture_management
name: Cloud Security Posture Management (CSPM)
description: Deploy CSPM for continuous multicloud misconfiguration detection, prioritization, and remediation.
risk: low
permissions: []
requires_confirmation: false
tags: [cloud, posture-management]
version: 1.0.0
---
## Purpose
Cloud misconfigurations — public storage, open security groups, disabled logging, unencrypted
databases — remain a top breach cause, and manual review can't keep up with API-driven provisioning.
CSPM continuously assesses cloud configurations against benchmarks and threat-informed checks,
prioritizes by exploitability, and drives remediation. This playbook deploys CSPM as the always-on
configuration conscience of the cloud estate.

## When to use
- Gaining continuous visibility into multicloud (AWS, Azure, GCP) configuration risk.
- After incidents caused by misconfiguration (public buckets, exposed databases, open management
  ports).
- Meeting continuous-compliance needs across frameworks with one assessment plane.
- Before or during rapid cloud expansion, where provisioning outpaces review.
- As the detective control paired with preventive guardrails (IaC scanning, policy-as-code).

## Prerequisites
- Cloud accounts/projects/subscriptions inventory across all providers in scope.
- A CSPM platform (Wiz, Orca, Prisma Cloud, native: Security Hub + Defender for Cloud + SCC) with
  read access to cloud APIs.
- Defined benchmarks: CIS Foundations per platform, plus org-specific hardening rules.
- Ticketing/SOAR integration for remediation workflow and an owner mapping per account/project.
- Change-control understanding: who can fix what, and which fixes need approval windows.

## Procedure
1. **Connect all accounts with least-privilege read roles.** Onboard every
   account/project/subscription, including sandbox and acquired-company accounts. Verify asset
   counts against billing records — a gap means unscanned infrastructure. Use read-only roles; CSPM
   doesn't need write to assess.
2. **Establish the benchmark baseline.** Enable CIS Foundations benchmarks per platform plus
   threat-informed checks (public exposure, KEV-adjacent misconfigs). Run the initial assessment and
   triage: true misconfigurations, benchmark items not applicable (document), and accepted risks
   (exception process).
3. **Prioritize by toxic combinations, not finding counts.** Weight: internet exposure + sensitive
   data + critical misconfiguration (public DB with PII outranks 100 unencrypted dev disks). Use the
   platform's attack-path/toxic-combination features to find the few findings that actually enable
   breach.
4. **Route to owners with SLAs.** Auto-create tickets with evidence (resource, misconfiguration,
   benchmark reference, fix guidance) assigned to account owners. SLAs by severity: internet-exposed
   criticals in days, others in weeks. Escalate aging findings to management.
5. **Tune ruthlessly in the first month.** Suppress or scope findings that are false positives or
   accepted patterns (documented, with expiry). An untuned CSPM feed generating thousands of tickets
   will be muted by engineering — precision first, then coverage expansion.
6. **Add custom checks for org policy.** Encode requirements the benchmarks miss: mandatory tags,
   approved regions, required private endpoints, banned instance families, encryption with
   customer-managed keys. Keep custom checks few, documented, and owned.
7. **Shift findings left to IaC.** For recurring misconfiguration classes, add the equivalent check
   to IaC scanning (Checkov, tfsec, CloudFormation Guard) so the same issue stops being introduced.
   Track the "introduced in IaC vs. drifted in console" ratio — console drift indicates process
   gaps.
8. **Monitor CSPM health.** Alert on: failed account scans, API permission errors, and sudden
   asset-count drops (someone removed the role). A silently broken connector is a blind spot with a
   green dashboard.
9. **Report posture trends.** Weekly to engineering: new critical misconfigs, MTTR, top offending
   accounts/teams. Monthly to leadership: posture score trend, toxic-combination count, exception
   aging, and IaC-shift progress. Deltas, not snapshots.
10. **Review benchmarks and coverage quarterly.** Adopt new benchmark versions, reassess custom
    checks against architecture changes, and verify new services/regions are covered. Cloud
    providers ship new services monthly — coverage must follow.

## Expected outputs
- All cloud accounts onboarded with verified asset coverage and least-privilege roles.
- Baselined benchmarks with triaged findings, tuned noise, and org-specific custom checks.
- Owner-routed remediation with SLAs and escalation; toxic-combination prioritization.
- IaC-shifted preventive checks for recurring misconfiguration classes.
- Trend reporting on posture, MTTR, and coverage health.

## Pitfalls
- Partial onboarding: the unscanned account is where the breach happens. Reconcile against
  billing/organizations APIs continuously.
- Ticketing every low finding on day one: engineers will bulk-close or ignore. Phase severity, tune
  first, then expand automation.
- Treating CSPM as the whole cloud security program: it finds misconfigurations, not threats (that's
  CDR/CWPP), identities (that's CIEM), or vulnerabilities (that's agentless scanning). Know its
  lane.
- Stale exceptions: accepted risks without review become permanent. Expire and re-justify.
- Ignoring connector health: a broken scan looks identical to a clean account. Monitor the monitors.

## References
- CIS Benchmarks for AWS, Azure, and GCP Foundations
- NIST SP 800-53 CM-6, CA-7 (configuration settings, continuous monitoring)
- CSA Cloud Controls Matrix (CSPM control mappings)
- CISA KEV catalog (for prioritizing exploitable misconfigurations)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
