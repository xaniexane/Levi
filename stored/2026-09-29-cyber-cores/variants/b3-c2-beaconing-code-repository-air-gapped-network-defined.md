---
skill_id: cyber_b3_c2_beaconing_code_repository_air_gapped_network_defined
name: C2 Beaconing Defense for Code Repositories in Air-Gapped Networks (Defined Maturity)
description: "C2 Beaconing defense playbook for Code Repositories in Air-Gapped Networks at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [network, c2, devops, supply-chain, secrets, air-gap, ot, high-security, maturity-defined]
version: 1.0.0
---
# C2 Beaconing Defense for Code Repositories in Air-Gapped Networks (Defined Maturity)

## Purpose

Compromised hosts check in with attacker infrastructure on a schedule — the heartbeat of an intrusion. Beaconing detection is statistical: regularity, jitter analysis, and connection uniformity reveal what signatures miss. Applies to Code Repositories in Air-Gapped Networks at Defined maturity.

## When to use

- Outbound connections at fixed intervals (e.g., every 60s) with consistent byte counts to an external host — visible in NetFlow or proxy logs as metronomic traffic.
- Long-lived sessions to IPs with no domain, newly registered domains, or domains with no legitimate business purpose.
- Jittered but statistically regular timing: inter-arrival times clustering around a mean with small variance.
- Lens: Best telemetry: push/audit logs + secret-scanning alerts + branch-protection change history. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Push logs (who pushed what to which branch), force-push and history-rewrite records and Secret-scanning and code-scanning alerts with their resolution state; run `git log --since='7 days ago' --format='%h %an %ad %s' --date=short | head -30` then `git log --all --diff-filter=A -- '*secret*' '*credential*' '*key*' --format='%h %an %s' | head -20`.
3. **Analyze.** Compute inter-arrival statistics on the suspect flows; true beacons show low variance even with jitter, unlike human browsing. Then: Capture the beacon payload in a sandbox detonation to identify the implant family and its tasking protocol.
4. **Contain and harden.** Egress filtering: default-deny outbound with allowlisted destinations for servers; alert on direct-to-IP connections. Asset layer: Branch protection with required reviews, signed commits, push protection for secrets. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Chasing the C2 IP instead of the implant — infrastructure is disposable, the foothold is what matters.
- Assuming encrypted traffic cannot be analyzed: timing, size, and destination metadata still betray beacons.

## References

- MITRE ATT&CK: T1071.001 (Command and Control: Web Protocols)
- Vendor logging and hardening baselines for Code Repositories; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
