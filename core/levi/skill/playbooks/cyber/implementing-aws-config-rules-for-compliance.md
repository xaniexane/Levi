---
skill_id: cyber_implementing_aws_config_rules_for_compliance
name: AWS Config Rules for Compliance
description: Implement AWS Config rules for continuous compliance monitoring and auto-remediation.
risk: low
permissions: []
requires_confirmation: false
tags: [aws, compliance]
version: 1.0.0
---
## Purpose
Cloud configurations drift: an engineer opens a security group for debugging and forgets to close
it, an S3 bucket goes public, encryption gets disabled. AWS Config records configuration history and
evaluates rules continuously, turning "are we compliant right now?" from an audit scramble into a
dashboard. This playbook implements Config rules mapped to your compliance frameworks, with alerting
and auto-remediation where safe.

## When to use
- Meeting continuous-compliance needs for SOC 2, PCI DSS, HIPAA, CIS benchmarks, or internal
  baselines on AWS.
- After incidents caused by configuration drift (public S3 buckets, open security groups,
  unencrypted volumes).
- Multi-account AWS estates where manual config review is impossible.
- As the detective control beneath preventive guardrails (SCPs, CloudFormation Guard, Service
  Control Policies).
- To produce auditor-ready evidence of configuration compliance over time, not just at audit.

## Prerequisites
- AWS Config enabled in all in-scope regions and accounts (ideally via Organizations + StackSets or
  Control Tower).
- An aggregation setup (Config aggregator) for multi-account visibility.
- Defined compliance mappings: which framework controls map to which Config rules (CIS AWS
  Foundations, PCI DSS, HIPAA conformance packs).
- An SNS topic / EventBridge bus and ticketing integration for non-compliant alerts.
- IAM roles permitting Config recording and any auto-remediation actions (SSM Automation), scoped
  least-privilege.

## Procedure
1. **Enable Config correctly.** Turn on configuration recording for all supported resource types in
   every in-scope region — selective recording creates blind spots. Enable S3 delivery of
   configuration snapshots and history with versioning and restricted access.
2. **Deploy conformance packs for your frameworks.** Use AWS-managed conformance packs (CIS AWS
   Foundations, PCI DSS, HIPAA) as the starting baseline rather than hand-writing dozens of rules.
   Deploy via StackSets to all accounts so new accounts inherit compliance automatically.
3. **Add custom rules for org-specific policy.** Write Lambda-backed custom Config rules for
   requirements the managed packs miss: mandatory tagging (owner, data classification), approved AMI
   lists, required VPC endpoints, or region restrictions. Keep custom rules few and high-value —
   each one is code to maintain.
4. **Tune evaluation scope.** Exclude sandbox/development accounts or resource types where strict
   rules don't apply (via rule scope or separate packs per OU). A rule that fires constantly on dev
   accounts trains everyone to ignore it.
5. **Wire non-compliant events to response.** Route Config rule compliance-change events through
   EventBridge to SNS/ticketing with context: resource, rule, account, and last-known-good state.
   Severity-tag rules so critical findings (public S3, open admin ports) page while minor ones
   ticket.
6. **Implement auto-remediation where safe.** Use SSM Automation documents triggered by Config for
   low-risk fixes: enabling S3 block-public-access, turning on EBS encryption by default, removing
   0.0.0.0/0 from non-approved security groups. Require human approval for anything destructive or
   availability-affecting.
7. **Handle exceptions formally.** Resources that must violate a rule (a public bucket for a static
   site) get a documented exception: justification, compensating controls, owner, expiry. Implement
   exceptions as rule-scope exclusions with review dates, not as ignored alerts.
8. **Retain history for audit.** Keep configuration history for at least your audit lookback period
   (typically 1+ years). Demonstrate to auditors: the rule, the evaluation history, the finding, and
   the remediation record — the full control lifecycle.
9. **Review rule health monthly.** Check for: rules in error (permissions, Lambda failures), rules
   with 100% non-compliance (mis-scoped or wrong), and newly released managed rules worth adopting.
   Prune or fix broken rules — a red dashboard nobody trusts is worse than none.
10. **Report compliance as a trend.** Dashboard per framework: percent compliant resources, open
    non-compliant findings by severity and age, MTTR, and auto-remediation success rate. Present
    deltas to leadership and evidence packs to auditors.

## Expected outputs
- AWS Config recording enabled across accounts/regions with centralized aggregation.
- Deployed conformance packs (framework-mapped) plus org-specific custom rules.
- Alerting pipeline from non-compliant events to tickets/pages, severity-tagged.
- Auto-remediation for safe fixes with approval gates for risky ones.
- Audit-ready evidence: rule definitions, evaluation history, findings, remediations.

## Pitfalls
- Enabling Config without aggregation: per-account consoles don't scale; findings hide in accounts
  nobody checks.
- Deploying every managed rule at once: hundreds of findings on day one with no triage plan burns
  out the team. Phase by framework priority.
- Auto-remediating without approval on production: an SSM document that "fixes" security groups can
  break applications. Start with notify-only, add automation cautiously.
- Ignoring Config costs: recording all resource types across many accounts/regions generates
  significant charges — budget for it and exclude genuinely irrelevant types deliberately.
- Custom rules without maintenance: Lambda runtimes deprecate, APIs change — assign owners and test
  custom rules quarterly.

## References
- AWS Config documentation (rules, conformance packs, aggregators, remediation)
- CIS Amazon Web Services Foundations Benchmark (rule baseline)
- AWS conformance pack samples on GitHub (aws-config-rules / conformance packs)
- NIST SP 800-53 CM-6, SI-4 (configuration settings, system monitoring)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
