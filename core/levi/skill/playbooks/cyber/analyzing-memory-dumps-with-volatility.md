---
skill_id: cyber_analyzing_memory_dumps_with_volatility
name: Analyzing Memory Dumps with Volatility
description: Memory forensics with Volatility: processes, network, and injection artifacts.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, malware-analysis]
version: 1.0.0
---
# Analyzing Memory Dumps with Volatility

## Purpose

Extract actionable evidence from a captured RAM image — running processes, network connections, loaded drivers, injected code, and credential artifacts — using the Volatility memory-forensics framework, without executing anything from the suspect memory on a production host.

## When to use

- A host shows signs of fileless malware, process injection, or credential dumping (LSASS access, T1003).
- Endpoint agents are blind (kernel rootkit suspected) and you need OS-level ground truth.
- You already hold a `.raw`, `.mem`, or crash-dump image; if not, acquire one first per your memory-acquisition runbook.
- Volatility 3 is the current maintained branch; use Volatility 2 only when an old image/profile demands it.

## Prerequisites

- Written authorization to handle the evidence; chain-of-custody form with hash (SHA-256) recorded at acquisition.
- Work only on a forensic copy, in an isolated analyst VM — never analyze on the suspect machine itself.
- Python 3.9+ with Volatility 3 installed (`pip install volatility3`), plus plugins you need pre-loaded.
- OS profile knowledge: Volatility 3 auto-detects via `windows.info`; Volatility 2 requires the correct profile.

## Procedure

1. Verify the image hash against the acquisition record before doing anything:
   `sha256sum suspect-mem.raw` — if it does not match, stop; the evidence is not what you think it is.
2. Confirm image information and build (Volatility 3):
   `vol -f suspect-mem.raw windows.info`
   Note `NtMajorVersion`, `NtMinorVersion`, and `KernelBase` — every later plugin depends on this.
3. List processes and their parent relationships:
   `vol -f suspect-mem.raw windows.pslist`
   Then cross-check with the scan view to catch hidden processes:
   `vol -f suspect-mem.raw windows.psscan`
4. Diff `pslist` against `psscan`. Any process present in `psscan` but missing from `pslist` is unlinked — a classic DKOM hiding indicator. Record PID, name, and PPID.
5. Enumerate active network state:
   `vol -f suspect-mem.raw windows.netscan`
   Flag foreign IPs, unusual local ports, and connections tied to hidden/suspicious PIDs from step 4.
6. Check loaded kernel modules and drivers for unsigned or oddly named entries:
   `vol -f suspect-mem.raw windows.modules` then `vol -f suspect-mem.raw windows.modscan`
   Compare against a known-good baseline for the same OS build.
7. Hunt injected code with `windows.malfind`:
   `vol -f suspect-mem.raw windows.malfind --dump`
   Review dumped regions for PE headers, shellcode patterns, or reflective loaders.
8. Inspect process handles and DLLs for credential-access tooling:
   `vol -f suspect-mem.raw windows.dlllist --pid <PID>` and `vol -f suspect-mem.raw windows.handles --pid <PID>`
   Look for `lsass.exe` handles opened with `PROCESS_VM_READ`, or `sekurlsa`-style modules.
9. Dump the registry hives resident in memory for persistence clues:
   `vol -f suspect-mem.raw windows.registry.hivelist`
   Then `vol -f suspect-mem.raw windows.registry.printkey --key "Software\Microsoft\Windows\CurrentVersion\Run"`
10. Extract command-line history and recent console activity:
    `vol -f suspect-mem.raw windows.cmdline` and `vol -f suspect-mem.raw windows.consoles`
11. Look for file traces still resident in memory:
    `vol -f suspect-mem.raw windows.filescan | grep -i -E "mimikatz|\.ps1|\.vbs|temp"`
    Filter on your case's keywords rather than guessing.
12. Dump suspicious process memory for offline string/review:
    `vol -f suspect-mem.raw windows.memmap --pid <PID> --dump`
    Then run `strings` and YARA rules over the dump in your malware lab, never on the analyst host's main filesystem without containment.
13. Check for hooks and callbacks indicating rootkit behavior:
    `vol -f suspect-mem.raw windows.ssdt` and `vol -f suspect-mem.raw windows.callbacks`
14. Build a unified memory timeline and merge it with the disk forensic timeline:
    `vol -f suspect-mem.raw windows.timeliner --output-file mem_timeline.csv`
    Sequencing process creation, network connections, and registry writes exposes the attack order.
15. Review active sessions and token privileges for token-manipulation signs:
    `vol -f suspect-mem.raw windows.sessions` and `vol -f suspect-mem.raw windows.getsids --pid <PID>`
    A user process holding a SYSTEM token warrants deeper review.
16. Where credential theft is suspected and explicitly authorized, extract SAM hashes for offline assessment in the lab only:
    `vol -f suspect-mem.raw windows.hashdump`
    Treat the output as highly sensitive: encrypt at rest and strictly limit distribution.
17. Check environment variables of suspicious processes for staging paths and C2 strings:
    `vol -f suspect-mem.raw windows.envars --pid <PID>`
18. Correlate every finding with disk and log evidence (Prefetch, Shimcache, Sysmon, EDR) before declaring a conclusion; memory is one lens, not the verdict.

## Key tools & commands

- `vol -f <image> windows.info` — identifies OS/build; foundation for all plugins.
- `vol -f <image> windows.pslist / windows.psscan` — process lists; the pslist-vs-psscan diff is the core hiding check.
- `vol -f <image> windows.netscan` — TCP/UDP endpoints and owning PIDs.
- `vol -f <image> windows.malfind --dump` — injected code detection with dump output.
- `vol -f <image> windows.modules / windows.modscan` — kernel module inventory.
- `vol -f <image> windows.cmdline / windows.consoles` — command-line and console history.
- `vol -f <image> windows.registry.hivelist / windows.registry.printkey` — in-memory registry.
- `vol -f <image> windows.ssdt / windows.callbacks` — kernel hooks and notification callbacks.
- `vol -f <image> windows.filescan` — resident file object scan.
- `vol -f <image> windows.timeliner --output-file timeline.csv` — unified timeline of memory artifacts.
- `vol -f <image> windows.getsids --pid <PID>` — token SIDs; spot privilege anomalies.
- `vol -f <image> windows.hashdump` — SAM hashes; lab-only, authorized cases, sensitive handling.
- `vol -f <image> windows.envars --pid <PID>` — process environment variables.
- `vol -f <image> windows.sessions` — logon session enumeration.
- Volatility 2 equivalents (legacy): `vol.py -f <image> --profile=Win10x64_19041 pslist`, `netscan`, `malfind -D <dir>`.

## Expected outputs

- Verified image hash matching the acquisition record.
- Process inventory with hidden-process diff results (PID, image name, PPID).
- Network endpoint list mapped to owning processes.
- Injected-code dumps from `malfind` with extracted strings/YARA hits.
- Kernel module list with anomalies flagged against baseline.
- Registry persistence keys resident in memory.
- Unified memory timeline CSV merged with the disk forensic timeline.
- Credential-artifact inventory with an access and handling log.
- A findings memo: what ran, what hid, what talked to the network, and what remains unanswered.

## Pitfalls

- Skipping the hash check and analyzing a corrupted or swapped image.
- Using the wrong Volatility 2 profile — every plugin then returns garbage or nothing; prefer Volatility 3's auto-detection.
- Treating `psscan` entries as live processes — it finds terminated-process remnants too; verify with thread and handle data.
- Analyzing on the suspect host or mounting the image read-write, destroying evidence integrity.
- Stopping at memory: fileless malware still leaves disk/log traces (WMI subscriptions, scheduled tasks) — correlate.
- Dumping process memory with `--dump` into an uncontained directory; treat dumps as live malware.
- Running `hashdump` without explicit authorization or mishandling its output — it is credential material.
- Drowning in `timeliner` noise — filter to the incident window before drawing conclusions.
- Pasting `envars` output into reports unredacted — it can contain secrets.

See also: analyzing-memory-forensics-with-lime-and-volatility.md

## References

- Volatility 3 documentation: https://volatility3.readthedocs.io
- Volatility Foundation project: https://github.com/volatilityfoundation/volatility3
- MITRE ATT&CK T1055 (Process Injection), T1003 (OS Credential Dumping), T1014 (Rootkit)
- SANS FOR508 memory-forensics methodology guidance
- NIST SP 800-86, Guide to Integrating Forensic Techniques into Incident Response

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
