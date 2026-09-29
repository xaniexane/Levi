# Red team topics — chunk 4: defense evasion (10) + credential access (10)

RED_4 = [
dict(
slug="amsi-bypass-test",
title="AMSI Bypass Validation Test",
description="Test AMSI bypass techniques to validate that defenses do not depend on AMSI alone.",
tags=["red-team","defense-evasion","amsi"],
risk="high", confirm=True,
blue_kw=["amsi","defense-evasion","antimalware"],
purpose=("AMSI is a scan interface, not a security boundary — bypasses are public and reliable. This "
"test runs known AMSI bypass variants against the EDR stack to prove whether detection survives "
"AMSI failure, and to justify defense-in-depth beyond the scan interface."),
when=[
"During defense-evasion phases on Windows.",
"To validate that EDR detections don't collapse when AMSI is bypassed.",
"To justify behavioral-over-signature detection investments.",
],
prereq=[
"Authorization for in-memory bypass techniques on test hosts.",
"Inert payloads only — the bypass delivers a canary, never a real payload.",
],
procedure=[
"Establish the AMSI baseline: confirm a known-bad canary string is blocked by AMSI on the test host.",
"Execute public AMSI bypass variants (field-tamper, DLL-hijack-free memory patch, obfuscated invocation) each delivering an inert canary.",
"For each variant, record: did AMSI fire, did the EDR's behavioral engine fire, did anything fire at all?",
"Measure per-variant detection outcome: blocked, alerted-only, or silent.",
"Re-test after any EDR tuning to confirm the bypass is still caught behaviorally (or document the residual gap).",
"Deliver the AMSI-dependence assessment: which detections survive AMSI failure.",
],
outputs=[
"Per-variant AMSI/EDR outcome matrix.",
"AMSI-dependence rating per detection control.",
"Residual-gap documentation where behavioral coverage is missing.",
],
pitfalls=[
"Real payloads behind the bypass — canaries only.",
"Testing on production workstations without isolation — use test hosts.",
"Treating a bypass as 'EDR evaded' when the behavioral engine still caught the canary — record both layers.",
],
references=[
"MITRE ATT&CK: Impair Defenses — Disable or Modify Tools (T1562.001).",
],
blue_note="their detection stack's dependence on AMSI is what's measured — controls that die with AMSI are signature-dependent and need behavioral backup.",
),
dict(
slug="etl-tampering-test",
title="ETW/ETL Tampering Validation Test",
description="Test ETW tampering techniques to validate sensor resilience against telemetry blinding.",
tags=["red-team","defense-evasion","etw","telemetry"],
risk="high", confirm=True,
blue_kw=["etw","telemetry","defense-evasion","sensors"],
purpose=("ETW is the telemetry backbone most EDRs rely on; attackers blind it to go dark. This test "
"applies known ETW-tampering techniques in the lab and validates whether the sensor stack detects "
"the tampering itself, fails closed, or silently goes blind."),
when=[
"Lab-first, during defense-evasion phases.",
"To validate EDR self-protection and tamper alerting.",
"When the threat model includes telemetry-aware adversaries.",
],
prereq=[
"Lab authorization; production only with explicit approval and sensor-health monitoring.",
"Sensor-health baseline captured before the test.",
],
procedure=[
"Baseline the sensor: confirm ETW providers are flowing and the EDR reports healthy.",
"Apply ETW-tampering variants (provider patching, trace-session manipulation) per public techniques, each followed by a canary action that should have generated telemetry.",
"For each variant: did the EDR alert on the tampering, did it fail closed (block), or did the canary go silent?",
"Restore ETW state after each variant and verify sensor health returns.",
"Deliver the telemetry-resilience verdict: tamper-evident, fail-closed, or blind.",
],
outputs=[
"Per-variant tampering outcome (alerted/blocked/blind).",
"Sensor-health before/after evidence.",
"Tamper-response recommendations.",
],
pitfalls=[
"Leaving ETW tampered on a production host — restore and verify after every variant.",
"No sensor-health baseline — without it you can't prove the tampering had an effect.",
"Confusing EDR self-protection blocks with detection — record both separately.",
],
references=[
"MITRE ATT&CK: Impair Defenses — Disable Windows Event Logging (T1562.002).",
],
blue_note="their telemetry pipeline's resilience is under test — an EDR that goes silently blind is worse than one that fails loudly.",
),
dict(
slug="defender-exclusion-abuse",
title="Defender Exclusion Abuse Test",
description="Test Microsoft Defender exclusion abuse to validate exclusion governance and monitoring.",
tags=["red-team","defense-evasion","defender","exclusions"],
risk="moderate", confirm=True,
blue_kw=["defender","exclusions","defense-evasion","monitoring"],
purpose=("Defender exclusions are a sanctioned blind spot — attackers with admin rights add exclusions "
"for their tooling. This test adds canary exclusions and validates whether exclusion changes are "
"monitored, alerted, and governed by policy."),
when=[
"During defense-evasion phases on Defender-managed hosts.",
"To validate exclusion-change alerting (event 5007).",
"To audit the existing exclusion list for overly broad entries.",
],
prereq=[
"Authorization for Defender configuration changes on test hosts.",
"Canary exclusions scoped to test paths only.",
],
procedure=[
"Audit the existing exclusion list for broad entries (entire drives, temp paths, process exclusions) — report these regardless.",
"Add a canary path exclusion via authorized tooling; record whether event 5007 fired and whether any alert reached the SOC.",
"Test exclusion via GPO/Intune vs. local — which paths does the blue team monitor?",
"Verify the canary path is actually unscanned (EICAR-style canary file, not real malware).",
"Remove all test exclusions; verify the exclusion list matches the pre-test baseline.",
"Deliver the exclusion-governance assessment with least-exclusion recommendations.",
],
outputs=[
"Pre-existing exclusion audit with risk ratings.",
"Exclusion-change detection timeline.",
"Baseline-restoration verification.",
],
pitfalls=[
"Broad exclusions left behind — diff the exclusion list before and after.",
"Real malware in the excluded path — canary files only.",
"Testing GPO-managed exclusions without the AD team's coordination.",
],
references=[
"MITRE ATT&CK: Impair Defenses — Disable or Modify Tools (T1562.001).",
"Microsoft Defender event 5007 documentation.",
],
blue_note="their Defender exclusion governance is under test — unmonitored exclusion changes are an attacker-controlled blind spot.",
),
dict(
slug="process-injection-test",
title="Process Injection Detection Test",
description="Test process-injection techniques to validate EDR memory and API monitoring.",
tags=["red-team","defense-evasion","process-injection"],
risk="high", confirm=True,
blue_kw=["process-injection","defense-evasion","edr","monitoring"],
purpose=("Process injection hides malicious code inside legitimate processes. This test runs the "
"injection family — classic DLL injection, process hollowing, APC injection, mapping injection — "
"with inert payloads to map exactly which techniques the EDR sees and which slip through."),
when=[
"During defense-evasion phases on Windows.",
"To build a per-technique EDR detection matrix.",
"To validate Sysmon configs (CreateRemoteThread, image-load events).",
],
prereq=[
"Authorization for memory-injection techniques on test hosts.",
"Inert shellcode: canary file write or beacon, no real payloads.",
],
procedure=[
"For each injection variant (CreateRemoteThread DLL, process hollowing, QueueUserAPC, NT-map-section), inject an inert canary into a test target process.",
"Record per variant: Sysmon events (8, 10, 25), EDR alert or block, and whether the canary executed.",
"Test both signed and unsigned target processes; note Protected Process Light boundaries.",
"Measure detection latency per variant.",
"Terminate all injected processes and verify no canary artifacts remain.",
"Deliver the per-technique detection matrix with Sysmon/EDR tuning recommendations.",
],
outputs=[
"Injection-variant detection matrix (Sysmon + EDR).",
"Canary-execution evidence per variant.",
"Cleanup verification.",
],
pitfalls=[
"Injecting into production processes — test targets only.",
"Real payloads in the injected shellcode — inert canaries.",
"Process hollowing crashing the target — snapshot or use disposable test processes.",
],
references=[
"MITRE ATT&CK: Process Injection (T1055) and sub-techniques.",
],
blue_note="their EDR's injection coverage gets a technique-by-technique scorecard — silent variants are memory-monitoring gaps to close.",
),
dict(
slug="timestomping-test",
title="Timestomping Detection Test",
description="Test timestomping (timestamp manipulation) to validate forensic timeline integrity controls.",
tags=["red-team","defense-evasion","timestomping","forensics"],
risk="moderate", confirm=True,
blue_kw=["timestomping","forensics","defense-evasion","timeline"],
purpose=("Timestomping rewrites file timestamps to corrupt forensic timelines. This test timestomps "
"canary files and validates whether the blue team's forensic tooling and timeline analysis detect "
"the manipulation (USN journal, $STANDARD_INFORMATION vs. $FILE_NAME discrepancies)."),
when=[
"During defense-evasion phases.",
"To validate forensic readiness: can the team detect timeline tampering?",
"As a DFIR exercise input — the timestomped files become the investigation scenario.",
],
prereq=[
"Authorization for the test hosts; canary files in a test directory.",
"DFIR team awareness if the test doubles as an exercise.",
],
procedure=[
"Create canary files, then timestomp their MFT timestamps (creation/modification) to misleading values.",
"Have the blue/DFIR side analyze: do their tools flag the $SI/$FN discrepancy? Does the USN journal contradict the timestamps?",
"Record which forensic tools detected the tampering and which trusted the forged timestamps.",
"Test timestomping on executables placed in autostart locations (combined persistence + evasion).",
"Restore or delete all canary files; verify the test directory is clean.",
"Deliver the forensic-timeline-integrity assessment.",
],
outputs=[
"Per-tool timestomp-detection results.",
"USN/MFT discrepancy evidence.",
"DFIR exercise debrief (if combined).",
],
pitfalls=[
"Timestomping outside the test directory — scope strictly.",
"Forgetting the USN journal also needs checking — that's the detection path.",
"Presenting timestomping as unstoppable — the discrepancies ARE detectable with the right analysis.",
],
references=[
"MITRE ATT&CK: Indicator Removal — Timestomp (T1070.006).",
],
blue_note="their forensic timeline discipline is under test — teams that trust $STANDARD_INFORMATION blindly will misdate the whole intrusion.",
),
dict(
slug="log-tampering-test",
title="Log Tampering and Clearing Test",
description="Test event-log tampering and clearing to validate log forwarding and tamper alerting.",
tags=["red-team","defense-evasion","logs","siem"],
risk="moderate", confirm=True,
blue_kw=["logs","tampering","siem","forwarding"],
purpose=("Attackers clear or tamper logs to hide; the defense is logs the attacker can't reach. This "
"test clears and tampers canary logs and validates that centralized forwarding captured the events "
"first, and that the tampering itself alerted."),
when=[
"During defense-evasion phases.",
"To validate log-forwarding latency vs. attacker dwell time.",
"To test SIEM rules for log-clearing events (1102, 104).",
],
prereq=[
"Authorization for log manipulation on test hosts.",
"SIEM forwarding confirmed as the prerequisite — the test measures it.",
],
procedure=[
"Generate canary events on the test host, then clear the Security log (event 1102) and the System log (104).",
"Check the SIEM: did the canary events arrive before the clear? Did the clear event itself arrive and alert?",
"Test targeted tampering: deleting specific canary events vs. wholesale clearing.",
"Measure forwarding latency: event creation → SIEM ingestion time.",
"Test log-size and retention settings: can the attacker rotate logs away before forwarding?",
"Deliver the log-resilience assessment with forwarding and retention recommendations.",
],
outputs=[
"Forwarding-latency measurements.",
"Tamper/clear detection results (1102/104 alerting).",
"Retention and rotation findings.",
],
pitfalls=[
"Clearing production logs without explicit approval — test hosts only.",
"No pre-test forwarding baseline — measure the normal latency first.",
"Forgetting that 1102 itself must be forwarded — the clear event is the alert.",
],
references=[
"MITRE ATT&CK: Indicator Removal — Clear Windows Event Logs (T1070.001).",
],
blue_note="their log pipeline's race against the attacker is what's measured — events that never reach the SIEM are a forwarding-latency finding.",
),
dict(
slug="obfuscation-resilience",
title="Obfuscation Resilience Test",
description="Test obfuscated payloads against static detection to validate layered detection.",
tags=["red-team","defense-evasion","obfuscation"],
risk="moderate", confirm=True,
blue_kw=["obfuscation","static-analysis","detection","defense-evasion"],
purpose=("Obfuscation defeats signature and static analysis; behavior must catch what static misses. "
"This test runs progressively obfuscated canary payloads to prove the detection stack's layers — "
"static, AMSI, behavioral — each get their score."),
when=[
"During defense-evasion phases.",
"To validate that behavioral detection covers what static analysis misses.",
"To tune allow/block thresholds on obfuscation heuristics.",
],
prereq=[
"Authorization for the test hosts; canary payloads only.",
"Layered telemetry: static scan logs, AMSI, EDR behavioral alerts.",
],
procedure=[
"Build a canary payload in cleartext; verify each detection layer fires (baseline).",
"Apply progressive obfuscation: encoding, string splitting, dynamic invocation, packing — re-test each layer per stage.",
"Record per stage and per layer: blocked, alerted, or silent.",
"Identify the obfuscation stage where static/AMSI goes silent and confirm behavioral coverage takes over (or document the gap).",
"Clean all payload artifacts from test hosts.",
"Deliver the layered-detection scorecard with tuning recommendations.",
],
outputs=[
"Obfuscation-stage × detection-layer matrix.",
"Static-to-behavioral handoff analysis.",
"Tuning recommendations per layer.",
],
pitfalls=[
"Real malicious payloads 'for realism' — canaries only.",
"Packing that the EDR quarantines the test tooling over — coordinate with the SOC.",
"Concluding 'obfuscation wins' when behavioral caught it — score each layer honestly.",
],
references=[
"MITRE ATT&CK: Obfuscated Files or Information (T1027).",
],
blue_note="their detection layering is under test — the stage where every layer goes silent defines the obfuscation ceiling they must raise.",
),
dict(
slug="living-off-land-detection",
title="Living-off-the-Land Detection Test",
description="Test LOLBin abuse patterns to validate behavioral detection of legitimate-tool misuse.",
tags=["red-team","defense-evasion","lolbin","behavioral"],
risk="moderate", confirm=True,
blue_kw=["lolbin","behavioral","defense-evasion","detection"],
purpose=("LOLBins are signed, legitimate, and everywhere — detection must be behavioral (parent-child "
"anomalies, command-line patterns), not reputation-based. This test exercises LOLBin abuse patterns "
"with inert actions to score the behavioral rules."),
when=[
"During defense-evasion phases, after the execution-lab baseline.",
"To validate Sysmon command-line logging and EDR behavioral rules.",
"To tune LOLBin alerting without drowning the SOC in false positives.",
],
prereq=[
"Authorization for the test hosts; inert LOLBin actions (canary file writes, no exfil).",
"Command-line logging enabled as a prerequisite check.",
],
procedure=[
"Execute a battery of LOLBin abuse patterns with inert outcomes: mshta/jscript canary, rundll32 javascript canary, certutil download of a canary file, bitsadmin canary transfer.",
"For each pattern, record: command-line logged, EDR alert, parent-child anomaly flagged.",
"Test the benign baseline too: normal admin use of the same binaries — measure the false-positive distance.",
"Tune recommendations: which patterns alert reliably, which need new rules, which are too noisy to alert on.",
"Clean all canary artifacts.",
"Deliver the LOLBin behavioral scorecard.",
],
outputs=[
"Per-pattern detection results (logged/alerted/silent).",
"Benign-baseline comparison for tuning.",
"Rule recommendations with noise estimates.",
],
pitfalls=[
"LOLBin actions with real exfil or download of untrusted content — canary files only.",
"No benign baseline — without it you can't tune without noise.",
"Alerting on the binary name alone — that's the false-positive trap this test exposes.",
],
references=[
"MITRE ATT&CK: System Binary Proxy Execution (T1218); LOLBAS project (public).",
],
blue_note="their behavioral rules for legitimate-tool abuse are under test — binary-name alerting is the false-positive trap this exercise exposes.",
),
dict(
slug="rootkit-detection-test",
title="Rootkit Detection Validation Test",
description="Test rootkit-style hiding techniques in a lab to validate integrity monitoring.",
tags=["red-team","defense-evasion","rootkit","lab"],
risk="high", confirm=True,
blue_kw=["rootkit","integrity","defense-evasion","monitoring"],
purpose=("Rootkits hide by subverting the OS's own reporting. This lab test deploys canary hiding "
"techniques (userland hooks, DKOM concepts) and validates whether integrity monitoring, "
"cross-view detection, and offline analysis catch the deception."),
when=[
"Lab-only, during advanced defense-evasion phases.",
"To validate boot integrity (Secure Boot, measured boot) and offline-analysis capability.",
"When the threat model includes kernel-level adversaries.",
],
prereq=[
"Isolated lab VMs with snapshots; explicit authorization for kernel techniques.",
"Inert hiding: canary processes/files hidden, nothing destructive.",
],
procedure=[
"Snapshot the lab VM; deploy a userland hiding canary (API-hook process hiding) and test detection via cross-view (tasklist vs. direct handle enumeration).",
"Test bootkit concepts discussion-only unless the lab is specifically built for it — validate Secure Boot and measured-boot attestation instead.",
"Run the EDR and an offline disk analysis against the VM; compare what each sees.",
"Record which hiding techniques were caught by which layer.",
"Restore the snapshot; verify the VM is clean.",
"Deliver the integrity-monitoring assessment with boot-attestation recommendations.",
],
outputs=[
"Per-technique hiding vs. detection matrix.",
"Online vs. offline analysis comparison.",
"Boot-integrity recommendations.",
],
pitfalls=[
"Kernel techniques outside the snapshot-capable lab — never on real hardware.",
"Deploying real rootkits 'for realism' — canary hiding techniques only.",
"Forgetting the offline analysis — cross-view is the detection principle being validated.",
],
references=[
"MITRE ATT&CK: Rootkit (T1014).",
],
blue_note="their integrity monitoring and offline-analysis capability are under test — hiding the EDR can't see from inside is proven from outside.",
),
dict(
slug="indicator-removal-audit",
title="Indicator Removal Audit",
description="Audit artifact/indicator-removal techniques to validate forensic completeness.",
tags=["red-team","defense-evasion","forensics","audit"],
risk="low", confirm=False,
blue_kw=["indicators","forensics","audit","defense-evasion"],
purpose=("Attackers systematically remove their indicators: logs, files, registry keys, timestamps. "
"This audit enumerates the removal techniques relevant to the environment and validates — per "
"technique — whether a forensic trail survives somewhere the attacker can't reach."),
when=[
"As a DFIR readiness audit, independent of live phases.",
"After incident-response tabletop exercises.",
"To validate backup and immutable-logging investments.",
],
prereq=[
"Inventory of log destinations, backup systems, and forensic tooling.",
"No live removal needed — this is an audit of survivability, mostly.",
],
procedure=[
"Enumerate the removal techniques in scope: file deletion, log clearing, timestomping, registry cleanup, shadow-copy deletion.",
"For each, trace where evidence would survive: SIEM copies, backups, USN journal, cloud audit logs, EDR cloud telemetry.",
"Where survivability is unproven, run a canary removal on a test host and verify the surviving trail.",
"Score each technique: fully survivable, partially survivable, or evidence-destroying.",
"Deliver the forensic-survivability matrix with investment recommendations (immutable logging, backup scope).",
],
outputs=[
"Per-technique evidence-survivability matrix.",
"Canary verification results where tested.",
"Investment recommendations (what to make immutable next).",
],
pitfalls=[
"Live destructive testing on production — canary tests on test hosts only.",
"Assuming backups capture the needed artifacts — verify restore and content, not just job success.",
"Forgetting cloud audit logs as a surviving trail for on-prem removal.",
],
references=[
"MITRE ATT&CK: Indicator Removal (T1070).",
],
blue_note="their forensic survivability is what's audited — every technique with no surviving trail is an immutable-logging investment case.",
),
dict(
slug="lsass-dump-test",
title="LSASS Dump Detection Test",
description="Test LSASS memory-dump techniques to validate credential-access monitoring.",
tags=["red-team","credential-access","lsass","monitoring"],
risk="high", confirm=True,
blue_kw=["lsass","credential-access","monitoring","detection"],
purpose=("LSASS holds credentials in memory; dumping it is the canonical credential-theft technique. "
"This test runs the dump family — Task Manager, procdump, comsvcs, direct API — with the goal of "
"mapping exactly which paths the EDR blocks, alerts on, or misses."),
when=[
"During credential-access phases on Windows.",
"To build a per-technique LSASS-access detection matrix.",
"To validate Protected Process Light and Credential Guard coverage.",
],
prereq=[
"Authorization for LSASS access on test hosts; explicit approval for the privilege level.",
"Inert goal: dump handle opened, canary credential marker — full credential extraction only where explicitly authorized.",
],
procedure=[
"For each dump technique (Task Manager UI, procdump -ma, comsvcs MiniDump, direct MiniDumpWriteDump, Dumpert-style), attempt LSASS access on the test host.",
"Record per technique: blocked, alerted, or silent — with Sysmon event 10 details.",
"Test with Credential Guard / PPL enabled vs. disabled to show the control's effect.",
"Verify whether any technique produced a usable dump (handle the dump file per the credential ROE).",
"Securely delete all dump artifacts; verify deletion.",
"Deliver the LSASS-access matrix with hardening recommendations (Credential Guard rollout, PPL).",
],
outputs=[
"Per-technique LSASS-access outcome matrix.",
"Control-effectiveness comparison (Credential Guard/PPL on vs. off).",
"Dump-artifact destruction log.",
],
pitfalls=[
"Full credential extraction without explicit approval — scope the goal first.",
"Dump files left on disk — they're credential material, destroy per the ROE.",
"Testing on production domain controllers without a dedicated window.",
],
references=[
"MITRE ATT&CK: OS Credential Dumping — LSASS Memory (T1003.001).",
],
blue_note="their LSASS protection stack is under test — every silent dump path is a Credential Guard or EDR-rule gap.",
),
dict(
slug="sam-ntds-extraction",
title="SAM/NTDS Extraction Test",
description="Test SAM and NTDS.dit extraction paths to validate DC hardening and backup security.",
tags=["red-team","credential-access","sam","ntds","active-directory"],
risk="high", confirm=True,
blue_kw=["sam","ntds","credential-access","domain-controller"],
purpose=("The SAM and NTDS.dit are the credential databases; extracting them is total credential "
"compromise. This test validates the extraction paths — registry hive saves, VSS copies, DCSync "
"alternatives — and the DC/backup hardening that should block them."),
when=[
"During credential-access phases with elevated access.",
"To validate domain-controller hardening and backup-file security.",
"Lab-preferred; production DCs only with explicit approval.",
],
prereq=[
"Authorization for the target tier; lab preferred for NTDS.dit.",
"Strict credential-material handling per the ROE.",
],
procedure=[
"Test SAM extraction paths on a member host: reg save of SAM/SYSTEM hives with authorized privileges.",
"Test NTDS.dit paths in the lab: VSS snapshot copy, ntdsutil snapshot — verify each step's telemetry.",
"Record detection per path: EDR alerts, 4662-style audit events, VSS creation alerts.",
"Handle all extracted material as credential material: lab-only analysis, destruction logged.",
"Audit backup locations for unprotected NTDS.dit/system-state copies — the real-world exposure.",
"Deliver the extraction-path matrix with DC-hardening and backup-security recommendations.",
],
outputs=[
"Per-path extraction feasibility and detection results.",
"Backup-location audit for credential-database exposure.",
"Credential-material destruction log.",
],
pitfalls=[
"Extracting production NTDS.dit without explicit approval — lab first, always.",
"Backup copies of NTDS.dit forgotten in the audit — check backup storage, not just the DC.",
"Leaving VSS snapshots behind — clean every snapshot created.",
],
references=[
"MITRE ATT&CK: OS Credential Dumping — SAM (T1003.002), NTDS (T1003.003).",
],
blue_note="their DC hardening and backup hygiene are under test — an unprotected NTDS.dit in backups is a finding regardless of live extraction.",
),
dict(
slug="credential-manager-abuse",
title="Credential Manager Abuse Test",
description="Test Windows Credential Manager and DPAPI abuse to validate stored-credential protections.",
tags=["red-team","credential-access","dpapi","credential-manager"],
risk="moderate", confirm=True,
blue_kw=["credential-manager","dpapi","credential-access","windows"],
purpose=("Windows Credential Manager stores user credentials encrypted with DPAPI — decryptable in "
"the user's context. This test validates what an attacker with user-context access can recover, "
"and whether DPAPI-abuse tooling is detected."),
when=[
"During credential-access phases on user workstations.",
"To validate the risk of credentials stored in Credential Manager and browsers.",
"After gaining user-context access in an exercise.",
],
prereq=[
"Authorization for the test user contexts; canary credentials planted for the test.",
"Agreement on whether real stored credentials may be viewed (prefer canaries).",
],
procedure=[
"Plant canary credentials in the test users' Credential Manager vaults.",
"With user-context access, enumerate and decrypt the vaults using authorized tooling; record success.",
"Test DPAPI master-key paths: with and without the user's password context.",
"Record EDR telemetry during vault enumeration and DPAPI abuse.",
"Audit real vaults (with approval) for high-value stored credentials — report counts, not values.",
"Remove canary credentials; verify vaults are clean.",
],
outputs=[
"Vault-recovery feasibility per context.",
"DPAPI-abuse detection results.",
"Stored-credential hygiene findings (counts).",
],
pitfalls=[
"Reading users' real stored passwords without explicit approval — canaries first.",
"Exporting vault contents off the host — analyze in place, report counts.",
"Forgetting browser-stored credentials in the same audit — include them.",
],
references=[
"MITRE ATT&CK: Credentials from Password Stores (T1555).",
],
blue_note="their stored-credential hygiene is under test — every production password recoverable from a vault is a credential-storage finding.",
),
dict(
slug="browser-credential-theft",
title="Browser Credential Theft Test",
description="Test browser-stored credential theft to validate browser hardening and password-manager rollout.",
tags=["red-team","credential-access","browser","passwords"],
risk="moderate", confirm=True,
blue_kw=["browser","credentials","password-manager","credential-access"],
purpose=("Browsers store passwords, cookies, and session tokens — a rich target that bypasses MFA via "
"stolen sessions. This test measures what browser-stored material is recoverable and validates the "
"enterprise password-manager and session-security controls."),
when=[
"During credential-access phases on user workstations.",
"To build the business case for enterprise password-manager rollout.",
"To validate session-timeout and cookie-security policies.",
],
prereq=[
"Authorization for test browser profiles; canary credentials and sessions planted.",
"Real user profiles only with explicit approval.",
],
procedure=[
"Plant canary credentials and sessions in test browser profiles (Chrome, Edge, Firefox as deployed).",
"With user-context access, extract the Login Data stores and cookie databases using authorized tooling.",
"Test session-cookie replay: does the canary session still authenticate (in the lab, against canary services)?",
"Record EDR/file-access telemetry during the extraction.",
"Audit the fleet for password-manager deployment vs. browser-stored passwords.",
"Remove all canary material; verify profiles are clean.",
"Deliver the browser-credential risk assessment with password-manager recommendations.",
],
outputs=[
"Per-browser extraction feasibility results.",
"Session-replay proof (canary services).",
"Password-manager coverage gap analysis.",
],
pitfalls=[
"Extracting real users' cookies/sessions without approval — canary profiles first.",
"Session replay against production services — canary services only.",
"Forgetting Firefox's separate key4.db/key3.db handling — cover all deployed browsers.",
],
references=[
"MITRE ATT&CK: Credentials from Password Stores — Credentials from Web Browsers (T1555.003).",
],
blue_note="their browser credential posture is under test — recoverable production passwords are the password-manager business case.",
),
dict(
slug="wifi-password-recovery",
title="Wi-Fi Password Recovery Test",
description="Test wireless profile and credential recovery to validate wireless security posture.",
tags=["red-team","credential-access","wifi","wireless"],
risk="low", confirm=False,
blue_kw=["wifi","wireless","credentials","profiles"],
purpose=("Windows stores wireless profiles with recoverable keys; `netsh wlan show profiles` with "
"key=clear is a built-in credential disclosure. This test validates what wireless material is "
"recoverable and whether PSK hygiene and certificate-based auth are in place."),
when=[
"During credential-access phases on laptops.",
"To validate the move from PSK to certificate-based wireless auth.",
"As a quick win during workstation assessments.",
],
prereq=[
"Authorization for the test laptops; user-context access.",
],
procedure=[
"Enumerate wireless profiles on test laptops; export keys for canary SSIDs.",
"Assess: are production SSIDs using PSKs recoverable by any user-context process?",
"Check for certificate-based (EAP-TLS) vs. PSK deployments across the sampled fleet.",
"Record whether profile enumeration tripped any monitoring (it usually doesn't — note that).",
"Deliver the wireless-auth assessment with EAP-TLS migration recommendations.",
],
outputs=[
"Wireless-profile recovery results per laptop.",
"PSK vs. certificate-auth deployment map.",
"Migration recommendations.",
],
pitfalls=[
"Recovering real production PSKs — report existence and scope, handle values per the ROE.",
"Assuming 'it usually doesn't alert' without testing — run the canary and check.",
],
references=[
"MITRE ATT&CK: Credentials from Password Stores; netsh wlan documentation.",
],
blue_note="their wireless-auth architecture is under test — user-recoverable production PSKs are a migration-to-EAP-TLS finding.",
),
dict(
slug="clipboard-credential-capture",
title="Clipboard Credential Capture Test",
description="Test clipboard monitoring for credential exposure to validate user-awareness controls.",
tags=["red-team","credential-access","clipboard","awareness"],
risk="low", confirm=False,
blue_kw=["clipboard","credentials","awareness","exposure"],
purpose=("Credentials live on clipboards constantly — copied passwords, tokens, connection strings. "
"This test measures clipboard credential exposure in the environment and validates user-awareness "
"training and clipboard-manager policies."),
when=[
"During credential-access phases, as a low-risk awareness test.",
"To validate security-awareness training effectiveness.",
"Combined with the credential-hygiene audit.",
],
prereq=[
"Authorization for clipboard monitoring on test hosts; user notification per the ROE.",
"Canary credentials for controlled tests.",
],
procedure=[
"Deploy a canary clipboard monitor on test hosts (authorized, time-boxed).",
"Measure: how often do password/token-shaped strings appear on clipboards?",
"Plant canary credentials via authorized test users and verify capture.",
"Check for clipboard-manager tools and cloud clipboard sync (a sync service holding credentials).",
"Correlate with awareness training: do trained users still copy passwords?",
"Remove the monitor; deliver the clipboard-exposure assessment with training recommendations.",
],
outputs=[
"Clipboard credential-exposure statistics.",
"Clipboard-sync and manager-tool findings.",
"Awareness-training effectiveness notes.",
],
pitfalls=[
"Monitoring clipboards without user notification where required — check the ROE.",
"Storing captured clipboard contents beyond the analysis — aggregate statistics, destroy samples.",
"Forgetting cloud clipboard sync as an exfil path — include it.",
],
references=[
"MITRE ATT&CK: Input Capture — Clipboard Data (T1115).",
],
blue_note="their credential-hygiene culture is what's measured — clipboard passwords are a training and tooling finding, not a malware finding.",
),
dict(
slug="mimikatz-detection-test",
title="Mimikatz and Credential Tooling Detection Test",
description="Test signatured credential-dumping tools to validate AV/EDR signature and behavioral coverage.",
tags=["red-team","credential-access","mimikatz","detection"],
risk="moderate", confirm=True,
blue_kw=["mimikatz","credential-access","signatures","edr"],
purpose=("Mimikatz is the most signatured tool in existence — if it runs silently, signature and "
"behavioral layers are both failing. This controlled test executes renamed, obfuscated, and "
"in-memory variants to score each layer honestly."),
when=[
"During credential-access phases.",
"To validate the signature-to-behavioral detection spectrum.",
"As a canary for AV/EDR health: it should NEVER run silent.",
],
prereq=[
"Authorization for credential-tooling on test hosts.",
"Inert execution goals: sekurlsa::logonpasswords output to canary verification only where explicitly authorized; otherwise load-and-detect tests.",
],
procedure=[
"Baseline: run the stock binary — record block/alert.",
"Run renamed, recompiled, and in-memory (reflective-load) variants — record per-variant outcomes.",
"Run the PowerShell and .NET in-memory variants — record AMSI + behavioral outcomes.",
"Score each variant: blocked pre-execution, alerted on behavior, or silent.",
"Verify no credential material persists on the test host after the exercise.",
"Deliver the signature-vs-behavioral scorecard.",
],
outputs=[
"Per-variant detection outcomes (stock → in-memory).",
"Signature-vs-behavioral layering analysis.",
"Cleanup verification.",
],
pitfalls=[
"Real credential output captured without approval — scope the extraction goal first.",
"Variants that the EDR quarantines the test tooling over — coordinate with the SOC.",
"Concluding 'detected' from a signature alone — the in-memory variants test the behavioral layer.",
],
references=[
"MITRE ATT&CK: OS Credential Dumping (T1003).",
],
blue_note="their AV/EDR layering gets a brutally honest scorecard — a silent Mimikatz variant is a layered-detection failure.",
),
dict(
slug="token-theft-session-hijack",
title="Token Theft and Session Hijacking Test",
description="Test access-token and session-cookie theft to validate session-security controls.",
tags=["red-team","credential-access","tokens","session"],
risk="moderate", confirm=True,
blue_kw=["tokens","session","hijacking","credential-access"],
purpose=("Modern auth is token-based; stealing the token skips the password and the MFA. This test "
"validates token theft paths — memory, disk, browser — and the controls that limit token value: "
"short lifetimes, binding, and conditional access."),
when=[
"During credential-access phases.",
"To validate token-lifetime and binding policies.",
"To test conditional-access resilience against stolen sessions.",
],
prereq=[
"Authorization for token-handling on test accounts; canary tokens and sessions.",
"Token material handled per the credential ROE.",
],
procedure=[
"With user-context access, enumerate token material: browser session cookies, app token caches, memory-resident tokens (canary).",
"Attempt replay of canary tokens from a different host/network — record whether conditional access stopped it.",
"Test token-lifetime: how long does a stolen canary token remain valid?",
"Check for token binding / DPoP-style controls in the environment.",
"Destroy all canary token material; verify no test tokens remain valid.",
"Deliver the session-security assessment with lifetime and binding recommendations.",
],
outputs=[
"Token-replay results per control (CA, lifetime, binding).",
"Token-lifetime measurements.",
"Session-security recommendations.",
],
pitfalls=[
"Replaying real user tokens without approval — canary tokens only.",
"Token material lingering after the test — verify invalidation.",
"Forgetting refresh tokens while focusing on access tokens — test both.",
],
references=[
"MITRE ATT&CK: Steal Application Access Token (T1528).",
],
blue_note="their session-security architecture is under test — replayable long-lived tokens are a lifetime-and-binding finding.",
),
dict(
slug="password-spray-test",
title="Password Spraying Test",
description="Test password spraying with strict account-safety controls to validate lockout and alerting.",
tags=["red-team","credential-access","password-spray"],
risk="moderate", confirm=True,
blue_kw=["password-spray","lockout","alerting","authentication"],
purpose=("Password spraying — one common password across many accounts — dodges per-account lockouts "
"and finds the weak-password outliers. This carefully controlled test validates lockout policy, "
"spray detection, and whether any accounts actually fall."),
when=[
"During credential-access phases, with explicit authentication-testing authorization.",
"To validate Azure AD / AD spray-detection and smart lockout.",
"To prove the weak-password tail exists (or doesn't).",
],
prereq=[
"Explicit authorization naming password spraying with attempt ceilings.",
"Agreed password list (common, non-targeted), attempt rate, and time window.",
"Account allowlist/blocklist: never spray service, admin, or VIP accounts without specific approval.",
],
procedure=[
"Confirm the lockout policy and spray-detection baseline with the blue team before starting.",
"Run the spray within the agreed ceiling: one password per round, rounds spaced per the agreement.",
"Monitor for lockouts in real time; abort immediately if any unapproved account locks.",
"Record valid credentials per the ROE — verify and hand to the blue team for rotation, never retain.",
"Check detection: did the spray trip identity-protection alerts? How many rounds before it fired?",
"Deliver the spray assessment: policy effectiveness, detection latency, and the weak-password findings.",
],
outputs=[
"Spray execution log within agreed ceilings.",
"Detection-latency measurement (rounds to alert).",
"Weak-credential findings with rotation handoff.",
],
pitfalls=[
"Exceeding the attempt ceiling — the ceiling is the authorization, not a suggestion.",
"Spraying without a live lockout monitor — abort capability must be real.",
"Retaining discovered credentials beyond the rotation handoff.",
],
references=[
"MITRE ATT&CK: Brute Force — Password Spraying (T1110.003).",
],
blue_note="their authentication monitoring faces a low-and-slow attack — silent spraying across many rounds is an identity-protection gap.",
),
dict(
slug="hash-cracking-lab",
title="Offline Hash-Cracking Lab Test",
description="Crack captured hashes offline in the lab to validate password-policy strength.",
tags=["red-team","credential-access","hash-cracking","lab"],
risk="low", confirm=False,
blue_kw=["hash-cracking","password-policy","lab","credential-access"],
purpose=("Captured hashes are only as strong as the passwords behind them. This lab test cracks "
"authorized hash sets offline to produce the password-policy verdict: what fraction falls to "
"dictionary, rules, and brute force — and what that means for policy."),
when=[
"As a password-policy audit, using hashes obtained under authorization.",
"After any credential-dumping phase that produced hashes.",
"To justify policy changes (length, managers, MFA).",
],
prereq=[
"Hashes obtained under explicit authorization; lab-only cracking.",
"Cracking wordlists and rules agreed; results handled per the credential ROE.",
],
procedure=[
"Transfer authorized hashes to the isolated lab; verify chain of custody.",
"Crack in stages: dictionary, dictionary+rules, targeted masks, full brute force (time-boxed).",
"Record per-stage crack rates and the time-to-crack distribution.",
"Analyze patterns: seasons, company names, keyboard walks — the policy failures made visible.",
"Destroy the hashes and results per the ROE after reporting (retain statistics, not values).",
"Deliver the password-policy verdict with specific policy recommendations.",
],
outputs=[
"Per-stage crack-rate statistics.",
"Password-pattern analysis.",
"Policy recommendations with evidence.",
"Destruction log for hash material.",
],
pitfalls=[
"Cracking outside the isolated lab — never on shared infrastructure.",
"Retaining cracked passwords beyond the report — statistics outlive values.",
"Presenting crack rates without the time-box context — methodology matters.",
],
references=[
"MITRE ATT&CK: Brute Force — Password Cracking (T1110.002).",
],
blue_note="their password policy gets an empirical verdict — crack-rate statistics are the evidence that changes policy.",
),
]
