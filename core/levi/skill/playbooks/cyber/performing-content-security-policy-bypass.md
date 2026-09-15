---
skill_id: cyber_performing_content_security_policy_bypass
name: CSP Bypass Detection and Hardening
description: Detect Content-Security-Policy bypass attempts and strengthen policies against real-world evasion.
risk: low
permissions: []
requires_confirmation: false
tags: [web, hardening, detection]
version: 1.0.0
---

## Purpose

Content Security Policy is only as strong as its weakest directive: a single `unsafe-inline`, an overly broad allowlist, or a JSONP endpoint on a trusted domain can let an attacker execute script despite the policy. This playbook is defensive: it covers assessing your own CSP for bypass weaknesses, detecting bypass attempts in your logs, and hardening policies toward nonces/hashes and strict-dynamic. Testing is limited to your own applications.

## When to use

- Reviewing or deploying a Content Security Policy on your applications.
- A penetration test reports "CSP bypass" and you need to validate and fix it.
- Investigating XSS attempts that succeeded despite a deployed CSP.
- Migrating from allowlist-based CSP to nonce/hash-based strict policies.
- Building CSP monitoring (report-only mode, violation endpoints) for incident detection.

## Prerequisites

- Authorization covering the applications under assessment.
- Inventory of current CSP headers/policies per application and environment.
- A CSP evaluation mindset: know your directives (`script-src`, `object-src`, `base-uri`, `frame-ancestors`) and what each one permits.
- Access to CSP violation reports (report-uri/report-to endpoint) or application logs showing injection attempts.
- Test environment mirroring production headers for safe validation.

## Procedure

1. **Collect the effective policy.** Retrieve the actual response headers (not the intended config) for key pages, including error pages and API responses that render content. Policies set via meta tags are weaker (no framing or reporting control) — note where they are used.
2. **Evaluate for known-weak patterns.** Flag: `unsafe-inline` or `unsafe-eval` in `script-src`, `*` or `https:` wildcards, `data:` in script-src, allowlisted domains hosting JSONP or open-redirect endpoints, missing `object-src`/`base-uri` restrictions, and absent `frame-ancestors`. Each is a documented bypass class.
3. **Check trusted-domain bypasses.** For every allowlisted script domain, determine whether it hosts user-uploadable content, JSONP callbacks, or AngularJS libraries — classic policy-escape hatches. An allowlist is only as trustworthy as its least-controlled member.
4. **Validate safely in test.** Where authorized, confirm bypass impact using benign proof-of-concept payloads in the test environment only (e.g., a nonce-less inline script to prove `unsafe-inline` is effective). The goal is confirming the policy gap, not building exploit kits.
5. **Harden toward strict CSP.** Migrate `script-src` to nonces or hashes with `strict-dynamic`, remove `unsafe-inline`, set `object-src 'none'`, lock `base-uri`, and add `frame-ancestors`. Deploy in `Content-Security-Policy-Report-Only` first, tune against real violation reports, then enforce.
6. **Deploy violation monitoring.** Stand up a report collection endpoint, alert on violation spikes (which indicate either attacks or broken deployments), and retain reports for forensic correlation with WAF and application logs.
7. **Detect bypass attempts in production.** Correlate CSP violation reports with WAF XSS alerts: repeated violations from single sessions with probing payloads suggest active bypass testing. Feed confirmed attacker IPs and payload patterns into blocking rules.
8. **Regression-test on every release.** Add automated checks asserting the expected CSP header on key pages; frontend changes routinely reintroduce inline scripts that force `unsafe-inline` back. Policy strength decays without CI enforcement.

## Expected outputs

- Per-application CSP assessment: effective policy, weak patterns, and bypass feasibility ratings.
- Safe validation evidence from the test environment confirming each material gap.
- Hardened strict-CSP policies deployed via report-only → enforce migration.
- Violation monitoring with alerting on attack-indicative spikes.
- CI regression checks pinning the expected policy on key pages.

## Pitfalls

- Deploying CSP in report-only mode and never enforcing — monitoring without enforcement is theater.
- Allowlists that include CDNs or third-party domains with user-content hosting; audit every member.
- Forgetting `base-uri` and `object-src`, which bypass script-src restrictions via base-tag hijacking and plugins.
- Breaking the application with an over-strict policy and rolling back to `unsafe-inline` permanently — use report-only tuning to get it right.
- Testing bypasses against production, which risks stored payloads affecting real users; keep validation in test.

## References

- Content Security Policy Level 3 (W3C)
- OWASP Content Security Policy Cheat Sheet
- Google's CSP Evaluator documentation and strict-CSP guidance
- CWE-693, "Protection Mechanism Failure"
- MDN documentation on CSP directives and violation reporting
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
