---
skill_id: cyber_analyzing_threat_intelligence_feeds
name: Analyzing Threat Intelligence Feeds
description: Evaluate and operationalize threat feeds: scoring, aging, and false positives.
risk: low
permissions: [network.read]
requires_confirmation: false
tags: [threat-intel]
version: 1.0.0
---
# Analyzing Threat Intelligence Feeds

See also: analyzing-threat-landscape-with-misp.md

## Purpose

Turn raw threat-intelligence feeds — commercial, open-source, and government — into trusted,
deduplicated, actionable indicators for your defenses. This playbook covers feed selection,
ingestion, normalization, scoring, and operationalization: getting the right IOCs into the right
controls with an expiration date, not a bigger haystack.

The program-level goal is measurable defensive value per feed. Every feed should justify its cost
(money, engineering time, alert volume) in attacks blocked or detections enabled — if it can't, it
gets cut.

## When to use

- Standing up or rationalizing a threat-intel program: deciding which feeds to pay for, keep, or
  drop.
- Tuning detection and blocking: feeding IPs, domains, hashes, and URLs into firewalls, proxies,
  EDR, and SIEM with confidence tiers.
- Evaluating a new feed's quality before committing budget or engineering time.
- Post-incident: rapidly ingesting actor-specific IOCs and pushing them to controls.
- Annual budget review: defending (or cutting) intel spend with data.

## Prerequisites

- Written authorization from security leadership for the intel program scope: which feeds may be
  ingested, how intel may be shared externally (TLP rules), and data-retention limits.
- An inventory of your enforcement points (firewall, DNS filter, proxy, EDR, SIEM) and their
  indicator-format requirements and volume limits — a feed your firewall cannot ingest at scale is a
  feed you cannot use.
- Baseline metrics for existing feeds (true-positive rate, overlap, time-to-ingest) if
  rationalizing; otherwise a 30-day evaluation window for new feeds.
- Handling rules for victim-identifying or personal data that may appear in feeds, per your
  jurisdiction.
- A staging environment (or at minimum a staging index/table) where new feeds can be evaluated
  without touching production block lists.

## Procedure

1. Catalog candidate feeds. For each feed record: provider, cost, delivery method (TAXII, API, MISP
   feed, flat file), indicator types, claimed update frequency, TLP/licensing restrictions, and
   geographic/sector relevance to your organization.
2. Evaluate quality before committing. Ingest each candidate for 30 days into a staging store and
   measure: volume per day, deduplication rate against your existing feeds (what fraction is
   genuinely new), overlap between feeds, and — most importantly — true-positive rate against your
   own telemetry (how many indicators actually fired on real malicious activity vs. noise). Drop
   feeds that add volume without novelty.
3. Normalize on ingest. Convert every indicator to a canonical schema: type (ip/domain/url/hash),
   value, first-seen, last-seen, source feed, confidence, TLP, and expiration. Strip duplicates
   across feeds while preserving the source list — one indicator, many sources.
4. Score and tier. Assign each indicator a confidence score from source reliability × corroboration
   × recency. Tier into: block automatically (high confidence, corroborated), alert only (medium),
   and context-only (low — available for investigation, never blocking). Document the thresholds.
5. Set expirations. Every indicator gets a TTL based on type: phishing URLs and malware C2 IPs decay
   in days to weeks; file hashes of commodity malware last longer. Expired indicators leave the
   block lists automatically — stale IOCs are a leading cause of false-positive blocks.
6. Operationalize per control. Push tiers to the right enforcement points in the right format:
   firewall/IP lists, DNS RPZ or filter for domains, proxy categories for URLs, EDR/SIEM watchlists
   for hashes. Verify ingestion counts at each control match what you sent.
7. Measure true-positive contribution per feed. Monthly, join each feed's indicators against
   confirmed-malicious events in your telemetry and compute precision per feed. This is the number
   that defends the budget — or kills the feed.
8. Monitor feed health continuously. Track per-feed: ingestion lag (feed timestamp vs. your
   receipt), parse failures, volume anomalies (a feed going silent or exploding 100x are both
   incidents), and ongoing true-positive contribution. Alert on feed outages like any other control
   failure.
9. Share back where allowed. Contribute your own sightings and validated IOCs to the communities you
   draw from (ISAC, MISP communities), respecting TLP. Feeds improve when consumers contribute; a
   pure-taker posture degrades the commons.
10. Review quarterly. Re-run the quality evaluation: kill feeds whose novelty dropped, renegotiate
    or replace underperformers, and adjust TTLs and thresholds from the quarter's false-positive
    data. Publish a one-page feed scorecard for leadership.

## Key tools & commands

- MISP (or OpenCTI) as the normalization and correlation hub: feeds in, deduplicated attributes out,
  with expiration handled by the platform's decay models.
- TAXII clients (`taxii2-client` in Python) for STIX/TAXII polling: `from taxii2_client.v21 import
  Collection; coll.get_objects()` to pull a collection's indicators.
- `jq` for inspecting feed payloads: `curl -s <feed-url> | jq '.indicators | length'` as a quick
  volume sanity check.
- Your SIEM for true-positive measurement: join feed indicators against proxy/firewall logs over the
  evaluation window and count hits that were confirmed malicious.
- Feed-health dashboards: scheduled queries on ingestion lag and daily volume per feed, alerting on
  silence or spikes.
- Format converters (e.g., simple Python scripts) translating the canonical schema into firewall
  address-group, DNS RPZ zone, and SIEM lookup formats.

## Expected outputs

- A feed catalog with provider, format, cost, TLP, and relevance notes.
- A 30-day evaluation report per candidate feed: volume, novelty rate, overlap, true-positive rate.
- A normalized, deduplicated indicator store with confidence scores, tiers, and TTLs.
- Per-control push configurations with verified ingestion counts.
- Per-feed precision metrics from the monthly true-positive measurement.
- A feed-health monitoring setup with lag/volume alerting.
- Contribution records for shared-back intelligence.
- A quarterly feed scorecard and rationalization decisions.

## Pitfalls

- Buying feeds for volume: ten overlapping feeds give you one feed's value at ten feeds' noise.
  Measure novelty, not count.
- No expiration: IOCs from 2021 still blocking in 2026 generate false positives and erode trust in
  the whole program.
- Auto-blocking low-confidence indicators: one bad auto-block on a CDN IP teaches the business to
  bypass your controls.
- Ignoring TLP/licensing: re-sharing a TLP:RED or commercially licensed feed to a partner can breach
  contract and trust.
- Measuring success by "indicators ingested" instead of "attacks blocked or detected" — the only
  metric that matters.
- Evaluating a feed during an atypical month (major incident, holiday lull) and generalizing — use
  the full 30 days and note anomalies.
- Pushing the same tier to every control: what belongs in the SIEM as context does not belong on the
  firewall as a block.

## References

- NIST SP 800-150 "Guide to Cyber Threat Information Sharing" — sharing models and handling.
- FIRST Traffic Light Protocol (TLP) version 2.0 — handling and re-sharing rules.
- OASIS STIX 2.1 and TAXII 2.1 specifications — the standard feed formats.
- MISP documentation on feed ingestion and decay models.
- SANS threat-intelligence program guidance — feed evaluation criteria.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
