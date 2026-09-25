---
skill_id: web_sec_output_encoding_xss
name: Output Encoding Against XSS
description: Defeat cross-site scripting by encoding output for its context and hardening with Content Security Policy.
risk: info
permissions: []
requires_confirmation: false
tags: [security, defense, web]
version: 1.0.0
---
# Output Encoding Against XSS
## Purpose
Ensure user data rendered in pages stays data and never becomes executable script.
## Key ideas
- XSS happens when attacker-controlled data is interpreted as code by the browser.
- Encode output for its context: HTML-encode in HTML, JS-encode in scripts, URL-encode in URLs.
- Modern template engines auto-escape by default; the danger is the explicit 'safe/raw' bypass.
- Content Security Policy (CSP) restricts where scripts may load from, containing the damage of an injection.
- HttpOnly cookies keep session tokens out of JavaScript's reach even if a script does execute.

## In practice
Keep auto-escaping on everywhere and treat every use of a raw/safe bypass as a security review item; most XSS bugs are a bypass applied to user data 'just this once'. Set a CSP that disallows inline scripts and restricts script sources to your own CDN, then monitor violation reports to catch both attacks and legitimate breakage. Store session identifiers in HttpOnly, Secure, SameSite cookies so a successful script injection still cannot steal the session directly. When you must render rich user HTML (comments, bios), pass it through a dedicated sanitizer with an explicit allowlist of tags and attributes, never a regex.

```html
<!-- Auto-escaped by the template engine: user text stays text -->
<p>{{ user_comment }}</p>

<!-- NEVER do this with user data -->
<!-- <p>{{ user_comment | safe }}</p> -->

<!-- Defense in depth: strict Content Security Policy -->
<!-- Content-Security-Policy: default-src 'self'; script-src 'self';
     object-src 'none'; base-uri 'self' -->
```

## Common mistakes
- Marking user content as safe/raw to fix a display quirk, opening stored XSS.
- Running without a CSP, so one injection executes with full page privileges.
- Putting session tokens in localStorage where any injected script can read them.

## Checklist
- Is auto-escaping on with every raw bypass individually reviewed?
- Does a strict CSP block inline scripts and untrusted sources?
- Are session tokens in HttpOnly cookies, not in JavaScript-reachable storage?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
