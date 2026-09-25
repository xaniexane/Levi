---
skill_id: cyber_performing_cloud_forensics_with_aws_cloudtrail
name: Cloud Forensics with AWS CloudTrail
description: Investigate AWS incidents using CloudTrail management and data event logs for timeline reconstruction.
risk: info
permissions: []
requires_confirmation: false
tags: [cloud, forensics, aws]
version: 1.0.0
---

## Purpose

CloudTrail is the authoritative record of "who called which AWS API, when, from where" — the closest thing AWS gives you to a system-wide audit trail. This playbook covers using CloudTrail forensically: ensuring the trail is trustworthy, querying management and data events for attacker activity, reconstructing timelines, and recognizing the log's blind spots. It assumes you are investigating within your own AWS organization.

## When to use

- Any suspected compromise of AWS resources, credentials, or identities.
- Reconstructing the sequence of API calls behind a GuardDuty or Detective finding.
- Validating whether a leaked access key was actually used, and for what.
- Auditing privileged actions (IAM changes, policy attachments, console logins) over a time window.
- Preparing CloudTrail as a forensic source before incidents (trail design review).

## Prerequisites

- An organization trail (or account trails) writing to a centralized, integrity-protected S3 bucket: log file validation enabled, MFA delete on the bucket, and restricted write access so attackers cannot tamper with history.
- Sufficient retention: CloudTrail Lake or S3 lifecycle policy covering your investigation window (90 days in Event History is rarely enough for forensics).
- Query tooling: CloudTrail Lake SQL, Athena over the S3 bucket, or a SIEM ingesting the logs.
- Familiarity with the CloudTrail event schema: `eventName`, `eventSource`, `userIdentity`, `sourceIPAddress`, `userAgent`, `requestParameters`, `responseElements`, `errorCode`.
- A list of the identities, resources, and time bounds under investigation.

## Procedure

1. **Verify trail integrity first.** Confirm log file validation digests are intact for the investigation window and that no `StopLogging` / `DeleteTrail` / `UpdateTrail` events (or gaps in expected delivery) suggest tampering. An untrustworthy trail changes what conclusions you can draw.
2. **Establish the identity under investigation.** Extract all events for the suspect `userIdentity` (ARN, access key ID, assumed-role session): first and last seen, source IPs, user agents. Compare against the identity's historical baseline — a key used from a new country at 3 AM with a scripted user agent is the classic signal.
3. **Reconstruct the API timeline.** Pull events in chronological order and annotate: reconnaissance calls (`Describe*`, `List*`, `Get*`), privilege moves (`Attach*Policy`, `CreateAccessKey`, `AssumeRole`), persistence (`CreateUser`, `PutRolePolicy`, backdoor Lambda), and impact (`Delete*`, `TerminateInstances`, S3 `GetObject` on sensitive buckets).
4. **Hunt for anti-forensics.** Search for `StopLogging`, `DeleteTrail`, `DeleteBucket` on the log bucket, `PutBucketLifecycleConfiguration` shortening retention, and CloudWatch Logs subscription filter deletions. Attackers who know AWS try to blind CloudTrail early.
5. **Correlate with data-plane sources.** CloudTrail management events do not show S3 object reads by default — enable data events for sensitive buckets/tables, then join `GetObject`/`GetItem` events to the management timeline. Add VPC flow logs and GuardDuty findings to complete the picture.
6. **Attribute console vs. programmatic access.** Use `userAgent` and `eventType` to distinguish console sessions from CLI/SDK calls. Attackers typically use programmatic access; a sudden shift from console to scripted calls on a human user's identity is a strong compromise indicator.
7. **Check for cross-account and federated paths.** Follow `AssumeRole` chains across accounts, review `sts:GetSessionToken` and federation events, and inspect resource policies the attacker may have modified to grant external principals access.
8. **Preserve and report.** Export the relevant event set (with hashes) to the forensic account, document the exact queries used so the timeline is reproducible, and write findings distinguishing confirmed attacker actions from responder and automation activity (filter out your own collection calls).

## Expected outputs

- Integrity verification result for the trail over the investigation window.
- A chronological attacker timeline: reconnaissance, privilege escalation, persistence, and impact API calls.
- Attribution evidence: IPs, user agents, key IDs, and role session chains.
- Anti-forensics assessment: whether logging was tampered with and when.
- Preserved event exports with hashes and reproducible query definitions.

## Pitfalls

- Relying on the 90-day Event History window for incidents older than 90 days — ensure Lake or S3 archival before you need it.
- Treating absence of data events as absence of activity; S3 reads and Lambda invokes are not logged unless data events are enabled.
- Forgetting that the attacker's first move is often disabling the trail — check for logging gaps before concluding "nothing happened."
- Confusing responder/automation API calls with attacker activity; tag your own collection actions in the timeline.
- Ignoring `errorCode` fields: `AccessDenied` bursts are reconnaissance, and they reveal what the attacker was after.

## References

- AWS CloudTrail documentation (event reference, log file validation, CloudTrail Lake)
- AWS re:Inforce and security blog guidance on CloudTrail forensics
- MITRE ATT&CK T1078 (Valid Accounts), T1136 (Create Account), T1562.008 (Disable Cloud Logs)
- NIST SP 800-92, "Guide to Computer Security Log Management"
- SANS guidance on AWS logging and incident response
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
