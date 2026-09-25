---
skill_id: web_sec_auth_best_practices
name: Authentication Best Practices
description: Verify identity carefully: credential handling, MFA, lockout policy, and secure password reset flows.
risk: info
permissions: []
requires_confirmation: false
tags: [security, defense, web]
version: 1.0.0
---
# Authentication Best Practices
## Purpose
Build login flows that resist guessing, phishing, and replay without punishing legitimate users.
## Key ideas
- Never reveal whether the username or password was wrong; 'invalid credentials' covers both.
- Rate-limit and progressively delay login attempts; lockouts should be temporary and logged.
- Offer MFA, preferably phishing-resistant forms (authenticator apps, security keys) over SMS.
- Password reset tokens must be random, single-use, short-lived, and delivered out of band.
- Re-authenticate before sensitive actions (email change, payout) even in an active session.

## In practice
Keep login responses identical for bad usernames and bad passwords so attackers cannot enumerate accounts; log the distinction server-side for your own monitoring. Throttle by both account and IP with exponential backoff, and alert on distributed guessing patterns rather than just blocking single IPs. Store nothing about the password except a strong hash (see password storage), and never email passwords or reset links that stay valid for days. Design the reset flow as: request, out-of-band single-use token with 15-60 minute expiry, forced new password, session invalidation everywhere, and a notification to the account's contact points.

```python
import secrets, time

def make_reset_token() -> tuple[str, int]:
    token = secrets.token_urlsafe(32)   # 256 bits, unguessable
    expires = int(time.time()) + 30 * 60  # 30 minutes, single use
    return token, expires

# On use: look up token, check expiry + unused, consume it,
# set new password hash, invalidate ALL sessions, notify user.
```

## Common mistakes
- Telling attackers which half of the credential was wrong, enabling username enumeration.
- Allowing unlimited login attempts, inviting credential stuffing.
- Issuing reset tokens that never expire or can be reused.

## Checklist
- Are login failures indistinguishable between bad user and bad password?
- Are attempts throttled with alerting on distributed patterns?
- Are reset tokens random, single-use, short-lived, and fully invalidating on use?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
