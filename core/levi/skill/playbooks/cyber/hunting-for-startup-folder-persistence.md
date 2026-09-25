---
skill_id: cyber_hunting_for_startup_folder_persistence
name: Hunting for Startup Folder Persistence
description: Detect persistence via Windows startup folders: rogue shortcuts and scripts in per-user and all-users startup locations.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, persistence, windows]
version: 1.0.0
---
## Purpose

The Windows startup folders execute their contents at user logon —
simple, well-known, and still used by commodity malware and some
targeted intrusions. This focused playbook covers enumerating startup-
folder persistence, distinguishing legitimate entries, and triaging
malicious ones.

## When to use

- Persistence triage during incident response (quick win alongside
  Run keys).
- Hunting commodity malware (which favors simple persistence).
- Validating user-profile hygiene on shared or high-risk hosts.
- Training analysts on basic persistence enumeration.

## Prerequisites

- File enumeration across startup locations: per-user
  `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup` for every
  profile, and all-users
  `C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Startup`.
- Shortcut (.lnk) parsing capability to resolve targets and arguments.
- Gold-image baselines per host role.
- Target-binary analysis for unknowns.

## Procedure

1. **Enumerate all startup folders.** Collect contents from every user
   profile's startup folder plus the all-users location. On shared
   hosts, enumerate all profiles — attackers target other users'
   folders.
2. **Resolve shortcuts fully.** Parse each .lnk for its target path,
   arguments, working directory, and icon location (icon paths are a
   classic masquerading trick). Record target hashes and signer status.
3. **Diff against baselines.** Legitimate startup contents are usually
   sparse (a few vendor utilities). Flag: scripts (.bat, .ps1, .vbs,
   .js), shortcuts to script interpreters, unsigned executables, and
   entries created outside software deployment.
4. **Inspect script contents.** Read every script file found — startup
   scripts are small and readable, making this a high-value,
   low-effort check. Look for download cradles, encoded payloads, and
   persistence re-establishment logic.
5. **Date and attribute.** Use file timestamps (with timestomping
   awareness), USN journal, and creation-event logs to date each entry
   and find the installing process or user session.
6. **Check for companion persistence.** Startup-folder entries are
   often paired with Run keys or scheduled tasks as backup — when you
   find one, sweep the other mechanisms on the same host.
7. **Remediate and verify.** Remove malicious shortcuts/scripts and
   their payloads, then re-enumerate to confirm. For multi-user hosts,
   verify all profiles.
8. **Monitor simply.** Startup folders change rarely — file-integrity
   monitoring or scheduled collection with alerting on new entries is
   cheap and effective.

## Expected outputs

- Startup-folder inventories per host/profile with baseline diffs.
- Resolved shortcut targets with analysis and dispositions.
- Script contents reviewed with findings.
- Verified remediation records.
- FIM or scheduled monitoring for startup-folder changes.

## Pitfalls

- Checking only the current user's folder — enumerate every profile
   and the all-users location.
- Trusting shortcut names and icons — resolve and validate the actual
   target.
- Legitimate per-user software (chat clients, updaters) populates
   startup folders — baseline before alerting.
- Timestomped files in startup folders — corroborate dates with the
   USN journal.
- Removing the shortcut but leaving a re-creating companion mechanism.

## References

- MITRE ATT&CK: T1547.001 (Registry Run Keys / Startup Folder)
- Sysinternals Autoruns documentation (startup folder coverage)
- Forensic .lnk parsing references
- NIST SP 800-86: forensic techniques in incident response
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
