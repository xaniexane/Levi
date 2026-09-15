---
skill_id: cyber_performing_ics_asset_discovery_with_claroty
name: ICS Asset Discovery with Claroty
description: Discover and inventory OT assets passively for security visibility.
risk: low
permissions: []
requires_confirmation: false
tags: [ics, ot, asset-management]
version: 1.0.0
---
# ICS Asset Discovery with Claroty

## Purpose

You cannot protect controllers, HMIs, and historians you do not know
exist. Passive OT asset discovery identifies industrial devices without
disrupting fragile processes. This playbook uses Claroty-style passive
monitoring to build a defensible OT asset inventory and risk picture.

## When to use

- Building the first authoritative OT asset inventory.
- Pre-assessment scoping for an ICS security review.
- Detecting rogue or unauthorized devices on the OT network.
- Supporting incident response in an OT environment.

## Prerequisites

- Authorization from OT operations and plant management; even passive
  monitoring touches production networks and needs their sign-off.
- Network taps or SPAN ports at the OT aggregation points, placed with
  the controls engineers who know the architecture.
- Claroty (or equivalent passive OT monitoring) deployed and baselined
  to the site's protocols.

## Procedure

1. Confirm the monitoring design with operations: tap/SPAN placement,
   which segments are covered, and confirmation that the sensor is
   receive-only (no active scanning on fragile OT segments without
   explicit approval).
2. Let the platform learn: allow a full process cycle of passive
   collection so device identification is based on real protocol
   traffic, not guesses.
3. Review discovered assets: validate device types, vendors, firmware
   versions, and roles against engineering documentation and walkdowns.
4. Identify the unknowns: unmanaged devices, IT/OT boundary crossings,
   and devices speaking protocols they should not — each gets an owner
   and a disposition.
5. Assess risk per asset: unpatched firmware with known CVEs,
   default credentials, cleartext protocols (Modbus, S7, DNP3 without
   protection), and Internet-reachable paths.
6. Map communication flows: which assets talk to whom, across which
   Purdue-model levels — this becomes the segmentation baseline.
7. Feed the IT SOC: export asset and vulnerability data to the
   ticketing/CMDB process so OT findings get tracked like IT findings.
8. Maintain the inventory: review new-device alerts weekly; any device
   appearing without a change ticket is investigated.

## Expected outputs

- A validated OT asset inventory with firmware versions and roles.
- A risk-ranked vulnerability list per asset.
- A communication-flow map across Purdue levels.
- A process for ongoing new-device detection.

## Pitfalls

- Active scanning on OT networks: it can crash fragile controllers —
   stay passive unless operations explicitly approves otherwise.
- Treating the platform's auto-identification as gospel: validate
   against engineering records.
- Discovering assets but never assigning owners: an inventory without
   accountability does not get patched.
- Pushing IT patching cadences onto OT: maintenance windows and safety
   testing govern OT remediation.

## References

- NIST SP 800-82, Guide to OT Security
- CISA ICS advisories and alerts (cisa.gov/ics)
- ISA/IEC 62443 series on industrial automation security
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
