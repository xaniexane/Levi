---
skill_id: cyber_analyzing_cobalt_strike_beacon_configuration
name: Detecting Cobalt Strike Beacon Configurations
description: Detect and dissect Cobalt Strike beacons: config extraction and network signatures.
risk: low
permissions: []
requires_confirmation: false
tags: [network, threat-intel]
version: 1.0.0
---
# Detecting Cobalt Strike Beacon Configurations

## Purpose

Detect Cobalt Strike beacons in your environment by extracting and analyzing
beacon configurations from captured samples or memory — turning a suspicious
binary into network IOCs, watermark context, and high-confidence detection
logic. Defensive use only: finding and characterizing beacons, never
deploying them.

## When to use

- EDR/AV flags a suspected beacon loader, stager, or injected process.
- Incident response needs C2 infrastructure IOCs from a captured payload.
- Threat hunting: searching the fleet for beacon-indicative behaviors and
  configurations.
- Intel enrichment: extracting a beacon's configured C2, user-agent, sleep,
  and watermark for blocking and sharing.
- Validating that your controls detect current beacon variants, not just
  last year's samples.

See also: analyzing-cobaltstrike-malleable-c2-profiles.md

## Prerequisites

- Written authorization from the asset/data owner to analyze the sample and
  handle any embedded C2 infrastructure data.
- Chain-of-custody notes: sample hash, source host, collection method and
  time, and memory-dump provenance where applicable.
- An isolated analysis VM (no production credentials, controlled/sinkholed
  networking) for any detonation; static extraction is preferred and usually
  sufficient.
- Config-extraction tooling (a beacon-config parser you trust and have
  validated against known samples) plus standard analysis tools (strings,
  disassembler, YARA).

## Procedure

1. **Triage the suspect binary.** Hash it, check against intel/VirusTotal from the analysis VM, and note where it was found: path, parent process, persistence mechanism, and signing status. Beacon loaders often hide as legitimate-named DLLs/EXEs in unusual paths, as injected threads in `rundll32.exe`/`dllhost.exe`, or as memory-only payloads with no on-disk artifact at all.
2. **Look for beacon-indicative behaviors first.** Before extraction: check EDR telemetry for named-pipe patterns beacons use for SMB peer-to-peer communication, memory regions with beacon-characteristic allocation patterns, process-injection events into the observed hosts, and network connections with beacon-like timing (regular callbacks with jitter). Behavior corroborates whatever the config says — and catches beacons whose configs your parser can't read.
3. **Extract the beacon configuration.** Run a validated beacon-config parser against the sample or a memory dump of the injected process. A typical extracted config includes: C2 server(s)/URIs, HTTP method and headers, user-agent string, sleep time and jitter, DNS/HTTP/SMB comms mode, spawn-to process, watermark/license ID, and kill date. Record every field — each is detection material, and the comms-mode field tells you which network telemetry to check.
4. **Validate the extraction.** Sanity-check fields against the binary: confirm the C2 hostname actually appears in strings or decoded config blobs, and that sleep/jitter values are plausible. Parsers misfire on packed, customized, or updated loaders; a config that doesn't match the binary is worse than no config because it sends hunters after phantom infrastructure.
5. **Assess the watermark.** The watermark (license ID) indicates whether this is a licensed, cracked, or trial copy. Cracked-copy watermarks are widely published in threat intel — matching one supports the assessment that this is illicit infrastructure, and the watermark itself becomes a shareable IOC. Never treat a watermark as operator attribution: cracked copies share watermarks across unrelated actors.
6. **Pivot to infrastructure.** Resolve the C2 domains/IPs: check passive DNS, certificate data, WHOIS, and hosting patterns. Look for additional beacons, stagers, or redirectors on the same infrastructure. Distinguish dedicated attacker infrastructure from compromised legitimate hosts — your block strategy differs. Treat infrastructure as volatile: prioritize blocking and detection over long-term tracking of a single IP.
7. **Determine campaign scope.** Search EDR telemetry fleet-wide for the extracted indicators: the C2 domains, the user-agent string, the named-pipe pattern, the spawn-to anomalies, and the file hashes. Establish patient zero and the full host set *before* remediating — partial remediation of a beacon deployment just teaches the operator which hosts you found.
8. **Write high-confidence detections.** Beacon configs yield excellent detection content: IDS signatures on the URI patterns and headers, DNS/proxy blocks on C2 domains, EDR rules on the named-pipe and spawn-to behaviors, JA3/JA4 rules if the TLS stack is distinctive, and YARA rules on the config blob for memory and file scanning. Include the watermark in intel sharing with context.
9. **Remediate as an incident.** Isolate affected hosts, capture memory and disk forensics, reset credentials for accounts active on compromised hosts (assume credential exposure on any beaconed host), and hunt for follow-on tooling — beacons are typically a foothold, not the objective. Check for lateral movement to adjacent hosts before declaring scope.
10. **Harden against re-entry.**
    Determine how the beacon arrived (phishing, exposed service, valid
    account, supply chain) and close that vector with an owner and a date.
    Consider application allowlisting on common beacon staging paths, egress
    filtering improvements, and phishing-resistant MFA if credential
    phishing was the entry point.

## Key tools & commands

- Beacon config parsers (community tools parsing the config block from
  beacon binaries/memory) — validate output against strings/disassembly
  before trusting; keep the parser updated as beacon versions change.
- `strings`, Ghidra/IDA — manual verification of extracted C2 endpoints
  and settings.
- EDR telemetry — fleet-wide hunting on pipes, parent/child anomalies,
  injection events, and network callbacks.
- Passive DNS / WHOIS / certificate data — infrastructure pivoting and
  redirector identification.
- YARA — memory and file scanning rules built from the config blob and
  loader characteristics.
- IDS (Suricata/Snort) — network signatures from URIs, headers, and
  user-agents.

## Expected outputs

- Extracted beacon config: C2, URIs, user-agent, sleep/jitter, comms mode,
  spawn-to, watermark, kill date — validated against the binary.
- Campaign scope: full affected-host list with patient zero, timeline, and
  entry vector.
- Detection package: IDS signatures, DNS/proxy blocks, EDR rules, YARA
  rules — each tested where possible.
- Incident remediation log, credential-reset records, and vector-closure
  actions with owners.

## Pitfalls

- Modified/custom loaders break parsers silently — always cross-check with
  strings and behavior before publishing IOCs.
- Blocking a single C2 IP while the config lists three domains and a
  fallback channel gives false confidence. Extract *all* comms paths from
  the config, including SMB peer-to-peer and DNS.
- Watermark alone doesn't identify the operator — cracked copies share
  watermarks across unrelated actors. Use it as an IOC and context, not
  attribution.
- Memory-only beacons (fileless) leave no on-disk sample; if you only image
  disks, you'll conclude "nothing found." Capture memory from suspect hosts
  as a matter of routine.
- Kill dates in configs are sometimes set far in the future or to zero —
  don't plan your response timeline around them.

## References

- MITRE ATT&CK: S0154 (Cobalt Strike software), T1071.001 (Web Protocols
  C2), T1090 (Proxy), T1055 (Process Injection), T1573 (Encrypted Channel)
- Vendor threat reports on beacon infrastructure and watermark tracking
  (cite per claim)
- YARA documentation (rule construction for memory/file scanning)
- EDR vendor docs on named-pipe and injection telemetry

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
