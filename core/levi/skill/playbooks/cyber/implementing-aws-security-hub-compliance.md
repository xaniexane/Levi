---
skill_id: cyber_implementing_aws_security_hub_compliance
name: Compliance Monitoring with AWS Security Hub
description: Operate Security Hub's compliance standards as a continuous audit program with evidence and exceptions.
risk: info
permissions: []
requires_confirmation: false
tags: [aws, compliance]
version: 1.0.0
---
## Purpose
Security Hub's compliance standards (CIS, PCI DSS, NIST) turn frameworks into continuously evaluated
controls — but raw control findings don't satisfy auditors without process: scoping, exception
handling, remediation evidence, and trend reporting. This playbook operates Security Hub as a
continuous compliance program, producing auditor-ready evidence instead of a red dashboard.

## When to use
- Preparing for or maintaining SOC 2, PCI DSS, HIPAA, or ISO 27001 with AWS in scope.
- Replacing point-in-time audit scrambles with continuous control monitoring.
- After audit findings about undetected configuration drift between assessments.
- When leadership wants a defensible, always-current compliance posture view.
- As the compliance-reporting layer on top of the Security Hub implementation playbook.

## Prerequisites
- Security Hub implemented per the companion playbook (administrator account, member enrollment,
  regions).
- A control-to-framework mapping: which Security Hub controls satisfy which audit requirements (many
  auditors accept AWS's mappings — confirm with yours).
- Defined exception policy: who approves, required compensating controls, maximum duration.
- Ticketing integration for failed-control remediation with severity-based SLAs.
- Auditor expectations documented: evidence format, lookback period, sampling approach.

## Procedure
1. **Select and scope standards deliberately.** Enable the standards matching your audit
   obligations. Immediately scope out controls that don't apply (documented per control, e.g., "RDS
   controls N/A — no RDS in scope accounts") and assign remaining controls to owner teams. An
   unowned control never gets fixed.
2. **Baseline the control posture.** Export the initial pass/fail per control per account. Triage
   failures into: genuine misconfigurations (fix), mis-scoped controls (fix the scope), and accepted
   risks (exception process). This triage is the program's foundation — do it before automating
   anything.
3. **Build the exception register.** For each accepted failure: control ID, resource scope, business
   justification, compensating controls, owner, approver, and expiry date (max 12 months, aligned to
   audit cycle). Exceptions live in a register, not in suppressed findings — auditors want the paper
   trail.
4. **Automate remediation evidence collection.** For fixed controls, capture: the finding, the
   change ticket, the re-evaluation showing PASS, and timestamps. Store evidence packs per control
   per quarter in an auditor-accessible location. Manual screenshot collection at audit time is the
   failure mode you're eliminating.
5. **Route failures by severity and age.** New failures ticket to owners with SLAs (critical
   controls: days; others: weeks). Escalate aging failures (30/60/90 days) to management.
   Distinguish new failures (regressions — urgent) from long-standing ones (backlog — planned).
6. **Monitor for control regressions specifically.** Alert when a control flips from PASS to FAIL —
   that's configuration drift, the exact thing continuous monitoring exists to catch. Regression
   alerts get higher priority than long-standing failures.
7. **Review exceptions and scope quarterly.** Re-validate every exception before expiry: does the
   justification still hold? Re-check scoped-out controls when architecture changes (new services
   adopted, new regions enabled). Stale scope is how drift hides.
8. **Produce the auditor evidence pack.** Per audit cycle: standard enabled, control results
   history, exception register with approvals, remediation tickets with resolution evidence, and the
   regression-alert log. Walk the auditor through the process once — then hand them read access.
9. **Trend and report.** Monthly to leadership: control pass rate per standard, new failures vs.
   remediated, exception count and aging, top failing controls by recurrence. The story is "posture
   improving and drift caught fast," told with deltas.
10. **Close the loop with preventive controls.** For controls that fail repeatedly, add prevention:
    SCPs, CloudFormation Guard rules, or pipeline checks that block the misconfiguration before
    deployment. Compliance findings should migrate from detective to preventive over time.

## Expected outputs
- Scoped standards with control-to-owner mapping and documented exclusions.
- An exception register with justifications, compensating controls, and expiries.
- Automated evidence packs per control per period, auditor-accessible.
- Regression alerting on PASS→FAIL flips with escalation paths.
- Trend reporting and a preventive-control backlog for repeat failures.

## Pitfalls
- Enabling standards without scoping: hundreds of N/A failures drown the real ones and auditors
  question your competence, not just your posture.
- Exceptions as permanent suppressions: without expiries and re-validation, the register becomes a
  write-off ledger.
- Collecting evidence manually at audit time: defeats the purpose. Automate evidence capture into
  the remediation workflow.
- Ignoring control regressions: a control that was passing and now fails is the highest-signal event
  in compliance monitoring — treat it as such.
- Confusing compliance with security: passing CIS controls is a baseline, not a threat model. Keep
  the threat-driven program (GuardDuty findings, attack paths) separate and equally funded.

## References
- AWS Security Hub standards documentation (CIS, PCI DSS, NIST 800-53 mappings)
- CIS Amazon Web Services Foundations Benchmark
- AICPA SOC 2 Trust Services Criteria (CC7 — system monitoring)
- PCI DSS v4.0 (continuous compliance expectations)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
