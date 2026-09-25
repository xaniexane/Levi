---
skill_id: cyber_testing_for_open_redirect_vulnerabilities
name: Testing for Open Redirect Vulnerabilities
description: Authorized testing for open redirects in redirect parameters, and allowlist-based fixes.
risk: low
permissions: []
requires_confirmation: false
tags: [web, testing, phishing]
version: 1.0.0
---
## Purpose
Open redirects turn your domain's trust into phishing leverage: `yoursite.com/?next=evil.com` makes a malicious link look legitimate. This playbook covers authorized testing of redirect parameters in your own applications and the allowlist patterns that eliminate the issue.

## When to use
- Security testing of login, logout, and post-action redirect flows.
- After adding `next`, `returnUrl`, or `redirect` parameters.
- Reviewing OAuth or SSO flows that bounce through your domain.
- Investigating phishing reports abusing your domain in redirect chains.

## Prerequisites
- Written authorization and a map of endpoints accepting redirect targets.
- Proxy tooling for parameter manipulation.
- Knowledge of intended redirect destinations per flow.
- Understanding of any existing allowlist or validation logic.

## Procedure
1. Inventory all parameters and headers influencing redirects (`next`, `returnUrl`, `redirect_uri`, `Referer`-based).
2. Substitute an external domain; check for a 302/JS/meta-refresh to it.
3. Try bypasses: `//evil.com`, `/\/evil.com`, `evil%2ecom`, `trusted.com.evil.com`, and protocol variants (`javascript:`, `data:`).
4. Test each bypass against the validation logic; record which are blocked and which pass.
5. Assess chaining: can the redirect land on an attacker page that then harvests credentials with your branding context?
6. Fix: allowlist of exact destinations or indirect redirect IDs mapped server-side; reject everything else.
7. Re-test the full bypass list after the fix.
8. Monitor logs for redirect-parameter probing as an early phishing-campaign signal.
9. Test logout and post-registration redirects, not just login flows.
10. Check mobile deep-link redirects; they have the same phishing leverage.
11. Verify that error pages do not redirect to user-controlled locations.

## Expected outputs
- Redirect parameter inventory with test results per bypass variant.
- Findings with phishing-abuse impact assessment.
- Allowlist configuration and retest evidence.
- Full redirect-flow inventory with test results.
- Deep-link redirect assessment.
- Error-page redirect review.

## Pitfalls
- Regex-based validators are bypassed regularly; use URL parsing plus exact allowlists.
- Client-side redirect validation is not a control.
- OAuth `redirect_uri` validation must be exact; open redirect there enables token theft.
- Fixing the login flow while marketing pages keep `?next=` leaves the phishing vector alive.
- Allowing redirects to any subdomain is risky when subdomains host user content.
- Marketing pages with `?next=` parameters are frequently forgotten in remediation.
- URL shorteners in the redirect chain obscure the final destination; resolve fully when testing.
- Redirects after OAuth consent are trusted implicitly by users; validate them strictly.

## References
- OWASP Web Security Testing Guide: testing for open redirects.
- OWASP Cheat Sheet: unvalidated redirects and forwards.
- PortSwigger Web Security Academy: open redirection.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
