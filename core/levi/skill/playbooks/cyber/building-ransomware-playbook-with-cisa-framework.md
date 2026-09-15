---
skill_id: cyber_building_ransomware_playbook_with_cisa_framework
name: Building a Ransomware Playbook with the CISA Framework
description: Practitioner guide to building a ransomware response playbook aligned with CISA guidance, covering preparation through recovery.
risk: info
permissions: []
requires_confirmation: false
tags: [incident-response, ransomware]
version: 1.0.0
---
## Purpose
Ransomware demands decisions in hours: isolate or observe, pay or rebuild, notify whom. This playbook uses CISA's ransomware guidance as its backbone to build a scenario-specific plan covering preparation, detection, containment, eradication, recovery, and the hard policy questions (including the organizational stance on ransom payment) decided before an incident, not during one.

## When to use
- Creating or overhauling the organization's ransomware response plan.
- Aligning existing procedures with federal guidance and best practices.
- Preparing for cyber-insurance or regulatory scrutiny of ransomware readiness.
- Running ransomware-focused tabletop exercises.

## Prerequisites
- Executive decision on ransom-payment policy, documented with legal counsel.
- Tested, offline, and immutable backups with defined recovery objectives.
- Network segmentation map and identity of critical systems for prioritized recovery.
- Contacts: retainer IR firm, insurer, FBI field office or CISA regional contact.

## Procedure
1. Establish the policy foundation. Document the ransom-payment stance, decision authority, and legal and insurance notification requirements before any incident.
2. Harden the preparation layer. Verify offline backups, MFA on remote access and admin accounts, and network segmentation that limits blast radius.
3. Define detection triggers. List the alerts that indicate ransomware: mass file renames, shadow-copy deletion, disabled EDR, ransom notes, and backup-repository access.
4. Write the containment procedure. Specify isolation methods (host, network segment, identity), the order of operations, and how to preserve evidence while stopping spread.
5. Plan eradication. Document how to identify patient zero, remove persistence, reset credentials enterprise-wide, and validate systems are clean before rebuild.
6. Build the recovery sequence. Prioritize restoration by business criticality; define criteria for bringing systems back online and monitoring for re-encryption.
7. Prepare communications. Draft ransom-note handling, internal updates, customer notifications, and law-enforcement reporting steps.
8. Exercise and update. Run the playbook in a tabletop at least annually; update it after every exercise, real incident, and major CISA guidance revision.

## Expected outputs
- Ransomware playbook with pre-decided policies, containment and recovery procedures.
- Backup and segmentation verification evidence.
- Exercise schedule and improvement tracking.

## Pitfalls
- Deciding the payment question mid-incident under time pressure leads to bad outcomes.
- Backups that were never restore-tested are not backups.
- Rebuilding into the same flat network invites immediate re-infection.
- Paying does not guarantee decryption and may violate sanctions; get counsel involved.

## References
- CISA: Stop Ransomware guide and ransomware resources
- CISA Known Exploited Vulnerabilities (KEV) catalog
- NIST SP 800-61 Rev. 3, Computer Security Incident Handling Guide
- FBI Internet Crime Complaint Center (IC3) reporting guidance
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
