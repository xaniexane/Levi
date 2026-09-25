---
skill_id: web_sec_session_management
name: Session Management
description: Run sessions securely: random ids, server-side state, rotation, timeouts, and logout that actually logs out.
risk: info
permissions: []
requires_confirmation: false
tags: [security, defense, web]
version: 1.0.0
---
# Session Management
## Purpose
Keep the 'logged in' state trustworthy from login through logout, across devices and incidents.
## Key ideas
- Session ids must be long, random, and unguessable; never derive them from usernames or timestamps.
- Store session data server-side keyed by the id; the cookie carries only the random identifier.
- Rotate the session id at login and privilege changes to defeat session fixation.
- Idle timeouts limit the window of an abandoned session; absolute timeouts bound total session life.
- Logout must destroy the server-side session, not just delete the client cookie.

## In practice
Generate session ids from a cryptographic random source with at least 128 bits of entropy, and mark the cookie HttpOnly, Secure, and SameSite. Bind sessions lightly to context (a hash of user agent plus IP subnet) and challenge on significant change rather than hard-failing, since mobile IPs roam. Implement idle timeout (15-30 minutes for sensitive apps) and absolute timeout (8-24 hours), and give users a visible 'sign out everywhere' that revokes all sessions; during a suspected compromise this is the button that matters. Log session creation, rotation, and destruction with the account id so anomalous session patterns are investigable.

```python
import secrets

def new_session_id() -> str:
    return secrets.token_urlsafe(32)  # 256-bit random id

# On login:
#   1. destroy any pre-login session (fixation defense)
#   2. create session server-side: {user_id, created_at, last_seen, ua_hash}
#   3. set cookie: session=<id>; HttpOnly; Secure; SameSite=Lax; Path=/
# On each request: refresh last_seen; enforce idle + absolute timeouts
# On logout: delete server-side session AND clear the cookie
```

## Common mistakes
- Using predictable session ids (usernames, sequential numbers) that attackers can guess.
- Deleting only the client cookie on logout while the server session stays valid.
- Never expiring sessions, so a stolen cookie works forever.

## Checklist
- Are session ids 128-bit cryptographic random with secure cookie flags?
- Is the id rotated at login and sessions expired by idle and absolute timeouts?
- Does logout destroy server-side state with a working sign-out-everywhere?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
