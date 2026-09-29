---
skill_id: cyber_core_insider_data_theft
name: Insider Data Theft Defense — Threat Core
description: "Authoritative defensive core for Insider Data Theft: full threat intel, detection, analysis, and hardening, with an adaptation matrix covering 40 asset types, 10 environments, and 5 maturity tiers."
risk: low
permissions: []
requires_confirmation: false
tags: [insider, dlp, threat-core, core]
version: 1.0.0
---
# Insider Data Theft Defense — Threat Core

## Purpose

A trusted user steals data — often before resignation. Unlike external attacks there is no malware to find; detection relies on behavioral baselines: access volume, off-hours activity, and personal-storage uploads. Handle with HR and legal from the start. This core is the single authoritative defensive
playbook for Insider Data Theft; the adaptation matrix below tailors it to
40 asset types, 10 environments, and 5 maturity tiers.

## When to use

- A user accessing far more files or records than their role baseline, especially in the 30 days before resignation or termination.
- Bulk downloads to USB, personal cloud uploads, or emailing attachments to personal addresses from a corporate account.
- Off-hours access to repositories the user never touched before, or permission changes granting themselves broader access.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to the telemetry listed for your asset type and environment in the adaptation matrix.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in the asset-appropriate telemetry from the adaptation matrix; capture the artifacts listed for your asset type before they age out.
3. **Analyze.** Build a 90-day access timeline for the user: volume, data sensitivity, destination (USB serial, cloud account, personal email) — coordinate collection with HR/legal to stay compliant. Then: Determine business justification for each anomaly with the user's manager before concluding malice; over-collection without cause creates liability.
4. **Contain and harden.** UEBA baselines with alerting on pre-resignation access spikes; disable USB mass storage or enforce encryption + logging. Apply the asset-layer and environment-layer controls from the adaptation matrix for your specific asset type and environment.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned. Re-assess maturity tier and advance one tier where feasible.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Adaptation matrix

### Asset types (40)

- **Windows Workstations:** Best telemetry: Sysmon + EDR + PowerShell script-block logging forwarded to the SIEM. | harden: Application allowlisting (WDAC/AppLocker) and LSA Protection + Credential Guard enabled.
- **Windows Servers:** Best telemetry: Security log with advanced audit policy + Sysmon + service-install monitoring. | harden: Server Core installs where possible; disable unnecessary roles and SMBv1; enforce SMB signing.
- **Linux Servers:** Best telemetry: auditd + centralized syslog/journald + osquery or an EDR agent. | harden: Key-only SSH (no passwords), fail2ban or equivalent, unattended security updates enabled.
- **Linux Workstations:** Best telemetry: auditd user-session logging + EDR agent + desktop shell histories (with user notice). | harden: Standard user accounts for daily work, full-disk encryption, and screen-lock enforcement.
- **macOS Endpoints:** Best telemetry: unified log + EDR agent + Santa/Munki logs where deployed. | harden: Gatekeeper + XProtect current, FileVault on, firewall on, and MDM-enforced configuration profiles.
- **Active Directory Domain Controllers:** Best telemetry: forwarded Security logs (4768/4769/4771/4662/4720/4732/4724/5136) + AD replication monitoring. | harden: Tier-zero isolation: DCs on dedicated hosts, no browsing/email, admin access via PAW/jump host only.
- **Microsoft Entra ID Tenants:** Best telemetry: Entra sign-in + audit logs streamed to Log Analytics/SIEM with 30+ day retention. | harden: Conditional Access: require phishing-resistant MFA, compliant devices, block legacy auth and risky sign-ins.
- **AWS Accounts:** Best telemetry: CloudTrail (org trail, all regions) + GuardDuty + VPC flow logs + Config. | harden: MFA on root + all IAM users, SCPs denying logging disablement and unapproved regions, no long-lived keys.
- **Azure Subscriptions:** Best telemetry: Activity Log + Entra sign-in logs + Defender for Cloud + NSG flow logs. | harden: Azure Policy deny-effects on public storage/exposure; PIM for subscription roles; Defender plans on.
- **GCP Projects:** Best telemetry: Cloud Audit Logs (Admin Activity + Data Access) + Security Command Center + VPC flow logs. | harden: Organization policies: no public buckets, no default SA use, OS Login on; deny unapproved APIs.
- **Kubernetes Clusters:** Best telemetry: Kubernetes audit logs + container runtime logs + admission-controller denials. | harden: Least-privilege RBAC, Pod Security Standards enforced, no privileged pods, image signing/verification.
- **Docker Hosts:** Best telemetry: Docker daemon logs + host auditd + container stdout/stderr shipped centrally. | harden: No --privileged, no host socket mounts except for explicit agents, user namespaces enabled, read-only root filesystems.
- **VMware ESXi Hosts:** Best telemetry: vCenter tasks/events + ESXi syslog + lockdown-mode audit. | harden: Lockdown mode on, isolated management network, unique per-host root passwords, MFA on vCenter.
- **Hyper-V Hosts:** Best telemetry: Hyper-V-VMMS/Hyper-V-Worker event logs + host Security log + SCVMM job history. | harden: Dedicated management NIC/vLAN, Shielded VMs for sensitive workloads, guarded fabric where available.
- **Firewall Appliances:** Best telemetry: traffic/deny logs + admin audit log + config-change diffs shipped to SIEM. | harden: Default-deny with documented rules, admin on dedicated interface with MFA, config backups versioned.
- **IDS/IPS Sensors:** Best telemetry: alert logs with full packet captures for high-severity events + sensor health metrics. | harden: Sensors on SPAN/TAP at every trust boundary; signature sets auto-updated; TLS inspection feeding sensors.
- **VPN Gateways:** Best telemetry: authentication logs + session logs (user, IP, bytes, duration) + gateway patch state. | harden: MFA on every VPN profile, device posture checks before granting access, gateway firmware patched urgently.
- **Wireless Controllers:** Best telemetry: client association/auth logs + rogue-AP detection + RADIUS accounting. | harden: WPA3-Enterprise with EAP-TLS (certificates, not PSK); rogue-AP containment enabled.
- **Email Gateways:** Best telemetry: message-tracking logs + sandbox verdicts + URL-rewrite click logs. | harden: Sandbox detonation for all attachments/links, DMARC p=reject on owned domains, banner external mail.
- **Web Applications:** Best telemetry: app audit logs (with authenticated identity) + WAF logs + structured access logs. | harden: Authorization checks on every object reference, output encoding, parameterized queries, secure session handling.
- **API Gateways:** Best telemetry: per-request logs with API key/identity, endpoint, params hash, and response size. | harden: Positive-security policies: schema validation, per-client rate limits, OAuth scopes per endpoint.
- **Database Servers:** Best telemetry: query audit logs (who ran what) + auth logs + backup/restore history. | harden: Least-privilege DB roles, no app superusers, encrypted connections, auditing on privileged actions.
- **File Servers:** Best telemetry: object-access auditing (who opened/modified what) + share-permission reviews. | harden: Access-based enumeration, least-privilege share/NTFS rights, no Everyone:Full Control anywhere.
- **Backup Servers:** Best telemetry: job audit logs + admin-console access logs + integrity-check results. | harden: Immutable storage, separate admin credentials with MFA, no domain-joined backup console if avoidable.
- **DNS Servers:** Best telemetry: query logs (or passive DNS) + zone-transfer/change audit + resolver cache stats. | harden: Restrict recursion to internal clients, block outbound port 53 except resolvers, DNSSEC validation on.
- **Proxy Servers:** Best telemetry: full URL logs with user identity + TLS SNI logs + block/allow verdicts. | harden: Authenticated proxying (no anonymous egress), category blocking, TLS inspection where policy allows.
- **SIEM Platforms:** Best telemetry: ingestion health metrics + rule-hit history + analyst audit trail. | harden: Separate SIEM admin credentials, tamper-evident storage, monitored ingestion pipelines.
- **EDR Consoles:** Best telemetry: raw process/network telemetry + detection history + sensor health inventory. | harden: Tamper protection locked with console-only disable, auto-isolation policies for high-severity detections.
- **Container Registries:** Best telemetry: push/pull audit logs + image-scan results + signature verification logs. | harden: Image signing required, immutable tags for releases, vulnerability gates blocking critical CVEs.
- **Code Repositories:** Best telemetry: push/audit logs + secret-scanning alerts + branch-protection change history. | harden: Branch protection with required reviews, signed commits, push protection for secrets.
- **CI/CD Runners:** Best telemetry: job execution logs + runner registration events + secret-access audit. | harden: Ephemeral isolated runners, OIDC short-lived credentials, no persistent secrets on runners.
- **IoT Device Fleets:** Best telemetry: device heartbeat/status + firmware version inventory + network flow from IoT VLAN. | harden: Dedicated VLAN with no internet egress except via proxy, unique credentials per device, firmware update process.
- **OT Controllers:** Best telemetry: passive OT network monitoring + engineering-workstation logs + change-management records. | harden: Air-gap or data-diode segmentation from IT, unidirectional gateways, strict change control on logic.
- **Mobile Devices (MDM):** Best telemetry: MDM compliance/app inventory + mobile threat defense alerts + enrollment logs. | harden: Enrollment required for corporate data, OS version minimums, jailbreak/root = automatic quarantine.
- **SaaS Applications:** Best telemetry: SaaS audit logs (admin + user activity) streamed to SIEM + SSO logs. | harden: SSO with MFA enforced, SCIM provisioning, least-privilege roles, external-sharing restricted.
- **SSO Identity Providers:** Best telemetry: authentication logs with MFA detail + app-assignment changes + federation trust changes. | harden: Phishing-resistant MFA default, sign-on policies per app risk, session lifetime limits.
- **Secrets Vaults:** Best telemetry: secret access audit (who read what, when) + policy-change audit + unseal events. | harden: Short-lived dynamic secrets, no static long-lived tokens, MFA on UI access, sealed storage backend.
- **Load Balancers:** Best telemetry: access logs with X-Forwarded-For + backend health flaps + config-change audit. | harden: TLS 1.2+ with strong ciphers, HSTS, WAF integration at the edge, config changes via version control.
- **Message Queues:** Best telemetry: queue depth/lag metrics + producer/consumer auth logs + dead-letter queues. | harden: Authentication on all clients, TLS in transit, authorization per queue/topic, quotas on producers.
- **Network Switches:** Best telemetry: syslog (port up/down, STP changes, config changes) + SNMP/NetFlow + NAC logs. | harden: Port security / 802.1X on access ports, BPDU guard, DHCP snooping + dynamic ARP inspection.

### Environments (10)

- **On-Premises Datacenter:** Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture. | control: Physical access controls with badge logs correlatable to logical access during investigations.
- **AWS Cloud:** Organization CloudTrail in all regions, GuardDuty, and VPC flow logs shipped to the security account. | control: SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).
- **Azure Cloud:** Activity Log and Entra sign-in/audit logs streamed to Log Analytics/SIEM; Defender for Cloud alerts. | control: Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.
- **GCP Cloud:** Cloud Audit Logs (admin + data access) exported to a locked-down logging project. | control: Organization policies constraining public exposure, API enablement, and service-account key creation.
- **Hybrid Cloud:** Unified SIEM ingesting both on-prem syslog and cloud audit trails with identity correlation across both. | control: Consistent identity (single IdP) across on-prem and cloud; no parallel credential stores.
- **Remote Workforce:** EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts). | control: Zero-trust access: device compliance + MFA per application, not per network.
- **Branch Offices:** SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution. | control: Standardized branch firewall policy deployed as code; no local admin exceptions.
- **Colocation Facilities:** Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually). | control: Locked cabinets, private cages, and escort policies for remote hands.
- **Air-Gapped Networks:** Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs. | control: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
- **Multi-Cloud:** Cloud-agnostic SIEM normalizing AWS CloudTrail, Azure Activity Log, and GCP Audit Logs into one schema. | control: Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.

### Maturity tiers (5)

- **Foundational:** Foundational maturity: core hygiene is in place but detection is largely manual and reactive. This playbook emphasizes the minimum viable checks, free or built… Next: Start with the built-in logs and free tools listed here before buying anything — most incidents are solvable with what the OS already records.
- **Developing:** Developing maturity: centralized logging exists and the SOC runs playbooks, but coverage has gaps. This playbook adds correlation queries, defined roles, and c… Next: Build one correlation rule per detection signal in this playbook and tune it for 30 days before trusting its output.
- **Defined:** Defined maturity: documented processes, measured SLAs, and broad telemetry coverage. This playbook adds metrics per phase, threat-informed prioritization, and … Next: Track MTTD/MTTR for this scenario class and review monthly; a rising trend triggers a control-gap review.
- **Managed:** Managed maturity: quantitative management with automation handling routine containment. This playbook adds SOAR-driven enrichment and pre-approved containment … Next: Automate enrichment (threat intel, asset criticality, user risk) so every alert for this scenario arrives pre-scored.
- **Optimized:** Optimized maturity: continuous improvement driven by adversary emulation and detection-as-code. This playbook adds purple-team validation, atomic-test coverage… Next: Validate every detection in this playbook with adversary emulation (atomic tests) at least quarterly; retire or fix what fails.

## Analysis notes

- Build a 90-day access timeline for the user: volume, data sensitivity, destination (USB serial, cloud account, personal email) — coordinate collection with HR/legal to stay compliant.
- Determine business justification for each anomaly with the user's manager before concluding malice; over-collection without cause creates liability.

## Hardening notes

- UEBA baselines with alerting on pre-resignation access spikes; disable USB mass storage or enforce encryption + logging.
- Immediate deprovisioning workflow: access revoked at the moment of termination notice, not end of day.

## Pitfalls

- Investigating without HR/legal involvement — privacy and employment law exposure is real.
- Confronting the user before evidence is preserved; they will delete local copies first.

## References

- MITRE ATT&CK: T1005 (Collection: Data from Local System) — insider context

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI. Compressed 2026-09-29 from 2,000 combinatorial variants per Chauncey's ruling.*
