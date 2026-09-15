---
skill_id: cyber_implementing_purdue_model_network_segmentation
name: Implementing Purdue Model Network Segmentation
description: Apply the Purdue Enterprise Reference Architecture levels 0–5 to segment IT/OT networks — level boundaries, DMZ placement, and conduit controls.
risk: info
permissions: []
requires_confirmation: false
tags: [ot, ics, network, segmentation]
version: 1.0.0
---
## Purpose

Use the Purdue model's six levels (0: physical process, 1: basic control, 2: supervisory, 3: operations/DMZ, 4: enterprise, 5: internet) as the skeleton for OT network segmentation: assets assigned to levels, traffic between levels crossing explicit conduits, and the level 3.5 industrial DMZ mediating all IT/OT interaction. The model gives operations and security a shared language for where boundaries go and why.

## When to use

- Designing greenfield OT networks or remediating flat brownfield ones.
- Communicating segmentation architecture to operations teams who think in process terms, not firewall rules.
- Aligning with IEC 62443 zones/conduits (Purdue levels are the natural starting point for zone definition).
- Planning IT/OT convergence projects with clear demarcation.
- Teaching and onboarding: the Purdue model remains the lingua franca of OT architecture.

## Prerequisites

- Asset inventory classifiable by function: sensors/actuators, controllers, HMIs/SCADA, historians/MES, business systems.
- Data-flow documentation (or traffic captures) showing actual cross-level communication.
- Operations partnership: level assignments affect how engineers work; they must co-own the design.
- Firewall/segmentation enforcement points identified per level boundary.
- Understanding that Purdue is a reference model, not a security standard — it organizes, IEC 62443 secures.

## Procedure

1. **Assign every asset to a Purdue level.** Level 0: sensors, actuators, the physical process. Level 1: PLCs, RTUs, DCS controllers, safety systems. Level 2: HMIs, SCADA servers, engineering workstations. Level 3: historians, MES, OT DMZ services, patch/file servers. Level 4: ERP, email, business applications. Level 5: internet. Document borderline cases (a historian also feeding the cloud, a vendor gateway) explicitly — ambiguity here becomes firewall exceptions later.
2. **Draw the as-is against the model.** Map current connectivity onto the levels and highlight every violation of the model's intent: Level 4 workstations reaching Level 1 controllers directly, internet-reachable HMIs, flat L2/L3 networks spanning levels. This gap diagram is the business case for the segmentation project.
3. **Insert the Level 3.5 industrial DMZ.** Between Level 3 and Level 4, establish the DMZ hosting the boundary services: replicated historians, remote-access jump hosts, AV/patch relays, data-transfer servers. All IT↔OT traffic passes through the DMZ; no direct Level 4→Level 2 (or lower) connections survive the redesign.
4. **Define inter-level conduits.** For each adjacent level pair, specify the allowed protocols, directions, and endpoints: Level 2→3 historian replication (OPC UA, initiated upward); Level 3.5→2 read-only data access for authorized jump hosts; Level 5→3.5 vendor remote access only via the jump host with MFA. Default-deny all other inter-level traffic.
5. **Enforce with appropriate controls per boundary.** Firewalls with application-aware OT rules at each level boundary; unidirectional gateways for strictly one-way flows (e.g., Level 3→4 monitoring exports); data diodes where consequence justifies them. Match control strength to the consequence of boundary violation — the L1/L2 boundary near safety systems gets the strongest controls.
6. **Separate safety within Level 1.** The Purdue model groups safety with basic control, but security practice separates safety instrumented systems into their own zone with dedicated conduits. Note this explicitly in the design — the model is the starting point, risk assessment refines it.
7. **Validate against observed traffic.** After implementation, compare firewall/conduit logs against the designed conduits for a full production cycle. Every unexpected flow is either a missed requirement (update the design) or a violation (investigate). First-seen inter-level flows deserve SOC attention permanently.
8. **Maintain through change control.** New devices, vendor connections, and application integrations get a Purdue-level assignment and conduit review before connection. Audit level assignments annually — assets drift (that "temporary" Level 4 analytics feed into Level 2 becomes permanent) without governance.

## Expected outputs

- Purdue-level asset assignment register with borderline cases documented.
- As-is vs. target architecture diagrams showing level boundaries.
- Level 3.5 DMZ design with hosted boundary services.
- Inter-level conduit matrix (protocols, directions, endpoints) implemented in firewall policy.
- Change-control procedure for level assignments and new conduits.

## Pitfalls

- **Treating Purdue as a security control.** The model describes functional layers; it doesn't specify security requirements. Pair every level boundary with IEC 62443-derived requirements or you have an organized but unprotected network.
- **Level 3.5 as a checkbox.** A DMZ with permissive any-any rules between its tiers provides no mediation. Each DMZ transition needs its own allowlist.
- **Ignoring wireless and serial.** The model is usually drawn for Ethernet; plant Wi-Fi, cellular modems, and serial links bypass level boundaries entirely. Inventory all paths.
- **Safety lumped with control.** Failing to separate SIS from basic process control within Level 1 mixes safety and security risk in ways both disciplines regret.
- **Static model, dynamic plant.** Turnarounds, vendor visits, and new lines constantly add connections. Without change control, the Purdue diagram becomes historical fiction.

## References

- Purdue Enterprise Reference Architecture (ISA-95/IEC 62264 functional model) — via ISA
- NIST SP 800-82 Rev. 3, "Guide to OT Security" — https://csrc.nist.gov/publications/detail/sp/800-82/rev-3/final
- IEC 62443 series (zones and conduits refine Purdue levels) — via IEC/ISA
- MITRE ATT&CK for ICS — https://attack.mitre.org/techniques/ics/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
