---
skill_id: cyber_detecting_process_injection_techniques
name: Detecting Process Injection Techniques
description: Comprehensive detection for process injection techniques (T1055 sub-techniques).
risk: low
permissions: []
requires_confirmation: false
tags: [process-injection, edr, detection]
version: 1.0.0
---
## Purpose

Process injection — running code inside another process's address space — underpins credential theft, defense evasion, and C2. ATT&CK catalogs many variants (DLL injection, PE injection, thread execution hijacking, APC injection, and more). This playbook gives defenders a unified detection strategy across the T1055 family: common telemetry, per-variant nuances, and rules that generalize.

## When to use

- You need comprehensive T1055 coverage, not just one injection variant.
- EDR injection alerts need tuning — too noisy or missing variants.
- Threat hunting for in-memory tradecraft after a suspected intrusion.
- Purple-team results show injection blind spots.

## Prerequisites

- Sysmon with Event IDs 8 (CreateRemoteThread), 10 (ProcessAccess), 7 (ImageLoad); or EDR with thread/memory telemetry.
- Memory-forensics capability (Volatility) for confirmation.
- Baseline of legitimate injectors: security products, accessibility tools, application compatibility shims.
- ATT&CK T1055 sub-technique list for coverage mapping.

## Procedure

1. Map coverage per sub-technique. Inventory your detections against T1055.001–T1055.015 (DLL injection, PE injection, thread hijacking, APC/queue APC, process hollowing, Ptrace, etc.). Most organizations cover DLL injection and hollowing but miss APC injection, thread-local-storage callbacks, and extra-window-memory injection — the mapping reveals the gaps to prioritize.
2. Build the common detection core. Across variants, alert on: CreateRemoteThread (Event 8) with suspicious start addresses (unbacked memory), cross-process memory writes followed by remote thread creation, processes loading DLLs from unusual paths (Event 7 with non-standard ImageLoaded), and LSASS or security-product processes as injection targets. This core catches most variants regardless of specific API sequence.
3. Add variant-specific rules for high-risk techniques. APC injection: alert on QueueUserAPC patterns into threads of target processes. Thread execution hijacking: SetThreadContext anomalies on suspended threads. Ptrace (Linux): unexpected ptrace attachments. Module stomping/overwriting: image-load events where the loaded module hash doesn't match the on-disk file. One focused rule per variant you actually see in intel.
4. Baseline legitimate injection aggressively. Security products, screen readers, gaming overlays, and application shims inject legitimately — document them by (source image, target process, technique) and exclude precisely. Blanket exclusions by technique name ('ignore all CreateRemoteThread') destroy coverage; exclusions must be source-specific.
5. Confirm in memory, hunt at scale. For alerts: validate with memory forensics (identify the injected payload), extract IOCs, then hunt fleet-wide for the same injection source/target patterns and payload hashes. Injection is a means, not an end — always determine what the injected code did (C2 beacon, credential theft, ransomware).

## Expected outputs

- T1055 coverage matrix: sub-technique → detection rule → status (covered/partial/gap).
- Core injection detections plus variant-specific rules for prioritized techniques.
- Legitimate-injector baseline with precise exclusions.
- Memory-confirmation and fleet-hunting procedure.

## Pitfalls

- Excluding by technique name instead of by legitimate source destroys detection value.
- Some variants (APC, TLS callbacks) generate no CreateRemoteThread — Event 8-only coverage misses them.
- Legitimate security products are the noisiest injectors; work with vendors to document their behavior.
- Detecting injection without identifying the payload leaves the incident unscoped — always extract and analyze.
- Linux/macOS injection (ptrace, dylib hijacking) needs separate telemetry — don't assume Windows-only coverage.

## References

- MITRE ATT&CK T1055 (Process Injection) and sub-techniques — https://attack.mitre.org/techniques/T1055/; Sysmon documentation (Events 7, 8, 10); Volatility documentation for memory confirmation
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
