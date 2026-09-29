---
skill_id: red_external_remote_service_brute_force
name: External Remote Service Brute Force
description: Test externally exposed RDP, SSH, and VPN endpoints against brute-forcing to validate hardening and monitoring.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, initial-access, brute-force, remote-services]
version: 1.0.0
team: red
tests_blue: cyber_detecting_rdp_brute_force_attacks
---
# External Remote Service Brute Force

## Purpose

Internet-exposed remote services are the front door attackers knock on first. This test
measures whether brute-forcing those doors is feasible, detected, and rate-limited — or
whether the blue team is blind to it. Findings here are usually 'expose less, monitor
more.'

## When to use

- After the exposed-service review identifies internet-facing RDP/SSH/VPN.
- To validate account lockout, IP blocklisting, and geo-blocking on remote access.
- Before recommending VPN/RDP exposure reduction.

## Prerequisites

- Authorization for the exact endpoints and a conservative attempt budget.
- Agreement on lockout-risk: the test must not denial-of-service legitimate remote
  workers.

## Procedure

1. Inventory the exposed remote services from the recon phase; confirm each is in scope and
   note its auth mechanism (password, key, MFA).
2. Run low-and-slow brute-forcing with a small credential set (defaults, common pairs) —
   this is a controls test, not a cracking run.
3. Test for missing MFA, default credentials, and absent lockout by observing responses
   (not by hammering).
4. Monitor blue-team detection in parallel: firewall blocks, IDS alerts, SIEM failed-logon
   rules.
5. Document every finding with the exact attempt count and rate that produced it.
6. Recommend exposure reduction (VPN-only, allowlisting, MFA) for each vulnerable service.

## Expected outputs

- Per-endpoint brute-force resistance assessment.
- Detection telemetry: which attempts were seen and blocked.
- Exposure-reduction recommendations per service.

## Pitfalls

- High-volume brute-forcing that locks out legitimate users or triggers upstream ISP
  blocks.
- Testing VPN endpoints shared with third parties without confirming scope.
- Confusing 'login page exists' with 'vulnerable' — the finding is about controls, not
  existence.

## References

- MITRE ATT&CK: Brute Force (T1110), External Remote Services (T1133).

## Blue-team control under test

This playbook validates their perimeter monitoring and remote-access hardening are under
test — unalerted brute-forcing is a detection gap even when no credential works. Paired
blue-team counterpart: `cyber_detecting_rdp_brute_force_attacks`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
