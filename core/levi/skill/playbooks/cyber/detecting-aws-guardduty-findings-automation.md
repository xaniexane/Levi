---
skill_id: cyber_detecting_aws_guardduty_findings_automation
name: Detecting AWS GuardDuty Findings Automation
description: Operationalize GuardDuty with automated triage, enrichment, and response playbooks via EventBridge and Lambda.
risk: info
permissions: []
requires_confirmation: false
tags: [aws, detection, automation]
version: 1.0.0
---
## Purpose

Turn GuardDuty from an alert inbox into an automated detection-and-response pipeline: findings enriched, deduplicated, routed by severity, and — for high-confidence classes — acted on automatically via EventBridge and Lambda. Automation handles the known-bad; analysts handle the novel.

## When to use

- Standing up GuardDuty across an AWS organization (delegated administrator model).
- Reducing mean-time-to-respond on GuardDuty findings through automation.
- Building consistent triage for GuardDuty finding types (Tor, crypto-mining, credential exfiltration).
- Auditing that GuardDuty coverage is complete (all accounts, all regions, all protection plans).

## Prerequisites

- GuardDuty enabled via delegated administrator across the organization, all regions, with S3/RDS/Lambda/EKS/EBSS protection plans per your threat model.
- EventBridge rules and Lambda (or Step Functions) deployment capability; SNS topics for analyst notification.
- A finding-severity mapping agreed with the SOC: which types auto-remediate, which page, which ticket.
- Suppression rules documented for known-benign patterns (pen-test windows, security scanners).

## Procedure

1. **Verify complete coverage.** Confirm GuardDuty is enabled in every region of every account via the delegated admin. Check that protection plans (S3, EKS audit logs, RDS, Lambda, EBS volumes) are on where the workloads exist. Unmonitored regions are where attackers operate — verify, don't assume.
2. **Build the EventBridge routing layer.** Create rules matching GuardDuty findings by severity and type: critical/high → immediate analyst notification + enrichment Lambda; medium → ticket queue; low/informational → aggregated daily digest. Route on `detail.type` and `detail.severity`, not just severity — some medium findings (e.g. `UnauthorizedAccess:IAMUser/ConsoleLoginSuccess.B`) deserve fast handling.
3. **Automate enrichment before human triage.** On each significant finding, a Lambda function gathers context: the principal's recent CloudTrail activity, the instance's tags and owner, related findings in the last 7 days, and threat-intel reputation of involved IPs/domains. Analysts get a pre-built case, not a raw finding.
4. **Automate response for high-confidence finding classes.** Pre-authorize playbooks: `CryptoCurrency:EC2/BitcoinTool.B` → snapshot and isolate the instance; `Exfiltration:S3/*` → block the external IP at the bucket policy and snapshot access logs; `UnauthorizedAccess:IAMUser/*Tor*` → disable the key and force rotation. Each automation logs its actions and notifies the SOC — automation acts, humans verify.
5. **Handle finding lifecycle properly.** Auto-archive findings only for documented benign patterns with expiry dates (pen-test windows, approved scanners). Never auto-archive entire finding types — today's benign `Recon:EC2/PortProbe` source is tomorrow's attacker. Review archived findings monthly for pattern changes.
6. **Tune with feedback.** Weekly review: false-positive rate per finding type, automation action accuracy, and mean-time-to-triage. Feed tuning back into EventBridge routing (re-route noisy types) and suppression rules. Track which finding types most often lead to real incidents — invest detection engineering there.
7. **Test the pipeline end to end.** Quarterly, generate controlled test findings (GuardDuty's sample findings generator) and verify: routing fires, enrichment completes, notifications arrive, and automated responses execute. A pipeline that's never tested fails silently during the real incident.

## Expected outputs

- Organization-wide GuardDuty with all protection plans, routed through EventBridge by type and severity.
- Automated enrichment and pre-authorized response playbooks for high-confidence finding classes.
- Documented suppression rules with expiries, weekly tuning, and quarterly end-to-end tests.

## Pitfalls

- Enabling GuardDuty in one region — attackers use the regions you don't monitor.
- Auto-archiving whole finding types — you lose the signal permanently.
- Automation without notification — the SOC discovers the Lambda isolated production at 3 AM with no context.
- No enrichment — analysts triage raw findings slowly and inconsistently.
- Suppression rules without expiry — the pen-test exception from 2024 is still hiding 2026's attacker.

## References

- AWS documentation — GuardDuty finding types, EventBridge integration, delegated administration
- AWS Security Blog — automating GuardDuty response patterns
- MITRE ATT&CK — map finding types to techniques for coverage analysis
- NIST SP 800-61 Rev. 2 — incident handling for automated detections
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
