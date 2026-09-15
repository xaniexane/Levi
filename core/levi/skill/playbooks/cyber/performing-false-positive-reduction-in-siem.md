---
skill_id: cyber_performing_false_positive_reduction_in_siem
name: False Positive Reduction in SIEM
description: Tune noisy detection rules with thresholds, allowlists, and context.
risk: info
permissions: []
requires_confirmation: false
tags: [siem, detection, tuning]
version: 1.0.0
---
# False Positive Reduction in SIEM

## Purpose

Alert fatigue kills detection: when 95% of alerts are benign, analysts
stop looking. This playbook gives detection engineers a disciplined tuning
process — measuring noise, understanding the benign behavior, and
suppressing or rewriting rules without blinding the SOC.

## When to use

- A rule's alert volume spikes or analysts consistently close its alerts
  as benign.
- Onboarding a new log source that floods existing correlations.
- Quarterly detection-health reviews of the highest-volume rules.
- Before an audit that will sample alert handling quality.

## Prerequisites

- Access to SIEM alert and case data with enough history (30–90 days)
  to measure true/false positive rates.
- A change process for detection content: dev/test before production,
  peer review, rollback plan.
- Baseline context: asset inventory and known-benign behaviors for the
  affected systems (backups, vulnerability scans, admin tooling).

## Procedure

1. Quantify the noise: for the target rule, compute alert volume,
   percentage closed as false positive, and analyst minutes per alert
   over the last 30 days.
2. Sample and classify: pull 20–50 representative alerts and label each
   benign cause — scheduled backups, scanners, admin scripts, expected
   service behavior — until the dominant causes emerge.
3. Fix data quality first: mis-parsed fields and missing asset context
   often create noise that no threshold can solve; correct the parser
   or enrichment.
4. Add precision, not just volume cuts: require an additional
   corroborating signal (e.g. the process is unsigned, the host is not in
   the admin jump list) before suppressing by the benign pattern.
5. Apply suppression carefully: allowlist by exact entity (known scanner
   IP, backup service account) with expiry dates — never suppress a
   whole rule or a broad subnet permanently.
6. Test changes in a shadow or staging view: replay recent data through
   the tuned rule and confirm true positives still fire before
   promoting to production.
7. Document every change: what was suppressed, why it was benign,
   expiry, and the detection-coverage impact.
8. Re-measure after two weeks: if the false-positive rate stays high,
   rewrite the rule logic; if true positives dropped, roll back and
   investigate.

## Expected outputs

- A tuned rule with documented suppressions, thresholds, and expiry
  dates.
- Before/after metrics: alert volume, false-positive rate, analyst
  time saved.
- A detection-coverage note confirming true positives still fire.
- A recurring tuning schedule for the noisiest rules.

## Pitfalls

- Suppressing by IP or user without expiry: benign today, compromised
  tomorrow.
- Tuning to the metric instead of the threat: a quiet rule that misses
  real attacks is a failure, not a success.
- Changing production rules directly without staging or peer review.
- Ignoring the root cause: sometimes the fix is a better log source,
  not a quieter rule.

## References

- SANS guidance on SIEM tuning and detection engineering practices
- MITRE ATT&CK: detection strategies per technique page
- NIST SP 800-92, Guide to Computer Security Log Management
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
