---
skill_id: cyber_b3_credential_stuffing_linux_server_aws_cloud_developing
name: Credential Stuffing Defense for Linux Servers in AWS Cloud (Developing Maturity)
description: "Credential Stuffing defense playbook for Linux Servers in AWS Cloud at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, authentication, linux, server, cloud, aws, maturity-developing]
version: 1.0.0
---
# Credential Stuffing Defense for Linux Servers in AWS Cloud (Developing Maturity)

## Purpose

Attackers replay username/password pairs stolen from third-party breaches against your login endpoints, betting on password reuse. It shows up as high-volume failed logons from distributed IPs, occasionally followed by a small number of successful takeovers. Applies to Linux Servers in AWS Cloud at Developing maturity.

## When to use

- Authentication logs show a spike in failed logons (often 100s per minute) from many source IPs against a single login endpoint, with a low success rate and common password patterns.
- Successful logons immediately followed by password or MFA changes, mailbox rule creation, or impossible-travel alerts for the same account within minutes.
- WAF/bot-management flags distributed requests with identical user-agent strings, headless-browser markers, or known credential-stuffing tool signatures.
- Lens: Best telemetry: auditd + centralized syslog/journald + osquery or an EDR agent. Organization CloudTrail in all regions, GuardDuty, and VPC flow logs shipped to the security account.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CloudWatch and workload logs centralized; S3 access logging on sensitive buckets.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in auth.log/secure (SSH logons), auditd logs (execve, file writes), and cron tables (/etc/crontab, /etc/cron.d/*, user crontabs) and systemd unit files in /etc/systemd/system/ and SSH authorized_keys files for all users; run `sudo grep -E 'Failed|Accepted' /var/log/auth.log | tail -40` then `sudo ausearch -m EXECVE --start recent -i | grep -E 'curl|wget|bash|sh|python|perl' | tail -30`.
3. **Analyze.** Separate spray from stuffing: stuffing reuses many passwords per username from breach corpora; confirm by checking whether the attempted passwords appear in public breach datasets. Then: For each successful post-stuffing logon, inventory session actions: read mail rules, forwarding addresses, OAuth grants, and API keys created in the 24 hours after compromise.
4. **Contain and harden.** Enforce MFA everywhere and block legacy/basic authentication; stuffing dies against phishing-resistant MFA. Asset layer: Key-only SSH (no passwords), fail2ban or equivalent, unattended security updates enabled. Environment layer: SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Blocking single IPs is whack-a-mole against botnets; block on behavior (velocity, fingerprint) rather than address.
- Forcing a fleet-wide password reset without confirming which accounts were actually taken over burns goodwill and teaches users to pick weaker passwords.

## References

- MITRE ATT&CK: T1110.004 (Credential Access: Brute Force: Credential Stuffing)
- Vendor logging and hardening baselines for Linux Servers; SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
