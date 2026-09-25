---
skill_id: cyber_tracking_threat_actor_infrastructure
name: Tracking Threat Actor Infrastructure
description: Passively track adversary infrastructure with DNS, WHOIS, certificate, and hosting pivots for defensive intel.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intel, infrastructure, tracking]
version: 1.0.0
---
## Purpose
Knowing an adversary's infrastructure lets defenders block, hunt, and anticipate. This playbook covers passive infrastructure tracking for defensive intelligence: pivoting from known indicators through passive DNS, WHOIS, certificate transparency, and hosting patterns. All collection is passive; active engagement with adversary infrastructure is out of scope and an operational risk.

## When to use
- Enriching an investigation with infrastructure context.
- Proactive blocking: turning one indicator into a cluster for firewall/DNS blocks.
- Attribution support through infrastructure overlaps.
- Monitoring for infrastructure reuse indicating a returning actor.

## Prerequisites
- Seed indicators from investigations or trusted intel (domains, IPs, hashes, certificates).
- Access to passive DNS, WHOIS history, and certificate transparency data.
- Analytic environment separated from production networks.
- Handling rules for sensitive sources and TLP markings.

## Procedure
1. Start from validated seed indicators; record their first-seen dates and sources.
2. Pivot on passive DNS: other domains resolving to the same IPs, and IP history of the seed domains.
3. Pivot on WHOIS: shared registrant emails, creation patterns, and privacy-service usage.
4. Pivot on certificates: certificate transparency logs for same-subject or same-organization certificates.
5. Pivot on hosting: ASNs, netblocks, and server banners/fingerprints (JA3, favicon hashes) shared across nodes.
6. Cluster related infrastructure; assign confidence and note which pivots are strong vs weak.
7. Convert high-confidence clusters into blocks, detections, and hunt queries; monitor for new nodes.
8. Maintain operational security: use dedicated analytic infrastructure and avoid tipping off the actor.
9. Set up automated certificate-transparency alerts for patterns matching the actor.
10. Re-validate cluster confidence monthly; infrastructure churns and pivots decay.
11. Share sanitized clusters with trusted peers to corroborate and extend coverage.

## Expected outputs
- Infrastructure cluster map with pivot evidence and confidence per node.
- Blocklists and hunt queries derived from clusters.
- Monitoring for cluster expansion.
- CT-log monitoring rules for actor patterns.
- Monthly cluster re-validation log.
- Peer-shared sanitized cluster reports.

## Pitfalls
- Shared hosting and CDNs create false clusters; require multiple independent pivots.
- Active probing of adversary infrastructure can alert them and may be unlawful; stay passive.
- WHOIS privacy and GDPR redaction limit registrant pivots; adjust expectations.
- Infrastructure churns fast; timestamp everything and expire stale clusters.
- Fast-flux and bulletproof hosting defeat IP blocking quickly; prefer domain and behavior blocks.
- Blocking too broadly on shared infrastructure causes collateral damage; scope carefully.
- Analyst attribution bias can force weak pivots into a cluster; require independent corroboration.
- Passive collection still leaves traces in some services; use dedicated infrastructure for all pivots.

## References
- NIST SP 800-150, Guide to Cyber Threat Information Sharing.
- SANS FOR578 cyber threat intelligence concepts.
- MITRE ATT&CK: infrastructure mapping within technique context.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
