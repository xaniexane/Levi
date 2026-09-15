---
skill_id: cyber_extracting_config_from_agent_tesla_rat
name: Extracting Agent Tesla RAT Configuration
description: Safely extract C2 configuration and IOCs from Agent Tesla samples using sandboxed static and dynamic malware analysis.
risk: low
permissions: []
requires_confirmation: false
tags: [malware, reverse-engineering, threat-intel]
version: 1.0.0
---
## Purpose

Agent Tesla is a long-lived .NET-based remote access trojan / infostealer
sold as "commercial" malware and widely used in phishing campaigns. Its
configuration — exfiltration channels (SMTP, FTP, Telegram, Discord),
credentials, and C2 addresses — is embedded in the sample. This playbook
covers extracting that configuration safely in a sandbox to produce
actionable IOCs for detection and blocking.

## When to use

- A phishing-delivered .NET binary or document macro dropper is
  suspected to be Agent Tesla.
- You need C2/exfil IOCs from a sample to write firewall, proxy, and
  email-gateway blocks.
- Triaging an endpoint alert where an infostealer may have run: the
  config tells you where data went.
- Building detection content for commodity infostealer campaigns.

## Prerequisites

- An isolated malware-analysis VM or sandbox with no route to production
  networks and snapshots for rollback.
- Authorization to handle the sample; treat it as live malware at all
  times.
- Tools: a .NET decompiler/dnSpy-class tool, string-analysis utilities,
  a sandbox (any modern automated sandbox), and network capture.
- A safe IOC-handling workflow: extracted credentials and addresses go
  to the intel pipeline, never pasted into chat or tickets in raw form.

## Procedure

1. **Establish the lab baseline.** Work only in the isolated analysis VM.
   Snapshot before execution. Confirm host-only or sinkholed networking
   so any C2 attempt cannot reach the real infrastructure.
2. **Triage statically first.** Check file type, hashes, compile
   timestamp, and .NET metadata. Agent Tesla samples are typically
   obfuscated .NET assemblies — note the obfuscator family, which guides
   deobfuscation choices.
3. **Extract strings and embedded resources.** Pull ASCII/Unicode strings
   and enumerate .NET resources. Look for SMTP hosts/ports, FTP paths,
   Telegram bot tokens, Discord webhooks, and credential-like strings.
   These are usually the exfiltration configuration in lightly
   obfuscated builds.
4. **Decompile the configuration class.** In the decompiler, locate the
   settings/configuration initialization — Agent Tesla historically
   stores exfil endpoints as encrypted or encoded strings decrypted at
   runtime. Identify the decryption routine and recover the plaintext
   values; document the algorithm for future samples.
5. **Detonate dynamically to confirm.** Execute the sample in the sandbox
   with network capture. Observe DNS queries, SMTP/FTP connections,
   and HTTP(S) posts to confirm which configured channels are actually
   used, and capture the exact exfiltrated data shape (headers, field
   names) for DLP/proxy detection.
6. **Extract persistence and anti-analysis behavior.** Note scheduled
   tasks, startup entries, process-injection targets, and sandbox/VM
   checks — these feed endpoint detections and hunting queries.
7. **Build the IOC package.** Produce file hashes, C2 domains/IPs,
   email addresses, FTP paths, bot tokens/webhooks (report abusive ones
   to the provider), mutexes, and YARA-able strings. Classify each IOC
   by confidence and expiry expectation.
8. **Operationalize and share.** Push network IOCs to firewall/proxy
   blocklists, file hashes to EDR, and behavior to SIEM detections.
   Share via your threat-intel process with TLP markings; consider
   reporting exfil infrastructure to the relevant abuse contacts.

## Expected outputs

- The decrypted configuration: exfil channels, servers, credentials,
  and C2 endpoints with confidence ratings.
- An IOC package (hashes, network, behavioral) in your standard
  interchange format.
- Sandbox report: process tree, network capture, persistence
  mechanisms.
- Deployed blocks and detections with validation results.

## Pitfalls

- Never detonate on a host with production network access — Agent Tesla
  exfiltrates immediately on execution.
- Extracted credentials (SMTP/FTP accounts) are often compromised
  third-party accounts — handle as sensitive and rotate/report rather
  than testing them.
- Heavy obfuscation defeats naive string extraction; budget time for
  deobfuscation or rely on dynamic extraction instead.
- Bot tokens and webhooks change per campaign — IOCs expire fast, so
  pair them with behavioral detections.
- Uploading the sample to public multi-scanners notifies the adversary
  that you have it — use private sandboxes for sensitive cases.

## References

- MITRE ATT&CK: T1041, T1048 (exfiltration); T1114 (credential access)
  — infostealer technique mappings
- CISA guidance on commodity RAT/phishing-delivered malware triage
- .NET decompiler and sandbox vendor documentation
- NIST SP 800-86: forensic techniques in incident response
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
