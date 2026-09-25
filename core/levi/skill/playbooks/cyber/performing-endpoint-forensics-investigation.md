---
skill_id: cyber_performing_endpoint_forensics_investigation
name: Endpoint Forensics Investigation
description: Scope and investigate a compromised endpoint using forensic artifacts.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, endpoint, incident-response]
version: 1.0.0
---
# Endpoint Forensics Investigation

## Purpose

When an EDR alert or user report points at a host, analysts need a
repeatable way to scope the compromise: what ran, what persisted, what
touched the network, and whether the host can be trusted again. This
playbook walks a defensible endpoint investigation from triage to
containment decision.

## When to use

- Responding to EDR detections (malware, suspicious process chains,
  credential-access alerts).
- User-reported symptoms: unexpected pop-ups, slowness, ransom notes.
- Scoping lateral movement from a known-compromised account or host.
- Verifying whether a host is clean enough to return to service.

## Prerequisites

- Written authorization to collect forensic data from the endpoint,
  including any privacy-sensitive artifacts (browser history, files).
- Remote forensic access or the ability to ship a collector: EDR live
  response, Velociraptor, or a triage script.
- A working timeline hypothesis from the initial alert: the detection
  time, the user context, and the alerting sensor's blind spots.

## Procedure

1. Preserve first: capture a triage collection (running processes with
   command lines, network connections, scheduled tasks, services, recent
   files, prefetch, shimcache, registry Run keys) before making any
   change; snapshot the VM if virtual.
2. Isolate judiciously: apply network containment through the EDR if the
   host is beaconing or encrypting, but delay isolation if you need live
   C2 evidence — document the trade-off.
3. Reconstruct execution: walk the process tree around the alert time,
   flagging unsigned binaries, LOLBin abuse, renamed tools, and processes
   spawned from temporary or user-writable directories.
4. Check persistence: compare autoruns, scheduled tasks, services, WMI
   subscriptions, and startup folders against a known-good baseline for
   the same OS build.
5. Correlate network evidence: map established connections and DNS
   queries from the host to the alert window; pivot on remote IPs in the
   firewall and proxy logs.
6. Look for credential access: recent LSASS access events, SAM/SECURITY
   reads, NTDS.dit copies on domain controllers, and new lateral
   logons from this host in the DC logs.
7. Scope outward: list logons from this host to others (event 4624 type 3)
   and repeat the triage collection on any destination showing
   anomalous activity.
8. Decide containment: wipe-and-reimage is the default for confirmed
   compromise; document the artifacts that justify either rebuild or
   return-to-service.

## Expected outputs

- A timeline of malicious activity on the host with artifact citations.
- A scoping statement: confirmed compromised hosts, suspected hosts, and
  evidence each conclusion rests on.
- A containment decision with justification and a rebuild/return plan.
- IOCs fed to SIEM/EDR for enterprise-wide hunting.

## Pitfalls

- Touching the host before collection: every login, reboot, or AV
  quarantine changes the artifact record.
- Treating a single alert as the whole incident: always scope for
  lateral movement and persistence before closing.
- Trusting timestamps blindly: check for timestomping and clock skew
  against domain controllers.
- Returning a host to service after only removing the payload without
  verifying persistence and credential theft.

## References

- NIST SP 800-61, Computer Security Incident Handling Guide
- SANS FOR508-style endpoint triage artifact references
- MITRE ATT&CK Enterprise matrix (Persistence and Defense Evasion tactics)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
