---
skill_id: grey_cloud_range_provisioning
name: Cloud Range Provisioning
description: Provision cloud-based exercise ranges with account isolation and cost guardrails.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, provisioning, cloud, range]
version: 1.0.0
team: grey
---
# Cloud Range Provisioning

## Purpose

Cloud ranges spin up fast and tear down clean — if the accounts, guardrails, and cost
controls are right. This runbook provisions cloud exercise environments with hard
isolation from production accounts and spend limits that can't surprise anyone.

## When to use

- For cloud-focused exercises (cloud red-team, IAM attack paths).
- When physical lab capacity is unavailable.
- For distributed exercises with remote participants.

## Prerequisites

- Cloud organization with a dedicated range OU/account, separate from production.
- Cost alerts and hard spend caps configured before provisioning.
- IaC templates for the range reviewed.

## Procedure

1. Create the range accounts under the dedicated OU with SCPs denying production access and
   expensive services.
2. Deploy via IaC: VPCs, subnets, IAM roles, logging (CloudTrail/audit) enabled in all
   regions from minute one.
3. Configure cost alerts at 50/80/100% of the exercise budget; set hard caps where the
   platform allows.
4. Deploy the target cloud estate: canary data, test identities, vulnerable-by-design
   resources per the scenario.
5. Verify isolation: no trust to production accounts, no shared networking.
6. Tag everything with the exercise codename and auto-expiry date.
7. Hand over with the cloud-range checklist; schedule the teardown job.

## Expected outputs

- Provisioned cloud range with IaC state.
- Isolation and guardrail verification.
- Cost-alert configuration evidence.
- Teardown schedule.

## Pitfalls

- Range accounts under the production OU — SCPs must deny the crossover explicitly.
- No spend cap — a crypto-mining scenario or a mistake becomes a bill.
- Forgetting to enable audit logging in all regions — partial logging is a gap.

## References

- Cloud provider documentation (Organizations/SCP, CloudTrail, budgets).

## Exercise role

Cloud ranges trade lab fidelity for speed and teardown cleanliness — the guardrails
(isolation, cost, logging) are what make the trade safe.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
