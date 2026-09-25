---
skill_id: cyber_analyzing_prefetch_files_for_execution_history
name: Analyzing Prefetch Files for Execution History
description: Reconstruct program execution from Windows Prefetch files.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, windows]
version: 1.0.0
---
# Analyzing Prefetch Files for Execution History

## Purpose

Reconstruct program execution history on Windows from Prefetch (`.pf`) files — what ran, when it first and last ran, how many times, and which files it touched — even when the executables themselves are deleted.

## When to use

- Proving a malware binary or hacking tool executed on a host, and when.
- Timeline building: first-run vs. last-run times anchor the intrusion timeline.
- Triage when EDR telemetry is incomplete or the agent was disabled.

## Prerequisites

- Written authorization; chain-of-custody for the disk image.
- Access to `C:\Windows\Prefetch` from a forensic image (parse offline; do not rely on the live system's Prefetch service state).
- A Prefetch parser (`PECmd`, or Python with a prefetch-parsing library); hashes of the `.pf` files.
- Knowledge of the naming scheme: `EXECUTABLENAME-HASH.pf` (hash of path, uppercase exe name, 8 hex chars).

## Procedure

1. Acquire `C:\Windows\Prefetch\*.pf` from the forensic image and hash each file.
2. Parse the full directory in bulk:
   `PECmd.exe -d C:\forensics\prefetch --csv ./out --csvf prefetch.csv`
   This yields run counts, last-run timestamps (up to 8 on Win10+), and embedded file/volume references.
3. Sort by last-run time and filter to the incident window — this is your execution timeline backbone.
4. Identify suspicious executables: names matching known tools (`MIMIKATZ`, `PSEXEC`, `NMAP`), odd locations (`TEMP-*.pf`, `APPDATA-*.pf`), and recently created `.pf` files for binaries that no longer exist on disk.
5. For each suspicious `.pf`, examine the embedded file list: DLLs loaded and files accessed reveal what the program did (e.g., `lsass` memory access patterns, archive creation).
6. Check run counts: a tool that ran 47 times is interactive attacker use; a single run may be automated deployment.
7. Correlate with the executable's MFT record: if the binary is deleted but its `.pf` remains, use the MFT playbook to attempt recovery and confirm the binary's hash.
8. Cross-reference with other execution artifacts: Shimcache/AppCompatCache, Amcache, UserAssist, BAM/DAM, and Sysmon/EDR — Prefetch alone can be disabled or cleared by attackers.
9. Hunt lateral-movement tools specifically: `PSEXESVC`, `WMIADAP`, and `RUNDLL32` with odd parents; renamed Sysinternals binaries show up as hash-named `.pf` files whose embedded paths reveal the true executable name.
10. Mind parser versions: Windows 10+ Prefetch uses its own compression scheme — an outdated parser silently misparses new formats, so keep PECmd current.
11. Compare Prefetch last-run times against the executable's MFT timestamps to spot timestomped binaries hiding their true age.
12. Check Prefetch for evidence of cleanup tools: `CIPHER`, `SDELETE`, or `WEvtUtil` executions indicate anti-forensics — and timestamp the cover-up.
13. Correlate Prefetch run counts with UserAssist: disagreements between the two can indicate one artifact was tampered with.
14. Look for Prefetch entries of installers: legitimate-looking names (`UPDATE-*.pf`, `SETUP-*.pf`) sometimes mask renamed malware — verify the executable's hash.
15. Parse `C:\Windows\Prefetch\Layout.ini`: it reveals which files the prefetcher prioritized — corroborating the `.pf` story.
16. Use volume serial numbers in `.pf` files for USB attribution: match them against `USBSTOR` registry keys.
17. Check Prefetch for admin tools (`REGEDIT`, `MMC`, `EVENTVWR`): their execution times show when the attacker worked interactively.
18. Correlate with RecentDocs: files the attacker opened should appear in both artifacts.
19. Look for Prefetch entries created while the system was supposedly idle — scheduled malicious execution stands out.
20. Note the Prefetch caveats in your findings: max 128 entries on modern Windows (old entries age out), and `.pf` creation requires the Prefetcher/SysMain service — absence of a `.pf` is not proof of non-execution.
21. Build the execution timeline rows: executable, path hash, first/last run, run count, and corroborating artifacts.

## Key tools & commands

- `PECmd.exe -d <dir> --csv <out>` — Eric Zimmerman's Prefetch parser, bulk mode.
- `PECmd.exe -f <file.pf>` — single-file detailed parse.
- Python prefetch libraries — scripted parsing for fleet-scale triage.
- `fls`/`icat` (Sleuth Kit) — recovering deleted executables referenced by `.pf` files.
- WinPrefetchView (NirSoft) — quick GUI triage of `.pf` files.
- `strings` on `.pf` files — fast keyword triage before full parsing.
- Registry `EnablePrefetcher` value — confirming the Prefetch configuration.
- Corroborating artifacts: Shimcache (`AppCompatCacheParser`), Amcache (`AmcacheParser`), UserAssist.

## Expected outputs

- Parsed Prefetch CSV with hashes of source `.pf` files.
- Suspicious-execution list: binary, timestamps, run counts, embedded file references.
- Corroboration matrix vs. Shimcache/Amcache/UserAssist/EDR.
- Timestomp cross-check: Prefetch last-run times vs. MFT timestamps.
- Execution timeline rows for the incident report.

## Pitfalls

- Treating a missing `.pf` as proof the binary never ran — Prefetch caps at 128 entries and can be disabled.
- Misreading the filename hash as meaningful — it is just a path hash, not a file hash.
- Forgetting that `.pf` files persist after the executable is deleted — which is a feature for forensics, not a contradiction.
- Parsing the live `C:\Windows\Prefetch` on a running suspect host instead of the image.
- Relying on Prefetch alone without corroborating artifacts.
- Outdated parsers silently misparsing Windows 10+ Prefetch compression — keep PECmd current.
- Prefetch disabled via registry (`EnablePrefetcher=0`) — check the configuration before concluding.
- Filename hash collisions (rare) — always verify via the embedded path.
- Prefetch on SSDs with SysMain disabled — many enterprise images disable it; check the config.
- Misattributing `.pf` files after OS upgrades — embedded paths may reference old locations.
- Volume serial numbers in `.pf` files identify the source drive — useful for USB attribution.
- Not hashing `.pf` files at acquisition — chain of custody applies to artifacts too.
- Ignoring `Layout.ini` — it reveals which files the prefetcher prioritized.
- Forgetting Prefetch tracks the first seconds of execution — short-lived processes are underrepresented.
- Not checking the Prefetch directory's own timestamps — they bound activity.
- Assuming `.pf` run counts are exact — they're counters; treat as approximate.
- Missing Prefetch for processes run from removable media — volume serials tell the story.
- Overlooking that Windows tracks up to 8 last-run timestamps — use all of them.
- Not comparing against a known-good host's Prefetch set.
- Prefetch is capped (128 entries on older Windows) — absence is not proof of non-execution.
- `Amcache.hve` corroborates better than Prefetch alone — always cross-reference.
- Prefetch timestamps reflect the last run, not the first — do not use them for initial-access dating.
- Copying `.pf` files on a running system risks torn reads — prefer image-based collection.
- Prefetch disabled by GPO in hardened builds — verify `EnablePrefetcher` before concluding.
- Embedded paths may reference old locations after OS upgrades — verify, do not assume.
- Hash the `.pf` set at collection — chain of custody applies to artifacts too.
- Ignoring `Layout.ini` — it reveals which files the prefetcher prioritized at boot.
- Forgetting that disabled Prefetch still leaves `Layout.ini` clues.
- Overlooking `.pf` files for DLL side-loading victims — the host process executes, the DLL doesn't.

See also: analyzing-windows-prefetch-with-python.md

## References

- Eric Zimmerman's PECmd documentation
- NirSoft WinPrefetchView documentation
- Russinovich et al. — "Windows Internals" (Prefetcher chapter)
- MITRE ATT&CK T1070 (Indicator Removal — artifact wiping context)
- SANS FOR500 Windows forensic analysis methodology

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
