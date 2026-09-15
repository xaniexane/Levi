---
skill_id: cyber_performing_cloud_storage_forensic_acquisition
name: Cloud Storage Forensic Acquisition
description: Acquire cloud object and volume storage forensically with integrity verification and chain of custody.
risk: moderate
permissions: []
requires_confirmation: true
tags: [cloud, forensics, acquisition]
version: 1.0.0
---

## Purpose

When evidence lives in S3 buckets, Azure blobs, GCS objects, or cloud volumes, "imaging the disk" becomes copying objects and snapshots across accounts while proving nothing changed in transit. This playbook covers forensically sound acquisition of cloud storage: preserving metadata and versions, hashing to prove integrity, maintaining chain of custody for API-collected evidence, and handling provider-specific quirks. Acquisition touches live production storage, so it runs under explicit authorization with confirmation.

## When to use

- Preserving a bucket or container implicated in data theft, malware hosting, or fraud.
- Acquiring volume snapshots of suspect cloud instances for offline analysis.
- Litigation holds or regulatory investigations involving cloud-stored data.
- Ransomware affecting cloud storage where version history may allow recovery analysis.
- Any matter where you must prove the acquired copy matches the source at collection time.

## Prerequisites

- Written authorization to access and copy the storage, including handling of personal or regulated data it may contain.
- A forensic account/subscription with no trust to the source environment, and encrypted evidence storage provisioned there.
- IAM permissions for read, snapshot, export, and (where needed) legal-hold application on the source storage.
- Chain-of-custody documentation started: bucket/container names, object counts, version IDs, snapshot IDs, collectors, timestamps.
- Enough time and bandwidth budget: multi-terabyte acquisitions are limited by API throughput and egress costs — estimate before starting.

## Procedure

1. **Freeze the source against change.** Enable versioning (if not already), apply legal hold or retention locks to prevent deletion, and suspend lifecycle policies that could expire objects mid-acquisition. Record the protection state before and after.
2. **Inventory what you are acquiring.** List buckets/containers, object counts, total bytes, versioning status, and encryption settings. For volumes, record volume IDs, attachment state, and existing snapshot chains. The inventory defines the acquisition's completeness claim.
3. **Snapshot first where the platform supports it.** For block volumes, create snapshots before any copy; for object storage with versioning, record the current version ID of every object as the acquisition baseline. Snapshots give you a point-in-time anchor.
4. **Copy to the forensic account.** Transfer objects/snapshots to evidence storage in the forensic account using provider copy mechanisms (which preserve server-side metadata) or authenticated downloads. Use multipart-aware tooling for large objects and enable transfer integrity checks (checksums on both ends).
5. **Hash and verify.** Generate cryptographic hashes (SHA-256) of acquired objects and compare against source-side hashes where the provider exposes them (S3 ETags for non-multipart objects, custom metadata hashes you compute via ranged reads). For snapshots, record snapshot IDs and creation timestamps as the integrity anchor. Any mismatch triggers re-acquisition of the affected objects.
6. **Preserve metadata, not just bytes.** Capture object metadata: version IDs, last-modified timestamps, storage class, encryption status, ACLs/policies, tags, and access-log configuration. Metadata often answers "who put this here and when" better than content does.
7. **Handle special cases explicitly.** For buckets with millions of objects, acquire in manifest-driven batches with per-batch verification. For objects under Object Lock, document the retention mode — you cannot alter them, which is itself evidence. For cross-region or cross-cloud copies, note the transfer path and any transformations applied.
8. **Log chain of custody.** Record every API call or tool invocation used in acquisition, the identities that performed them, start/end times, byte counts, hash values, and the final evidence locations. Store the log with the evidence, not separately.
9. **Secure the evidence.** Apply restrictive access policies to the forensic storage, enable MFA delete and versioning on the evidence bucket itself, and log all subsequent access. Work only on copies from this point forward.

## Expected outputs

- A complete, hash-verified copy of the in-scope storage in the forensic account.
- Acquisition manifest: object/version/snapshot inventory with hashes and metadata.
- Chain-of-custody log: who, what, when, which API calls, which hashes.
- Documentation of source protections applied (legal holds, suspended lifecycles).
- Verification report confirming source-to-copy integrity, including any re-acquired items.

## Pitfalls

- Acquiring without freezing the source: objects deleted or overwritten mid-copy silently invalidate completeness.
- Trusting ETags as content hashes for multipart uploads — they are not MD5s of content; verify accordingly.
- Ignoring versioning: acquiring only current versions misses the deleted or overwritten objects that often matter most.
- Egress cost surprises on multi-terabyte acquisitions — estimate and get budget approval first.
- Collecting evidence into the same account under investigation, where a compromised admin could tamper with it.

## References

- AWS documentation on S3 versioning, Object Lock, and S3 inventory
- Azure Storage documentation on immutable blob storage and blob snapshots
- Google Cloud documentation on object versioning and retention policies
- NIST SP 800-86, "Guide to Integrating Forensic Techniques into Incident Response"
- SWGDE guidance on digital evidence integrity and chain of custody
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
