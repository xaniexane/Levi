# Red team topics — chunk 3: persistence (10) + privilege escalation (10)

RED_3 = [
dict(
slug="registry-run-keys",
title="Registry Run Key Persistence Test",
description="Test registry run-key persistence mechanisms to validate autostart monitoring and EDR coverage.",
tags=["red-team","persistence","registry","windows"],
risk="moderate", confirm=True,
blue_kw=["registry","persistence","autostart","run-keys"],
purpose=("Registry run keys are the oldest persistence trick on Windows and still effective. Testing "
"them validates autostart-entry monitoring (Sysmon Event 13, EDR) and the blue team's ability to "
"distinguish legitimate software autostarts from attacker persistence."),
when=[
"During persistence phases on Windows hosts.",
"To validate Sysmon registry-event coverage and EDR autostart rules.",
"As a baseline persistence test before exotic mechanisms.",
],
prereq=[
"Authorization for persistence testing with defined dwell time and cleanup.",
"Registry baseline of the target hosts to distinguish test entries.",
],
procedure=[
"Create run-key entries (HKCU/HKLM Run, RunOnce) pointing at an inert canary executable; log exact keys and values.",
"Reboot or log off/on the target as authorized and verify the canary executed (canary file timestamp).",
"Record the telemetry: Sysmon 13 registry events, EDR autostart alerts, and whether the value data was inspected.",
"Test variations: RunOnceEx, Wow6432Node redirection, and run-key-adjacent locations (AppInit_DLLs concepts where authorized).",
"Measure detection latency from creation to alert.",
"Remove all test entries at phase end and verify removal events fired.",
"Deliver the autostart-monitoring assessment with Sysmon config recommendations.",
],
outputs=[
"Per-location creation/detection matrix.",
"Persistence-verification evidence (canary execution).",
"Cleanup verification with removal telemetry.",
],
pitfalls=[
"Leaving run keys behind — cleanup is part of the test.",
"Testing HKLM keys without authorization for the privilege level.",
"Forgetting Wow6432Node — 32-bit views hide entries from naive checks.",
],
references=[
"MITRE ATT&CK: Boot or Logon Autostart Execution — Registry Run Keys (T1547.001).",
],
blue_note="their autostart monitoring (Sysmon 13, EDR) faces the most basic persistence there is — silent run keys are a foundational visibility gap.",
),
dict(
slug="scheduled-task-persistence",
title="Scheduled Task Persistence Test",
description="Test scheduled-task persistence with hidden and SYSTEM-level tasks to validate task auditing.",
tags=["red-team","persistence","scheduled-tasks"],
risk="moderate", confirm=True,
blue_kw=["scheduled-tasks","persistence","auditing"],
purpose=("Scheduled tasks double as execution and persistence. This test creates tasks designed to "
"persist — hidden, SYSTEM-level, with triggers on idle/logon — and measures whether task auditing "
"(4698/4702) and EDR catch them, including the stealthier variants."),
when=[
"During persistence phases, after basic execution tests pass.",
"To validate that scheduled-task auditing covers hidden and privileged tasks.",
],
prereq=[
"Authorization for persistence with dwell time and cleanup defined.",
"Task names uniquely identifying the test (e.g., prefix with the exercise codename).",
],
procedure=[
"Create persistence tasks: daily trigger, on-logon trigger, and on-idle trigger, each running an inert canary.",
"Test the hidden attribute and SYSTEM principal variants where authorized.",
"Verify persistence across reboot and user logon/logoff cycles.",
"Record telemetry per variant: 4698/4702 events, EDR alerts, and whether hidden tasks were surfaced in audits.",
"Test task modification (changing the action post-creation) and record 4702 update events.",
"Delete all test tasks; verify 4699 deletion events and that no artifacts remain.",
],
outputs=[
"Per-variant persistence/detection matrix.",
"Reboot/logon verification evidence.",
"Cleanup verification.",
],
pitfalls=[
"Hidden tasks forgotten at cleanup — enumerate tasks programmatically at phase end.",
"SYSTEM-level tasks without explicit privilege authorization.",
"Trigger conditions that fire during business hours and confuse users — schedule off-hours.",
],
references=[
"MITRE ATT&CK: Scheduled Task (T1053.005).",
],
blue_note="their task-auditing GPOs face stealthy variants here — hidden or SYSTEM tasks that go unlogged are audit-policy failures.",
),
dict(
slug="service-persistence",
title="Windows Service Persistence Test",
description="Test service-based persistence to validate service-installation monitoring (event 7045).",
tags=["red-team","persistence","services"],
risk="moderate", confirm=True,
blue_kw=["services","persistence","7045","monitoring"],
purpose=("Malicious services persist with SYSTEM privileges and blend into legitimate service noise. "
"Testing service-based persistence validates 7045 service-install logging, binary-path auditing, "
"and the blue team's service-baseline discipline."),
when=[
"During persistence phases requiring privileged persistence.",
"To validate service-installation monitoring and allowlisted service baselines.",
],
prereq=[
"Authorization for service installation with the privilege level specified.",
"Service binary inert (canary writer); service names exercise-prefixed.",
],
procedure=[
"Install a test service with an inert binary via sc.exe; set it to auto-start.",
"Record 7045 events: service name, binary path, account, and start type.",
"Test recovery-action abuse: configure the service to run a canary on failure.",
"Verify persistence across reboots; confirm the canary executed.",
"Check whether the blue team's service baseline flagged the new service or it blended in.",
"Remove the service and binary; verify 7045-adjacent removal evidence and clean state.",
],
outputs=[
"Service-install telemetry record with 7045 details.",
"Baseline-blending assessment (was the new service noticed?).",
"Cleanup verification.",
],
pitfalls=[
"Service binaries left on disk after service removal — clean both.",
"Testing on domain controllers or critical servers without specific approval.",
"Recovery-action payloads that loop and destabilize the host — keep canaries single-shot.",
],
references=[
"MITRE ATT&CK: System Services — Service Execution (T1569.002).",
],
blue_note="their service-install monitoring and baseline discipline are under test — a new SYSTEM service nobody noticed is a visibility failure.",
),
dict(
slug="wmi-event-subscription",
title="WMI Event Subscription Persistence Test",
description="Test fileless WMI event-subscription persistence to validate WMI auditing and EDR coverage.",
tags=["red-team","persistence","wmi","fileless"],
risk="moderate", confirm=True,
blue_kw=["wmi","persistence","event-subscription","fileless"],
purpose=("WMI event subscriptions persist without files — a filter, a consumer, and a binding, all in "
"the WMI repository. This test validates that WMI auditing (5857-5861 events) and EDR detect "
"subscription creation, the classic fileless persistence defenders most often miss."),
when=[
"During persistence phases testing fileless techniques.",
"To validate WMI operational-log auditing is enabled and forwarded.",
"When the threat model includes advanced persistent threats.",
],
prereq=[
"Authorization for WMI persistence with dwell time and cleanup.",
"WMI operational log auditing confirmed as a prerequisite check — the test also validates it's on.",
],
procedure=[
"Create an __EventFilter (e.g., timer or logon event), a CommandLineEventConsumer running an inert canary, and the __FilterToConsumerBinding.",
"Verify the consumer fires on the trigger event (canary evidence).",
"Record telemetry: WMI operational log events, Sysmon/EDR alerts, and whether the subscription was visible in standard admin tooling.",
"Test persistence across reboots (WMI repository survives).",
"Remove filter, consumer, and binding; verify the repository is clean via enumeration.",
"Deliver the WMI-auditing assessment with enablement guidance for the operational log.",
],
outputs=[
"WMI subscription creation/detection matrix.",
"Trigger-verification evidence.",
"Repository-cleanup verification.",
],
pitfalls=[
"Orphaned consumers or bindings after cleanup — enumerate all three classes at phase end.",
"Assuming the WMI operational log is enabled — verify; its absence is itself a finding.",
"Timer-interval triggers that fire too often and create noise — use sparse intervals.",
],
references=[
"MITRE ATT&CK: WMI Event Subscription (T1546.003).",
],
blue_note="their WMI operational-log auditing is usually the gap this test exposes — no 5857-5861 events means fileless persistence is invisible.",
),
dict(
slug="startup-folder-persistence",
title="Startup Folder Persistence Test",
description="Test startup-folder persistence (including LNK abuse) to validate file-monitoring and user-awareness controls.",
tags=["red-team","persistence","startup-folder"],
risk="moderate", confirm=True,
blue_kw=["startup","persistence","lnk","autostart"],
purpose=("The startup folder is the simplest user-level persistence: drop a shortcut, wait for logon. "
"Testing it validates file-integrity monitoring of autostart locations and whether users notice or "
"report unexpected startup items."),
when=[
"During persistence phases on user workstations.",
"To validate FIM coverage of per-user autostart paths.",
"Combined with the removable-media test for a full user-vector exercise.",
],
prereq=[
"Authorization for the target workstations; user notification plan per the ROE.",
"Inert LNK/shortcut payloads only.",
],
procedure=[
"Place an inert shortcut in the user's startup folder pointing at a canary executable.",
"Test LNK argument abuse: shortcut with hidden-window arguments and icon spoofing.",
"Log off/on and verify the canary executed.",
"Record telemetry: FIM alerts on the startup folder, EDR process-ancestry (explorer.exe → canary).",
"Check whether the user noticed or reported the new startup item.",
"Remove the shortcut and canary; verify the folder is clean.",
],
outputs=[
"Startup-folder detection matrix (FIM, EDR, user report).",
"Execution-verification evidence.",
"Cleanup verification.",
],
pitfalls=[
"Placing items in all-users startup without authorization for the privilege level.",
"Icon-spoofed LNKs that users can't distinguish — that's the point of the test, but debrief affected users.",
"Forgetting the registry-run-key overlap — test locations independently for clean telemetry.",
],
references=[
"MITRE ATT&CK: Boot or Logon Autostart Execution — Shortcut Modification (T1547.009).",
],
blue_note="their FIM coverage of autostart locations and user reporting both get tested — silent persistence here is a monitoring and awareness gap.",
),
dict(
slug="dll-hijacking-test",
title="DLL Hijacking Test",
description="Test DLL search-order hijacking in a lab to validate application directory permissions and monitoring.",
tags=["red-team","persistence","dll-hijacking","lab"],
risk="moderate", confirm=True,
blue_kw=["dll","hijacking","search-order","permissions"],
purpose=("Applications that load DLLs from writable directories can be hijacked: place a malicious DLL "
"earlier in the search order and it executes with the application's privileges. This lab test "
"identifies hijackable applications and validates directory-permission hardening."),
when=[
"During persistence/privesc phases, lab-first.",
"To validate that application directories are not user-writable.",
"To test EDR detection of sideloaded DLL loads.",
],
prereq=[
"Lab authorization; identify candidate applications with writable install directories.",
"Inert DLLs only (canary MessageBox or file write).",
],
procedure=[
"Enumerate applications with missing DLLs (procmon-style missing-DLL profiling) or writable application directories.",
"Check directory permissions: is the application folder writable by the test user?",
"Place an inert hijack DLL in the search-order position and launch the application; verify the canary executed.",
"Record EDR telemetry: was the sideloaded DLL load flagged (image-load events)?",
"Test the phantom-DLL variant (DLL named for a non-existent import) vs. search-order variant.",
"Remediate in the report: directory ACL fixes per application; re-test to confirm.",
],
outputs=[
"Hijackable-application list with permission evidence.",
"EDR image-load detection matrix.",
"Remediation verification (re-test after ACL fixes).",
],
pitfalls=[
"Real malicious DLLs — inert canaries only.",
"Hijacking system applications without authorization for the blast radius.",
"Forgetting that installers/updates reset directory permissions — note in the report.",
],
references=[
"MITRE ATT&CK: Hijack Execution Flow — DLL Search Order Hijacking (T1574.001).",
],
blue_note="their application-directory ACLs and EDR image-load monitoring are under test — writable app directories are a hardening finding on their own.",
),
dict(
slug="browser-extension-persistence",
title="Browser Extension Persistence Test",
description="Test malicious browser extension persistence to validate extension allowlisting and review processes.",
tags=["red-team","persistence","browser","extensions"],
risk="moderate", confirm=True,
blue_kw=["browser","extensions","persistence","allowlist"],
purpose=("Browser extensions run with broad permissions and persist across sessions — a malicious or "
"compromised extension is durable access to everything the user does in the browser. This test "
"measures extension allowlisting enforcement and the review process for new extensions."),
when=[
"When the org allows browser extensions without centralized control.",
"To validate extension allowlist GPOs actually block unapproved installs.",
"As part of the user-workstation persistence phase.",
],
prereq=[
"Authorization for extension installation on test workstations.",
"Inert extension: canary beacon on install, no data collection.",
"Browser inventory: which browsers and extension policies are deployed.",
],
procedure=[
"Build an inert test extension requesting broad permissions (tabs, cookies) with a canary install beacon.",
"Attempt installation via the web store, sideloading, and enterprise policy paths.",
"Record which paths the allowlist blocked and which succeeded.",
"For successful installs, verify persistence across browser restarts and the canary beacon.",
"Test whether the EDR or browser management console flagged the new extension.",
"Remove the extension from all test workstations; verify removal.",
"Deliver the extension-control assessment with allowlist policy recommendations.",
],
outputs=[
"Per-install-path block/allow matrix.",
"Persistence-verification evidence.",
"Extension inventory vs. allowlist delta.",
],
pitfalls=[
"Extensions that phone home with real browsing data — inert canary beacons only.",
"Testing on users' primary profiles without consent — use test profiles.",
"Forgetting mobile browsers if the fleet includes them.",
],
references=[
"MITRE ATT&CK: Browser Extensions (T1176).",
"Browser enterprise policy documentation (Chrome/Edge extension allowlisting).",
],
blue_note="their extension allowlist and review process are under test — unapproved extensions installing silently is a policy-enforcement failure.",
),
dict(
slug="cloud-oauth-app-persistence",
title="Cloud OAuth App Persistence Test",
description="Test malicious OAuth application grants as cloud persistence to validate app-consent monitoring.",
tags=["red-team","persistence","cloud","oauth"],
risk="high", confirm=True,
blue_kw=["oauth","cloud","persistence","consent"],
purpose=("In cloud environments, persistence isn't a registry key — it's an OAuth grant. A malicious "
"app registration with Mail.Read or full mailbox permissions persists independently of passwords "
"and MFA. This test measures whether app-consent grants are monitored and whether malicious apps "
"would be noticed."),
when=[
"During cloud persistence phases (M365, Google Workspace).",
"To validate OAuth app governance: who can consent, and what gets flagged.",
"After phishing tests, as the 'what if they consented' follow-on.",
],
prereq=[
"Explicit authorization for OAuth app registration in the tenant; test tenant preferred.",
"Agreement on permission scope ceiling for the test app (read-only, canary data).",
],
procedure=[
"Register a test OAuth application with attention-grabbing but in-test naming; request the authorized permission set.",
"Complete the consent flow as the test user; record whether admin consent workflow triggered or user consent sufficed.",
"Verify persistence: revoke the user's password session and confirm the app grant still provides access (to canary data only).",
"Monitor the blue-team side: did app-registration or consent-grant alerts fire? How fast?",
"Enumerate existing third-party app grants in the tenant as a bonus finding — stale grants are the real-world version of this test.",
"Delete the test app and revoke all grants; verify removal in audit logs.",
],
outputs=[
"Consent-flow control assessment (user vs. admin consent).",
"App-registration detection timeline.",
"Stale third-party grant inventory (bonus finding).",
"Cleanup verification with audit-log evidence.",
],
pitfalls=[
"Requesting excessive permissions 'for realism' — stay within the agreed ceiling.",
"Testing in the production tenant without explicit approval — prefer the test tenant.",
"Leaving the app registered — revocation is verified, not assumed.",
],
references=[
"MITRE ATT&CK: Valid Accounts — Cloud Accounts (T1078.004); OAuth abuse literature (public).",
],
blue_note="their OAuth app governance and consent-grant monitoring are under test — unalerted app registrations are an identity-governance gap.",
),
dict(
slug="linux-systemd-persistence",
title="Linux systemd Persistence Test",
description="Test systemd service and timer persistence on Linux hosts to validate Linux autostart monitoring.",
tags=["red-team","persistence","linux","systemd"],
risk="moderate", confirm=True,
blue_kw=["linux","systemd","persistence","timer"],
purpose=("On modern Linux, persistence means systemd: services, timers, and user units. This test "
"validates that Linux hosts have the equivalent of Windows autostart monitoring — unit-file "
"integrity checks, timer auditing, and EDR coverage of systemd-spawned processes."),
when=[
"During persistence phases on Linux estates.",
"To validate that Linux hardening baselines cover systemd persistence.",
"When the threat model includes Linux servers and cloud VMs.",
],
prereq=[
"Authorization for the Linux hosts; root-level persistence needs explicit privilege approval.",
"Inert unit payloads (canary file writes).",
],
procedure=[
"Create a systemd service unit and a timer unit running an inert canary; enable them.",
"Test user-level units (~/.config/systemd/user) vs. system units — different visibility, different controls.",
"Verify persistence across reboots and timer firings.",
"Record telemetry: auditd unit-file watches, EDR alerts, and journal entries.",
"Check for monitoring of the unit directories (/etc/systemd/system, user paths) via FIM or auditd.",
"Remove all units, reload the daemon, and verify clean state.",
],
outputs=[
"Per-unit-type persistence/detection matrix.",
"Reboot/timer verification evidence.",
"Cleanup verification.",
],
pitfalls=[
"System units without root authorization — match the privilege to the approval.",
"Timer units with aggressive schedules creating noise — use sparse schedules.",
"Forgetting user units, which survive in user sessions and are less monitored.",
],
references=[
"MITRE ATT&CK: Systemd Service (T1543.002).",
],
blue_note="their Linux monitoring often lags Windows — silent systemd persistence is the finding that justifies Linux EDR and auditd baselines.",
),
dict(
slug="golden-ticket-persistence",
title="Golden Ticket Persistence Test",
description="Test Kerberos golden-ticket forgery in a lab to validate KRBTGT rotation and ticket monitoring.",
tags=["red-team","persistence","kerberos","active-directory","lab"],
risk="high", confirm=True,
blue_kw=["kerberos","golden-ticket","krbtgt","active-directory"],
purpose=("A golden ticket — a forged Kerberos TGT signed with the KRBTGT hash — persists until the "
"KRBTGT password is rotated twice, surviving password changes. This lab test validates KRBTGT "
"rotation hygiene and ticket-anomaly monitoring without endangering a production domain."),
when=[
"Lab-only, during AD persistence phases.",
"To validate KRBTGT rotation policy (twice, with replication wait).",
"To test SIEM rules for ticket anomalies (lifetime, encryption type).",
],
prereq=[
"Isolated lab domain; never a production AD.",
"KRBTGT hash obtained in the lab under authorization.",
],
procedure=[
"Extract the KRBTGT hash in the lab domain using authorized tooling.",
"Forge a golden ticket with an anomalous lifetime (e.g., 10 years) for a test account.",
"Use the ticket to access a lab resource; record success.",
"Check blue-team detection: ticket-lifetime anomalies, RC4 vs. AES encryption downgrades, and logon without prior AS-REQ.",
"Rotate the KRBTGT password twice (with replication wait) and verify the forged ticket stops working.",
"Deliver the KRBTGT-hygiene assessment with rotation runbook recommendations.",
],
outputs=[
"Forged-ticket usage evidence with anomaly markers.",
"Detection assessment per anomaly type.",
"KRBTGT double-rotation verification.",
],
pitfalls=[
"Any contact with production AD — lab only, no exceptions.",
"Single KRBTGT rotation presented as remediation — it must be twice.",
"Forgetting that golden tickets bypass smart-card requirements — note the implication.",
],
references=[
"MITRE ATT&CK: Steal or Forge Kerberos Tickets — Golden Ticket (T1558.001).",
"Microsoft: KRBTGT reset guidance.",
],
blue_note="their KRBTGT rotation hygiene and Kerberos anomaly monitoring are under test — unalerted decade-long tickets are an AD-monitoring failure.",
),
dict(
slug="unquoted-service-path",
title="Unquoted Service Path Escalation Test",
description="Test unquoted service paths for privilege escalation to validate service-configuration auditing.",
tags=["red-team","privilege-escalation","windows","services"],
risk="moderate", confirm=True,
blue_kw=["service","unquoted","privilege-escalation","permissions"],
purpose=("Services with unquoted binary paths containing spaces can be hijacked by planting an "
"executable earlier in the path — running as SYSTEM on restart. This test finds such services and "
"validates that service-configuration auditing would catch the exploitation."),
when=[
"During Windows privilege-escalation phases.",
"To validate service binary-path quoting across the fleet.",
"As a low-noise privesc test before noisier techniques.",
],
prereq=[
"Authorization for privilege escalation on the targets.",
"Write access to the hijack location confirmed as part of the test (that's the vulnerability).",
],
procedure=[
"Enumerate services with unquoted paths containing spaces (`wmic service get name,pathname` filtered).",
"For each candidate, check write permissions on each path component — only writable components are exploitable.",
"Plant an inert executable at the hijackable path location.",
"Restart the service (as authorized) and verify the canary executed as SYSTEM.",
"Record telemetry: service-control events, process ancestry (services.exe → canary as SYSTEM).",
"Remove the planted binary; recommend quoting fixes per service.",
],
outputs=[
"Exploitable unquoted-path services with permission evidence.",
"SYSTEM-execution proof (canary).",
"Per-service remediation (quoted paths).",
],
pitfalls=[
"Restarting critical services without a maintenance window — coordinate.",
"Planting in system directories without explicit authorization for the location.",
"Missing the secondary path components — check every space-separated segment.",
],
references=[
"MITRE ATT&CK: Hijack Execution Flow — Path Interception by Unquoted Path (T1574.009).",
],
blue_note="their service-configuration baseline should have no unquoted paths — each one found is a hardening gap with a one-line fix.",
),
dict(
slug="token-impersonation",
title="Token Impersonation Test",
description="Test token impersonation and potato-family escalation paths in a lab to validate token monitoring.",
tags=["red-team","privilege-escalation","tokens","windows","lab"],
risk="high", confirm=True,
blue_kw=["token","impersonation","potato","privilege-escalation"],
purpose=("Windows access tokens can be stolen and impersonated; the 'potato' family chains this with "
"DCOM/NtLM quirks into SYSTEM. This lab test validates token-theft monitoring and whether the "
"specific potato prerequisites (SeImpersonatePrivilege) are even present in the environment."),
when=[
"Lab-first, during Windows privilege-escalation phases.",
"To validate that service accounts hold only the privileges they need.",
"To test EDR detection of token-manipulation APIs.",
],
prereq=[
"Lab authorization; production only with explicit approval and a maintenance window.",
"Inert proof goals (whoami / privileges output), never destructive.",
],
procedure=[
"Enumerate privileges of the test context (`whoami /priv`); confirm SeImpersonatePrivilege or SeAssignPrimaryTokenPrivilege is present.",
"In the lab, execute the potato-chain variant matching the OS version; capture the SYSTEM token.",
"Verify escalation with inert proof (privilege listing as SYSTEM).",
"Record EDR telemetry: which API calls (DuplicateToken, ImpersonateLoggedOnUser) were flagged.",
"Test the mitigation: remove SeImpersonatePrivilege from the service account and re-run to prove the chain breaks.",
"Deliver the privilege-hygiene findings: which accounts hold dangerous privileges unnecessarily.",
],
outputs=[
"Token-impersonation feasibility per OS/service-account combination.",
"EDR API-monitoring assessment.",
"Privilege-reduction verification (re-test after hardening).",
],
pitfalls=[
"Running potato exploits against production without a window — they can crash hosts.",
"Assuming all potato variants work everywhere — match the variant to the OS build in the lab first.",
"Forgetting the mitigation test — proving the fix works is half the finding.",
],
references=[
"MITRE ATT&CK: Access Token Manipulation (T1134).",
"Public potato-family research (Google Project Zero et al.).",
],
blue_note="their service-account privilege hygiene is the real finding — SeImpersonatePrivilege on web-facing service accounts is the gap, the exploit is just the proof.",
),
dict(
slug="kernel-exploit-lab",
title="Kernel Exploit Test (Lab Only)",
description="Test kernel privilege-escalation exploits in an isolated lab to validate patching cadence.",
tags=["red-team","privilege-escalation","kernel","lab"],
risk="high", confirm=True,
blue_kw=["kernel","exploit","privilege-escalation","patching"],
purpose=("Unpatched kernels fall to public exploits. This strictly-lab test runs version-appropriate "
"kernel exploits against unpatched lab VMs to prove the patching gap — then validates that patched "
"VMs resist. The lab result becomes the patching-SLA evidence."),
when=[
"Lab-only, when vulnerability scans show missing kernel patches.",
"To turn 'patch missing' into 'exploit proven' for prioritization.",
"Never against production — the lab mirrors production patch levels.",
],
prereq=[
"Isolated lab with VMs at the exact production patch levels.",
"Explicit authorization for kernel-exploit execution in the lab.",
],
procedure=[
"Build lab VMs matching production OS builds and patch levels (patched and unpatched pairs).",
"Select public kernel exploits matching the unpatched builds; review the exploit code before running (no blind execution).",
"Execute against the unpatched VM; verify SYSTEM/root with inert proof.",
"Execute the same exploit against the patched VM; verify it fails.",
"Record EDR behavior on both: did anything fire during successful exploitation?",
"Deliver the patching-gap report: vulnerable build → exploit proof → patched verification.",
],
outputs=[
"Per-build exploit success/failure matrix.",
"EDR behavior during kernel exploitation.",
"Patching-priority recommendations with proof.",
],
pitfalls=[
"Any production contact — lab only, enforced by network isolation.",
"Running exploits without code review — understand the payload before executing.",
"Kernel panics destroying lab state — snapshot before each run.",
],
references=[
"MITRE ATT&CK: Exploitation for Privilege Escalation (T1068).",
],
blue_note="their patching SLA is what this test actually measures — every successful lab exploit is a patch-window failure with a CVE attached.",
),
dict(
slug="sudo-misconfiguration",
title="Sudo Misconfiguration Escalation Test",
description="Test sudo misconfigurations (NOPASSWD, wildcard commands) for privilege escalation on Linux.",
tags=["red-team","privilege-escalation","linux","sudo"],
risk="moderate", confirm=True,
blue_kw=["sudo","linux","privilege-escalation","misconfiguration"],
purpose=("Sudo is the gatekeeper on Linux, and its configuration is frequently the vulnerability. "
"This test enumerates sudo rights (`sudo -l`) and exploits misconfigurations — NOPASSWD, wildcard "
"commands, editable scripts — to validate sudoers hygiene."),
when=[
"During Linux privilege-escalation phases.",
"To validate sudoers baselines across the fleet.",
"After gaining any low-privilege Linux shell.",
],
prereq=[
"Authorization for privilege escalation on the Linux targets.",
"Low-privilege test accounts with representative sudo rights.",
],
procedure=[
"Enumerate with `sudo -l` and inspect /etc/sudoers.d/ for NOPASSWD entries, wildcards, and dangerous binaries (vim, less, find, awk).",
"Exploit GTFOBins-style sudo abuses with inert proof (read a canary root-owned file).",
"Test wildcard command abuse: can arguments be injected past the intended command?",
"Check for editable scripts run via sudo — a writable script is root execution.",
"Record which misconfigurations yielded root and which were properly constrained.",
"Deliver per-host sudoers findings with corrected sudoers snippets.",
],
outputs=[
"Sudo misconfiguration inventory per host.",
"Root-proof evidence per exploitable entry.",
"Corrected sudoers configurations.",
],
pitfalls=[
"Modifying sudoers during the test and breaking admin access — read-only enumeration plus inert proofs.",
"Assuming `sudo -l` shows everything — inspect the included files too.",
"Forgetting LDAP/SSSD-provided sudo rules in enterprise environments.",
],
references=[
"MITRE ATT&CK: Sudo and Sudo Caching (T1548.003); GTFOBins (public).",
],
blue_note="their sudoers baseline is the control under test — every NOPASSWD wildcard is a configuration finding with a known fix.",
),
dict(
slug="suid-binary-escalation",
title="SUID Binary Escalation Test",
description="Test SUID/SGID binary abuse for privilege escalation on Linux hosts.",
tags=["red-team","privilege-escalation","linux","suid"],
risk="moderate", confirm=True,
blue_kw=["suid","linux","privilege-escalation","binaries"],
purpose=("SUID binaries run as their owner — usually root. Non-standard SUID binaries and known-"
"abusable ones (via GTFOBins) are a classic Linux privesc path. This test inventories SUID/SGID "
"binaries and validates each against abuse techniques with inert proofs."),
when=[
"During Linux privilege-escalation phases.",
"To validate the SUID inventory against a hardened baseline.",
"After software installs that may have added SUID binaries.",
],
prereq=[
"Authorization for privilege escalation on the targets.",
"Inert proofs only (canary file reads as root).",
],
procedure=[
"Inventory all SUID/SGID binaries (`find / -perm -4000`) and compare against the hardened baseline; flag non-standard entries.",
"Check each against GTFOBins-style abuse techniques; test with inert payloads.",
"Look for SUID binaries with relative-path or environment-variable flaws (PATH hijacking, LD_PRELOAD).",
"Verify each successful escalation with a canary root-file read.",
"Record which binaries the EDR/auditd flagged during abuse.",
"Deliver the SUID findings with remediation (remove SUID bit, use capabilities).",
],
outputs=[
"SUID/SGID inventory with baseline delta.",
"Per-binary abuse feasibility with proof.",
"Remediation per binary (chmod u-s, capabilities).",
],
pitfalls=[
"Removing SUID bits during the test and breaking applications — report, don't remediate, without approval.",
"Missing SGID and capabilities (`getcap`) while focusing only on SUID.",
"Environment-variable attacks that affect other users' sessions — test carefully.",
],
references=[
"MITRE ATT&CK: Setuid and Setgid (T1548.001); GTFOBins (public).",
],
blue_note="their Linux hardening baseline should define the allowed SUID set — every extra binary is a finding, every abusable one is critical.",
),
dict(
slug="kerberoasting",
title="Kerberoasting Test",
description="Test Kerberoasting (requesting crackable service tickets) to validate service-account password hygiene.",
tags=["red-team","privilege-escalation","kerberos","active-directory"],
risk="moderate", confirm=True,
blue_kw=["kerberoasting","kerberos","service-accounts","active-directory"],
purpose=("Service accounts with weak passwords and SPNs hand attackers crackable Kerberos tickets — "
"no privileged access needed, just any domain user. This test requests service tickets, extracts "
"the hashes, and cracks them offline in the lab to prove which service accounts fall."),
when=[
"During AD privilege-escalation phases with any domain user context.",
"To validate service-account password policy and SPN hygiene.",
"After user-hunting shows service accounts with old passwords.",
],
prereq=[
"Authorization for the AD environment; any domain user context suffices for the request phase.",
"Cracking performed offline in the lab — never on the target network.",
],
procedure=[
"Enumerate user accounts with SPNs set (service accounts) via LDAP.",
"Request TGS tickets for each SPN-holding account and extract the ticket hashes (Rubeus/Impacket-style, authorized tooling).",
"Transfer hashes to the lab and attempt offline cracking with the agreed wordlists/rules.",
"For each cracked account, verify the impact: what does this service account administer?",
"Record detection: did requesting dozens of TGS tickets trip any alert (Honeypot SPNs, unusual TGS volume)?",
"Deliver the crackable-service-account list with password-policy and managed-service-account recommendations.",
],
outputs=[
"Service-account enumeration with SPN details.",
"Crack results per account (lab only).",
"Detection assessment for TGS-request anomalies.",
],
pitfalls=[
"Cracking on the target network or with cloud GPUs outside the agreed lab — keep it in the lab.",
"Using cracked service-account credentials beyond verification without fresh authorization.",
"Forgetting AES-only enforcement as the mitigation — note it in recommendations.",
],
references=[
"MITRE ATT&CK: Steal or Forge Kerberos Tickets — Kerberoasting (T1558.003).",
],
blue_note="their service-account password hygiene is the finding — every cracked account is a password-policy failure, and silent mass TGS requests are a detection gap.",
),
dict(
slug="asrep-roasting",
title="AS-REP Roasting Test",
description="Test AS-REP roasting against accounts without Kerberos pre-authentication to validate account hardening.",
tags=["red-team","privilege-escalation","kerberos","active-directory"],
risk="moderate", confirm=True,
blue_kw=["asrep","kerberos","pre-authentication","active-directory"],
purpose=("Accounts with Kerberos pre-authentication disabled hand out crackable AS-REP hashes to "
"anyone who asks — no credentials needed. This test finds such accounts, grabs the hashes, and "
"cracks them offline to prove the exposure."),
when=[
"During AD privilege-escalation phases, even with zero credentials.",
"To validate that pre-authentication is enforced on all accounts.",
],
prereq=[
"Authorization for the AD environment; the request phase needs no credentials by design.",
"Offline cracking in the lab only.",
],
procedure=[
"Enumerate accounts with DONT_REQUIRE_PREAUTH set via LDAP.",
"Request AS-REP hashes for each such account (no authentication required).",
"Crack the hashes offline in the lab with agreed wordlists.",
"For cracked accounts, assess impact and verify per the credential-handling ROE.",
"Check detection: are pre-auth-disabled accounts alerted on, and did the hash requests trip anything?",
"Deliver findings with the one-line fix per account (enable pre-authentication) and a sweep for reoccurrence.",
],
outputs=[
"Pre-auth-disabled account list with evidence.",
"Crack results (lab).",
"Remediation verification (re-sweep after enabling pre-auth).",
],
pitfalls=[
"Assuming only user accounts matter — service and legacy accounts get this flag too.",
"Cracking outside the lab or keeping cracked passwords beyond the rotation workflow.",
],
references=[
"MITRE ATT&CK: Steal or Forge Kerberos Tickets — AS-REP Roasting (T1558.004).",
],
blue_note="their account-hardening baseline should have zero pre-auth-disabled accounts — each one is a one-line fix, and the sweep is automatable.",
),
dict(
slug="dcsync-test",
title="DCSync Test",
description="Test DCSync credential replication to validate replication monitoring and privileged-account hygiene.",
tags=["red-team","privilege-escalation","active-directory","dcsync"],
risk="high", confirm=True,
blue_kw=["dcsync","replication","active-directory","credentials"],
purpose=("DCSync abuses replication privileges to pull password hashes — including KRBTGT — without "
"touching the DC's disk. Testing it validates that replication rights are tightly held and that "
"the resulting 4662/5136-style replication telemetry actually alerts."),
when=[
"During AD privilege-escalation phases with elevated rights.",
"To validate who holds replication privileges (the keys to the kingdom list).",
"To test SIEM rules for anomalous replication traffic.",
],
prereq=[
"High-privilege context obtained under authorization; explicit approval for hash retrieval.",
"Strict credential-handling: retrieved hashes go to the lab, never linger.",
],
procedure=[
"Enumerate who holds DS-Replication-Get-Changes rights (the DCSync-capable principals).",
"With the authorized elevated context, perform a DCSync for a canary account first — prove the path with minimal data.",
"Record the replication telemetry: event 4662 access, network replication traffic, and SIEM alerts.",
"Test detection of DCSync from a non-DC host (the anomaly) vs. normal DC-to-DC replication.",
"Deliver the replication-rights inventory with least-privilege recommendations.",
"Verify credential hygiene: all retrieved material handled per the ROE and destroyed after the lab analysis.",
],
outputs=[
"DCSync-capable principal inventory.",
"Replication telemetry assessment (canary-first).",
"Credential-handling and destruction log.",
],
pitfalls=[
"DCSyncing KRBTGT or the full domain without explicit approval — canary accounts first, scope the rest.",
"Leaving retrieved hashes on test systems — destroy per the ROE.",
"Confusing normal replication with DCSync — the test is about non-DC initiators.",
],
references=[
"MITRE ATT&CK: OS Credential Dumping — DCSync (T1003.006).",
],
blue_note="their replication-privilege hygiene and 4662 monitoring are under test — DCSync from a workstation that nobody noticed is a critical detection failure.",
),
dict(
slug="adcs-escalation",
title="AD CS (ESC) Escalation Test",
description="Test Active Directory Certificate Services misconfigurations (ESC1-ESC8) for privilege escalation.",
tags=["red-team","privilege-escalation","active-directory","adcs"],
risk="high", confirm=True,
blue_kw=["adcs","certificates","esc","active-directory"],
purpose=("AD CS misconfigurations (the ESC family) turn certificate templates into domain-compromise "
"paths: enroll-as-anyone, weak EKU, NTLM relay to HTTP enrollment. This test enumerates the CA "
"configuration and validates each ESC primitive with proof-only certificate operations."),
when=[
"During AD privilege-escalation phases where AD CS is deployed.",
"To validate certificate-template hardening against the ESC checklist.",
"When the threat model includes AD CS (most enterprises have it).",
],
prereq=[
"Authorization for the AD environment including the CA infrastructure.",
"Proof-only goals: enroll test certificates, never use them beyond verification.",
],
procedure=[
"Enumerate CAs, templates, and permissions with authorized tooling (Certify/Impacket-style).",
"Check each ESC primitive: ESC1 (enroll-as-anyone + client auth EKU), ESC2/3 (weak EKU/permissions), ESC4 (template write), ESC6 (EDITF_ATTRIBUTESUBJECTALTNAME2), ESC8 (HTTP relay).",
"For each vulnerable template, perform a proof enrollment for a canary identity — stop at issuance.",
"Record whether certificate-services auditing logged the enumeration and enrollments.",
"Deliver per-template findings with the exact hardening change (permissions, EKU, flags).",
"Re-test after remediation to confirm each ESC path is closed.",
],
outputs=[
"CA/template enumeration with ESC mapping.",
"Proof-enrollment evidence per vulnerable template.",
"Remediation verification (re-test).",
],
pitfalls=[
"Using issued certificates for actual authentication beyond proof — stop at issuance.",
"Missing ESC6/ESC8 which live in CA configuration, not templates.",
"Forgetting to check enrollment permissions for low-privileged groups — that's where ESC1 hides.",
],
references=[
"MITRE ATT&CK: Valid Accounts via certificates; SpecterOps Certified Pre-Owned research (public).",
],
blue_note="their AD CS hardening gets an ESC-by-ESC verdict — each vulnerable template is a high-severity finding with a documented fix.",
),
dict(
slug="shadow-credentials-test",
title="Shadow Credentials Test",
description="Test shadow-credential attacks (msDS-KeyCredentialLink) to validate privileged-attribute monitoring.",
tags=["red-team","privilege-escalation","active-directory","shadow-credentials"],
risk="high", confirm=True,
blue_kw=["shadow-credentials","keycredentiallink","active-directory","whisker"],
purpose=("Shadow credentials abuse the msDS-KeyCredentialLink attribute: with write access to a "
"target's attribute, an attacker adds their own key and authenticates as the victim via PKINIT — "
"no password needed. Testing it validates attribute-write monitoring and AD hardening."),
when=[
"During AD privilege-escalation phases.",
"To validate monitoring of KeyCredentialLink modifications.",
"When the environment uses Windows Hello for Business (the legitimate feature this abuses).",
],
prereq=[
"Authorization for the AD environment; attribute-write rights obtained under authorization.",
"Lab-preferred; production only with explicit approval.",
],
procedure=[
"Identify targets where the test principal holds write access to msDS-KeyCredentialLink (often via GenericWrite).",
"Add a canary key credential to a test target's link attribute using authorized tooling.",
"Authenticate as the target via PKINIT with the canary key — proof only.",
"Record telemetry: directory-service audit events for the attribute write and the PKINIT logon.",
"Remove the canary key credential; verify the attribute is clean.",
"Deliver findings with monitoring recommendations for KeyCredentialLink writes.",
],
outputs=[
"Shadow-credential feasibility per target with evidence.",
"Attribute-write telemetry assessment.",
"Cleanup verification.",
],
pitfalls=[
"Leaving key credentials on real accounts — verify removal on every target.",
"Testing against privileged targets (Domain Admins) without specific approval.",
"Confusing legitimate WHfB key material with test artifacts — label everything.",
],
references=[
"MITRE ATT&CK: account-manipulation via key credentials; public shadow-credentials research.",
],
blue_note="their directory auditing for KeyCredentialLink writes is under test — silent attribute writes are an AD-monitoring gap.",
),
]
