---
skill_id: cyber_implementing_deception_based_detection_with_canarytoken
name: Deception-Based Detection with Canarytokens
description: Deploy Canarytokens (files, credentials, URLs) as a lightweight deception fabric for breach detection.
risk: low
permissions: []
requires_confirmation: false
tags: [deception, detection]
version: 1.0.0
---
## Purpose
Canarytokens are the simplest effective deception: tripwire tokens embedded in files, credentials,
URLs, QR codes, and cloud keys that alert the moment anyone interacts with them. Legitimate users
never touch them; attackers (and malicious insiders) can't resist. This playbook deploys the
open-source Canarytokens platform (Thinkst) or equivalents across the estate as a low-cost,
high-signal detection layer.

## When to use
- Adding breach detection that works even when attackers evade EDR and logging.
- Detecting insider snooping and data-staging behaviors.
- After incidents where dwell time was long — tokens shorten it dramatically.
- Protecting file shares, code repos, cloud consoles, and physical spaces cheaply.
- As the entry-level deception program before full honeypot infrastructure.

## Prerequisites
- A token platform: self-hosted Canarytokens (Docker) or Thinkst's hosted service, plus a
  notification channel (email, webhook to SIEM).
- Placement inventory: file shares, wikis, repos, cloud accounts, workstations, and physical
  locations.
- A response runbook: token fires are high-priority — the SOC must know what to do.
- DNS control if using DNS-based tokens (a subdomain for token callbacks).
- Legal/HR coordination: tokens can implicate insiders — ensure monitoring notices cover this.

## Procedure
1. **Deploy the token infrastructure.** Self-host the Canarytokens Docker image on hardened
   infrastructure with TLS, or subscribe to the hosted service. Configure alert destinations: a
   monitored SOC mailbox plus webhook to the SIEM/SOAR for automated enrichment and paging.
2. **Start with the highest-value token types.** AWS API key tokens (detect cloud credential
   theft/use), DNS tokens (detect internal reconnaissance and data-staging), Windows folder tokens,
   and PDF/DOCX document tokens (detect file-share snooping). Each type catches a distinct attacker
   behavior — deploy all four early.
3. **Place tokens where attackers and snoopers look.** File servers: enticing filenames in shared
   folders ("Q3-bonuses.xlsx", "vpn-credentials.pdf"). Wikis/docs: fake connection strings and API
   keys. Code repos: fake keys in config examples. Workstations: tokens in Documents folders of
   high-value users. Cloud: fake access keys in old automation scripts.
4. **Tune for zero false positives.** Brief IT on token locations (not exact tokens), exclude token
   paths from scanners and backup-indexing tools, and use token types that require deliberate
   interaction. Investigate every accidental trigger and adjust placement — the goal is that any
   fire is meaningful.
5. **Write the fire-response runbook.** On alert: capture source IP/user/time, isolate the source
   host if internal, determine the token's discovery path (which reveals attacker movement), hunt
   for related activity in EDR/SIEM, and rotate adjacent real credentials. Treat fires as
   likely-intrusion until proven otherwise.
6. **Expand token variety over time.** Add: QR code tokens (physical spaces — server rooms,
   executive offices), SQL Server tokens (database snooping), Kubernetes config tokens,
   Slack/Discord webhook tokens, and custom exe/cloned-site tokens for targeted scenarios. Variety
   covers more attacker behaviors.
7. **Inventory everything.** Register every token: ID, type, placement, deployment date, owner,
   rotation due. Store token secrets securely (not in the register plaintext — store retrieval
   method). Uninventoried tokens become mystery alerts that erode trust.
8. **Rotate periodically and after incidents.** Refresh token values every 6-12 months; immediately
   rotate any token type an incident may have exposed. Stale tokens that attackers have mapped lose
   their surprise value.
9. **Integrate fires into metrics.** Report token fires as intrusion attempts; track time-to-deploy
   for new token types and coverage (tokens per critical system). A token fire with fast containment
   is a program success story — publicize it internally.
10. **Review quarterly.** Assess: accidental-trigger rate (tune if rising), coverage of new
    systems/locations, token-type effectiveness (which types actually fire), and platform health
    (callback infrastructure up, alerts delivering). Deception needs gardening.

## Expected outputs
- Deployed token infrastructure with SIEM-integrated alerting.
- Tokens placed across file shares, docs, repos, workstations, cloud, and physical spaces, fully
  inventoried.
- A fire-response runbook treating alerts as likely intrusions.
- Tuning records showing near-zero false positives; rotation schedule.
- Quarterly reviews and intrusion-attempt metrics.

## Pitfalls
- Tokens that grant real access: inert or alert-and-deny only. A working credential labeled "canary"
  is a backdoor.
- Alerts to unmonitored destinations: token value is speed — fires must page the SOC with context.
- Scanner-induced noise: coordinate exclusions or analysts learn to ignore fires, destroying the
  program's value.
- No inventory: mystery fires waste investigations and breed distrust in the alerts.
- Over-sharing token details: broad knowledge of placements kills insider-detection value.
  Need-to-know.

## References
- Thinkst Canary / Canarytokens documentation (self-hosting, token types, alerting)
- NIST SP 800-53 SC-36, SI-4 (deception and monitoring)
- MITRE ATT&CK T1083, T1552, T1078 (discovery/credential behaviors tokens catch)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
