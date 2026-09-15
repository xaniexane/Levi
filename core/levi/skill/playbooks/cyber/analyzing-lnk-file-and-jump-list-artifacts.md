# Analyzing LNK File and Jump List Artifacts

## Purpose

Windows shortcut (`.lnk`) files and Jump Lists record which files and
applications a user opened, when, and from where — including files on removable
drives and network shares that no longer exist. This playbook shows how to
parse them forensically to reconstruct user activity and identify execution of
malicious payloads.

## When to use

- Reconstructing what a user (or malware acting as the user) opened and when.
- Proving execution of a payload delivered to Downloads, Desktop, or a USB drive.
- Correlating file-open activity with malware detonation times.

See also: analyzing-windows-lnk-files-for-artifacts.md

## Prerequisites

- Written authorization to examine the user's profile data; LNK/Jump Lists
  reveal personal activity — keep strictly within the authorized scope.
- Forensic copies of the profile artifacts with hashes; parse the copies, not
  the live profile.
- Parsing tools on the analysis workstation (Eric Zimmerman's LECmd/JLECmd or
  Python `pylnk3`); Windows paths are case/encoding sensitive — preserve them.

## Procedure

1. Collect the artifacts from the forensic image (do not work on the live host):
   - LNK files: `%USERPROFILE%\Recent\`, Desktop, and any custom locations.
   - Automatic Jump Lists: `%APPDATA%\Microsoft\Windows\Recent\
     AutomaticDestinations\` (`*.automaticDestinations-ms`).
   - Custom Jump Lists: `...\Recent\CustomDestinations\`.
2. Hash every collected file and record source paths before parsing.
3. Parse LNK files in bulk: `LECmd.exe -d <lnk-dir> --csv <out-dir>`
   Review target paths, arguments, working directories, and the embedded
   timestamps (creation, access, write of both the link and its target).
4. Parse Jump Lists: `JLECmd.exe -d <destinations-dir> --csv <out-dir>`
   Automatic destinations map AppIDs to recently opened files per application;
   resolve AppIDs to application names (JLECmd output includes them, or use a
   known AppID list).
5. Focus the review on attacker-relevant entries:
   - LNKs pointing to executables in Downloads, Temp, or removable drives.
   - LNKs with suspicious arguments (PowerShell `-enc`, `cmd /c`, wscript).
   - Jump-list entries for `powershell.exe`, `cmd.exe`, `mshta.exe`,
     `rundll32.exe` showing recently "opened" documents that are actually
     payloads.
   - LNKs whose target no longer exists (deleted payload) — the link often
     survives the file.
6. Extract volume and machine identifiers: LNK files embed volume serial
   numbers and (sometimes) the originating machine name — use these to tie a
   USB-delivered payload to a specific removable drive.
7. Correlate timestamps with the master timeline: LNK target-access times vs.
   Prefetch, UserAssist, and EDR process-creation events for the same binary.
8. Distinguish user action from programmatic creation: installers and malware
   both create LNKs; check creation context (installer logs, parent process)
   before attributing a shortcut to the user.
9. Check startup-folder LNKs (`%APPDATA%\Microsoft\Windows\Start Menu\Programs\
   Startup`) explicitly — a favorite persistence location — and compare each
   against the user's known applications.

## Key tools & commands

- `LECmd.exe -d <dir> --csv <out>` — bulk LNK parsing (Eric Zimmerman).
- `JLECmd.exe -d <dir> --csv <out>` — Jump List parsing.
- `pylnk3` (Python) — scripted LNK parsing when Zimmerman tools are unavailable.
- AppID reference lists — mapping `*.automaticDestinations-ms` AppIDs to apps.
- Timeline tools (Plaso) — merging LNK timestamps into the case timeline.

## Expected outputs

- CSV/parsed set of all LNK and Jump List entries with target, arguments,
  timestamps, and volume info.
- Findings: which suspicious files were opened, when, and via which
  application.
- USB/network-share attribution where volume serials resolve.
- Correlation notes tying shortcut activity to execution evidence.

## Pitfalls

- Jump Lists cap entries per AppID and rotate — absence of an entry does not
  prove a file was never opened.
- LNK timestamps reflect the link and target at creation; opening a file does
  not always update every timestamp — corroborate with Prefetch/UserAssist.
- Parsing the live profile instead of a forensic copy risks timestamp
  modification and spoliation challenges.
- AppID-to-application mapping errors misattribute activity; verify unusual
  AppIDs rather than guessing.
- Malware-created LNKs in startup folders look like user shortcuts — check
  parentage before attributing intent.
- Volume serial numbers can collide across drives; corroborate USB attribution
  with `setupapi.dev.log` and USB registry artifacts before asserting a
  specific device.

## References

- Eric Zimmerman tool documentation (ericzimmerman.github.io — LECmd, JLECmd)
- MITRE ATT&CK: T1547.009 (Shortcut Modification), T1204 (User Execution)
- SANS "LNK Files" forensic posters and Jump List research papers
- Microsoft MS-SHLLINK specification (shortcut file format)

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
