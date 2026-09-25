---
skill_id: cyber_analyzing_azure_activity_logs_for_threats
name: Analyzing Azure Activity Logs for Threats
description: Hunt threats in Azure Activity logs: control-plane abuse, policy changes, and anomalous principals.
risk: low
permissions: []
requires_confirmation: false
tags: [cloud, siem]
version: 1.0.0
---
# Analyzing Azure Activity Logs for Threats

## Purpose

Detect malicious and anomalous activity in Azure Activity Logs — the
control-plane record of subscription-level operations — covering privilege
escalation, persistence, resource abuse, and logging tampering in Azure.
This is the control-plane companion to data-plane analysis: it answers "who
changed what in the cloud," not "who read which blob."

## When to use

- Investigating a suspected Azure tenant/subscription compromise.
- Hunting for persistence mechanisms (new service principals, role
  assignments, automation accounts, Run Command abuse).
- Reviewing the blast radius of a leaked credential or phished
  administrator account.
- Building baseline detections for cloud control-plane threats.
- Post-incident: verifying the attacker didn't leave backdoors in
  automation or policy.

## Prerequisites

- Written authorization from the cloud/subscription owner to query Activity
  Logs and related audit data.
- Chain-of-custody notes: record export time ranges, KQL queries used, and
  hashes of exported result sets if they become evidence.
- Reader (or Security Reader) access on the target subscriptions plus
  access to the Log Analytics workspace receiving the logs.
- Knowledge of the environment's normal automation: which service
  principals and runbooks routinely perform write operations, and which
  deployment pipelines exist.
- Retention verified: confirm the workspace retains logs covering the full
  suspected compromise window before you start.

## Procedure

1. **Confirm log coverage.** Activity Logs must flow to a Log Analytics workspace with adequate retention. Verify:
   ```kusto
   AzureActivity
   | summarize min(TimeGenerated), max(TimeGenerated), count()
     by SubscriptionId
   ```
   Gaps here are a finding — you cannot hunt what you did not retain. Also confirm diagnostic settings exist on the subscriptions themselves, not just resource groups.
2. **Baseline the control plane.** Identify normal high-privilege actors: which service principals create resources, which humans hold Owner/User Access Administrator roles, what deployment pipelines look like (caller identities, operation patterns, timing). Document them; every hunt below excludes or scrutinizes against this list. Undocumented automation is your biggest false-positive source.
3. **Hunt privilege escalation.** Query for role-assignment changes, especially grants of Owner, Contributor, or User Access Administrator:
   ```kusto
   AzureActivity
   | where OperationNameValue endswith "roleAssignments/write"
   | project TimeGenerated, Caller, CallerIpAddress, Properties_d
   ```
   Flag grants by unusual callers, grants to newly created principals, grants at odd hours, and grants scoped at subscription or management-group level. Cross-check the grantor's own authority — escalation often starts with a compromised mid-privilege account granting upward.
4. **Hunt persistence via service principals and apps.** Look for new application/service-principal registrations and credential additions:
   ```kusto
   AzureActivity
   | where OperationNameValue has "applications"
      or OperationNameValue has "servicePrincipals"
   | where ActivitySubstatusValue == "Created"
      or OperationNameValue endswith "/write"
   ```
   Correlate with Microsoft Entra audit logs for `Add service principal credentials` — a new secret on an existing app is the quieter persistence path and won't show as a "new" principal.
5. **Hunt resource abuse.** Watch for VM/VMSS creation in unusual regions or SKUs (crypto-mining pattern: large GPU SKUs in regions you never use), new storage accounts with public access, new container registries, and firewall/NSG rule changes opening management ports (22/3389/5985-5986). Pair with cost-anomaly alerts from Cost Management — miners show up on the bill fast.
6. **Review policy and diagnostic tampering.** Attackers disable logging to hide. Alert on operations that stop diagnostic settings, delete or purge Log Analytics workspaces, or modify Azure Policy assignments and exemptions:
   ```kusto
   AzureActivity
   | where OperationNameValue has "diagnosticSettings"
      or OperationNameValue has "policies"
   | where ActivityStatusValue == "Succeeded"
   ```
   Treat any success here by a non-change-control identity as critical — this is the attacker blinding you.
7. **Investigate Key Vault access-policy changes.** `vaults/write` operations that add access policies or change network ACLs precede secret theft. List which identities gained `get`/`list` on secrets and keys, and whether those identities ever used them legitimately. A new access policy followed by no legitimate use is a theft setup.
8. **Check automation-account and Run Command abuse.** Hunt for new Automation Accounts, runbook creation/modification, and `virtualMachines/runCommand` operations — Run Command is effectively remote code execution on the VM and a favorite post-compromise tool. Any Run Command outside your patching automation deserves investigation.
9. **Reconstruct the incident timeline.** For a confirmed compromise: order all write operations by the suspect caller, identify the first anomalous action, enumerate created/modified resources and role grants, and scope which data-plane assets (VMs, storage, databases, Key Vaults) those grants could reach. This scoping drives the data-impact assessment.
10. **Remediate in the right order.**
    Revoke sessions and rotate credentials of compromised identities first,
    then remove rogue role assignments and service principals, then delete
    attacker resources — reversing the order lets the attacker re-persist
    during cleanup.
    Finally, re-enable any disabled logging and verify it flows.
11. **Operationalize.**
    Convert validated hunts into scheduled KQL alert rules with the baseline
    exclusions from step 2.
    Add Activity Log coverage checks to your cloud-security posture reviews,
    and document the runbook so the next analyst doesn't reinvent the KQL.

## Key tools & commands

- Azure Log Analytics + KQL over the `AzureActivity` table — the primary
  hunt surface; learn `Properties_d` parsing for operation details.
- Microsoft Entra audit & sign-in logs — correlate control-plane actions
  with authentication anomalies (impossible travel, new device,
  leaked-credential detections, MFA anomalies).
- Microsoft Defender for Cloud — secure-score and alert correlation as a
  second opinion, not a replacement for log review.
- Azure Resource Graph (`az graph query`) — point-in-time inventory to diff
  "what exists now" against "what the logs say was created."
- Azure Cost Management alerts — crypto-mining and resource-abuse early
  warning.

## Expected outputs

- Coverage verification: retention, latency, and any subscription gaps
  documented.
- Baseline document: normal automation identities, deployment pipelines,
  privileged humans.
- Hunt findings: suspicious role grants, new principals/credentials,
  resource abuse, logging-tamper attempts, Run Command abuse — each with
  timeline and actor.
- Incident timeline and remediation log for confirmed compromises, executed
  in dependency-safe order.
- Scheduled KQL alert rules with baselined exclusions and a documented
  runbook.

## Pitfalls

- Activity Logs record the *control plane*, not data-plane reads —
  downloading a blob doesn't appear here. Pair with Storage diagnostic logs
  and Defender data-plane alerts for data-theft questions.
- `Caller` can be a service principal running legitimate automation;
  blocking on name alone causes outages. Baseline first, alert on deviation.
- Multi-geo tenants: `TimeGenerated` is UTC — convert carefully when
  correlating with local-time evidence like badge logs or HR records.
- Retention defaults are short. If the compromise is older than your
  retention, say so explicitly instead of declaring "no evidence found."
- Management-group-scoped grants are easy to miss when filtering by
  subscription — always include management-group scope in
  privilege-escalation hunts.

## References

- Microsoft Docs: "Azure Activity log" (schema, categories, retention)
- Microsoft Docs: Kusto Query Language (KQL) reference
- Microsoft Docs: "Microsoft Entra audit logs" (service-principal
  credential events)
- MITRE ATT&CK: T1078 (Valid Accounts), T1136 (Create Account), T1098
  (Account Manipulation), T1526 (Cloud Service Discovery), T1562.008
  (Disable Cloud Logs)

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
