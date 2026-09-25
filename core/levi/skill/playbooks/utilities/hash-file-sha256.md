---
skill_id: utility.hash_file_sha256
name: Hash File SHA-256
description: Compute the SHA-256 digest of a file, streamed in chunks - read-only.
risk: info
permissions: []
requires_confirmation: false
tags: [hash, sha256, integrity]
version: 1.0.0
---

# Hash File SHA-256

Hash File SHA-256 reads a file in chunks and reports its SHA-256 hex digest. Use it to verify downloads, confirm copies are identical, or record a file's fingerprint. The file is never modified.

## When to use

- Verifying a download against a published checksum.
- Proving two files are byte-identical.
- Recording fingerprints in a manifest.

## Steps

1. Stream the file in 64KB chunks through hashlib.sha256 - memory stays flat on huge files.
2. Display the hex digest.
3. Optionally compare against an expected digest and report MATCH or MISMATCH explicitly.
4. Record the digest next to the filename in your manifest or notes so the fingerprint stays reusable.

## Honest limits

- Standard library only (hashlib).
- A hash proves integrity (unchanged), not authenticity (from whom) - different promises.
- Compare digests with hmac.compare_digest when the check matters; eyeballing hex is error-prone.

Original work authored for LEVI - utilities pack.
