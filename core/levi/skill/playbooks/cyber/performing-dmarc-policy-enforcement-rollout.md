---
skill_id: cyber_performing_dmarc_policy_enforcement_rollout
name: DMARC Policy Enforcement Rollout
description: Roll out DMARC from monitoring to enforcement to stop exact-domain email spoofing.
risk: low
permissions: []
requires_confirmation: false
tags: [email, hardening, phishing]
version: 1.0.0
---

## Purpose

DMARC lets domain owners tell receivers what to do with mail that fails SPF/DKIM authentication — and, critically, gives owners visibility through aggregate reports. Rolling it out carelessly (jumping to `p=reject`) breaks legitimate mail flows; rolling it out correctly stops exact-domain spoofing, the backbone of much business email compromise. This playbook covers the staged rollout: inventory senders, deploy monitoring, remediate legitimate failures, then enforce.

## When to use

- Your domain lacks DMARC or sits at `p=none` and spoofing is a concern.
- A phishing incident used your exact domain as the sender.
- Compliance or customer contracts require email authentication.
- Consolidating email security after mergers or SaaS sprawl (many senders, little visibility).
- Preparing for BIMI (brand indicators), which requires enforced DMARC.

## Prerequisites

- Control of the domain's DNS (ability to publish TXT records).
- Inventory of legitimate senders: corporate mail, marketing platforms, ticketing, HR systems, and any SaaS that sends as your domain.
- SPF and DKIM deployed (or deployable) on those senders — DMARC builds on them; it cannot fix their absence.
- A mailbox or reporting service for DMARC aggregate (rua) and forensic (ruf) reports.
- Change window awareness: DNS propagation and mail-flow validation take days per stage.

## Procedure

1. **Inventory every legitimate sender.** Survey IT, marketing, and business units for anything sending as your domain, including forgotten SaaS integrations. Check current SPF/DKIM status per sender. Unknown senders discovered later are the top cause of enforcement breakage.
2. **Publish DMARC in monitoring mode.** Deploy `_dmarc` TXT with `p=none`, `rua` pointing at your report mailbox, and a reasonable `pct=100`. Monitoring mode changes nothing about delivery — it only starts the visibility feed.
3. **Analyze aggregate reports.** Parse rua reports (use a DMARC analysis tool, not raw XML) to map: which IPs/domains send as you, their SPF/DKIM pass rates, and forwarding-induced failures. Build the definitive sender list from data, not surveys.
4. **Fix legitimate authentication failures.** For each legitimate sender failing DMARC: add missing SPF includes (watch the 10-DNS-lookup limit — flatten if needed), configure DKIM signing, and align the From domain with the authenticated domain (DMARC requires alignment, not just a pass). Work with vendors that do not support DKIM — replace or isolate them.
5. **Address forwarding and mailing lists.** Identify forwarders and lists that break SPF/DKIM; where they matter, ensure ARC or DKIM-surviving configurations, or accept and document the residual failure. Do not let edge cases block the whole rollout indefinitely — scope them explicitly.
6. **Step up enforcement gradually.** Move `p=quarantine` with `pct` ramping (10 → 25 → 50 → 100), monitoring reports and helpdesk tickets at each step for legitimate mail being quarantined. Then move to `p=reject` with the same ramp. Each stage needs days of observation.
7. **Lock down subdomains.** Set an explicit `sp=` policy (reject for non-sending subdomains) so attackers cannot simply spoof `subdomain.yourdomain`. Publish SPF/DKIM/DMARC for major subdomains or a wildcard policy as appropriate.
8. **Maintain continuously.** Monitor reports for new senders (SaaS sprawl never stops), review `p=reject` effectiveness via spoofing tests, and keep SPF records within lookup limits as senders change.

## Expected outputs

- A data-driven inventory of legitimate senders with SPF/DKIM/DMARC status.
- DMARC deployed at `p=reject` (with `sp=` coverage) after staged ramp-up.
- Remediated authentication for all legitimate senders; documented exceptions.
- Ongoing aggregate-report monitoring with new-sender alerting.
- Measurable reduction in exact-domain spoofing reaching inboxes.

## Pitfalls

- Jumping straight to `p=reject` — legitimate mail will break, and the rollback will be cited forever as why "DMARC doesn't work."
- SPF lookup-limit exceeded (more than 10 DNS lookups) silently failing SPF for everyone; flatten includes.
- Forgetting alignment: SPF/DKIM can pass while DMARC fails if the domains do not align with the From header.
- Ignoring subdomains — attackers pivot to `secure.yourdomain` the day you enforce on the apex.
- Publishing the record and never reading the reports; the visibility is half the value.

## References

- RFC 7489 (DMARC specification)
- CISA guidance on email authentication and BOD 18-01 context
- NIST SP 800-177, "Trustworthy Email"
- DMARC.org deployment guidance
- M3AAWG best practices for sender authentication
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
