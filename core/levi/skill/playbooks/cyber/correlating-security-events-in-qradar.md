---
skill_id: cyber_correlating_security_events_in_qradar
name: Correlating Security Events in QRadar
description: Build QRadar correlation rules, offenses, and reference sets that turn raw events into prioritized investigations.
risk: info
permissions: []
requires_confirmation: false
tags: [siem, correlation, soc]
version: 1.0.0
---
## Purpose

Make IBM QRadar produce offenses worth investigating: normalized event taxonomy, correlation rules tied to the kill chain, tuned thresholds, and reference sets that enrich automatically — instead of a firehose of unprioritized events.

## When to use

- Deploying or re-tuning QRadar for a SOC that is drowning in low-value offenses.
- Building detection coverage for specific attack techniques (lateral movement, data staging, C2).
- Onboarding new log sources where DSM parsing and event mapping need validation.
- Reducing offense volume through correlation rather than blind suppression.

## Prerequisites

- QRadar admin or content-management access and a staging/testing environment for rule validation.
- Log sources onboarded with correct DSMs and verified event mapping (QID, category, credibility).
- Network hierarchy configured (servers, DMZ, user networks) — many rules depend on it.
- Baseline event volumes per log source to set sane thresholds.

## Procedure

1. **Validate parsing before writing rules.** For each new log source, confirm events arrive with correct QIDs, low/high-level categories, and parsed fields (source/destination IP, username). A correlation rule on broken parsing is a silent failure — run test searches and verify field extraction first.
2. **Design rules around the kill chain, not single events.** Write building blocks and rules that chain: e.g. "successful VPN login from new ASN" followed by "first-time RDP to server segment" followed by "large outbound transfer" within 4 hours → one high-magnitude offense. Single-event rules create noise; chained rules create cases.
3. **Use reference sets for statefulness.** Populate reference sets with watchlists (known-bad IOCs, VIP users, crown-jewel assets, approved scanner IPs) and reference them in rules via "is in reference set" tests. Automate IOC ingestion from threat intel with expiry so stale indicators age out.
4. **Tune thresholds with data, not guesses.** For each threshold rule (e.g. failed logons), measure the 95th percentile of normal activity per source type and set the threshold above it; document the basis. Review offense-to-true-positive ratios monthly and adjust — a rule with a 99% false-positive rate is a broken rule, not a detection.
5. **Set offense magnitude deliberately.** Configure magnitude contributions (relevance, severity, credibility) so chained, high-confidence detections score high and single low-confidence events stay low. Analysts should work offenses in magnitude order without needing a cheat sheet.
6. **Build custom properties for huntable fields.** Extract custom event properties for fields QRadar doesn't parse natively (command lines, process names, URL paths) and make them searchable/indexed. These properties are what make rules reusable across log sources.
7. **Test rules safely.** Use the rule wizard's test with historical events and a "test mode" deployment that logs matches without creating offenses. Let rules run in test mode for one to two weeks, review matches, then promote. Never deploy an untested rule directly to offense creation.
8. **Maintain a rule lifecycle.** Quarterly review: disable rules with zero matches over 90 days, document every disabled rule's rationale, version-control rule exports, and map active rules to MITRE ATT&CK for coverage reporting to leadership.

## Expected outputs

- A validated log-source inventory with correct DSM parsing and event mapping.
- Kill-chain correlation rules with documented thresholds, test-mode history, and magnitude tuning.
- Reference sets with automated IOC ingestion/expiry; quarterly rule-lifecycle reviews.

## Pitfalls

- Single-event rules for everything — offense volume explodes and analysts ignore the console.
- Rules on unvalidated parsing — they silently never fire, and nobody notices until the incident review.
- Thresholds copied from blog posts without measuring your own baseline.
- Reference sets that never expire — stale IOCs generate noise and false confidence.
- Editing rules directly in production without test mode — one bad regex can suppress real detections.

## References

- IBM QRadar documentation — custom rules, building blocks, reference sets, DSM guide
- MITRE ATT&CK — technique mapping for rule coverage tracking
- NIST SP 800-92 (Guide to Computer Security Log Management)
- SANS SIEM/detection engineering resources for correlation design patterns
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
