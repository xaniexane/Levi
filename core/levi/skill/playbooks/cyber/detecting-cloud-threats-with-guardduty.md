---
skill_id: cyber_detecting_cloud_threats_with_guardduty
name: Detecting Cloud Threats with GuardDuty
description: Build a GuardDuty-centered cloud threat detection program with tuned findings and analyst triage workflows.
risk: info
permissions: []
requires_confirmation: false
tags: [aws, cloud, detection]
version: 1.0.0
---
## Purpose

Make GuardDuty the reliable core of cloud threat detection: complete coverage, tuned finding handling, analyst triage workflows, and integration with the broader SOC. Distinct from the automation playbook — this one is about detection quality and the human process around it.

## When to use

- Establishing cloud threat detection for AWS workloads.
- Tuning a GuardDuty deployment analysts don't trust (too noisy or too quiet).
- Building the SOC's cloud triage runbooks and severity model.
- Preparing for audits requiring cloud intrusion-detection evidence.

## Prerequisites

- GuardDuty enabled organization-wide (delegated administrator), all regions, relevant protection plans.
- Findings centralized (Security Hub or SIEM) with analyst access.
- Baseline understanding of the environment's normal cloud behavior (automation, scanners, pen tests).
- Defined severity tiers and SLAs agreed with the SOC.

## Procedure

1. **Confirm coverage is genuinely complete.** Verify every account and region, and that protection plans match the workload: EKS protection where Kubernetes runs, RDS where databases live, S3 for data-heavy accounts, Lambda for serverless, EBS for EC2 fleets. Document any intentional gaps with risk acceptance — unknown gaps are the ones attackers find.
2. **Learn the finding taxonomy cold.** Study the finding types most relevant to your environment: `UnauthorizedAccess` (Tor, unusual geo, IAM anomalies), `CryptoCurrency` (mining), `Exfiltration` (S3, DNS), `Recon` (port probes, IAM enumeration), `Trojan`/`Backdoor` (C2), and `Policy:IAMUser/*` (credential and logging tampering). Analysts who know what each type means triage 10x faster.
3. **Build per-type triage runbooks.** For each major finding type, write the 15-minute triage: what to check in CloudTrail (which principal, what APIs, what timeframe), what host evidence to pull (for EC2 findings), when to escalate to incident, and when to close as benign. Runbooks turn findings into consistent investigations instead of ad-hoc guesses.
4. **Tune with trusted IP lists and suppression discipline.** Add your scanners, pen-test ranges, and known automation to trusted IP lists so their activity doesn't generate findings. Use suppression rules only for documented, time-bounded benign patterns — never suppress a finding type entirely. Review suppressions monthly.
5. **Correlate findings into incidents.** A single `Recon:EC2/PortProbe` is noise; the same source followed by `UnauthorizedAccess:EC2/SSHBruteForce` and then `CryptoCurrency:EC2/BitcoinTool.B` is an incident timeline. Build correlation rules that chain findings by principal, instance, or source IP within 24–72 hour windows, and present them as cases.
6. **Hunt beyond the findings.** GuardDuty detects known-bad patterns; hunt for the novel: principals with GuardDuty-quiet but CloudTrail-anomalous behavior, findings in accounts with no baseline (new accounts deserve extra scrutiny), and low-severity findings that cluster around one asset. The findings are the starting point, not the finish line.
7. **Measure and report detection effectiveness.** Track: mean time from finding to triage, true-positive rate per finding type, coverage percentage, and incidents first detected by GuardDuty versus other sources. Report quarterly — these metrics justify the service and guide tuning investment.

## Expected outputs

- Complete GuardDuty coverage with documented protection-plan mapping and per-type triage runbooks.
- Disciplined suppression (documented, time-bounded) and trusted-IP management.
- Finding-correlation rules producing cases; quarterly effectiveness metrics.

## Pitfalls

- Partial coverage treated as complete — check every region, not just the console's default view.
- No runbooks — every analyst triages differently and inconsistently.
- Suppressing noisy finding types instead of tuning them — the noise was signal about your environment.
- Treating GuardDuty as the whole cloud detection strategy — it's one sensor; CloudTrail hunting and CSPM complete the picture.
- Ignoring low-severity findings entirely — attackers' early phases live there.

## References

- AWS documentation — GuardDuty finding types and severity reference
- AWS Security Hub documentation — findings aggregation
- MITRE ATT&CK — cloud technique mapping for finding coverage
- NIST SP 800-61 Rev. 2 — incident handling workflows
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
