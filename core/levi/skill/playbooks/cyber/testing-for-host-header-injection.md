---
skill_id: cyber_testing_for_host_header_injection
name: Testing for Host Header Injection
description: Authorized testing for Host header attacks: password-reset poisoning, cache poisoning, and routing flaws.
risk: low
permissions: []
requires_confirmation: false
tags: [web, injection, testing]
version: 1.0.0
---
## Purpose
Applications that trust the Host header for generating links, selecting tenants, or cache keys are vulnerable to poisoning: password-reset emails pointing at attacker domains, cache entries keyed to evil hosts, or routing to the wrong tenant. This playbook covers authorized testing of your own applications and the validation patterns that fix it.

## When to use
- Security testing of multi-tenant or white-label applications.
- Reviewing password-reset and email-link generation code.
- After adding custom-domain support for tenants.
- Investigating phishing reports abusing your reset flows.

## Prerequisites
- Written authorization and test accounts for reset flows.
- List of valid hostnames and tenant domains for the application.
- Proxy tooling for Host header manipulation.
- Access to email capture for observing generated links.

## Procedure
1. Baseline: record how the application uses the Host header (absolute URLs, tenant selection, cache keys).
2. Send requests with an attacker domain in the Host header; check password-reset emails and generated links.
3. Test `X-Forwarded-Host` and similar proxy headers, which applications often trust implicitly.
4. Attempt cache poisoning via Host variants if responses are cached.
5. Test tenant confusion: does another tenant's Host serve the victim tenant's data?
6. Verify the fix: allowlist of valid hosts, generated links built from configuration (not the request), and Host validation at the edge.
7. Confirm that unrecognized hosts receive an error, not a default tenant's content.
8. Re-test reset flows and multi-tenant routing after the fix.
9. Test absolute-URL generation in passwordless and magic-link flows as well.
10. Check Kubernetes ingress default backends; they can serve the app on unexpected hosts.
11. Verify that health-check and internal endpoints also validate Host.

## Expected outputs
- Host-header test matrix with observed behaviors per variant.
- Findings including reset-poisoning proof in captured emails.
- Allowlist configuration and retest evidence.
- Magic-link and passwordless flow Host test results.
- Ingress default-backend review.
- Internal endpoint Host-validation status.

## Pitfalls
- Frameworks behind proxies see the proxy's Host; configure trusted proxies explicitly.
- Fixing the web app while the CDN still forwards arbitrary Host headers leaves exposure.
- Default virtual hosts serving real content turn any Host attack into tenant confusion.
- Password-reset tokens in poisoned links are time-sensitive; test quickly and rotate test tokens.
- Kubernetes ingress default backends can serve the app on unexpected hosts; check ingress config.
- Health checks that skip Host validation are minor alone but aid reconnaissance.
- CDN host-header forwarding settings can reintroduce the flaw after the app is fixed.
- Web cache keyed on Host can be poisoned alongside the application; test the cache layer too.

## References
- OWASP Web Security Testing Guide: host header testing.
- PortSwigger Web Security Academy: host header attacks.
- Framework documentation on trusted hosts/proxies.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
