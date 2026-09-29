---
skill_id: cyber_b3_cryptominer_intrusion_cicd_runner_remote_workforce_defined
name: Cryptominer Intrusion Defense for CI/CD Runners in Remote Workforce (Defined Maturity)
description: "Cryptominer Intrusion defense playbook for CI/CD Runners in Remote Workforce at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [malware, cloud, devops, supply-chain, remote, endpoint, zero-trust, maturity-defined]
version: 1.0.0
---
# Cryptominer Intrusion Defense for CI/CD Runners in Remote Workforce (Defined Maturity)

## Purpose

Unauthorized miners burn CPU/GPU and cloud spend, and — more importantly — prove an attacker has code execution on your assets. Treat every miner as a foothold to investigate, not just a performance problem. Applies to CI/CD Runners in Remote Workforce at Defined maturity.

## When to use

- Sustained high CPU/GPU on hosts or cloud instances with no business workload, especially at night/weekends, plus connections to known mining pools on Stratum ports.
- Cloud billing spikes for compute in regions you do not use, or new instances launched by unfamiliar principals.
- EDR detections for xmrig or similar binaries, scheduled tasks re-fetching miner payloads, or WMI persistence entries.
- Lens: Best telemetry: job execution logs + runner registration events + secret-access audit. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Job logs with executed commands and exit codes for suspect runs and Runner registration/deregistration events and runner version inventory; run `runner-cli jobs list --status failed --last 7d | head -20` then `runner-cli runners list --format table`.
3. **Analyze.** Trace the miner's persistence and delivery: the initial access vector (exposed service, weak SSH, vulnerable app) matters more than the miner itself. Then: Check for dual-use: many miner campaigns also exfiltrate credentials or deploy additional payloads — sweep for those.
4. **Contain and harden.** Close the entry vector (patch the exploited service, enforce key-based SSH, remove internet exposure), then block mining pool domains at DNS. Asset layer: Ephemeral isolated runners, OIDC short-lived credentials, no persistent secrets on runners. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Killing the miner without removing persistence — it returns on reboot or on schedule.
- Writing it off as 'just a miner' without investigating the initial access that delivered it.

## References

- MITRE ATT&CK: T1496 (Impact: Resource Hijacking)
- Vendor logging and hardening baselines for CI/CD Runners; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
