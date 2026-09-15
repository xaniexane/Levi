---
skill_id: cyber_testing_for_xss_vulnerabilities
name: Testing for XSS Vulnerabilities
description: Authorized cross-site scripting testing: reflected, stored, and DOM-based XSS with safe payload practices.
risk: low
permissions: []
requires_confirmation: false
tags: [web, xss, testing]
version: 1.0.0
---
## Purpose
Cross-site scripting remains one of the most impactful web flaws, enabling session theft and actions as the victim. This playbook covers authorized testing of your own applications for reflected, stored, and DOM-based XSS using safe, non-destructive proof payloads, plus the encoding and CSP defenses that fix it.

## When to use
- Security assessment of any application rendering user input.
- After adding rich-text, comment, or profile features.
- Validating fixes for a reported XSS finding.
- Building XSS regression tests for CI.

## Prerequisites
- Written authorization and test accounts; staging preferred for stored XSS.
- Map of inputs reflected in responses (parameters, headers, stored content).
- Proxy tooling and a safe callback setup for blind XSS confirmation (or time-based).
- Understanding of the application's output encoding and CSP.

## Procedure
1. Inventory reflection points: URL parameters, form fields, headers, file names, and stored content areas.
2. Test reflected contexts with benign probes first to identify the exact output context (HTML, attribute, JS, URL).
3. Craft context-appropriate payloads; confirm execution with a harmless marker (e.g. `console.log`, unique string in title).
4. Test stored XSS by submitting payloads and viewing them as a second test user; never test stored XSS against real users.
5. Test DOM XSS by tracing client-side sources (location, postMessage, storage) to sinks (innerHTML, eval, document.write).
6. Assess impact: session cookies (HttpOnly?), sensitive actions reachable, and admin vs user contexts.
7. Fix: context-aware output encoding, safe DOM APIs (textContent), input validation, and a strict Content Security Policy.
8. Re-test each vector after fixes; encoding bugs often survive in one context while fixed in another.
9. Test file-upload filenames and SVG uploads; they are classic stored-XSS vectors.
10. Review WYSIWYG editor configurations; they have their own XSS histories.
11. Test rich-text rendering in emails and PDFs generated from user content.

## Expected outputs
- XSS findings per vector with context, payload, and execution proof.
- Impact assessment per finding (cookie access, action capability).
- Remediation verification and CSP deployment notes.
- Upload-vector XSS test results (filenames, SVG).
- WYSIWYG editor configuration review.
- Generated-document XSS assessment.

## Pitfalls
- Testing stored XSS in production can hit real users; keep it in staging.
- DOM XSS is missed by server-side scanners; manual source-to-sink tracing is required.
- `alert(1)` proves execution but assess real impact: what can the script actually reach?
- CSP is defense in depth, not a fix; encode output correctly first.
- WYSIWYG editors have their own XSS histories; keep them patched and sandboxed.
- SVG uploads are executable content; treat them as scripts, not images.
- Mutation XSS (mXSS) bypasses server-side sanitizers; test in the real browser DOM.
- Markdown renderers have their own XSS histories; pin and patch the renderer library.

## References
- OWASP Top 10: Injection / XSS (owasp.org/www-project-top-ten).
- OWASP XSS Prevention Cheat Sheet.
- PortSwigger Web Security Academy: cross-site scripting.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
