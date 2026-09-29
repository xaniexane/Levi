---
skill_id: grey_ad_lab_provisioning
name: Active Directory Lab Provisioning
description: Provision lab Active Directory forests with realistic structure and intentional weaknesses.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, provisioning, active-directory, lab]
version: 1.0.0
team: grey
---
# Active Directory Lab Provisioning

## Purpose

AD exercises need a forest that looks real: OUs, groups, GPOs, trusts, and the
intentional misconfigurations the scenario calls for. This runbook builds it
reproducibly from IaC/scripts, never by hand-tweaking a snowflake domain.

## When to use

- For AD-focused exercises (kerberos attacks, trust abuse, DCSync).
- When the scenario needs multi-domain or trust topologies.
- To rebuild AD between exercise iterations.

## Prerequisites

- AD deployment scripts/IaC reviewed and version-controlled.
- Scenario's intentional-weakness list (what's misconfigured on purpose).
- Lab DNS and network segments ready.

## Procedure

1. Deploy the forest: root domain, child domains/trusts per the scenario topology.
2. Build the OU structure, security groups, and GPO baselines from the versioned scripts.
3. Create user, service, and admin accounts per the roster — with the scenario's password
   hygiene (weak where intended, documented).
4. Apply the intentional misconfigurations from the scenario list — each one ticketed and
   documented as deliberate.
5. Enable the auditing the exercise needs: AD DS auditing, LDAP logging, DC event
   forwarding.
6. Verify replication health and the blue team's visibility before handover.
7. Snapshot the DCs; hand over with the AD design document.

## Expected outputs

- Provisioned AD forest with design doc.
- Intentional-weakness register (deliberate vs. real).
- Replication and auditing health check.
- DC snapshot reference.

## Pitfalls

- Hand-tweaked domains nobody can rebuild — script everything.
- Intentional weaknesses undocumented — the blue team must know what's deliberate.
- Production password vaults or real data in the lab — never.

## References

- Microsoft AD DS deployment documentation.

## Exercise role

A lab domain is a stage set — realistic enough to exercise in, documented enough to
rebuild, and never confused with production.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
