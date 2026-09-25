---
skill_id: cyber_implementing_cloud_trail_log_analysis
name: CloudTrail Log Analysis
description: Build CloudTrail logging and analysis for AWS audit trails, threat detection, and forensics.
risk: low
permissions: []
requires_confirmation: false
tags: [aws, logging]
version: 1.0.0
---
## Purpose
CloudTrail is the authoritative record of who did what in AWS — every API call, by whom, from where,
with what result. Without it, cloud incidents are uninvestigable: you cannot answer "how did the
attacker get in" or "what did they touch." This playbook implements comprehensive CloudTrail logging
(management + data events), centralized storage, and the analysis workflows for threat detection and
forensics.

## When to use
- Establishing the audit and forensic foundation for any AWS security program.
- After incidents where missing or incomplete API logs hampered investigation.
- Meeting log-retention and audit-trail requirements (SOC 2, PCI DSS, HIPAA, FedRAMP).
- Building cloud threat-detection content (impossible travel, privilege escalation, data-access
  anomalies).
- Before granting broad AWS access: logging must precede privilege.

## Prerequisites
- An Organizations structure with a dedicated log-archive account (per AWS best practice).
- Defined retention: hot analysis window (e.g., 90 days queryable) plus cold archive (1-7 years per
  compliance).
- A SIEM or analysis platform (Athena, OpenSearch, Splunk, or native CloudTrail Lake) chosen for
  query scale.
- KMS key for log encryption with a key policy restricting decryption appropriately.
- Understanding of CloudTrail event types: management events, data events, Insights, network
  activity events.

## Procedure
1. **Create an organization trail in the log-archive account.** Enable an organization-wide trail
   capturing all regions (including future regions) and all accounts. This is the non-negotiable
   foundation — per-account trails fragment the record and get disabled individually.
2. **Enable management events for all.** Record read and write management events. These answer "who
   changed what configuration" — the core of both audit and incident response. Verify with a test
   API call that events land within the expected latency.
3. **Enable data events selectively.** Turn on S3 object-level and Lambda execution logging for
   buckets/functions holding sensitive data or critical code. Data events are high-volume and costly
   — scope to crown-jewel resources, not the entire estate.
4. **Harden the log pipeline.** Deliver logs to an S3 bucket with: versioning, MFA delete, Object
   Lock (WORM) for the retention period, bucket policy denying deletion, and restricted access
   (security team + SIEM role only). Enable log file validation (digest files) so tampering is
   detectable.
5. **Encrypt with a customer-managed KMS key.** Use SSE-KMS with a key whose policy allows
   CloudTrail to write and only authorized roles to read. Rotate per policy. The threat model
   includes attackers deleting or reading logs — encryption and access control address both.
6. **Build the analysis layer.** Options: CloudTrail Lake (SQL queries, 7-year retention), Athena on
   the S3 archive (cheap, flexible), or SIEM ingestion (correlation with other sources). Ensure
   analysts can query by: user/role, source IP, event name, resource, time range, and error code —
   the standard forensic pivots.
7. **Write baseline detection content.** Priority detections: ConsoleLogin failures and successes
   without MFA, AssumeRole to privileged roles from unusual IPs, IAM policy changes (PutUserPolicy,
   AttachRolePolicy), security-group openings to 0.0.0.0/0, S3 bucket policy changes to public, KMS
   key policy changes, CloudTrail StopLogging/ DeleteTrail (tamper attempts — page immediately), and
   GetSecretValue/Decrypt spikes (credential/data access).
8. **Establish the forensic workflow.** Document: how to scope a time window, list all actions by a
   principal, identify first malicious action, and export evidence with integrity (hash the exported
   logs, record the query). Time-to-first-answer for "what did this role do in the last 30 days"
   should be minutes.
9. **Monitor the pipeline itself.** Alert on: trail disabled or deleted, S3 delivery failures, KMS
   key deletion/disablement, and log-volume anomalies (sudden drops suggest tampering; spikes
   suggest incidents or misconfiguration). Pipeline health is a security control.
10. **Test with a simulated incident.** Quarterly: perform a controlled malicious sequence in a test
    account (privilege escalation, data access, log-tamper attempt) and verify every step appears in
    analysis with correct attribution. If the simulation isn't fully visible, neither is a real
    attacker.

## Expected outputs
- Organization CloudTrail with all-regions coverage, hardened S3 archive, and KMS encryption.
- Data-event logging scoped to sensitive resources; log validation enabled.
- A queryable analysis layer with documented forensic pivots and detection content.
- Pipeline-health monitoring with tamper-attempt paging.
- Quarterly simulation tests proving end-to-end visibility.

## Pitfalls
- Per-account trails instead of an organization trail: inconsistent, individually disableable, and a
  forensic nightmare.
- Logging without analysis: terabytes of logs nobody queries are compliance theater. Detections and
  forensic workflows must ship with the pipeline.
- Data events everywhere: cost explosion. Scope to sensitive resources deliberately.
- No Object Lock / weak bucket policy: attackers who compromise an admin can delete the trail
  covering their tracks. Immutability is the point of the archive.
- Ignoring read events: many investigations hinge on "who read the secret/bucket" — ensure read
  management events are captured, not just writes.

## References
- AWS CloudTrail documentation (organization trails, data events, log validation)
- AWS Prescriptive Guidance: logging strategy and log-archive account design
- NIST SP 800-92 (log management) and SP 800-53 AU family (audit logging)
- MITRE ATT&CK T1562.008 (Impair Defenses: Disable Cloud Logs) — the tamper scenario
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
