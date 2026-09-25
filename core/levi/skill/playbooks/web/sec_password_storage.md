---
skill_id: web_sec_password_storage
name: Password Storage
description: Store passwords so a database breach does not become an account breach: hashing, salts, and pepper.
risk: info
permissions: []
requires_confirmation: false
tags: [security, defense, web]
version: 1.0.0
---
# Password Storage
## Purpose
Make stolen password hashes expensive to crack and useless to reuse.
## Key ideas
- Store salted hashes, never plaintext or reversible encryption; the server should not know the password.
- Use a password-hashing function built for the job (bcrypt, scrypt, Argon2), not a fast general hash.
- Each password gets a unique random salt so identical passwords hash differently and rainbow tables fail.
- Work factors should make hashing take a fraction of a second: slow for attackers, invisible to users.
- Peppering (a secret mixed in before hashing, stored outside the DB) adds defense if only the database leaks.

## In practice
Pick Argon2id or bcrypt via a maintained library and never implement the primitive yourself; the library handles salt generation, encoding, and constant-time comparison. Set the work factor so hashing takes roughly 200-500ms on your hardware, and re-evaluate as hardware improves, re-hashing on next login when you raise it. Store the algorithm identifier and parameters alongside the hash so future upgrades do not require a flag day. On breach, assume hashes are in play: force resets, because even good hashes fall to weak passwords, and encourage passphrases or password managers at signup with a strength meter that teaches rather than scolds.

```python
from argon2 import PasswordHasher

ph = PasswordHasher(time_cost=2, memory_cost=102400, parallelism=8)

stored = ph.hash("correct horse battery staple")  # salt + params embedded

# On login: constant-time verify, then optionally rehash if params aged
try:
    ph.verify(stored, candidate)
    if ph.check_needs_rehash(stored):
        stored = ph.hash(candidate)  # upgrade work factor transparently
    ok = True
except Exception:
    ok = False
```

## Common mistakes
- Hashing with MD5/SHA-256 alone, which attackers brute-force at billions of guesses per second.
- Reusing one salt for all passwords, letting rainbow tables and batch cracking work.
- Encrypting passwords reversibly, so a key leak reveals every password.

## Checklist
- Are passwords hashed with Argon2/bcrypt/scrypt via a maintained library?
- Is each hash uniquely salted with parameters stored for future upgrades?
- Can the work factor be raised with transparent rehashing on login?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
