---
skill_id: sys_python_hashlib_secrets
name: Python hashlib and secrets
description: Cryptographic hashes and secure randomness: what to use and what to avoid.
risk: info
permissions: []
requires_confirmation: false
tags: [python, security]
version: 1.0.0
---
# Python hashlib and secrets

## Purpose

Cryptographic hashes and secure randomness: what to use and what to avoid.

## Overview

hashlib provides cryptographic hash functions: SHA-256 and SHA-512 for integrity and fingerprinting, with .update() feeding data and .hexdigest() producing the hex string. Hashes are one-way and deterministic - same input, same digest - which makes them right for verifying downloads and deduplicating content, and wrong for passwords unless built into a proper password-hashing scheme. For passwords use a dedicated KDF: hashlib.pbkdf2_hmac with high iterations, or bcrypt/argon2 from third-party libs - never plain SHA-256, which attackers brute-force at billions of guesses per second, and never unsalted. HMAC (hmac.new(key, msg, hashlib.sha256)) authenticates messages with a shared secret; compare digests with hmac.compare_digest to avoid timing leaks. The secrets module is the secure-randomness source: secrets.token_hex()/token_urlsafe() for tokens, secrets.choice() for passwords - never the random module for anything security-sensitive, since it is deterministic and predictable. MD5 and SHA-1 are broken for collision resistance: fine for non-security checksums of trusted data, unacceptable for signatures or integrity against adversaries.

## Quick reference

- hashlib.sha256/sha512: integrity and fingerprinting, not password storage.

- Passwords need a KDF: pbkdf2_hmac (high iterations), bcrypt, or argon2.

- hmac.new(key, msg, sha256) + compare_digest: authenticated, timing-safe checks.

- secrets.token_hex/token_urlsafe/choice: secure randomness for tokens.

- Never use random for secrets: it is deterministic and predictable.

- MD5/SHA-1 are broken for security uses; fine only for non-adversarial checksums.


## Worked example

Hashing a file and minting a secure token:

```
import hashlib, hmac, secrets

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()

token = secrets.token_urlsafe(32)

key = secrets.token_bytes(32)
tag = hmac.new(key, b'message', hashlib.sha256).hexdigest()
ok = hmac.compare_digest(tag, hmac.new(key, b'message',
                                       hashlib.sha256).hexdigest())
print(token[:8], ok)
```

- Streaming update() hashes files of any size in 64 KB chunks.

- secrets.token_urlsafe gives unguessable tokens; random never qualifies.

- compare_digest runs in constant time to block timing attacks.


## Common mistakes

- Using random.randint for tokens or password resets.
  Fix: Use secrets - random output is predictable.

- Comparing HMAC digests with ==, leaking timing information.
  Fix: Use hmac.compare_digest for constant-time comparison.


## Quick checks

Q: Can I store passwords as SHA-256 hashes?
A: No. SHA-256 is too fast - GPUs try billions per second - and unsalted hashes fall to rainbow tables. Use pbkdf2_hmac with 200k+ iterations, bcrypt, or argon2, each with a unique salt.


Q: random vs secrets - what is the actual difference?
A: random is a deterministic PRNG seeded from system state: fine for simulations, fatal for tokens. secrets draws from the OS CSPRNG (os.urandom): unpredictable, suitable for security.


## Mental model

A hash is a fingerprint: it identifies the data but cannot rebuild the person. A KDF is a fingerprint taken through frosted glass thousands of times - deliberately slow so an attacker cannot try every finger in the world quickly. secrets is rolling dice in a locked room; random is rolling dice on a livestream.
