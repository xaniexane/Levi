---
skill_id: cyber_hunting_for_dcsync_attacks
name: Hunting for DCSync Attacks
description: Detect DCSync credential theft via Directory Replication Service event auditing, ACL monitoring, and anomalous replication patterns.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, active-directory, credentials]
version: 1.0.0
---
## Purpose

DCSync lets an attacker with the right extended rights impersonate a
domain controller and pull password hashes for any account via directory
replication — no code execution on the DC required. This playbook covers
detecting DCSync through DS replication auditing, monitoring the rights
that enable it, and responding when it is observed.

## When to use

- Any Active Directory compromise investigation: DCSync is the fastest
  path to total domain credential theft.
- After alerts for unusual replication or Directory Service access
  events on domain controllers.
- Proactive AD hygiene: auditing who holds replication rights.
- Post-incident: determining whether DCSync occurred defines the
  credential-reset scope (often: everything).

## Prerequisites

- "Audit Directory Service Access" / DS Access auditing enabled on DCs
  to generate event 4662 for replication operations.
- Rights to query AD ACLs and extended rights assignments.
- Centralized DC Security logs with adequate retention.
- An inventory of legitimate DC computer accounts (the only normal
  source of replication traffic).

## Procedure

1. **Understand the primitive.** DCSync requires the
   `DS-Replication-Get-Changes` (and for some attributes,
   `-Get-Changes-All`) extended right on the domain. Detection has two
   halves: who *holds* the right (the attack surface) and who *uses* it
   (the attack).
2. **Audit the attack surface.** Enumerate all principals with
   replication rights over the domain object — beyond Domain Controllers
   and Enterprise/Domain Admins, flag service accounts, helpdesk groups,
   and any custom delegations. Each is a DCSync-capable account if
   compromised.
3. **Enable and verify DS auditing.** Confirm 4662 events for
   `DS-Replication-Get-Changes` operations are generated and forwarded.
   Without this auditing, DCSync is invisible in native logs — treat
   the gap as a finding and enable it immediately.
4. **Hunt replication anomalies.** Alert on 4662 replication-access
   events where the caller is not a domain controller computer account;
   replication requests from user or service accounts are the core
   signal. Correlate with the volume of replicated attributes — DCSync
   pulls are targeted and bursty compared to normal DC-to-DC traffic.
5. **Hunt the enabling changes.** Monitor for ACL modifications granting
   replication rights (event 5136/5137 directory-service changes, or
   4662 access events) — attackers often grant themselves the right
   just before using it. Alert on any new replication-right grant.
6. **Correlate with follow-on activity.** DCSync is usually followed by
   credential use: pass-the-hash logons, new privileged sessions, or
   Golden Ticket activity (anomalous TGT lifetimes). Build the timeline
   from first replication access through subsequent abuse.
7. **Respond as total compromise.** Confirmed DCSync means every
   domain credential must be treated as compromised: emergency
   credential-reset scope includes the KRBTGT account (twice, to kill
   golden tickets), all privileged accounts, and service accounts.
   Follow your AD disaster-recovery runbook.
8. **Close the rights gap.** Remove unnecessary replication rights,
   enforce tiering so Tier-0 rights cannot be reached from lower tiers,
   and deploy durable detections for both rights grants and
   non-DC replication access.

## Expected outputs

- An inventory of DCSync-capable principals with remediation of
  excessive rights.
- DS-auditing coverage verification per DC.
- Hunt findings: anomalous replication-access events with
  attribution.
- Incident scoping and credential-reset records (including KRBTGT).
- Durable detections for replication-right grants and non-DC DCSync.

## Pitfalls

- Without 4662 DS-access auditing, native detection is impossible —
   verify auditing before promising coverage.
- Azure AD Connect and similar sync services hold replication rights
   legitimately — baseline them to avoid false positives.
- Attackers may DCSync selectively (a few accounts) rather than the
   whole domain — volume thresholds alone will miss targeted pulls.
- Resetting KRBTGT once is insufficient — it must be reset twice with
   replication between resets to invalidate golden tickets.
- Focusing only on the DCSync event: the initial compromise that
   yielded the rights is a separate investigation track.

## References

- MITRE ATT&CK: T1003.006 (DCSync)
- Microsoft Learn: "Audit Directory Service Access" and extended-
  rights documentation
- Microsoft: guidance on KRBTGT reset procedures
- CISA: Active Directory security best-practice guidance
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
