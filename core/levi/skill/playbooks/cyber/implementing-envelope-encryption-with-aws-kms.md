---
skill_id: cyber_implementing_envelope_encryption_with_aws_kms
name: Envelope Encryption with AWS KMS
description: Implement envelope encryption with AWS KMS: data keys, key hierarchy, and least-privilege key policies.
risk: low
permissions: []
requires_confirmation: false
tags: [aws, cryptography]
version: 1.0.0
---
## Purpose
Encrypting data directly with a KMS key doesn't scale: every encrypt/decrypt call hits KMS (latency,
cost, throttling), and key rotation gets complicated. Envelope encryption solves it: a unique data
key encrypts the data, KMS encrypts (wraps) the data key, and only the wrapped key is stored
alongside the ciphertext. This playbook implements the pattern correctly on AWS KMS — key hierarchy,
caching, rotation, and least-privilege policies.

## When to use
- Encrypting application data (databases, files, messages) with customer-controlled keys.
- Meeting encryption requirements where key custody and rotation must be demonstrable (HIPAA, PCI
  DSS, FedRAMP).
- Building multi-tenant encryption (per-tenant data keys under one or per-tenant KMS keys).
- Reducing KMS API costs and latency in high-throughput encryption workloads.
- Anywhere "encrypt with KMS" is currently done naively per-operation.

## Prerequisites
- KMS keys created per data classification/tenant boundary, with key policies drafted
  (least-privilege from the start).
- An encryption SDK: AWS Encryption SDK (preferred — handles the envelope pattern correctly) or a
  vetted equivalent.
- Defined key-rotation schedule and data-re-encryption policy (rotate keys; decide whether
  historical data gets re-wrapped).
- CloudTrail logging of KMS API calls (enabled by default — ensure it's monitored).
- Threat model: who must not read the data (defines key-policy principals and the need for
  encryption-context constraints).

## Procedure
1. **Design the key hierarchy.** Levels: KMS key (root of trust, in KMS/HSM) → data key (generated
   per object, file, or tenant-period) → data. Decide data-key scope: per-object keys maximize
   isolation (and key count); per-tenant-per-period keys balance practicality. Document the
   hierarchy and rotation boundaries.
2. **Use the AWS Encryption SDK.** Don't hand-roll envelope encryption — the SDK implements data-key
   generation, wrapping, algorithm suites, and (critically) encryption context binding correctly.
   Choose an algorithm suite with commitment (e.g., AES-256-GCM with HKDF and ECDSA commitment) to
   prevent key-commitment attacks.
3. **Bind encryption context.** Include encryption context (tenant ID, purpose, object identifier)
   in every Encrypt call and require it on Decrypt. Key policies can constrain decryption by
   encryption context (kms:EncryptionContext keys) — this stops a wrapped key stolen from one
   tenant's record being decrypted in another's context. Context binding is the feature most
   implementations skip.
4. **Write least-privilege key policies.** Grant encrypt/decrypt only to the application roles that
   need them, scoped by encryption-context conditions where possible. Separate key administrators
   (who manage the key) from key users (who use it). Never use the default key policy that grants
   the account root full access without thought — scope deliberately.
5. **Cache data keys safely.** For high throughput, cache plaintext data keys in memory with strict
   limits (max messages/bytes per key, short TTLs — the SDK's caching CMM enforces this). Never
   persist plaintext data keys to disk or logs. Caching bounds KMS costs without weakening the
   model.
6. **Implement rotation properly.** Enable automatic annual KMS key rotation (new backing key
   material; old material retained for decrypting old data keys). For data keys: rotation means
   generating new data keys for new data — decide whether to re-encrypt historical data (expensive;
   often deferred with documented risk acceptance) or rely on KMS-side rotation.
7. **Monitor KMS as a security control.** Alert on: Decrypt spikes (possible bulk-data access),
   key-policy changes, key deletion/disablement (scheduled deletion has a waiting period — alert
   immediately), and grants created unexpectedly. KMS telemetry reveals data-access patterns — treat
   it as detection signal.
8. **Handle multi-tenancy.** Per-tenant KMS keys (strongest isolation, higher cost) or per-tenant
   data keys under shared KMS keys with encryption-context-bound policies (practical middle ground).
   Tenant offboarding: destroy or disable their keys/data keys per the data-destruction policy —
   cryptographic erasure is the cleanest deletion.
9. **Test the failure modes.** Verify: decryption with wrong encryption context fails, tampered
   ciphertext fails authentication (GCM), revoked key users are denied, and key rotation doesn't
   break reads of old data. Include these in integration tests permanently.
10. **Document the cryptosystem.** Write the spec: hierarchy, algorithm suites, context fields, key
    IDs and rotation schedule, policy principals, and the destruction procedure. Auditors and
    incident responders both need this document — "how is our data encrypted" should have a one-page
    answer.

## Expected outputs
- Envelope encryption implemented via AWS Encryption SDK with committing algorithm suites.
- Key hierarchy designed per tenant/classification with encryption-context binding.
- Least-privilege key policies with context conditions; separated admin/user roles.
- Rotation, caching, monitoring, and destruction procedures documented and tested.
- A one-page cryptosystem spec for auditors and responders.

## Pitfalls
- Hand-rolled envelope encryption: subtle bugs (IV reuse, unauthenticated wrapping, missing context
  binding) are the norm, not the exception. Use the SDK.
- No encryption context: without it, wrapped keys are portable across tenants/contexts — the
  isolation story collapses.
- Overly broad key policies: the default "account administrators can do everything" policy needs
  deliberate scoping, or key custody is fiction.
- Plaintext data keys persisted: caching to disk or logging data keys voids the entire construction.
  Memory-only, bounded TTL.
- Forgetting the destruction story: "delete the data" must include key destruction for cryptographic
  erasure — plan tenant offboarding upfront.

## References
- AWS KMS documentation (key policies, grants, rotation, encryption context)
- AWS Encryption SDK documentation (envelope encryption, caching CMM, algorithm suites)
- NIST SP 800-57 (key management guidance)
- NIST SP 800-53 SC-12, SC-28 (key management, data-at-rest protection)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
