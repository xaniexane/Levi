---
skill_id: cyber_b3_password_spraying_active_directory_dc_remote_workforce_defined
name: Password Spraying Defense for Active Directory Domain Controllers in Remote Workforce (Defined Maturity)
description: "Password Spraying defense playbook for Active Directory Domain Controllers in Remote Workforce at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, authentication, windows, active-directory, remote, endpoint, zero-trust, maturity-defined]
version: 1.0.0
---
# Password Spraying Defense for Active Directory Domain Controllers in Remote Workforce (Defined Maturity)

## Purpose

Attackers try a small set of common passwords against many usernames, staying under per-account lockout thresholds. It is quieter than stuffing and specifically tuned to evade lockout policies, often running for days or weeks. Applies to Active Directory Domain Controllers in Remote Workforce at Defined maturity.

## When to use

- A handful of failed logons per account (1-3) spread across hundreds of accounts from one or a few IPs, repeating on a schedule — the classic low-and-slow pattern.
- The same few passwords attempted everywhere (SeasonYear!, Company123, Password1); check by aggregating failed-logon password hashes where your IdP logs them.
- Spray bursts correlated with newly published password lists or timed to holidays/weekends when response is slower.
- Lens: Best telemetry: forwarded Security logs (4768/4769/4771/4662/4720/4732/4724/5136) + AD replication monitoring. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Security log Kerberos events (4768 TGT requests, 4769 service tickets, 4771 pre-auth failures) and Directory-service change events (5136/5137) and replication metadata (repadmin /showobjmeta); run `repadmin /showrepl | Select-String -Pattern 'error|fail' -Context 2` then `Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4769} -MaxEvents 200 | Group-Object {$_.Properties[0].Value} | Sort-Object Count -Descending | Select-Object -First 10 Name, Count`.
3. **Analyze.** Reconstruct the spray window: first-seen to last-seen per source IP, and list every account with even one success inside the window — those are confirmed or suspected takeovers. Then: Check whether sprayed accounts share traits (same OU, same onboarding batch, service accounts) to find how the username list was built.
4. **Contain and harden.** Smart lockout (soft lockout with increasing delays) plus alerting on distributed low-volume failures, not just lockouts. Asset layer: Tier-zero isolation: DCs on dedicated hosts, no browsing/email, admin access via PAW/jump host only. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Per-account lockout thresholds alone will not catch spraying; you need cross-account velocity detection.
- Treating one success as an isolated incident misses the campaign — always scope the full spray window.

## References

- MITRE ATT&CK: T1110.003 (Credential Access: Brute Force: Password Spraying)
- Vendor logging and hardening baselines for Active Directory Domain Controllers; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
