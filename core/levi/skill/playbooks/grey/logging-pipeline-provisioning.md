---
skill_id: grey_logging_pipeline_provisioning
name: Exercise Logging Pipeline Provisioning
description: Provision the exercise logging pipeline: collection, forwarding, and retention.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, provisioning, logging, siem]
version: 1.0.0
team: grey
---
# Exercise Logging Pipeline Provisioning

## Purpose

An exercise without telemetry is theater. This runbook provisions the logging pipeline
before any exercise traffic: endpoint forwarding, network taps, cloud audit streams, and
the SIEM workspace — with retention covering the exercise plus analysis time.

## When to use

- Before every exercise, as part of range provisioning.
- When standing up persistent range logging.
- To rebuild logging between iterations.

## Prerequisites

- SIEM capacity for the exercise data volume.
- Log-source inventory from the range design.
- Retention policy for exercise data.

## Procedure

1. Deploy forwarders/agents on all range hosts; verify event flow per source.
2. Configure network-tap/SPAN ingestion and cloud-audit streams.
3. Build the exercise SIEM workspace: indices, dashboards, and the exercise codename tag.
4. Verify end-to-end: generate canary events on each source type and confirm SIEM arrival
   with latency measurement.
5. Configure retention: exercise data kept for the analysis window, then purged per policy.
6. Hand over with the logging-health dashboard and source inventory.

## Expected outputs

- Log-source inventory with health status.
- Canary-event verification per source.
- Latency measurements.
- Retention configuration.

## Pitfalls

- Exercise traffic before logging verification — the first red action with no telemetry
  is lost data.
- Retention shorter than the analysis window — keep data until the report is done.
- No canary verification — 'forwarding configured' isn't 'forwarding working'.

## References

- NIST SP 800-92 (log management).

## Exercise role

Telemetry is the exercise's memory — provisioned and verified before anything happens,
or the exercise never really happened.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
