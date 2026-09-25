---
skill_id: cyber_implementing_dragos_platform_for_ot_monitoring
name: OT Monitoring with the Dragos Platform
description: Deploy the Dragos Platform for OT network visibility, threat detection, and incident response.
risk: low
permissions: []
requires_confirmation: false
tags: [ot, monitoring]
version: 1.0.0
---
## Purpose
OT networks are blind spots for IT security tools: proprietary protocols (Modbus, DNP3, EtherNet/IP,
S7), fragile legacy devices that can't take agents or active scans, and process-aware context IT
analysts lack. The Dragos Platform provides OT-specific network monitoring: passive protocol
dissection, asset identification, threat detection with OT context, and playbooks for industrial
incidents. This playbook deploys it without disrupting operations.

## When to use
- Gaining visibility into OT network traffic and asset inventory for the first time.
- After OT security incidents or near-misses where lack of visibility hampered response.
- Meeting OT monitoring expectations (NERC CIP, TSA directives, IEC 62443, internal risk
  requirements).
- Building an OT SOC capability or extending the IT SOC into OT with proper context.
- As the detection layer for the OT security program (alongside segmentation and remote-access
  conduits).

## Prerequisites
- Network access design: SPAN/mirror ports or network taps at key OT aggregation points (agreed with
  OT network engineering — no inline deployment initially).
- Asset inventory seed: known controllers, HMIs, historians, and network diagrams to validate
  discovery.
- Defined OT crown jewels and process-critical systems (what matters most if compromised).
- IT/OT coordination: who owns the platform, who responds to alerts, and the escalation path between
  SOC and operations.
- Change control with operations: any deployment activity needs operations awareness and maintenance
  windows.

## Procedure
1. **Plan sensor placement with operations.** Identify choke points: core/distribution switches in
   each OT zone, DMZ boundaries, and remote-access ingress points. Prefer passive taps or SPAN —
   never inline on first deployment, and never on links where SPAN oversubscription could drop
   control traffic. Document placement rationale.
2. **Deploy sensors passively.** Install Dragos sensors (physical or virtual) receiving mirrored
   traffic. Verify: sensors see expected protocols, no impact on control traffic (coordinate with
   operations to confirm process stability), and time synchronization (NTP) for accurate event
   correlation.
3. **Baseline the OT environment.** Let the platform learn: asset discovery (controllers, HMIs,
   engineering workstations, network gear), protocol inventory, and communication baselines (who
   talks to whom, normally). Validate discovered assets against the seed inventory — unknowns get
   investigated, not ignored.
4. **Tune detections for OT reality.** Enable threat detections and tune for the environment:
   expected engineering activities (firmware uploads during maintenance windows), vendor remote
   sessions (approved vs. not), and protocol anomalies. OT false positives often look like attacks
   to IT analysts — involve OT engineers in tuning.
5. **Build OT-specific alert handling.** Route alerts to analysts with OT context; define severity:
   safety-impacting or process-control anomalies page immediately; reconnaissance and policy
   violations ticket. Every alert needs an OT-knowledgeable reviewer — pure-IT triage misreads OT
   events.
6. **Develop OT incident playbooks.** Write playbooks for: suspected controller compromise,
   ransomware in OT (IT/OT boundary), unauthorized engineering workstation activity, and malicious
   firmware changes. Include operations coordination steps, safety considerations, and the decision
   authority for process shutdown (operations owns that call — never the SOC alone).
7. **Integrate with IT SOC carefully.** Forward high-fidelity alerts to the IT SIEM with OT context
   attached, but keep OT raw data in the platform (volume and protocol specifics don't belong in the
   IT SIEM). Establish the joint escalation path and run a tabletop to prove it works.
8. **Track vulnerabilities with OT constraints.** Use the platform's vulnerability identification,
   but plan remediation around maintenance windows and vendor-certified patches — OT patching is
   slower and riskier than IT. Prioritize: internet-exposed OT, then safety-critical, then the rest.
   Compensating controls (segmentation, monitoring) cover what can't be patched promptly.
9. **Exercise regularly.** Quarterly: tabletop an OT incident scenario with IT + operations;
   annually: a live-fire exercise in a test lab if available. Verify alert-to-response times and the
   operations handoff. Untested OT response plans fail at the safety/operations boundary.
10. **Report OT security posture.** Metrics: asset discovery coverage and accuracy, detection counts
    by severity with disposition, mean time to triage OT alerts, vulnerability backlog with
    compensating-control coverage, and exercise results. Report to both security leadership and
    operations leadership — shared ownership needs shared visibility.

## Expected outputs
- Dragos sensors deployed passively at key OT choke points with operations sign-off.
- Validated OT asset inventory, protocol map, and communication baselines.
- Tuned detections with OT-aware alert handling and severity definitions.
- OT incident playbooks with operations coordination and safety decision authority.
- Quarterly exercises and OT posture reporting to security and operations leadership.

## Pitfalls
- Active scanning of OT: never run IT vulnerability scanners against control networks — fragile
  devices crash. Passive monitoring only, unless operations explicitly approves scoped active
  checks.
- Inline deployment first: start passive. Inline (IPS-style) in OT risks process disruption — only
  after extensive validation and operations approval.
- IT-only triage: OT alerts without OT context get misjudged (normal engineering looks like attacks;
  real attacks look like glitches). OT expertise in the loop, always.
- Ignoring safety: OT incidents have physical consequences. Response playbooks must include safety
  review and operations decision authority for any action affecting processes.
- Visibility without response: detecting threats in OT with no playbook or authority to act is just
  earlier awareness of the same outcome. Build response with operations from day one.

## References
- Dragos Platform documentation (deployment, detections, OT playbooks)
- NIST SP 800-82 Rev. 3 (OT security)
- IEC 62443 series (industrial automation security)
- CISA OT cybersecurity guidance and advisories
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
