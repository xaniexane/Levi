---
skill_id: cyber_investigating_ransomware_attack_artifacts
name: Investigating Ransomware Attack Artifacts
description: Collect and analyze ransomware artifacts to scope the intrusion and support recovery.
risk: low
permissions: []
requires_confirmation: false
tags: [ransomware, forensics, incident-response]
version: 1.0.0
---
## Purpose
This playbook guides forensic analysis of ransomware artifacts: identifying the variant, reconstructing the intrusion timeline, determining data theft, and producing the evidence needed for scoping, recovery prioritization, and reporting.

## When to use
- Ransomware has detonated or a ransom note is discovered.
- You need to answer: which variant, how did they get in, what did they touch, was data stolen.
- Supporting legal, insurance, and regulatory notification decisions with facts.

## Prerequisites
- Declared incident with an incident commander and preserved evidence (do not wipe and rebuild before collection).
- Forensic images or EDR telemetry from affected hosts; network logs covering the intrusion window.
- Threat intel on the suspected variant's TTPs and leak-site practices.

## Procedure
1. **Identify the variant.** Capture the ransom note text, encrypted file extensions/markers, and sample binaries; compare against known families via threat intel — variant determines decryptor availability and negotiation posture.
2. **Preserve before remediation.** Take forensic images of key hosts (initial access, domain controllers, backup servers); record hashes and chain of custody.
3. **Reconstruct initial access.** Work backward from detonation: phishing, exposed RDP/VPN, exploited edge device — corroborate with logs, not assumptions.
4. **Map lateral movement and privilege escalation.** Trace host-to-host movement, credential dumping, and persistence mechanisms across the timeline.
5. **Determine data theft.** Analyze staging directories, archive creation, and exfiltration (large outbound transfers, cloud uploads); assume breach of accessed sensitive data unless evidence shows otherwise.
6. **Assess backup and recovery state.** Document which backups were targeted, deleted, or encrypted; identify clean recovery points and rebuild order.
7. **Package findings.** Deliver a factual report: variant, timeline, scope of encryption and theft, root cause, and prioritized remediation — without speculation beyond the evidence.

8. **Check for double extortion.** Monitor the variant's leak site for your organization's data; publication changes legal notification obligations and negotiation dynamics.
9. **Harden the recovery environment.** Rebuild on isolated, patched infrastructure with new credentials before reconnecting to the network; re-infection during recovery is depressingly common.

## Expected outputs
- Variant identification with confidence and decryptor-availability assessment.
- Full intrusion timeline from initial access through detonation.
- Data-theft determination and recovery prioritization input.
- Example: timeline shows initial access via an unpatched edge device 23 days before detonation, lateral movement to the backup server on day 18, and 40GB exfiltrated on day 21 — driving both the recovery order and the notification decision.

## Pitfalls
- Rebuilding systems before forensic collection destroys the evidence you need.
- Paying or negotiating without understanding the variant and the attacker's actual leverage.
- Declaring "no data theft" from absence of evidence; check thoroughly before asserting it.

- Trusting a decryptor found on a random forum; only use decryptors from vetted sources (No More Ransom, vendor labs) and test on copies first.
- Communicating with the attacker from a monitored corporate account; use dedicated, controlled channels and involve legal counsel.

## References
- CISA StopRansomware Guide (cisa.gov/stopransomware).
- NIST SP 800-61 Rev. 2, Computer Security Incident Handling Guide.
- No More Ransom project (nomoreransom.org) — vetted decryptor repository.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
