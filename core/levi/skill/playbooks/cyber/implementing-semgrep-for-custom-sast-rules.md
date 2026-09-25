---
skill_id: cyber_implementing_semgrep_for_custom_sast_rules
name: Implementing Semgrep for Custom SAST Rules
description: Write and deploy custom Semgrep SAST rules for your codebase's specific flaw patterns, integrated into CI with triage workflows.
risk: low
permissions: []
requires_confirmation: false
tags: [sast, appsec, devops]
version: 1.0.0
---
## Purpose

Generic SAST rules miss organization-specific flaws: dangerous internal
APIs, framework misuse patterns, and recurring bug classes from your own
incident history. Semgrep's accessible rule syntax makes custom rules
practical. This playbook covers writing, testing, deploying, and
maintaining custom Semgrep rules integrated into CI.

## When to use

- Encoding lessons from security incidents into preventative rules.
- Banning dangerous internal APIs or patterns (unsafe deserializers,
  raw SQL builders, weak crypto).
- Enforcing secure-framework usage (your auth library, not hand-
  rolled checks).
- Supplementing generic SAST with codebase-specific coverage.

## Prerequisites

- A Semgrep installation (CLI or CI-integrated) and a rule repository
  under version control.
- Access to the target repositories and their primary languages/
  frameworks.
- CI pipeline access to add SAST gates on pull requests and scheduled
  scans.
- Security-incident and pentest history to mine for rule candidates.

## Procedure

1. **Mine your flaw history.** Review past vulnerabilities, pentest
   findings, and bug-bounty reports for recurring patterns specific
   to your codebase and frameworks. Each recurring pattern is a rule
   candidate — prioritize by severity and frequency.
2. **Write precise rules.** Use Semgrep's pattern syntax with
   metavariables, pattern-inside/pattern-not-inside for context, and
   taint tracking (sources/sanitizers/sinks) for dataflow flaws like
   injection. Precision beats coverage: a rule with 90% false
   positives will be disabled.
3. **Test against the codebase.** Run new rules against the full
   repository and triage every hit. Tune until the rule is high-
   precision on your code, and add test cases (true positives and
   true negatives) alongside each rule.
4. **Classify severity honestly.** Reserve blocking/error severity for
   high-confidence, high-impact findings. Advisory rules (warning/
   info) suit style-level or uncertain patterns. Mis-severitized
   rules either block development unnecessarily or get ignored.
5. **Integrate into CI thoughtfully.** Run Semgrep on pull requests
   (diff-aware for speed) with blocking only on error-severity rules;
   run the full rule set on a schedule for the whole codebase.
   Provide developers with clear fix guidance per rule (custom
   messages with examples).
6. **Build the triage workflow.** Findings need owners and SLAs:
   auto-assign to PR authors, track aging, and provide a documented
   suppression process (with expiry and security review) for false
   positives — not silent ignores.
7. **Maintain the rule set.** Review rule performance quarterly:
   precision, findings fixed vs. suppressed, and coverage of new
   frameworks or languages adopted. Retire rules for removed APIs;
   write new rules for each significant incident.
8. **Measure effectiveness.** Track: flaws caught pre-merge, recurrence
   rate of ruled patterns (should drop toward zero), developer
   satisfaction, and time from rule idea to deployment. Rules that do
   not reduce recurrence are not working.

## Expected outputs

- A custom rule set with tests, severity classifications, and fix
  guidance per rule.
- CI integration: PR diff-aware blocking plus scheduled full scans.
- Triage workflow with SLAs and suppression governance.
- Effectiveness metrics: pre-merge catches, recurrence rates.

## Pitfalls

- Low-precision rules — developers disable noisy SAST; invest in
   tuning before enforcing.
- Blocking on low-severity findings — blocks trains and breeds
   resentment; block only on high-confidence, high-impact rules.
- Rules without tests rot — codebase evolution silently breaks rule
   patterns; tests catch it.
- Suppression without governance — `# nosemgrep` sprawl defeats the
   program; require justification and expiry.
- Writing rules for flaws your frameworks already prevent —
   focus custom rules on your actual residual risk.

## References

- Semgrep official documentation (rule syntax, taint mode)
- OWASP: SAST guidance and code-review methodology
- NIST SP 800-53: flaw remediation controls (SI-10, SI-2)
- CWE database (weakness taxonomy for rule classification)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
