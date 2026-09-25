---
skill_id: cyber_performing_web_cache_deception_attack
name: Detecting and Mitigating Web Cache Deception
description: Detect and harden against web cache deception, where attackers trick caches into storing authenticated responses.
risk: info
permissions: []
requires_confirmation: false
tags: [web, cache, detection]
version: 1.0.0
---

## Purpose
Web cache deception tricks a CDN or reverse proxy into caching a response that contains one victim's private data, then serves it to an attacker. This playbook is written from the defender's side: how to determine whether your applications are exposed, how to detect exploitation attempts in logs, and how to harden cache configuration. All testing described here is for systems you own, in staging first.

## When to use
- Your application serves authenticated content behind a CDN or reverse proxy cache.
- During secure design review of caching rules and cache-key configuration.
- When investigating a suspected data-exposure incident involving cached responses.

## Prerequisites
- Documentation of your cache-key scheme (what is keyed: path, query, headers, cookies).
- Access to CDN/proxy cache configuration and cache status logs (HIT/MISS).
- A staging environment mirroring production caching behavior.
- List of URL patterns that return authenticated or personalized content.

## Procedure
1. Map every cache rule: which paths are cached, what the cache key includes, and how authenticated requests are treated.
2. In staging, request authenticated-only URLs with path-confusion suffixes (e.g. `/account/profile.css`, `/account/profile/..;/x.js`) using a test account and observe cache status.
3. Flag any case where a response containing private data returns `X-Cache: HIT` for a second, unauthenticated request.
4. In production logs, hunt for requests to private paths with static-file extensions or encoded traversal that returned cache HITs.
5. Harden: exclude authenticated responses from caching (`Cache-Control: private, no-store`), normalize cache keys, and never include session cookies in the key.
6. Add detection: alert when a cache HIT is served for URL patterns classified as private.
7. Re-test in staging after changes and confirm private responses are never served from cache.
8. Verify the fix holds across all cache layers (CDN, reverse proxy, application cache), since deception can occur at any tier.
9. Include cache-deception checks in the release checklist for any feature that adds authenticated pages or changes URL routing.
10. Test authenticated API endpoints, not just pages; JSON responses carrying PII are high-value deception targets.
11. Check mobile API variants separately; they often have different cache rules than web.
12. Document the exact cache-key formula in the runbook so future changes can be reviewed against it.

## Expected outputs
- Cache-key map documenting which responses may be cached and why.
- List of vulnerable URL patterns with before/after cache behavior evidence.
- Hardened cache configuration plus a detection rule for anomalous private-path HITs.
- Release-checklist item ensuring future authenticated pages are evaluated for cache exposure.
- Per-tier test results (CDN, reverse proxy, application cache) with cache statuses.
- Runbook entry documenting the approved cache-key formula.
- Incident-response note: how to purge and verify if deception is ever exploited.

## Pitfalls
- CDN behavior differs by vendor and even by POP; test the actual production configuration.
- Over-aggressive no-cache rules can break performance; scope exclusions to private paths.
- Path normalization happens at multiple layers; a fix at the CDN may be undone by the origin.
- Log retention for cache status is often short; enable it before you need it.
- Authenticated API responses cached for performance are the highest-risk variant; audit them first.
- Keying the cache by session cookie still caches per-user private data; it is not a fix.
- A/B testing and personalization layers can reintroduce private content into shared cache entries.
- Staging that bypasses the CDN entirely gives false confidence; mirror the full chain.

## References
- OWASP Web Security Testing Guide (testing for cache-related issues).
- CDN vendor documentation on cache keys and Cache-Control handling.
- NIST SP 800-95, Guide to Secure Web Services.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
