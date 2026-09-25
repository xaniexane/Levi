---
skill_id: cyber_building_adversary_infrastructure_tracking_system
name: Building an Adversary Infrastructure Tracking System
description: Track adversary infrastructure: passive DNS, certificates, and pivoting.
risk: low
permissions: [network.read]
requires_confirmation: false
tags: [threat-intel]
version: 1.0.0
---
# Building an Adversary Infrastructure Tracking System

## Purpose

Build a defensive system that tracks adversary infrastructure — domains, IPs, ASNs,
certificates, and hosting patterns associated with threat actors — so the SOC can detect
new attacker assets early, attribute campaigns, and block infrastructure before it's
weaponized.

## When to use

- Standing up a threat-intel capability focused on actor tracking (not just IOC feeds).
- Supporting incident response with infrastructure pivoting ("what else does this actor
  own?").
- Proactive defense: detecting lookalike domains or fresh phishing infrastructure aimed
  at your organization.
- Maturing from reactive IOC blocking to pattern-based actor detection.

## Prerequisites

- Written authorization defining what may be actively probed — default to passive data
  sources (CT logs, passive DNS, WHOIS history); active scanning of suspected adversary
  assets needs explicit approval.
- API access to passive DNS, WHOIS history, and CT data sources; budget for commercial
  feeds if free tiers prove insufficient.
- A defined actor-prioritization list — track the actors that actually target your sector
  first; tracking everyone tracks no one.
- Storage for historical data (even a modest tracker accumulates millions of DNS records).

## Procedure

1. **Define the tracking model.**
   - Decide the entities: domains, IPs, CIDRs, ASNs, certificates, name servers, WHOIS
     registrant fingerprints, and favicon/TLS fingerprints where useful.
   - Define relationships (domain→IP, IP→ASN, domain→cert) and the actor-attribution
     model (confidence levels, never single-source attribution).

2. **Seed from known reporting.**
   - Ingest infrastructure from CTI reports, prior incidents, and trusted sharing
     communities for your priority actors.
   - Normalize and tag every seed with source and confidence — seeds of unknown quality
     poison the whole tracker.

3. **Build passive collectors.**
   - Certificate Transparency feed filtered on actor patterns (issuer habits, SAN
     structures, lookalike keywords).
   - Passive DNS for resolution history of seed domains/IPs; WHOIS for registration
     patterns (registrar, creation cadence, name server reuse).
   - Schedule collection (hourly/daily depending on actor tempo) and store raw plus
     normalized forms.

4. **Implement pivoting rules.**
   - Encode the pivots analysts actually use: shared ASN + temporal clustering, reused
     name servers, certificate SAN overlap, WHOIS registrant reuse, identical
     page/TLS fingerprints.
   - Each pivot produces a candidate with a score and the evidence chain — analysts
     confirm, the system never auto-attributes.

5. **Add organization-specific tripwires.**
   - Watch for lookalike domains of your brands (typosquat permutations), certificates
     issued for your domains from unexpected CAs, and new infrastructure reusing your
     incident-derived fingerprints.
   - These tripwires are the highest-value output: they detect targeting *of you*.

6. **Build the analyst workflow.**
   - Queue candidates for review with full evidence (timeline, pivots, raw records);
     one-click promote to tracked-actor infrastructure or dismiss with a reason.
   - Dismissals tune the scoring — feed them back, or the queue fills with the same
     false positives.

7. **Publish to defenses.**
   - Export confirmed actor infrastructure as blocklists/watchlists to firewall, proxy,
     DNS filtering, and the SIEM (with expiry — infrastructure churns).
   - Publish internal actor profiles: infrastructure patterns, tempo, and TTPs for hunt
     teams.

8. **Maintain and age out.**
   - Re-validate tracked infrastructure periodically; sinkholed, reassigned, or dormant
     assets age out automatically.
   - Review actor priorities quarterly — threat landscapes shift, and stale priorities
     waste collection budget.

## Key tools & commands

- crt.sh / certstream — CT-based infrastructure discovery.
- Passive DNS: VirusTotal, SecurityTrails, or team Cymru-style feeds (pick per budget).
- WHOIS history: commercial WHOIS APIs; `whois` CLI for spot checks.
- Python (requests, dnspython) collectors → Postgres/SQLite store → simple web UI or
  notebook for analyst review.
- MISP / OpenCTI — publish confirmed infrastructure as events/indicators for sharing.

## Expected outputs

- Tracker database: entities, relationships, attribution confidence, history.
- Analyst review queue with evidence chains and disposition log.
- Blocklist/watchlist feeds consumed by network defenses, with expiry.
- Actor infrastructure profiles for hunt teams.

## Pitfalls

- Active probing of suspected adversary infrastructure without authorization — it tips
  off the actor and may violate policy; stay passive by default.
- Single-pivot attribution (one shared ASN = same actor) — infrastructure is shared,
  resold, and coincidental; require converging evidence.
- Never expiring tracked assets — stale infrastructure in blocklists causes false
  positives and erodes trust in the feed.
- Tracking too many actors — depth on priority actors beats shallow coverage of dozens.

## References

- MITRE ATT&CK: T1583 (Acquire Infrastructure), T1584 (Compromise Infrastructure), T1598
  (Phishing for Information).
- NIST SP 800-150 (Guide to Cyber Threat Information Sharing).
- SANS / public CTI methodology writings on infrastructure pivoting and diamond-model
  analysis.
- crt.sh, certstream, and passive DNS provider documentation.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
