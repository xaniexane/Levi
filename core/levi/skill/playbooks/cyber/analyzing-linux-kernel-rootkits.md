---
skill_id: cyber_analyzing_linux_kernel_rootkits
name: Analyzing Linux Kernel Rootkits
description: Detect kernel-mode rootkits: syscall-table hooks, module hiding, and memory forensics.
risk: low
permissions: []
requires_confirmation: false
tags: [malware-analysis, linux]
version: 1.0.0
---
# Analyzing Linux Kernel Rootkits

## Purpose

Kernel rootkits hide processes, files, and network connections by subverting
the kernel itself — via loadable kernel modules (LKMs), syscall-table hooks, or
direct kernel-object manipulation. Because they defeat on-host tooling, the
reliable detection path is memory forensics plus integrity comparison. This
playbook covers detecting, confirming, and eradicating Linux kernel rootkits.

## When to use

- A host shows signs of compromise but `ps`, `netstat`, and `ls` disagree with
  memory or network evidence (hidden processes/connections).
- Unexplained kernel modules, or `lsmod` output that changes between boots.
- Post-incident validation that a compromised host is truly clean before
  return to service.

See also: analyzing-bootkit-and-rootkit-samples.md

## Prerequisites

- Written authorization to capture full physical memory and to take the host
  offline; memory images contain credentials and PII — encrypt at rest and
  restrict access.
- The host should be considered untrusted: do not rely on its own binaries
  (`ps`, `lsmod`) for conclusions — use memory forensics from a trusted
  analysis machine.
- Known-good baselines where available: kernel version, expected module list,
  and Secure Boot / module-signing policy.

## Procedure

1. Capture physical memory with a trusted tool (LiME, AVML, or your EDR's
   memory-capture feature) and hash the image immediately. Prefer capturing
   before any remediation reboot.
2. Build or obtain a Volatility 3 symbol/profile set matching the exact kernel
   version (`uname -r` from the image); without correct symbols, Linux plugins
   misbehave.
3. Cross-view process and module lists:
   - `linux.pslist` vs. `linux.pstree` — look for processes visible in one
     view but not the other (DKOM hiding).
   - `linux.lsmod` vs. modules recovered from memory scans — LKMs hidden from
     the module list are a classic rootkit indicator.
4. Check syscall-table integrity: `linux.check_syscall` flags hooked syscall
   entries; compare the handler addresses against the expected kernel text
   range — handlers pointing into module memory are hooks.
5. Inspect for inline hooks and IDT tampering: `linux.check_idt` and review
   suspicious function-pointer overwrites in network and VFS paths.
6. Examine kernel modules on disk: compare `/lib/modules/<ver>/` contents and
   `modules.dep` against the running set; look for recently modified `.ko`
   files, unsigned modules on a signing-enforced host, and modules with no
   corresponding package (`dpkg -S` / `rpm -qf`).
7. Run on-host corroboration only from trusted media: `rkhunter --check` and
   `chkrootkit` from a live CD/USB, comparing their findings with the memory
   analysis — treat on-host tool output as advisory, not conclusive.
8. Determine the rootkit family from strings and behavior in the dumped module
   (extract the `.ko` from memory or disk, then static-analysis per the ELF
   malware playbook) to find its persistence mechanism and C2.
9. Eradicate by rebuilding, not cleaning: back up data, wipe, and reinstall
   from known-good media; rotate all credentials that existed on the host.
   Kernel-level compromise cannot be reliably "cleaned" in place.
10. Harden the rebuilt host: enable Secure Boot, enforce kernel-module
    signing, disable module loading if the workload allows
    (`kernel.modules_disabled=1`), and deploy integrity monitoring.

## Key tools & commands

- Volatility 3: `linux.pslist`, `linux.lsmod`, `linux.check_syscall`,
  `linux.check_idt`, `linux.hidden_modules`-style cross-view plugins.
- LiME / AVML — trusted memory acquisition on Linux.
- `rkhunter --check`, `chkrootkit -q` — on-host heuristic scanners (run from
  trusted media).
- `modinfo <module>`, `lsmod`, `/proc/modules` — module metadata (advisory
  on a suspect host).
- `mokutil --sb-state` — Secure Boot status verification.

## Expected outputs

- Confirmation (or exclusion) of kernel compromise with cited evidence:
  hooked syscalls, hidden modules, cross-view discrepancies.
- Rootkit family identification and its persistence/C2 profile.
- Eradication record: rebuild performed, credentials rotated.
- Hardening changes: Secure Boot, module signing, monitoring deployed.

## Pitfalls

- Trusting on-host `ps`/`lsmod`/`netstat` output on a suspected host — a
  kernel rootkit's entire job is lying to these tools.
- Volatility symbol mismatch: wrong kernel profile produces garbage or
  crashes; verify `uname -r` from within the image first.
- Concluding "clean" from `rkhunter`/`chkrootkit` alone — they miss modern
  DKOM and in-memory-only rootkits; memory forensics is the standard.
- Attempting in-place removal of a kernel rootkit and returning the host to
  service — assume persistence you cannot see and rebuild.
- Forgetting firmware/UEFI: if the rootkit arrived via bootkit, a disk wipe
  is insufficient (see the sibling bootkit playbook).

## References

- Volatility 3 Linux plugin documentation (volatility3.readthedocs.io)
- MITRE ATT&CK: T1014 (Rootkit), T1547.006 (Kernel Modules and Extensions),
  T1564 (Hide Artifacts)
- NIST SP 800-86, Guide to Integrating Forensic Techniques into Incident Response
- CIS Linux Benchmarks (Secure Boot, kernel-module controls)

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
