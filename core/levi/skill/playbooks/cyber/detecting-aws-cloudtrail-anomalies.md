---
skill_id: cyber_detecting_aws_cloudtrail_anomalies
name: Detecting AWS CloudTrail Anomalies
description: Hunt anomalous API activity in CloudTrail with baselined behavioral detections beyond default GuardDuty findings.
risk: info
permissions: []
requires_confirmation: false
tags: [aws, cloud, detection]
version: 1.0.0
---
## Purpose

Find the AWS attacks that slip past default detections: anomalous CloudTrail API patterns — unusual callers, impossible geographies, privilege-probing sequences — using behavioral baselines you build yourself. CloudTrail is the ground truth of your AWS control plane; this playbook teaches you to read it like an investigator.

## When to use

- Hunting for compromised AWS credentials or insider misuse.
- Building custom detections beyond GuardDuty's defaults.
- Investigating an alert where CloudTrail provides the authoritative timeline.
- Validating that CloudTrail logging itself is complete and tamper-evident.

## Prerequisites

- CloudTrail enabled in all regions (organization trail) with log file validation, delivered to a centralized, immutable S3 bucket.
- Athena or a SIEM with CloudTrail parsed (or CloudTrail Lake) for ad-hoc querying.
- Baseline of normal API activity per role/user: which principals call which APIs at what rates.
- Alerting pipeline for custom detections with runbooks attached.

## Procedure

1. **Verify logging integrity first.** Confirm the organization trail covers all regions, log file validation is enabled, and the S3 bucket has Object Lock / MFA delete. Alert on `StopLogging`, `DeleteTrail`, or `UpdateTrail` events — attackers disable logging before doing anything else. A gap in CloudTrail is itself a high-severity finding.
2. **Baseline API behavior per principal.** For each IAM user/role, record: normal API call mix, call rates, source IPs/ASNs, and active hours. Roles used by automation are highly regular — any deviation (new APIs, new sources, interactive hours) is significant. Human users get looser baselines but geography and hour anomalies still apply.
3. **Detect reconnaissance sequences.** Alert on: `iam:List*` / `Get*` bursts, `sts:GetCallerIdentity` from new sources (attackers validating stolen keys), `ec2:Describe*` sweeps, and `s3:ListBuckets` followed by `GetObject` patterns. Reconnaissance is the noisiest phase — catch it here.
4. **Detect privilege-escalation probing.** Alert on: `iam:CreatePolicyVersion`, `iam:AttachUserPolicy`/`AttachRolePolicy`, `iam:PutUserPolicy`, `sts:AssumeRole` to new roles, and `iam:PassRole` combined with service creation. Chain these with the reconnaissance alerts — recon followed by policy modification is an active attack, not curiosity.
5. **Detect persistence and exfiltration staging.** Alert on: new IAM users/keys created, CloudTrail/S3-logging modifications, new EC2 key pairs, snapshot sharing (`ModifySnapshotAttribute`), S3 bucket policy changes to public, and large `GetObject` volumes. These are the "setting up to steal or stay" signals.
6. **Hunt geographically and temporally.** Alert on API calls from countries the principal never uses, calls at hours inconsistent with the principal type, and user-agent anomalies (a human user's key suddenly used by `aws-cli` from a datacenter ASN). Join with GuardDuty findings for corroboration, not replacement.
7. **Build the investigation runbook.** For any CloudTrail anomaly: pivot on the access key ID to list all its activity, check `userAgent` and source IP, review what the key did before the anomaly (compromise timeline), and check for concurrent anomalies on other principals (campaign vs. isolated). Preserve the relevant log files with legal hold if it's an incident.

## Expected outputs

- An integrity-verified organization CloudTrail with tamper alerting on logging changes.
- Per-principal behavioral baselines with detections for recon, privilege probing, persistence, and exfiltration staging.
- An investigation runbook pivoting on access key, source, and timeline.

## Pitfalls

- Regional trails only — attackers operate in regions you're not logging; use an organization trail.
- No log file validation — you can't prove the logs weren't altered.
- Alerting on raw API volume without baselines — AWS is chatty; volume alone is noise.
- Ignoring `userAgent` — it's one of the best compromise signals in CloudTrail.
- Treating GuardDuty as a replacement for CloudTrail hunting — GuardDuty finds known-bad; hunting finds novel.

## References

- AWS documentation — CloudTrail log file validation, organization trails, CloudTrail Lake
- MITRE ATT&CK — cloud techniques (T1078, T1552.005, T1530)
- AWS Security Blog — threat detection guidance for CloudTrail
- NIST SP 800-92 (Guide to Computer Security Log Management)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
