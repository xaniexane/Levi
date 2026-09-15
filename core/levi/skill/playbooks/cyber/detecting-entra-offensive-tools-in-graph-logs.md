---
skill_id: cyber_detecting_entra_offensive_tools_in_graph_logs
name: Detecting Entra Offensive Tools in Graph Logs
description: Detect attacker tooling abusing Microsoft Graph with app-identity, user-agent, and API-pattern analysis.
risk: info
permissions: []
requires_confirmation: false
tags: [azure, entra, detection]
version: 1.0.0
---
## Purpose

Detect offensive security tools — and real attackers using the same techniques — operating against Entra ID via Microsoft Graph: enumeration tools, token-abuse utilities, and Graph-based persistence. The Graph API is the attacker's command line for the cloud directory; monitor it like one.

## When to use

- Hunting for Entra ID enumeration, privilege escalation, or persistence via Graph.
- Building detections for attacker tooling in cloud identity environments.
- Investigating alerts involving suspicious Graph API activity.
- Validating that Graph audit logging captures the necessary telemetry.

## Prerequisites

- Entra ID audit logs and sign-in logs (including service-principal sign-ins) in Log Analytics/SIEM.
- Baseline of legitimate Graph usage: which apps and admins call which endpoints.
- Knowledge of common offensive tooling patterns (without needing the tools themselves — detect the behavior).
- Alerting path with app-revocation and credential-reset authority.

## Procedure

1. **Baseline legitimate Graph API usage.** Record per app/service principal: endpoints called, call rates, source IPs, and user agents. Administrative tools (your IAM automation, PIM workflows) have regular patterns; attacker tooling deviates in endpoints (enumeration-heavy), user agents (tool-specific or spoofed), and sources (new IPs).
2. **Detect enumeration patterns.** Alert on: high-volume user/group/application enumeration (`/users`, `/groups`, `/applications` with `$top` paging), Conditional Access policy reads by non-admin apps, role-assignment enumeration, and directory-structure mapping. Attackers map the directory before acting — enumeration is the early warning.
3. **Detect tooling fingerprints.** Alert on: known offensive-tool user-agent strings, Graph calls from user agents inconsistent with the app's normal client, PowerShell-based Graph modules (MSAL/Graph SDK) used from unexpected hosts, and anonymous or newly registered apps making privileged calls. Fingerprint the behavior class, not just the string — attackers change user agents.
4. **Monitor for Graph-based persistence.** Alert on: new application registrations, credential additions to service principals, API permission grants (especially `Directory.ReadWrite.All`, `RoleManagement.ReadWrite.Directory`), and Conditional Access policy modifications via Graph. Each of these via an unexpected app or user is a persistence attempt.
5. **Detect token abuse via Graph.** Alert on: tokens used from geographies inconsistent with issuance, refresh-token anomalies for Graph-scoped tokens, and Graph calls with tokens issued to different apps (token replay across app boundaries). Correlate with the human identity behind the app — compromised user + new Graph tooling is the attack chain.
6. **Hunt for living-off-the-land Graph abuse.** Attackers increasingly use legitimate tools (Azure CLI, Graph Explorer, PowerShell modules) rather than custom malware. Hunt for: legitimate tools used from unusual hosts, at unusual hours, or performing unusual operations (Graph Explorer enumerating all users isn't normal). The tool is legitimate; the context is the detection.
7. **Respond with app-level containment.** On confirmation: revoke the app's credentials and tokens, remove malicious app registrations, audit everything the app accessed (Graph audit logs show the calls), and investigate the human account that created or consented to the app. Then harden: restrict who can register apps, require admin consent for privileged permissions, and review app inventory quarterly.

## Expected outputs

- Baselined Graph API usage per app with enumeration, fingerprint, and persistence detections.
- Token-abuse monitoring correlated with human-identity compromise signals.
- App-level containment runbooks and quarterly app-registration hygiene reviews.

## Pitfalls

- No Graph audit logging — the API activity is invisible; enable and centralize it first.
- User-agent-only detection — trivially spoofed; always pair with behavioral signals.
- Ignoring legitimate-tool abuse — the attacker with Azure CLI looks like your admin.
- Alerting on enumeration without baselines — your own IAM automation enumerates constantly.
- Treating the app as the whole incident — find the human account and the initial access.

## References

- Microsoft Learn — Microsoft Graph audit logging, Entra ID audit logs
- MITRE ATT&CK T1526 (Cloud Service Discovery) and T1550.001 (Application Access Token)
- Microsoft threat-hunting guidance for Entra ID attacks
- NIST SP 800-207 — service and application identity considerations
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
