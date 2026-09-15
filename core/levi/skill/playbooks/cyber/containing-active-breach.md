---
skill_id: cyber_containing_active_breach
name: Containing an Active Breach
description: Execute rapid containment of an in-progress intrusion with a disciplined isolate-eradicate-verify sequence.
risk: low
permissions: []
requires_confirmation: false
tags: [incident-response, containment, soc]
version: 1.0.0
---
## Purpose

Stop the bleeding first: a repeatable containment sequence for an active intrusion — scope, isolate, preserve evidence, and cut attacker access — executed in the right order so containment doesn't destroy the evidence or tip off the adversary prematurely. Defensive incident response, not retaliation.

## When to use

- An intrusion is confirmed or strongly suspected: C2 beacons, lateral movement, ransomware encryption in progress.
- The SOC needs a containment runbook during the first hour of a major incident.
- Tabletop exercises validating the IR team's containment muscle memory.
- Post-incident reviews where containment sequencing needs to be documented.

## Prerequisites

- An invoked incident: incident commander assigned, war-room channel open, and legal/communications looped in per the IR plan.
- Pre-authorized containment actions: who may isolate hosts, disable accounts, and block at the firewall without waiting for a committee (this is decided in peacetime, not during the breach).
- Evidence-preservation capability: memory/disk capture tooling and a forensically sound storage location.
- Contact lists: EDR/network admins on call, identity-team on call, and executive escalation path.

## Procedure

1. **Scope before you swing.** In the first 30 minutes, answer: which hosts show attacker activity, which accounts are compromised, and what is the earliest evidence timestamp. Pull EDR timelines, firewall denies, and authentication logs. Containment without scope either misses hosts or isolates half the company.
2. **Preserve volatile evidence on priority hosts.** Before isolating, capture memory from the 2–5 most important hosts if the tooling is in place and it won't take longer than minutes — rebooted or isolated hosts lose running processes, injected code, and encryption keys. Triage decision: evidence value versus speed; when ransomware is actively encrypting, speed wins.
3. **Isolate affected endpoints at the network layer.** Use EDR network containment (host can talk to the console, nothing else) rather than pulling cables — it preserves remote forensic access and is reversible. Prioritize: hosts with active C2, hosts encrypting files, then hosts with confirmed lateral-movement artifacts.
4. **Kill attacker access paths.** Disable compromised user and service accounts, revoke active sessions and tokens (IdP session revocation, not just password reset — reset alone doesn't kill existing tokens), rotate credentials the attacker touched (especially service accounts and local admin passwords via LAPS rotation), and block C2 domains/IPs at DNS and firewall.
5. **Contain at the identity layer.** Force re-authentication for privileged roles, review and revoke suspicious OAuth/app consent grants and API keys, and check for attacker-created persistence: new accounts, new MFA methods, mailbox forwarding rules, and scheduled tasks. Identity persistence survives endpoint rebuilds — this step is where re-infection usually hides.
6. **Segment to stop lateral movement.** If the attacker is moving between subnets, implement emergency ACLs at choke points (block SMB/RDP/WinRM between user and server segments except from jump hosts). Temporary and documented; record every emergency rule for later removal.
7. **Verify containment with active hunting.** After actions are taken, hunt for 48–72 hours: fresh EDR alerts on isolated hosts, new authentication anomalies, DNS queries to blocked domains (queries after a block mean something is still trying), and any re-appearance of known IOCs. Silence across all of these is your containment signal — not the absence of alerts on a single console.
8. **Transition to eradication deliberately.** Only after verified containment: rebuild compromised hosts from known-good media (not "cleaned"), reset the KRBTGT account twice in AD environments to invalidate golden tickets, and rotate all credentials in the blast radius. Document every action with timestamps for the post-incident report and any legal proceedings.

## Expected outputs

- A scoped incident with isolated hosts, disabled accounts, revoked sessions, and blocked C2.
- Preserved memory/disk evidence with chain of custody from priority hosts.
- 48–72 hours of verified hunting silence before eradication begins.
- A timestamped action log feeding the post-incident report.

## Pitfalls

- Isolating everything at once without scoping — you lose the trail and may miss the hosts that matter.
- Password resets without session/token revocation — the attacker's existing sessions survive the reset.
- Rebuilding hosts before verifying containment — re-infection from a still-active persistence mechanism.
- Forgetting identity-layer persistence (consent grants, MFA methods, forwarding rules) — the breach "comes back."
- Containment actions with no timestamps or owner — the post-incident review can't reconstruct what happened.

## References

- NIST SP 800-61 Rev. 2 (Computer Security Incident Handling Guide) — containment phase
- CISA incident response guidance and the CISA IR checklist
- MITRE ATT&CK — technique-to-containment mapping for prioritization
- SANS Incident Handler's Handbook — six-step IR process
