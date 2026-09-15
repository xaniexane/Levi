---
skill_id: cyber_implementing_ot_incident_response_playbook
name: Implementing OT Incident Response Playbook
description: Build an OT-specific incident response playbook — roles, safety-first containment, forensic preservation on live processes, and recovery without reintroducing the threat.
risk: info
permissions: []
requires_confirmation: false
tags: [ot, ics, incident-response]
version: 1.0.0
---
## Purpose

Prepare for the incident where IT playbooks get people hurt: in operational technology, containment actions (isolating a network segment, rebooting a host) can trip processes, damage equipment, or endanger safety. This playbook defines OT incident response with safety as the overriding priority — roles spanning security and operations, containment options graded by process impact, forensic preservation that doesn't stop production, and recovery validated before restart.

## When to use

- Standing up incident response capability for plants, utilities, pipelines, or manufacturing.
- Adapting an IT-centric IR plan that currently treats OT as "just more servers."
- Meeting IEC 62443-2-1 incident response or NERC CIP-008 requirements.
- After a near-miss or tabletop reveals that nobody knows who can authorize isolating a control network.
- Integrating OT into the enterprise SOC's detection and escalation paths.

## Prerequisites

- OT asset inventory with Purdue-level mapping and identification of safety-critical systems (SIS, emergency shutdown).
- Network architecture documentation: zones, conduits, and the actual isolation points available.
- Defined authority: who (by role, reachable 24/7) can authorize process-affecting containment — this must be operations leadership, not the SOC alone.
- Forensic tooling suitable for OT (write-blocked imaging, OT-aware network capture, memory acquisition tools tested against control hosts).
- Communication plans that work when OT networks are isolated (out-of-band phones, runners — assume the compromised network carries your VoIP).

## Procedure

1. **Establish the unified command structure.** Define the OT incident team: incident commander, operations/process lead (authority on process impact), safety officer (veto power over any action affecting safety), OT security analyst, IT security liaison, vendor contacts, and legal/regulatory. Publish the call tree with 24/7 reachability and test it — the first time you need the process engineer should not be during the incident.
2. **Define severity levels with OT consequences.** Extend IT severity scales with process impact: S1 = safety system affected or production halt required; S2 = control system compromise without immediate safety impact; S3 = IT/DMZ compromise with OT exposure. Severity drives who gets woken and what containment authority is pre-delegated.
3. **Pre-authorize containment playbooks graded by impact.** For each scenario (ransomware in the OT DMZ, suspicious traffic to PLCs, compromised engineering workstation), document containment options from least to most disruptive: block at the conduit firewall → disable remote access → isolate the DMZ → isolate the control network segment → controlled shutdown. Each option lists the process impact, who authorizes it, and the safety checks required first. Never improvise isolation of a live control network.
4. **Preserve forensics without stopping the process.** Prioritize memory capture and network-flow/packet evidence from live systems (order of volatility applies doubly when rebooting means downtime); image engineering workstations via write-blocked methods during maintenance windows; preserve historian and firewall logs immediately (extend retention on detection). Document chain of custody adapted for OT constraints.
5. **Eradicate with OT realities in mind.** Removal may require vendor involvement (proprietary firmware, safety recertification after changes), maintenance windows for reimaging, and password/credential resets across shared OT accounts. Validate that eradication is complete before recovery — reintroducing a compromised PLC program restarts the incident.
6. **Recover in the safe sequence.** Restore from known-good backups (controller programs, HMI configurations — version-controlled and offline), verify integrity (hashes, logic comparisons against golden images), bring systems up in dependency order, and run process-safety checks before resuming production. Involve the safety officer in the go/no-go decision explicitly.
7. **Notify per regulatory obligations.** Map notification requirements in advance: NERC CIP-008/E-ISAC for the power sector, CISA for critical infrastructure, sector ISACs, regulators, and customers. Pre-draft notification templates with the fields each requires; during the incident you fill in facts, not invent process.
8. **Exercise relentlessly.** Run tabletop exercises quarterly with operations in the room, and full simulations (including actually isolating a non-production segment) annually. Every exercise must test the authorization chain for disruptive containment — that is the decision that fails in real incidents.

## Expected outputs

- OT incident response plan with unified command structure and 24/7 call tree.
- Severity scale incorporating process/safety impact.
- Graded containment playbooks with pre-authorized actions and safety checks.
- Forensic preservation procedures adapted to live OT systems.
- Recovery sequence with safety go/no-go gates; regulatory notification matrix; exercise schedule and after-action reports.

## Pitfalls

- **IT playbook applied to OT.** "Isolate the host immediately" is correct for a laptop and potentially catastrophic for a safety controller. OT containment always weighs process impact first.
- **No pre-authorized containment.** Debating who can isolate the control network during the incident wastes the hours that matter. Pre-authorize with clear triggers.
- **Forensics vs. uptime conflicts unplanned.** Operations will (rightly) prioritize restoring production; without pre-agreed forensic preservation steps, evidence is destroyed in the rush. Agree the minimum evidence set in advance.
- **Vendor dependence discovered mid-incident.** Proprietary systems may need vendor engineers for recovery; identify contracts, SLAs, and emergency contacts before you need them.
- **Skipping the safety veto.** Every containment and recovery action affecting the process needs safety review. The safety officer's veto is absolute — write that into the plan, not just the culture.

## References

- NIST SP 800-82 Rev. 3, "Guide to OT Security" (incident response section) — https://csrc.nist.gov/publications/detail/sp/800-82/rev-3/final
- NIST SP 800-61 Rev. 2, "Computer Security Incident Handling Guide" — https://csrc.nist.gov/publications/detail/sp/800-61/rev-2/final
- CISA ICS incident response resources — https://www.cisa.gov/topics/industrial-control-systems
- IEC 62443-2-1 (IACS security program including incident response) — via IEC/ISA
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
