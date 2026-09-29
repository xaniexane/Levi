"""Batch-3 dimension data: 40 asset types, 10 environments, 5 maturity tiers.

Original defensive blue-team content authored for LEVI. Zero contact with
any external skill repository.
"""

ASSETS = [
    {
        "slug": "windows-workstation",
        "title": "Windows Workstations",
        "telemetry": "Best telemetry: Sysmon + EDR + PowerShell script-block logging forwarded to the SIEM.",
        "artifacts": [
            "Security event log (4624/4625 logons, 4688 process creation, 7045 service installs)",
            "Sysmon operational log and PowerShell operational log (4104 script blocks)",
            "EDR process trees, file-modification timelines, and $MFT / USN journal",
        ],
        "commands": [
            "Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4625} -MaxEvents 50 | Format-List TimeCreated, @{n='TargetUser';e={$_.Properties[5].Value}}, @{n='SourceIP';e={$_.Properties[19].Value}}",
            "autorunsc64.exe -accepteula -a * -c -h -s -t | findstr /v \"Microsoft Corporation\"",
            "Get-ScheduledTask | Where-Object {$_.TaskPath -notlike '\\Microsoft*'} | Get-ScheduledTaskInfo | Sort-Object LastRunTime -Descending",
        ],
        "harden": [
            "Application allowlisting (WDAC/AppLocker) and LSA Protection + Credential Guard enabled.",
            "Remove local admin rights from daily-use accounts; deploy LAPS for the built-in Administrator.",
        ],
        "tags": ["windows", "endpoint"],
    },
    {
        "slug": "windows-server",
        "title": "Windows Servers",
        "telemetry": "Best telemetry: Security log with advanced audit policy + Sysmon + service-install monitoring.",
        "artifacts": [
            "Security log (7045 service installs, 4720 account creation, 4732 group changes)",
            "IIS/HTTP.sys logs for web-facing roles; scheduled-task store in C:\\Windows\\System32\\Tasks",
            "Service binaries and their hashes; registry service keys under HKLM\\SYSTEM\\CurrentControlSet\\Services",
        ],
        "commands": [
            "Get-WinEvent -FilterHashtable @{LogName='System'; Id=7045} | Select-Object -First 20 TimeCreated, Message",
            "Get-Service | Where-Object {$_.Status -eq 'Running'} | ForEach-Object { Get-CimInstance Win32_Service -Filter \"Name='$($_.Name)'\" | Select-Object Name, PathName, StartName }",
            "wevtutil qe Security \"/q:*[System[(EventID=4720)]]\" /f:text /c:20",
        ],
        "harden": [
            "Server Core installs where possible; disable unnecessary roles and SMBv1; enforce SMB signing.",
            "Just Enough Administration (JEA) endpoints for remote management instead of full admin sessions.",
        ],
        "tags": ["windows", "server"],
    },
    {
        "slug": "linux-server",
        "title": "Linux Servers",
        "telemetry": "Best telemetry: auditd + centralized syslog/journald + osquery or an EDR agent.",
        "artifacts": [
            "auth.log/secure (SSH logons), auditd logs (execve, file writes), and cron tables (/etc/crontab, /etc/cron.d/*, user crontabs)",
            "systemd unit files in /etc/systemd/system/ and SSH authorized_keys files for all users",
            "Web/app access logs and package-manager histories for the server's role",
        ],
        "commands": [
            "sudo grep -E 'Failed|Accepted' /var/log/auth.log | tail -40",
            "sudo ausearch -m EXECVE --start recent -i | grep -E 'curl|wget|bash|sh|python|perl' | tail -30",
            "ls -la /etc/cron.d/ /var/spool/cron/crontabs/ 2>/dev/null; systemctl list-timers --all --no-pager | head -30",
        ],
        "harden": [
            "Key-only SSH (no passwords), fail2ban or equivalent, unattended security updates enabled.",
            "Least-privilege sudoers, no NOPASSWD, remove unused SUID binaries, and mandatory access controls where available.",
        ],
        "tags": ["linux", "server"],
    },
    {
        "slug": "linux-workstation",
        "title": "Linux Workstations",
        "telemetry": "Best telemetry: auditd user-session logging + EDR agent + desktop shell histories (with user notice).",
        "artifacts": [
            "User shell histories (~/.bash_history), desktop autostart entries (~/.config/autostart/)",
            "auditd execve logs and USB device logs; browser profiles for web-vector cases",
            "Package manager logs showing recently installed software",
        ],
        "commands": [
            "ls -la ~/.config/autostart/ 2>/dev/null; grep -r 'Exec=' ~/.config/autostart/ 2>/dev/null",
            "sudo ausearch --start recent -m EXECVE -i | tail -30",
            "last -n 30; echo ---; sudo grep -i 'usb' /var/log/syslog 2>/dev/null | tail -10",
        ],
        "harden": [
            "Standard user accounts for daily work, full-disk encryption, and screen-lock enforcement.",
            "Approved software repositories only; browser sandboxing and ad/script blocking by policy.",
        ],
        "tags": ["linux", "endpoint"],
    },
    {
        "slug": "macos-endpoint",
        "title": "macOS Endpoints",
        "telemetry": "Best telemetry: unified log + EDR agent + Santa/Munki logs where deployed.",
        "artifacts": [
            "Unified log (log show) for process execution and auth events; login items and LaunchAgents/LaunchDaemons plists",
            "Quarantine attributes (xattr com.apple.quarantine) on downloads; Gatekeeper assessment history",
            "EDR telemetry for process trees and network connections",
        ],
        "commands": [
            "log show --predicate 'eventMessage contains \"sshd\"' --last 2h | tail -20",
            "ls -la ~/Library/LaunchAgents/ /Library/LaunchDaemons/ /Library/LaunchAgents/ 2>/dev/null",
            "xattr -l ~/Downloads/* 2>/dev/null | grep -A2 quarantine | head -30",
        ],
        "harden": [
            "Gatekeeper + XProtect current, FileVault on, firewall on, and MDM-enforced configuration profiles.",
            "Block unsigned kernel extensions; require admin approval for new login items.",
        ],
        "tags": ["macos", "endpoint"],
    },
    {
        "slug": "active-directory-dc",
        "title": "Active Directory Domain Controllers",
        "telemetry": "Best telemetry: forwarded Security logs (4768/4769/4771/4662/4720/4732/4724/5136) + AD replication monitoring.",
        "artifacts": [
            "Security log Kerberos events (4768 TGT requests, 4769 service tickets, 4771 pre-auth failures)",
            "Directory-service change events (5136/5137) and replication metadata (repadmin /showobjmeta)",
            "NTDS.dit (via authorized forensic copy only) and SYSVOL contents including GPO scripts",
        ],
        "commands": [
            "repadmin /showrepl | Select-String -Pattern 'error|fail' -Context 2",
            "Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4769} -MaxEvents 200 | Group-Object {$_.Properties[0].Value} | Sort-Object Count -Descending | Select-Object -First 10 Name, Count",
            "Get-ADUser -Filter * -Properties userAccountControl | Where-Object { ($_.userAccountControl -band 0x400000) } | Select-Object SamAccountName",
        ],
        "harden": [
            "Tier-zero isolation: DCs on dedicated hosts, no browsing/email, admin access via PAW/jump host only.",
            "Audit and strip replication rights (Get-Changes-All); enforce AES Kerberos; protect AdminSDHolder.",
        ],
        "tags": ["windows", "identity", "active-directory"],
    },
    {
        "slug": "entra-id-tenant",
        "title": "Microsoft Entra ID Tenants",
        "telemetry": "Best telemetry: Entra sign-in + audit logs streamed to Log Analytics/SIEM with 30+ day retention.",
        "artifacts": [
            "Sign-in logs (interactive, non-interactive, service principal) with risk detections and MFA details",
            "Audit logs: app registrations, consent grants, Conditional Access changes, role assignments",
            "Identity Protection risk detections and risky-user/service-principal listings",
        ],
        "commands": [
            "# Microsoft Graph (delegated admin): recent risky sign-ins",
            "Get-MgAuditLogSignIn -Filter \"riskState eq 'atRisk'\" -Top 25 | Select-Object CreatedDateTime, UserPrincipalName, IpAddress, @{n='Risk';e={$_.RiskDetail}}",
            "Get-MgApplication -All | Where-Object {$_.CreatedDateTime -gt (Get-Date).AddDays(-30)} | Select-Object DisplayName, CreatedDateTime, PublisherDomain",
        ],
        "harden": [
            "Conditional Access: require phishing-resistant MFA, compliant devices, block legacy auth and risky sign-ins.",
            "Admin-consent workflow for apps; PIM for all privileged roles with approval and short activation.",
        ],
        "tags": ["identity", "cloud", "microsoft"],
    },
    {
        "slug": "aws-account",
        "title": "AWS Accounts",
        "telemetry": "Best telemetry: CloudTrail (org trail, all regions) + GuardDuty + VPC flow logs + Config.",
        "artifacts": [
            "CloudTrail event history (console logons, IAM changes, AssumeRole, security-group changes)",
            "GuardDuty findings, IAM Access Analyzer results, and S3 server-access logs for data stores",
            "VPC flow logs and instance system logs for workload-level evidence",
        ],
        "commands": [
            "aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=ConsoleLogin --max-items 20",
            "aws iam generate-credential-report && aws iam get-credential-report --query Content --output text | base64 -d | head -5",
            "aws guardduty list-findings --detector-id $(aws guardduty list-detectors --query 'DetectorIds[0]' --output text) --max-results 15",
        ],
        "harden": [
            "MFA on root + all IAM users, SCPs denying logging disablement and unapproved regions, no long-lived keys.",
            "GuardDuty + Security Hub enabled org-wide; CloudTrail to immutable, separate-account bucket.",
        ],
        "tags": ["cloud", "aws"],
    },
    {
        "slug": "azure-subscription",
        "title": "Azure Subscriptions",
        "telemetry": "Best telemetry: Activity Log + Entra sign-in logs + Defender for Cloud + NSG flow logs.",
        "artifacts": [
            "Azure Activity Log (write/delete on IAM, policy, network) and Entra audit/sign-in logs",
            "Defender for Cloud recommendations and alerts; resource-change history",
            "NSG flow logs and storage diagnostic logs for data-plane evidence",
        ],
        "commands": [
            "az monitor activity-log list --max-events 25 --query '[].{time:eventTimestamp, op:operationName.value, caller:caller}' -o table",
            "az security alert list --query '[].{name:alertDisplayName, severity:severity, time:timeGeneratedUtc}' -o table",
            "az role assignment list --all --query '[?createdByType!=`Application`].{principal:principalName, role:roleDefinitionName}' -o table | head -30",
        ],
        "harden": [
            "Azure Policy deny-effects on public storage/exposure; PIM for subscription roles; Defender plans on.",
            "No service-principal secrets in code — workload identity federation; private endpoints for PaaS.",
        ],
        "tags": ["cloud", "azure"],
    },
    {
        "slug": "gcp-project",
        "title": "GCP Projects",
        "telemetry": "Best telemetry: Cloud Audit Logs (Admin Activity + Data Access) + Security Command Center + VPC flow logs.",
        "artifacts": [
            "Cloud Audit Logs: setIamPolicy, storage.setIamPermissions, compute inserts, and console logons",
            "Security Command Center findings; Forseti/Config Validator drift reports where deployed",
            "VPC flow logs and Cloud DNS query logs",
        ],
        "commands": [
            "gcloud logging read 'protoPayload.methodName:\"SetIamPolicy\"' --limit 20 --format='table(timestamp, protoPayload.authenticationInfo.principalEmail, resourceName)'",
            "gcloud scc findings list organizations/$ORG_ID --filter='state=\"ACTIVE\"' --limit 15",
            "gcloud projects get-iam-policy $PROJECT --format=json | python3 -c 'import json,sys; [print(b[\"role\"], [m for m in b[\"members\"]]) for b in json.load(sys.stdin)[\"bindings\"]]'",
        ],
        "harden": [
            "Organization policies: no public buckets, no default SA use, OS Login on; deny unapproved APIs.",
            "No user-managed service-account keys; workload identity federation; SCC premium tier on.",
        ],
        "tags": ["cloud", "gcp"],
    },
    {
        "slug": "kubernetes-cluster",
        "title": "Kubernetes Clusters",
        "telemetry": "Best telemetry: Kubernetes audit logs + container runtime logs + admission-controller denials.",
        "artifacts": [
            "API-server audit log (who created pods/bindings/secrets, from where)",
            "Kubelet/container runtime logs and image pull histories per node",
            "etcd-adjacent evidence: secret access patterns and controller-manager logs",
        ],
        "commands": [
            "kubectl audit2rbac --filename=audit.log 2>/dev/null | head; kubectl get clusterrolebindings -o wide | head -20",
            "kubectl get pods -A -o json | python3 -c \"import json,sys; [print(p['metadata']['namespace'], p['metadata']['name'], p['spec'].get('hostNetwork'), p['spec'].get('hostPID')) for p in json.load(sys.stdin)['items']]\" | head -30",
            "kubectl auth can-i --list --as=system:serviceaccount:default:default | head -20",
        ],
        "harden": [
            "Least-privilege RBAC, Pod Security Standards enforced, no privileged pods, image signing/verification.",
            "Audit logging on; secrets via external vault with short TTLs; network policies default-deny.",
        ],
        "tags": ["containers", "kubernetes"],
    },
    {
        "slug": "docker-host",
        "title": "Docker Hosts",
        "telemetry": "Best telemetry: Docker daemon logs + host auditd + container stdout/stderr shipped centrally.",
        "artifacts": [
            "Docker daemon log (container create/start with full flags), docker events history",
            "Container image digests and layer histories (docker history) versus expected digests",
            "Host auditd execve logs showing container-runtime-spawned processes",
        ],
        "commands": [
            "docker ps --format '{{.Names}} {{.Image}}' ; echo ---; docker events --since 24h --until 0s 2>/dev/null | tail -20",
            "docker inspect $(docker ps -q) --format '{{.Name}} privileged={{.HostConfig.Privileged}} mounts={{.Mounts}}' 2>/dev/null",
            "sudo ausearch --start recent -k docker -i 2>/dev/null | tail -20",
        ],
        "harden": [
            "No --privileged, no host socket mounts except for explicit agents, user namespaces enabled, read-only root filesystems.",
            "Images from trusted registries with digest pinning; daemon socket never TCP-exposed.",
        ],
        "tags": ["containers", "docker"],
    },
    {
        "slug": "vmware-esxi",
        "title": "VMware ESXi Hosts",
        "telemetry": "Best telemetry: vCenter tasks/events + ESXi syslog + lockdown-mode audit.",
        "artifacts": [
            "vCenter tasks and events (VM power ops, snapshot create/delete, host profile changes)",
            "ESXi hostd/vpxa logs and shell-access records; VM .vmx changes",
            "Virtual switch port-group changes and vMotion histories",
        ],
        "commands": [
            "esxcli system auditrecords local list | tail -20",
            "vim-cmd vmsvc/getallvms 2>/dev/null | head -20",
            "esxcli network vm list 2>/dev/null; echo ---; esxcli system permission list 2>/dev/null",
        ],
        "harden": [
            "Lockdown mode on, isolated management network, unique per-host root passwords, MFA on vCenter.",
            "VM snapshots monitored; virtual hardware kept patched; no direct host shell for daily admin.",
        ],
        "tags": ["virtualization", "vmware"],
    },
    {
        "slug": "hyperv-host",
        "title": "Hyper-V Hosts",
        "telemetry": "Best telemetry: Hyper-V-VMMS/Hyper-V-Worker event logs + host Security log + SCVMM job history.",
        "artifacts": [
            "Microsoft-Windows-Hyper-V-VMMS event log (VM create/start/stop, checkpoint ops)",
            "Virtual switch and virtual NIC configuration; VM configuration files and checkpoints",
            "Host Security log for administrative logons and privilege use",
        ],
        "commands": [
            "Get-WinEvent -LogName 'Microsoft-Windows-Hyper-V-VMMS-Admin' -MaxEvents 25 | Select-Object TimeCreated, Id, Message | Format-Table -Wrap",
            "Get-VM | Select-Object Name, State, CheckpointType, @{n='Switch';e={(Get-VMNetworkAdapter $_).SwitchName}} | Format-Table",
            "Get-VMSnapshot -VMName * | Select-Object VMName, Name, CreationTime | Sort-Object CreationTime -Descending | Select-Object -First 10",
        ],
        "harden": [
            "Dedicated management NIC/vLAN, Shielded VMs for sensitive workloads, guarded fabric where available.",
            "Checkpoints treated as temporary; host patching cadence equal to guest patching.",
        ],
        "tags": ["virtualization", "hyperv", "windows"],
    },
    {
        "slug": "firewall-appliance",
        "title": "Firewall Appliances",
        "telemetry": "Best telemetry: traffic/deny logs + admin audit log + config-change diffs shipped to SIEM.",
        "artifacts": [
            "Traffic logs (allowed/denied with rule IDs), threat logs (IPS/AV verdicts), admin audit log",
            "Configuration revisions and diffs; VPN session logs and authentication failures",
            "URL-filtering logs for web-vector cases",
        ],
        "commands": [
            "# vendor CLIs differ; conceptually:",
            "show log traffic query (source <suspect-ip>)             # Palo Alto style",
            "show log system query (eventid eq config-commit)          # config change audit",
            "diagnose sys session list | grep <suspect-ip>              # FortiOS live sessions",
        ],
        "harden": [
            "Default-deny with documented rules, admin on dedicated interface with MFA, config backups versioned.",
            "IPS/threat-prevention profiles on internet-facing rules; TLS inspection where policy allows.",
        ],
        "tags": ["network", "firewall"],
    },
    {
        "slug": "ids-ips-sensor",
        "title": "IDS/IPS Sensors",
        "telemetry": "Best telemetry: alert logs with full packet captures for high-severity events + sensor health metrics.",
        "artifacts": [
            "Signature alert logs with triggering packet payloads; anomaly-detection baselines and deviations",
            "PCAP ring buffers for incident windows; sensor placement/coverage maps",
            "Tuning history: suppressed signatures and their justifications",
        ],
        "commands": [
            "# Suricata/Snort style triage:",
            "jq -c 'select(.alert.severity<=2) | {ts:.timestamp, sig:.alert.signature, src:.src_ip, dst:.dest_ip}' /var/log/suricata/eve.json | tail -20",
            "tcpdump -r /var/log/sensor/capture.pcap -nn host <suspect-ip> 2>/dev/null | head -30",
            "suricata --dump-counters 2>/dev/null | grep -i drop | head -5",
        ],
        "harden": [
            "Sensors on SPAN/TAP at every trust boundary; signature sets auto-updated; TLS inspection feeding sensors.",
            "Alert tuning as a managed process: every suppression documented with expiry dates.",
        ],
        "tags": ["network", "ids"],
    },
    {
        "slug": "vpn-gateway",
        "title": "VPN Gateways",
        "telemetry": "Best telemetry: authentication logs + session logs (user, IP, bytes, duration) + gateway patch state.",
        "artifacts": [
            "VPN auth logs (success/failure per user with source IPs), session tables with data volumes",
            "Gateway admin audit log and firmware/patch version; client version inventory",
            "Post-auth network flows from VPN-assigned addresses into the LAN",
        ],
        "commands": [
            "# conceptually (vendor CLIs differ):",
            "show vpn-sessiondb detail anyconnect | grep -E 'Username|Assigned IP|Login Time'",
            "grep -i 'failed' /var/log/vpn-auth.log | tail -30",
            "show version   # confirm gateway firmware is current",
        ],
        "harden": [
            "MFA on every VPN profile, device posture checks before granting access, gateway firmware patched urgently.",
            "Split-tunnel policies reviewed; idle/session timeouts enforced; no shared VPN credentials.",
        ],
        "tags": ["network", "vpn", "remote-access"],
    },
    {
        "slug": "wifi-controller",
        "title": "Wireless Controllers",
        "telemetry": "Best telemetry: client association/auth logs + rogue-AP detection + RADIUS accounting.",
        "artifacts": [
            "Client association, authentication (EAP) and roaming logs with device MACs",
            "Rogue AP / evil-twin detections and deauth-flood alerts from WIDS",
            "RADIUS accounting records tying users to sessions and data volumes",
        ],
        "commands": [
            "# conceptually (vendor CLIs differ):",
            "show wireless client summary | include <suspect-mac>",
            "show wireless wps rogue ap summary",
            "grep <username> /var/log/radius/accounting.log | tail -20",
        ],
        "harden": [
            "WPA3-Enterprise with EAP-TLS (certificates, not PSK); rogue-AP containment enabled.",
            "Separate SSIDs/VLANs for corporate, guest, and IoT; PSK rotated on staff changes.",
        ],
        "tags": ["network", "wireless"],
    },
    {
        "slug": "email-gateway",
        "title": "Email Gateways",
        "telemetry": "Best telemetry: message-tracking logs + sandbox verdicts + URL-rewrite click logs.",
        "artifacts": [
            "Message tracking (sender, recipients, subject hash, attachments, verdicts) for the campaign window",
            "Sandbox detonation reports for attachments/URLs; quarantined message copies",
            "Click-time URL protection logs showing who clicked weaponized links",
        ],
        "commands": [
            "# conceptually (gateway CLIs differ):",
            "message-tracking --sender <suspect-domain> --last 7d",
            "quarantine list --reason malware --last 7d",
            "url-protection clicks --url <suspect-url> --last 7d",
        ],
        "harden": [
            "Sandbox detonation for all attachments/links, DMARC p=reject on owned domains, banner external mail.",
            "Attachment-type policies blocking macros/ISOs; reported-phish button deployed to mail clients.",
        ],
        "tags": ["email", "phishing"],
    },
    {
        "slug": "web-application",
        "title": "Web Applications",
        "telemetry": "Best telemetry: app audit logs (with authenticated identity) + WAF logs + structured access logs.",
        "artifacts": [
            "Application audit log: who did what to which object, with session IDs and source IPs",
            "WAF block logs and anomaly scores; web-server access/error logs around the incident",
            "Uploaded-file quarantine and form-input validation failure logs",
        ],
        "commands": [
            "grep -E ' 4[0-9]{2} | 5[0-9]{2} ' /var/log/nginx/access.log | awk '{print $1}' | sort | uniq -c | sort -rn | head -15",
            "journalctl -u myapp --since '2 hours ago' | grep -iE 'error|unauthor|exception' | tail -30",
            "find /var/www/uploads -type f -newermt '2026-09-20' -exec ls -la {} \\; 2>/dev/null | head -20",
        ],
        "harden": [
            "Authorization checks on every object reference, output encoding, parameterized queries, secure session handling.",
            "WAF in blocking mode with tuned rules; file-upload allowlisting by type with malware scanning.",
        ],
        "tags": ["web", "application"],
    },
    {
        "slug": "api-gateway",
        "title": "API Gateways",
        "telemetry": "Best telemetry: per-request logs with API key/identity, endpoint, params hash, and response size.",
        "artifacts": [
            "Gateway access logs with authenticated identity per call; rate-limit trigger logs",
            "Schema-validation failure logs (attacks often start as malformed requests)",
            "Backend latency/error spikes correlated with abuse windows",
        ],
        "commands": [
            "grep <api-key-id> /var/log/apigw/access.log | awk '{print $7}' | sort | uniq -c | sort -rn | head -20",
            "grep -c 'schema_validation_failed' /var/log/apigw/error.log",
            "awk '{print $1}' /var/log/apigw/access.log | sort | uniq -c | sort -rn | head -10  # top callers",
        ],
        "harden": [
            "Positive-security policies: schema validation, per-client rate limits, OAuth scopes per endpoint.",
            "Key rotation support, anomaly alerting per API key, and versioned/deprecated insecure endpoints.",
        ],
        "tags": ["web", "api"],
    },
    {
        "slug": "database-server",
        "title": "Database Servers",
        "telemetry": "Best telemetry: query audit logs (who ran what) + auth logs + backup/restore history.",
        "artifacts": [
            "Database audit log: logons, privileged statements (DCL/DDL), and bulk-export queries",
            "Slow/general query logs around the incident window; new users, roles, or linked servers",
            "Backup files and restore history; replication topology changes",
        ],
        "commands": [
            "-- PostgreSQL style:",
            "SELECT usename, query, query_start FROM pg_stat_activity WHERE state='active' ORDER BY query_start;",
            "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;",
            "-- check for new superusers:",
            "SELECT usename FROM pg_user WHERE usesuper;",
        ],
        "harden": [
            "Least-privilege DB roles, no app superusers, encrypted connections, auditing on privileged actions.",
            "Network isolation: DB reachable only from app tier; backups encrypted and tested.",
        ],
        "tags": ["data", "database"],
    },
    {
        "slug": "file-server",
        "title": "File Servers",
        "telemetry": "Best telemetry: object-access auditing (who opened/modified what) + share-permission reviews.",
        "artifacts": [
            "File-access audit events (4663/4656 on Windows; auditd on Linux) for sensitive shares",
            "Share and NTFS/ACL permission exports; recent permission-change events",
            "Ransomware-style signals: mass renames, extension changes, or new note files",
        ],
        "commands": [
            "Get-SmbShare | Select-Object Name, Path, Description; echo ---; Get-SmbShareAccess -Name <share>",
            "Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4663} -MaxEvents 100 | Group-Object {$_.Properties[1].Value} | Sort-Object Count -Descending | Select-Object -First 10 Name, Count",
            "find /srv/shares -name '*DECRYPT*' -o -name '*README*ransom*' 2>/dev/null | head",
        ],
        "harden": [
            "Access-based enumeration, least-privilege share/NTFS rights, no Everyone:Full Control anywhere.",
            "FSRM/file-screening to block known ransomware extensions; offline backup of shares.",
        ],
        "tags": ["data", "windows", "linux"],
    },
    {
        "slug": "backup-server",
        "title": "Backup Servers",
        "telemetry": "Best telemetry: job audit logs + admin-console access logs + integrity-check results.",
        "artifacts": [
            "Backup job definitions, run histories, and deletion/retention-change audit entries",
            "Admin console logons and configuration exports; repository credential-change history",
            "Integrity/verification job results and recovery-point inventories",
        ],
        "commands": [
            "# conceptually (product CLIs differ):",
            "backup-cli jobs list --failed --last 7d",
            "backup-cli audit log --action delete --last 30d",
            "backup-cli repository verify --latest",
        ],
        "harden": [
            "Immutable storage, separate admin credentials with MFA, no domain-joined backup console if avoidable.",
            "Alert on any deletion or retention change; monthly test restores with integrity verification.",
        ],
        "tags": ["backup", "ransomware"],
    },
    {
        "slug": "dns-server",
        "title": "DNS Servers",
        "telemetry": "Best telemetry: query logs (or passive DNS) + zone-transfer/change audit + resolver cache stats.",
        "artifacts": [
            "DNS query logs showing tunneling/DGA patterns; zone files and their change history",
            "Zone-transfer (AXFR) request logs; DNSSEC validation failure logs",
            "Cache contents for poisoned or hijacked entries",
        ],
        "commands": [
            "grep -E '.{60,}' /var/log/named/query.log | tail -20   # long labels: tunneling/DGA",
            "rndc status; echo ---; journalctl -u named --since '1 hour ago' | grep -iE 'transfer|denied|error' | tail -15",
            "dig @localhost <suspect-domain> TXT +short",
        ],
        "harden": [
            "Restrict recursion to internal clients, block outbound port 53 except resolvers, DNSSEC validation on.",
            "RPZ feeds for malicious domains; TSIG for zone transfers; query logging retained centrally.",
        ],
        "tags": ["network", "dns"],
    },
    {
        "slug": "proxy-server",
        "title": "Proxy Servers",
        "telemetry": "Best telemetry: full URL logs with user identity + TLS SNI logs + block/allow verdicts.",
        "artifacts": [
            "Access logs (user, URL, category, verdict, bytes) for the incident window",
            "Blocked-request logs showing attempted C2/malware/phishing destinations",
            "Authentication logs tying traffic to user identities",
        ],
        "commands": [
            "grep <username> /var/log/squid/access.log | awk '{print $7}' | sort | uniq -c | sort -rn | head -20",
            "grep -E 'TCP_DENIED|BLOCK' /var/log/squid/access.log | tail -30",
            "awk '{print $3}' /var/log/squid/access.log | sort | uniq -c | sort -rn | head -10  # top users by requests",
        ],
        "harden": [
            "Authenticated proxying (no anonymous egress), category blocking, TLS inspection where policy allows.",
            "Alert on malware/phishing category hits even when blocked — the click already happened.",
        ],
        "tags": ["network", "proxy", "web"],
    },
    {
        "slug": "siem-platform",
        "title": "SIEM Platforms",
        "telemetry": "Best telemetry: ingestion health metrics + rule-hit history + analyst audit trail.",
        "artifacts": [
            "Detection rule hit history for the incident's indicators across the full retention window",
            "Ingestion gap reports: which sources stopped logging and when (coverage blind spots)",
            "Analyst case notes, triage decisions, and escalation history",
        ],
        "commands": [
            "# conceptually (SIEM query languages differ):",
            "index=* <indicator> earliest=-30d | stats count by sourcetype",
            "| metadata type=sources | where recentTime < now()-3600   # stale sources",
            "index=_audit action=search | stats count by user          # analyst activity",
        ],
        "harden": [
            "Separate SIEM admin credentials, tamper-evident storage, monitored ingestion pipelines.",
            "Detection-as-code: rules versioned, tested, with coverage mapping to the threat model.",
        ],
        "tags": ["soc", "siem", "monitoring"],
    },
    {
        "slug": "edr-console",
        "title": "EDR Consoles",
        "telemetry": "Best telemetry: raw process/network telemetry + detection history + sensor health inventory.",
        "artifacts": [
            "Full process trees with command lines, hashes, and network connections for suspect hosts",
            "Detection and response action history (isolations, kills, quarantines)",
            "Sensor health: offline, outdated, or tamper-disabled agents",
        ],
        "commands": [
            "# conceptually (EDR APIs differ):",
            "edr-cli hunt process --hostname <host> --since 24h --tree",
            "edr-cli devices --filter 'sensor_status:offline' --limit 50",
            "edr-cli detections --severity high --last 7d --format table",
        ],
        "harden": [
            "Tamper protection locked with console-only disable, auto-isolation policies for high-severity detections.",
            "Sensor coverage at 100% with alerting on offline/outdated agents; API access scoped and audited.",
        ],
        "tags": ["soc", "edr", "endpoint"],
    },
    {
        "slug": "container-registry",
        "title": "Container Registries",
        "telemetry": "Best telemetry: push/pull audit logs + image-scan results + signature verification logs.",
        "artifacts": [
            "Push/pull audit log (who pushed which tag/digest, who pulled it, from where)",
            "Vulnerability scan results per image; signature (cosign/Notary) verification outcomes",
            "Tag-mutation history: digests changing under floating tags",
        ],
        "commands": [
            "reg audit log --since 7d --action push | head -30",
            "reg scan results --image <image:tag> --severity high,critical",
            "reg tag history <image> | head -20   # digest changes under tags",
        ],
        "harden": [
            "Image signing required, immutable tags for releases, vulnerability gates blocking critical CVEs.",
            "RBAC on push rights; retention policies; pull-through caching with upstream verification.",
        ],
        "tags": ["containers", "supply-chain"],
    },
    {
        "slug": "code-repository",
        "title": "Code Repositories",
        "telemetry": "Best telemetry: push/audit logs + secret-scanning alerts + branch-protection change history.",
        "artifacts": [
            "Push logs (who pushed what to which branch), force-push and history-rewrite records",
            "Secret-scanning and code-scanning alerts with their resolution state",
            "Branch protection and deploy-key/app-permission change history",
        ],
        "commands": [
            "git log --since='7 days ago' --format='%h %an %ad %s' --date=short | head -30",
            "git log --all --diff-filter=A -- '*secret*' '*credential*' '*key*' --format='%h %an %s' | head -20",
            "# hosting audit API: list recent push events and permission changes",
        ],
        "harden": [
            "Branch protection with required reviews, signed commits, push protection for secrets.",
            "Least-privilege app/token scopes; SSO enforcement; dormant-access reviews.",
        ],
        "tags": ["devops", "supply-chain", "secrets"],
    },
    {
        "slug": "cicd-runner",
        "title": "CI/CD Runners",
        "telemetry": "Best telemetry: job execution logs + runner registration events + secret-access audit.",
        "artifacts": [
            "Job logs with executed commands and exit codes for suspect runs",
            "Runner registration/deregistration events and runner version inventory",
            "Secret/variable access logs per job; artifact checksums produced",
        ],
        "commands": [
            "runner-cli jobs list --status failed --last 7d | head -20",
            "runner-cli runners list --format table",
            "grep -iE 'curl|wget|exfil|token' /var/log/runner/job-<id>.log | head -30",
        ],
        "harden": [
            "Ephemeral isolated runners, OIDC short-lived credentials, no persistent secrets on runners.",
            "Pipeline definitions in version control with required reviews; artifact signing.",
        ],
        "tags": ["devops", "supply-chain"],
    },
    {
        "slug": "iot-device-fleet",
        "title": "IoT Device Fleets",
        "telemetry": "Best telemetry: device heartbeat/status + firmware version inventory + network flow from IoT VLAN.",
        "artifacts": [
            "Device inventory with firmware versions and last-seen timestamps",
            "Network flows from the IoT segment (unexpected destinations, scanning behavior)",
            "Device syslog/remote logs where available; default-credential audit results",
        ],
        "commands": [
            "nmap -sn 192.0.2.0/24 2>/dev/null | grep -E 'Nmap scan|MAC' | head -40   # authorized scan only",
            "grep <device-ip> /var/log/iot-flows.log | awk '{print $5}' | sort | uniq -c | sort -rn | head -15",
            "mosquitto_sub -t 'devices/+/status' -C 20 2>/dev/null | head -20   # MQTT status sample",
        ],
        "harden": [
            "Dedicated VLAN with no internet egress except via proxy, unique credentials per device, firmware update process.",
            "Network anomaly detection on the IoT segment; decommission orphaned devices.",
        ],
        "tags": ["iot", "network"],
    },
    {
        "slug": "ot-controller",
        "title": "OT Controllers",
        "telemetry": "Best telemetry: passive OT network monitoring + engineering-workstation logs + change-management records.",
        "artifacts": [
            "OT protocol logs (Modbus/DNP3/OPC) from passive taps — never active-scan OT networks",
            "Engineering workstation access and project-file change logs",
            "Controller firmware/program checksums versus known-good baselines",
        ],
        "commands": [
            "# PASSIVE ONLY on OT networks — no active scanning:",
            "tshark -r /captures/ot-span.pcap -Y 'modbus' -T fields -e frame.time -e modbus.func_code 2>/dev/null | head -20",
            "sha256sum /backups/plc-program-*.bin | diff - baselines.txt",
            "last -n 20   # engineering workstation logons",
        ],
        "harden": [
            "Air-gap or data-diode segmentation from IT, unidirectional gateways, strict change control on logic.",
            "No internet on engineering workstations; removable-media controls; tested offline backups of programs.",
        ],
        "tags": ["ot", "ics", "critical-infrastructure"],
    },
    {
        "slug": "mobile-device-mdm",
        "title": "Mobile Devices (MDM)",
        "telemetry": "Best telemetry: MDM compliance/app inventory + mobile threat defense alerts + enrollment logs.",
        "artifacts": [
            "MDM device inventory: OS versions, jailbreak/root detections, installed app lists",
            "Mobile threat defense alerts (malicious apps, network attacks, OS tampering)",
            "Enrollment/disenrollment and wipe/retire action history",
        ],
        "commands": [
            "# conceptually (MDM APIs differ):",
            "mdm-cli devices list --noncompliant --limit 30",
            "mdm-cli devices get <device-id> --include apps,os,threats",
            "mdm-cli audit log --action wipe --last 30d",
        ],
        "harden": [
            "Enrollment required for corporate data, OS version minimums, jailbreak/root = automatic quarantine.",
            "App allowlisting for corporate profiles; per-app VPN; remote wipe capability tested.",
        ],
        "tags": ["mobile", "mdm", "endpoint"],
    },
    {
        "slug": "saas-application",
        "title": "SaaS Applications",
        "telemetry": "Best telemetry: SaaS audit logs (admin + user activity) streamed to SIEM + SSO logs.",
        "artifacts": [
            "Admin audit log (settings changes, user provisioning, sharing changes)",
            "User activity logs: file access, downloads, external sharing events",
            "OAuth/token grants to third-party integrations",
        ],
        "commands": [
            "# conceptually (SaaS APIs differ):",
            "saas-cli audit log --category admin --last 7d --format table | head -25",
            "saas-cli sharing list --external --last 30d",
            "saas-cli integrations list --format table",
        ],
        "harden": [
            "SSO with MFA enforced, SCIM provisioning, least-privilege roles, external-sharing restricted.",
            "Quarterly access reviews; integration allowlisting; DLP policies where supported.",
        ],
        "tags": ["cloud", "saas", "identity"],
    },
    {
        "slug": "identity-provider-sso",
        "title": "SSO Identity Providers",
        "telemetry": "Best telemetry: authentication logs with MFA detail + app-assignment changes + federation trust changes.",
        "artifacts": [
            "Authentication logs per application (success/failure, MFA method, device, location)",
            "Application assignment and provisioning logs; new SSO integrations",
            "Federation trust and certificate changes",
        ],
        "commands": [
            "# conceptually (IdP APIs differ):",
            "idp-cli logs auth --user <upn> --last 7d --format table | head -25",
            "idp-cli apps list --created-after 30d",
            "idp-cli logs admin --action federation.change --last 90d",
        ],
        "harden": [
            "Phishing-resistant MFA default, sign-on policies per app risk, session lifetime limits.",
            "App integration approval workflow; monitor for new high-privilege app assignments.",
        ],
        "tags": ["identity", "sso", "authentication"],
    },
    {
        "slug": "secrets-vault",
        "title": "Secrets Vaults",
        "telemetry": "Best telemetry: secret access audit (who read what, when) + policy-change audit + unseal events.",
        "artifacts": [
            "Audit log of secret reads/writes/deletes with client identity and source IP",
            "Policy and auth-method changes; root-token generation events",
            "Lease/expiry records for dynamic secrets",
        ],
        "commands": [
            "vault audit log --since 24h 2>/dev/null | grep -E '\"path\":\"secret' | head -20",
            "vault list sys/policy 2>/dev/null; vault auth list 2>/dev/null",
            "vault operator raft list-peers 2>/dev/null   # cluster health",
        ],
        "harden": [
            "Short-lived dynamic secrets, no static long-lived tokens, MFA on UI access, sealed storage backend.",
            "Alert on bulk secret reads and policy changes; break-glass procedures documented and tested.",
        ],
        "tags": ["secrets", "identity"],
    },
    {
        "slug": "load-balancer",
        "title": "Load Balancers",
        "telemetry": "Best telemetry: access logs with X-Forwarded-For + backend health flaps + config-change audit.",
        "artifacts": [
            "Access logs (client IP, Host header, URI, status, bytes) — the edge view of web attacks",
            "Backend pool changes and health-check failure histories",
            "TLS certificate deployments and cipher-suite configurations",
        ],
        "commands": [
            "grep -E ' 4[0-9]{2} ' /var/log/haproxy.log | awk '{print $6}' | sort | uniq -c | sort -rn | head -15",
            "echo 'show stat' | socat unix-connect:/var/run/haproxy.sock stdio 2>/dev/null | cut -d, -f1,2,18 | head -20",
            "openssl s_client -connect <lb-vip>:443 -servername <host> 2>/dev/null | openssl x509 -noout -dates -issuer",
        ],
        "harden": [
            "TLS 1.2+ with strong ciphers, HSTS, WAF integration at the edge, config changes via version control.",
            "Health checks that detect compromised backends; drain procedures tested.",
        ],
        "tags": ["network", "web"],
    },
    {
        "slug": "message-queue",
        "title": "Message Queues",
        "telemetry": "Best telemetry: queue depth/lag metrics + producer/consumer auth logs + dead-letter queues.",
        "artifacts": [
            "Queue metrics: depth spikes, consumer lag, and poison-message dead-letter queues",
            "Authentication logs for producers/consumers; new queue/topic creation events",
            "Message payload samples (with authorization) for injected-content cases",
        ],
        "commands": [
            "rabbitmqctl list_queues name messages consumers 2>/dev/null | head -20",
            "kafka-consumer-groups --bootstrap-server <broker> --describe --all-groups 2>/dev/null | head -20",
            "grep -iE 'auth|denied' /var/log/rabbitmq/*.log 2>/dev/null | tail -15",
        ],
        "harden": [
            "Authentication on all clients, TLS in transit, authorization per queue/topic, quotas on producers.",
            "Alert on queue-depth anomalies and dead-letter growth; schema validation on message ingress.",
        ],
        "tags": ["messaging", "application"],
    },
    {
        "slug": "network-switch",
        "title": "Network Switches",
        "telemetry": "Best telemetry: syslog (port up/down, STP changes, config changes) + SNMP/NetFlow + NAC logs.",
        "artifacts": [
            "Syslog: link-state changes, MAC flaps, STP topology changes, login attempts",
            "MAC address tables and ARP tables for device-to-port mapping during incidents",
            "Configuration archives and diffs; NAC authentication decisions per port",
        ],
        "commands": [
            "show mac address-table | include <suspect-mac>",
            "show logging | include %SEC-6-IPACCESSLOGP|%PORT_SECURITY",
            "show interfaces status | include connected",
        ],
        "harden": [
            "Port security / 802.1X on access ports, BPDU guard, DHCP snooping + dynamic ARP inspection.",
            "Management on isolated VLAN with MFA; config backups versioned; unused ports disabled.",
        ],
        "tags": ["network", "switching"],
    },
]

ENVIRONMENTS = [
    {
        "slug": "on-prem-datacenter",
        "title": "On-Premises Datacenter",
        "telemetry": [
            "Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.",
            "Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.",
        ],
        "controls": [
            "Physical access controls with badge logs correlatable to logical access during investigations.",
            "Network segmentation between server, workstation, management, and DMZ zones with firewall policy between each.",
        ],
        "tags": ["on-prem", "datacenter"],
    },
    {
        "slug": "aws-cloud",
        "title": "AWS Cloud",
        "telemetry": [
            "Organization CloudTrail in all regions, GuardDuty, and VPC flow logs shipped to the security account.",
            "CloudWatch and workload logs centralized; S3 access logging on sensitive buckets.",
        ],
        "controls": [
            "SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).",
            "No long-lived credentials: IAM roles, instance profiles, and OIDC federation for workloads.",
        ],
        "tags": ["cloud", "aws"],
    },
    {
        "slug": "azure-cloud",
        "title": "Azure Cloud",
        "telemetry": [
            "Activity Log and Entra sign-in/audit logs streamed to Log Analytics/SIEM; Defender for Cloud alerts.",
            "NSG flow logs and storage analytics for data-plane visibility.",
        ],
        "controls": [
            "Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.",
            "Private endpoints for PaaS; no public storage accounts; workload identity federation.",
        ],
        "tags": ["cloud", "azure"],
    },
    {
        "slug": "gcp-cloud",
        "title": "GCP Cloud",
        "telemetry": [
            "Cloud Audit Logs (admin + data access) exported to a locked-down logging project.",
            "Security Command Center findings and VPC flow logs centralized.",
        ],
        "controls": [
            "Organization policies constraining public exposure, API enablement, and service-account key creation.",
            "VPC Service Controls perimeters around sensitive data projects.",
        ],
        "tags": ["cloud", "gcp"],
    },
    {
        "slug": "hybrid-cloud",
        "title": "Hybrid Cloud",
        "telemetry": [
            "Unified SIEM ingesting both on-prem syslog and cloud audit trails with identity correlation across both.",
            "Conditional-access and network logs covering the interconnect (ExpressRoute/Direct Connect/VPN).",
        ],
        "controls": [
            "Consistent identity (single IdP) across on-prem and cloud; no parallel credential stores.",
            "Interconnect treated as untrusted: inspected, logged, and segmented like an extranet link.",
        ],
        "tags": ["hybrid", "cloud", "on-prem"],
    },
    {
        "slug": "remote-workforce",
        "title": "Remote Workforce",
        "telemetry": [
            "EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).",
            "VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.",
        ],
        "controls": [
            "Zero-trust access: device compliance + MFA per application, not per network.",
            "Full-disk encryption, EDR tamper protection, and automated patching enforced via MDM.",
        ],
        "tags": ["remote", "endpoint", "zero-trust"],
    },
    {
        "slug": "branch-office",
        "title": "Branch Offices",
        "telemetry": [
            "SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.",
            "NAC or port-level logs identifying which device was on which port during the incident.",
        ],
        "controls": [
            "Standardized branch firewall policy deployed as code; no local admin exceptions.",
            "Guest Wi-Fi fully isolated from corporate; IoT (printers, cameras) on a dedicated VLAN.",
        ],
        "tags": ["branch", "network"],
    },
    {
        "slug": "colocation-facility",
        "title": "Colocation Facilities",
        "telemetry": [
            "Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).",
            "Badge/physical access logs from the facility correlated with remote-hand ticket times.",
        ],
        "controls": [
            "Locked cabinets, private cages, and escort policies for remote hands.",
            "Out-of-band management network independent of the provider's infrastructure.",
        ],
        "tags": ["on-prem", "colocation"],
    },
    {
        "slug": "air-gapped-network",
        "title": "Air-Gapped Networks",
        "telemetry": [
            "Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.",
            "Strict allowlisting logs: every binary execution recorded, since the set is small and known.",
        ],
        "controls": [
            "Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.",
            "No wireless, disabled USB mass storage, and BIOS-level boot controls.",
        ],
        "tags": ["air-gap", "ot", "high-security"],
    },
    {
        "slug": "multi-cloud",
        "title": "Multi-Cloud",
        "telemetry": [
            "Cloud-agnostic SIEM normalizing AWS CloudTrail, Azure Activity Log, and GCP Audit Logs into one schema.",
            "CSPM coverage across all clouds with consistent misconfiguration alerting.",
        ],
        "controls": [
            "Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.",
            "Egress and inter-cloud traffic inspected; no implicit trust between cloud environments.",
        ],
        "tags": ["cloud", "multi-cloud"],
    },
]

TIERS = [
    {
        "slug": "foundational",
        "title": "Foundational",
        "depth": (
            "Foundational maturity: core hygiene is in place but detection is "
            "largely manual and reactive. This playbook emphasizes the "
            "minimum viable checks, free or built-in tooling, and clear "
            "escalation triggers so a small team can still respond correctly."
        ),
        "steps": [
            "Start with the built-in logs and free tools listed here before buying anything — most incidents are solvable with what the OS already records.",
            "Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander.",
        ],
        "tags": ["maturity-foundational"],
    },
    {
        "slug": "developing",
        "title": "Developing",
        "depth": (
            "Developing maturity: centralized logging exists and the SOC runs "
            "playbooks, but coverage has gaps. This playbook adds correlation "
            "queries, defined roles, and checklists that turn ad-hoc response "
            "into a repeatable process."
        ),
        "steps": [
            "Build one correlation rule per detection signal in this playbook and tune it for 30 days before trusting its output.",
            "Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly.",
        ],
        "tags": ["maturity-developing"],
    },
    {
        "slug": "defined",
        "title": "Defined",
        "depth": (
            "Defined maturity: documented processes, measured SLAs, and broad "
            "telemetry coverage. This playbook adds metrics per phase, "
            "threat-informed prioritization, and formal handoffs between "
            "detection, response, and recovery."
        ),
        "steps": [
            "Track MTTD/MTTR for this scenario class and review monthly; a rising trend triggers a control-gap review.",
            "Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog.",
        ],
        "tags": ["maturity-defined"],
    },
    {
        "slug": "managed",
        "title": "Managed",
        "depth": (
            "Managed maturity: quantitative management with automation "
            "handling routine containment. This playbook adds SOAR-driven "
            "enrichment and pre-approved containment actions that execute in "
            "minutes, with humans deciding only the ambiguous cases."
        ),
        "steps": [
            "Automate enrichment (threat intel, asset criticality, user risk) so every alert for this scenario arrives pre-scored.",
            "Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging.",
        ],
        "tags": ["maturity-managed"],
    },
    {
        "slug": "optimized",
        "title": "Optimized",
        "depth": (
            "Optimized maturity: continuous improvement driven by adversary "
            "emulation and detection-as-code. This playbook adds purple-team "
            "validation, atomic-test coverage, and feedback loops that keep "
            "detections effective as attacker tradecraft evolves."
        ),
        "steps": [
            "Validate every detection in this playbook with adversary emulation (atomic tests) at least quarterly; retire or fix what fails.",
            "Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF.",
        ],
        "tags": ["maturity-optimized"],
    },
]
