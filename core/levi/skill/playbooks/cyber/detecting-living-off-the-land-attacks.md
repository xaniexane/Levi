---
skill_id: cyber_detecting_living_off_the_land_attacks
name: Detecting Living-off-the-Land Attacks
description: Detect adversaries abusing legitimate system tools (LOLBins) instead of malware.
risk: low
permissions: []
requires_confirmation: false
tags: [lolbins, detection, endpoint]
version: 1.0.0
---
## Purpose

Living-off-the-land (LotL) attacks use built-in tools — PowerShell, WMI, PsExec, certutil, mshta — so there is no malware to signature. This playbook gives defenders a behavior-based approach: which native tools matter most, what malicious usage looks like versus legitimate administration, and how to build detections that survive in real environments.

## When to use

- EDR malware detections are quiet but you suspect hands-on-keyboard activity.
- Threat intel describes an actor using only native tools and you need coverage.
- Red team / purple team exercises showed your controls miss LOLBin abuse.
- You need to reduce LOLBin false positives without blinding yourself.

## Prerequisites

- Endpoint telemetry with command lines and parent/child process relationships: Sysmon (Event IDs 1, 3, 7, 11) or an EDR with equivalent data.
- A list of dual-use binaries relevant to your OS mix (Windows LOLBins plus Linux/macOS equivalents).
- Known-good baselines: which teams legitimately use PowerShell remoting, WMI, PsExec, BITS, certutil, and from where.
- MITRE ATT&CK mapping of LOLBins to techniques for prioritizing coverage.

## Procedure

1. Prioritize by attacker utility, not by list size. Start with the LOLBins most abused in real intrusions: script interpreters (powershell, wscript, mshta), remote execution (wmic, psexec, winrs, schtasks), download/transfer (certutil, bitsadmin, curl), and credential/persistence helpers (rundll32, regsvr32, msbuild). Cover these deeply before expanding to the long tail.
2. Detect on behavior + context, never the binary name alone. powershell.exe running is normal; powershell.exe with encoded commands, spawned by winword.exe, downloading from an external IP, is not. Build rules on: suspicious parent processes, encoded/obfuscated arguments, network connections from non-browser binaries, and LOLBins spawning other LOLBins.
3. Hunt parent/child anomalies systematically. Query for: Office applications spawning script interpreters or LOLBins; LOLBins spawning from web servers or user download folders; rundll32/regsvr32 with URLs or script-like arguments; and mshta/certutil making network connections. Each pattern gets its own tuned rule, not one mega-rule.
4. Baseline legitimate administrative use and carve it out precisely. Work with IT to document: deployment tools using PsExec/WinRM (by service account and source host), admin scripts using WMI, and backup tools using BITS. Suppress by (parent process + user + source host), never by binary name alone — blanket exclusions are attacker gifts.
5. Correlate LOLBin chains into incidents. A single certutil download may be ambiguous; certutil download → rundll32 execution → WMI persistence within an hour on one host is an incident. Build correlation rules that group LOLBin sequences per host in time windows.
6. Constrain the tools where business allows. Application control (WDAC/AppLocker) in audit-then-enforce mode, Constrained Language Mode for PowerShell, disabling unused interpreters (mshta, wscript) via policy, and removing local admin rights all shrink the LotL surface without breaking documented admin workflows.

## Expected outputs

- Prioritized LOLBin list mapped to ATT&CK techniques with per-tool detection rules.
- Tuned rules with documented legitimate-use exclusions (parent+user+host, not binary-only).
- LOLBin-chain correlation logic and incident examples.
- Hardening recommendations: PowerShell Constrained Language Mode, AppLocker/WDAC, interpreter disablement — with business-impact notes.

## Pitfalls

- Blocking LOLBins by name breaks legitimate administration — always audit-mode first and carve out documented use.
- Encoded PowerShell is sometimes legitimate (SCCM, admin scripts); investigate the parent and purpose, not just the encoding flag.
- Attackers rename LOLBins or use lesser-known ones — behavior rules (parent/child, network) outlast name rules.
- One mega-rule for 'all LOLBins' produces unactionable alerts; one tuned rule per high-value pattern wins.
- Linux/macOS environments have their own native-tool abuse (curl, python, cron, launchd) — don't apply a Windows-only list.

## References

- MITRE ATT&CK T1218 (System Binary Proxy Execution) — https://attack.mitre.org/techniques/T1218/; LOLBAS project documentation (lolbas-project.github.io) for binary behavior reference; NIST SP 800-53 CM-7 (least functionality)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
