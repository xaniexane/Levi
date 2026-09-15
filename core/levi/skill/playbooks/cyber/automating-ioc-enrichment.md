# Automating IOC Enrichment

## Purpose

Build an automated pipeline that takes raw indicators of compromise (IPs, domains, URLs,
file hashes, email addresses) and enriches them with reputation, geolocation, passive DNS,
WHOIS, and sandbox verdicts — turning a bare IOC list into triaged, context-rich
intelligence analysts can act on.

## When to use

- SOC triage: enriching IOCs from alerts, phishing reports, or threat intel feeds before
  analyst review.
- Incident response: rapidly contextualizing indicators found on compromised hosts.
- Threat intel production: normalizing and scoring feed data before ingestion into the
  SIEM or TIP.
- Retro-hunting: re-enriching historical IOCs when new context becomes available.

See also: analyzing-indicators-of-compromise.md

## Prerequisites

- Written authorization if enrichment queries touch third-party infrastructure beyond
  public APIs (most enrichment is passive API lookups — define what's in scope).
- API keys for the chosen enrichment sources, stored in a secrets manager (never in code
  or logs).
- A normalizer: every source returns different schemas, so plan a canonical IOC record
  format up front (type, value, first/last seen, sources, verdicts, confidence).
- Rate-limit and cost budget: commercial APIs bill per query — design caching first.

## Procedure

1. **Define the canonical IOC record.**
   - Fields: `type`, `value` (normalized — lowercase domains, defanged display form kept
     separate), `first_seen`, `last_seen`, `sources[]`, `verdicts{}` per source,
     `confidence`, `tags[]`.
   - Normalization rules prevent the same indicator enriching twice under different
     spellings.

2. **Build the ingestion layer.**
   - Accept IOCs from files (CSV/JSON), MISP events, SIEM exports, or a message queue;
     validate type against a strict allowlist (ipv4, domain, url, md5/sha1/sha256,
     email).
   - Deduplicate on `(type, normalized value)` before any API call — duplicates are the
     main cost driver.

3. **Add a caching layer.**
   - Cache enrichment results (SQLite/Postgres/Redis) with per-source TTLs (reputation
     data goes stale; 24h is a common default, shorter for fast-flux infrastructure).
   - Serve repeats from cache; log cache hit rate as a pipeline health metric.

4. **Integrate reputation sources.**
   - Query in parallel with timeouts and retries: VirusTotal v3 API (file/URL/IP/domain
     reports), AbuseIPDB (IP check), GreyNoise (IP classification — internet-scanner
     noise vs. targeted), urlscan.io (URL/DOM scan history).
   - Record each source's raw verdict plus a normalized score; never let one source
     decide alone.

5. **Add infrastructure context.**
   - Passive DNS (which domains resolved to this IP, what IPs this domain used),
     WHOIS/creation dates (domains registered in the last 30 days score higher risk),
     and ASN/geolocation.
   - Newly registered domains resolving to bulletproof-hosting ASNs are a classic
     high-confidence pattern — encode it as a rule, not analyst folklore.

6. **Add sandbox/malware context for hashes.**
   - Query malware repositories/sandboxes for hash verdicts, family labels, and related
     samples; link hashes to the URLs/IPs in the same incident for pivoting.
   - Handle "unknown hash" gracefully — absence of a verdict is information, not failure.

7. **Score and prioritize.**
   - Compute a composite score from source verdicts, infrastructure signals, and age;
     output tiers (e.g., block / monitor / informational) mapped to SOC actions.
   - Make the scoring explainable: every tier assignment must list the contributing
     signals so analysts can override confidently.

8. **Emit to consumers.**
   - Write enriched records to the SIEM/TIP (MISP, OpenCTI), a blocklist feed for the
     firewall/proxy, and a human-readable triage view.
   - Include expiry: enrichment-driven blocks must age out, or the blocklist becomes
     permanent noise.

9. **Monitor pipeline health.**
   - Track API error rates, quota consumption, cache hit rate, enrichment latency, and
     the fraction of IOCs reaching each tier.
   - Alert on source outages — silent enrichment failure looks like "no threats found."

## Key tools & commands

- Python `requests`/`httpx` with per-source client modules, timeouts, and retry/backoff.
- VirusTotal API v3 (`/ip_addresses/`, `/domains/`, `/files/`, `/urls/`), AbuseIPDB
  `/api/v2/check`, GreyNoise IP lookup, urlscan.io search API — all keyed, all rate-limited.
- MISP REST API / PyMISP for ingestion and publishing; OpenCTI connectors as an
  alternative.
- `sqlite3`/Postgres for the cache; Redis if the SOC needs sub-second repeat lookups.
- `cron`/systemd timers or a small queue worker (Celery/RQ) for scheduling; keep it
  boring and observable.

## Expected outputs

- Enriched IOC records in the canonical schema with per-source verdicts and composite
  tier.
- Block/monitor feeds consumed by firewall, proxy, and EDR.
- Pipeline health dashboard (latency, quota, error rate, tier distribution).
- Runbook: adding a new source, tuning scores, handling outages.

## Pitfalls

- No caching — re-querying the same IOCs burns quota and budget within days.
- Single-source verdicts driving blocks — false positives from any one feed will block
  legitimate infrastructure; require corroboration for automated blocking.
- Enrichment as active probing: resolving attacker domains or fetching URLs from the SOC
  network tips off the adversary — prefer passive APIs over direct interaction.
- Stale blocks: an IP that was malicious in January may be reassigned by June — expire
  everything.

## References

- VirusTotal API v3 documentation; AbuseIPDB API documentation; GreyNoise API
  documentation; urlscan.io API documentation.
- MISP documentation (REST API, PyMISP); OpenCTI documentation.
- MITRE ATT&CK: T1598 (Phishing for Information — intel analog), defensive mapping to
  detection workflow rather than a single technique.
- NIST SP 800-150 (Guide to Cyber Threat Information Sharing).

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
