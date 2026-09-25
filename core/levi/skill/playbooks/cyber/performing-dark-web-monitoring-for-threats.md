---
skill_id: cyber_performing_dark_web_monitoring_for_threats
name: Dark Web Monitoring for Threats
description: Monitor dark web sources for leaked credentials, stolen data, and threats targeting your organization.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intel, monitoring]
version: 1.0.0
---

## Purpose

Credentials, customer databases, initial-access listings, and ransomware victim announcements surface on dark web forums and marketplaces — often weeks before the victim knows. Dark web monitoring is the defensive practice of collecting from these sources (directly or via a vendor), matching findings against your assets and identities, and acting on hits: forcing password resets, hunting for the intrusion that produced the leak, and preparing for extortion. This playbook covers building the capability with proper legal and operational safeguards.

## When to use

- Standing threat-intel collection for credential and data-leak detection.
- After a suspected breach, to determine whether stolen data is being traded.
- Monitoring for your executives, VIPs, and critical third parties as impersonation targets.
- Ransomware preparedness: early warning that your organization appears on a leak site.
- Validating the effectiveness of your credential policies (are corporate emails appearing in combo lists?).

## Prerequisites

- Legal and policy approval defining what may be collected, accessed, and retained — dark web sources contain stolen data and illicit content; set boundaries before analysts browse.
- Operational security for collection: isolated infrastructure, no attribution to your organization, and analyst safety procedures.
- A collection approach: commercial dark-web monitoring vendor, in-house Tor-based collection, or (most commonly) a hybrid.
- Watchlists: corporate email domains, executive names, product/codename keywords, critical vendor names, and infrastructure identifiers.
- Response runbooks for hit types: credential leaks, data dumps, access-for-sale listings, and leak-site postings.

## Procedure

1. **Define scope and rules of engagement.** Document which sources are in scope, what analysts may download (prefer metadata and samples over full dumps), retention limits, and escalation paths. Prohibit interaction with threat actors (no purchases, no forum engagement) without explicit legal authorization.
2. **Establish collection.** Configure vendor feeds and/or in-house collection covering: credential combo lists and stealer logs, marketplace listings for access/data, ransomware leak sites, and relevant forums. Normalize collection into a searchable repository with source and date attribution.
3. **Match against your watchlists.** Automate matching of collected credentials (email domains, usernames) and keywords against your identity inventory and asset lists. Stealer-log entries tying a corporate email to a plaintext password are the highest-value automated hit.
4. **Triage hits by type.** Credential leaks → force password resets and review for session-token theft (stealer logs often include cookies that bypass MFA). Data dumps → verify authenticity via sample records, then scope the breach that produced them. Access-for-sale → hunt immediately for the intrusion. Leak-site posting → activate the ransomware/extortion playbook.
5. **Hunt for the source intrusion.** A leaked dataset implies a past or ongoing compromise: correlate the data's vintage with your logs, look for the exfiltration window, and treat the leak as an incident trigger, not just an intel item.
6. **Act on credential hits fast.** Reset affected passwords, revoke active sessions and tokens, enforce MFA enrollment where missing, and notify affected users with specific guidance (not generic "change your password" — tell them which account and why). Track completion; partial resets leave the attacker options.
7. **Prepare for extortion scenarios.** If your organization appears on a leak site, engage legal and executive leadership per the extortion playbook: do not negotiate without counsel, preserve evidence, and coordinate public communications. Dark web monitoring's value here is early warning, not prevention.
8. **Measure and tune.** Track time-from-posting to detection, hit actionability rate, and false-positive sources. Tune watchlists and matching rules quarterly; stale keywords produce noise that buries real hits.

## Expected outputs

- Documented collection scope, legal boundaries, and analyst safety procedures.
- Automated watchlist matching against collected dark web data.
- Triage and response records per hit type, with actions taken.
- Credential-reset and session-revocation completion tracking.
- Program metrics: detection latency, actionability rate, and coverage gaps.

## Pitfalls

- Analysts browsing dark web sources without OPSEC — attribution to your organization invites targeting.
- Downloading and retaining full stolen datasets without legal review; prefer verification samples and strict retention.
- Treating vendor coverage as complete — no source sees everything; layer vendors and targeted collection.
- Acting on unverified "data dumps" that turn out to be recycled or fabricated; verify before declaring a breach.
- Resetting passwords without revoking sessions and tokens — stealer-log cookies keep the attacker in.

## References

- CISA guidance on credential theft and passwordless/MFA adoption
- NIST SP 800-63B on memorized secrets and breach-corpus checking
- "Have I Been Pwned" k-anonymity model as a reference for safe breach-data querying
- SANS threat-intel guidance on collection management and legal considerations
- Ransomware leak-site monitoring references from CISA's #StopRansomware guide
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
