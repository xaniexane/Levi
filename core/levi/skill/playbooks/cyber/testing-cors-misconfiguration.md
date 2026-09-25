---
skill_id: cyber_testing_cors_misconfiguration
name: Testing for CORS Misconfiguration
description: Authorized testing of CORS policies for reflected origins, null origin, and credentialed wildcard flaws.
risk: low
permissions: []
requires_confirmation: false
tags: [api, cors, testing]
version: 1.0.0
---
## Purpose
Cross-Origin Resource Sharing misconfigurations let attacker sites read authenticated API responses in victims' browsers. This playbook covers authorized testing of your own applications' CORS policies: detecting reflected origins, null origin trust, and wildcard-with-credentials flaws, plus the correct restrictive configuration.

## When to use
- Security testing of browser-facing APIs.
- After adding new origins for partners or frontends.
- Reviewing CDN or gateway CORS settings.
- Investigating suspected cross-origin data theft.

## Prerequisites
- Written authorization and the list of intended allowed origins.
- Test setup able to send arbitrary Origin headers (proxy or curl).
- Understanding of which endpoints require authentication.
- Access to the CORS configuration (application, gateway, or CDN).

## Procedure
1. Identify endpoints returning `Access-Control-Allow-Origin` and note which require credentials.
2. Send requests with an attacker-controlled Origin; flag if it is reflected verbatim in the response.
3. Test the `null` origin, subdomain variations, and suffix tricks (e.g. `trusted.com.evil.com`).
4. Check whether `Access-Control-Allow-Credentials: true` is combined with a dynamic or wildcard origin.
5. Verify preflight handling: which methods and headers are allowed for untrusted origins.
6. Assess impact: can an attacker's page read authenticated responses, or only unauthenticated ones?
7. Fix: allowlist exact origins, never reflect; avoid credentials unless required; set `Vary: Origin`.
8. Re-test all origin variants after the fix and add CORS checks to security regression tests.
9. Test WebSocket handshake origins with the same rigor; they share the browser trust model.
10. Monitor DNS for subdomain takeovers that would turn allowlisted origins hostile.
11. Verify that mobile WebView origins are handled distinctly from browser origins.

## Expected outputs
- CORS test matrix: origin tested, response headers, verdict.
- Findings with exploitability assessment per endpoint.
- Corrected CORS configuration and regression tests.
- WebSocket origin validation results.
- Subdomain-takeover monitoring status.
- WebView origin handling assessment.

## Pitfalls
- Reflecting origins is sometimes intentional for public APIs; the risk is credentialed reflection.
- Suffix-matching bugs (`evil-trusted.com`) are common in hand-rolled validators; use exact matching.
- CDN-cached CORS headers can serve stale permissive policies; purge after changes.
- Preflight caching (`Access-Control-Max-Age`) prolongs the window of a bad policy.
- Subdomain takeovers turn allowlisted origins into attacker origins; monitor DNS.
- Allowing null origin for credentialed requests is almost never correct.
- Developer tools and browser extensions can mask CORS behavior; test with clean profiles.
- Server-sent events and other streaming endpoints need the same origin checks as XHR.

## References
- OWASP Web Security Testing Guide: testing for CORS.
- PortSwigger Web Security Academy: CORS.
- MDN Web Docs: CORS protocol.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
