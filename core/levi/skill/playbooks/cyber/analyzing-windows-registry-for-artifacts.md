# Analyzing the Windows Registry for Artifacts

## Purpose

Systematically extract forensic evidence from Windows registry hives: persistence mechanisms, execution history, user activity, USB and network history, and system configuration. The registry is the richest single artifact source on a Windows host — this playbook gives the key hives, keys, and triage order so analysis is thorough without drowning in ten thousand keys.

The registry rewards a methodical order: identify the system, sweep persistence, reconstruct execution and user activity, then hunt tradecraft. Analysts who start by searching for strings usually find noise; analysts who walk the structure find cases.

## When to use

- Any Windows host investigation: the registry answers persistence, execution, and user-activity questions in nearly every case.
- Malware triage: finding Run keys, services, COM hijacks, and other auto-start mechanisms.
- User-activity reconstruction: typed paths, recent documents, connected networks, mounted devices.
- System-configuration review: RDP settings, firewall rules, audit policy, time zone.
- Scoping lateral movement: which accounts and services were configured or altered.

## Prerequisites

- Written authorization to examine the endpoint(s), with legal basis and scope documented. Registry hives contain credentials-adjacent material (SAM hashes, LSA secrets) — define handling rules and never export secrets beyond the authorized scope.
- Forensic images or targeted collections of the hives: `SYSTEM`, `SOFTWARE`, `SAM`, `SECURITY`, `NTUSER.DAT` per user, and `UsrClass.dat` per user, plus transaction logs (`*.LOG*`) for dirty hives. Hash everything at collection; parse copies.
- Chain-of-custody records: source paths, collection timestamps, collector, hashes, tool versions.
- The investigation timezone plan: most registry timestamps are FILETIME UTC; a few (e.g., ShutdownTime) need care. Convert explicitly.
- A known-good baseline (gold image or clean reference host of the same build) for the persistence sweep — "unusual service" is only meaningful against "usual."

## Procedure

1. Verify and inventory the hives. Confirm each hive opens (merge transaction logs for dirty hives with a forensic tool), record the Windows version and install date (`SOFTWARE\Microsoft\Windows NT\CurrentVersion`), computer name (`SYSTEM\ControlSet001\Control\ComputerName`), and timezone (`SYSTEM\ControlSet001\Control\TimeZoneInformation`). These anchor every later finding.
2. Sweep persistence locations first. Check, in both HKLM and each user's HKCU: `...\Run` and `RunOnce` (SOFTWARE and NTUSER), services (`SYSTEM\ControlSet001\Services` — compare against a known-good baseline, look at `ImagePath` and `Start` values), scheduled tasks (cross-check with the Task Scheduler log), Winlogon entries (`Userinit`, `Shell`), and COM hijacking points (`HKLM\SOFTWARE\Classes\CLSID`). Document every auto-start entry with its key path, value, and target binary.
3. Examine execution artifacts. Review: UserAssist (`NTUSER\Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist` — ROT13-encoded, shows GUI program executions with run counts), RecentDocs, typed URLs (`...\Explorer\TypedPaths`), and Shimcache/AppCompat (`SYSTEM\ControlSet001\Control\Session Manager\AppCompatCache` — last-modified timestamps of executed binaries). Decode UserAssist with a parser, not by hand.
4. Reconstruct device and network history. Check USBSTOR (`SYSTEM\ControlSet001\Enum\USBSTOR`) for connected storage devices with serials; `SOFTWARE\Microsoft\Windows NT\CurrentVersion\NetworkList\Profiles` for wired/wireless networks joined with first/last-connected dates; and `MountedDevices` for drive-letter-to-volume mappings.
5. Review system configuration relevant to the case. Check: RDP state (`SYSTEM\ControlSet001\Control\Terminal Server\fDenyTSConnections`), firewall profiles and rules (`SYSTEM\ControlSet001\Services\SharedAccess\Parameters\FirewallPolicy`), audit policy (`SECURITY` or via `auditpol` equivalent keys), installed programs (`SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`), and the last shutdown time.
6. Look for attacker tradecraft in the registry. Search for: Run keys with encoded PowerShell or `mshta`/`rundll32` payloads, service `ImagePath` values pointing to Temp directories or with `svchost -k` anomalies, AppInit_DLLs, IFEO (Image File Execution Options) debugger hijacks, and recently created keys with suspicious names. Treat each as a lead to verify against file-system and log evidence.
7. Diff against the baseline. Export the persistence-relevant keys from the suspect hives and the gold-image hives and diff them. Additions and modifications on the suspect host that don't exist in the baseline are your highest-value leads — this catches the persistence your eyes skip.
8. Handle deleted keys. Registry slack and unallocated hive cells can retain deleted keys — use a tool that parses deleted cells (e.g., Registry Explorer's deleted-value recovery) and label such findings as recovered with lower confidence.
9. Correlate key timestamps with the incident timeline. Merge registry last-write times (persistence keys, USBSTOR installs, network profile connections) into the case timeline. A Run key written minutes after the initial-access timestamp is the story of the intrusion in one line.
10. Write key-sourced findings. For each finding record the full key path, value name/data, last-write timestamp (UTC with conversion noted), the hive file it came from, and corroborating artifacts. Persistence findings get a verdict: legitimate, suspicious-needs-review, or malicious with evidence cited.

## Key tools & commands

- Eric Zimmerman's Registry Explorer (with bookmarks for Run keys, services, USBSTOR, UserAssist) and RECmd for batch triage: `RECmd.exe --bn <bookmark> -d <hive-dir> --csv outdir`.
- RegRipper (`rip.pl -r SYSTEM -f system`) for plugin-based reporting across hives.
- `reg query` / PowerShell `Get-ItemProperty` for targeted live-triage (only on non-suspect or triage-authorized live hosts).
- `diff` on exported key dumps (suspect vs. gold image) for the baseline-comparison step.
- YARA or binary-safe text search over exported hive text for hunting encoded payloads in Run values.
- `sha256sum` for hashing hives at acquisition.

## Expected outputs

- Hive inventory: files, hashes, Windows version, computer name, timezone.
- A persistence sweep report: every auto-start entry with key path, target, and verdict.
- Execution-artifact findings: UserAssist, Shimcache, RecentDocs, TypedPaths with decoded values.
- Device/network history: USBSTOR devices, network profiles, drive mappings.
- Configuration findings: RDP, firewall, audit policy, installed programs, shutdown time.
- Attacker-tradecraft leads with verification status.
- Baseline diff results: suspect-vs-gold additions and modifications.
- Recovered deleted-key findings labeled by confidence.
- A registry-derived timeline merged into the case timeline.
- Per-finding records with full key paths, timestamps, and corroboration.

## Pitfalls

- Last-write timestamps apply to the key, not the value: a key's timestamp changes when any value under it changes — don't attribute it to a specific value without care.
- UserAssist is ROT13-encoded and tracks GUI executions only; console tools won't appear. Absence there means nothing for command-line malware.
- ControlSet001 vs. CurrentControlSet: analyze the actual control set in use; also check ControlSet002 for prior-boot configuration that may differ.
- Dirty hives without transaction logs show stale data — always recover the `.LOG` files from the image.
- SAM/LSA secrets: extracting them is credential access — stay within the authorized scope and handle the output as credential material.
- The registry is huge: analysts who "browse around" miss keys and waste hours. Work the checklist in order.
- Baseline drift: a gold image from six months ago differs from current builds legitimately (patches add services). Refresh baselines with the patch cycle or the diff drowns in noise.

## References

- Microsoft documentation on registry structure, Run keys, and services configuration.
- Eric Zimmerman's Registry Explorer / RECmd documentation — key bookmarks and batch usage.
- RegRipper plugin documentation.
- MITRE ATT&CK T1547 (Boot or Logon Autostart Execution) and sub-techniques for the persistence locations.
- NIST SP 800-86 — forensic evidence handling.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
