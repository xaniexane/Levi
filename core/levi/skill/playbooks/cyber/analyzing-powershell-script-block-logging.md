# Analyzing PowerShell Script Block Logging

## Purpose

Use PowerShell Script Block Logging (Event ID 4104) as a primary detection and forensic source — reconstructing exactly what PowerShell code executed on a host, including deobfuscated content, even when the original script files are gone.

## When to use

- Investigating any incident involving PowerShell: encoded launchers, download cradles, lateral movement, or ransomware deployment scripts.
- Threat hunting for obfuscated PowerShell across the fleet.
- Validating whether a suspicious process actually executed malicious script content.

## Prerequisites

- Written authorization; access to centralized Windows event logs or host-level PowerShell operational logs.
- Script Block Logging enabled via Group Policy (it is not on by default on older builds — verify coverage before concluding "nothing ran").
- Note the log size reality: 4104 is verbose; ensure your SIEM retention covers the incident window.
- A lab PowerShell for safely decoding obfuscated snippets (never on production hosts).

## Procedure

1. Verify logging coverage: check the GPO `Turn on PowerShell Script Block Logging` and confirm 4104 events exist in the window. No 4104s may mean "not enabled," not "clean."
2. Pull 4104 events for suspect hosts and the incident window:
   `Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-PowerShell/Operational'; Id=4104; StartTime=<t1>; EndTime=<t2>}`
   Export to EVTX/CSV with hashes for the case file.
3. Triage by script content, not just presence: search the `ScriptBlockText` for high-risk patterns —
   `FromBase64String`, `Invoke-Expression`/`iex`, `DownloadString`, `Net.WebClient`, `VirtualAlloc`, `bypass`/`-ExecutionPolicy Bypass`, and credential-theft cmdlet names.
4. Reconstruct multi-part scripts: PowerShell splits long script blocks across multiple 4104 events sharing a `ScriptBlock ID` — group by that ID and concatenate in `MessageNumber` order before analysis.
5. Decode obfuscation in the lab: copy the encoded blob, decode base64, and de-layer string concatenation/replacements iteratively until the payload is readable. Document each layer.
6. Correlate each malicious script block with its creating process: match timestamps against Sysmon Event ID 1 / Security 4688 to find the parent (e.g., `winword.exe` spawning `powershell.exe` = macro-launched).
7. Check for logging tampering: gaps in 4104 sequences, or Event ID 4104 with the provider disabled mid-incident, suggest the attacker blinded logging — treat surrounding telemetry as attacker-influenced.
8. Hunt fleet-wide for the same script patterns: push the distinctive strings (decoded, not the raw obfuscated form) to the SIEM/EDR hunt to find other hosts.
9. Map script capabilities to ATT&CK: download cradle (T1105), in-memory execution (T1059.001), credential access cmdlets (T1003), and persistence commands — this drives the scoping questions.
10. Check for AMSI bypass attempts in the same window: 4104 content referencing `amsiInitFailed`, reflection-based patching of AMSI internals, or `Set-MpPreference` disabling Defender shows the attacker fought the protection stack.
11. Review PowerShell Module Logging (Event ID 4103) as a fallback where Script Block Logging was off — pipeline execution details partially compensate for the gap.
12. Correlate with Event IDs 4105/4106 (script block invocation start/stop) when that auditing is enabled, to confirm execution rather than just logging.
13. Hunt encoded-command launchers fleet-wide: search Sysmon/EDR for `-EncodedCommand` / `-Enc` with abnormally long arguments.
14. Reconstruct download cradles: extract URLs from `DownloadString`/`Invoke-WebRequest` blocks and check proxy logs for who else fetched them.
15. Check for runspace-based evasion: code executed through raw runspaces can bypass 4104 — correlate with Sysmon ImageLoad events for System.Management.Automation.
16. Document the deobfuscation chain: each transformation layer recorded with input/output hashes for reproducibility.
17. Preserve the raw 4104 exports; note the GPO state and any coverage gaps in the findings memo.

## Key tools & commands

- `Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-PowerShell/Operational'; Id=4104}` — pull script blocks.
- `wevtutil qe Microsoft-Windows-PowerShell/Operational /q:"*[System/EventID=4104]"` — CLI alternative.
- Group Policy: `Turn on PowerShell Script Block Logging` (+ `Log script block invocation start/stop events` for 4105/4106).
- Sysmon Event ID 1 / Security 4688 — parent-process correlation.
- Lab decoding: Python `base64`, PowerShell `-EncodedCommand` inspection in isolation.
- Event IDs 4103 (Module Logging) and 4105/4106 (invocation start/stop) — complementary coverage.
- AMSI-bypass indicator terms — hunting for protection-stack tampering.
- SIEM/EDR hunt queries on decoded distinctive strings.

## Expected outputs

- 4104 export (EVTX/CSV) with hash, covering the incident window.
- Reconstructed full scripts (multi-part reassembled, deobfuscated in layers).
- Process lineage per malicious script (parent chain to initial access).
- Fleet hunt results for the same patterns.
- AMSI-bypass findings in the incident window.
- Invocation start/stop (4105/4106) correlation where available.
- Coverage-gap notes (where logging was off or tampered with).

## Pitfalls

- Analyzing raw obfuscated text without de-layering — you will miss the actual payload.
- Forgetting multi-part reassembly — a script split across events looks benign in fragments.
- Assuming no 4104 = no PowerShell — check the GPO and consider Module Logging (4103) as fallback.
- Hunting on raw obfuscated strings — they change per run; hunt on decoded distinctive content.
- Decoding payloads on a production host instead of the lab.
- 4104 truncation of very long scripts — check MessageNumber sequences for gaps.
- Event-log overwrites on busy hosts silently losing the incident window.
- GPO enabled but log forwarding broken — the events exist locally but never reached the SIEM.
- Case-sensitivity mistakes in hunt queries — PowerShell is case-insensitive, your SIEM may not be.
- Searching only `powershell.exe` — `pwsh`, custom hosts, and WMI-launched script bypass process-name hunts.
- Ignoring constrained-language-mode bypasses in the same window.
- Forgetting transcription logs (`Start-Transcript`) as a complementary source.
- Correlating by hostname only in VDI/non-persistent environments — use session IDs.

## References

- Microsoft: "PowerShell Script Block Logging" documentation
- Microsoft: Antimalware Scan Interface (AMSI) documentation
- Microsoft — PowerShell logging documentation (transcription, module logging)
- MITRE ATT&CK T1059.001 (PowerShell), T1027 (Obfuscated Files or Information), T1105 (Ingress Tool Transfer), T1562.002 (Disable Windows Event Logging)
- SANS FOR508: PowerShell forensics guidance

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
