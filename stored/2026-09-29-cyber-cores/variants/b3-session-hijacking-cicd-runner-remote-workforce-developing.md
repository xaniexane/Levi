---
skill_id: cyber_b3_session_hijacking_cicd_runner_remote_workforce_developing
name: Web Session Hijacking Defense for CI/CD Runners in Remote Workforce (Developing Maturity)
description: "Web Session Hijacking defense playbook for CI/CD Runners in Remote Workforce at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [web, identity, devops, supply-chain, remote, endpoint, zero-trust, maturity-developing]
version: 1.0.0
---
# Web Session Hijacking Defense for CI/CD Runners in Remote Workforce (Developing Maturity)

## Purpose

Stolen session cookies let attackers ride authenticated web sessions without credentials or MFA. Cookie theft via infostealer or XSS is the usual source; concurrent-session anomalies are the usual signal. Applies to CI/CD Runners in Remote Workforce at Developing maturity.

## When to use

- The same session active from two geographies or ASNs simultaneously, or a session suddenly continuing from a datacenter IP.
- Session created without a fresh authentication event (cookie replay), or user-agent/IP changing mid-session.
- Infostealer execution on the user's device shortly before the anomalous session.
- Lens: Best telemetry: job execution logs + runner registration events + secret-access audit. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Job logs with executed commands and exit codes for suspect runs and Runner registration/deregistration events and runner version inventory; run `runner-cli jobs list --status failed --last 7d | head -20` then `runner-cli runners list --format table`.
3. **Analyze.** Determine the theft vector: device compromise (cookie files exfiltrated) versus application XSS — the fix differs. Then: Inventory actions taken in the hijacked session: data viewed, settings changed, transactions performed.
4. **Contain and harden.** Short session lifetimes, binding sessions to device/IP characteristics, and step-up auth for sensitive actions. Asset layer: Ephemeral isolated runners, OIDC short-lived credentials, no persistent secrets on runners. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Invalidating the password but not the session — the hijacker stays logged in.
- Missing that the user's DEVICE is compromised; the next session gets stolen too until the infostealer is removed.

## References

- MITRE ATT&CK: T1539 (Credential Access: Steal Web Session Cookie)
- Vendor logging and hardening baselines for CI/CD Runners; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
