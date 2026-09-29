---
skill_id: cyber_b3_pass_the_hash_cicd_runner_remote_workforce_optimized
name: Pass-the-Hash Defense for CI/CD Runners in Remote Workforce (Optimized Maturity)
description: "Pass-the-Hash defense playbook for CI/CD Runners in Remote Workforce at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, lateral-movement, devops, supply-chain, remote, endpoint, zero-trust, maturity-optimized]
version: 1.0.0
---
# Pass-the-Hash Defense for CI/CD Runners in Remote Workforce (Optimized Maturity)

## Purpose

Stolen NTLM hashes authenticate without the password ever being cracked. It is invisible to password monitoring because no password is used — defense means killing NTLM where possible and watching for its telltale logon patterns. Applies to CI/CD Runners in Remote Workforce at Optimized maturity.

## When to use

- 4624 type-3/9 logons using NTLM where Kerberos is expected, especially from workstations to servers with admin accounts.
- Logon sessions with no interactive activity but successful authentication, or the same hash authenticating from multiple hosts simultaneously.
- NTLM audit logs showing authentication for accounts that should be Kerberos-only.
- Lens: Best telemetry: job execution logs + runner registration events + secret-access audit. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Job logs with executed commands and exit codes for suspect runs and Runner registration/deregistration events and runner version inventory; run `runner-cli jobs list --status failed --last 7d | head -20` then `runner-cli runners list --format table`.
3. **Analyze.** Determine hash source: LSASS dump, SAM extraction, or DCSync — each implies a different prior compromise to remediate. Then: List every host the hash authenticated to; each is a foothold until reimaged or verified clean.
4. **Contain and harden.** Reduce NTLM usage (audit mode first, then restrict), deploy Credential Guard, and use unique local admin passwords (LAPS). Asset layer: Ephemeral isolated runners, OIDC short-lived credentials, no persistent secrets on runners. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Resetting the password without considering that the attacker may have dumped the NEW hash too if still present.
- Disabling NTLM blindly and breaking legacy apps — audit first, restrict second.

## References

- MITRE ATT&CK: T1550.002 (Lateral Movement: Pass the Hash)
- Vendor logging and hardening baselines for CI/CD Runners; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
