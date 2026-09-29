---
skill_id: grey_exercise_network_time_sync
name: Exercise Time Synchronization Setup
description: Establish authoritative time sync across the range for timeline correlation.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, setup, ntp, forensics]
version: 1.0.0
team: grey
---
# Exercise Time Synchronization Setup

## Purpose

Timelines are the exercise's evidence, and timelines need synchronized clocks. This
setup establishes authoritative NTP across the range so red actions, blue detections,
and logs correlate to the second.

## When to use

- During range setup, before exercise traffic.
- When timeline disputes arise (retroactive fix is impossible — do it first).

## Prerequisites

- Range network with an NTP source (simulator or upstream, documented).

## Procedure

1. Designate the authoritative NTP source for the range; document its stratum and source.
2. Configure all range hosts, network devices, and the SIEM to sync to it.
3. Verify offset on a sample of hosts (chrony/ntp sources, event-log timestamps).
4. Document the time zone policy (UTC everywhere recommended).
5. Re-verify at exercise start and after any range reset.

## Expected outputs

- NTP design with source documentation.
- Offset-verification results.
- Time-zone policy.

## Pitfalls

- Hosts syncing to different sources — one authority, no exceptions.
- Assuming virtualization host time is correct — verify the whole chain.
- Time-zone soup in timelines — UTC everywhere.

## References

- NTP documentation; forensic-timeline literature.

## Exercise role

A second of clock skew is a timeline dispute — synchronized time is the cheapest
forensic control there is.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
