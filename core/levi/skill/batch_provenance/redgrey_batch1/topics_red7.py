# Red team topics — chunk 7: exfiltration (8) + impact validation (12)

RED_7 = [
dict(
slug="exfil-over-dns",
title="DNS Exfiltration Test",
description="Test DNS exfiltration to validate DNS monitoring and data-loss controls.",
tags=["red-team","exfiltration","dns","dlp"],
risk="high", confirm=True,
blue_kw=["dns","exfiltration","dlp","monitoring"],
purpose=("DNS exfiltration moves data out through queries — the channel most environments barely "
"monitor. This test exfiltrates canary data via DNS and validates tunneling detection, query "
"logging, and DLP's DNS blindness."),
when=[
"During exfiltration phases.",
"To validate DNS tunneling/exfiltration detection.",
"To prove the DLP's DNS blind spot (or lack of one).",
],
prereq=[
"Authorization for exfiltration testing; canary data only, canary authoritative server.",
"DNS-team coordination.",
],
procedure=[
"Exfiltrate canary data via DNS TXT/NULL queries at varying rates and encoding densities.",
"Record detection: DNS logs, tunneling heuristics, DLP alerts (expect DLP silence — document it).",
"Test chunking and compression effects on detectability.",
"Measure maximum exfil rate before alerting (the detection threshold).",
"Tear down the canary server; verify no test domains remain.",
"Deliver the DNS-exfiltration assessment with monitoring recommendations.",
],
outputs=[
"DNS exfiltration detection results per rate/encoding.",
"Detection-threshold measurements.",
"DLP DNS-blindness documentation.",
],
pitfalls=[
"Real data over DNS — canary data only, always.",
"Exfil rates that degrade DNS service — rate-limit.",
],
references=[
"MITRE ATT&CK: Exfiltration Over C2 Channel — DNS (T1041 variants); DNS tunneling literature.",
],
blue_note="their DNS monitoring and DLP face the classic blind spot — canary data nobody noticed leaving via DNS is the finding.",
),
dict(
slug="exfil-over-https",
title="HTTPS Exfiltration Test",
description="Test HTTPS exfiltration to validate DLP, TLS inspection, and egress controls.",
tags=["red-team","exfiltration","https","dlp"],
risk="high", confirm=True,
blue_kw=["https","exfiltration","dlp","tls"],
purpose=("HTTPS is the exfiltration highway — encrypted, ubiquitous, trusted. This test exfiltrates "
"canary data over HTTPS to trusted and untrusted destinations, validating DLP content inspection, "
"TLS-interception coverage, and egress allowlisting."),
when=[
"During exfiltration phases.",
"To validate DLP HTTPS inspection and TLS-interception deployment.",
"To test egress filtering against trusted-domain exfil.",
],
prereq=[
"Authorization for exfiltration testing; canary data only.",
"DLP-team coordination for the inspection check.",
],
procedure=[
"Exfiltrate canary-pattern data over HTTPS POST to canary destinations (trusted-domain and untrusted).",
"Test with and without TLS interception: what does the DLP see in each case?",
"Vary the exfil: chunked uploads, compressed archives, encrypted blobs — record per-variant DLP results.",
"Test exfil to cloud storage and collaboration platforms (the trusted-domain path).",
"Verify all canary data destroyed at the destination.",
"Deliver the HTTPS-exfiltration assessment with inspection-coverage recommendations.",
],
outputs=[
"Per-variant DLP detection results.",
"TLS-interception coverage map.",
"Trusted-domain exfil findings.",
],
pitfalls=[
"Real sensitive data — canary patterns only.",
"Exfil to real external services — canary destinations only.",
],
references=[
"MITRE ATT&CK: Exfiltration Over Web Service (T1567).",
],
blue_note="their DLP's HTTPS visibility is what's measured — canary patterns leaving silently define the inspection gap.",
),
dict(
slug="cloud-exfil-test",
title="Cloud Exfiltration Test",
description="Test cloud-service exfiltration paths to validate CASB and cloud DLP.",
tags=["red-team","exfiltration","cloud","casb"],
risk="high", confirm=True,
blue_kw=["cloud","exfiltration","casb","dlp"],
purpose=("Cloud sync and storage turn exfiltration into 'normal' traffic. This test moves canary data "
"through cloud sync clients, storage APIs, and collaboration shares, validating CASB and cloud-DLP "
"detection of anomalous cloud exfil."),
when=[
"During exfiltration phases in cloud-heavy environments.",
"To validate CASB upload monitoring and cloud DLP.",
"To test personal-cloud-account vs. corporate-account controls.",
],
prereq=[
"Authorization for exfiltration testing; canary data only.",
"CASB-team coordination.",
],
procedure=[
"Exfiltrate canary data via corporate cloud sync, personal cloud accounts (canary), and direct storage APIs.",
"Test sharing-link exfil: anyone-with-link on canary data — does anything alert?",
"Record CASB and cloud-DLP verdicts per path.",
"Test large-archive uploads vs. trickle uploads.",
"Delete all canary data from cloud destinations; verify.",
"Deliver the cloud-exfiltration assessment.",
],
outputs=[
"Per-path cloud-exfil detection results.",
"Sharing-link alerting assessment.",
"CASB coverage findings.",
],
pitfalls=[
"Real data to personal cloud accounts — canary data only, canary accounts only.",
"Sharing links left active — verify deactivation.",
],
references=[
"MITRE ATT&CK: Exfiltration Over Web Service (T1567).",
],
blue_note="their CASB and cloud DLP face normal-looking exfil — silent canary uploads are the cloud-egress gap.",
),
dict(
slug="removable-media-exfil",
title="Removable Media Exfiltration Test",
description="Test USB/removable-media exfiltration to validate device-control policies.",
tags=["red-team","exfiltration","usb","device-control"],
risk="moderate", confirm=True,
blue_kw=["usb","device-control","exfiltration","dlp"],
purpose=("USB exfiltration bypasses every network control. This test copies canary data to authorized "
"test media and validates device-control enforcement: blocked, read-only, or silently permitted."),
when=[
"During exfiltration phases.",
"To validate USB device-control GPOs and DLP endpoint policies.",
"Combined with the BadUSB test for the full media-vector picture.",
],
prereq=[
"Authorization for removable-media use; canary data only; test USB devices.",
"Endpoint-team coordination.",
],
procedure=[
"Attempt canary-data copies to test USB devices on sample hosts.",
"Record per host: blocked, read-only, encrypted-only enforcement, or allowed.",
"Test bypass variants: MTP phones, SD cards, USB-CDROM emulation (authorized).",
"Check DLP endpoint: did the canary copy trigger endpoint DLP?",
"Verify no canary data remains on test media after the exercise (wipe).",
"Deliver the device-control assessment.",
],
outputs=[
"Per-host device-control enforcement results.",
"Bypass-variant findings.",
"Endpoint-DLP results.",
],
pitfalls=[
"Real data on test media — canary data only.",
"Test media leaving the facility with canary data — wipe and verify.",
"Forgetting non-USB removable paths (SD, MTP) — cover the variants.",
],
references=[
"MITRE ATT&CK: Exfiltration Over Physical Medium (T1052).",
],
blue_note="their device-control policy meets reality — silently permitted copies are the endpoint gap.",
),
dict(
slug="scheduled-exfil-test",
title="Scheduled Exfiltration Test",
description="Test scheduled/low-and-slow exfiltration to validate anomaly detection over time.",
tags=["red-team","exfiltration","scheduling","anomaly"],
risk="high", confirm=True,
blue_kw=["exfiltration","scheduling","anomaly-detection","dlp"],
purpose=("Low-and-slow exfiltration — small amounts on a schedule — defeats volume thresholds. This "
"time-boxed test exfiltrates canary data on a schedule and validates whether time-based anomaly "
"detection notices the pattern."),
when=[
"During exfiltration phases, as the stealth variant.",
"To validate UEBA time-series anomaly detection.",
"To tune DLP away from pure volume thresholds.",
],
prereq=[
"Authorization for exfiltration testing; canary data only; agreed schedule and total volume cap.",
"Longer time-box agreed with the blue team.",
],
procedure=[
"Exfiltrate canary data in small scheduled batches within the agreed volume cap.",
"Vary the schedule: business-hours blending vs. off-hours.",
"Monitor detection daily: did time-series analytics flag the pattern? When?",
"Test the threshold boundary: find the batch size/frequency that stays silent (within the cap).",
"Verify all canary data destroyed at the destination.",
"Deliver the scheduled-exfiltration assessment with analytics-tuning recommendations.",
],
outputs=[
"Detection timeline across the schedule.",
"Threshold-boundary measurements (within cap).",
"Time-series analytics findings.",
],
pitfalls=[
"Exceeding the volume cap — the cap is the authorization.",
"Running past the agreed time-box — schedule discipline.",
"Real data in the trickle — canary only.",
],
references=[
"MITRE ATT&CK: Exfiltration — scheduled transfer literature.",
],
blue_note="their time-based anomaly detection is under test — silent scheduled exfil within the cap is the analytics gap.",
),
dict(
slug="steganographic-exfil-test",
title="Steganographic Exfiltration Test",
description="Test image-embedded exfiltration to validate DLP content-inspection depth.",
tags=["red-team","exfiltration","steganography","dlp"],
risk="high", confirm=True,
blue_kw=["steganography","exfiltration","dlp","content-inspection"],
purpose=("Hiding data in images defeats content inspection that only reads text. This test exfiltrates "
"canary data embedded in images through email, web, and cloud channels, validating DLP's "
"content-depth honestly."),
when=[
"During advanced exfiltration phases.",
"To validate DLP image-analysis capabilities.",
"Paired with the steganography C2 test.",
],
prereq=[
"Authorization for exfiltration testing; canary data in canary images.",
"DLP-team coordination.",
],
procedure=[
"Embed canary data in images (LSB and transform-domain).",
"Exfiltrate via email attachments, web uploads, and cloud storage (canary destinations).",
"Record DLP verdicts per channel and per embedding method.",
"Test DLP image OCR/hash analysis against the carriers.",
"Destroy all carriers and recovered data.",
"Deliver the steganographic-exfiltration assessment with realistic scoping.",
],
outputs=[
"Per-channel/per-method DLP results.",
"Image-analysis capability findings.",
"Scoping recommendations (endpoint vs. content).",
],
pitfalls=[
"Real data in carriers — canary only.",
"Presenting undetectability as the conclusion — endpoint controls are the honest recommendation.",
],
references=[
"MITRE ATT&CK: Steganography (T1027.003).",
],
blue_note="their DLP content depth is honestly assessed — the usual outcome scopes detection to the endpoint.",
),
dict(
slug="exfil-size-limit-test",
title="Exfiltration Size-Limit Test",
description="Test DLP size thresholds and archive nesting to validate inspection completeness.",
tags=["red-team","exfiltration","dlp","archives"],
risk="moderate", confirm=True,
blue_kw=["exfiltration","dlp","archives","thresholds"],
purpose=("DLP often skips large files, deep archives, and encrypted blobs — the exact containers "
"exfiltration uses. This test probes those boundaries with canary data to map what the DLP "
"actually inspects."),
when=[
"During exfiltration phases.",
"To validate DLP inspection limits (size, depth, encryption).",
"To tune DLP policies with boundary evidence.",
],
prereq=[
"Authorization for exfiltration testing; canary data only.",
"DLP-team coordination.",
],
procedure=[
"Exfiltrate canary data in files of increasing size; find the size threshold where inspection stops.",
"Test archive nesting: canary data nested 5, 10, 20 deep — where does extraction stop?",
"Test encrypted archives: does the DLP block, allow, or quarantine what it can't read?",
"Test split archives and renamed extensions.",
"Deliver the DLP-boundary map with policy recommendations.",
],
outputs=[
"Size-threshold measurements.",
"Archive-depth boundary results.",
"Encrypted-container policy findings.",
],
pitfalls=[
"Real data in the test archives — canary only.",
"Crashing the DLP with pathological nesting — stay within sane bounds, coordinate.",
],
references=[
"DLP vendor documentation on inspection limits; MITRE T1027.",
],
blue_note="their DLP's inspection boundaries are mapped — every skipped container type is a policy decision to make explicitly.",
),
dict(
slug="data-encryption-impact",
title="Data Encryption Impact Validation",
description="Validate ransomware-style encryption impact in a lab to test backup and recovery controls.",
tags=["red-team","impact","ransomware","lab"],
risk="high", confirm=True,
blue_kw=["ransomware","impact","backups","recovery"],
purpose=("Ransomware impact is the scenario every backup strategy claims to survive. This lab test "
"encrypts canary data with ransomware-style techniques and validates the recovery story: backups "
"restore, in what time, with what loss — without ever touching production data."),
when=[
"Lab-only, as the ransomware-readiness validation.",
"To test backup restoration honestly (not just backup job success).",
"To validate EDR ransomware-behavior detection.",
],
prereq=[
"Isolated lab with canary data; explicit authorization for encryption testing.",
"Backup/recovery team participation — this is their drill too.",
"Never production systems or data.",
],
procedure=[
"Snapshot the lab; deploy canary data mirroring production structure.",
"Execute ransomware-style encryption (intermittent and full) against the canary data.",
"Record EDR behavior: did ransomware heuristics fire? How much was encrypted before containment?",
"Attempt recovery from backups: measure RTO, RPO, and integrity of restored data.",
"Test backup-target attacks: are the backups themselves reachable/deletable from the test context?",
"Restore the lab; deliver the ransomware-readiness report.",
],
outputs=[
"Encryption-vs-detection timeline.",
"Backup recovery measurements (RTO/RPO).",
"Backup-target security findings.",
],
pitfalls=[
"Any production contact — lab only, enforced by isolation.",
"Real ransomware samples — canary encryption routines only.",
"Declaring 'backups work' from job success — restoration is the test.",
],
references=[
"MITRE ATT&CK: Data Encrypted for Impact (T1486).",
],
blue_note="their ransomware readiness gets an honest drill — recovery measured in hours and data loss, not backup-job green lights.",
),
dict(
slug="wiper-impact-test",
title="Wiper Impact Validation Test",
description="Validate wiper-style destruction impact in a lab to test recovery and resilience.",
tags=["red-team","impact","wiper","lab"],
risk="high", confirm=True,
blue_kw=["wiper","impact","recovery","resilience"],
purpose=("Wipers don't ask for ransom — they destroy. This lab test simulates wiper-style destruction "
"against canary systems and validates the resilience story: what survives, what rebuilds, how fast.",
),
when=[
"Lab-only, for destructive-impact readiness.",
"To validate bare-metal recovery and rebuild runbooks.",
"When the threat model includes nation-state actors.",
],
prereq=[
"Isolated lab; explicit authorization for destructive testing.",
"Rebuild-team participation.",
],
procedure=[
"Snapshot everything; prepare the rebuild runbook as the test subject.",
"Execute wiper-style destruction (MBR/partition concepts, file wiping) against canary lab systems.",
"Record EDR behavior during the destruction.",
"Execute the rebuild runbook: measure time to operational, data loss, and runbook gaps.",
"Test offline backups and gold images as the recovery path.",
"Deliver the wiper-readiness report.",
],
outputs=[
"Destruction-vs-detection timeline.",
"Rebuild measurements and runbook gaps.",
"Offline-recovery findings.",
],
pitfalls=[
"Lab escape — network-isolated, snapshot-backed, no exceptions.",
"Real wiper samples — canary destruction routines.",
"Skipping the rebuild — the rebuild IS the test.",
],
references=[
"MITRE ATT&CK: Data Destruction (T1485), Disk Wipe (T1561).",
],
blue_note="their destructive-attack resilience is drilled — rebuild time is the metric that matters.",
),
dict(
slug="defacement-impact-test",
title="Website Defacement Impact Test",
description="Test web-defacement scenarios to validate web-integrity monitoring and recovery.",
tags=["red-team","impact","defacement","web"],
risk="moderate", confirm=True,
blue_kw=["defacement","web","integrity","monitoring"],
purpose=("Defacement is reputational impact with a technical path. This test validates web-content "
"integrity monitoring and the recovery path using canary defacements on staging — never production.",
),
when=[
"During impact phases, against staging/test web properties.",
"To validate file-integrity monitoring on web roots.",
"To test the web-recovery runbook.",
],
prereq=[
"Authorization for the staging web properties; canary defacement content.",
"Web-team coordination.",
],
procedure=[
"Deploy canary defacement content to the staging web root via the authorized path.",
"Measure detection: FIM alerts, uptime/content monitoring, SOC notification time.",
"Execute the web-recovery runbook: time to restore, integrity verification.",
"Test the attack path that enabled it (writable web root, compromised CMS creds) — report separately.",
"Verify staging is clean and the runbook updated.",
"Deliver the defacement-readiness report.",
],
outputs=[
"Defacement-detection timeline.",
"Recovery measurements.",
"Attack-path findings.",
],
pitfalls=[
"Production web properties — staging only.",
"Offensive defacement content — neutral canary content.",
],
references=[
"MITRE ATT&CK: Defacement (T1491).",
],
blue_note="their web-integrity monitoring is drilled — detection and recovery time are the scored outcomes.",
),
dict(
slug="dos-resilience-test",
title="Denial-of-Service Resilience Test",
description="Test DoS resilience with controlled load to validate mitigation and capacity planning.",
tags=["red-team","impact","dos","resilience"],
risk="moderate", confirm=True,
blue_kw=["dos","resilience","capacity","mitigation"],
purpose=("DoS is impact without intrusion. This controlled test applies agreed load levels against "
"staging or explicitly authorized targets, validating DDoS mitigation, rate limiting, and capacity "
"headroom — never as an uncontrolled flood."),
when=[
"During impact phases, with explicit load-testing authorization.",
"To validate DDoS-mitigation service effectiveness.",
"To measure capacity headroom before peak seasons.",
],
prereq=[
"Explicit authorization with load ceilings, time windows, and target scope.",
"NetOps and mitigation-vendor coordination.",
],
procedure=[
"Ramp load gradually against the authorized target within the agreed ceiling.",
"At each level, measure: availability, latency, mitigation engagement.",
"Test layer-7 patterns (slowloris-style, expensive endpoints) separately from volumetric.",
"Verify the mitigation service's detection and scrubbing behavior.",
"Stop at the ceiling or at first customer impact — whichever comes first.",
"Deliver the DoS-resilience report with capacity recommendations.",
],
outputs=[
"Load-vs-availability measurements per level.",
"Mitigation-engagement analysis.",
"Capacity recommendations.",
],
pitfalls=[
"Exceeding the load ceiling — the ceiling is the authorization.",
"Testing production without explicit approval and a maintenance window.",
"Layer-7 tests that look like real attacks to upstream providers — coordinate.",
],
references=[
"MITRE ATT&CK: Network Denial of Service (T1498).",
],
blue_note="their DoS mitigation gets measured, not assumed — the load level where mitigation engages is the finding.",
),
dict(
slug="firmware-impact-test",
title="Firmware Impact Validation Test",
description="Validate firmware-attack impact concepts in a lab to test hardware-root-of-trust controls.",
tags=["red-team","impact","firmware","lab"],
risk="high", confirm=True,
blue_kw=["firmware","impact","hardware","lab"],
purpose=("Firmware attacks persist below the OS and survive reinstallation. This lab test validates "
"firmware-integrity controls — Secure Boot, measured boot, firmware update signing — against "
"canary firmware-tampering concepts, without bricking real hardware.",
),
when=[
"Lab-only, with sacrificial or virtualized hardware.",
"To validate Secure Boot and measured-boot attestation.",
"When the threat model includes firmware persistence.",
],
prereq=[
"Lab hardware/VMs designated sacrificial; explicit authorization.",
"Firmware-team/vendor coordination.",
],
procedure=[
"Baseline firmware measurements (PCR values, Secure Boot state) on lab systems.",
"Attempt canary firmware modifications (unsigned option ROM concepts, boot-variable tampering).",
"Verify which modifications Secure Boot/measured boot blocked or detected.",
"Test firmware-update signing: does the updater accept a canary unsigned image?",
"Test recovery: can the lab system recover via known-good firmware?",
"Deliver the firmware-integrity assessment.",
],
outputs=[
"Firmware-tampering block/detect results.",
"Update-signing verification results.",
"Recovery-path findings.",
],
pitfalls=[
"Real hardware outside the sacrificial lab — bricking risk is real.",
"Disabling Secure Boot 'to test deeper' without explicit approval.",
],
references=[
"MITRE ATT&CK: Firmware Corruption (T1495); NIST SP 800-147/155.",
],
blue_note="their hardware root of trust is validated — firmware the platform accepts unsigned is the finding.",
),
dict(
slug="sabotage-scenario-test",
title="Sabotage Scenario Test",
description="Exercise insider-sabotage scenarios as a tabletop-plus-validation drill.",
tags=["red-team","impact","sabotage","insider"],
risk="low", confirm=False,
blue_kw=["sabotage","insider","impact","exercise"],
purpose=("Sabotage by a trusted insider is the impact scenario technical controls handle worst. This "
"exercise — tabletop plus canary validation — tests what a malicious insider could destroy and "
"which controls would slow or catch them.",
),
when=[
"As a joint exercise with HR/legal/security leadership.",
"To validate insider-threat controls and separation of duties.",
"To test backup and recovery against the malicious-admin case.",
],
prereq=[
"Exercise authorization with leadership; canary systems/data.",
"Legal/HR coordination — insider scenarios are sensitive.",
],
procedure=[
"Tabletop: walk the malicious-insider scenarios (data destruction, logic bombs, credential abuse).",
"Validate technically with canary actions: what CAN the test insider account actually destroy?",
"Check separation of duties: can one account both destroy and delete the backups?",
"Test detection: would the canary sabotage alert anyone?",
"Deliver the sabotage-readiness report with control recommendations.",
],
outputs=[
"Scenario walkthrough with feasibility ratings.",
"Canary-validation results.",
"Separation-of-duties findings.",
],
pitfalls=[
"Real destructive actions — canary only, always.",
"Framing findings as accusations — this tests controls, not people.",
],
references=[
"Insider-threat literature (CERT, CISA).",
],
blue_note="their insider-threat posture is exercised — single points of destructive trust are the findings.",
),
dict(
slug="ransomware-negotiation-drill",
title="Ransomware Negotiation Drill",
description="Drill ransomware negotiation and decision-making as a tabletop exercise.",
tags=["red-team","impact","ransomware","exercise"],
risk="low", confirm=False,
blue_kw=["ransomware","negotiation","exercise","incident-response"],
purpose=("The ransom decision gets made under pressure — this drill makes it beforehand. A tabletop "
"exercise walking leadership through the ransom demand, the legal constraints, and the recovery "
"math, so the real incident isn't the first discussion.",
),
when=[
"As a leadership tabletop, independent of technical phases.",
"After the ransomware-impact lab test, using its recovery numbers.",
"To validate cyber-insurance and legal notification workflows.",
],
prereq=[
"Leadership participation; legal counsel involvement.",
"Recovery metrics from the lab test as input.",
],
procedure=[
"Present the scenario: canary ransomware event with the lab's real recovery numbers.",
"Walk the decision tree: pay vs. rebuild, legal constraints, notification obligations.",
"Test the communications plan: who speaks, what gets said, when.",
"Validate the insurance notification workflow and coverage understanding.",
"Deliver the drill report with decision-playbook recommendations.",
],
outputs=[
"Decision-tree walkthrough with leadership positions.",
"Communications-plan gaps.",
"Insurance/legal workflow findings.",
],
pitfalls=[
"Making the actual pay/don't-pay decision in the drill — the drill builds the playbook, leadership decides in the moment.",
"Skipping legal — ransom payments have sanctions implications.",
],
references=[
"CISA ransomware guidance; FBI IC3 guidance.",
],
blue_note="their leadership gets the ransom decision before the crisis — the playbook is the deliverable.",
),
dict(
slug="backup-destruction-test",
title="Backup Destruction Test",
description="Test backup-target attacks to validate backup immutability and isolation.",
tags=["red-team","impact","backups","ransomware"],
risk="high", confirm=True,
blue_kw=["backups","destruction","immutability","ransomware"],
purpose=("Modern ransomware kills the backups first. This test attacks canary backup targets with "
"the compromised-context credentials, validating immutability, air-gapping, and whether backup "
"deletion alerts anyone.",
),
when=[
"During impact phases, against canary backup targets.",
"To validate backup immutability (object lock, air gap).",
"Paired with the ransomware-impact lab test.",
],
prereq=[
"Authorization for backup-target testing; canary backup data.",
"Backup-team participation — this is their control being tested.",
],
procedure=[
"From the compromised test context, attempt backup deletion, encryption, and retention-policy changes.",
"Test immutability: does object lock / air gap actually stop the deletion?",
"Record alerting: did backup-tampering generate any alert, and how fast?",
"Test the backup-console: can the attacker pivot through the backup software itself?",
"Verify canary backups intact afterward; restore one as proof.",
"Deliver the backup-resilience report.",
],
outputs=[
"Backup-attack results per technique.",
"Immutability-verification evidence.",
"Backup-tampering alert timeline.",
],
pitfalls=[
"Production backup targets — canary targets only.",
"Actually deleting backups even as a test — immutability should stop you; verify, don't force.",
],
references=[
"MITRE ATT&CK: Inhibit System Recovery (T1490).",
],
blue_note="their backup strategy faces the attack it's designed for — deletable backups are the finding that matters most.",
),
dict(
slug="endpoint-encryption-drill",
title="Endpoint Encryption Drill",
description="Drill mass endpoint-encryption scenarios to validate EDR and recovery at scale.",
tags=["red-team","impact","ransomware","endpoints"],
risk="moderate", confirm=True,
blue_kw=["endpoints","encryption","ransomware","recovery"],
purpose=("Ransomware at fleet scale is a different problem than one host. This drill encrypts canary "
"data across lab endpoints simultaneously, validating EDR fleet-wide response, isolation at scale, "
"and mass-recovery procedures.",
),
when=[
"Lab-only fleet drill, during impact phases.",
"To validate SOC fleet-wide response procedures.",
"To test mass-recovery tooling and imaging pipelines.",
],
prereq=[
"Lab endpoint fleet; explicit authorization for simultaneous encryption.",
"Canary data on all lab endpoints.",
],
procedure=[
"Snapshot the lab fleet; deploy canary data.",
"Trigger simultaneous canary encryption across the fleet.",
"Measure SOC response: time to fleet-wide isolation, containment completeness.",
"Execute mass recovery: imaging pipeline throughput, data restoration.",
"Test the EDR's automated response at scale (did it keep up?).",
"Restore the fleet; deliver the mass-impact drill report.",
],
outputs=[
"Fleet-wide detection/containment timeline.",
"Mass-recovery throughput measurements.",
"EDR-at-scale findings.",
],
pitfalls=[
"Any production endpoint in the fleet — lab only.",
"Real ransomware samples — canary encryption.",
"Skipping the recovery — mass recovery is the scored outcome.",
],
references=[
"MITRE ATT&CK: Data Encrypted for Impact (T1486).",
],
blue_note="their fleet-scale response is drilled — containment and recovery at scale are the measured outcomes.",
),
dict(
slug="data-leak-site-drill",
title="Data Leak-Site Drill",
description="Drill the data-leak-site extortion scenario as a communications and legal exercise.",
tags=["red-team","impact","extortion","exercise"],
risk="low", confirm=False,
blue_kw=["extortion","leak-site","ransomware","exercise"],
purpose=("Double extortion adds a leak site to the ransom — this drill walks the team through the "
"scenario: canary data 'published', notification obligations, and the communications response.",
),
when=[
"As a tabletop with legal, comms, and leadership.",
"After exfiltration testing, using realistic scenario inputs.",
"To validate breach-notification workflows.",
],
prereq=[
"Exercise authorization; canary data for the scenario.",
"Legal and communications participation.",
],
procedure=[
"Present the scenario: canary data appears on a simulated leak site.",
"Walk notification obligations: regulators, customers, timelines.",
"Test the takedown options: what can actually be done about the leak site?",
"Exercise the communications response: holding statements, customer notifications.",
"Validate the forensics question: what data was actually taken (the exfil tests inform this)?",
"Deliver the drill report with notification-playbook updates.",
],
outputs=[
"Notification-obligation walkthrough.",
"Takedown-option analysis.",
"Communications-plan updates.",
],
pitfalls=[
"Real data on a real leak site — simulated scenario only.",
"Skipping the forensics input — the exfil tests determine what's actually at risk.",
],
references=[
"CISA/ FBI guidance on double-extortion ransomware.",
],
blue_note="their extortion response is drilled before it's needed — notification readiness is the deliverable.",
),
dict(
slug="recovery-time-drill",
title="Recovery Time Drill",
description="Drill full recovery timing to validate RTO/RPO claims against reality.",
tags=["red-team","impact","recovery","rto"],
risk="low", confirm=False,
blue_kw=["recovery","rto","rpo","resilience"],
purpose=("RTO/RPO numbers in the BCP are claims until drilled. This exercise times a full recovery "
"of canary systems from backups, producing the honest numbers leadership plans against.",
),
when=[
"As a resilience drill, independent of attack phases.",
"To validate business-continuity plan recovery claims.",
"After backup-restoration tests, at full-system scale.",
],
prereq=[
"Canary systems and data; recovery-team participation.",
"Agreed drill scope and success criteria.",
],
procedure=[
"Declare the drill: canary systems 'lost', recovery begins.",
"Time every phase: backup location, restoration, configuration, validation, handover.",
"Record gaps: missing credentials, undocumented steps, broken runbook links.",
"Compare measured RTO/RPO against the BCP claims.",
"Deliver the recovery-timing report with runbook fixes.",
],
outputs=[
"Measured RTO/RPO per system.",
"BCP-claim vs. reality deltas.",
"Runbook gap list.",
],
pitfalls=[
"Declaring success at 'data restored' — recovery means operational, validated, handed over.",
"Drilling only the easy systems — include the hard ones.",
],
references=[
"NIST SP 800-34 (contingency planning).",
],
blue_note="their recovery claims get timed honestly — the delta between BCP numbers and drill numbers is the finding.",
),
dict(
slug="impact-cleanup-verification",
title="Impact Exercise Cleanup Verification",
description="Verify complete cleanup after impact exercises to validate range hygiene.",
tags=["red-team","impact","cleanup","hygiene"],
risk="low", confirm=False,
blue_kw=["impact","cleanup","verification","hygiene"],
purpose=("Impact exercises are destructive by design — this verification pass proves the range is "
"clean afterward: no canary encryption, no test backups altered, no drill artifacts left to "
"confuse future operations.",
),
when=[
"After every impact exercise, as the mandatory close-out.",
"Before the range is returned to general use.",
],
prereq=[
"Inventory of all impact-exercise artifacts.",
],
procedure=[
"Enumerate all impact-test artifacts: encrypted canary data, test backups, drill systems.",
"Verify lab systems restored to pre-exercise snapshots.",
"Confirm backup targets untouched (canary backups verified intact).",
"Check for leftover scheduled tasks, services, or accounts from the exercises.",
"Sign off the range-clean certificate with the blue team.",
"Deliver the cleanup-verification report.",
],
outputs=[
"Artifact inventory with disposition.",
"Snapshot-restoration verification.",
"Range-clean sign-off.",
],
pitfalls=[
"Assuming the snapshot restore worked — verify, then sign.",
"Rushing close-out — cleanup verification is a phase, not an afterthought.",
],
references=[
"Exercise-hygiene best practices (internal).",
],
blue_note="their range hygiene is verified — a clean range is the precondition for the next exercise.",
),
]
