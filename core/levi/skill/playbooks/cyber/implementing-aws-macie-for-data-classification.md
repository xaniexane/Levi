---
skill_id: cyber_implementing_aws_macie_for_data_classification
name: Data Classification with AWS Macie
description: Deploy Amazon Macie for automated sensitive-data discovery and classification in S3.
risk: low
permissions: []
requires_confirmation: false
tags: [aws, dlp]
version: 1.0.0
---
## Purpose
You cannot protect data you cannot find. S3 buckets accumulate years of exports, logs, backups, and
data-lake drops — including PII, credentials, and payment data nobody remembers storing. Amazon
Macie automates sensitive-data discovery across S3 using machine learning and pattern matching,
producing the classified inventory that DLP, encryption, and access policies depend on.

## When to use
- Building the data-discovery foundation for DLP, privacy (GDPR/CCPA), or PCI DSS programs on AWS.
- After incidents involving sensitive data in unexpected S3 locations.
- Before data-lake or analytics-platform launches: classify first, then set access policy.
- For periodic sensitive-data sweeps across large, old S3 estates.
- As input to S3 Block Public Access, bucket policies, and KMS encryption scoping.

## Prerequisites
- Macie enabled in the relevant regions with a designated administrator account (via Organizations).
- S3 inventory of in-scope buckets; decide exclusions deliberately (e.g., buckets with no plausible
  sensitive data — document why).
- Defined data-classification tiers and which Macie managed data identifiers map to each (PII,
  financial, credentials, health).
- An SNS/EventBridge destination and ticketing workflow for findings.
- Cost awareness: Macie charges per GB processed — scope initial jobs to avoid surprise bills.

## Procedure
1. **Enable Macie with proper administration.** Designate the Macie administrator account in
   Organizations; enable in each region holding in-scope buckets. Verify service-linked roles and
   permissions before running jobs.
2. **Start with a scoped pilot.** Select 10-20 representative buckets (data lake raw zones, backup
   buckets, shared team buckets). Run one-time classification jobs to calibrate: which identifiers
   fire, false-positive rates, and cost per bucket. Tune before estate-wide rollout.
3. **Configure managed and custom identifiers.** Enable managed data identifiers matching your data
   types (names, addresses, national IDs, credit cards, AWS keys, private keys). Build custom
   identifiers for org-specific patterns (employee IDs, internal account formats) using regex plus
   context keywords to cut false positives.
4. **Run automated discovery.** Enable automated sensitive-data discovery for continuous coverage of
   new and changed objects. Schedule full classification jobs for the existing estate in waves,
   prioritizing buckets by: public/block-public-access status, cross-account access, and age (older
   = more likely forgotten data).
5. **Triage findings by bucket risk.** For each finding, assess: bucket access posture (public?
   cross-account? broadly shared internally?), data type and volume, and business justification. A
   thousand SSNs in a locked-down, encrypted, access-logged bucket is a governance item; the same in
   a public bucket is an incident.
6. **Remediate systematically.** Standard actions: enable Block Public Access and restrictive bucket
   policies, move data to appropriately classified buckets, apply KMS encryption with proper key
   policies, remove stale cross-account grants, and delete data past retention. Each finding gets an
   owner and deadline.
7. **Suppress with care.** Tune or suppress noisy identifiers only with documented justification and
   periodic re-review — suppression lists are where real findings go to die. Prefer
   custom-identifier refinement over blanket suppression.
8. **Feed downstream controls.** Export classification results to: the data catalog/CMDB (bucket
   classification tags), DLP policy scope, backup/retention policy, and access-review lists (who has
   access to buckets holding regulated data gets reviewed first).
9. **Monitor Macie health and cost.** Watch job completion rates, finding trends, and monthly spend.
   Alert on discovery-job failures — silent scanner death means silent data accumulation.
10. **Report data-risk reduction.** Track: percent of S3 data classified, count of sensitive-data
    findings by severity, remediation MTTR, and repeat-offense buckets/teams. Present the trend: the
    estate getting cleaner, not just the finding count.

## Expected outputs
- Macie enabled with automated discovery across in-scope regions/accounts.
- Calibrated identifier set (managed + custom) with documented tuning decisions.
- Classified S3 inventory feeding the data catalog and downstream controls.
- Triaged findings with owners, remediations, and MTTR tracking.
- Cost-monitored, health-monitored discovery jobs.

## Pitfalls
- Enabling estate-wide jobs on day one: cost shock and thousands of un-triaged findings. Pilot,
  calibrate, then expand.
- Treating Macie as DLP: it discovers and classifies; it does not block exfiltration. Pair with
  bucket policies, access controls, and egress monitoring.
- Ignoring non-S3 storage: EBS snapshots, RDS, and EFS hold sensitive data too — Macie covers S3;
  plan equivalent discovery elsewhere.
- Over-suppression of noisy identifiers: tune patterns with context keywords rather than disabling
  categories wholesale.
- No remediation loop: a classified inventory with no owner follow-up is an auditor's exhibit of
  known-unfixed risk. Findings need SLAs.

## References
- Amazon Macie documentation (managed data identifiers, automated discovery, findings)
- NIST SP 800-60 (guide for mapping types of information to security categories)
- PCI DSS v4.0 Requirement 3 (protect stored account data — discovery prerequisite)
- AWS S3 security best practices (Block Public Access, bucket policies, access logging)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
