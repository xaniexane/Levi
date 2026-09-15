# Analyzing Cloud Storage Access Patterns

## Purpose

Detect data theft, misconfiguration abuse, and insider threats in cloud object storage (S3, Azure Blob, GCS) by analyzing access patterns: who read what, how much, from where, and whether the access fits the bucket's purpose. Object storage is where the data lives — this playbook treats its access logs as a primary exfiltration-detection surface.

## When to use

- Investigating suspected data exfiltration through cloud storage.
- Auditing storage buckets/containers for public exposure or over-broad access.
- Hunting insider threats: unusual bulk reads by legitimate identities.
- Post-incident scoping: determining exactly which objects an attacker touched, for breach-notification decisions.
- Validating that storage logging, encryption, and access controls actually work as designed.

## Prerequisites

- Written authorization from the data/storage owner to query access logs (they reveal who accessed what data, including other users' activity — handle accordingly).
- Chain-of-custody notes: record log sources, time ranges, queries, and hashes of any exported evidence.
- Access logging enabled and centralized: S3 server-access logs / CloudTrail data events, Azure Storage Analytics logging, GCP Cloud Audit Logs for GCS. If logging wasn't on, say so explicitly — do not claim completeness from management events alone.
- An inventory of buckets/containers with intended purpose, data classification, and authorized accessor list. You cannot judge "anomalous" without "normal."

## Procedure

1. **Verify log coverage per bucket.** Confirm access logging is enabled on every in-scope bucket and flowing to your analytics store. List buckets *without* logging — that is both a blind spot and a hardening finding. Note the retention window; exfiltration older than retention is unknowable from these logs, and your report must state that boundary.
2. **Baseline legitimate access.** For each sensitive bucket, profile: which identities (IAM roles, users, service principals) access it, typical operation mix (GET vs. LIST vs. PUT), normal volume per identity per day, and normal source networks. Service accounts doing nightly syncs look like exfiltration until baselined — document them with their job schedules so the SOC doesn't re-investigate monthly.
3. **Hunt bulk-read exfiltration.** Aggregate GET/HEAD operations by identity and bucket over 24h/7d windows. Flag identities whose read volume or object count deviates sharply from their baseline, especially first-time bulk readers of sensitive buckets. In CloudTrail terms, this means grouping `GetObject` data events by `userIdentity.arn` and bucket, ranked by bytes and object count.
4. **Hunt access from unusual places.** Flag reads from IPs/ASNs/geographies never seen for that identity, access via anonymous or presigned URLs, and access from compute resources the identity doesn't normally use. For presigned URLs, identify the *issuer* identity and whether the URL's scope and lifetime match a legitimate sharing workflow — over-broad presigned URLs are a common exfiltration enabler.
5. **Audit bucket policy and ACL exposure.** Review each sensitive bucket's policy for `Principal: "*"` grants, overly broad `s3:GetObject` allows, public-access-block settings (S3), anonymous-access settings (Azure), and IAM `allUsers`/`allAuthenticatedUsers` bindings (GCS). An "internal" bucket readable by the world is an incident, not a misconfiguration ticket — check access logs for whether anyone actually downloaded before declaring impact.
6. **Check for access-pattern anomalies indicating automation abuse.** LIST-heavy enumeration followed by targeted GETs suggests an attacker inventorying the bucket before stealing selectively. Compare LIST:GET ratios against baseline; humans browse, scripts enumerate. Also watch for `ListObjects` across many buckets from one identity (discovery phase, T1619).
7. **Investigate encryption and versioning gaps.** Confirm SSE is enforced (bucket policy denying unencrypted PUTs), versioning plus MFA-delete is on for critical buckets (ransomware resilience — attackers overwrite, versioning lets you recover), and that access logs themselves land in a separate, locked-down bucket. Attackers delete logs first when they can; log-bucket protection is part of the control.
8. **Reconstruct the incident.** For a confirmed case: enumerate every object the suspect identity read (object-level listing from data events), determine the data classification of those objects, establish the first anomalous access, check for concurrent PUTs (possible data planting or ransomware staging), and produce the definitive object list for breach-notification scoping with legal.
9. **Remediate in dependency-safe order.** Revoke the abusive identity's access and rotate its credentials first, then re-tighten bucket policies to least privilege, enable missing logging, and re-encrypt or restore from versioning if integrity is in doubt. For public exposures, determine via logs whether anyone actually downloaded the data before declaring impact — exposure without access is still a finding, but a different notification decision.
10. **Operationalize.** Scheduled queries: daily bulk-read anomaly per sensitive bucket, weekly public-exposure audit across all buckets, and alerting on policy changes (`PutBucketPolicy`, `SetBlobServiceProperties`, IAM binding changes) by non-approved identities. Add storage-logging coverage to your cloud-posture reviews so new buckets inherit logging from day one.

## Key tools & commands

- AWS CloudTrail (data events for S3) + Athena/CloudWatch Logs Insights — query `GetObject`/`ListObjects`/`PutBucketPolicy` at scale; remember data events cost and must be enabled per bucket.
- Azure Monitor / Log Analytics over Storage diagnostic logs; GCP Cloud Audit Logs (Data Access audit logs) for GCS.
- `aws s3api get-bucket-policy`, `get-public-access-block`, `get-bucket-encryption`; `az storage account show`; `gsutil iam get` — exposure and encryption auditing.
- CSPM tools (Prowler, ScoutSuite, Defender for Cloud) — automated public-exposure and encryption checks as a second opinion, not a replacement for log analysis.

## Expected outputs

- Coverage report: which buckets log, retention windows, gaps, and the remediation plan for gaps.
- Baseline profiles per sensitive bucket: identities, volumes, operation mix, source networks, with review dates.
- Findings: bulk-read anomalies, public exposures, policy changes — each with timeline, actor, and legitimacy verdict.
- For confirmed incidents: the full object-access list for impact scoping, shared with legal.
- Scheduled detection queries and a recurring exposure-audit task with an owner.

## Pitfalls

- CloudTrail *management* events don't include object-level reads — you need data events (S3) / diagnostic logging (Azure/GCS), which many environments never enabled. Check before promising answers; "no evidence of exfiltration" from management events alone is a false negative factory.
- CDN and presigned-URL access can bypass identity attribution; correlate with CDN logs and URL-issuance records before concluding "anonymous."
- Declaring "no exfiltration" without stating your log-source limits misleads stakeholders — always state what you could and couldn't see.
- Log-delivery latency (minutes to hours) means real-time alerting on storage access always lags — design response SLAs around it, and don't page on every bulk read.
- Cross-account access via bucket policies referencing external principals is easy to miss in single-account audits — review the policy principals, not just your own IAM.

## References

- AWS docs: "Logging requests with server access logging" and "CloudTrail data events for S3"
- Microsoft Docs: "Azure Storage analytics logging"; Google Cloud docs: "Cloud Audit Logs for Cloud Storage" (Data Access logs)
- MITRE ATT&CK: T1530 (Data from Cloud Storage), T1537 (Transfer Data to Cloud Account), T1619 (Cloud Storage Object Discovery)
- CIS Benchmarks for AWS/Azure/GCP (storage logging, encryption, and public-exposure controls)

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
