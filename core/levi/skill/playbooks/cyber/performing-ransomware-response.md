---
skill_id: cyber_performing_ransomware_response
name: Ransomware Response
description: Respond to active ransomware incidents with containment, eradication, and recovery steps that protect evidence and operations.
risk: low
permissions: []
requires_confirmation: false
tags: [ransomware, incident-response, recovery]
version: 1.0.0
---

## Purpose
- Give responders a clear action sequence for the chaotic first hours of a ransomware incident.
- Contain the spread quickly while preserving evidence for investigation and potential legal action.
- Recover operations safely without reintroducing the infection or paying unnecessarily.

## When to use
- When ransomware is confirmed or strongly suspected on any organizational system.
- When a ransomware group claims to have exfiltrated data and threatens publication.
- During preparedness work, to validate that the playbook, backups, and contacts are ready.

## Prerequisites
- An incident response plan with defined roles, plus current contact lists for IT, legal, executives, and insurers.
- Network segmentation capability and the authority to isolate hosts quickly.
- Backup and recovery procedures that have been tested, including offline or immutable copies.
- Relationships with law enforcement and, if retained, an external IR firm.

## Procedure
1. Declare the incident and activate the response team; assign an incident commander immediately.
2. Isolate affected hosts from the network but do not power them off, preserving volatile evidence and encryption keys in memory.
3. Identify the ransomware variant from ransom notes, file extensions, and threat intel to understand its behavior.
4. Determine scope: which systems are encrypted, which show attacker activity, and whether data was exfiltrated.
5. Preserve evidence: capture memory from key hosts, image patient-zero systems, and secure logs centrally.
6. Block attacker infrastructure at the perimeter: C2 domains, IPs, and malicious email senders.
7. Engage legal, executive leadership, and the cyber insurer before any ransom discussion; document every decision.
8. Check for available decryptors from trusted sources before considering any payment; payment is a last resort with legal review.
9. Eradicate: remove persistence, close the initial access vector, and reset credentials across the affected environment.
10. Recover from clean backups, verifying backup integrity and scanning restored systems before reconnecting them.
11. Monitor intensely post-recovery for re-infection attempts, since ransomware groups often return.
12. Conduct a lessons-learned review and update defenses, backups, and the response plan.

## Expected outputs
- A contained incident with documented scope and preserved evidence.
- Recovered operations from verified clean backups.
- A lessons-learned report with prioritized defensive improvements.
- A communications log documenting every external notification and its timing.
- An updated asset inventory reflecting systems rebuilt or replaced during recovery.

## Pitfalls
- Powering off encrypted hosts immediately, destroying memory evidence and any chance of key recovery.
- Paying the ransom without legal and executive review; payment does not guarantee recovery and may be illegal.
- Recovering from backups that were also compromised; verify backup integrity and isolation first.
- Declaring victory too early; ransomware affiliates frequently re-target the same victim.
- Forgetting to rotate credentials for service accounts that lived on compromised hosts.

## References
- CISA's Ransomware Readiness Assessment tool
- CISA ransomware guide and stopransomware.gov resources
- NIST SP 800-61 Incident Handling Guide, https://csrc.nist.gov/publications/detail/sp/800-61/rev-2/final
- NIST SP 800-34 Contingency Planning Guide for recovery planning
- FBI Internet Crime Complaint Center guidance on reporting ransomware
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
