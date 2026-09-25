---
skill_id: cyber_hunting_for_webshell_activity
name: Hunting for Webshell Activity
description: Detect webshells on web servers: file-creation anomalies, access-pattern analysis, and command-execution telemetry.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, web, persistence]
version: 1.0.0
---
## Purpose

Webshells — malicious scripts planted on web servers — give attackers
persistent, interactive access through the web tier and are a staple of
both targeted intrusions and mass-exploitation campaigns. This playbook
covers hunting webshells via file-system, access-log, and process
telemetry, plus eradication and hardening.

## When to use

- After patching internet-facing applications (especially following
  mass-exploited CVEs): assume webshells until proven otherwise.
- Investigating suspicious web-server process behavior (cmd.exe or
  PowerShell spawned by w3wp/php-fpm).
- Threat hunting following webshell-related threat intel.
- Validating web-server file-integrity monitoring.

## Prerequisites

- Web-server access logs with timestamps, URIs, parameters, status
  codes, and user agents.
- File-integrity or file-creation telemetry for web document roots.
- Process-creation logs on web servers (web worker → script
  interpreter → OS command chains).
- Known-good file inventory (hashes) of the web application.

## Procedure

1. **Establish the known-good baseline.** Hash all files in document
   roots and compare against deployment artifacts and version control.
   Unknown files — especially with recent timestamps, odd names, or in
   upload/temp directories — are the primary suspects.
2. **Hunt file-creation anomalies.** Look for script files (.php,
   .aspx, .jsp, .asp) created outside deployment processes, files with
   double extensions or image extensions containing script content,
   and recently modified files inconsistent with release history.
3. **Analyze access patterns.** In access logs, hunt: rare URIs
   accessed with POST requests and parameters, the same URI hit with
   varying parameter values (interactive use), requests with
   webshell-associated user agents or missing referrers, and access
   from unusual geographies or Tor exits.
4. **Hunt command-execution chains.** On the server, look for OS
   commands spawned by web-worker processes (w3wp.exe → cmd.exe/
   powershell.exe, php-fpm → sh) — this is the highest-fidelity
   webshell signal. Correlate process start times with suspicious
   access-log entries.
5. **Inspect suspect files safely.** Review candidate files' contents
   in an isolated environment: obfuscated code, eval/exec constructs,
   password-protected access panels, and file-manager/upload
   functionality confirm webshells. Do not execute them on the server.
6. **Scope the intrusion.** For each confirmed webshell: determine
   implantation date (file timestamps, logs), what commands were run
   (access-log parameters, process history), whether it was used for
   lateral movement or persistence, and whether additional webshells
   exist (sweep all web servers, not just the first).
7. **Eradicate thoroughly.** Remove webshell files, kill related
   processes, rotate credentials accessible from the web tier,
   rebuild or restore the server from known-good media (webshells
   imply deeper compromise until proven otherwise), and patch the
   exploited vulnerability.
8. **Harden the web tier.** Deploy WAF rules for webshell-upload
   patterns, enforce file-integrity monitoring on document roots,
   restrict upload functionality, run app pools with least privilege,
   and add durable detections for web-worker process anomalies.

## Expected outputs

- Webshell findings: file paths, hashes, implantation dates, and
  analyzed capabilities.
- Access-log analysis: attacker IPs, accessed URIs, and executed
  commands.
- Scoping: lateral movement and data access from each webshell.
- Eradication verification and server rebuild records.
- Hardening changes and durable detections.

## Pitfalls

- Removing the webshell without patching the entry vulnerability —
   re-compromise is usually fast.
- Legitimate admin scripts in document roots look like webshells —
   baseline and validate before deleting production functionality.
- Encoded/obfuscated parameters hide commands in logs — correlate
   with process telemetry rather than relying on log readability.
- Attackers plant multiple webshells — finding one is the start, not
   the end, of the sweep.
- Assuming the web tier is the only foothold — webshells are often
   used to pivot inward; scope the internal network too.

## References

- MITRE ATT&CK: T1505.003 (Server Software Component: Web Shell)
- CISA: webshell-related advisories and detection guidance
- OWASP: file-upload and unrestricted-upload prevention guidance
- NIST SP 800-44: Guidelines on Securing Public Web Servers
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
