---
skill_id: web_sec_security_headers
name: Security Headers
description: Harden every response with headers: CSP, HSTS, X-Frame-Options, and the rest of the defensive set.
risk: info
permissions: []
requires_confirmation: false
tags: [security, defense, web, http]
version: 1.0.0
---
# Security Headers
## Purpose
Turn on the browser's built-in protections with a small set of response headers on every page.
## Key ideas
- Content-Security-Policy controls which sources can load scripts, styles, and frames: the strongest header you set.
- Strict-Transport-Security tells browsers to use HTTPS only, for you and your subdomains, for a long max-age.
- X-Frame-Options or frame-ancestors stops your pages being framed by attacker sites (clickjacking defense).
- X-Content-Type-Options: nosniff stops browsers from guessing content types, blocking a class of smuggling tricks.
- Referrer-Policy and Permissions-Policy limit what data and device features leak to third parties.

## In practice
Set the baseline set on every response from the edge or framework middleware so no route is forgotten: HSTS, nosniff, frame denial, a referrer policy, and a CSP. Start CSP in report-only mode, collect violation reports for a week, then enforce; flipping straight to enforce breaks legitimate features you forgot. Keep the policy tight but honest: 'self' plus the specific CDNs you actually use, no wildcards, no unsafe-inline once you have refactored. Re-scan headers after every major deploy, because new pages and new third-party scripts are how policies silently rot.

```http
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'; script-src 'self' https://cdn.example.com; object-src 'none'; base-uri 'self'; frame-ancestors 'none'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

## Common mistakes
- Deploying CSP straight to enforce mode and breaking production features that violate it.
- Setting headers on some routes but not others, leaving forgotten pages unprotected.
- Allowing unsafe-inline or broad wildcards in CSP, neutering the protection.

## Checklist
- Is the baseline header set applied to every response from shared middleware?
- Was CSP tuned in report-only mode before enforcement?
- Are headers re-verified after deploys that add pages or third parties?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
