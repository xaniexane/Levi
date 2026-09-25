---
skill_id: cyber_performing_csrf_attack_simulation
name: CSRF Control Validation
description: Validate anti-CSRF controls on your applications and detect cross-site request forgery attempts.
risk: info
permissions: []
requires_confirmation: false
tags: [web, hardening, assessment]
version: 1.0.0
---

## Purpose

Cross-site request forgery rides a victim's authenticated session: a malicious page triggers a state-changing request to your application, and the browser helpfully attaches the cookies. The defense is well understood — unpredictable tokens, SameSite cookies, and origin validation — but implementations decay: tokens missing on new endpoints, SameSite=None leftovers, GET requests that change state. This playbook covers validating your anti-CSRF controls safely on your own applications and detecting CSRF attempts in production.

## When to use

- Security review of state-changing endpoints in your applications.
- Validating anti-CSRF token coverage after a framework upgrade or new feature launch.
- A scanner or bounty report flags missing CSRF protection and you need to confirm impact.
- Investigating suspicious state changes with no corresponding user action in logs.
- Setting framework-level CSRF defaults for new services.

## Prerequisites

- Authorization covering the application under test.
- Inventory of state-changing endpoints and the CSRF defense each is supposed to use.
- Test accounts with known session state, in a test environment mirroring production defenses.
- Access to application and WAF logs for detection work.
- A local test harness page (kept off public hosting) for safe validation.

## Procedure

1. **Inventory state-changing endpoints.** List every endpoint that mutates state: profile updates, transfers, permission changes, deletions, and any GET endpoint with side effects (itself a finding). Note the expected CSRF defense per endpoint.
2. **Verify token implementation.** For token-based defenses, check: tokens are cryptographically random per session (or per request), validated on the server for every state-changing request, bound to the session, and rejected when absent or mismatched. Tokens in GET parameters or logged URLs are findings.
3. **Verify cookie and origin defenses.** Confirm session cookies carry `SameSite=Lax` or `Strict` (never `None` without `Secure` and a documented cross-site need), and that sensitive endpoints validate `Origin`/`Referer` against an allowlist where tokens are absent. Defense in depth: prefer tokens plus SameSite, not one alone.
4. **Test safely in the test environment.** Using your local harness, attempt cross-origin state-changing requests against test endpoints: missing token, wrong token, token replay across sessions, and cookie-only requests. Confirm the server rejects each. Never run these against production or with real user sessions.
5. **Hunt for gaps systematically.** Check new endpoints added since the last review, API variants of web forms (mobile/SPA endpoints often skip token checks), and state-changing GETs. CSRF coverage decays with every feature release — make this a checklist item in security review.
6. **Detect CSRF attempts in production.** Alert on: state-changing requests with missing/invalid tokens at volume from single sources, `Origin` headers pointing at attacker-like domains on sensitive endpoints, and bursts of failed token validations correlated with phishing campaigns.
7. **Fix structurally.** Prefer framework-level CSRF middleware enabled by default over per-endpoint tokens; eliminate state-changing GETs; set SameSite defaults at the cookie-issuing layer. Per-endpoint fixes do not survive team turnover — defaults do.
8. **Regression-test.** Add automated tests asserting token rejection on state-changing endpoints and cookie attribute assertions to CI, so future changes cannot silently drop protection.

## Expected outputs

- Endpoint inventory with per-endpoint CSRF defense status.
- Safe test evidence confirming token/cookie/origin validation behavior.
- Severity-rated findings for unprotected or weakly protected endpoints.
- Structural fixes: framework defaults, SameSite policy, elimination of state-changing GETs.
- Production detection rules for CSRF probing and CI regression tests.

## Pitfalls

- Protecting the web form but not the API endpoint behind it — SPAs and mobile apps are the usual gap.
- `SameSite=None` carried over from a legacy integration need, silently disabling the cookie defense.
- Tokens validated client-side or only on some code paths; validation must be server-side and universal.
- Testing against production with real sessions, which can trigger actual state changes.
- Treating CSRF as low severity by default — on financial, admin, or account-recovery endpoints it is not.

## References

- OWASP Cross-Site Request Forgery Prevention Cheat Sheet
- CWE-352, "Cross-Site Request Forgery (CSRF)"
- RFC 6265bis (SameSite cookie semantics)
- MITRE ATT&CK T1204-adjacent context for user-interaction-dependent attacks
- Framework documentation for CSRF middleware (Django, Rails, Spring, Express/csrf)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
