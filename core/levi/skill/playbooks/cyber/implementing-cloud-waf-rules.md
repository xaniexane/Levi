---
skill_id: cyber_implementing_cloud_waf_rules
name: Cloud WAF Rule Design and Tuning
description: Design, test, and operate cloud WAF rulesets that block real attacks without breaking legitimate traffic.
risk: moderate
permissions: []
requires_confirmation: true
tags: [cloud, waf]
version: 1.0.0
---
## Purpose
A WAF with default rules in block mode is either blocking customers or blocking nothing — usually
both at different times. Effective WAF operation means: managed baseline rules tuned to your
applications, custom rules for your specific threats (credential stuffing, scraping, business-logic
abuse), and a disciplined count→block lifecycle. This playbook implements that discipline on a cloud
WAF (AWS WAF, Cloudflare, Azure WAF, GCP Cloud Armor — patterns are portable). Confirmation is
required because WAF changes directly affect production traffic.

## When to use
- Deploying a WAF in front of internet-facing applications for the first time.
- After WAF bypasses or incidents where the WAF should have blocked (SQLi, XSS, L7 DDoS, bot abuse).
- Tuning a noisy WAF that blocks legitimate users or drowns the SOC in false positives.
- Meeting PCI DSS 6.4 / 11.6 or contractual requirements for web-application protection.
- As the enforcement layer for API threat protection and bot management programs.

## Prerequisites
- The WAF deployed in front of target applications (CDN, ALB, API Gateway, or cloud-native
  attachment) with logging enabled to durable storage/SIEM.
- Application knowledge: tech stack, legitimate traffic patterns, known bots/partners, and release
  cadence.
- A non-production environment (or traffic mirroring) for rule testing.
- Change control with rollback: who approves rule changes, how to revert in minutes.
- Baseline traffic data: at least 2 weeks of logs to distinguish normal from attack.

## Procedure
1. **Start every rule in count/monitor mode.** Deploy managed rule groups (baseline: SQLi, XSS,
   known-bad inputs; plus platform-specific groups) in count mode first. Collect 1-2 weeks of
   would-block data. Never enable block mode on a rule you haven't measured.
2. **Tune the managed baselines.** Analyze count-mode hits: identify false positives (legitimate
   requests matching rules — common with rich-text inputs, APIs, and admin panels) and create scoped
   exclusions (by path, parameter, or header — never global rule disables). Only then switch to
   block mode, rule group by rule group.
3. **Add rate-based rules for abuse.** Implement rate limiting on: login/auth endpoints (credential
   stuffing), expensive operations (search, export, report generation), and APIs (per-key quotas).
   Set thresholds from measured p99 traffic plus headroom; alert before blocking on first
   deployment.
4. **Write custom rules for your threats.** Managed rules don't know your business logic: block/flag
   scraping patterns (sequential ID enumeration), enforce geo restrictions where the business
   allows, challenge known-bad ASNs or data-center ranges hitting login endpoints, and create rules
   for incident-specific IOCs. Document each custom rule's intent and owner.
5. **Implement bot management deliberately.** Distinguish: good bots (search engines, uptime
   monitors, partners — allowlist), bad bots (credential stuffing, scalping, scraping —
   challenge/block), and gray (rate-limit). Use the platform's bot signals (TLS/JA3 fingerprints,
   behavior) rather than user-agent strings alone.
6. **Protect the WAF configuration itself.** Restrict who can edit rules (IAM/RBAC, MFA, change
   tickets), log all rule changes, and alert on changes outside change windows. A WAF an attacker
   can reconfigure is worse than none — it provides false confidence.
7. **Test with real attacks.** Periodically replay attack samples (SQLi, XSS, path traversal,
   Log4Shell-style payloads) against a staging WAF and confirm blocks; test bypass variants
   (encoding, case, chunking) to find rule gaps. Include WAF validation in pre-launch testing for
   new apps.
8. **Monitor as a detection source.** Ship WAF logs to the SIEM. Alert on: spikes in blocked
   requests (active attack), blocks on admin/login paths, bypass-indicator patterns (same attacker
   trying encodings), and rule-change events. Blocked-attack timelines are incident evidence.
9. **Maintain a rule lifecycle.** Quarterly: review custom rules for continued relevance, update
   managed rule group versions (vendors add/retire rules — test updates in count mode first), prune
   stale exclusions, and re-baseline rate limits after traffic changes (launches, marketing
   campaigns).
10. **Plan for bypass and failure.** Document: what happens if the WAF fails (fail-open vs.
    fail-closed per app — a business decision), how to emergency-disable a rule breaking production
    (runbook with <15 min target), and the escalation path when blocks spike. Test the emergency
    disable quarterly.

## Expected outputs
- Managed rule groups tuned and in block mode with scoped exclusions documented.
- Rate-based rules on auth and expensive endpoints; custom rules for business-specific threats.
- Bot management policy distinguishing good/bad/gray automation.
- Change-controlled WAF configuration with logged changes and emergency rollback runbook.
- SIEM-integrated WAF logging with attack-spike alerting and quarterly rule reviews.

## Pitfalls
- Block mode on day one: guaranteed false positives blocking customers. Count → tune → block,
  always.
- Global rule disables instead of scoped exclusions: one noisy endpoint shouldn't disarm protection
  for the whole app.
- Rate limits from guesses: too tight breaks launches; too loose doesn't stop stuffing. Measure p99,
  add headroom, alert first.
- Forgetting managed-rule updates: vendors evolve rules; pinned old versions miss new attack
  classes. Update on a tested cadence.
- No emergency rollback plan: when a rule breaks checkout on Black Friday, you need a 15-minute
  disable path, not a change ticket.

## References
- OWASP Core Rule Set documentation (rule tuning methodology, applies beyond ModSecurity)
- Cloud vendor WAF documentation (AWS WAF, Cloudflare, Azure WAF, GCP Cloud Armor rule management)
- PCI DSS v4.0 Requirement 6.4.2 (WAF or equivalent for public-facing web apps)
- MITRE ATT&CK T1190 (Exploit Public-Facing Application) — what WAF rules mitigate
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
