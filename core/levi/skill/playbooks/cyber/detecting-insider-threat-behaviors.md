---
skill_id: cyber_detecting_insider_threat_behaviors
name: Detecting Insider Threat Behaviors
description: Detect malicious insider activity with behavioral analytics across identity, data, and HR signals.
risk: info
permissions: []
requires_confirmation: false
tags: [insider-threat, detection, uepa]
version: 1.0.0
---
## Purpose

Detect the behavioral precursors and actions of malicious insiders — sabotage, data theft, fraud, and espionage — by fusing identity, data-access, and HR signals into behavioral analytics. Insiders don't hack in; they log in. Detection must focus on what they do with legitimate access.

## When to use

- Building an insider-threat program (detection component).
- Tuning UEBA/UBA for insider scenarios.
- Investigating concerning employee behavior referred by management or HR.
- Monitoring high-risk populations (privileged users, departing employees, contractors).

## Prerequisites

- Centralized telemetry: identity logs, data-access logs, DLP, EDR, badge/physical access where available.
- HR partnership with defined information-sharing boundaries (what HR can share, when).
- Legal review of monitoring scope and employee-privacy obligations in your jurisdictions.
- Baseline of normal behavior per role — insider detection is deviation-from-self, not deviation-from-average.

## Procedure

1. **Define the insider-threat scenarios.** Scope the program to concrete scenarios: data theft (IP, customer data), sabotage (deletion, logic bombs), fraud (financial manipulation), and espionage (long-term collection). Each scenario gets its own behavioral indicators — generic "anomaly detection" without scenarios produces unactionable alerts.
2. **Build behavioral baselines per individual.** For each monitored user, baseline: working hours, accessed systems and data, download/upload volumes, and application usage. Insider detection compares the person to their own history — the malicious insider's actions deviate from their own norms, not from the company average.
3. **Monitor scenario-specific indicators.** Data theft: mass downloads, access outside role/projects, personal-cloud uploads. Sabotage: mass deletions, backup tampering, unusual administrative actions before departure. Fraud: financial-system access outside duties, approval-pattern anomalies. Espionage: long-term broad collection, access to compartmented data without need.
4. **Fuse HR and behavioral signals.** The strongest insider detections combine: HR triggers (resignation, PIP, disciplinary action, contractor end-date) with behavioral changes (increased downloads, off-hours access, new data areas). Build compound alerts — HR signal alone isn't malice, behavior alone isn't context, together they're the case.
5. **Detect the pre-incident indicators.** Research shows insiders often display precursors: policy violations, conflicts with management, financial stress indicators (where legally observable), and disgruntlement expressed in communications (where monitoring is authorized). These feed risk scoring, not standalone alerts — they're context for the behavioral detections.
6. **Investigate with care and legality.** Insider investigations demand: legal counsel involved from the start, evidence preserved with chain of custody, minimal necessary monitoring expansion (no fishing expeditions), HR partnership for any personnel actions, and strict confidentiality (false accusations destroy trust and create liability). Document every investigative step.
7. **Respond through the proper channels.** Confirmed insider threats resolve via HR/legal processes, not just technical ones: access revocation coordinated with HR, evidence handoff to legal, law-enforcement referral where appropriate, and lessons-learned feeding back into hiring, access-review, and monitoring practices. The technical response (revoke, preserve) is the easy part; the personnel process is the real procedure.

## Expected outputs

- Scenario-scoped insider-threat detection with per-individual behavioral baselines.
- HR-fused compound alerts with risk scoring from behavioral and precursor indicators.
- A legal/HR-governed investigation and response workflow with evidence procedures.

## Pitfalls

- Monitoring without legal review — employment and privacy law varies by jurisdiction; get counsel first.
- Deviation-from-average instead of deviation-from-self — the insider's baseline is their own history.
- Alerting on HR signals alone — a PIP isn't a crime; it's context for behavioral investigation.
- Fishing expeditions — expanding monitoring without predicate destroys trust and may violate policy.
- Treating it as purely technical — the response is HR/legal; the technology is the detection layer.

## References

- CERT Insider Threat Center (CMU SEI) — behavioral indicators and case research
- NITTF (National Insider Threat Task Force) guidance
- NIST SP 800-53 PM-12 / PS family (insider threat program, personnel security)
- CISA insider-threat mitigation guidance
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
