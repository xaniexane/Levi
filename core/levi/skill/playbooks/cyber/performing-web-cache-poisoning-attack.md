---
skill_id: cyber_performing_web_cache_poisoning_attack
name: Detecting and Mitigating Web Cache Poisoning
description: Detect and harden against web cache poisoning, where unkeyed inputs let attackers poison cached responses served to others.
risk: info
permissions: []
requires_confirmation: false
tags: [web, cache, detection]
version: 1.0.0
---

## Purpose
In web cache poisoning, an attacker smuggles malicious content through an input the cache does not include in its key (an unkeyed header or parameter), so the poisoned response is served to other users. This playbook takes the defender's view: identifying unkeyed inputs, detecting poisoning attempts in logs, and hardening cache behavior. Testing is for your own systems, in staging.

## When to use
- Your stack caches responses at a CDN, WAF, or reverse proxy.
- After adding new headers, query parameters, or marketing parameters to the application.
- When WAF or CDN logs show anomalous cache HITs with unexpected content.

## Prerequisites
- Full cache-key documentation: keyed vs unkeyed inputs per route.
- Staging environment with production-equivalent caching.
- Access to cache logs showing HIT/MISS and the request that populated the entry.
- Inventory of user-controlled inputs reflected in responses (headers, parameters).

## Procedure
1. Enumerate inputs reflected in responses: query parameters, headers (e.g. X-Forwarded-Host, User-Agent), and cookies.
2. Determine which of these are excluded from the cache key; those are your unkeyed inputs.
3. In staging, send requests varying only unkeyed inputs and check whether distinct variants collapse into one cached entry.
4. Test whether attacker-controlled reflection (e.g. a JavaScript payload in an unkeyed header) gets stored and served to a second clean request.
5. Review production logs for bursts of requests with unusual header values followed by elevated cache HIT rates on the same URLs.
6. Harden: include security-relevant inputs in the cache key or strip them before caching; validate the Host header; set explicit Vary and Cache-Control directives.
7. Deploy detection: alert on cache HIT responses whose bodies contain unexpected script content or mismatched headers.
8. Establish a cache purge runbook: who can purge, how fast, and how to confirm the poisoned entry is gone from all POPs.
9. Re-test after every CDN configuration change; cache-key behavior is frequently altered by well-meaning performance tuning.
10. Audit the `Vary` header configuration; missing Vary on User-Agent or encoding widens poisoning.
11. Test marketing and analytics parameters specifically; they are the most common unkeyed inputs.
12. Verify that error pages are not cached with attacker-influenced content.

## Expected outputs
- Unkeyed-input inventory per cached route with risk rating.
- Evidence of exploitable poisoning paths found in staging (before fix).
- Hardened cache configuration and a cache-poisoning detection rule.
- Cache purge runbook with roles, timing, and verification steps.
- Vary-header audit results per cached route.
- Change-control record linking cache configuration changes to the finding.
- Monitoring dashboard for cache HIT-rate anomalies per URL pattern.

## Pitfalls
- Unkeyed inputs often arrive via marketing or analytics parameters added without security review.
- Some CDNs normalize or drop headers silently; verify actual edge behavior, not documentation.
- Purging poisoned entries is time-sensitive; know your cache purge procedure in advance.
- Fat-pipe testing in production can poison real users; keep proof-of-concept work in staging.
- Response-header reflection (e.g. via unkeyed `X-Forwarded-*` headers) is easy to miss when only body content is reviewed.
- Error-page caching with reflected input is an overlooked poisoning vector.
- Multiple cache layers with different key rules create inconsistent protection; align them.
- Cache-busting parameters added by developers can become unkeyed inputs themselves.

## References
- PortSwigger Web Security Academy: Web cache poisoning (portswigger.net/web-security).
- OWASP Web Security Testing Guide.
- CDN vendor cache-key and purge documentation.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
