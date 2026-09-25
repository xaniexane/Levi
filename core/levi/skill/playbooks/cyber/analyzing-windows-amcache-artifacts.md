---
skill_id: cyber_analyzing_windows_amcache_artifacts
name: Analyzing Windows Amcache Artifacts
description: Extract program execution evidence from Amcache.hve.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, windows]
version: 1.0.0
---
# Analyzing Windows Amcache Artifacts

## Purpose

Extract program execution evidence from the Windows Amcache hive (`Amcache.hve`): which applications
ran on the system, their file paths, hashes, installation/execution timestamps, and publisher
information. Amcache is one of the most reliable execution artifacts on modern Windows because it
records GUI and installed applications independently of Prefetch and event logs.

Amcache's strength is its independence: it is populated by the application-compatibility
infrastructure, not by the same mechanisms that produce Prefetch or event logs. When an attacker
clears event logs, Amcache often still tells the story.

## When to use

- Establishing that a specific executable ran on a host (malware, hacking tools, or unauthorized
  software).
- Building an application-installation timeline during incident scoping.
- Identifying portable executables run from removable media or unusual paths.
- Corroborating (or challenging) user claims about what software was used.
- Post-log-wipe investigations where event logs are unavailable.

## Prerequisites

- Written authorization to examine the endpoint, with the legal basis and scope (machines, time
  window) documented.
- A forensic image or targeted collection of `C:\Windows\AppCompat\Programs\Amcache.hve` (plus the
  `.LOG` transaction files if the hive is dirty) with hashes and chain-of-custody records. Parse a
  copy, never the live hive on a running suspect system.
- Knowledge of the Windows version under analysis: Amcache's schema changed significantly between
  Windows 7/8 and Windows 10/11 (newer versions store richer per-file data under
  `Root\InventoryApplicationFile`).
- The investigation's timezone plan: Amcache timestamps are FILETIME (UTC); convert explicitly.
- A triage collection tool (e.g., KAPE) or manual copy procedure approved for pulling the hive plus
  its transaction logs together.

## Procedure

1. Acquire and verify the hive. Copy `Amcache.hve` (and any `Amcache.hve.LOG*` files) from the
   image, hash the copies, and confirm the hive opens cleanly. If the hive is dirty, merge
   transaction logs with a forensic tool rather than editing the original.
2. Parse the hive. Run AmcacheParser (Eric Zimmerman) against the hive: `AmcacheParser.exe -f
   Amcache.hve --csv outdir`. This produces CSVs for the key subkeys, including
   `Root\InventoryApplicationFile` (per-file execution records) and `Root\InventoryApplication`
   (installed programs).
3. Review the InventoryApplicationFile records. For each entry note: file path, file name, SHA-1
   hash, publisher, version, language, and the timestamps (install date, first run where available).
   Sort by path to spot executables in unusual locations (`\Temp\`, `\Users\Public\`,
   removable-drive letters).
4. Hunt for suspicious entries. Filter for: executables with missing or mismatched publisher data,
   known hacking-tool names, files executed from temporary or removable paths, and entries whose
   hash matches threat-intel. Cross-check hashes against your intel platform before declaring a hit.
5. Distinguish installed vs. merely present. Use `Root\InventoryApplication` (programs with install
   metadata) versus `InventoryApplicationFile` (files seen by the inventory, including portable
   executables that were never "installed"). A hacking tool in the file inventory but not the
   program inventory likely ran portably — note the distinction.
6. Build the execution timeline. Merge Amcache timestamps with Prefetch last-run times, UserAssist
   entries, and Security log process-creation events (4688) into one timeline. Agreement across
   artifacts strengthens the finding; disagreement is itself worth investigating (e.g.,
   timestomping).
7. Check program installation records. Review `Root\InventoryApplication` for installed programs:
   name, version, publisher, install date, and uninstall entries. Unauthorized remote-access tools
   or dual-use utilities installed shortly before the incident window are significant.
8. Sweep for the indicators across hosts. Once suspicious programs are identified, search other
   hosts' Amcache hives for the same file names, hashes, or publishers to scope the incident
   laterally. Amcache's per-file hashes make this a precise hunt.
9. Handle deleted or overwritten entries. Amcache is a live hive — uninstalled programs may leave
   orphaned entries and entries may be pruned. Note which findings come from current vs.
   recovered/deleted cells and label confidence accordingly.
10. Document and report. For each relevant program: path, hash, publisher, timestamps, the artifact
    source (Amcache subkey), and corroborating artifacts. Include the AmcacheParser version, the
    hive hash, and the UTC-to-local conversion used.

## Key tools & commands

- AmcacheParser (Eric Zimmerman): `AmcacheParser.exe -f Amcache.hve --csv outdir [--dt "yyyy-MM-dd
  HH:mm:ss"]` — the standard parser for modern Amcache hives.
- Registry Explorer (Eric Zimmerman) for manual browsing of `Root\InventoryApplicationFile` when the
  parser output needs verification.
- KAPE (Kroll Artifact Parser and Extractor) for targeted triage collection of `Amcache.hve` plus
  transaction logs across many hosts.
- `sha256sum` / `Get-FileHash` for hashing the hive at acquisition.
- Timeline tools (Plaso/log2timeline or a manual spreadsheet) for merging Amcache timestamps with
  Prefetch, UserAssist, and 4688 events.
- Your threat-intel platform or hash-lookup service for suspicious file hashes.

## Expected outputs

- Hashed Amcache hive copy with acquisition log.
- Parsed CSVs of InventoryApplicationFile and InventoryApplication.
- An installed-vs-portable classification for programs of interest.
- A suspicious-entry list: unusual paths, missing publishers, intel hash hits.
- A merged execution timeline with corroborating artifacts.
- Cross-host sweep results for the identified indicators.
- Per-program findings with paths, hashes, timestamps, and confidence labels.
- Parser version, hive hash, and timezone conversion documented.

## Pitfalls

- Assuming every Amcache entry means the program executed: inventory entries can be created by
  installation or scanning without execution. Corroborate with Prefetch or 4688 before claiming
  execution.
- Windows version schema differences: parsing a Windows 11 hive with expectations from Windows 7
  documentation leads to misread fields. Check the schema for the version at hand.
- Dirty hives: analyzing `Amcache.hve` without its transaction logs can show stale data. Recover the
  logs from the image.
- Hash mismatches from file updates: a program updated after the incident will have a different hash
  than the incident-time binary — the Amcache entry may reflect the newer version.
- Overstating deleted-cell findings: recovered entries lack the reliability of live ones; label them
  as such.
- Portable tools on removable media: the path records the drive letter at execution time, which may
  be reassigned later. Correlate with USB history before attributing to a specific device.
- Amcache pruning on long-running systems: very old entries may be gone. Absence of an entry is not
  proof the program never ran.

## References

- Microsoft documentation on the Application Compatibility cache and Amcache.hve.
- Eric Zimmerman's AmcacheParser documentation — subkey reference and output schema.
- KAPE documentation — triage collection targets for Amcache.
- SANS DFIR posters and Windows forensic artifact references for Amcache key paths.
- NIST SP 800-86 — forensic evidence handling.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
