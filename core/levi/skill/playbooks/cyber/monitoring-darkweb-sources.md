---
skill_id: cyber_monitoring_darkweb_sources
name: Monitoring Dark Web Sources (Defensive)
description: Monitor dark web sources for stolen credentials, leaked data, and threats to your organization.
risk: low
permissions: []
requires_confirmation: false
tags: [threat-intelligence, dark-web, monitoring]
version: 1.0.0
---
## Purpose
This playbook establishes defensive dark web monitoring: detecting your organization's leaked credentials, stolen data, and targeted threats in criminal forums and marketplaces — strictly for protecting your own assets, with clear legal and ethical boundaries.

## When to use
- You need early warning of credential dumps or data leaks affecting your organization.
- Supporting incident response: determining whether stolen data is being traded.
- Brand and executive protection against targeted threats.

## Prerequisites
- Legal review of monitoring scope: what may be collected, stored, and acted upon in your jurisdiction.
- A commercial dark-web monitoring service or a controlled collection capability with operational security.
- Playbooks for what happens on a hit: credential resets, fraud monitoring, takedown requests.

## Procedure
1. **Define the watchlist.** Domains, brand terms, executive names, product codenames, and internal identifiers worth monitoring; keep it focused on your assets.
2. **Choose the collection method.** Prefer reputable commercial monitoring services over direct forum engagement, which carries legal and operational risk.
3. **Set handling rules.** Define what gets collected (your data only), retention limits, and who may access raw collected material.
4. **Triage hits fast.** Validate each hit: is it really your data, is it current, what is the blast radius; prioritize live credential dumps and active sale of access.
5. **Respond decisively.** Force password resets for exposed accounts, revoke sessions and tokens, monitor for fraud, and initiate takedown or legal action where viable.
6. **Feed the SOC.** Turn validated hits into detections: alert on logons using exposed credentials, and hunt for the intrusion that produced the leak.
7. **Report trends.** Track hit volume, time-to-detect, and response actions; brief leadership without exposing analysts to unnecessary raw criminal content.

8. **Coordinate with law enforcement.** For significant theft or extortion, engage law enforcement early; they may already track the actor and can advise on engagement risks.
9. **Review collection legality annually.** Laws on data collection vary by jurisdiction and change; re-validate the program's legal basis every year.

## Expected outputs
- Documented watchlist and collection/handling policy with legal sign-off.
- Response runbooks for credential dumps, data leaks, and access sales.
- Metrics: time from leak to detection, accounts remediated, repeat-leak rate.
- Example: a monitoring alert finds 200 corporate credentials in a fresh combo list; within 4 hours all accounts are force-reset, sessions revoked, and the SOC hunts for logons using the exposed passwords.

## Pitfalls
- Collecting or storing criminal content beyond what is needed to protect your assets.
- Direct engagement with threat actors without law enforcement coordination.
- Treating every mention as a crisis; validate before escalating.

- Analysts browsing criminal forums directly from corporate infrastructure, exposing the organization to retaliation and legal risk; use proper operational security.
- Paying for stolen data to "verify" a breach; this funds criminals and rarely produces reliable confirmation.

## References
- CISA guidance on credential exposure response (cisa.gov).
- NIST SP 800-150, Guide to Cyber Threat Information Sharing.
- FBI IC3 (ic3.gov) — reporting internet crime, including extortion.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
