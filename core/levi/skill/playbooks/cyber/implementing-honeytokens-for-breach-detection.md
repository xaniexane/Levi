---
skill_id: cyber_implementing_honeytokens_for_breach_detection
name: Honeytokens for Breach Detection
description: Deploy honeytokens — fake data planted in real systems — to detect breaches with near-zero false positives.
risk: low
permissions: []
requires_confirmation: false
tags: [deception, detection]
version: 1.0.0
---
## Purpose
Honeytokens are fake data that looks valuable but exists only to be stolen: bogus customer records
in databases, fake credentials in password stores, decoy documents in file shares, phony API keys in
code. No legitimate process touches them — so any access is evidence of unauthorized browsing,
insider snooping, or an attacker staging data theft. This playbook deploys honeytokens inside
production-adjacent systems as the breach-detection tripwire other controls can't provide.

## When to use
- Detecting data theft and insider snooping that bypasses perimeter and EDR controls.
- After incidents where attackers dwelled in systems accessing data undetected.
- Protecting databases, file shares, and code repositories holding sensitive data.
- Meeting detection requirements for data-centric threats (the "assume breach" complement).
- As the data-layer deception program alongside network canary tokens and honeypots.

## Prerequisites
- Target systems identified: databases, file shares, document stores, code repos, CRM/ERP with
  sensitive data.
- Monitoring capable of detecting honeytoken access: database auditing, file-access logging, DLP, or
  SIEM correlation.
- A honeytoken inventory system (register of every token, its location, and its expected-zero access
  baseline).
- Legal/HR coordination: honeytokens implicate insiders — monitoring notices and investigation
  procedures must be in place.
- Change control: tokens must survive migrations, and DBAs/admins must not "clean up" unknown
  records.

## Procedure
1. **Choose honeytoken types per system.** Databases: fake customer/patient/employee rows with
   distinctive-but-plausible values (and a canary email/phone that alerts if used). File shares:
   decoy documents ("Executive compensation 2026.xlsx", "M&A targets.docx") with embedded canary
   URLs or macros that beacon (use beaconing carefully — see pitfalls). Code/config: fake API keys
   and credentials. CRM: fake high-value accounts.
2. **Make tokens believable and identifiable.** Values must pass casual inspection (realistic
   formats, consistent with neighboring data) but be machine-identifiable as fake: a reserved email
   domain you monitor, phone numbers in unassigned ranges, names from a known-fake list. Document
   the identification scheme securely — the team investigating alerts must distinguish tokens from
   real data instantly.
3. **Instrument access monitoring.** Enable: database audit logging on honeytoken rows (or triggers
   alerting on SELECT of token IDs), file-access auditing on decoy documents, and SIEM rules for
   canary-value appearance in egress (DLP rules matching token emails/keys catch exfiltration). Test
   that each token type actually generates an alert when touched.
4. **Establish the zero-baseline.** After deployment, verify no legitimate process touches the
   tokens during a burn-in period (2-4 weeks). Any hits get investigated: legitimate system or
   misplacement? Tune placement until the baseline is truly zero — that zero is what makes every
   future alert meaningful.
5. **Write the access-response runbook.** On honeytoken alert: identify the accessor (user/service,
   source, time), determine the access path (which query, which share, which session), assess
   whether real data was accessed alongside (scope the breach), preserve evidence, and escalate per
   insider-threat or intrusion procedures. Speed matters — data theft in progress needs containment.
6. **Protect tokens operationally.** Brief DBAs and sysadmins on token tables/files (existence, not
   necessarily exact values); exclude tokens from ETL, reporting, and backup-restore validation that
   might "fix" them; ensure migrations carry tokens forward. Tokens that vanish silently create
   coverage gaps nobody notices — monitor token presence itself.
7. **Vary and refresh.** Rotate token values periodically; add new tokens when new sensitive systems
   come online; retire tokens from decommissioned systems. Attackers who learn token patterns avoid
   them — freshness preserves the surprise.
8. **Correlate with the broader program.** Honeytoken alerts join: canary-token fires (network),
   honeypot alerts, DLP exfiltration events, and UEBA anomalies in the SOC's insider/intrusion
   picture. A honeytoken access preceded by a canary-token fire is a confirmed intrusion timeline —
   build the correlation rules.
9. **Inventory rigorously.** Register: token ID, type, exact location, creation date, owner,
   monitoring method, and rotation due. Never store the full token secrets alongside the register
   insecurely — the register is sensitive (it tells an insider what to avoid). Access-controlled,
   audited.
10. **Measure and report.** Metrics: token coverage (sensitive systems with tokens), zero-baseline
    health (accidental touches), true-positive alert rate, and mean time from access to containment.
    Report honeytoken detections as prevented-or-detected data-theft attempts — the program's value
    in the starkest terms.

## Expected outputs
- Honeytokens deployed across databases, shares, repos, and CRM: realistic, monitored, inventoried.
- Access monitoring (audit triggers, SIEM/DLP rules) verified per token type with a confirmed
  zero-baseline.
- An access-response runbook (identify → scope → preserve → escalate) tied to insider-threat
  procedures.
- Operational protection (migration survival, presence monitoring) and rotation schedule.
- Correlation with canary tokens/honeypots/UEBA and data-theft-attempt metrics.

## Pitfalls
- Beaconing tokens without legal review: documents that "phone home" when opened can have privacy
  and legal implications — get counsel's sign-off on active beacons.
- Tokens in backups/ETL: fake records flowing into analytics or customer communications cause
  real-world embarrassment. Exclude tokens from downstream pipelines.
- No zero-baseline: deploying tokens that legitimate jobs touch creates noise that trains analysts
  to ignore the alerts. Burn-in and tune first.
- Inventory insecurity: the token register in a shared spreadsheet tells insiders exactly what to
  avoid. Protect it like the secrets it is.
- Stale tokens: unrotated, long-known tokens lose effectiveness. Refresh on schedule and after
  incidents.

## References
- NIST SP 800-53 SC-36, SI-4 (deception, monitoring)
- Research literature on honeytokens/honeydata for insider-threat detection
- CERT insider-threat guidance (detection via decoys)
- MITRE ATT&CK T1005, T1039, T1074 (data collection/staging behaviors honeytokens catch)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
