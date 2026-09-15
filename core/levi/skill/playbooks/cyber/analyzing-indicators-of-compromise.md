# Analyzing Indicators of Compromise

## Purpose

Indicators of Compromise (IOCs) — IPs, domains, URLs, hashes, mutexes, registry
keys — are the atomic facts of an intrusion. This playbook covers the full IOC
lifecycle: extracting them from evidence, validating and de-duplicating them,
scoring confidence, hunting for them across the estate, and sharing them in
standard formats. Good IOC work turns one incident into fleet-wide visibility.

## When to use

- During or after any incident: extract IOCs from malware, logs, and memory.
- Proactive threat hunting using externally sourced IOC feeds.
- Building or tuning blocklists, SIEM correlation rules, and EDR hunts.

See also: automating-ioc-enrichment.md

## Prerequisites

- Written authorization for the investigation and for any active hunting that
  touches user systems; define the time window and data sources up front.
- Evidence handled with chain of custody (hashes, sources, timestamps) so IOCs
  are traceable to the artifact they came from.
- A case/tracking system to record IOC disposition — never manage IOCs in
  chat threads or spreadsheets alone.

## Procedure

1. Extract candidate IOCs from each evidence source:
   - Malware/configs: C2 IPs, domains, URLs, mutexes, file paths, hashes.
   - Logs: external IPs in firewall/proxy/DNS logs, suspicious domains.
   - Memory/disk: injected process names, registry keys, scheduled tasks.
2. Normalize every IOC: lowercase domains, strip URL parameters that are
   session-specific, expand shorteners, and resolve domains to IPs with a
   timestamp (resolutions change; record when you looked).
3. De-duplicate and validate:
   - Hashes: confirm they belong to the malicious file, not a benign library.
   - IPs: check whether it is shared infrastructure (CDN, cloud provider) —
     blocking a Cloudflare IP is not a containment plan.
   - Domains: check age, registrar, and whether the domain is compromised-
     legitimate vs. attacker-registered.
4. Score confidence per IOC (high/medium/low) with a one-line justification
   and an expiry: C2 IPs decay in days, file hashes last longer.
5. Enrich selectively: passive DNS, WHOIS, sandbox verdicts, and internal
   history ("have we seen this before?"). Record enrichment sources.
6. Hunt the estate: search SIEM/EDR for each high/medium IOC across the full
   retention window — not just the incident timeframe — to find additional
   affected hosts.
7. Convert validated IOCs into controls: firewall blocks, DNS sinkholes,
   proxy denylists, EDR indicators, SIEM correlation rules. Prefer narrow,
   high-confidence IOCs for automated blocking; keep low-confidence ones for
   hunting only.
8. Share in standard formats: MISP events, STIX 2.1 bundles, or simple
   CSV/JSON with type, value, confidence, first/last seen, and source.
9. Retire IOCs on schedule: review and expire them; stale IOCs cause false
   positives and erode trust in the feed.

## Key tools & commands

- MISP (misp-project.org) — IOC storage, correlation, and sharing.
- `dig`, `nslookup`, `whois` — manual DNS/registration checks with timestamps.
- VirusTotal / abuse.ch (URLhaus, MalwareBazaar, ThreatFox) — hash, URL, and
  IP reputation and context.
- Passive DNS (your provider of choice) — historical resolutions.
- SIEM/EDR hunt queries — estate-wide searching; keep queries IOC-typed
  (hash vs. domain vs. IP need different fields).
- `yara` — converting file/hash IOCs into content-based detections that
  survive trivial hash changes.

## Expected outputs

- A validated IOC table: type, value, confidence, expiry, source artifact,
  first/last seen.
- Hunt results: additional affected hosts (or confirmed absence).
- Deployed controls (blocks, rules) with change records.
- Shared package (MISP event / STIX bundle) for partners or the community.

## Pitfalls

- Treating every extracted string as an IOC — unvalidated IOCs become false
  positives that burn analyst trust.
- Blocking shared infrastructure (CDNs, DNS providers, cloud IPs) based on a
  single sighting; always check for shared use first.
- Forgetting expiry: a C2 IP reassigned to a benign customer six months later
  will page someone at 3 a.m.
- Hunting only the incident window — attackers dwell for months; search full
  retention.
- Sharing IOCs without confidence scores or context, which makes them useless
  (or harmful) to recipients.

## References

- MITRE ATT&CK (technique pages list the IOC-relevant artifacts per technique)
- MISP documentation (misp-project.org); STIX 2.1 / TAXII 2.1 specs (OASIS)
- NIST SP 800-150, Guide to Cyber Threat Information Sharing
- abuse.ch project docs (urlhaus.abuse.ch, bazaar.abuse.ch, threatfox.abuse.ch)

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
