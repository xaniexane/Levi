---
skill_id: grey_network_segmentation_build
name: Exercise Network Segmentation Build
description: Build segmented exercise networks with controlled choke points and monitoring.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, provisioning, network, segmentation]
version: 1.0.0
team: grey
---
# Exercise Network Segmentation Build

## Purpose

Exercise networks need the segmentation the scenario demands — user segments, server
segments, DMZ, red-team ingress — with taps and choke points the grey team controls.
This runbook builds it.

## When to use

- For network-focused exercises (lateral movement, segmentation validation).
- When the scenario tests firewall rules between segments.
- To rebuild network topology between iterations.

## Prerequisites

- Network design document for the exercise.
- Firewall/router capacity (virtual or physical).
- Monitoring taps or SPAN ports planned.

## Procedure

1. Build the segments per the design: addressing, VLANs, inter-segment firewall rules.
2. Deploy the choke points: all inter-segment traffic through grey-team-controlled
   firewalls with logging.
3. Place network taps/SPAN for the blue team's NDR and the grey team's exercise monitoring.
4. Deploy the scenario services per segment (user services, crown-jewel servers, internet
   simulator).
5. Verify the ruleset: test each allowed/denied path and log the results.
6. Document the as-built topology; hand over with the firewall ruleset.

## Expected outputs

- As-built network topology.
- Firewall ruleset with path-test results.
- Tap/monitoring placement map.

## Pitfalls

- Untested deny rules — verify the blocks, don't assume the firewall did it.
- No taps on the choke points — exercise traffic without network telemetry.
- Internet simulator leaking to real internet — contain it.

## References

- NIST SP 800-41 (firewall guidance); network-security literature.

## Exercise role

The network is the exercise's physics — every segment, rule, and tap the grey team
builds determines what the red and blue teams can prove.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
