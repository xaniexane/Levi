---
skill_id: cyber_detecting_living_off_the_land_with_lolbas
name: Detecting Living-off-the-Land with LOLBAS
description: Operationalize the LOLBAS project as a detection knowledge base for native-binary abuse.
risk: low
permissions: []
requires_confirmation: false
tags: [lolbas, detection, threat-intel]
version: 1.0.0
---
## Purpose

This playbook focuses specifically on the LOLBAS project (Living Off The Land Binaries, Scripts and Libraries) as a defensive resource: how to consume its per-binary documentation, map it to your environment's telemetry, and turn it into prioritized, low-noise detections rather than a 150-row spreadsheet nobody uses.

## When to use

- You know about LOLBAS but haven't turned it into working detections.
- Your team debates which LOLBin alerts to build first — you need a prioritization method.
- A new LOLBAS entry appears and you need to assess your exposure quickly.
- Auditing whether existing SIEM/EDR rules cover documented LOLBAS abuse patterns.

## Prerequisites

- Access to the LOLBAS project documentation (per-binary pages describing functions, arguments, and ATT&CK mappings).
- Endpoint telemetry with full command lines (Sysmon/EDR) to match against documented abusive arguments.
- An inventory of which LOLBAS-listed binaries actually exist in your fleet (OS versions and installed features vary).
- A tracking method (ticket queue or detection backlog) for per-binary coverage status.

## Procedure

1. Inventory your exposure first. Enumerate which LOLBAS-listed binaries, scripts, and libraries are present on your standard builds. A binary that isn't installed needs no detection — this step alone usually cuts the list dramatically and focuses effort where the tools actually exist.
2. Consume LOLBAS entries as detection specs, not reading material. For each in-scope binary, extract: the ATT&CK technique(s) it maps to, the specific abusive command-line patterns documented, and the legitimate functions to avoid breaking. Translate each abusive pattern into a telemetry query against your command-line data.
3. Prioritize with a simple scoring model. Rank binaries by: (a) observed in-the-wild abuse frequency (threat intel), (b) presence in your environment, (c) legitimate-use volume (high legitimate use = harder detection, needs tighter context). Build detections for high-abuse/low-legitimate-use binaries first — they give the best precision per effort.
4. Write argument-aware rules. LOLBAS entries document the exact flags attackers use (e.g., specific download, execute, or bypass arguments). Rule on binary + argument pattern + parent-process context, and test each rule against 30 days of history to measure the legitimate-use hit rate before enabling alerts.
5. Handle libraries and scripts, not just EXEs. LOLBAS covers DLLs (rundll32-style proxying), scripts (PS1/JS/VBA), and other execution vectors. Ensure your telemetry captures script-block logging (PowerShell Script Block Logging, Event ID 4104) and DLL loads where relevant — command-line-only visibility misses script-based abuse.
6. Maintain the mapping. Review new and updated LOLBAS entries on a cadence, mark coverage per binary (detected / partially / gap), and feed gaps into the detection backlog with the same priority scoring. Treat the LOLBAS list as a living control-assessment framework, not a one-time project.

## Expected outputs

- Environment-specific LOLBAS inventory: present binaries, scripts, libraries per build.
- Per-binary detection coverage matrix with priority scores and rule links.
- Argument-aware detection rules tested against historical telemetry.
- Recurring review cadence for new/updated LOLBAS entries.

## Pitfalls

- Trying to cover every LOLBAS entry equally guarantees burnout — prioritize by in-the-wild abuse and your exposure.
- Command-line-only telemetry misses script and DLL abuse; enable script-block and image-load logging too.
- Rules on binary name alone either break admins or get blanket-excluded — always include arguments and parent context.
- LOLBAS documents known abuse; attackers innovate — pair list-driven rules with behavioral anomaly hunting.
- Legitimate-use baselines differ per organization; someone else's exclusion list is not yours.

## References

- LOLBAS project (lolbas-project.github.io) — per-binary documentation; MITRE ATT&CK technique pages referenced per entry; Microsoft Learn: Sysmon and PowerShell Script Block Logging configuration
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
