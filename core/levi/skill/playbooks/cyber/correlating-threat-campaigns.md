---
skill_id: cyber_correlating_threat_campaigns
name: Correlating Threat Campaigns
description: Fuse multi-source intelligence into campaign-level pictures of adversary activity with confidence grading.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intel, analysis, soc]
version: 1.0.0
---
## Purpose

Move from isolated IOCs to campaigns: cluster related incidents, alerts, and intelligence into named adversary efforts with timelines, infrastructure, TTPs, and targeting — so leadership and defenders act on the campaign, not the indicator.

## When to use

- Multiple incidents or alerts share infrastructure, tooling, or targeting and may be one actor.
- Building threat profiles for intelligence reporting or briefing executives.
- Prioritizing defenses against the adversaries actually targeting your sector.
- Feeding long-term detection engineering with campaign-level TTPs rather than expiring IOCs.

## Prerequisites

- Access to internal telemetry (SIEM alerts, incident reports, EDR data) and external intel feeds (commercial, ISAC, open-source).
- A threat-intel platform or structured store (MISP, OpenCTI, or a governed spreadsheet at minimum) with STIX-friendly object modeling.
- Defined confidence levels and a naming convention for campaigns before analysis starts.
- Analyst time protected from the daily alert queue — campaign analysis dies under constant interruption.

## Procedure

1. **Collect candidate activity.** Pull incidents, high-fidelity alerts, and intel reports from the last 6–12 months that share any pivot: IPs, domains, hashes, email senders, targeted business units, or malware families. Cast wide initially; filtering comes later.
2. **Pivot on infrastructure and tooling.** For each candidate, expand: passive DNS on domains, WHOIS/registration patterns, certificate overlaps, and malware family/tooling (e.g. same custom loader, same RMM tool). Shared infrastructure registered in the same window with the same patterns is strong campaign evidence.
3. **Cluster by TTPs and targeting.** Map each incident's techniques to MITRE ATT&CK and compare sequences, not just individual techniques — the same three-technique chain (spearphish → living-off-the-land binary → cloud exfil) across victims is a campaign fingerprint. Overlay targeting: same sector, same region, same role types phished.
4. **Build the campaign timeline.** Order all events chronologically: first reconnaissance, first intrusion, infrastructure stand-up, follow-on intrusions. Gaps are informative — infrastructure built months before first use suggests a planned campaign, not opportunism.
5. **Grade confidence and name it.** Assign each cluster a confidence level (low/medium/high) based on the number of independent pivots supporting it, and give the campaign an internal name. Document dissenting evidence explicitly — the IOC that doesn't fit may be the next campaign.
6. **Extract campaign-level detections.** From the TTP clusters, write detections that survive IOC churn: the technique chain, the tooling behaviors, the targeting pattern. Push these to the SOC as hunt hypotheses and permanent detection content, not one-off alerts.
7. **Produce the campaign report.** One page for leadership (who, what, impact, what we're doing), plus an analyst appendix (timeline, infrastructure, TTPs, confidence, gaps). Distribute internally and, where appropriate, to your ISAC — campaign intel shared early protects the sector.
8. **Maintain and re-correlate.** Revisit open campaigns quarterly: new incidents get checked against campaign pivots first, and dormant campaigns get closed with a summary. Campaigns are living analysis, not one-time reports.

## Expected outputs

- Named, confidence-graded campaigns with timelines, infrastructure maps, and TTP clusters.
- Campaign-level detections and hunt hypotheses in the SOC backlog.
- A leadership one-pager and analyst appendix per campaign; quarterly re-correlation cadence.

## Pitfalls

- Naming a campaign on a single shared IP — shared hosting and VPN exit nodes create false clusters.
- Confusing tooling overlap with actor identity — the same commodity RAT is used by dozens of groups.
- Analysis paralysis: waiting for perfect attribution before acting on the TTPs, which are actionable now.
- Forgetting to document what doesn't fit — the excluded evidence is where the next campaign hides.
- Letting campaign reports go stale — an unmaintained campaign file is archaeology, not intelligence.

## References

- MITRE ATT&CK — technique sequencing for campaign clustering
- STIX 2.1 / TAXII specifications for structured campaign objects
- NIST SP 800-150 (Guide to Cyber Threat Information Sharing)
- Mandiant / CISA campaign reporting examples for report structure
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
