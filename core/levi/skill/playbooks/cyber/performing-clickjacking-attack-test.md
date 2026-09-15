---
skill_id: cyber_performing_clickjacking_attack_test
name: Clickjacking Control Validation
description: Verify that your applications resist UI-redressing attacks through framing controls and test the defenses safely.
risk: info
permissions: []
requires_confirmation: false
tags: [web, hardening, assessment]
version: 1.0.0
---

## Purpose

Clickjacking (UI redressing) tricks a user into clicking something different from what they perceive — typically by layering a transparent iframe of your application under an attacker-controlled page. The defensive question is simple: can your sensitive pages be framed, and do your framing controls actually hold? This playbook covers validating `X-Frame-Options` and Content-Security-Policy `frame-ancestors` on your own applications, testing the controls safely, and remediating gaps. All testing is limited to applications you own or are authorized to assess.

## When to use

- Security review of any page with state-changing actions: account settings, payment flows, admin consoles, OAuth consent screens.
- Validating a recent header or CSP deployment before declaring it effective.
- A penetration test or scanner flags "missing X-Frame-Options" and you need to confirm real impact.
- Building secure defaults for a web framework or shared frontend platform.
- Post-incident review if a UI-redressing lure is suspected.

## Prerequisites

- Authorization covering the application under test.
- A list of sensitive endpoints and the framing policy each is supposed to enforce.
- A test harness: a local HTML page you control that attempts to iframe the target (same test origin discipline — never host the harness on a public domain).
- Browser developer tools and the ability to inspect response headers on the target endpoints.

## Procedure

1. **Inventory sensitive framed-able pages.** List pages where a hijacked click has consequences: transfers, permission grants, settings changes, delete actions, and login forms (login CSRF via framing). Note which are supposed to be frameable (e.g., intentional embeds, widgets) versus not.
2. **Inspect framing headers on each page.** For every sensitive endpoint, record the `X-Frame-Options` value (`DENY`, `SAMEORIGIN`) and the CSP `frame-ancestors` directive. Check both the HTML document response and any endpoints that render forms via AJAX/partials — headers must be set consistently, including on error pages.
3. **Test framing safely.** Load your local harness page that iframes the target URL. Confirm whether the browser renders it or blocks it, and which policy did the blocking (devtools console names the violated directive). Test with both `http`/`https` variants and with the page reached via redirects, since header loss on redirect chains is a common gap.
4. **Probe for bypass conditions.** Check: pages that set `ALLOW-FROM` (obsolete and ignored by modern browsers — treat as unprotected), missing headers on mobile or API-rendered variants of the same page, overly broad `frame-ancestors` (e.g., `https:` or wildcarded subdomains you do not control), and endpoints that reflect user content that could break out of intended framing.
5. **Assess residual risk per page.** A missing header on a read-only marketing page is informational; on a "delete account" confirmation it is a real finding. Document exploitability honestly: clickjacking still requires user interaction and social engineering, so severity follows the sensitivity of the framed action.
6. **Remediate with layered controls.** Set `frame-ancestors 'none'` (or `'self'` where same-origin framing is required) via CSP as the primary control, keep `X-Frame-Options: DENY`/`SAMEORIGIN` for legacy browser coverage, and for the highest-sensitivity actions add defense in depth: re-authentication or step-up confirmation before the action executes, so a hijacked click alone is insufficient.
7. **Verify and regression-test.** Re-run the harness against the fixed endpoints and confirm blocking. Add header assertions to your CI pipeline or synthetic monitoring so a future deployment cannot silently drop the protection.

## Expected outputs

- An inventory of sensitive pages with their framing policy status (protected / gap / intentionally frameable).
- Safe test evidence: harness results showing which pages render in an iframe and which are blocked.
- Severity-rated findings tied to the sensitivity of each framed action.
- Remediation: CSP `frame-ancestors` and `X-Frame-Options` changes plus step-up controls where warranted.
- Regression coverage (CI assertions or monitor checks) preventing future header loss.

## Pitfalls

- Relying solely on `X-Frame-Options: ALLOW-FROM`, which modern browsers ignore — the page is effectively unprotected.
- Setting headers on the main page but not on error pages, print views, or mobile variants that render the same actions.
- Overly broad `frame-ancestors` (wildcards, `https:`) that permit framing from origins you do not control.
- Treating clickjacking as critical on read-only pages; calibrate severity to the framed action or findings lose credibility.
- Testing with a publicly hosted harness page, which itself becomes an attack artifact — keep the harness local.

## References

- OWASP guidance on clickjacking defense (frame-ancestors, X-Frame-Options)
- Content Security Policy Level 3, `frame-ancestors` directive (W3C)
- RFC 7034 (X-Frame-Options header semantics)
- CWE-1021, "Improper Restriction of Rendered UI Layers or Frames"
- MDN documentation on X-Frame-Options and CSP frame-ancestors
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
