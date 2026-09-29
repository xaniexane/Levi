---
skill_id: cyber_b3_business_email_compromise_windows_workstation_gcp_cloud_optimized
name: Business Email Compromise Defense for Windows Workstations in GCP Cloud (Optimized Maturity)
description: "Business Email Compromise defense playbook for Windows Workstations in GCP Cloud at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [email, fraud, windows, endpoint, cloud, gcp, maturity-optimized]
version: 1.0.0
---
# Business Email Compromise Defense for Windows Workstations in GCP Cloud (Optimized Maturity)

## Purpose

Attackers operate inside a compromised mailbox (or a lookalike domain) to redirect payments, harvest invoices, or pivot to executives. Dwell time is often weeks; the fraud, not the malware, is the payload. Applies to Windows Workstations in GCP Cloud at Optimized maturity.

## When to use

- Mailbox audit logs show inbox rules created to move or delete messages containing 'invoice', 'payment', 'wire', or executive names — the classic BEC rule footprint.
- Outbound messages to finance vendors from a slightly altered domain, or a legitimate mailbox suddenly sending payment-change requests with urgent tone.
- Logons to the mailbox from foreign IPs or anonymizing VPNs followed by long read-only sessions (the attacker learning the payment workflow before striking).
- Lens: Best telemetry: Sysmon + EDR + PowerShell script-block logging forwarded to the SIEM. Cloud Audit Logs (admin + data access) exported to a locked-down logging project.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Security Command Center findings and VPC flow logs centralized.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Security event log (4624/4625 logons, 4688 process creation, 7045 service installs) and Sysmon operational log and PowerShell operational log (4104 script blocks); run `Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4625} -MaxEvents 50 | Format-List TimeCreated, @{n='TargetUser';e={$_.Properties[5].Value}}, @{n='SourceIP';e={$_.Properties[19].Value}}` then `autorunsc64.exe -accepteula -a * -c -h -s -t | findstr /v "Microsoft Corporation"`.
3. **Analyze.** Export all inbox/transport rules for the affected mailbox and diff against a known-good baseline; BEC rules often hide with names like ';' or whitespace. Then: Trace every payment instruction the mailbox sent in the dwell window: which were acted on, which bank details changed, and whether funds are recallable.
4. **Contain and harden.** Require out-of-band (voice/video) verification for any payment detail change, no exceptions, and alert on new inbox rules fleet-wide. Asset layer: Application allowlisting (WDAC/AppLocker) and LSA Protection + Credential Guard enabled. Environment layer: Organization policies constraining public exposure, API enablement, and service-account key creation.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Focusing only on the compromised mailbox while the attacker already harvested the vendor's thread and will re-target from another account.
- Treating a lookalike-domain BEC as an IT problem alone — finance process change is the actual fix.

## References

- MITRE ATT&CK: T1566 (Initial Access: Phishing) leading to collection/fraud
- Vendor logging and hardening baselines for Windows Workstations; Organization policies constraining public exposure, API enablement, and service-account key creation.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
