---
skill_id: cyber_analyzing_windows_lnk_files_for_artifacts
name: Analyzing Windows LNK Files for Artifacts
description: Parse Windows shortcut files for execution and exfiltration evidence.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, windows]
version: 1.0.0
---
# Analyzing Windows LNK Files for Artifacts

See also: analyzing-lnk-file-and-jump-list-artifacts.md

## Purpose

Extract forensic value from Windows shortcut (`.lnk`) files: which files, folders, and applications
a user opened, the original paths of moved or deleted targets, volume and machine identifiers, and
MAC timestamps embedded in the shortcut. LNK files survive in `Recent`, user profile, and USB-device
contexts long after the target is gone, making them a quiet but powerful execution and file-access
record.

LNK analysis punches above its weight because shortcuts are created automatically: every document
opened from Explorer typically leaves one. Users rarely think to clean them, and attackers rarely
think to plant convincing ones.

## When to use

- Proving a user opened a specific document or application (insider-threat and data-access cases).
- Recovering the original path of a file that was moved, renamed, or deleted.
- Identifying files accessed from removable media (LNK records the volume serial and device).
- Corroborating execution timelines alongside Prefetch, Amcache, and jump lists.
- Investigating malicious LNK files used for persistence or initial access.

## Prerequisites

- Written authorization to examine the endpoint(s), with legal basis and scope documented. LNK files
  reveal user activity in detail — apply your organization's privacy handling.
- A forensic image or targeted collection of LNK locations: `%APPDATA%\Microsoft\Windows\Recent\`,
  `%APPDATA%\Microsoft\Office\Recent\`, user Desktop and Start Menu folders, and any removable-media
  images. Hash everything at collection.
- Chain-of-custody records: source paths, collection timestamps, collector identity, hashes.
- A defined investigation timezone: LNK timestamps are FILETIME (UTC); convert explicitly before
  merging with local-time timelines.
- The companion artifacts for correlation: jump lists, Prefetch, and USB history locations collected
  in the same pass.

## Procedure

1. Collect the LNK files. From the image, gather `.lnk` files from Recent folders, Office Recent,
   Desktop, Quick Launch, and Start Menu for each user profile in scope. Record the full source path
   of every LNK file — its location is itself evidence (e.g., Recent vs. manually created on
   Desktop).
2. Parse with a dedicated tool. Run LECmd (Eric Zimmerman) across the collection: `LECmd.exe -d
   <lnk-directory> --csv outdir`. This decodes the shell-link header, link-target ID lists,
   timestamps, and embedded extra data (console properties, Darwin descriptors, known-folder GUIDs).
3. Read the target metadata. For each LNK of interest record: target local path and/or network path,
   file size, target MAC timestamps (these reflect the target file at shortcut-creation time — a
   goldmine when the target is deleted), volume serial number, and machine ID. The volume serial
   ties the target to a specific disk or USB device.
4. Resolve removable-media targets. LNK files pointing to drive letters like `E:\` with a volume
   serial let you match the shortcut to a USB device from the USBSTOR history (same serial = same
   physical device). This links "file opened" to "device connected" — the exfiltration chain.
5. Check for tampering or planting. Compare the LNK file's own timestamps against its embedded
   target timestamps; a shortcut created long after its target's timestamps, or one with a target
   path that never existed on the system, warrants scrutiny. Attackers occasionally plant LNK files
   for persistence (Startup folder) — inspect those for malicious targets.
6. Hunt for malicious LNK usage. Inspect shortcuts in Startup folders and recently created LNK files
   for: targets pointing to `powershell.exe`/`cmd.exe`/`mshta.exe` with encoded arguments, targets
   with double extensions, and LNK files whose icon is spoofed to look like a document. These are
   classic initial-access and persistence techniques — document the full target command line.
7. Examine LNK files from external media. Shortcuts recovered from USB images or email attachments
   get extra scrutiny: check their target paths for UNC paths to attacker infrastructure
   (`\\evil\share`) and their icons for document spoofing. These are common phishing payloads.
8. Build the access timeline. Merge LNK target-access evidence (shortcut creation/modification times
   approximate last access) with jump lists, Prefetch, UserAssist, and shellbags. Multiple artifacts
   agreeing on "user opened X at time T" is a strong finding; a lone LNK is weaker.
9. Cross-check against Volume Shadow Copies. If shadow copies exist, compare the LNK collection
   across snapshots: shortcuts present in an older snapshot but deleted since can recover
   file-access history the current state hides.
10. Report with precision. For each relevant LNK: its location, target path, volume serial,
    timestamps (with UTC noted), and what the finding supports (access, execution, device linkage).
    Include the LECmd version and the hash of the parsed LNK files.

## Key tools & commands

- LECmd (Eric Zimmerman): `LECmd.exe -d <directory> --csv <outdir>` for batch parsing; `-f <file>`
  for a single shortcut.
- Registry/artifact cross-reference: USBSTOR serials from the SYSTEM hive to match LNK volume
  serials to physical devices.
- `sha256sum` for hashing collected LNK files.
- Timeline merge tools (Plaso/log2timeline or spreadsheet) combining LNK, jump list, Prefetch, and
  UserAssist timestamps.
- Jump-list parsers (JLECmd) for the companion artifact — jump lists often contain the same targets
  with richer per-application history.
- Volume Shadow Copy examination (via your forensic suite) for historical LNK states.

## Expected outputs

- A hashed LNK collection with source paths documented.
- LECmd CSV output: targets, timestamps, volume serials, machine IDs.
- Removable-media linkages: LNK volume serials matched to USBSTOR devices.
- Malicious-LNK findings with full target command lines (if present).
- External-media/phishing LNK assessment (if in scope).
- An access timeline merged with corroborating artifacts.
- Shadow-copy comparison results (if applicable).
- Per-finding write-ups with confidence levels and tool versions.

## Pitfalls

- LNK creation time ≠ target access time in every case: Windows updates shortcuts on access, but
  pinned or copied shortcuts can carry stale timestamps. State which timestamp you are relying on
  and why.
- Volume serial numbers are not globally unique and can collide — use them as corroboration with
  USBSTOR data, not as standalone device identification.
- Network-path targets (`\\server\share`) resolve differently across sessions; a dead network target
  does not mean the file never existed.
- Parsing a live system's Recent folder while the user is active produces a moving target — prefer
  image-based collection.
- Over-reading: a LNK file proves the shortcut existed and was likely used, not the user's intent.
  Keep conclusions to what the artifact supports.
- Malicious LNK command lines may use environment-variable obfuscation (`%COMSPEC%`, caret escapes)
  — expand and normalize before judging the target.
- Assuming Recent-folder shortcuts imply the user double-clicked: applications can create shortcuts
  programmatically. Corroborate with execution artifacts for high-stakes claims.

## References

- Microsoft MS-SHLLINK specification — the authoritative Shell Link Binary File Format reference.
- Eric Zimmerman's LECmd documentation — parsed field reference.
- MITRE ATT&CK T1547.009 (Shortcut Modification) and T1204.001 (Malicious Link) for the
  malicious-use context.
- NIST SP 800-86 — forensic evidence handling.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
