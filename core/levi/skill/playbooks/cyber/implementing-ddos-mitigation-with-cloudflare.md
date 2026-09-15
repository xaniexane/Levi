---
skill_id: cyber_implementing_ddos_mitigation_with_cloudflare
name: DDoS Mitigation with Cloudflare
description: Deploy Cloudflare DDoS protection: proxying, L3/L4/L7 rules, and tested incident runbooks.
risk: moderate
permissions: []
requires_confirmation: true
tags: [network, ddos]
version: 1.0.0
---
## Purpose
DDoS attacks don't need to breach anything to cause damage — saturating links, exhausting
application capacity, or triggering cloud autoscale bills is enough. Cloudflare's globally
distributed edge absorbs volumetric attacks and provides L7 controls for application-layer floods.
This playbook onboards assets to Cloudflare with correct DNS/proxying, tuned DDoS rules, and
rehearsed response. Confirmation is required: DNS and traffic-routing changes affect production
availability.

## When to use
- Protecting internet-facing web properties, APIs, and infrastructure from DDoS.
- After DDoS incidents that caused outages or ransom-adjacent extortion attempts.
- Before high-visibility events (launches, elections, sales) that attract attacks.
- When origin infrastructure is directly exposed (attackers bypassing the CDN by hitting origin
  IPs).
- As the network-availability layer of the resilience program.

## Prerequisites
- Inventory of assets to protect: domains, subdomains, APIs, and origin IPs/hosting.
- DNS control: ability to change nameservers or delegate zones to Cloudflare.
- Origin hardening plan: origins must not be directly reachable (that's the bypass attackers use).
- Defined escalation: who declares a DDoS incident, who can change rules, and vendor support
  contacts (including emergency escalation path).
- Baseline traffic data: normal request rates, geographic distribution, and known-good bots.

## Procedure
1. **Onboard domains correctly.** Change nameservers to Cloudflare (or use CNAME setup where
   required) and ensure all public DNS records are proxied (orange cloud) — DNS-only records expose
   origin IPs directly. Verify with external DNS lookups that no origin IPs leak via unproxied
   records, MX-adjacent hosts, or historical DNS data.
2. **Hide and harden origins.** Firewall origins to accept traffic only from Cloudflare IP ranges
   (published lists, updated automatically); drop everything else. Rotate any previously exposed
   origin IPs if feasible. An exposed origin makes the entire DDoS investment bypassable — verify
   with direct-IP connection attempts.
3. **Enable DDoS managed rules.** Turn on Cloudflare's DDoS protection: network-layer (L3/4)
   rulesets with appropriate sensitivity, and HTTP DDoS managed rules. Start with the recommended
   defaults, then tune sensitivity based on false-positive monitoring — overly aggressive L7 rules
   challenge legitimate users.
4. **Configure rate limiting and Bot Fight Mode.** Add rate-limiting rules for expensive endpoints
   (login, search, API) and enable bot management. During attacks, escalate to "Under Attack Mode"
   (IUAM challenge) per runbook — know in advance which assets get it and the UX tradeoff.
5. **Set up caching and Always Online.** Maximize edge caching for static content (reduces origin
   load during attacks), enable Always Online / cache reserve so the site survives origin failure.
   An attack that can't reach the origin can't exhaust it.
6. **Tune WAF alongside DDoS.** DDoS rules handle volume; WAF rules handle malicious payloads.
   Ensure both are active and tuned (see the cloud WAF playbook) — application-layer attacks often
   combine floods with exploit attempts.
7. **Build monitoring and alerting.** Alert on: DDoS events (Cloudflare analytics + notifications),
   origin error-rate spikes, cache-hit-ratio drops, and traffic anomalies vs. baseline. Ship logs to
   the SIEM for correlation with application incidents.
8. **Write the DDoS runbook.** Define: detection (who notices, how), declaration criteria,
   escalation steps (enable Under Attack Mode, tighten rate limits, engage Cloudflare support,
   notify stakeholders), communication templates (status page, customer comms), and stand-down
   criteria. Include the extortion variant: never pay, engage law enforcement, document everything.
9. **Test before you need it.** Run a controlled load test through Cloudflare (coordinated, within
   terms of service — or use Cloudflare's own testing guidance) to validate: rules engage, origins
   stay healthy, alerts fire, and the runbook works. Tabletop the extortion scenario annually.
10. **Review after every event.** Post-incident: attack vectors and volumes, which rules engaged,
    false positives, time-to-mitigate, and cost impact. Feed learnings into rule tuning and runbook
    updates. Track mitigation effectiveness as the program metric.

## Expected outputs
- All public assets proxied through Cloudflare with origins firewalled to Cloudflare IPs only.
- Tuned DDoS managed rules, rate limiting, and bot management with documented sensitivity choices.
- Caching and resilience configuration reducing origin exposure.
- A written, rehearsed DDoS runbook including the extortion variant.
- Monitoring, alerting, and post-event review process.

## Pitfalls
- Unproxied DNS records: a single gray-cloud record or leaked origin IP (via history, email headers,
  or misconfigured subdomains) lets attackers bypass everything. Audit continuously.
- Origin reachable directly: firewall rules that "allow Cloudflare" but were never tested from
  outside. Test the bypass yourself.
- Under Attack Mode as a permanent setting: it degrades UX and trains users to distrust challenges.
  Use per-runbook during events, then stand down.
- No runbook: the first real attack is the wrong time to figure out who can enable mitigations and
  what to tell customers.
- Ignoring L7 during L3/4 focus: volumetric protection doesn't stop slowloris-style or
  expensive-query application attacks. Both layers, always.

## References
- Cloudflare documentation (DDoS protection, rate limiting, Under Attack Mode, origin protection)
- NIST SP 800-53 SC-5 (denial of service protection)
- CISA guidance on DDoS mitigation and response
- MITRE ATT&CK T1498 (Network Denial of Service)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
