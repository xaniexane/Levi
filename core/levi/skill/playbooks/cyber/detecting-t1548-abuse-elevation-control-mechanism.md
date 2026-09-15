---
skill_id: cyber_detecting_t1548_abuse_elevation_control_mechanism
name: Detecting T1548 Abuse Elevation Control Mechanism
description: Detect ATT&CK T1548 elevation-control abuses: bypasses, setuid, sudo exploits.
risk: low
permissions: []
requires_confirmation: false
tags: [privilege-escalation, mitre-attack, detection]
version: 1.0.0
---
## Purpose

T1548 (Abuse Elevation Control Mechanism) covers bypassing the controls that gate privilege elevation: UAC bypasses, sudo/suid abuse, and authorization-plugin exploitation. This playbook maps the sub-techniques to detections across Windows and Linux, focusing on the bypass behaviors rather than the payloads they enable.

## When to use

- You need ATT&CK-mapped coverage for elevation-control bypasses.
- UAC-bypass or sudo-exploit attempts need dedicated detections.
- Purple-team testing T1548 variants.
- Hardening assessment of elevation controls.

## Prerequisites

- Windows: Security logs (4672, 4688), Sysmon (Event 1 with integrity levels, Event 13 registry); Linux: auditd (execve, setuid), sudo logs, auth logs.
- Inventory of elevation mechanisms in use: UAC settings, sudoers, setuid binaries, polkit, AuthorizationExecuteWithPrivileges (macOS).
- Baseline of legitimate elevation workflows per platform.
- T1548 sub-technique list (T1548.001–T1548.004) as coverage framework.

## Procedure

1. Map sub-techniques to platform telemetry. T1548.001 Setuid/Setgid → Linux auditd execve of setuid binaries, unexpected setuid bit changes (chmod +s), new setuid files. T1548.002 Bypass UAC → Windows auto-elevate binary abuse (fodhelper, eventvwr, computerdefaults patterns), registry hijacks under auto-elevated COM keys, integrity-level anomalies. T1548.003 Sudo caching / T1548.004 Elevated Execution with Prompt → sudo timestamp abuse, unexpected sudoers modifications, authorization-plugin exploitation. Document telemetry per sub-technique.
2. Detect UAC bypass patterns (Windows). Alert on: auto-elevating binaries (fodhelper.exe, eventvwr.exe, sdclt.exe, computerdefaults.exe) spawned with suspicious command lines or by unusual parents, registry writes to the COM/auto-elevate hijack keys followed by elevated process creation, and processes jumping from medium to high integrity without a consent prompt event. Pair with parent/child context — Office apps spawning fodhelper is never legitimate.
3. Detect setuid/sudo abuse (Linux/macOS). Alert on: execution of unexpected setuid binaries, setuid bit set on new or copied files (hunt for recently chmodded binaries), sudoers file modifications outside change management, sudo timestamp-file manipulation, and polkit rule changes. Maintain a known-good setuid inventory per build — any deviation is a finding.
4. Detect authorization-mechanism tampering. Alert on: modifications to sudoers.d, polkit policies, macOS authorization database, and PAM configuration; disabling of UAC via registry (EnableLUA changes); and tools that manipulate elevation prompts. Tampering with the control itself is higher severity than a single bypass — it enables repeated silent elevation.
5. Correlate bypass with objective. Elevation bypass is a means: follow each alert to what the elevated process did — credential access, persistence installation, defense disabling. A UAC bypass that installs a scheduled task is an incident; scope the full chain. Also verify the bypass didn't disable your telemetry (attackers bypass UAC then kill EDR).
6. Harden the controls: enforce UAC at appropriate levels (never disable), minimize setuid binaries (remove unneeded bits), manage sudoers via configuration management with reviews, patch elevation CVEs urgently, and move to just-in-time elevation. Detection compensates; least-privilege architecture prevents.

## Expected outputs

- T1548 coverage matrix: sub-technique → telemetry → rule → validation status.
- Platform-specific rules: UAC bypass (Windows), setuid/sudo/polkit (Linux/macOS).
- Known-good setuid inventory and sudoers baselines.
- Elevation-control hardening backlog.

## Pitfalls

- UAC bypass techniques evolve rapidly — behavior rules (integrity jumps, parent anomalies) outlast technique-specific ones.
- Legitimate admin tools trigger elevation constantly — baseline per workflow, not per binary.
- Setuid inventory drifts with patching — refresh per build, automate where possible.
- Disabling UAC 'for compatibility' removes the control entirely — treat as a security exception requiring approval.
- macOS authorization mechanisms differ from Linux — don't copy Linux rules to Mac fleets.

## References

- MITRE ATT&CK T1548 (Abuse Elevation Control Mechanism) — https://attack.mitre.org/techniques/T1548/; Microsoft Learn: UAC architecture; Linux auditd documentation
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
