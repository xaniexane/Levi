---
skill_id: cyber_performing_active_directory_forest_trust_attack
name: Detecting Active Directory Forest Trust Abuse (Defensive)
description: Detect, investigate, and harden against abuse of AD forest and domain trusts.
risk: low
permissions: []
requires_confirmation: false
tags: [active-directory, trust-abuse, detection]
version: 1.0.0
---

## Purpose
Inter-forest and inter-domain trusts are a classic privilege-escalation path: compromise one domain, abuse the trust to reach another. This is a defensive playbook for detecting trust abuse, assessing your trust exposure, and hardening trust configurations. It does not teach offensive exploitation.

## When to use
- Your environment has forest trusts, external trusts, or shortcut trusts.
- Hunting for cross-domain movement during an incident.
- Assessing whether trusts are necessary and properly secured.

## Prerequisites
- Inventory of all trusts: direction, transitivity, type, and business justification.
- Domain controller security logs and Kerberos logging from all trusting/trusted domains.
- Authority to modify trust configurations with the owning teams.

## Procedure
1. **Inventory and justify trusts.** Document every trust relationship; eliminate trusts with no current business need — the safest trust is a removed one.
2. **Harden trust configuration.** Enable SID filtering (quarantine) on external trusts, use selective authentication where full trust is not required, and document why each trust is transitive or bidirectional.
3. **Monitor cross-domain authentication.** Alert on: TGT requests across trusts from unexpected principals, SID-history presence in cross-trust tickets, and authentication from low-trust to high-trust domains.
4. **Hunt for abuse patterns.** Look for privileged access in domain B originating from compromised accounts in domain A, anomalous inter-domain ticket lifetimes, and DC-to-DC traffic inconsistent with replication.
5. **Validate with authorized testing.** During sanctioned AD assessments, verify that trust hardening (selective auth, SID filtering) actually blocks the paths the configuration claims to block.
6. **Respond to confirmed abuse.** Treat as full compromise of the trusting domain: scope both sides, sever or quarantine the trust during investigation if business-impact acceptable, and reset trust passwords.
7. **Review periodically.** Re-validate trust necessity and configuration annually; trusts accumulate silently through mergers and legacy projects.

8. **Log trust authentication centrally.** Forward Kerberos and trust-related events from all domains in the trust to one SIEM view; split visibility is how cross-domain attacks hide.
9. **Include trusts in merger planning.** Every acquisition or divestiture review must inventory and justify trusts; this is when the riskiest ones are created.

## Expected outputs
- Trust inventory with justification, direction, and hardening state.
- SIEM detections for cross-trust abuse patterns.
- Periodic trust review records with decommissioned trusts documented.
- Example: an external trust with SID filtering disabled is found during review; enabling quarantine and selective authentication closes a path that would have let a compromised partner domain reach internal resources.

## Pitfalls
- Assuming a forest trust is "internal and safe": it is a security boundary decision, not a formality.
- Disabling SID filtering for application compatibility without documenting the accepted risk.
- Investigating only one side of a compromised trust relationship.

- Treating trust passwords as set-and-forget; rotate them on schedule like any other credential, and alert on unexpected changes.
- Assuming selective authentication is configured correctly without testing; verify with an authorized assessment, not with the checkbox.

## References
- Microsoft Learn: forest trust and SID filtering guidance (learn.microsoft.com).
- MITRE ATT&CK T1484 (Domain or Tenant Policy Modification) and trust-related techniques.
- NIST SP 800-47, Security Guide for Interconnecting Information Technology Systems.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
