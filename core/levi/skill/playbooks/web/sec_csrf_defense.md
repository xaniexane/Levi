---
skill_id: web_sec_csrf_defense
name: CSRF Defense
description: Stop cross-site request forgery with tokens, SameSite cookies, and origin checks on state-changing requests.
risk: info
permissions: []
requires_confirmation: false
tags: [security, defense, web]
version: 1.0.0
---
# CSRF Defense
## Purpose
Ensure state-changing requests originate from your own pages, not from an attacker's site riding the user's session.
## Key ideas
- CSRF exploits the browser's automatic cookie sending: a malicious page triggers a request your session authorizes.
- Synchronizer tokens (per-session, per-form secrets) prove the request came from your rendered page.
- SameSite=Lax or Strict on session cookies blocks most cross-site cookie sending outright.
- Checking Origin/Referer headers adds a second layer for fetch and form submissions.
- GET requests must never change state, or CSRF protection has nothing to anchor to.

## In practice
Layer the defenses: SameSite cookies as the baseline, anti-CSRF tokens on all state-changing forms and fetch calls, and Origin checks on the server as backstop. Generate tokens per session with a cryptographic random source, rotate them on privilege changes, and validate with constant-time comparison. For single-page apps, the double-submit cookie pattern or a custom header (which cross-site forms cannot set) both work; pick one and apply it uniformly. Test by building a malicious page in staging that auto-submits to your endpoints; if any state changes, the defense has a gap.

```html
<!-- Server renders a per-session token into each form -->
<form method="post" action="/transfer">
  <input type="hidden" name="csrf_token" value="9f2c7a1e4b6d...">
  <input type="number" name="amount" required>
  <button type="submit">Send</button>
</form>

<!-- For fetch calls: custom header the browser only sends same-origin -->
<script>
fetch("/api/transfer", {
  method: "POST",
  headers: {"Content-Type": "application/json", "X-CSRF-Token": csrfToken},
  body: JSON.stringify({amount: 50}),
});
</script>
```

## Common mistakes
- Relying on SameSite alone while supporting old browsers that ignore it.
- Protecting forms but forgetting JSON API endpoints that change state.
- Using GET requests for state changes, making CSRF possible with a simple link.

## Checklist
- Do all state-changing requests carry an anti-CSRF token or custom header?
- Are session cookies SameSite=Lax or Strict?
- Is there a staging test that attempts CSRF against your endpoints?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
