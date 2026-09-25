---
skill_id: cyber_deploying_honeytokens_and_canarytokens
name: Deploying Honeytokens and Canarytokens
description: Deploy a layered honeytoken program — fake credentials, documents, and infrastructure beacons — for early breach detection.
risk: low
permissions: []
requires_confirmation: false
tags: [deception, detection, monitoring]
version: 1.0.0
---
## Purpose

Build a program of honeytokens (fake credentials, files, database records) and canary tokens (beaconing tripwires) across the environment so that attacker reconnaissance, lateral movement, and exfiltration each have a chance to trip a high-fidelity alarm. Any interaction is malicious by definition — that's what makes the signal clean.

## When to use

- Adding early-warning detection with minimal cost and no agent deployment.
- Detecting insider misuse and compromised credentials (tokens catch both).
- Validating that monitoring and alerting actually work end-to-end.
- Environments where you need detection coverage quickly while bigger projects (EDR rollout, SIEM tuning) mature.

## Prerequisites

- Written authorization to plant deceptive artifacts in production systems.
- An alerting destination (SIEM, email-to-SOC, webhook) with a defined SLA for token triggers.
- An inventory of where tokens live, with owners — tokens are production artifacts with a lifecycle.
- A canary-token service or self-hosted beacon infrastructure (unique URLs, DNS beacons, fake AWS keys).

## Procedure

1. **Design a token matrix.** Plan tokens for each attacker phase: reconnaissance (fake entries in internal wikis, decoy hostnames in DNS), credential access (fake AWS keys in a decoy repo, fake VPN credentials in a "leaked" config), lateral movement (fake RDP/SSH credentials, decoy service accounts), and exfiltration (canary documents with beacon URLs, fake database records). Coverage across phases beats depth in one.
2. **Deploy canary tokens for external beaconing.** Generate tokens that phone home when used: unique URLs embedded in documents, DNS canary hostnames, fake AWS access keys that alert on `sts:GetCallerIdentity` attempts, and webhook tokens in config files. Place them where attackers look — decoy S3 buckets, fake code repositories, internal documentation, and file shares.
3. **Plant honeytokens in identity systems.** Create fake user accounts with monitored logon alerting, plant fake credentials in password-manager-adjacent locations attackers check (never in the real vault), and add decoy entries to internal directories. Coordinate with the identity team so tokens don't break provisioning or audits.
4. **Seed honeytokens in data stores.** Insert fake customer/employee records (clearly synthetic, flagged internally) into production-shaped databases and CRM exports. Any access to these records outside the security team's tests indicates unauthorized data access — by an outsider or an insider.
5. **Wire every token to an alert.** Each token type gets a specific alert: canary-token service webhooks → SOC channel, fake-account logons → SIEM high-severity, decoy-record access → DLP/SIEM alert. Include token identity, timestamp, and source in the alert payload so triage starts immediately.
6. **Test the full chain per token.** Trigger each token type from an isolated host and verify the alert arrives within the SLA with correct context. Record test results; re-test after SIEM, email, or network changes. An untested token is a hope, not a control.
7. **Govern the program.** Maintain the token inventory (type, location, owner, creation date, last test), rotate credential-type tokens quarterly, and review plausibility — tokens must keep matching your real naming and data conventions. Retire tokens that become widely known internally.

## Expected outputs

- A token matrix covering recon, credential access, lateral movement, and exfiltration, with an owner per token.
- Tested alert paths for every token type with defined SLAs.
- A governed inventory with quarterly rotation and plausibility reviews.

## Pitfalls

- Tokens nobody monitors — the most common failure; the alert path matters more than the token.
- Real data or real access in tokens — synthetic only, least-privilege only.
- Alerting the whole org about token locations — insiders route around them and the signal dies.
- Token sprawl with no inventory — forgotten tokens fire during incidents and waste triage time, or rot silently.
- Treating a token trigger as low priority — by design it's one of your highest-fidelity signals.

## References

- MITRE Engage (engage.mitre.org) — deception planning framework
- NIST SP 800-53 SC-26 (honeypots) and SI-4 (system monitoring)
- Canary-token service documentation for token types and webhook integration
- SANS / deception-community guidance on honeytoken program design
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
