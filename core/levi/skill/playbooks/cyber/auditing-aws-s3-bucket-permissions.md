# Auditing AWS S3 Bucket Permissions

## Purpose

Systematically audit Amazon S3 bucket policies, ACLs, Block Public Access settings, and
encryption configuration to find publicly exposed or over-permissive buckets before they
become a breach disclosure.

## When to use

- Periodic cloud security reviews and compliance audits (SOC 2, ISO 27001, PCI DSS).
- After organization policy changes, account migrations, or incident response involving S3.
- Before product launches that store customer data in S3.
- When onboarding a new AWS account or Organization into the security program.
- After acquiring a company whose AWS footprint is unknown.

## Prerequisites

- Written authorization and a defined scope: account IDs, OUs, or resource tags in bounds.
- Read-only AWS IAM access (e.g., the `SecurityAudit` managed policy plus
  `s3:GetBucketPolicy`, `s3:GetBucketAcl`, `s3:GetBucketPublicAccessBlock`,
  `s3:GetEncryptionConfiguration`).
- List of buckets expected to be public (static websites, public datasets) to distinguish
  intended exposure from misconfiguration.
- AWS CLI v2 configured with the audit role; note the region used for each call.

## Procedure

1. **Enumerate all buckets in scope.**
   - Run `aws s3api list-buckets` and record the region of each with
     `aws s3api get-bucket-location --bucket <name>`.
   - Note which accounts or OUs each bucket belongs to; multi-account estates hide
     buckets from single-account views.

2. **Check Block Public Access at account and bucket level.**
   - Query `aws s3control get-public-access-block --account-id <id>` for the
     account-level guardrail.
   - Query `aws s3api get-public-access-block --bucket <name>` per bucket; any bucket
     without all four blocks enabled is a candidate for review.

3. **Inspect bucket policies.**
   - Pull each policy with `aws s3api get-bucket-policy --bucket <name>`.
   - Look for `"Principal": "*"` or `"AWS": "*"` combined with `s3:GetObject` (public
     read) or `s3:PutObject` (public write — far worse).
   - Flag `Condition` clauses that are trivially satisfiable, such as IP ranges covering
     the whole internet or `aws:Referer` checks.

4. **Inspect ACLs.**
   - Run `aws s3api get-bucket-acl --bucket <name>` and spot-check object ACLs; flag
     grants to the `AllUsers` or `AuthenticatedUsers` groups.
   - Prefer bucket policies over ACLs; recommend `BucketOwnerEnforced` object ownership to
     disable ACLs entirely.

5. **Check Access Points and Object Lambda.**
   - Enumerate access points with `aws s3control list-access-points --account-id <id>` —
     they carry their own policies that can re-expose a locked-down bucket.
   - Review each access point policy with `get-access-point-policy` the same way as
     bucket policies.

6. **Verify encryption.**
   - Confirm default encryption with `aws s3api get-bucket-encryption --bucket <name>`.
   - Flag buckets without SSE-S3 or SSE-KMS, and note KMS key ownership and key policies
     for cross-account keys.

7. **Review logging and versioning.**
   - Confirm access logging (`get-bucket-logging`) targets a centralized, restricted log
     bucket — not the bucket itself with public read.
   - Confirm versioning and MFA delete on buckets holding critical or regulated data.

8. **Cross-check with AWS Access Analyzer and Config.**
   - Review S3 access findings in IAM Access Analyzer for unintended external access.
   - Check AWS Config rules `s3-bucket-public-read-prohibited`,
     `s3-bucket-public-write-prohibited`, and `s3-bucket-ssl-requests-only`.

9. **Test from the outside (authorized).**
   - For buckets flagged public, make an unauthenticated request —
     `curl -sI https://<bucket>.s3.<region>.amazonaws.com/` and an anonymous list
     attempt — to confirm actual exposure versus policy ambiguity.
   - Do this only within the written scope, and stop at confirmation (no data download).

10. **Remediate and verify.**
    - Enable Block Public Access, tighten policies to least-privilege principals, and
      switch to `BucketOwnerEnforced`.
    - Re-run steps 2–4 to confirm each finding is closed; record exceptions with owner,
      justification, and expiry date.

## Key tools & commands

- `aws s3api get-bucket-policy|get-bucket-acl|get-public-access-block|get-bucket-encryption|
  get-bucket-logging --bucket <name>` — the core read-only audit primitives.
- `aws s3control get-public-access-block --account-id <id>` — account-level guardrail check.
- AWS IAM Access Analyzer (S3 findings) and AWS Config managed rules for continuous
  monitoring.
- IAM policy simulator (`aws iam simulate-custom-policy`) — validate tightened bucket
  policies before applying them.
- Prowler (`prowler aws` with the s3 checks) or ScoutSuite — open-source sweeps that codify
  these checks; treat output as leads, not verdicts.

## Expected outputs

- Bucket inventory with region, public-access-block status, policy/ACL summary, encryption,
  logging, and versioning.
- Findings table: bucket, exposure type (public read/write, weak condition, open ACL),
  evidence (policy excerpt), severity.
- External confirmation results for buckets reachable anonymously.
- Remediation log with before/after policy snippets and an exception register.

## Pitfalls

- Block Public Access at the account level masking bucket-level intent — check both, since
  bucket settings can drift if account blocks are later relaxed.
- Object ACLs surviving after a bucket policy is fixed; old objects may still carry public
  grants — check a sample of objects, not just the bucket.
- Cross-account access via `aws:PrincipalOrgID` conditions that look safe but include the
  whole organization.
- Treating scanner output as ground truth — always confirm with the actual
  `get-bucket-policy` JSON and an authorized external request.

## References

- MITRE ATT&CK: T1530 (Data from Cloud Storage), T1578 (Modify Cloud Compute
  Infrastructure).
- AWS documentation: "Blocking public access to your Amazon S3 storage", "Bucket policies
  and user policies", "Setting default server-side encryption behavior".
- CIS Amazon Web Services Foundations Benchmark: S3-related controls.
- AWS Config managed rules: `s3-bucket-public-read-prohibited`,
  `s3-bucket-public-write-prohibited`, `s3-bucket-server-side-encryption-enabled`.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
