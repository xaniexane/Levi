---
skill_id: cyber_performing_aws_account_enumeration_with_scout_suite
name: Performing AWS Account Audits with Scout Suite (Authorized)
description: Audit your own AWS accounts for misconfigurations using Scout Suite.
risk: low
permissions: []
requires_confirmation: false
tags: [cloud-security, aws, auditing]
version: 1.0.0
---

## Purpose
This playbook uses Scout Suite to audit AWS accounts your organization owns: read-only enumeration of services and configurations, mapped to clear findings with remediation guidance. It covers only accounts you are authorized to assess.

## When to use
- Periodic cloud security posture review or pre-audit assessment.
- After organizational changes: new accounts, migrations, or acquisitions.
- Validating that guardrails (SCPs, Config rules) are actually effective.

## Prerequisites
- Read-only IAM credentials for the target accounts (SecurityAudit managed policy is the standard starting point).
- Authorization to assess the accounts, including any member accounts in an Organization.
- A findings workflow: Scout Suite output must land somewhere actionable.

## Procedure
1. **Scope and authorize.** List the accounts and regions in scope; confirm read-only access and note any sensitive workloads requiring extra care.
2. **Run with least privilege.** Execute Scout Suite with the read-only role; never use administrative credentials for assessment tooling.
3. **Review findings by service.** Work through the HTML report systematically: IAM (unused keys, overprivileged policies, no MFA), S3 (public buckets, unencrypted), EC2 (open security groups), CloudTrail (disabled or incomplete logging), and others.
4. **Validate before reporting.** Confirm each finding in the console or CLI; Scout Suite rules can misfire on legitimate architectures (e.g., intentional public buckets with compensating controls).
5. **Prioritize by exposure.** Public-facing misconfigurations and identity findings first; cosmetic deviations last.
6. **Remediate with guardrails.** Fix the findings and add preventive controls (SCPs, Config rules, IaC checks) so the same misconfigurations cannot recur.
7. **Re-run to verify.** Execute Scout Suite again after remediation; track finding counts per account over time as the posture metric.

8. **Cover all regions.** Run with `--all-regions` awareness; misconfigurations hide in regions nobody looks at.
9. **Integrate into CI for IaC.** Run Scout Suite-style checks against Terraform plans in the pipeline so misconfigurations are caught before they deploy.

## Expected outputs
- Scout Suite reports per account with validated findings.
- Remediation tickets linked to findings with re-scan verification.
- Posture trend: finding counts and critical exposures over time.
- Example: the audit finds an S3 bucket with public read access holding customer exports; it is restricted the same day, an SCP is added to prevent recurrence, and the re-scan confirms closure.

## Pitfalls
- Assessing accounts without authorization, including "forgotten" shadow accounts — get scope in writing first.
- Reporting unvalidated scanner output as findings.
- Fixing findings without preventive guardrails: they reappear next quarter.

## References
- Scout Suite documentation (github.com/nccgroup/ScoutSuite — project docs).
- AWS security best practices (docs.aws.amazon.com/security).
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
