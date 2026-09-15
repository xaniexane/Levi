---
skill_id: cyber_remediating_s3_bucket_misconfiguration
name: Remediating S3 Bucket Misconfigurations
description: Find and fix public or over-permissive S3 buckets: block public access, tighten policies, and add guardrails.
risk: low
permissions: []
requires_confirmation: false
tags: [cloud, aws, remediation]
version: 1.0.0
---
## Purpose
Public S3 buckets remain a leading cause of cloud data exposure. This playbook covers the defensive workflow: discovering buckets with public or over-broad access, assessing what data is exposed, remediating with Block Public Access and least-privilege policies, and adding guardrails so misconfigurations cannot recur.

## When to use
- Cloud security posture review or compliance audit.
- After an alert for a publicly accessible bucket or exposed data report.
- Post-migration validation of storage moved to S3.
- Continuous CSPM findings requiring remediation.

## Prerequisites
- AWS account inventory with permission to read S3, IAM, and Config data.
- CSPM or inventory tooling (AWS Config, Prowler, or commercial CSPM).
- Data classification guidance to judge exposure severity.
- Change process for modifying bucket policies in production accounts.

## Procedure
1. Inventory all buckets across accounts and regions; include forgotten and logging buckets.
2. Check each bucket for public access: ACLs, bucket policies, and the account-level Block Public Access settings.
3. For any public or questionable bucket, determine what data it holds and whether exposure already occurred (access logs).
4. Remediate: enable Block Public Access, remove public ACL grants, and rewrite bucket policies to least privilege with explicit principals.
5. Replace legitimate public-content needs with CloudFront origin access control rather than public buckets.
6. Add preventive guardrails: SCPs denying public buckets, Config rules, and CI checks on IaC.
7. Enable S3 access logging and consider Macie for sensitive-data discovery in high-risk buckets.
8. Re-scan to confirm closure and document exceptions with owner and expiry.
9. Check S3 Object Ownership settings and disable ACLs entirely where possible to simplify the model.
10. Inventory S3 Access Points; they carry their own policies that can re-expose buckets.
11. Review CloudTrail for `PutBucketPolicy` and `PutBucketAcl` events to catch future changes quickly.

## Expected outputs
- Bucket inventory with public-access status before and after remediation.
- Remediation log per bucket: change made, data exposure assessment, verifier.
- Guardrail set: SCPs, Config rules, and IaC checks preventing recurrence.
- Access Point inventory with policy review results.
- CloudTrail monitoring rule for bucket-policy changes.
- ACL-disablement status per bucket.

## Pitfalls
- Account-level Block Public Access can break legitimate static-site hosting; plan migration to CloudFront OAC.
- Bucket policies with wildcard principals hide in complex JSON; automate the check, do not eyeball it.
- Cross-account access via IAM roles can bypass bucket-focused reviews; check both sides.
- Remediation without access-log review misses the question of whether data was already taken.
- Access Points with permissive policies re-expose locked-down buckets; inventory them too.
- Directory buckets and general-purpose buckets have different policy models; check both.
- Replication configurations can copy misconfigurations to the destination; review both ends.
- S3 Inventory reports take time to generate; enable them before an incident, not during one.

## References
- AWS Documentation: Blocking public access to S3 storage.
- AWS Documentation: IAM and S3 bucket policy examples.
- CIS Amazon Web Services Foundations Benchmark.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
