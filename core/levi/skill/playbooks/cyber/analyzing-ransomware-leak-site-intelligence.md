# Analyzing Ransomware Leak Site Intelligence

## Purpose

Collect and analyze ransomware data-leak site (DLS) postings about victim organizations — safely and legally — to assess exposure, track actor claims, and support victim notification and incident response.

## When to use

- You suspect or know an organization is a ransomware victim and need to confirm whether data was published.
- Threat-intel monitoring: tracking which actors are active and which sectors they target.
- Supporting breach-notification decisions with evidence of what was leaked.

## Prerequisites

- Written authorization and a defined intelligence requirement — do not browse leak sites recreationally.
- Isolated research environment: Tor Browser or equivalent in a VM with no organizational identifiers, no logins, and screenshots disabled by policy where required.
- Legal review: accessing victim data may have jurisdictional implications; downloading victim data is generally out of scope — collect metadata and indicators, not the stolen data itself.
- OPSEC: never interact with the actors (no messages, no payments, no registration with real details).

## Procedure

1. Define the requirement in writing: which organization(s), which actors, what questions (listed? data published? countdown active?).
2. Set up the research VM: fresh Tor Browser, no persistent identity, VPN-before-Tor per your org's policy, and a note-taking method that does not sync to corporate cloud.
3. Locate the actor's current leak site via your threat-intel feeds — onion addresses rotate; do not trust search-engine results at face value.
4. Verify the site's authenticity: compare PGP signatures or known design/listing formats against prior captures; clone sites exist.
5. Search for the victim: organization name variants, domain names, and known aliases. Record listing title, claimed data volume, data categories claimed, countdown timers, and sample-file descriptions — never download the samples.
6. Capture the listing page (screenshot/saved HTML) with timestamp and the onion address used; hash the capture for the case file.
7. Assess credibility: cross-check the claimed breach date against the victim's incident timeline; check whether the actor has a history of false or recycled claims.
8. Monitor for changes on a schedule: new victims added, countdowns expiring, listings removed (often means payment or negotiation — do not assume which).
9. Extract shareable intelligence: actor TTPs visible on the site, victimology (sectors, regions, sizes), and any infrastructure indicators in the site's own hosting.
10. Correlate with internal telemetry: if the victim is your organization, match claimed data categories against DLP/exfiltration findings from the network investigation.
11. Check for victim-data reuse: set up alerts on unique descriptive strings from the listing (not the data itself) to catch secondary extortion or fraud using the leaked material.
12. Record the actor's claimed initial-access vector when stated — leak-site posts sometimes name it, which informs defensive priorities.
13. Maintain a leak-site monitoring log: date, actor, victims added/removed, notes — trends beat one-off checks.
14. Produce the intelligence brief: what is claimed, evidence quality, recommended actions (notification, credential rotation for exposed accounts, monitoring for leaked data reuse).
15. Retain captures per policy; do not redistribute victim data or full listing contents beyond the authorized audience.

## Key tools & commands

- Tor Browser in an isolated VM — anonymous access to onion leak sites.
- Threat-intel platforms/feeds — actor tracking and onion-address verification.
- Screenshot/HTML capture with timestamps and hashes — evidence preservation.
- PGP verification tools — authenticating actor communications where signatures exist.
- Onion search engines (e.g., Ahmia) — locating current leak-site addresses, with OPSEC caveats.
- Offline note-taking — no cloud-synced notes for sensitive collection.
- Monitoring log (case file) — tracking listing changes over time.
- Your SIEM/EDR — correlating claimed breach dates with internal telemetry.

## Expected outputs

- Intelligence requirement and authorization record.
- Listing captures (screenshot/HTML) with hashes, timestamps, and source onion addresses.
- Claim assessment: data categories, volume claimed, countdown status, credibility rating.
- Correlation notes vs. internal incident timeline (for victim orgs).
- Leak-site monitoring log: date, actor, victims added/removed, notes.
- Intelligence brief with recommended actions.

## Pitfalls

- Downloading victim data "for analysis" — legal and ethical exposure; collect metadata, not content.
- Interacting with actors or attempting negotiation from the research environment.
- Treating every listing as truthful — false claims and recycled leaks are common.
- Poor OPSEC: accessing leak sites from corporate IPs or with organizational identifiers.
- Sharing victim data beyond the authorized audience.
- Stale onion addresses leading to phishing clone sites — verify addresses via intel feeds.
- Clone sites harvesting researcher IPs — confirm site authenticity before browsing.
- Countdown-timer pressure distorting assessments — timers are a negotiation tactic.

See also: analyzing-ransomware-payment-wallets.md

## References

- MITRE ATT&CK T1486 (Data Encrypted for Impact), T1567 (Exfiltration Over Web Service — double-extortion context)
- CISA #StopRansomware guidance: https://www.cisa.gov/stopransomware
- FBI IC3 ransomware reporting guidance

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
