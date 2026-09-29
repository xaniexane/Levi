---
skill_id: red_software_inventory_recon
name: Software Inventory Reconnaissance Test
description: Enumerate installed software to validate patching and unauthorized-software controls.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, discovery, inventory, patching]
version: 1.0.0
team: red
tests_blue: cyber_performing_asset_criticality_scoring_for_vulns
---
# Software Inventory Reconnaissance Test

## Purpose

The software inventory is the vulnerability surface made visible. This test enumerates
installed software across sampled hosts and validates patch currency, unauthorized
software detection, and the accuracy of the asset inventory itself.

## When to use

- During discovery phases.
- To validate vulnerability-management coverage and software allowlisting.
- To check the asset inventory's accuracy against ground truth.

## Prerequisites

- Authorization for the sampled hosts; read-only enumeration.
- Vulnerability-management team coordination for the patch comparison.

## Procedure

1. Enumerate installed software on sampled hosts (registry, WMI, package managers).
2. Compare against the official asset inventory — flag drift (installed but unrecorded).
3. Check patch levels of high-risk software (browsers, runtimes, VPN clients) against known
   CVEs.
4. Flag unauthorized software per the allowlist policy.
5. Deliver the inventory-accuracy and patch-currency assessment.

## Expected outputs

- Software inventory per sampled host with drift analysis.
- Patch-gap findings tied to CVEs.
- Unauthorized-software findings.

## Pitfalls

- Full-fleet enumeration without sampling approval — sample first, expand if the drift
  is bad.
- Flagging portable/approved exceptions as unauthorized — check the exception list.

## References

- MITRE ATT&CK: Software Discovery (T1518).

## Blue-team control under test

This playbook validates their asset inventory and patching get ground-truthed — drift
between the inventory and reality is the foundational finding. Paired blue-team
counterpart: `cyber_performing_asset_criticality_scoring_for_vulns`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
