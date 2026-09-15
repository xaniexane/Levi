---
skill_id: cyber_detecting_insider_data_exfiltration_via_dlp
name: Detecting Insider Data Exfiltration via DLP
description: Detect insider data theft with DLP policies, behavioral baselines, and egress monitoring tuned to data-movement patterns.
risk: info
permissions: []
requires_confirmation: false
tags: [dlp, insider-threat, detection]
version: 1.0.0
---
## Purpose

Catch insiders exfiltrating data — the departing employee, the compromised account, the malicious contractor — using DLP policies tuned to actual data-movement patterns, not just keyword matching. Insider exfiltration is a behavior problem as much as a content problem.

## When to use

- Building or tuning DLP for insider-threat detection.
- Investigating suspected data theft by an employee or contractor.
- Monitoring high-risk populations (departing employees, privileged users, contractors).
- Validating that DLP covers all egress channels (not just email).

## Prerequisites

- DLP deployed across egress channels: email, web upload, cloud sync, removable media, printing.
- Data classification (what's sensitive, where it lives) — DLP without classification is keyword guessing.
- Baseline of normal data movement per role (sales downloads CRM data; that's their job).
- Legal/HR partnership: insider investigations have employment-law and privacy constraints — establish the process before the incident.

## Procedure

1. **Classify data before writing policies.** Identify crown-jewel data: source code, customer PII, financials, M&A documents, trade secrets. Tag or fingerprint it (document fingerprinting, exact-data-match for structured data). DLP policies anchored to real data classifications outperform generic keyword rules by an order of magnitude.
2. **Baseline normal data movement per role.** Record per role: typical download volumes, normal destinations (which cloud services, which external partners), and normal hours. The insider's exfiltration stands out against their own baseline — a salesperson downloading the entire CRM the week before resigning is the pattern, not the download itself.
3. **Monitor all egress channels.** Cover: email (attachments, large sends to personal addresses), web uploads (file-sharing sites, personal cloud storage), corporate cloud sync (mass downloads from SharePoint/Drive), removable media (USB writes of sensitive files), and printing (bulk printing of sensitive documents). Attackers use the unmonitored channel — enumerate them all and close the gaps.
4. **Detect exfiltration behaviors.** Alert on: mass downloads preceding resignation (integrate with HR termination feeds — the highest-risk window), access to data outside the user's role or projects, downloads at unusual hours, use of personal cloud storage or USB on sensitive hosts, and data staging (large collections in temp folders or archives before exfiltration).
5. **Correlate with HR and identity signals.** Join DLP alerts with: resignation/termination notices, performance-improvement plans, contractor end dates, access reviews showing excessive permissions, and concurrent policy violations. The HR signal plus the DLP signal is the insider-threat detection — neither alone is sufficient.
6. **Investigate with legal and HR from the start.** Insider investigations require: legal review of monitoring scope (jurisdiction-dependent), HR partnership for interviews, evidence preservation with chain of custody, and no tipping off the subject prematurely. Define the investigation workflow in peacetime — the first insider case is not the time to discover the legal constraints.
7. **Respond proportionally and preserve evidence.** On confirmation: preserve all evidence (forensic images, logs, DLP alerts) before confronting, revoke access per HR/legal guidance, assess the full scope (what data, where did it go, who received it?), and pursue legal remedies where appropriate. Then fix the systemic issue: was it excessive access, missing DLP coverage, or a process failure?

## Expected outputs

- Data classification with fingerprinted crown jewels and role-based movement baselines.
- Multi-channel DLP monitoring (email, web, cloud, USB, print) with HR-feed correlation.
- A legal/HR-partnered investigation workflow with evidence-preservation procedures.

## Pitfalls

- DLP without classification — keyword rules generate noise and miss the real data.
- Monitoring without legal review — insider investigations have privacy and employment-law constraints.
- Ignoring the HR signal — the resignation feed is the most predictive insider indicator.
- Covering email but not USB/cloud — the exfiltration moves to the unmonitored channel.
- Tipping off the subject — premature confrontation destroys the investigation and the evidence.

## References

- NIST SP 800-53 MP-5 / SC-7 (media protection, boundary protection)
- CISA / NITTF insider-threat guidance
- CERT Insider Threat Center research (behavioral indicators)
- DLP vendor documentation for policy design (fingerprinting, EDM)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
