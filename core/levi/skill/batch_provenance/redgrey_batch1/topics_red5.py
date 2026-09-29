# Red team topics — chunk 5: discovery (10) + lateral movement (10)

RED_5 = [
dict(
slug="ad-enumeration",
title="Active Directory Enumeration Test",
description="Test AD enumeration paths to validate LDAP auditing and enumeration detection.",
tags=["red-team","discovery","active-directory","ldap"],
risk="low", confirm=False,
blue_kw=["active-directory","ldap","discovery","auditing"],
purpose=("AD enumeration is step zero of most intrusions and it's unauthenticated-adjacent: any "
"domain user can read most of the directory. This test maps what enumeration reveals and whether "
"bulk LDAP queries trip any monitoring at all."),
when=[
"Early in AD phases, with any domain user context.",
"To validate LDAP query monitoring and honeypot-object deployment.",
"To scope what an attacker learns before touching a privileged account.",
],
prereq=[
"Authorization for the AD environment; standard domain user context.",
"Enumeration tooling authorized (built-in + lab-standard).",
],
procedure=[
"Enumerate with built-in tools first: net user /domain, dsquery-style LDAP, PowerShell AD module — record what each reveals.",
"Run bulk enumeration (all users, groups, computers, SPNs, trusts) and measure: did any query volume alert?",
"Map trust relationships, privileged groups, and stale objects (the attack-planning view).",
"Check for honeypot accounts/objects: do they exist, and did touching them alert?",
"Deliver the AD-exposure map with LDAP-monitoring and honeypot recommendations.",
],
outputs=[
"AD enumeration results (users, groups, trusts, SPNs).",
"Query-volume detection assessment.",
"Honeypot coverage findings.",
],
pitfalls=[
"Bulk queries during business hours without coordination — they can load DCs.",
"Touching honeypots without telling the blue team the test includes them — coordinate.",
"Exporting the full directory off-network — analyze in place.",
],
references=[
"MITRE ATT&CK: Account Discovery, Group Discovery (T1087, T1069).",
],
blue_note="their AD is readable by design — the test measures whether anyone watches the reading, and whether deception exists.",
),
dict(
slug="network-share-discovery",
title="Network Share Discovery Test",
description="Test network-share enumeration to validate share permissions and sensitive-data exposure.",
tags=["red-team","discovery","shares","smb"],
risk="low", confirm=False,
blue_kw=["shares","smb","discovery","permissions"],
purpose=("Open shares are where credentials, PII, and backups live unprotected. This test enumerates "
"shares across the environment, samples permissions, and validates whether share-access auditing "
"and data-classification controls work."),
when=[
"During discovery phases on Windows networks.",
"To validate share-permission hygiene and auditing.",
"Combined with the sensitive-data discovery test.",
],
prereq=[
"Authorization for share enumeration; read-only sampling.",
"Agreement on sampling depth (listing vs. content sampling).",
],
procedure=[
"Enumerate shares on target hosts and file servers (net view, SMB enumeration).",
"Sample share permissions: which shares grant Everyone/Authenticated Users write?",
"Sample content (canary-named files first): look for credential files, PII patterns, backup files.",
"Record access auditing: did the sampling generate 5140/5145 events, and did anyone review them?",
"Check for administrative shares and their exposure.",
"Deliver the share-hygiene report with permission fixes and auditing recommendations.",
],
outputs=[
"Share inventory with permission analysis.",
"Content-sampling findings (canary-first).",
"Share-access auditing assessment.",
],
pitfalls=[
"Deep content crawling of user shares without approval — sample, don't vacuum.",
"Opening files with live malware — canary patterns and metadata first.",
"Forgetting that share enumeration itself is logged — that's part of the test.",
],
references=[
"MITRE ATT&CK: Network Share Discovery (T1135).",
],
blue_note="their file-share hygiene is under test — Everyone-write shares with credentials inside are findings that predate any exploit.",
),
dict(
slug="cloud-discovery-test",
title="Cloud Resource Discovery Test",
description="Test cloud resource and permission enumeration to validate cloud audit logging.",
tags=["red-team","discovery","cloud","iam"],
risk="low", confirm=False,
blue_kw=["cloud","discovery","iam","audit-logging"],
purpose=("Cloud consoles and APIs expose the whole estate to anyone with read rights — often "
"over-broad. This test enumerates cloud resources, IAM permissions, and storage exposure with a "
"read-only role to validate least privilege and control-plane audit logging."),
when=[
"During cloud phases, with a low-privilege cloud role.",
"To validate IAM least privilege and CloudTrail/audit-log coverage.",
"To find publicly exposed storage and over-permissive roles.",
],
prereq=[
"Authorization for the cloud accounts; read-only test role.",
"Agreement on enumeration scope (accounts, regions).",
],
procedure=[
"With the read-only role, enumerate: IAM users/roles/policies, compute, storage, databases, network config.",
"Evaluate effective permissions: what can this 'read-only' role actually do (privilege-escalation paths noted, not exploited without approval)?",
"Check storage exposure: public buckets, public snapshots, open security groups.",
"Verify control-plane logging: did the enumeration appear in CloudTrail/audit logs, and is it alerted on?",
"Deliver the cloud-exposure map with IAM and logging recommendations.",
],
outputs=[
"Cloud resource and IAM enumeration results.",
"Public-exposure findings.",
"Control-plane logging assessment.",
],
pitfalls=[
"Enumerating beyond the agreed accounts/regions — scope strictly.",
"Exploiting privesc paths found during enumeration without fresh approval — note, don't exploit.",
"Forgetting multi-cloud — cover each provider in scope.",
],
references=[
"MITRE ATT&CK: Cloud Service Discovery (T1526).",
],
blue_note="their cloud IAM least privilege and audit logging are under test — read-only roles that can enumerate everything are the norm to challenge.",
),
dict(
slug="container-discovery",
title="Container and Orchestration Discovery Test",
description="Test container-escape-surface discovery to validate Kubernetes RBAC and audit logging.",
tags=["red-team","discovery","containers","kubernetes"],
risk="low", confirm=False,
blue_kw=["containers","kubernetes","discovery","rbac"],
purpose=("A compromised pod is a foothold with an API server next door. This test enumerates the "
"container's view — service account tokens, mounted secrets, the API server — to validate "
"Kubernetes RBAC, pod security standards, and audit logging."),
when=[
"During container phases, from a test pod.",
"To validate pod security standards and service-account hygiene.",
"To test Kubernetes audit-log coverage of discovery queries.",
],
prereq=[
"Authorization for the test namespace/cluster; test pod with representative service account.",
"Read-only discovery; escape attempts need separate approval.",
],
procedure=[
"From the test pod, enumerate: service-account token, mounted secrets, environment variables, node metadata access.",
"Query the API server with the pod's credentials: what can this service account list and get?",
"Check for host mounts, privileged flags, and host-network in the pod spec.",
"Verify Kubernetes audit logs captured the discovery queries.",
"Deliver the pod-security assessment with RBAC and policy recommendations.",
],
outputs=[
"Pod-visible secret and API enumeration results.",
"Service-account permission analysis.",
"Kubernetes audit-log assessment.",
],
pitfalls=[
"Escaping the container without explicit approval — discovery only unless authorized.",
"Reading real mounted secrets beyond canary verification — report existence, handle values per ROE.",
"Testing in production namespaces without isolation — use the test namespace.",
],
references=[
"MITRE ATT&CK: Container Administration Command; Kubernetes RBAC documentation.",
],
blue_note="their Kubernetes RBAC and pod security standards are under test — over-permissive service accounts are the container finding.",
),
dict(
slug="ad-trust-mapping",
title="AD Trust Relationship Mapping Test",
description="Map AD trust relationships to validate trust-security monitoring and SID-filtering.",
tags=["red-team","discovery","active-directory","trusts"],
risk="low", confirm=False,
blue_kw=["active-directory","trusts","discovery","sid-filtering"],
purpose=("Trusts extend the security boundary — a compromise in one domain flows through trusts. This "
"test maps all trust relationships, their direction and transitivity, and validates SID filtering "
"and trust monitoring."),
when=[
"During AD discovery in multi-domain forests.",
"To validate trust hardening (SID filtering, selective auth).",
"When the threat model includes cross-domain movement.",
],
prereq=[
"Authorization for the forest; standard domain user context suffices.",
],
procedure=[
"Enumerate all trusts: direction, transitivity, type (forest, external, shortcut).",
"Check SID filtering and selective-authentication status per trust.",
"Map the attack paths trusts enable: which principals in trusted domains have rights here?",
"Test trust transitivity assumptions with canary cross-domain access (authorized).",
"Record whether cross-trust authentication is monitored.",
"Deliver the trust-security assessment with filtering recommendations.",
],
outputs=[
"Trust map with direction, transitivity, and filtering status.",
"Cross-trust attack-path analysis.",
"Trust-monitoring findings.",
],
pitfalls=[
"Cross-domain access testing without approval from both domain owners.",
"Assuming external trusts filter SIDs by default — verify.",
],
references=[
"MITRE ATT&CK: Domain Trust Discovery (T1482).",
"Microsoft: trust hardening guidance.",
],
blue_note="their trust architecture is under test — unfiltered trusts are boundary extensions the blue team must monitor.",
),
dict(
slug="sensitive-data-discovery",
title="Sensitive Data Discovery Test",
description="Discover sensitive-data exposure across shares, endpoints, and repos to validate DLP.",
tags=["red-team","discovery","dlp","data"],
risk="low", confirm=False,
blue_kw=["sensitive-data","dlp","discovery","classification"],
purpose=("Attackers hunt data; this test hunts it first — with rules. Canary-pattern scanning across "
"shares, endpoints, and repos validates DLP coverage, data classification, and whether sensitive "
"data lives where it shouldn't."),
when=[
"During discovery phases, as the data-risk complement to share enumeration.",
"To validate DLP rule coverage with canary patterns.",
"Before collection/exfiltration phases, to scope what's actually exposed.",
],
prereq=[
"Authorization with agreed data patterns (canary + pattern types, not real PII harvesting).",
"Sampling depth agreed; DLP team coordination.",
],
procedure=[
"Deploy canary files with known patterns (fake PANs, fake SSNs, canary tokens) across shares and endpoints.",
"Scan the agreed scope for the canary patterns and for real sensitive patterns (counts and locations, not exfiltration).",
"Check whether DLP flagged the canary files — per location and per pattern type.",
"Sample repositories and wikis for secrets (canary tokens planted; real secrets reported as counts).",
"Deliver the data-exposure map with DLP-tuning and classification recommendations.",
],
outputs=[
"Canary-pattern detection results per location.",
"Sensitive-data exposure map (counts and locations).",
"DLP coverage gaps with tuning recommendations.",
],
pitfalls=[
"Exfiltrating real sensitive data 'for proof' — counts and locations, never content.",
"Scanning outside the agreed scope — HR, legal, and exec shares need specific approval.",
"Forgetting that the scan itself must be logged — coordinate with the DLP team.",
],
references=[
"MITRE ATT&CK: Data Discovery; NIST SP 800-60 (data categorization).",
],
blue_note="their DLP and data classification are under test — canary patterns the DLP misses are coverage gaps with locations attached.",
),
dict(
slug="security-tool-discovery",
title="Security Tool Discovery Test",
description="Test security-tooling enumeration to validate tamper protection and deception.",
tags=["red-team","discovery","edr","deception"],
risk="low", confirm=False,
blue_kw=["security-tools","edr","discovery","deception"],
purpose=("Attackers enumerate defenses before evading them. This test performs standard security-"
"tooling discovery — installed EDR, AV, logging agents — and validates tamper protection, "
"uninstallation controls, and whether discovery of defenses is itself detected."),
when=[
"Early in engagements, mirroring attacker reconnaissance.",
"To validate EDR tamper protection and uninstall passwords.",
"To test whether defense-discovery triggers any alert.",
],
prereq=[
"Authorization for the test hosts; read-only enumeration.",
],
procedure=[
"Enumerate installed security products via standard paths (WMI, registry, services, processes).",
"Check tamper protection: can the test context disable or uninstall the agent (attempt the control, don't succeed without approval)?",
"Record whether the enumeration itself generated any telemetry.",
"Test the EDR's self-defense: service stop attempts, driver unload attempts (blocked expected).",
"Deliver the defense-visibility assessment with tamper-protection recommendations.",
],
outputs=[
"Security-product inventory per host.",
"Tamper-protection test results.",
"Defense-discovery telemetry assessment.",
],
pitfalls=[
"Actually disabling protection without approval — attempt-to-control tests need explicit scope.",
"Uninstalling agents even temporarily — that's an availability impact.",
],
references=[
"MITRE ATT&CK: Security Software Discovery (T1518.001).",
],
blue_note="their defense tamper protection is under test — an EDR the test user can disable is a control failure, not a finding to note politely.",
),
dict(
slug="software-inventory-recon",
title="Software Inventory Reconnaissance Test",
description="Enumerate installed software to validate patching and unauthorized-software controls.",
tags=["red-team","discovery","inventory","patching"],
risk="low", confirm=False,
blue_kw=["software","inventory","discovery","patching"],
purpose=("The software inventory is the vulnerability surface made visible. This test enumerates "
"installed software across sampled hosts and validates patch currency, unauthorized software "
"detection, and the accuracy of the asset inventory itself."),
when=[
"During discovery phases.",
"To validate vulnerability-management coverage and software allowlisting.",
"To check the asset inventory's accuracy against ground truth.",
],
prereq=[
"Authorization for the sampled hosts; read-only enumeration.",
"Vulnerability-management team coordination for the patch comparison.",
],
procedure=[
"Enumerate installed software on sampled hosts (registry, WMI, package managers).",
"Compare against the official asset inventory — flag drift (installed but unrecorded).",
"Check patch levels of high-risk software (browsers, runtimes, VPN clients) against known CVEs.",
"Flag unauthorized software per the allowlist policy.",
"Deliver the inventory-accuracy and patch-currency assessment.",
],
outputs=[
"Software inventory per sampled host with drift analysis.",
"Patch-gap findings tied to CVEs.",
"Unauthorized-software findings.",
],
pitfalls=[
"Full-fleet enumeration without sampling approval — sample first, expand if the drift is bad.",
"Flagging portable/approved exceptions as unauthorized — check the exception list.",
],
references=[
"MITRE ATT&CK: Software Discovery (T1518).",
],
blue_note="their asset inventory and patching get ground-truthed — drift between the inventory and reality is the foundational finding.",
),
dict(
slug="user-hunting-test",
title="User Hunting and Session Discovery Test",
description="Test user/session discovery to validate session monitoring and privileged-user hygiene.",
tags=["red-team","discovery","users","sessions"],
risk="low", confirm=False,
blue_kw=["users","sessions","discovery","monitoring"],
purpose=("Knowing who's logged in where tells an attacker where the privileged sessions are. This "
"test performs user and session discovery — logged-on users, RDP sessions, service sessions — and "
"validates whether session enumeration is monitored and privileged sessions are hygienic."),
when=[
"During discovery phases on Windows networks.",
"To validate privileged-session hygiene (no DA sessions on workstations).",
"To test detection of session-enumeration tooling.",
],
prereq=[
"Authorization for the target hosts; standard user context.",
],
procedure=[
"Enumerate logged-on users and sessions on target hosts (qwinsta, net session, PSLoggedOn-style).",
"Map privileged sessions: are Domain Admins logged into workstations or member servers?",
"Check for disconnected RDP sessions holding privileged tokens.",
"Record whether the enumeration tripped any monitoring.",
"Deliver the session-hygiene findings with privileged-access-workstation recommendations.",
],
outputs=[
"Session map with privilege analysis.",
"Privileged-session hygiene findings.",
"Enumeration-detection assessment.",
],
pitfalls=[
"Session enumeration on sensitive hosts (executive, HR) without specific approval.",
"Hijacking disconnected sessions — discovery only, no session takeover without approval.",
],
references=[
"MITRE ATT&CK: System Owner/User Discovery (T1033).",
"Microsoft: privileged access guidance.",
],
blue_note="their privileged-session hygiene is under test — Domain Admin sessions on workstations are the finding that justifies PAWs.",
),
dict(
slug="password-policy-discovery",
title="Password Policy Discovery Test",
description="Discover effective password policy to validate policy enforcement and fine-grained policies.",
tags=["red-team","discovery","password-policy"],
risk="low", confirm=False,
blue_kw=["password-policy","discovery","authentication"],
purpose=("Attackers read the password policy to tune their attacks; defenders should know what's "
"actually enforced. This test discovers the effective policy — domain default, fine-grained, and "
"cloud — and validates it matches the documented standard."),
when=[
"During discovery phases.",
"To validate fine-grained password policies apply where intended.",
"As input to the hash-cracking lab's policy verdict.",
],
prereq=[
"Authorization for the domain; standard user context.",
],
procedure=[
"Read the domain password policy (net accounts /domain, AD module) and all fine-grained policies.",
"Check cloud policy: Azure AD / Entra password protection status and custom banned lists.",
"Verify enforcement matches documentation: test canary accounts against the stated complexity (authorized).",
"Flag discrepancies: documented 14 characters, enforced 8.",
"Deliver the policy-vs-enforcement assessment.",
],
outputs=[
"Effective policy per scope (domain, FGPP, cloud).",
"Documentation-vs-enforcement deltas.",
"Canary enforcement-test results.",
],
pitfalls=[
"Testing enforcement with real user accounts — canary accounts only.",
"Forgetting cloud policy while auditing on-prem — cover both.",
],
references=[
"MITRE ATT&CK: Password Policy Discovery (T1201).",
"NIST SP 800-63B (password guidance).",
],
blue_note="their documented policy vs. enforced reality is compared — deltas are compliance findings with canary proof.",
),
dict(
slug="psexec-lateral-test",
title="PsExec-Style Lateral Movement Test",
description="Test PsExec-style lateral movement to validate SMB and service-creation monitoring.",
tags=["red-team","lateral-movement","psexec","smb"],
risk="moderate", confirm=True,
blue_kw=["psexec","lateral-movement","smb","services"],
purpose=("PsExec-style movement — SMB admin shares plus remote service creation — is the noisiest "
"lateral technique and therefore the detection baseline. This test validates that 7045/4624 "
"telemetry and EDR catch it, establishing the floor every stealthier technique is measured against."),
when=[
"During lateral-movement phases, first technique tested.",
"To establish the detection baseline before stealthier variants.",
"To validate SMB signing and admin-share controls.",
],
prereq=[
"Authorization for lateral movement between the named hosts.",
"Inert remote payload (canary file write on the target).",
],
procedure=[
"Execute PsExec-style movement to the target host with the authorized credential, running an inert canary.",
"Record the full telemetry: 4624 logon type 3, 7045 service creation, SMB sessions, EDR alerts.",
"Test variants: custom service names vs. default, renamed binaries.",
"Verify the canary executed on the target; clean the service and canary.",
"Measure detection latency from service creation to alert.",
"Deliver the lateral-movement baseline: this is the floor.",
],
outputs=[
"PsExec-telemetry record (4624/7045/SMB/EDR).",
"Variant detection comparison.",
"Detection-latency measurement.",
],
pitfalls=[
"Lateral movement outside the named hosts — scope is the authorization.",
"Leaving remote services installed — clean every target.",
"Forgetting the credential used — log which credential moved where.",
],
references=[
"MITRE ATT&CK: Lateral Movement via service execution; PsExec documentation.",
],
blue_note="their lateral-movement detection floor is established here — if PsExec-style movement goes silent, deeper techniques are untestable.",
),
dict(
slug="wmi-lateral-test",
title="WMI Lateral Movement Test",
description="Test WMI-based lateral movement to validate DCOM and WMI operational-log monitoring.",
tags=["red-team","lateral-movement","wmi","dcom"],
risk="moderate", confirm=True,
blue_kw=["wmi","lateral-movement","dcom","monitoring"],
purpose=("WMI lateral movement rides DCOM — no service installation, different telemetry than PsExec. "
"This test validates that WMI operational logs and DCOM monitoring catch remote process creation "
"via Win32_Process."),
when=[
"During lateral-movement phases.",
"To validate WMI operational-log forwarding from all hosts.",
"To compare against the PsExec baseline (different telemetry, different gaps).",
],
prereq=[
"Authorization for lateral movement between the named hosts.",
"Inert remote payload (canary).",
],
procedure=[
"Execute remote process creation via WMI (Win32_Process.Create) on the target with the authorized credential.",
"Record telemetry: WMI operational log events, DCOM 10036-style events, 4624 logons, EDR process-ancestry.",
"Test from non-standard initiators to check ancestry rules.",
"Verify the canary executed; clean all artifacts.",
"Compare detection against the PsExec baseline — which layers fired differently?",
"Deliver the WMI-movement assessment with operational-log recommendations.",
],
outputs=[
"WMI lateral-movement telemetry record.",
"PsExec-vs-WMI detection comparison.",
"Operational-log coverage findings.",
],
pitfalls=[
"Assuming the WMI operational log is forwarded everywhere — verify per host.",
"Lateral movement outside the named hosts.",
],
references=[
"MITRE ATT&CK: Windows Management Instrumentation for lateral movement (T1047).",
],
blue_note="their WMI/DCOM monitoring is measured against the PsExec floor — gaps here are operational-log forwarding failures.",
),
dict(
slug="rdp-lateral-test",
title="RDP Lateral Movement Test",
description="Test RDP-based lateral movement to validate RDP monitoring and session controls.",
tags=["red-team","lateral-movement","rdp"],
risk="moderate", confirm=True,
blue_kw=["rdp","lateral-movement","monitoring","sessions"],
purpose=("RDP is legitimate admin tooling, which makes it ideal cover for lateral movement. This "
"test performs authorized RDP sessions between hosts and validates that RDP logons are monitored, "
"that session hosts are hardened, and that anomalous RDP is distinguishable."),
when=[
"During lateral-movement phases.",
"To validate RDP logon monitoring (4624 type 10) and session-host hardening.",
"To test whether RDP from unusual sources alerts.",
],
prereq=[
"Authorization for RDP between the named hosts; test accounts.",
"RDP session recording/consent per the ROE.",
],
procedure=[
"Establish RDP sessions from authorized sources to target hosts; perform canary actions.",
"Record telemetry: 4624 type 10, RDP session events, EDR logon alerts.",
"Test from an unusual source (as authorized) to check anomaly alerting.",
"Verify NLA, session timeouts, and clipboard/drive-redirection policies on the targets.",
"Close all sessions; verify no disconnected sessions remain.",
"Deliver the RDP-monitoring and hardening assessment.",
],
outputs=[
"RDP telemetry record per session.",
"Anomaly-detection test results.",
"Session-host hardening findings.",
],
pitfalls=[
"Leaving disconnected RDP sessions — verify clean logoff.",
"Drive/clipboard redirection moving test artifacts unexpectedly — check policies first.",
"RDP to sensitive hosts without specific approval.",
],
references=[
"MITRE ATT&CK: Remote Services — Remote Desktop Protocol (T1021.001).",
],
blue_note="their RDP monitoring and session-host hardening are under test — unalerted anomalous RDP is a monitoring gap.",
),
dict(
slug="winrm-lateral-test",
title="WinRM Lateral Movement Test",
description="Test WinRM-based lateral movement to validate WinRM logging and JEA controls.",
tags=["red-team","lateral-movement","winrm","powershell"],
risk="moderate", confirm=True,
blue_kw=["winrm","lateral-movement","powershell","logging"],
purpose=("WinRM is the modern admin remoting — PowerShell remoting rides it. This test validates "
"that WinRM operational logging captures remote commands, and that Just Enough Administration "
"constrains what remote sessions can do."),
when=[
"During lateral-movement phases.",
"To validate PowerShell remoting logging (4103/4104, WinRM operational).",
"To test JEA endpoint constraints.",
],
prereq=[
"Authorization for WinRM remoting between the named hosts.",
"Inert remote commands (canary).",
],
procedure=[
"Execute remote commands via WinRM/PowerShell remoting with the authorized credential; run canary commands.",
"Record telemetry: WinRM operational logs, PowerShell 4103/4104 script-block logging on the target.",
"Test JEA endpoints: what can the constrained session actually do? Attempt boundary escapes (authorized, proof-only).",
"Verify the canary executed; clean artifacts.",
"Deliver the WinRM-logging and JEA assessment.",
],
outputs=[
"WinRM remoting telemetry record.",
"JEA constraint test results.",
"Script-block logging coverage findings.",
],
pitfalls=[
"JEA escape attempts beyond proof-of-concept without approval.",
"Assuming 4104 logging is on everywhere — verify per host.",
],
references=[
"MITRE ATT&CK: Remote Services — Windows Remote Management (T1021.006).",
"Microsoft: JEA documentation.",
],
blue_note="their WinRM logging and JEA constraints are under test — unconstrained remoting with silent script blocks is a double gap.",
),
dict(
slug="ssh-lateral-test",
title="SSH Lateral Movement Test",
description="Test SSH-based lateral movement to validate Linux authentication monitoring.",
tags=["red-team","lateral-movement","ssh","linux"],
risk="moderate", confirm=True,
blue_kw=["ssh","lateral-movement","linux","monitoring"],
purpose=("SSH is the Linux lateral-movement plane. This test moves between Linux hosts via SSH with "
"authorized keys and passwords, validating auth.log monitoring, key hygiene, and whether lateral "
"SSH is distinguishable from admin SSH."),
when=[
"During lateral-movement phases on Linux estates.",
"To validate SSH authentication monitoring and alerting.",
"To audit authorized_keys hygiene across hosts.",
],
prereq=[
"Authorization for SSH movement between the named hosts.",
"Test keys; canary commands.",
],
procedure=[
"Move between hosts via SSH with authorized test keys; run canary commands.",
"Test password auth where enabled (authorized) — record the difference in telemetry.",
"Audit authorized_keys files on the targets for stale/unknown keys.",
"Record telemetry: auth.log entries, SIEM SSH alerts, EDR process ancestry.",
"Test SSH agent forwarding abuse paths (authorized, proof-only) and note the risk.",
"Remove test keys; verify authorized_keys matches baseline.",
"Deliver the SSH-monitoring and key-hygiene assessment.",
],
outputs=[
"SSH movement telemetry record.",
"authorized_keys hygiene findings.",
"Agent-forwarding risk notes.",
],
pitfalls=[
"Leaving test keys in authorized_keys — verify removal per host.",
"Agent forwarding with real keys — test keys only.",
"Password-auth testing without approval where policy disables it.",
],
references=[
"MITRE ATT&CK: Remote Services — SSH (T1021.004).",
],
blue_note="their Linux authentication monitoring and key hygiene are under test — stale authorized_keys are persistent access the blue team forgot.",
),
dict(
slug="pass-the-hash-test",
title="Pass-the-Hash Test",
description="Test pass-the-hash lateral movement to validate NTLM monitoring and credential hygiene.",
tags=["red-team","lateral-movement","pass-the-hash","ntlm"],
risk="high", confirm=True,
blue_kw=["pass-the-hash","ntlm","lateral-movement","monitoring"],
purpose=("Pass-the-hash moves laterally with a hash instead of a password — no cracking needed. This "
"test validates NTLM auditing, signs of PtH (logon type 3 with NTLM, missing 4624/4648 pairs), and "
"whether Credential Guard blocks it."),
when=[
"During lateral-movement phases on Windows.",
"To validate NTLM monitoring and the case for NTLM restriction.",
"To test Credential Guard effectiveness.",
],
prereq=[
"Authorization for hash-based authentication; hashes handled per the credential ROE.",
"Explicit approval for the hash source (canary account or authorized extraction).",
],
procedure=[
"With the authorized NTLM hash, authenticate to the target host (SMB/WMI) without the password.",
"Record telemetry: 4624 type 3, NTLM audit events, EDR alerts — and the PtH indicators.",
"Test with Credential Guard enabled vs. disabled (lab) to show the control's effect.",
"Verify the canary action on the target; clean artifacts.",
"Destroy hash material per the ROE after the test.",
"Deliver the PtH assessment with NTLM-restriction recommendations.",
],
outputs=[
"PtH telemetry record with indicator analysis.",
"Credential Guard effectiveness comparison.",
"Hash-material destruction log.",
],
pitfalls=[
"Hash material lingering after the test — destroy per the ROE.",
"Testing with Domain Admin hashes without specific approval — canary accounts first.",
"Confusing PtH with overpass-the-hash — test and report separately.",
],
references=[
"MITRE ATT&CK: Use Alternate Authentication Material — Pass the Hash (T1550.002).",
],
blue_note="their NTLM monitoring and credential hygiene are under test — silent PtH is the evidence for NTLM auditing and restriction.",
),
dict(
slug="pass-the-ticket-test",
title="Pass-the-Ticket Test",
description="Test pass-the-ticket lateral movement to validate Kerberos monitoring.",
tags=["red-team","lateral-movement","kerberos","pass-the-ticket"],
risk="high", confirm=True,
blue_kw=["pass-the-ticket","kerberos","lateral-movement","monitoring"],
purpose=("Pass-the-ticket replays stolen Kerberos tickets for lateral movement that looks like normal "
"Kerberos. This test validates whether ticket replay — especially across hosts — is distinguishable "
"in the monitoring."),
when=[
"During lateral-movement phases in AD environments.",
"To validate Kerberos service-ticket monitoring.",
"Paired with the overpass-the-hash test for the full ticket-attack picture.",
],
prereq=[
"Authorization for ticket operations; ticket material handled per the ROE.",
"Canary service tickets where possible.",
],
procedure=[
"Export a canary service ticket from the source context (authorized).",
"Inject the ticket into a fresh logon session on the test host and access the target resource.",
"Record telemetry: 4624/4634 pairs, Kerberos service-ticket events, EDR alerts.",
"Test cross-host replay: does the ticket work from an unexpected host, and does anything flag it?",
"Test the overpass-the-hash variant (NTLM hash → Kerberos tickets) as a separate case.",
"Destroy all ticket material; verify no test tickets remain valid.",
"Deliver the ticket-replay assessment with Kerberos-monitoring recommendations.",
],
outputs=[
"Ticket-replay telemetry record.",
"Cross-host replay detection results.",
"Overpass-the-hash comparison.",
],
pitfalls=[
"Ticket material lingering — destroy per the ROE.",
"Real user TGTs without approval — canary tickets first.",
"Forgetting that ticket lifetime bounds the test window — plan accordingly.",
],
references=[
"MITRE ATT&CK: Use Alternate Authentication Material — Pass the Ticket (T1550.003).",
],
blue_note="their Kerberos monitoring is under test — ticket replay that looks like normal auth is the detection challenge to solve.",
),
dict(
slug="ad-replication-abuse",
title="AD Replication Abuse Test",
description="Test malicious DC promotion and replication abuse to validate DC-security monitoring.",
tags=["red-team","lateral-movement","active-directory","replication"],
risk="high", confirm=True,
blue_kw=["active-directory","replication","domain-controller","monitoring"],
purpose=("Rogue DC promotion (DCShadow) and replication abuse give attackers directory-write "
"primitives. This lab test validates DC-promotion monitoring and that replication-based attacks "
"are detectable — without endangering production AD."),
when=[
"Lab-only, during advanced AD phases.",
"To validate monitoring for unauthorized DC promotions.",
"To test SIEM rules for replication anomalies.",
],
prereq=[
"Isolated lab forest; explicit authorization for DC-promotion techniques.",
"Never against production AD.",
],
procedure=[
"In the lab, register a rogue DC (DCShadow-style) and push a canary directory change.",
"Record telemetry: DC-promotion events, replication anomalies, and SIEM alerts.",
"Test the reverse: unauthorized replication-partner additions.",
"Verify the lab forest is clean afterward (metadata cleanup of the rogue DC).",
"Deliver the DC-security monitoring assessment with promotion-alerting recommendations.",
],
outputs=[
"Rogue-DC telemetry record.",
"Replication-anomaly detection results.",
"Lab cleanup verification.",
],
pitfalls=[
"Any production AD contact — lab only, enforced.",
"Leaving rogue-DC metadata in the lab forest — clean it.",
"Confusing lab replication with the DCSync test — related but distinct techniques.",
],
references=[
"MITRE ATT&CK: Domain Controller artifacts; public DCShadow research.",
],
blue_note="their DC-promotion monitoring is under test — an unalerted rogue DC is a forest-security failure.",
),
dict(
slug="cloud-lateral-test",
title="Cloud Lateral Movement Test",
description="Test cloud role-assumption and lateral movement to validate CloudTrail and permission boundaries.",
tags=["red-team","lateral-movement","cloud","iam"],
risk="moderate", confirm=True,
blue_kw=["cloud","lateral-movement","iam","cloudtrail"],
purpose=("In cloud, lateral movement is role assumption and permission pivoting — no SMB needed. This "
"test chains assumable roles and cross-account trust with a low-privilege start, validating "
"permission boundaries and CloudTrail alerting on anomalous role use."),
when=[
"During cloud phases.",
"To validate IAM permission boundaries and trust policies.",
"To test CloudTrail alerting on role-assumption anomalies.",
],
prereq=[
"Authorization for the cloud accounts; low-privilege test role as the start.",
"Agreement on which roles may be assumed (canary roles preferred).",
],
procedure=[
"From the start role, enumerate assumable roles and cross-account trusts.",
"Assume roles along the authorized chain; at each step record effective permissions and CloudTrail events.",
"Test for confused-deputy and external-ID weaknesses in trust policies (proof-only).",
"Attempt the canary objective (read a canary-flagged resource) via the role chain.",
"Record whether anomalous role assumption alerted.",
"Deliver the cloud permission-boundary assessment with trust-policy fixes.",
],
outputs=[
"Role-assumption chain with per-step permissions.",
"CloudTrail anomaly-alerting results.",
"Trust-policy findings.",
],
pitfalls=[
"Assuming roles outside the agreed chain — scope strictly.",
"Exploiting confused-deputy beyond proof — note, don't exploit.",
"Forgetting that CloudTrail must be enabled in all regions — verify.",
],
references=[
"MITRE ATT&CK: Valid Accounts — Cloud Accounts (T1078.004).",
],
blue_note="their cloud permission boundaries are under test — role chains that reach further than intended are IAM findings.",
),
dict(
slug="supply-chain-vector-test",
title="Supply-Chain Vector Validation Test",
description="Validate software-supply-chain attack vectors to test update-integrity and vendor-risk controls.",
tags=["red-team","lateral-movement","supply-chain"],
risk="high", confirm=True,
blue_kw=["supply-chain","updates","integrity","vendor-risk"],
purpose=("Supply-chain attacks move laterally through trusted updates. This test validates the "
"controls around software updates — signature verification, update-channel integrity, and vendor-"
"risk processes — using canary update scenarios, never real trojanized software."),
when=[
"During advanced phases, with explicit supply-chain authorization.",
"To validate update-signature verification and channel security.",
"To test vendor-risk assessment processes.",
],
prereq=[
"Explicit authorization for supply-chain scenarios; canary updates only.",
"Update-infrastructure team coordination.",
],
procedure=[
"Map the update channels: which software auto-updates, from where, with what verification?",
"Test signature verification: does the updater reject a canary unsigned/modified package?",
"Simulate a canary malicious update through the test channel (authorized) and measure detection.",
"Audit vendor access: which vendors have direct update or remote-access paths?",
"Deliver the supply-chain integrity assessment with verification and vendor-risk recommendations.",
],
outputs=[
"Update-channel map with verification status.",
"Canary update-test results.",
"Vendor-access audit.",
],
pitfalls=[
"Real trojanized updates — canary scenarios only, never production update channels.",
"Testing vendor paths without the vendor-relationship owner's coordination.",
],
references=[
"MITRE ATT&CK: Supply Chain Compromise (T1195).",
],
blue_note="their update-integrity controls are under test — updaters that accept unsigned packages are a supply-chain gap.",
),
]
