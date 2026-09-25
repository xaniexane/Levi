---
skill_id: cyber_implementing_memory_protection_with_dep_aslr
name: Implementing Memory Protection with DEP and ASLR
description: Harden systems and applications with Data Execution Prevention and Address Space Layout Randomization, plus verification and compensating controls for legacy software.
risk: info
permissions: []
requires_confirmation: false
tags: [hardening, exploit-mitigation, endpoints]
version: 1.0.0
---
## Purpose

Raise the cost of memory-corruption exploitation across the fleet. Data Execution Prevention (DEP/NX) stops injected shellcode from executing on the stack and heap; Address Space Layout Randomization (ASLR) denies attackers the predictable addresses their exploits rely on. Together — enforced by OS policy and verified per application — they convert many would-be remote-code-execution vulnerabilities into mere crashes.

## When to use

- Establishing baseline endpoint and server hardening (CIS Benchmarks, STIGs).
- Reducing exploitability of C/C++ applications, browsers, document readers, and other memory-unsafe software.
- Meeting compliance expectations for technical exploit-mitigation controls.
- After a penetration test demonstrates trivial exploitation of a memory-corruption bug.
- Auditing whether legacy applications opted out of OS protections.

## Prerequisites

- Inventory of operating systems and their DEP/ASLR capabilities and defaults (modern Windows, Linux, macOS enable both by default; the work is in enforcement and exceptions).
- List of applications with known incompatibilities (legacy software, JIT compilers, self-modifying code, some industrial/OT applications).
- Administrative control over endpoint configuration (Group Policy, MDM, Ansible/Puppet, or EDR policy).
- A test environment representing production workloads for compatibility validation.
- Crash/telemetry collection so newly enabled mitigations' fallout is visible, not silent.

## Procedure

1. **Verify OS-level defaults are enforced.** Confirm DEP/NX is enabled (Windows: `bcdedit` / `Get-ProcessMitigation`; Linux: check `dmesg | grep -i nx`, kernel with `CONFIG_X86_X2APIC` era defaults; hardware NX bit present in `/proc/cpuinfo` flags). Enable ASLR system-wide (Linux: `kernel.randomize_va_space=2`; Windows: system-wide ASLR via Exploit Protection). These are defaults on modern systems — verify rather than assume, especially on hardened or minimal images.
2. **Enforce per-process mitigations.** On Windows, use Process Mitigation / Exploit Protection to mandate DEP, ASLR (force relocation for non-ASLR images), SEHOP, and CFG for application fleets via Group Policy or Intune. On Linux, prefer distributions and builds with PIE (position-independent executables) so ASLR applies to the main binary, not just libraries.
3. **Audit application opt-outs.** Scan for binaries lacking ASLR/DEP support: on Windows check PE headers (`Get-ProcessMitigation`, or dumpbin `/headers` for DYNAMIC_BASE/NXCOMPAT); on Linux check `hardening-check` or `checksec.sh` output for `No PIE`, `No NX`, missing RELRO/Canary. Every opt-out becomes a tracked exception with an owner and a remediation plan.
4. **Handle legacy exceptions narrowly.** Where a legacy application genuinely breaks (common in OT and old line-of-business software), exempt the specific binary — never disable the mitigation system-wide. Document the compensating controls: network isolation, application allowlisting, enhanced monitoring of the exempt process.
5. **Extend to the modern mitigation set.** DEP+ASLR are the floor, not the ceiling: enable Control Flow Guard/Integrity (Windows CFG, Linux CET/IBT where hardware supports), stack canaries (compile-time), and SEHOP. For browsers and high-risk apps, ensure sandboxing is active — mitigations layer, they do not substitute for each other.
6. **Validate with exploit-attempt telemetry.** Confirm EDR/AV exploit-protection modules report blocked exploitation attempts (e.g., blocked ROP, heap-spray, or stack-pivot detections). A mitigation nobody observes is a mitigation nobody can prove works.
7. **Build mitigations into the SDLC.** Require PIE, NX, RELRO, canaries, and CFG/CET in build flags for in-house software (`-fPIE -pie -Wl,-z,Noexecstack -fstack-protector-strong` on GCC/Clang; `/DYNAMICBASE /NXCOMPAT /CETCOMPAT /guard:cf` on MSVC) and gate releases on `checksec`-style verification in CI.
8. **Re-audit on change.** Re-scan binaries after every major application upgrade or OS migration; vendors silently drop hardening flags. Include mitigation status in the asset/vulnerability reporting.

## Expected outputs

- OS-level DEP/ASLR enforcement verified across the fleet with configuration evidence.
- Binary audit report listing opt-outs, each with owner, justification, and compensating controls.
- Build-flag standards and CI verification for in-house software.
- EDR exploit-protection telemetry confirming mitigation effectiveness.
- Exception register reviewed on a defined cadence.

## Pitfalls

- **Assuming defaults cover everything.** Third-party and legacy binaries frequently ship without DYNAMIC_BASE or PIE; the OS default does not fix a binary that opted out at link time.
- **System-wide exemptions for one bad app.** Disabling DEP or ASLR globally because one legacy application crashes trades fleet-wide protection for a single vendor's technical debt. Exempt the binary, isolate the host.
- **Ignoring JIT-heavy applications.** Browsers, runtimes, and document readers legitimately need executable memory regions; they rely on sandboxing plus fine-grained mitigations (ACG, CFG) rather than blanket DEP. Apply the right mitigations per application class.
- **No visibility into mitigation-triggered crashes.** Newly enforced mitigations can crash fragile apps; without crash telemetry, help desks chase ghosts and pressure builds to disable the control.
- **Treating mitigations as patching.** DEP/ASLR raise exploit cost; they do not fix the underlying vulnerability. Patch management remains mandatory — mitigations buy time, not immunity.

## References

- Microsoft Learn: Process mitigations / Windows Defender Exploit Guard — https://learn.microsoft.com/en-us/windows/security/threat-protection/
- NIST SP 800-53 Rev. 5, SI-16 (Memory Protection) — https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final
- CIS Benchmarks (OS-level exploit mitigation settings) — https://www.cisecurity.org/cis-benchmarks
- MITRE ATT&CK T1203 (Exploitation for Client Execution) — https://attack.mitre.org/techniques/T1203/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
