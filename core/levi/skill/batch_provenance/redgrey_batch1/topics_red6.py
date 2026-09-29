# Red team topics — chunk 6: collection (8) + command & control (10)

RED_6 = [
dict(
slug="audio-video-capture-test",
title="Audio/Video Capture Validation Test",
description="Test audio/video capture capabilities to validate DLP and endpoint-monitoring controls.",
tags=["red-team","collection","audio","video"],
risk="moderate", confirm=True,
blue_kw=["audio","video","collection","dlp"],
purpose=("Audio and video capture turn a compromised host into a bug. This test validates — with "
"canary recordings only — whether capture APIs are monitored, whether DLP covers multimedia, and "
"whether the environment has any technical barrier to covert recording."),
when=[
"During collection phases, with explicit AV-capture authorization.",
"To validate endpoint controls against covert recording.",
"When the threat model includes espionage.",
],
prereq=[
"Explicit authorization for audio/video capture testing; canary recordings only, immediately destroyed.",
"User notification per the ROE where legally required.",
],
procedure=[
"Test microphone capture via standard APIs with a canary recording (seconds, destroyed immediately).",
"Test screen capture and webcam access the same way.",
"Record telemetry: did any EDR/DLP rule fire on capture-API use?",
"Check for technical barriers: are cameras/mics disabled by policy on sensitive hosts?",
"Verify all canary recordings are destroyed; log the destruction.",
"Deliver the AV-capture assessment with policy and monitoring recommendations.",
],
outputs=[
"Capture-API detection results per modality.",
"Policy-barrier inventory (disabled devices).",
"Canary-recording destruction log.",
],
pitfalls=[
"Real recordings of real people without consent — canary only, destroy immediately.",
"Testing on hosts where recording is legally restricted without legal review.",
"Forgetting that screen capture includes credentials on screen — canary desktops only.",
],
references=[
"MITRE ATT&CK: Audio Capture (T1123), Video Capture (T1125).",
],
blue_note="their endpoint posture against covert collection is under test — unmonitored capture APIs are an espionage-readiness gap.",
),
dict(
slug="keylogging-detection-test",
title="Keylogging Detection Test",
description="Test keylogging techniques to validate behavioral detection of input capture.",
tags=["red-team","collection","keylogging","detection"],
risk="moderate", confirm=True,
blue_kw=["keylogging","input-capture","collection","detection"],
purpose=("Keyloggers capture credentials at the source. This test deploys canary keyloggers — API "
"hooks, raw input, kernel concepts discussed-only — and validates whether behavioral detection "
"catches input-capture techniques."),
when=[
"During collection phases on Windows.",
"To validate EDR behavioral rules for input-capture APIs.",
"To test user-awareness: do users notice the canary keylogger's indicators?",
],
prereq=[
"Authorization for input-capture testing on test hosts.",
"Canary keystrokes only; captured data destroyed immediately.",
],
procedure=[
"Deploy a canary keylogger using SetWindowsHookEx on the test host; type canary credentials.",
"Test raw-input and GetAsyncKeyState polling variants.",
"Record per variant: EDR alert, API-monitoring events, and whether canary keystrokes were captured.",
"Verify the captured canary data, then destroy it and remove the keylogger.",
"Kernel keylogger concepts: discuss and validate driver-signing policy instead of deploying.",
"Deliver the input-capture detection assessment.",
],
outputs=[
"Per-variant keylogger detection results.",
"Canary-capture verification and destruction log.",
"Driver-signing policy assessment.",
],
pitfalls=[
"Capturing real user keystrokes — canary input sessions only, scheduled and supervised.",
"Kernel keyloggers on real hardware — concepts and policy only.",
"Leaving the keylogger installed — removal verified, not assumed.",
],
references=[
"MITRE ATT&CK: Input Capture — Keylogging (T1056.001).",
],
blue_note="their behavioral detection of input capture is under test — silent keyloggers are a credential-theft gap.",
),
dict(
slug="credentialed-file-collection",
title="Credentialed File Collection Test",
description="Test automated file collection to validate DLP and file-access monitoring.",
tags=["red-team","collection","files","dlp"],
risk="low", confirm=False,
blue_kw=["collection","files","dlp","monitoring"],
purpose=("Automated collection — staging documents for exfiltration — has a recognizable pattern: "
"bulk reads, archive creation, staging directories. This test performs canary collection and "
"validates whether file-access monitoring and DLP notice the staging behavior."),
when=[
"During collection phases.",
"To validate DLP and file-access anomaly detection.",
"Before exfiltration phases, to test the staging half.",
],
prereq=[
"Authorization for bulk file operations on test data; canary files.",
"DLP team coordination for the detection check.",
],
procedure=[
"Plant canary sensitive files across test locations.",
"Perform staged collection: bulk copy to a staging directory, archive creation, archive encryption.",
"Record telemetry: file-access events, DLP alerts on the canary patterns, archive-creation monitoring.",
"Test collection via cloud-sync folders and removable media paths (authorized).",
"Clean the staging directory and all canary files; verify.",
"Deliver the collection-behavior detection assessment.",
],
outputs=[
"Collection-stage detection results per technique.",
"DLP canary-pattern results.",
"Cleanup verification.",
],
pitfalls=[
"Collecting real sensitive files — canary files only.",
"Archive encryption that looks like ransomware to the SOC — coordinate in advance.",
"Forgetting the staging directory in cleanup — verify empty.",
],
references=[
"MITRE ATT&CK: Automated Collection (T1119), Data Staged (T1074).",
],
blue_note="their DLP and file-access monitoring face bulk-collection behavior — silent staging is the pre-exfiltration gap.",
),
dict(
slug="email-collection-test",
title="Email Collection Test",
description="Test mailbox collection rules and exports to validate email-security monitoring.",
tags=["red-team","collection","email","exfiltration"],
risk="moderate", confirm=True,
blue_kw=["email","collection","mailbox","monitoring"],
purpose=("Attackers collect email with inbox rules (forwarding, auto-BCC) and bulk exports. This "
"test creates canary collection rules and validates whether mailbox-auditing and email-security "
"controls detect them."),
when=[
"During collection phases in M365/Google Workspace.",
"To validate inbox-rule alerting and mailbox-audit logging.",
"After phishing tests, as the post-compromise email-persistence check.",
],
prereq=[
"Authorization for the test mailboxes; canary rules only.",
"Mail-admin coordination for audit-log verification.",
],
procedure=[
"Create canary inbox rules: forward-to-external (canary address), move-to-RSS, mark-read-and-move.",
"Perform a canary mailbox export (eDiscovery-style, authorized) and record the audit trail.",
"Monitor detection: did rule-creation alert? Did the export generate the expected audit events?",
"Test the hidden-rule variant (rule with no client-visible UI change) where applicable.",
"Remove all canary rules; verify via audit log and rule enumeration.",
"Deliver the email-collection monitoring assessment.",
],
outputs=[
"Per-rule detection results.",
"Export audit-trail assessment.",
"Rule-removal verification.",
],
pitfalls=[
"Forwarding to real external addresses — canary addresses only.",
"Exporting real mailboxes beyond the canary scope — scope strictly.",
"Leaving rules behind — enumerate and verify removal.",
],
references=[
"MITRE ATT&CK: Email Collection (T1114).",
],
blue_note="their mailbox auditing and inbox-rule alerting are under test — silent forwarding rules are the business-email-compromise gap.",
),
dict(
slug="cloud-storage-collection",
title="Cloud Storage Collection Test",
description="Test cloud-storage enumeration and collection to validate CASB and DLP coverage.",
tags=["red-team","collection","cloud","dlp"],
risk="low", confirm=False,
blue_kw=["cloud","storage","collection","casb"],
purpose=("Cloud storage — drives, buckets, SharePoint — is where the data actually lives now. This "
"test enumerates and samples cloud storage with read-only roles, validating CASB visibility, "
"sharing-link governance, and cloud DLP."),
when=[
"During cloud collection phases.",
"To validate CASB discovery and cloud DLP policies.",
"To audit sharing-link exposure.",
],
prereq=[
"Authorization for the cloud tenants; read-only test roles.",
"Canary files planted for DLP validation.",
],
procedure=[
"Enumerate cloud storage: drives, buckets, SharePoint sites visible to the test role.",
"Audit sharing links: anyone-with-link exposures of canary and real sensitive locations (counts, not content).",
"Test the canary DLP: do canary-pattern files trigger cloud DLP policies?",
"Sample access logging: is storage access logged and is the test enumeration visible?",
"Deliver the cloud-storage exposure and DLP assessment.",
],
outputs=[
"Cloud-storage inventory with exposure analysis.",
"Sharing-link audit results.",
"Cloud DLP canary results.",
],
pitfalls=[
"Downloading real sensitive data — enumerate metadata, sample canaries.",
"Testing sharing links by accessing them externally without approval — audit, don't exploit.",
],
references=[
"MITRE ATT&CK: Cloud Storage Object Discovery; CSA guidance.",
],
blue_note="their CASB and cloud DLP are under test — anyone-with-link exposures are the cloud sharing finding.",
),
dict(
slug="database-collection-test",
title="Database Collection Test",
description="Test database dumping and query patterns to validate database-activity monitoring.",
tags=["red-team","collection","database","monitoring"],
risk="moderate", confirm=True,
blue_kw=["database","collection","monitoring","dam"],
purpose=("Databases hold the crown jewels in queryable form. This test performs canary database "
"dumps and anomalous query patterns against test databases, validating database-activity "
"monitoring and access controls."),
when=[
"During collection phases where databases are in scope.",
"To validate DAM tooling and query-anomaly alerting.",
"To test backup-file security as the alternate collection path.",
],
prereq=[
"Authorization for the test databases; canary data.",
"DBA coordination for monitoring verification.",
],
procedure=[
"Perform canary dumps (full and selective) via standard tooling; record telemetry.",
"Run anomalous query patterns: full-table scans, off-hours bulk selects, new-client connections.",
"Test backup-file access: are backup files readable by the test context?",
"Record which activities the DAM/monitoring flagged and which were silent.",
"Verify no canary data left the test database scope.",
"Deliver the database-monitoring assessment.",
],
outputs=[
"Dump and query-pattern detection results.",
"Backup-file access findings.",
"DAM coverage assessment.",
],
pitfalls=[
"Dumping production databases — test databases with canary data only.",
"Bulk queries that load production-adjacent systems — coordinate timing.",
],
references=[
"MITRE ATT&CK: Automated Collection; database-security literature.",
],
blue_note="their database-activity monitoring is under test — silent bulk extraction is the DAM gap.",
),
dict(
slug="memory-scraping-test",
title="Memory Scraping Test",
description="Test memory-scraping techniques to validate EDR memory protection.",
tags=["red-team","collection","memory","pos"],
risk="moderate", confirm=True,
blue_kw=["memory","scraping","collection","edr"],
purpose=("Memory scraping reads secrets straight from process memory — PANs, keys, tokens. This test "
"scrapes canary secrets from test processes and validates whether EDR memory-protection and "
"read-monitoring catch it."),
when=[
"During collection phases.",
"To validate EDR protections on sensitive processes.",
"When the threat model includes POS-style or secret-harvesting malware.",
],
prereq=[
"Authorization for memory-read operations on test processes.",
"Canary secrets in test process memory only.",
],
procedure=[
"Plant canary secrets (fake PANs, tokens) in test process memory.",
"Scrape process memory with authorized tooling; verify canary recovery.",
"Record EDR telemetry: process-memory-read events, alerts.",
"Test protected processes: does PPL or EDR self-protection block the scrape?",
"Verify no real process memory was read beyond the test processes.",
"Deliver the memory-protection assessment.",
],
outputs=[
"Memory-scrape success/detection per process type.",
"Protected-process effectiveness results.",
"Scope-compliance verification.",
],
pitfalls=[
"Scraping real processes (browsers, password managers) without approval — test processes only.",
"Recovered canary secrets handled per the credential ROE anyway — build the habit.",
],
references=[
"MITRE ATT&CK: Credential material from memory; POS-malware literature.",
],
blue_note="their EDR memory protections are under test — unalerted scraping of sensitive processes is a memory-monitoring gap.",
),
dict(
slug="screen-capture-ops-test",
title="Screen Capture Operations Test",
description="Test systematic screen capture to validate DLP and insider-threat monitoring.",
tags=["red-team","collection","screen-capture","dlp"],
risk="moderate", confirm=True,
blue_kw=["screen-capture","collection","dlp","insider"],
purpose=("Systematic screenshotting captures whatever the user sees — including credentials and "
"sensitive documents. This test runs canary screen-capture sessions and validates whether DLP, "
"EDR, or insider-threat tooling notices."),
when=[
"During collection phases, with explicit authorization.",
"To validate insider-threat monitoring coverage.",
"To test DLP's handling of image-based exfiltration.",
],
prereq=[
"Explicit authorization for screen capture; canary desktop sessions only.",
"User notification per the ROE.",
],
procedure=[
"Run a canary screen-capture session on the test host (time-boxed, canary desktop).",
"Record telemetry: EDR alerts on capture APIs, DLP image analysis, insider-threat tooling.",
"Test exfiltration of the screenshots via the authorized exfil channel (canary).",
"Verify all screenshots destroyed after analysis.",
"Deliver the screen-capture detection assessment.",
],
outputs=[
"Capture-session detection results.",
"Screenshot-exfiltration test results.",
"Destruction verification.",
],
pitfalls=[
"Capturing real user desktops — canary sessions only.",
"Screenshots retained beyond the analysis — destroy per the ROE.",
],
references=[
"MITRE ATT&CK: Screen Capture (T1113).",
],
blue_note="their insider-threat and DLP image handling are under test — silent systematic capture is the insider-monitoring gap.",
),
dict(
slug="dns-c2-test",
title="DNS Command-and-Control Test",
description="Test DNS-based C2 channels to validate DNS monitoring and filtering.",
tags=["red-team","command-and-control","dns","c2"],
risk="high", confirm=True,
blue_kw=["dns","c2","command-and-control","monitoring"],
purpose=("DNS is the protocol most likely to be allowed out — making it the classic covert channel. "
"This test exercises DNS tunneling and DNS-based C2 signaling with canary traffic, validating DNS "
"logging, tunneling detection, and resolver policy."),
when=[
"During C2 phases.",
"To validate DNS security monitoring (query volume, entropy, tunneling heuristics).",
"To test DNS filtering/allowlisting effectiveness.",
],
prereq=[
"Authorization for covert-channel testing; canary C2 infrastructure in the lab.",
"DNS-team coordination for log verification.",
],
procedure=[
"Stand up canary DNS C2 infrastructure (lab authoritative server).",
"Exercise DNS tunneling with canary data at varying volumes and encoding densities.",
"Test DNS-based signaling (TXT queries, subdomain encoding) separately from bulk tunneling.",
"Record detection: DNS logs, tunneling heuristics, firewall DNS-inspection alerts.",
"Test against the filtering policy: are unauthorized resolvers (DoH/DoT) reachable?",
"Tear down the canary infrastructure; verify no test domains remain active.",
"Deliver the DNS-channel assessment with monitoring recommendations.",
],
outputs=[
"Per-technique DNS detection results.",
"Volume/entropy detection thresholds observed.",
"DoH/DoT bypass findings.",
],
pitfalls=[
"Real C2 infrastructure outside the lab — canary infrastructure only.",
"High-volume tunneling that impacts DNS performance — rate-limit the test.",
"Forgetting to tear down test domains — verify deactivation.",
],
references=[
"MITRE ATT&CK: Application Layer Protocol — DNS (T1071.004), DNS tunneling literature.",
],
blue_note="their DNS monitoring is under test — high-entropy query streams nobody flagged are a DNS-security gap.",
),
dict(
slug="https-c2-test",
title="HTTPS Command-and-Control Test",
description="Test HTTPS-based C2 to validate TLS inspection and beaconing detection.",
tags=["red-team","command-and-control","https","c2"],
risk="high", confirm=True,
blue_kw=["https","c2","command-and-control","tls"],
purpose=("HTTPS C2 hides in the web's noise. This test runs canary HTTPS beacons with varying "
"profiles — intervals, jitter, JA3, domain fronting concepts — and validates beaconing detection, "
"TLS-inspection policy, and proxy logging."),
when=[
"During C2 phases.",
"To validate network beaconing analytics.",
"To test TLS-inspection coverage and proxy-log completeness.",
],
prereq=[
"Authorization for C2 testing; canary beacon infrastructure.",
"NetOps coordination for log verification.",
],
procedure=[
"Run canary HTTPS beacons at fixed intervals; check beaconing analytics for detection.",
"Vary the profile: jitter, randomized intervals, domain rotation, user-agent spoofing.",
"Test TLS-inspection: is the canary traffic decrypted and logged, or does it pass opaque?",
"Record proxy logs: are the beacon domains and JA3 fingerprints visible?",
"Test long-polling and websocket variants as alternate HTTPS channels.",
"Tear down beacons; verify no test infrastructure remains.",
"Deliver the HTTPS-C2 detection assessment.",
],
outputs=[
"Beaconing-detection results per profile.",
"TLS-inspection coverage findings.",
"Proxy-log completeness assessment.",
],
pitfalls=[
"Beaconing at volumes that trigger upstream abuse alerts — coordinate and rate-limit.",
"Real C2 frameworks' default profiles without customization — that's the attacker's laziness, test both.",
],
references=[
"MITRE ATT&CK: Application Layer Protocol — Web Protocols (T1071.001).",
],
blue_note="their network analytics face realistic beaconing — regular beacons nobody flagged are a network-detection gap.",
),
dict(
slug="domain-fronting-test",
title="Domain Fronting Validation Test",
description="Test domain-fronting concepts to validate SNI inspection and CDN controls.",
tags=["red-team","command-and-control","domain-fronting"],
risk="high", confirm=True,
blue_kw=["domain-fronting","sni","command-and-control","cdn"],
purpose=("Domain fronting hides the true destination behind a trusted front domain. This test "
"validates — with canary traffic — whether SNI inspection, CDN policies, and proxy controls "
"would distinguish fronted traffic from legitimate CDN use."),
when=[
"During C2 phases, where CDN usage is heavy.",
"To validate SNI-visibility and fronting-detection controls.",
"As a TLS-inspection complement.",
],
prereq=[
"Authorization for the test; canary front/back infrastructure.",
"Understanding of current CDN fronting mitigations (many CDNs now block it — the test verifies).",
],
procedure=[
"Attempt canary domain-fronted connections through the CDNs in use.",
"Record whether the CDN blocked the fronting (many now do) and whether the proxy distinguished the traffic.",
"Test the SNI-visibility: what does the monitoring see — front domain, back domain, or neither?",
"Document which CDNs permit fronting-like patterns and which block.",
"Tear down canary infrastructure.",
"Deliver the fronting assessment with SNI-inspection recommendations.",
],
outputs=[
"Per-CDN fronting feasibility results.",
"SNI-visibility assessment.",
"Monitoring recommendations.",
],
pitfalls=[
"Assuming fronting still works everywhere — verify per CDN, document blocks as the control working.",
"Real data over fronted channels — canary traffic only.",
],
references=[
"MITRE ATT&CK: Proxy — domain fronting concepts; CDN provider documentation.",
],
blue_note="their SNI inspection and CDN controls are under test — frontable paths are the finding, blocked paths are the control working.",
),
dict(
slug="c2-jitter-mimicry",
title="C2 Jitter and Mimicry Test",
description="Test C2 traffic mimicry (legitimate-service profiles) to validate anomaly detection.",
tags=["red-team","command-and-control","mimicry","c2"],
risk="high", confirm=True,
blue_kw=["c2","mimicry","anomaly-detection","command-and-control"],
purpose=("Advanced C2 mimics legitimate traffic — cloud APIs, social media, messaging platforms. This "
"test runs canary C2 over legitimate-service profiles and validates whether anomaly detection "
"distinguishes the mimicry from real use."),
when=[
"During advanced C2 phases.",
"To validate UEBA/anomaly-detection tuning.",
"To test allowlisted-domain monitoring (the trusted-domain blind spot).",
],
prereq=[
"Authorization for C2 testing; canary infrastructure.",
"Baseline of legitimate traffic for the mimicked services.",
],
procedure=[
"Profile legitimate traffic for the target service (timing, volume, endpoints).",
"Run canary C2 mimicking the profile; measure the statistical distance.",
"Check detection: did UEBA flag the anomalous use of a legitimate service?",
"Test data-volume anomalies: mimicry that moves 10x the normal volume.",
"Tear down; deliver the mimicry-detection assessment.",
],
outputs=[
"Mimicry-vs-legitimate statistical comparison.",
"UEBA detection results.",
"Allowlisted-domain monitoring findings.",
],
pitfalls=[
"Real user accounts on the mimicked services — canary accounts only.",
"Mimicry volumes that impact the real service — rate-limit.",
],
references=[
"MITRE ATT&CK: Application Layer Protocol — C2 mimicry literature.",
],
blue_note="their anomaly detection faces its hardest case — mimicry it can't distinguish is the UEBA-tuning gap.",
),
dict(
slug="fallback-channel-test",
title="C2 Fallback Channel Test",
description="Test C2 fallback and dead-drop channels to validate layered egress monitoring.",
tags=["red-team","command-and-control","fallback","egress"],
risk="high", confirm=True,
blue_kw=["c2","fallback","egress","command-and-control"],
purpose=("C2 frameworks fall back through channels when the primary is blocked — DNS to HTTPS to "
"cloud APIs to dead drops. This test exercises the fallback chain with canary traffic and "
"validates that blocking one channel doesn't just move the problem silently."),
when=[
"During C2 phases, after primary-channel tests.",
"To validate defense-in-depth across egress channels.",
"To test dead-drop resolver and social-media C2 concepts.",
],
prereq=[
"Authorization for multi-channel C2 testing; canary infrastructure per channel.",
],
procedure=[
"Block the primary canary channel (simulating the defense working) and observe fallback behavior.",
"Exercise each fallback: alternate protocol, cloud-API dead drop, legitimate-service signaling.",
"Record per-channel detection as the fallback chain executes.",
"Test dead-drop concepts: canary messages via cloud storage/comments (authorized test accounts).",
"Tear down all canary channels.",
"Deliver the fallback-chain assessment: which fallbacks were silent?",
],
outputs=[
"Fallback-chain execution log with per-channel detection.",
"Silent-fallback findings.",
"Layered-egress recommendations.",
],
pitfalls=[
"Dead drops on real public platforms without authorization — test accounts only.",
"Leaving fallback infrastructure active — tear down every channel.",
],
references=[
"MITRE ATT&CK: Fallback Channels (T1008).",
],
blue_note="their egress defense-in-depth is under test — every silent fallback is a channel the blocking strategy doesn't cover.",
),
dict(
slug="icmp-tunnel-test",
title="ICMP Tunnel Test",
description="Test ICMP tunneling to validate non-TCP/UDP channel monitoring.",
tags=["red-team","command-and-control","icmp","tunneling"],
risk="high", confirm=True,
blue_kw=["icmp","tunneling","c2","monitoring"],
purpose=("ICMP is rarely inspected — ping goes everywhere. This test tunnels canary data over ICMP "
"and validates whether any monitoring notices the non-standard ICMP payloads."),
when=[
"During C2 phases testing exotic channels.",
"To validate firewall ICMP policies and IDS coverage.",
"As the 'forgotten protocol' check.",
],
prereq=[
"Authorization for tunneling tests; canary endpoints.",
"NetOps awareness — ICMP anomalies may page someone.",
],
procedure=[
"Tunnel canary data over ICMP echo payloads between authorized endpoints.",
"Vary payload sizes and rates; record IDS/firewall reactions.",
"Check ICMP type/code policies: what's allowed out, and is it logged?",
"Test ICMPv6 variants where deployed.",
"Stop the tunnel; verify no test traffic continues.",
"Deliver the ICMP-channel assessment.",
],
outputs=[
"ICMP tunneling detection results.",
"Firewall ICMP-policy findings.",
"Monitoring recommendations.",
],
pitfalls=[
"Tunneling volumes that look like a ping flood — rate-limit and coordinate.",
"Forgetting IPv6 — test both where deployed.",
],
references=[
"MITRE ATT&CK: Protocol Tunneling (T1572).",
],
blue_note="their forgotten-protocol monitoring is under test — silent ICMP tunnels are the non-standard-channel gap.",
),
dict(
slug="cloud-api-c2-test",
title="Cloud API C2 Test",
description="Test cloud-API-based C2 (dead drops, tasking via cloud services) to validate cloud monitoring.",
tags=["red-team","command-and-control","cloud","c2"],
risk="high", confirm=True,
blue_kw=["cloud","c2","command-and-control","api"],
purpose=("Cloud APIs make excellent C2: the traffic is legitimate TLS to trusted domains. This test "
"builds canary dead-drop tasking over cloud storage/APIs and validates whether cloud audit logging "
"and CASB distinguish C2 use from normal use."),
when=[
"During cloud C2 phases.",
"To validate cloud audit-log alerting on anomalous API use.",
"To test the trusted-domain blind spot in web filtering.",
],
prereq=[
"Authorization for the cloud tenants; canary storage/identities.",
"CASB/cloud-admin coordination.",
],
procedure=[
"Build canary tasking: beacon writes a canary file, controller reads it, replies via another object.",
"Vary the pattern: polling intervals, object naming, data encoding.",
"Check cloud audit logs: is the anomalous API pattern visible and alerted?",
"Test CASB: does it distinguish the canary C2 from normal storage use?",
"Tear down all canary objects and identities.",
"Deliver the cloud-API C2 assessment.",
],
outputs=[
"Cloud-API C2 detection results.",
"Audit-log visibility assessment.",
"CASB findings.",
],
pitfalls=[
"Real cloud identities for the C2 — canary identities only.",
"Leaving canary objects in production buckets — verify deletion.",
],
references=[
"MITRE ATT&CK: Application Layer Protocol — cloud API abuse literature.",
],
blue_note="their cloud monitoring faces trusted-domain C2 — API patterns nobody flagged are the cloud-detection gap.",
),
dict(
slug="steganography-c2-test",
title="Steganography C2 Validation Test",
description="Test steganographic C2 channels to validate content-inspection controls.",
tags=["red-team","command-and-control","steganography"],
risk="high", confirm=True,
blue_kw=["steganography","c2","command-and-control","dlp"],
purpose=("Steganography hides C2 in images, audio, and documents — content inspection's hardest case. "
"This test moves canary tasking through steganographic channels and validates whether any "
"content analysis notices."),
when=[
"During advanced C2 phases.",
"To validate DLP content-inspection depth.",
"When the threat model includes steganography-aware actors.",
],
prereq=[
"Authorization for the test; canary images and carriers.",
"DLP-team coordination.",
],
procedure=[
"Embed canary tasking in images via standard steganographic tools.",
"Move the carriers through the monitored channels (email, web upload, cloud storage).",
"Record: did DLP/content-inspection flag anything? Did file-hash or perceptual-hash analysis trigger?",
"Test the reverse: canary exfil hidden in outbound images.",
"Destroy all canary carriers.",
"Deliver the steganography assessment with realistic expectations (detection is hard; focus on endpoint).",
],
outputs=[
"Steganographic-channel detection results per channel.",
"DLP content-depth findings.",
"Endpoint-focused recommendations.",
],
pitfalls=[
"Real sensitive data in carriers — canary tasking only.",
"Presenting steganography as undetectable — endpoint behavior still catches the implant.",
],
references=[
"MITRE ATT&CK: Steganography (T1027.003).",
],
blue_note="their content inspection meets its hardest case — the honest finding is usually 'detect at the endpoint, not the carrier'.",
),
dict(
slug="beacon-interval-analysis",
title="Beacon Interval Analysis Test",
description="Analyze beaconing intervals statistically to validate network-anomaly detection tuning.",
tags=["red-team","command-and-control","beaconing","analytics"],
risk="low", confirm=False,
blue_kw=["beaconing","analytics","command-and-control","detection"],
purpose=("Beaconing detection is statistics: interval regularity, jitter analysis, byte counts. This "
"test generates canary beacons with known profiles and validates that the network analytics "
"actually fire — tuning the detectors with ground truth."),
when=[
"As a detection-engineering exercise with the blue team.",
"To tune beaconing analytics with labeled data.",
"After HTTPS-C2 tests, as the analytics follow-on.",
],
prereq=[
"Authorization for beacon generation; canary beacon infrastructure.",
"NetOps/SOC coordination — this is a joint tuning exercise.",
],
procedure=[
"Generate canary beacons with known profiles: fixed interval, jittered, randomized, low-and-slow.",
"Feed the labeled beacon traffic to the analytics and record detection per profile.",
"Measure detection latency: how many beacons before the alert?",
"Test the evasion boundary: at what jitter/randomness does detection fail?",
"Deliver the beaconing-analytics tuning report with labeled datasets.",
],
outputs=[
"Per-profile detection results with latency.",
"Evasion-boundary measurements.",
"Labeled beacon dataset for the SOC.",
],
pitfalls=[
"Unlabeled beacon traffic confusing the SOC — label everything, coordinate timing.",
"Beaconing from production hosts without approval — dedicated test hosts.",
],
references=[
"Network beaconing-detection literature (public).",
],
blue_note="their beaconing analytics get ground-truth tuning data — labeled beacons are the detection-engineering gift.",
),
dict(
slug="c2-infrastructure-takedown",
title="C2 Infrastructure Takedown Exercise",
description="Exercise C2 infrastructure takedown procedures as a blue-team validation drill.",
tags=["red-team","command-and-control","takedown","exercise"],
risk="low", confirm=False,
blue_kw=["c2","takedown","exercise","incident-response"],
purpose=("This is the rare red playbook that's really a blue drill: given canary C2 infrastructure, "
"the blue team practices the takedown — domain sinkholing coordination, firewall blocks, "
"endpoint isolation — and the red side measures their speed and completeness."),
when=[
"As a joint exercise after C2 testing phases.",
"To validate incident-response playbooks for C2 infrastructure.",
"To measure takedown coordination across teams.",
],
prereq=[
"Canary C2 infrastructure designated as the takedown target.",
"IR playbook and stakeholder coordination.",
],
procedure=[
"Stand up the canary C2 infrastructure and generate realistic beacon traffic.",
"Hand the blue team the detection (simulated initial alert) and start the clock.",
"Observe the takedown: containment, blocking, sinkholing coordination, endpoint isolation.",
"Measure: time to containment, completeness (did all infrastructure get blocked?), communication quality.",
"Red-team debrief: which takedown steps were missed or slow?",
"Deliver the takedown exercise report with playbook improvements.",
],
outputs=[
"Takedown timeline with measurements.",
"Completeness assessment (infrastructure blocked?).",
"IR playbook improvement recommendations.",
],
pitfalls=[
"Real infrastructure as the target — canary only.",
"Grading individuals instead of the playbook — keep it blameless.",
],
references=[
"Incident-response exercise literature; C2 takedown case studies (public).",
],
blue_note="their IR playbook gets a live-fire drill — takedown speed and completeness are the measured outcomes.",
),
]
