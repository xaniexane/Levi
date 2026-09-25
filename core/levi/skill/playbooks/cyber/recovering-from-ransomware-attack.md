---
skill_id: cyber_recovering_from_ransomware_attack
name: Recovering from a Ransomware Attack
description: Structured ransomware recovery: contain, identify, evaluate decryption options, and rebuild from clean backups.
risk: moderate
permissions: []
requires_confirmation: true
tags: [incident-response, ransomware, recovery]
version: 1.0.0
---
## Purpose
Ransomware recovery fails when teams rush to restore without understanding the scope. This playbook provides the order of operations: contain the spread, preserve evidence, identify the variant, check for free decryptors, restore from known-clean backups, and rebuild compromised systems rather than trusting them. It assumes no ransom payment; the decision path favors restoration and rebuilding.

## When to use
- Active or discovered ransomware encryption event.
- Tabletop or live-fire exercise of the ransomware response plan.
- Post-incident review to validate that recovery procedures actually work.
- Evaluating backup and rebuild readiness before an incident occurs.

## Prerequisites
- Invoked incident response plan with defined roles and executive communication channel.
- Network segmentation capability to isolate affected hosts quickly.
- Backup inventory with last-known-good dates and offline/air-gapped copies.
- Contacts: legal, cyber insurance, and law enforcement reporting channels.

## Procedure
1. Isolate affected systems from the network immediately; disable remote access pathways the ransomware may use to spread.
2. Preserve evidence: capture memory and disk images of patient-zero and key servers before wiping anything.
3. Identify the variant from ransom notes, encrypted file extensions, and submitted samples (use reputable identification services).
4. Check for free decryptors from law-enforcement-backed initiatives before considering any other path.
5. Determine scope: which systems, backups, and credentials are compromised; assume domain compromise until proven otherwise.
6. Rebuild from known-clean media and restore data from backups verified predating the intrusion, not just the encryption.
7. Reset all credentials (especially privileged and service accounts) in the rebuilt environment.
8. Bring systems back in phases with enhanced monitoring; watch for re-encryption indicating missed persistence.
9. Conduct a lessons-learned review and update backups, segmentation, and detection based on the entry vector.
10. Notify cyber insurance and legal counsel before any ransom-related decision; document the decision process.
11. Verify backup restoration in an isolated network before reconnecting to production.
12. Conduct a compromise assessment of identity systems; assume credential theft until ruled out.

## Expected outputs
- Scoping report: affected systems, variant identification, evidence inventory.
- Restoration log: what was rebuilt, from which backup, and verification results.
- Lessons-learned report with control improvements and updated playbooks.
- Decision log for ransom stance with legal and insurance input.
- Isolated restore verification report before production reconnection.
- Identity compromise assessment results.

## Pitfalls
- Restoring onto still-compromised infrastructure leads to re-encryption; rebuild first.
- Backups connected to the network get encrypted too; offline copies are the real recovery path.
- Paying the ransom funds crime, may be sanctionable, and often fails to yield working decryptors.
- Wiping before evidence capture destroys the ability to understand the intrusion and meet reporting duties.
- Decryptors may only partially work on large files; test on copies and verify integrity.
- Threat actors often exfiltrate before encrypting; investigate data theft alongside recovery.
- Rushing restoration without removing persistence leads to re-encryption within hours.

## References
- CISA StopRansomware Guide (cisa.gov/stopransomware).
- No More Ransom project (decryptor repository).
- NIST SP 800-61 Rev. 2, Computer Security Incident Handling Guide.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
