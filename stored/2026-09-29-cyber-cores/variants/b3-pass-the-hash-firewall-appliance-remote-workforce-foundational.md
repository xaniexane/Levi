---
skill_id: cyber_b3_pass_the_hash_firewall_appliance_remote_workforce_foundational
name: Pass-the-Hash Defense for Firewall Appliances in Remote Workforce (Foundational Maturity)
description: "Pass-the-Hash defense playbook for Firewall Appliances in Remote Workforce at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, lateral-movement, network, firewall, remote, endpoint, zero-trust, maturity-foundational]
version: 1.0.0
---
# Pass-the-Hash Defense for Firewall Appliances in Remote Workforce (Foundational Maturity)

## Purpose

Stolen NTLM hashes authenticate without the password ever being cracked. It is invisible to password monitoring because no password is used — defense means killing NTLM where possible and watching for its telltale logon patterns. Applies to Firewall Appliances in Remote Workforce at Foundational maturity.

## When to use

- 4624 type-3/9 logons using NTLM where Kerberos is expected, especially from workstations to servers with admin accounts.
- Logon sessions with no interactive activity but successful authentication, or the same hash authenticating from multiple hosts simultaneously.
- NTLM audit logs showing authentication for accounts that should be Kerberos-only.
- Lens: Best telemetry: traffic/deny logs + admin audit log + config-change diffs shipped to SIEM. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Traffic logs (allowed/denied with rule IDs), threat logs (IPS/AV verdicts), admin audit log and Configuration revisions and diffs; VPN session logs and authentication failures; run `# vendor CLIs differ; conceptually:` then `show log traffic query (source <suspect-ip>)             # Palo Alto style`.
3. **Analyze.** Determine hash source: LSASS dump, SAM extraction, or DCSync — each implies a different prior compromise to remediate. Then: List every host the hash authenticated to; each is a foothold until reimaged or verified clean.
4. **Contain and harden.** Reduce NTLM usage (audit mode first, then restrict), deploy Credential Guard, and use unique local admin passwords (LAPS). Asset layer: Default-deny with documented rules, admin on dedicated interface with MFA, config backups versioned. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Resetting the password without considering that the attacker may have dumped the NEW hash too if still present.
- Disabling NTLM blindly and breaking legacy apps — audit first, restrict second.

## References

- MITRE ATT&CK: T1550.002 (Lateral Movement: Pass the Hash)
- Vendor logging and hardening baselines for Firewall Appliances; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
