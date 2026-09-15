---
skill_id: cyber_detecting_t1055_process_injection_with_sysmon
name: Detecting T1055 Process Injection with Sysmon
description: Detect ATT&CK T1055 process injection using Sysmon event correlation.
risk: low
permissions: []
requires_confirmation: false
tags: [sysmon, process-injection, mitre-attack]
version: 1.0.0
---
## Purpose

This playbook is the Sysmon-specific companion for T1055 detection: which Sysmon events expose each injection variant, how to write the correlation rules, and how to tune them. It assumes Sysmon is deployed and focuses on turning its process, thread, and image-load telemetry into reliable injection detections.

## When to use

- Sysmon is deployed and you need T1055-specific detections.
- Generic EDR injection alerts need Sysmon-based corroboration.
- Building Sysmon detection rules mapped to ATT&CK.
- Threat hunting injection with Sysmon historical data.

## Prerequisites

- Sysmon with a configuration capturing Event IDs 1 (process creation), 7 (image load), 8 (CreateRemoteThread), 10 (process access) at minimum.
- Centralized Sysmon log collection with sufficient retention.
- Sysmon configuration management (versioned config, change control).
- Baseline of legitimate cross-process activity in your environment.

## Procedure

1. Verify Sysmon captures the injection-relevant events. Audit your Sysmon config: Event ID 8 must not be filtered out, Event ID 10 should include relevant access masks (don't blanket-exclude), Event ID 7 should log DLL loads in target processes, and Event ID 1 must capture full command lines and parent info. A Sysmon config that excludes these for 'noise' reasons silently blinds T1055 detection — review exclusions specifically for injection impact.
2. Build the Event 8 + Event 10 correlation core. Alert on CreateRemoteThread (Event 8) where the StartAddress is in unbacked memory or the target is a sensitive process (lsass, services, browsers), combined with preceding process-access (Event 10) with memory-write access masks from the same source. This two-event sequence is the highest-fidelity generic injection signal in Sysmon data.
3. Add image-load (Event 7) anomaly rules. Alert on: DLLs loaded from user-writable or unusual paths (Temp, Downloads, AppData), unsigned DLLs loaded into signed processes, and DLL loads where the file hash doesn't match the expected module (module stomping). Event 7 catches injection variants that never create remote threads (APC, module overwriting).
4. Cover the variants Event 8 misses. For APC injection: monitor for the thread-queue patterns via Event 10 + subsequent execution anomalies. For process hollowing: Event 1 (suspended process creation) → Event 10/8 → image-path mismatches. For PE injection via process access only: Event 10 with write-heavy access masks into targets followed by thread creation. Document which rule covers which sub-technique.
5. Tune with a legitimate-injector inventory. Document every legitimate cross-process actor (security products, accessibility tools, app-compat shims, game anti-cheat) by (SourceImage, TargetImage, event pattern) and exclude precisely. Review the Sysmon config's own filters — many public configs exclude exactly the events injection detection needs.
6. Validate and hunt. Test each rule against safe injection simulations in a lab, confirm true positives fire and legitimate software doesn't, then hunt historical Sysmon data for the patterns — past undetected injections are common findings. Keep a T1055/Sysmon coverage matrix updated with rule status and test dates.

## Expected outputs

- Sysmon config audit: injection-relevant events verified captured, harmful exclusions removed.
- T1055 Sysmon rules: Event 8+10 correlation core, Event 7 anomalies, variant-specific coverage.
- Legitimate-injector inventory with precise exclusions.
- Coverage matrix with lab-validation and historical-hunt results.

## Pitfalls

- Public Sysmon configs often filter Event 8/10 aggressively — audit before assuming coverage.
- Event 8 alone misses APC, hollowing variants, and module stomping — layer Event 7 and 10.
- Excluding by target process ('ignore injections into chrome.exe') blinds you to real attacks on those targets.
- Sysmon config changes without change control silently break detections — version and review configs.
- High-volume Event 10 logging needs filtering strategy — capture smartly, don't drown the SIEM.

## References

- Sysmon documentation (Event IDs 1, 7, 8, 10); MITRE ATT&CK T1055 — https://attack.mitre.org/techniques/T1055/; SwiftOnSecurity-style public Sysmon config references for comparison (validate before adopting)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
