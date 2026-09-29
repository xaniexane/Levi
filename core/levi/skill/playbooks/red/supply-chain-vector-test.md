---
skill_id: red_supply_chain_vector_test
name: Supply-Chain Vector Validation Test
description: Validate software-supply-chain attack vectors to test update-integrity and vendor-risk controls.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, lateral-movement, supply-chain]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_sbom_for_supply_chain_vulnerabilities
---
# Supply-Chain Vector Validation Test

## Purpose

Supply-chain attacks move laterally through trusted updates. This test validates the
controls around software updates — signature verification, update-channel integrity, and
vendor-risk processes — using canary update scenarios, never real trojanized software.

## When to use

- During advanced phases, with explicit supply-chain authorization.
- To validate update-signature verification and channel security.
- To test vendor-risk assessment processes.

## Prerequisites

- Explicit authorization for supply-chain scenarios; canary updates only.
- Update-infrastructure team coordination.

## Procedure

1. Map the update channels: which software auto-updates, from where, with what
   verification?
2. Test signature verification: does the updater reject a canary unsigned/modified package?
3. Simulate a canary malicious update through the test channel (authorized) and measure
   detection.
4. Audit vendor access: which vendors have direct update or remote-access paths?
5. Deliver the supply-chain integrity assessment with verification and vendor-risk
   recommendations.

## Expected outputs

- Update-channel map with verification status.
- Canary update-test results.
- Vendor-access audit.

## Pitfalls

- Real trojanized updates — canary scenarios only, never production update channels.
- Testing vendor paths without the vendor-relationship owner's coordination.

## References

- MITRE ATT&CK: Supply Chain Compromise (T1195).

## Blue-team control under test

This playbook validates their update-integrity controls are under test — updaters that
accept unsigned packages are a supply-chain gap. Paired blue-team counterpart:
`cyber_analyzing_sbom_for_supply_chain_vulnerabilities`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
