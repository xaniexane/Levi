---
skill_id: cyber_hunting_for_process_injection_techniques
name: Hunting for Process Injection Techniques
description: Detect process injection (DLL injection, hollowing, APC, thread hijacking) via memory analysis and EDR behavioral telemetry.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, malware, edr]
version: 1.0.0
---
## Purpose

Process injection — executing code inside another process's address
space — is central to modern malware: it hides payloads, inherits
trusted process identities, and evades naive allow-listing. This playbook
covers detecting the major injection families (classic DLL injection,
process hollowing, PE-splicing/process doppelgänging variants, APC
injection, thread hijacking) in EDR telemetry and memory forensics.

## When to use

- Investigating EDR alerts for injection-like behavior.
- Hunting for fileless malware and in-memory implants.
- Triaging suspicious processes with anomalous memory regions.
- Validating EDR behavioral coverage of injection techniques.

## Prerequisites

- EDR with behavioral/memory visibility or Sysmon with events 8
  (CreateRemoteThread), 10 (ProcessAccess), and 7 (ImageLoad).
- Memory-forensics capability (Volatility 3) for confirmation.
- Baselines: legitimate software that injects (security products,
  accessibility tools, some game anti-cheat) to avoid false positives.
- Understanding of the target OS's normal process memory layouts.

## Procedure

1. **Know the technique family.** Map what you are hunting: classic
   DLL injection (remote thread + LoadLibrary), process hollowing
   (unmapped + rewritten image), APC injection (queued APCs to alertable
   threads), thread hijacking/execution (suspended-thread context
   modification), and module stomping/PE-splicing variants. Each has
   distinct telemetry artifacts.
2. **Hunt remote-thread creation.** Query Sysmon event 8 for
   CreateRemoteThread where the source and target are an unusual pair —
   especially injections into system processes (lsass, svchost,
   explorer) from user-context or unsigned sources. Baseline security
   products first.
3. **Hunt suspicious process-access patterns.** Review Sysmon event 10
   for processes opening others with VM_WRITE/VM_OPERATION-heavy access
   masks outside legitimate debugger/monitoring scenarios.
4. **Hunt image-load anomalies.** Check Sysmon event 7 for unsigned
   DLLs loaded into signed processes, DLLs loaded from unusual paths
   (temp, user-writable), and signed-binary-injection indicators where
   the loaded image does not match the expected module list.
5. **Confirm with memory analysis.** For high-confidence candidates,
   capture process memory and examine: private executable regions not
   backed by disk images, PE headers in memory that do not match the
   on-disk image (hollowing), and injected threads' start addresses
   pointing to non-image memory.
6. **Correlate the full chain.** Identify the injector (parent chain,
   how it arrived) and the injected payload's behavior (network
   connections from the victim process, subsequent actions). Injection
   is a means — find both the means and the ends.
7. **Scope and contain.** Determine all injected processes and hosts,
   isolate, capture memory images for evidence, and remediate per the
   IR plan (injection often indicates an active implant requiring full
   host rebuild).
8. **Build durable detections.** Convert validated patterns to EDR/SIEM
   rules (remote-thread pairs, unsigned image loads, hollowed-process
   memory traits) and track precision over time.

## Expected outputs

- Injection findings with technique classification and memory
  evidence.
- Injector-to-payload chains with full attack context.
- Memory images preserved for confirmed cases.
- New behavioral detections with tuning history.

## Pitfalls

- Security products inject legitimately and constantly — baseline
   them thoroughly or the hunt is unusable.
- Sysmon event 8/10 volume is high — scope queries by unusual
   source/target pairs, not raw event counts.
- Memory analysis of a live injected process can be destabilizing —
   capture first, analyze the image.
- Some injection (early-bird APC, kernel callbacks) has limited
   user-mode telemetry — acknowledge the visibility gap and layer
   defenses (Credential Guard, HVCI, WDAC).
- Declaring a process "clean" from user-mode telemetry alone —
   hollowed processes look normal to naive process listing.

## References

- MITRE ATT&CK: T1055 and sub-techniques (process injection family)
- Sysmon documentation (events 7, 8, 10)
- Volatility 3 documentation (malfind and related plugins)
- Microsoft Learn: memory-protection and virtualization-based
  security guidance
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
