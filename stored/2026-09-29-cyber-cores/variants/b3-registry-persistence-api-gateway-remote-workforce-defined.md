---
skill_id: cyber_b3_registry_persistence_api_gateway_remote_workforce_defined
name: Registry Persistence Defense for API Gateways in Remote Workforce (Defined Maturity)
description: "Registry Persistence defense playbook for API Gateways in Remote Workforce at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, web, api, remote, endpoint, zero-trust, maturity-defined]
version: 1.0.0
---
# Registry Persistence Defense for API Gateways in Remote Workforce (Defined Maturity)

## Purpose

Run keys, services, Winlogon helpers, and COM hijacks give attackers reboot-surviving execution with minimal footprint. Baseline the autoruns on gold images; alert on deviations, not on the mechanism's existence. Applies to API Gateways in Remote Workforce at Defined maturity.

## When to use

- Writes to Run/RunOnce keys, Winlogon Userinit/Shell values, or service ImagePath entries pointing at unusual binaries.
- Sysmon event 13 (registry value set) on autorun locations by non-installer processes, or new services with suspicious binaries.
- Autoruns deltas: new entries appearing between baseline scans on hosts with no software-change record.
- Lens: Best telemetry: per-request logs with API key/identity, endpoint, params hash, and response size. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Gateway access logs with authenticated identity per call; rate-limit trigger logs and Schema-validation failure logs (attacks often start as malformed requests); run `grep <api-key-id> /var/log/apigw/access.log | awk '{print $7}' | sort | uniq -c | sort -rn | head -20` then `grep -c 'schema_validation_failed' /var/log/apigw/error.log`.
3. **Analyze.** Capture the referenced binary: hash, signature, and sandbox detonation to confirm malicious intent. Then: Check the same autorun locations across the fleet — registry persistence is often deployed identically to many hosts.
4. **Contain and harden.** Scheduled Autoruns/Sysmon baselining with alerting on new persistence entries; restrict registry write rights for standard users. Asset layer: Positive-security policies: schema validation, per-client rate limits, OAuth scopes per endpoint. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Cleaning the registry value while the dropper that restores it still runs on a schedule.
- Overlooking user-hive (HKCU) persistence during a 'system-only' triage.

## References

- MITRE ATT&CK: T1112 (Defense Evasion: Modify Registry) for persistence
- Vendor logging and hardening baselines for API Gateways; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
