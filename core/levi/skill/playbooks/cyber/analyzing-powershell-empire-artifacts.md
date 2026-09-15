---
skill_id: cyber_analyzing_powershell_empire_artifacts
name: Analyzing PowerShell Empire Artifacts
description: Detect Empire framework residue: stagers, modules, and logging artifacts.
risk: low
permissions: []
requires_confirmation: false
tags: [malware-analysis, windows]
version: 1.0.0
---
# Analyzing PowerShell Empire Artifacts

## Purpose

Identify and analyze remnants of PowerShell Empire (and its forks) on Windows hosts and in logs — agents, launchers, stagers, and module activity — to scope an intrusion that used this post-exploitation framework.

## When to use

- EDR/Sysmon shows PowerShell with encoded commands, and you suspect Empire rather than generic malicious PowerShell.
- Hunting historically: Empire's default artifacts are distinctive and searchable.
- Scoping: finding every host where an Empire agent ran.

## Prerequisites

- Written authorization; chain-of-custody for any disk/memory images.
- Access to PowerShell logs (Script Block Logging, Module Logging, transcription), Sysmon/EDR telemetry, and proxy logs.
- A lab copy of Empire's source is useful for artifact reference — obtain from the public archived repository, never from an attacker's infrastructure.
- Familiarity with Empire's defaults: default user agent, default staging URIs, default profile names.

## Procedure

1. Search PowerShell Script Block Logging (Event ID 4104) for Empire's distinctive strings: `Invoke-Empire`, `New-Empire`, default staging keys, and the framework's characteristic function names. Start broad, then narrow.
2. Look for Empire launcher patterns in process command lines (Sysmon Event ID 1, Security 4688):
   `powershell -NoP -sta -NonI -W Hidden -Enc <base64>` — decode the base64 and check for the stager's `System.Net.WebClient` download cradle and Empire's launcher stub.
3. Check the default network indicators in proxy/firewall logs: Empire's default profile uses URIs like `/admin/get.php`, `/news.php`, `/login/process.php` with a distinctive default User-Agent — but assume customized profiles exist and pivot on behavior (beaconing intervals) too.
4. Examine the registry and filesystem for persistence Empire commonly uses: Run keys, WMI event subscriptions, scheduled tasks, and startup-folder LNKs pointing at encoded PowerShell.
5. Review the agent's working artifacts: Empire agents stage modules in memory, so check memory dumps (Volatility `windows.malfind`, `windows.cmdline`) for agent code on hosts where the process is gone but logs remain.
6. Extract the agent configuration from a recovered launcher: decode the base64, pull the C2 host/port, delay/jitter, and profile — these become high-confidence IOCs.
7. Determine agent capabilities used: search logs for Empire module names (`Invoke-Mimikatz`, `Get-Keystrokes`, `Invoke-Portscan`, lateral-movement modules) to understand what the attacker did, not just that they were present.
8. Map each agent to its C2 server and first/last beacon from proxy logs; build the per-host timeline of agent activity.
9. Hunt laterally: search the fleet's EDR/Sysmon for the same launcher patterns, C2 domains, and module strings to find every compromised host.
10. Correlate with authentication logs for the lateral movement Empire performed (WMI, PsExec-style, DCOM) to distinguish agent spread from legitimate admin activity.
11. Check for Empire's default HTTPS listener certificate in network captures: default Empire HTTPS uses a recognizable self-signed certificate — extract and fingerprint it as an additional IOC.
12. If an Empire server was seized, parse its SQLite database in the lab: agent tasking history there reconstructs the full operator timeline.
13. Distinguish Empire from its forks (Starkiller, SilentTrinity) by their distinct default strings before attributing the framework.
14. Extract the agent's delay, jitter, and kill-date from the launcher: these parameters distinguish Empire from lookalike custom implants.
15. Review PowerShell Module Logging (Event ID 4103) alongside 4104: Empire's module loads appear here even when script blocks arrive fragmented.
16. Check memory dumps of long-dead agents for the default staging key: it sometimes survives in unallocated process memory.
17. On a seized Empire server, list listeners: each listener maps a port to a profile — every one is a separate detection opportunity.
18. Review the obfuscation settings used: launcher obfuscation changes appearance but not the decoded behavior — decode, don't eyeball.
19. Map the agent kill-date: agents with kill-dates in the past may linger — verify they're actually dead.
20. Document the C2 profile as structured data (URIs, headers, user agent) for SIEM ingestion.
21. Preserve launcher samples and logs with hashes; document decoded configurations in the case file.
22. Remediation must include killing agents, removing persistence, blocking C2 at egress, and rotating credentials the agent could have harvested.

## Key tools & commands

- Windows Event Viewer / `wevtutil qe Microsoft-Windows-PowerShell/Operational` — Script Block Logging (4104).
- Sysmon Event IDs 1 (process create), 3 (network), 7 (image load) — launcher and agent telemetry.
- `Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-PowerShell/Operational'; Id=4104}` — scripted 4104 review.
- Base64 decoders (`[Convert]::FromBase64String` in a lab PowerShell, or Python `base64`) — launcher decoding.
- Proxy/firewall log search — C2 URI and beaconing analysis.
- `sqlite3 empire.db` — parsing a seized Empire server database in the lab.
- Wireshark certificate extraction — fingerprinting the default Empire HTTPS listener cert.
- Empire's public archived source — reference for default strings and profiles (read-only, lab use).
- Volatility (`windows.cmdline`, `windows.malfind`) — in-memory agent remnants.

## Expected outputs

- Confirmed Empire (or fork) identification with version indicators.
- Decoded launcher configurations: C2, delay/jitter, profile.
- Per-host agent timelines and module-usage inventory.
- Fleet-wide hunt results: all hosts with Empire artifacts.
- Seized server-database findings (agent tasking history).
- Framework fork determination (Empire vs. Starkiller/SilentTrinity).
- IOCs (C2, URIs, user agents) and detection rules.

## Pitfalls

- Relying only on default URIs/user agents — operators customize profiles; hunt behavior too.
- Missing encoded launchers because Script Block Logging was not enabled — check Module Logging and Sysmon as fallbacks.
- Confusing Empire with other frameworks (Cobalt Strike, Metasploit) that share launcher aesthetics — verify with framework-specific strings.
- Declaring the incident scoped after finding one agent — Empire deployments are rarely single-host.
- Decoding launchers on a production host instead of the lab.
- Confusing Empire with its forks — check fork-specific default strings before attributing.
- Assuming agent death equals eviction — persistence mechanisms survive process kills.
- Empire version differences (3.x/4.x/5.x) changing defaults — note the version indicators.
- Trusting decade-old blog posts on Empire 2.x defaults — verify against the version in play.
- Custom profiles making default-hunting useless — always pair with behavioral hunting.
- Missing Empire's Python/Linux agents — the framework isn't Windows-only.
- Treating agent "lost" status as eviction — check for persistence and re-staging.
- Hardcoded credentials in recovered configs — rotate anything the config touched.
- Searching only for "Empire" strings — operators rename everything.
- Forgetting that Empire agents can migrate processes — track by C2, not PID.
- Not checking for Empire's default kill-date — expired agents may still beacon.
- Missing the agents database on seized servers — it's the operator's own notes.
- Confusing Empire staging with Cobalt Strike — verify with framework-specific markers.
- Assuming HTTP-only — Empire supports multiple listener types.
- Empire's default profiles are well-signatured — hunt for modified jitter and custom modules.
- Stagers live in memory only — disk forensics alone misses reflective injection; take memory.
- AMSI bypass variants evolve — never rely on a single bypass signature.
- Overlooking WMI event subscriptions as the persistence paired with the agent.
- Agent check-in jitter defeating fixed-interval detection — use statistical beaconing analysis.
- Confusing Empire with sibling frameworks — verify via module/tasking artifacts before attributing.
- Not capturing the full stager URI path — the profile name lives in the path.

## References

- PowerShell Empire archived project documentation (public repository)
- BC Security Empire documentation (public repository)
- Empire default profile documentation (public repo)
- MITRE ATT&CK T1059.001 (PowerShell), T1071.001 (Web Protocols), T1053 (Scheduled Task/Job), T1047 (WMI)
- Microsoft: PowerShell Script Block Logging documentation

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
