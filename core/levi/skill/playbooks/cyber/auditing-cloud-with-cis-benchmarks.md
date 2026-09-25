---
skill_id: cyber_auditing_cloud_with_cis_benchmarks
name: Auditing Cloud Environments with CIS Benchmarks
description: Assess cloud posture against CIS Benchmarks: scoring and remediation.
risk: moderate
permissions: [cloud.read]
requires_confirmation: true
tags: [cloud, compliance]
version: 1.0.0
---
# Auditing Cloud Environments with CIS Benchmarks

## Purpose

Use the Center for Internet Security (CIS) Benchmarks as a structured, control-by-control
method to audit AWS, Azure, GCP, and Kubernetes configurations, producing comparable,
evidence-backed findings instead of ad-hoc checklists.

## When to use

- Baseline security assessments of cloud accounts, subscriptions, or projects.
- Compliance programs mapping to CIS Controls or regulatory frameworks.
- Pre-migration or post-migration validation of cloud landing zones.
- Periodic reassessment to measure drift from a hardened baseline.
- Vendor or acquisition due diligence on an unfamiliar cloud footprint.

See also: benchmarking-kubernetes-with-kube-bench.md

## Prerequisites

- Written authorization and a defined scope: accounts, subscriptions, projects, regions,
  and resource tags in bounds.
- Read-only audit access per platform (AWS `SecurityAudit`, Azure `Security Reader` /
  `Reader`, GCP `roles/viewer` plus security-reviewer custom roles).
- The correct CIS Benchmark version for the platform and the target profile (Level 1 vs
  Level 2) agreed with the asset owner — Level 2 controls can break functionality and must
  be opt-in.

## Procedure

1. **Select benchmark and profile.**
   - Identify the exact CIS Benchmark (e.g., CIS Amazon Web Services Foundations
     Benchmark, CIS Microsoft Azure Foundations Benchmark, CIS Google Cloud Platform
     Foundations Benchmark, CIS Kubernetes Benchmark) and version.
   - Agree Level 1 (safe defaults) or Level 2 (defense-in-depth) with the owner and
     record the decision.

2. **Choose the assessment method.**
   - Prefer automated scanners mapped to CIS controls (Prowler, ScoutSuite, Microsoft
     Defender for Cloud regulatory compliance, GCP Security Command Center).
   - Plan manual verification for high-impact controls where automation lacks context.

3. **Run the automated assessment.**
   - Execute the scanner with read-only credentials across all in-scope
     accounts/projects.
   - Capture raw output with timestamps and scanner version for reproducibility.

4. **Verify identity controls manually.**
   - For the highest-weight section in every CIS benchmark — IAM: check root/MFA usage,
     dormant credentials, over-privileged policies, and (Azure) guest/legacy-auth
     settings.
   - Automated tools miss context like "this dormant key belongs to a break-glass
     process" — confirm with the owner before reporting.

5. **Verify logging and monitoring controls.**
   - Confirm CloudTrail / Activity Log / Cloud Audit Logs are enabled, centralized,
     integrity-protected (log file validation, locked retention), and actually alerting.
   - A log nobody reads fails the control's intent — check the alerting path, not just
     the log's existence.

6. **Verify network controls.**
   - Sample security groups / NSGs / firewall rules against the benchmark's expectations:
     no `0.0.0.0/0` to sensitive ports, default-deny posture, flow logging enabled.
   - Pay special attention to rules added as "temporary" that never expired.

7. **Verify data protection controls.**
   - Check encryption at rest for storage services, TLS enforcement on endpoints, and key
     management alignment with the benchmark's recommendations.
   - Note where platform defaults (e.g., SSE-S3) are relied upon versus customer-managed
     keys, per the benchmark's expectations.

8. **Adjudicate each finding.**
   - For every failed control determine: true misconfiguration, compensating control
     (documented and effective), or accepted risk (owner-signed, time-boxed).
   - Never report raw scanner failures as final findings.

9. **Score and trend.**
   - Record pass/fail per control section to create a benchmark score.
   - Compare against the previous assessment to show drift or improvement; investigate
     regressions first.

10. **Deliver the report.**
    - Provide control-by-control results with evidence (CLI output, query used, console
      path), adjudication notes, and remediation mapped to the platform's native controls.
    - Include the benchmark version, profile, scope, and scanner versions so the next
      audit is comparable.

## Key tools & commands

- Prowler (`prowler aws|azure|gcp`) — open-source CIS-mapped checks; JSON/CSV output for
  evidence.
- ScoutSuite — multi-cloud HTML reporting; good for point-in-time snapshots.
- Native: AWS Security Hub (CIS AWS Foundations standard), Microsoft Defender for Cloud
  (regulatory compliance dashboard), GCP Security Command Center.
- `aws configservice`, `az policy`, GCP Organization Policy constraints — verify the
  guardrails that *prevent* drift, not just detect it.

## Expected outputs

- Benchmark version, profile, scope, and scanner versions recorded.
- Control-by-control results with evidence and adjudication (true positive / compensating
  / accepted risk).
- Benchmark score per section and trend vs prior assessment.
- Remediation plan prioritized by CIS control criticality and exploitability.

## Pitfalls

- Running Level 2 checks without owner agreement and causing operational breakage during
  "read-only" verification of remediation.
- Treating scanner pass/fail as final — CIS controls have intent that automation
  approximates; manual adjudication is the actual audit.
- Version drift: benchmarking against an outdated CIS version the platform team no longer
  targets.
- Ignoring compensating controls (e.g., a WAF or private endpoint mitigating an "open"
  finding) and reporting noise the business will dismiss.

## References

- Center for Internet Security: CIS Benchmarks (AWS, Azure, GCP, Kubernetes) via CIS
  WorkBench.
- CIS Controls v8 mapping to benchmark sections.
- AWS Security Hub CIS standard documentation; Microsoft Defender for Cloud regulatory
  compliance; Google Cloud Security Command Center compliance dashboards.
- MITRE ATT&CK cloud techniques: T1078 (Valid Accounts), T1530 (Data from Cloud Storage),
  T1578 (Modify Cloud Compute Infrastructure), T1552 (Unsecured Credentials).

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
