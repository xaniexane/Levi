---
skill_id: cyber_performing_cloud_log_forensics_with_athena
name: Cloud Log Forensics with Amazon Athena
description: Query CloudTrail, VPC flow, and S3 access logs at scale with Athena for forensic investigations.
risk: info
permissions: []
requires_confirmation: false
tags: [cloud, forensics, aws]
version: 1.0.0
---

## Purpose

Cloud log volumes defeat manual review: a single compromised account can generate millions of CloudTrail and flow-log records. Amazon Athena lets you run SQL directly against those logs in S3 without provisioning infrastructure, turning "needle in a haystack" into targeted queries. This playbook covers setting up Athena for forensic log analysis — table definitions, partitioning strategy, and the query patterns that answer the core incident questions: who, what, when, from where.

## When to use

- Forensic analysis of CloudTrail, VPC flow logs, S3 server access logs, or ALB logs stored in S3.
- Investigations where the SIEM lacks the retention or the raw fields you need.
- Building reproducible, shareable queries for timeline reconstruction.
- Validating a SIEM finding against the raw log source.
- Cost-conscious large-scale log analysis (pay per byte scanned, so query design matters).

## Prerequisites

- Logs centralized in S3 with a predictable key structure (ideally Hive-style partitions: `.../AWSLogs/<account>/<service>/<region>/<year>/<month>/<day>/`).
- Athena workgroup configured with query result encryption, and IAM permissions scoped to the forensic analyst role.
- Table definitions for each log type (CloudTrail, flow logs, S3 access logs, ALB logs) — create once, reuse across investigations.
- The investigation's time bounds, account IDs, and regions of interest to constrain partitions.
- Awareness of Athena pricing: every query scans data, so partition pruning and column selection directly control cost.

## Procedure

1. **Create or verify the log tables.** Define external tables over the S3 log locations with correct SerDe and partitioning. For CloudTrail, use the standard JSON schema (`eventTime`, `eventName`, `userIdentity`, `sourceIPAddress`, etc.); for VPC flow logs, the space-delimited versioned format. Test each table with a one-day, one-account query before the real investigation.
2. **Constrain partitions aggressively.** Every query must filter on partition columns (account, region, date) matching the investigation window. An unpartitioned full-bucket scan is slow, expensive, and returns irrelevant data — make partition filters non-negotiable in your query templates.
3. **Build the identity timeline.** Query CloudTrail for the suspect identity ordered by `eventtime`: select event name, source IP, user agent, and error codes. Use this as the master timeline to which other sources are joined.
4. **Answer the network question with flow logs.** For each suspect instance or IP from the timeline, query VPC flow logs for its conversations: distinct remote IPs/ports, bytes transferred, and direction. Large outbound transfers to unknown IPs during the window are exfiltration candidates; correlate timestamps with the CloudTrail timeline.
5. **Answer the data-access question.** Query S3 server access logs (or CloudTrail data events) for `GetObject`/`HeadObject` on sensitive buckets: which keys, which requester, how many bytes. For databases, join application or audit logs on the same time window.
6. **Hunt for anti-forensics and anomalies.** Query for `StopLogging`, trail modifications, `DeleteObject` bursts, and `AccessDenied` error spikes. Aggregate by `sourceIPAddress` to find attacker infrastructure, and by `useragent` to separate scripted attacker tooling from normal SDK traffic.
7. **Export and preserve results.** Save key result sets as CSV/Parquet to the forensic evidence location, hash them, and store the exact SQL text alongside — reproducibility is what makes query-based forensics defensible.
8. **Optimize for repeatability.** Convert successful ad-hoc queries into saved, parameterized templates (time window, identity, IP as parameters) so the next investigation starts from a library instead of a blank editor.

## Expected outputs

- Verified Athena table definitions for each in-scope log type.
- A suspect-identity API timeline derived from CloudTrail.
- Network conversation summaries from flow logs tied to timeline events.
- Data-access findings: objects read, volumes transferred, requesters.
- Preserved query results with hashes and the SQL used to produce them.

## Pitfalls

- Forgetting partition filters and scanning terabytes — slow, expensive, and avoidable.
- Schema drift: AWS occasionally adds flow-log fields; versioned formats handle this, but custom parsers break silently.
- Time-zone confusion: CloudTrail uses UTC; always normalize before correlating with local-time sources.
- Treating Athena as a SIEM replacement for alerting — it is an investigation tool, not a real-time detection engine.
- Querying logs in the compromised account's bucket without verifying integrity first; copy to the forensic account when tampering is suspected.

## References

- Amazon Athena documentation (querying CloudTrail logs, partitioning, workgroups)
- AWS documentation on VPC flow log and S3 server access log formats
- AWS re:Post knowledge articles on Athena table definitions for CloudTrail
- NIST SP 800-92, "Guide to Computer Security Log Management"
- SANS FOR509-style cloud forensic query references
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
