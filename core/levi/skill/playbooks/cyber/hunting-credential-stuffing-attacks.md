---
skill_id: cyber_hunting_credential_stuffing_attacks
name: Hunting Credential Stuffing Attacks
description: Detect credential-stuffing campaigns against authentication endpoints using velocity, reputation, and failure-pattern analysis.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, identity, web]
version: 1.0.0
---
## Purpose

Credential stuffing — replaying breached username/password pairs against
login endpoints at scale — is distinct from brute force (it uses many
usernames, few attempts each) and evades naive lockout policies. This
playbook covers detecting stuffing campaigns in authentication telemetry,
distinguishing them from legitimate traffic, and responding effectively.

## When to use

- Authentication logs show elevated failure rates or unusual login
  velocity.
- Threat intel or breach-notification services report your users'
  credentials in a new combo list.
- After deploying a customer-facing login or API auth endpoint: verify
  stuffing defenses actually work.
- Investigating account-takeover clusters.

## Prerequisites

- Centralized authentication logs: timestamp, username, source IP/ASN,
  user agent, result, and (where available) device fingerprints.
- IP reputation and ASN data; geolocation for impossible-travel checks.
- Baseline login patterns: normal failure rates, peak hours, user-agent
  distribution.
- Coordination with fraud/customer-support teams for victim outreach.

## Procedure

1. **Define the stuffing signature.** Look for the classic pattern: high
   volumes of login attempts spread thinly across many usernames (low
   attempts-per-user, evading lockouts), from rotating IPs or proxy
   infrastructure, with non-browser or scripted user agents and elevated
   failure rates punctuated by occasional successes.
2. **Hunt by velocity and distribution.** Aggregate attempts by source
   IP/ASN, user agent, and time window. Flag ASNs and IP ranges with
   attempt-to-unique-user ratios far above baseline, especially from
   hosting/datacenter ranges rather than residential ISPs.
3. **Hunt by failure patterns.** Identify usernames with failures from
   multiple geographically dispersed IPs in short windows, and IPs with
   high unique-username counts. Correlate successes that follow these
   patterns — those are likely takeovers.
4. **Distinguish from legitimate traffic.** Exclude password-manager
   autofill bursts, corporate NAT egress (many users, one IP), and
   monitoring/health-check logins. Validate against known-good device
   fingerprints before blocking.
5. **Confirm with breach correlation.** Check targeted usernames against
   breach datasets (via a breach-notification service or internal
   telemetry) — stuffing campaigns closely follow fresh combo-list
   releases.
6. **Respond and contain.** Rate-limit or challenge (CAPTCHA, MFA step-
   up) the offending infrastructure rather than only blocking IPs (they
   rotate); force password resets for accounts with anomalous successful
   logins; notify affected users.
7. **Harden the endpoint.** Deploy layered defenses: bot-management or
   risk-based authentication, breached-password screening at
   registration and login (k-anonymity APIs), MFA (phishing-resistant
   where possible), and device fingerprinting. Avoid CAPTCHA-only
   reliance.
8. **Monitor for adaptation.** Attackers shift to residential proxies and
   slower rates when blocked — maintain the hunt as a recurring analytic
   and track the campaign's infrastructure evolution.

## Expected outputs

- Campaign findings: infrastructure (IPs/ASNs), targeted user set,
  timeframe, success count.
- A victim list with forced-reset and notification records.
- Detection rules (velocity, distribution, reputation) with tuned
  thresholds.
- Hardening changes: risk-based auth, breached-password screening,
  MFA coverage.

## Pitfalls

- IP-only blocking is whack-a-mole against rotating proxy networks —
  combine with behavioral and reputation signals.
- Corporate NAT and shared egress IPs mimic stuffing distribution —
  allow-list known egress before alerting.
- CAPTCHAs degrade legitimate users and are increasingly solvable —
  treat as friction, not a control.
- Forcing resets on the entire user base for a targeted campaign
  creates support chaos — scope resets to affected accounts.
- Privacy: device fingerprinting and breach-data handling need legal
  review in regulated jurisdictions.

## References

- OWASP: Credential Stuffing prevention cheat sheet
- MITRE ATT&CK: T1110.004 (Credential Stuffing)
- NIST SP 800-63B: memorized secret and verifier guidance
- CISA: account-takeover and MFA guidance
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
