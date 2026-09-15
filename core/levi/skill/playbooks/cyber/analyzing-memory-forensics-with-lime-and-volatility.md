# Analyzing Memory Forensics with LiME and Volatility

## Purpose

Acquire a forensically sound full-memory image from a live Linux host with LiME (Linux Memory Extractor) and then analyze it with Volatility, closing the loop from acquisition to findings with a single defensible workflow.

## When to use

- A Linux server or workstation is suspected of compromise and you need volatile evidence (running processes, sockets, kernel modules) that disk forensics cannot provide.
- You have console/SSH access to the suspect host and authorization to load a kernel module.
- The kernel version is supported by your LiME build; otherwise fall back to `/dev/crash`, `makedumpfile`, or hypervisor snapshots.

## Prerequisites

- Written authorization to run acquisition on the target host; incident ticket or case number recorded.
- Chain-of-custody procedure ready: record hashes immediately after capture, note date/time/timezone and operator.
- LiME compiled against the target kernel (or DKMS-style build on the host); matching kernel headers available.
- An isolated analyst workstation with Volatility 3 (Linux profile support) installed.
- Sufficient storage: the dump equals physical RAM size; plan for it before starting.

## Procedure

1. Confirm the host's kernel version and architecture:
   `uname -r && uname -m`
   This determines which LiME binary or build you need.
2. Prepare the LiME module for that kernel. If building on the host:
   `cd lime/src && make`
   If pre-built elsewhere, transfer only the matching `lime.ko`.
3. Choose an acquisition target. Local disk (fast, but alters disk state) or TCP (network exfil of RAM; encrypt the channel):
   Local: `insmod lime.ko "path=/mnt/evidence/mem.lime format=lime"`
   TCP: `insmod lime.ko "path=tcp:4444 format=lime"` with a listener on the analyst side: `nc -l -p 4444 > mem.lime`
4. Record start time, then load the module. Do not run anything else on the host first — every command overwrites memory you want to capture.
5. After `insmod` returns, verify the output file exists and is growing to roughly RAM size:
   `ls -lh /mnt/evidence/mem.lime`
6. Unload the module when acquisition completes: `rmmod lime`
7. Immediately hash the image and log it:
   `sha256sum mem.lime | tee mem.lime.sha256`
8. Transfer the image and its hash to the analyst workstation over an encrypted channel; verify the hash on receipt.
9. Identify the Linux profile with Volatility 3:
   `vol -f mem.lime linux.info` (Volatility 3) or build the profile with `dwarfdump` for Volatility 2.
   If symbols are missing, install the matching `linux-image-$(uname -r)-dbg` / debuginfo package and rebuild.
10. Enumerate processes and look for anomalies:
    `vol -f mem.lime linux.pslist` and `vol -f mem.lime linux.pstree`
    Note processes with no parent, odd names, or unexpected UIDs.
11. Check network state:
    `vol -f mem.lime linux.netstat` — map listening ports and established sessions to PIDs from step 10.
12. Inspect loaded kernel modules for rootkit indicators:
    `vol -f mem.lime linux.lsmod` then `vol -f mem.lime linux.modscan`
    Compare against the distribution's known module list; unknown names warrant dumping.
13. Examine the bash history resident in memory and process environments:
    `vol -f mem.lime linux.bash` and `vol -f mem.lime linux.envvars --pid <PID>`
14. Check for hidden files and suspicious mounts:
    `vol -f mem.lime linux.mountinfo` and `vol -f mem.lime linux.check_syscall` / `linux.check_idt` for hooks.
15. Dump suspicious process address spaces for offline review:
    `vol -f mem.lime linux.proc --pid <PID> --dump-dir ./dumps/`
    Analyze strings and YARA hits inside your contained lab.
16. Check for syscall and IDT hooks indicating a kernel rootkit:
    `vol -f mem.lime linux.check_syscall` and `vol -f mem.lime linux.check_idt`
    Any hooked entry not attributable to installed security tooling is a major finding.
17. Inventory mapped ELF binaries and recover resident file content:
    `vol -f mem.lime linux.elfs`
    Compare unexpected binaries against distribution packages.
18. Group recovered bash history by UID and compare against on-disk `.bash_history` files — wiped or truncated on-disk history next to rich in-memory history indicates anti-forensics.
19. Correlate with host logs (`/var/log/auth.log`, `auditd`, `journalctl`) and disk artifacts before finalizing findings.

## Key tools & commands

- LiME: `insmod lime.ko "path=<target> format=lime"` — kernel-level RAM acquisition; `format=raw` also available.
- `vol -f <image> linux.info` — validates the Linux profile/symbols.
- `vol -f <image> linux.pslist / linux.pstree` — process enumeration.
- `vol -f <image> linux.netstat` — sockets mapped to processes.
- `vol -f <image> linux.lsmod / linux.modscan` — kernel module inventory and hidden-module scan.
- `vol -f <image> linux.bash` — recovered bash command history.
- `vol -f <image> linux.check_syscall` — syscall table hook detection.
- `vol -f <image> linux.check_idt` — interrupt descriptor table hook detection.
- `vol -f <image> linux.elfs` — ELF binaries mapped in memory.
- `vol -f <image> linux.mountinfo` — mount points visible to the kernel.
- `vol -f <image> linux.proc --pid <PID> --dump-dir` — per-process memory dumps.
- `dwarfdump` / distribution debuginfo packages — building symbols when profiles are missing.
- YARA + `strings` — offline review of dumped process memory.
- `sha256sum`, `nc` — hashing and TCP transfer of the image.

## Expected outputs

- `mem.lime` image with matching SHA-256 at capture and at receipt.
- Case notes: acquisition command, kernel version, timestamps, operator.
- Process tree with anomalies annotated; socket-to-process mapping.
- Kernel module inventory vs. baseline, hook-check results.
- Dumped suspicious process memory with string/YARA review notes.
- Syscall/IDT hook-check results with a disposition for each hooked entry.
- ELF binary inventory compared against the distribution package baseline.
- Findings memo linking memory evidence to host logs.

## Pitfalls

- Loading a LiME build for the wrong kernel — `insmod` fails or, worse, destabilizes the host; verify `uname -r` first.
- Writing the image to the suspect host's own disk, overwriting unallocated-space evidence; prefer TCP or external media.
- Running triage commands before acquisition, tainting the very memory you intend to capture.
- Volatility 2 without a matching profile — build symbols from the exact kernel; close is not good enough.
- Treating `linux.bash` output as complete history — it recovers fragments; cross-check with on-disk `.bash_history`.
- Forgetting to `rmmod lime` and leaving an acquisition module loaded on a production host.
- Symbol mismatch producing silently empty plugin output — rebuild against the exact kernel version.
- Corrupted TCP transfers — always re-verify the hash on receipt, not just at capture.

See also: analyzing-memory-dumps-with-volatility.md

## References

- LiME project: https://github.com/504ensicsLabs/LiME
- Volatility 3 documentation: https://volatility3.readthedocs.io
- Distribution debuginfo guides (Ubuntu ddebs, Debian dbgsym) for profile building
- MITRE ATT&CK T1014 (Rootkit), T1055 (Process Injection), T1070 (Indicator Removal)
- NIST SP 800-86, Guide to Integrating Forensic Techniques into Incident Response

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
