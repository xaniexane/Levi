---
skill_id: cyber_implementing_continuous_security_validation_with_bas
name: Continuous Security Validation with BAS
description: Run breach and attack simulation continuously to validate that defenses actually work.
risk: low
permissions: []
requires_confirmation: false
tags: [testing, validation]
version: 1.0.0
---
## Purpose
Security controls decay: EDR rules get disabled, firewall rules drift, detections go stale — and
nobody notices until the incident. Breach and Attack Simulation (BAS) continuously executes safe,
simulated adversary techniques against your own environment and reports which ones your controls
stopped, detected, or missed. This playbook implements BAS as the continuous validation loop: assume
breach, test constantly, fix what fails.

## When to use
- Validating that EDR, SIEM, firewall, and email controls work as configured — not as assumed.
- After control changes (new EDR, SIEM migration, firewall overhaul) to prove effectiveness.
- Meeting continuous-testing expectations (threat-informed defense, SOC 2, regulatory exams).
- Prioritizing security investments: BAS shows which controls actually stop techniques vs. which are
  shelfware.
- Between pentests: BAS provides continuous signal; pentests provide periodic depth.

## Prerequisites
- A BAS platform (AttackIQ, Cymulate, SafeBreach, Picus, or open-source atomic-style tooling)
  licensed/scoped for the environment.
- Defined scope and safety boundaries: which systems, networks, and techniques are in scope; what's
  off-limits (production databases, safety systems).
- SOC and IT awareness: simulations generate alerts — the SOC must know what's simulated vs. real
  (or run some blind, deliberately).
- Mapped controls inventory: which EDR, firewall, proxy, email gateway, and SIEM use cases claim to
  cover which techniques.
- Change control for the BAS platform itself: new simulation content reviewed before running in
  production.

## Procedure
1. **Scope and authorize explicitly.** Document: in-scope assets/networks, allowed technique
   categories (mapped to MITRE ATT&CK), blackout windows (change freezes, business-critical
   periods), and emergency stop procedures. Get written authorization — BAS executes attack
   techniques, and authorization is what separates it from an incident.
2. **Start with a baseline assessment.** Run the platform's baseline scenarios across the kill chain
   (initial access through exfiltration). Record per-technique results: prevented, detected,
   alerted, missed. This baseline is the "before" picture and the prioritization input.
3. **Map results to controls.** For each missed technique, identify the responsible control: was the
   EDR policy misconfigured, the SIEM use case missing, the firewall rule too broad? Assign findings
   to control owners with evidence (simulation ID, technique, expected vs. actual outcome).
4. **Fix, then re-run.** Remediation owners tune controls; BAS re-runs the failed scenarios to
   verify the fix. A finding isn't closed until the re-run shows prevention or detection. This
   closed loop is the entire value proposition.
5. **Automate continuous validation.** Schedule: daily lightweight scenarios (critical techniques),
   weekly full kill-chain, and event-triggered runs (after EDR policy changes, firewall updates, new
   SIEM content). Validation must be as continuous as the drift it catches.
6. **Run purple-team exercises on gaps.** For techniques BAS shows as missed, run collaborative
   purple-team sessions: red executes, blue tunes detections live, both document. BAS finds the
   gaps; purple team closes the hard ones.
7. **Vary realism deliberately.** Mix: known simulations (SOC expects them — tests control
   function), blind simulations (SOC doesn't know — tests detection and response process), and
   threat-informed scenarios (emulate specific actors/sectors relevant to your threat model). Each
   tests something different.
8. **Track security-control effectiveness metrics.** Report: prevention rate and detection rate per
   technique category and per control, mean time to fix failed validations, and trend over time.
   These metrics justify control investments with evidence instead of fear.
9. **Integrate with change management.** Require BAS validation after significant control changes
   before declaring them complete. New EDR rollout isn't done when deployed — it's done when BAS
   confirms it stops the techniques it claims to.
10. **Govern the program.** Quarterly review: coverage (which ATT&CK techniques are validated vs.
    not), persistent gaps and their risk acceptance, simulation safety record, and roadmap (new
    scenarios for emerging threats). Annual: reassess scope and platform effectiveness.

## Expected outputs
- Authorized BAS scope with safety boundaries and emergency procedures.
- Baseline assessment mapped per-technique to control outcomes.
- Closed-loop remediation: findings fixed and re-validated, not just reported.
- Continuous schedules (daily/weekly/event-triggered) plus purple-team exercises.
- Control-effectiveness metrics trended and reported quarterly.

## Pitfalls
- Running BAS without written authorization: simulated attacks without clear authorization create
  legal and HR exposure. Paper it first.
- Testing the SOC blind without coordination: surprise simulations during real incidents cause
  chaos. Coordinate, or explicitly designate blind windows with safeguards.
- Treating BAS as a pentest replacement: BAS validates known techniques continuously; pentests find
  novel paths. Both, not either.
- Findings without owners: "technique missed" with no control owner assigned is a report, not
  remediation. Map every technique to a control and an owner.
- Unsafe simulation content: techniques affecting production data or safety systems must be excluded
  or run in isolated labs. Review new content before production runs.

## References
- MITRE ATT&CK (technique taxonomy BAS scenarios map to)
- CISA guidance on threat-informed defense and continuous validation
- NIST SP 800-53 CA-8 (penetration testing) and SI-4 (monitoring) — validation mappings
- Vendor documentation for the chosen BAS platform (scenario library, safety controls)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
