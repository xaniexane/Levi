---
skill_id: cyber_implementing_iec_62443_security_zones
name: Implementing IEC 62443 Security Zones
description: Apply the IEC 62443 zone-and-conduit model — partitioning OT systems, assigning target security levels, and documenting conduit requirements.
risk: info
permissions: []
requires_confirmation: false
tags: [ics, ot, standards, segmentation]
version: 1.0.0
---
## Purpose

Partition an industrial automation and control system (IACS) into security zones connected by conduits, per IEC 62443-3-2, so that compromise of one area cannot freely propagate to safety-critical functions. Each zone receives a target security level (SL-T) derived from risk assessment, and each conduit gets explicit security requirements — turning "segment the OT network" from a slogan into an engineered, auditable design.

## When to use

- Designing or retrofitting OT network segmentation for a plant, pipeline, or utility.
- Preparing for IEC 62443-2-4 / 3-3 assessments or customer security requirements.
- After an incident showed flat OT networks allowed lateral movement to controllers.
- Integrating IT/OT convergence projects (remote access, cloud historians, vendor connectivity).
- Building the security architecture deliverable for a greenfield automation project.

## Prerequisites

- A system-under-consideration (SUC) definition: which assets, processes, and boundaries are in scope.
- Asset inventory with Purdue-level mapping and data-flow diagrams between systems.
- A risk assessment (per 62443-3-2) identifying threat scenarios and tolerable risk.
- Stakeholders from operations, process engineering, and safety — security levels must reflect process risk, and safety instrumented systems have constraints security cannot override.
- Access to the IEC 62443 series (3-2 for zones/conduits, 3-3 for system requirements, 2-1 for program requirements) via ISA/IEC.

## Procedure

1. **Define the system under consideration.** Draw the boundary: which plants, skids, or lines are in scope, and where the SUC meets the enterprise network, vendors, and the internet. Everything outside the boundary is untrusted by default.
2. **Draft initial zones from functional and physical groupings.** Group assets by process function, physical location, and criticality — e.g., separate safety instrumented systems (SIS) into their own zone from basic process control, and separate the DMZ/historian tier from control. Align roughly with Purdue levels but let risk, not the model, decide the final cuts.
3. **Identify conduits and their data flows.** For every zone pair that must communicate, define the conduit: protocols, ports, direction, and whether flows are initiated or polled. Document undocumented flows discovered via traffic capture; OT networks always have them.
4. **Perform the 62443-3-2 risk assessment per zone.** For each zone, evaluate threat scenarios against consequence (safety, environmental, production, financial) and likelihood to derive the target security level SL-T (0–4). A zone containing the SIS protecting against loss of life will carry a higher SL-T than a utility monitoring zone.
5. **Allocate conduit requirements.** Translate each zone's SL-T into conduit security requirements using 62443-3-3 system requirements (SRs) and requirement enhancements (REs): identification and authentication, use control, system integrity, data confidentiality, restricted data flow, timely response to events, and resource availability. Write these as testable requirements, not adjectives.
6. **Design enforcement for each conduit.** Map requirements to controls: firewalls or data diodes at high-SL conduits, jump hosts and MFA for remote access conduits, TLS for OPC UA conduits, allowlisted application protocols. Note where compensating measures apply because legacy devices cannot meet an SR natively.
7. **Verify and document.** Walk the design against the seven foundational requirements of 62443-1-1, record gaps with remediation plans, and produce the zone-and-conduit drawing as a controlled document. This drawing becomes the reference for every future firewall change and audit.
8. **Maintain through change control.** Any new connection crossing a conduit — a vendor laptop, a new historian feed — triggers a zone/conduit review. Re-assess SL-T when processes, threats, or consequences change.

## Expected outputs

- Controlled zone-and-conduit architecture drawing for the SUC.
- Risk assessment records with SL-T assigned per zone (62443-3-2 methodology).
- Conduit requirement specifications mapped to 62443-3-3 SRs/REs.
- Gap register with compensating controls and remediation owners.
- Change-control procedure tying future connections to conduit review.

## Pitfalls

- **Zones drawn around org charts instead of risk.** Grouping by "everything the vendor supports" produces zones that mix safety-critical and office-adjacent systems. Let consequence drive partitioning.
- **Conduits without enforcement.** A conduit on paper with no firewall, diode, or monitoring is just a line on a drawing. Every conduit needs a real control.
- **Ignoring the SIS.** Safety instrumented systems deserve their own zone with the strictest conduits; commingling them with process control undermines both safety and security cases.
- **One-time exercise.** Zones decay as soon as the next "temporary" vendor connection appears. Without change control, the drawing is fiction within a year.
- **Over-targeting SL-4.** SL-4 (protection against nation-state, extended resources) is rarely justified outside the most critical infrastructure; inflated SL-Ts produce unaffordable requirements that get waived wholesale.

## References

- IEC 62443-3-2, "Security risk assessment for system design" (zone/conduit methodology; via IEC/ISA)
- IEC 62443-3-3, "System security requirements and security levels" (via IEC/ISA)
- NIST SP 800-82 Rev. 3, "Guide to OT Security" — https://csrc.nist.gov/publications/detail/sp/800-82/rev-3/final
- MITRE ATT&CK for ICS — https://attack.mitre.org/techniques/ics/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
