---
skill_id: cyber_performing_dynamic_analysis_with_any_run
name: Dynamic Analysis with ANY.RUN
description: Detonate suspicious files in an interactive sandbox and turn behavior into IOCs.
risk: info
permissions: []
requires_confirmation: false
tags: [malware, sandbox, threat-intel]
version: 1.0.0
---
# Dynamic Analysis with ANY.RUN

## Purpose

Interactive malware sandboxes let analysts watch a sample execute in a real
Windows VM, clicking through prompts and observing process trees, network
calls, and file drops in real time. This playbook gives defenders a repeatable
workflow for detonating samples in such a sandbox and converting the observed
behavior into detection-ready intelligence.

## When to use

- Triaging email attachments, downloaded executables, or URLs flagged by
  users or mail gateways.
- Confirming whether a blocked file was truly malicious before writing a
  detection rule.
- Harvesting IOCs and TTPs for SIEM, EDR, and firewall blocklists.
- Supporting an incident by understanding exactly what a sample did in the
  first minutes of execution.

## Prerequisites

- A sandbox account (cloud or on-premise) with an isolated analysis VM;
  submissions must never include live customer data or credentials.
- The sample's SHA-256 hash searched in public repositories first — someone
  else's completed analysis may already answer the question.
- Redaction of any sensitive strings (internal hostnames, user names) in
  the sample before upload, per data-handling policy.

## Procedure

1. Submit the file or URL to a fresh sandbox VM matching the target
   environment (Windows version, Office build, locale) and start the task.
2. Watch the interactive session: open documents with macros enabled,
   click through installers, dismiss UAC prompts — mimic a realistic user
   to trigger conditional behavior.
3. Capture the process tree: parent-child relationships, injected
   processes, hollowed processes, and LOLBins used as proxies
   (powershell.exe, mshta.exe, rundll32.exe).
4. Record network activity: DNS resolutions, HTTP/HTTPS requests with
   full URLs, suspicious TLS certificate details, and any C2-like
   beaconing intervals.
5. Collect file and registry artifacts: dropped executables, scheduled
   tasks, Run keys, services, and modified system files, each with hashes.
6. Export the sandbox report: IOC list, MITRE ATT&CK mapping (many
   sandboxes auto-tag techniques), screenshots, and the PCAP.
7. Correlate against internal telemetry: search the SIEM/EDR for the same
   hashes, domains, and parent-child process patterns across the estate.
8. Promote validated IOCs to blocking/detection rules with expiry dates,
   and archive the sandbox task link in the case file.

## Expected outputs

- A behavior timeline from detonation to quiescence with screenshots.
- An IOC bundle: file hashes, domains, IPs, URLs, registry keys.
- An ATT&CK technique mapping for detection coverage review.
- Detection/blocking rules drafted and the sandbox report archived.

## Pitfalls

- Declaring a sample clean after one detonation: evasive samples wait,
  check for virtualization, or require specific user interaction.
- Uploading samples that contain real credentials or PII without
  redaction — treat sandbox submissions as public disclosures.
- Reusing a sandbox session across samples, mixing their artifacts.
- Promoting every observed domain to a permanent block without context,
  which breeds false positives on shared infrastructure.

## References

- MITRE ATT&CK Enterprise matrix (technique pages)
- NIST SP 800-83, Guide to Malware Incident Prevention and Handling
- Sandbox vendor documentation on interactive analysis and report exports
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
