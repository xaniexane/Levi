# Red team topics — chunk 2: initial access (12) + execution (8)

RED_2 = [
dict(
slug="phishing-simulation-campaign",
title="Phishing Simulation Campaign",
description="Plan and execute an authorized phishing simulation to test user reporting, gateway filtering, and incident response.",
tags=["red-team","initial-access","phishing"],
risk="moderate", confirm=True,
blue_kw=["phishing","email","awareness"],
purpose=("Measure the organization's real phishing resilience: do users click, do they report, does the "
"gateway filter, and does the SOC respond? A well-run simulation produces click rates, report rates, "
"and time-to-contain metrics — the three numbers that justify the entire awareness program."),
when=[
"As part of the social-engineering phase of an authorized assessment.",
"Quarterly, to track awareness-program effectiveness over time.",
"After a real phishing incident, to validate that the lessons stuck.",
],
prereq=[
"Explicit social-engineering authorization: allowed techniques, target groups, and forbidden pretexts.",
"Pre-approved email templates and landing pages; no credential harvesting beyond proof-of-submit.",
"IT/helpdesk pre-briefed so the simulation doesn't trigger a real incident response.",
],
procedure=[
"Build the target list from personnel OSINT; get client sign-off on the exact recipients.",
"Register lookalike infrastructure (typosquat domain or approved sender) and warm it up so the test measures the gateway, not spam reputation.",
"Craft 2-3 pretext variants (IT notification, HR document, vendor invoice) with increasing sophistication; keep payloads inert (tracking pixel + safe link only).",
"Launch in waves, not all at once, so the SOC can demonstrate detection on wave 1 and the report rate on later waves is meaningful.",
"Record per-wave: delivery rate, open rate, click rate, credential-submit rate (to the inert form), and report rate with time-to-report.",
"For clickers, serve the approved training page immediately — the teachable moment is the point.",
"Debrief with the blue team: which controls fired (gateway, EDR, user reports), what the SOC did with the first report, and the metrics trend vs. last quarter.",
],
outputs=[
"Per-wave metrics: delivered/opened/clicked/submitted/reported with timestamps.",
"Control-effectiveness map: which layer caught which wave.",
"Repeat-clicker list for targeted coaching (handled per the ROE privacy terms).",
],
pitfalls=[
"Payloads that actually harvest credentials or install anything — keep everything inert and client-approved.",
"Forgetting the helpdesk pre-brief; a good simulation looks exactly like a real incident to the unbriefed.",
"Targeting executives or finance with wire-transfer pretexts without extra approval — high blast radius, needs explicit sign-off.",
],
references=[
"MITRE ATT&CK: Phishing (T1566).",
"NIST SP 800-53: awareness and training controls (AT family).",
],
blue_note="their email gateway, user-reporting pipeline, and SOC triage each get a measurable score — the report rate trend is the awareness program's KPI.",
),
dict(
slug="spear-phishing-attachment",
title="Spear-Phishing Attachment Test",
description="Test email gateway and endpoint controls against weaponized-document simulations using inert payloads.",
tags=["red-team","initial-access","phishing","malware"],
risk="moderate", confirm=True,
blue_kw=["phishing","attachment","malware","email"],
purpose=("Determine whether malicious-document simulations reach inboxes and what happens when opened: "
"does the gateway detonate or strip the attachment, does EDR block the macro, does the user enable "
"content? All payloads are inert — the test measures controls, not exploitation."),
when=[
"To validate email-gateway sandboxing and attachment-stripping policies.",
"To test EDR behavior against macro and script execution in documents.",
"When the threat model includes document-borne initial access.",
],
prereq=[
"Authorization for attachment-based testing; payloads reviewed and approved as inert.",
"EDR/gateway teams aware of the test window to distinguish it from real malware.",
],
procedure=[
"Build inert document payloads: macros that write a canary registry key or beacon to a controlled listener, never a real implant.",
"Send through the normal mail flow (not whitelisted) so the gateway is genuinely tested — coordinate the window with the SOC.",
"Test the matrix: Office macro documents, PDFs with embedded scripts, archives (zip/iso) with script payloads, OneNote-style lures where in scope.",
"Record per-sample: gateway verdict (delivered/quarantined/stripped), EDR verdict on open, and whether macros were auto-blocked or user-enabled.",
"For delivered samples, measure whether the inert beacon fired — proving code execution would have occurred.",
"Map each result to the control that should have caught it and note the gap.",
],
outputs=[
"Per-sample control matrix: gateway verdict × EDR verdict × execution result.",
"Inert-beacon evidence proving which samples would have executed.",
"Control-gap list with recommended policy changes.",
],
pitfalls=[
"Real payloads 'for realism' — never; inert beacons prove the same point with zero risk.",
"Whitelisting the sender to 'make sure it arrives' — that defeats the gateway test entirely.",
"Testing file types the org has legitimately blocked (e.g., ISOs) without noting the block is the expected pass.",
],
references=[
"MITRE ATT&CK: Phishing — Spearphishing Attachment (T1566.001).",
],
blue_note="their gateway sandboxing and EDR macro policies get a per-sample scorecard — every delivered-and-executed sample is a control failure to fix.",
),
dict(
slug="credential-phishing-page",
title="Credential Phishing Page Test",
description="Stand up a cloned login page in a controlled test to measure credential-submit rates and MFA resilience.",
tags=["red-team","initial-access","phishing","credentials"],
risk="moderate", confirm=True,
blue_kw=["phishing","credentials","mfa","login"],
purpose=("Find out what happens after the click: do users enter credentials, does MFA stop the test, "
"does the SOC notice the lookalike domain? The cloned page captures nothing real — submissions are "
"hashed or discarded — but the submit rate and MFA-bypass rate are the metrics that matter."),
when=[
"After a phishing simulation shows high click rates, to test the next layer.",
"To validate MFA enrollment coverage and phishing-resistant MFA rollout.",
"When the threat model includes credential harvesting against SSO portals.",
],
prereq=[
"Authorization for credential-phishing specifically; some orgs allow click-tracking but not submit-tracking — honor the distinction.",
"Lookalike domain approved and registered; certificate obtained legitimately.",
"Agreement that submitted credentials are never stored in recoverable form.",
],
procedure=[
"Clone the target login page's look (public assets only) on the approved lookalike domain with TLS.",
"Implement submit handling that hashes or immediately discards credentials and logs only the submit event + timestamp.",
"Drive traffic via the approved phishing wave; record delivered → visited → submitted funnel metrics.",
"For submitters, test the MFA layer: does the org use phishing-resistant MFA (FIDO2), or would a real-time relay have succeeded? Report, don't relay, unless relay testing is explicitly authorized.",
"Monitor for blue-team detection: was the lookalike domain reported, blocklisted, or taken down, and how fast?",
"Debrief: submit rate, MFA coverage gaps, and detection timeline become the awareness and identity findings.",
],
outputs=[
"Visit/submit funnel metrics per wave.",
"MFA posture assessment: coverage and phishing-resistance of enrolled methods.",
"Lookalike-domain detection timeline.",
],
pitfalls=[
"Storing submitted credentials in plaintext 'for the report' — never; hash-or-discard is the rule.",
"Cloning pages with copyrighted assets beyond fair-use test scope — keep it minimal and client-approved.",
"Letting the lookalike domain linger after the test — tear it down and document the teardown.",
],
references=[
"MITRE ATT&CK: Phishing — Spearphishing Link (T1566.002).",
"NIST SP 800-63B: MFA phishing resistance.",
],
blue_note="their MFA rollout and lookalike-domain monitoring get tested end to end — every submitter without phishing-resistant MFA is an identity-program gap.",
),
dict(
slug="password-spraying",
title="Password Spraying Test",
description="Test authentication endpoints against password spraying using breached and common passwords to validate lockout and detection.",
tags=["red-team","initial-access","credentials","brute-force"],
risk="moderate", confirm=True,
blue_kw=["password","spraying","brute-force","authentication"],
purpose=("Validate that password spraying — a few common passwords against many accounts — is detected "
"and thwarted by lockout policy, MFA, and monitoring. This is the most common real-world initial "
"access technique against SSO and VPN portals, so the test directly measures resilience to it."),
when=[
"Against in-scope authentication portals (SSO, VPN, webmail, RDP gateways).",
"To validate account lockout thresholds and alerting before attackers do.",
"After a breach-corpus review suggests employee passwords are compromised.",
],
prereq=[
"Authorization naming the exact authentication endpoints; never spray endpoints outside the list.",
"Agreed password list (common + breach-corpus, no real employee passwords) and rate limits that respect lockout policy.",
"Service-account exclusion list — never lock out break-glass or service accounts.",
],
procedure=[
"Enumerate valid usernames first via the approved method (or use the personnel OSINT list) — spraying needs targets.",
"Build the spray list: seasonal passwords, company-name variants, and top breach-corpus passwords; explicitly exclude the exclusion list.",
"Spray slowly: one password per user per round, with long delays between rounds to stay under lockout thresholds — the point is stealth validation, not lockouts.",
"Monitor for detection: does the SIEM alert on distributed failed logons, impossible travel, or password-spray patterns?",
"Record any successful authentications immediately, stop, and report — a spray success is a critical finding, not a pivot opportunity, until re-authorized.",
"Deliver the spray report: attempts, rate, detection alerts fired (or not), and any compromised credentials rotated under supervision.",
],
outputs=[
"Spray attempt log with rate and timing.",
"Detection assessment: which alerts fired, with timestamps.",
"Any compromised credentials (handled per the credential-handling ROE).",
],
pitfalls=[
"Spraying too fast and locking out real users — the agreed rate is a safety control, not a suggestion.",
"Using real employee passwords from breach data as spray candidates — use generic corpus passwords only.",
"Continuing to pivot on a sprayed account without fresh authorization — stop and re-scope.",
],
references=[
"MITRE ATT&CK: Brute Force — Password Spraying (T1110.003).",
],
blue_note="their identity monitoring should detect the spray pattern itself — silent spraying is a SIEM detection gap regardless of whether any password worked.",
),
dict(
slug="credential-stuffing-test",
title="Credential Stuffing Test",
description="Test whether breached credential pairs work against in-scope logins, validating breach monitoring and MFA coverage.",
tags=["red-team","initial-access","credentials","breach"],
risk="moderate", confirm=True,
blue_kw=["credentials","breach","stuffing","authentication"],
purpose=("Employees reuse passwords; breach corpora prove it. This test checks a sample of breached "
"credential pairs against in-scope authentication endpoints to measure real account-takeover risk — "
"under strict handling rules, with immediate rotation of anything that works."),
when=[
"When breach-corpus review shows employee emails in known breaches.",
"To justify MFA enforcement with empirical compromise data.",
"As part of identity-hygiene assessments.",
],
prereq=[
"Explicit authorization for credential-stuffing; many ROEs require extra sign-off for this technique.",
"Credential-handling agreement: pairs tested from an isolated harness, successes trigger immediate forced rotation.",
"Scope limited to named endpoints; no stuffing against personal or third-party accounts.",
],
procedure=[
"Source breach pairs from the agreed corpus, filtered to in-scope employee identifiers only.",
"Build an isolated test harness that attempts logins at a low rate with full logging; never use a personal browser or mix with other activity.",
"On any success: stop that account's testing immediately, record the event, and trigger the agreed forced-password-reset workflow.",
"Measure detection: did the SIEM flag impossible-travel, new-device, or velocity alerts for the attempts?",
"Aggregate statistics only in the report (X of Y sampled pairs worked); never list working credentials in deliverables.",
"Recommendations focus on MFA enforcement, breach-monitoring, and password-manager rollout.",
],
outputs=[
"Aggregate success statistics (no working credentials in the report).",
"Detection assessment for stuffing-pattern alerts.",
"Forced-rotation records for any compromised accounts.",
],
pitfalls=[
"Testing credentials belonging to out-of-scope or personal accounts — filter strictly to in-scope employees.",
"Keeping working credentials 'for later phases' — rotate immediately per the ROE.",
"High-rate stuffing that triggers fraud controls and locks users out en masse.",
],
references=[
"MITRE ATT&CK: Valid Accounts (T1078).",
"OWASP: credential stuffing prevention cheat sheet.",
],
blue_note="their breach-monitoring and impossible-travel detections are the controls under test — working pairs that went unnoticed are identity-monitoring failures.",
),
dict(
slug="external-remote-service-brute-force",
title="External Remote Service Brute Force",
description="Test externally exposed RDP, SSH, and VPN endpoints against brute-forcing to validate hardening and monitoring.",
tags=["red-team","initial-access","brute-force","remote-services"],
risk="moderate", confirm=True,
blue_kw=["brute-force","rdp","ssh","vpn","remote"],
purpose=("Internet-exposed remote services are the front door attackers knock on first. This test "
"measures whether brute-forcing those doors is feasible, detected, and rate-limited — or whether "
"the blue team is blind to it. Findings here are usually 'expose less, monitor more.'"),
when=[
"After the exposed-service review identifies internet-facing RDP/SSH/VPN.",
"To validate account lockout, IP blocklisting, and geo-blocking on remote access.",
"Before recommending VPN/RDP exposure reduction.",
],
prereq=[
"Authorization for the exact endpoints and a conservative attempt budget.",
"Agreement on lockout-risk: the test must not denial-of-service legitimate remote workers.",
],
procedure=[
"Inventory the exposed remote services from the recon phase; confirm each is in scope and note its auth mechanism (password, key, MFA).",
"Run low-and-slow brute-forcing with a small credential set (defaults, common pairs) — this is a controls test, not a cracking run.",
"Test for missing MFA, default credentials, and absent lockout by observing responses (not by hammering).",
"Monitor blue-team detection in parallel: firewall blocks, IDS alerts, SIEM failed-logon rules.",
"Document every finding with the exact attempt count and rate that produced it.",
"Recommend exposure reduction (VPN-only, allowlisting, MFA) for each vulnerable service.",
],
outputs=[
"Per-endpoint brute-force resistance assessment.",
"Detection telemetry: which attempts were seen and blocked.",
"Exposure-reduction recommendations per service.",
],
pitfalls=[
"High-volume brute-forcing that locks out legitimate users or triggers upstream ISP blocks.",
"Testing VPN endpoints shared with third parties without confirming scope.",
"Confusing 'login page exists' with 'vulnerable' — the finding is about controls, not existence.",
],
references=[
"MITRE ATT&CK: Brute Force (T1110), External Remote Services (T1133).",
],
blue_note="their perimeter monitoring and remote-access hardening are under test — unalerted brute-forcing is a detection gap even when no credential works.",
),
dict(
slug="exploiting-public-facing-app",
title="Public-Facing Application Exploitation Test",
description="Validate exploitable vulnerabilities in in-scope public applications in a controlled manner to prove impact safely.",
tags=["red-team","initial-access","web","exploitation"],
risk="high", confirm=True,
blue_kw=["vulnerability","exploitation","web-application","penetration"],
purpose=("Move from 'vulnerability exists' to 'impact proven' — safely. Controlled exploitation of "
"validated vulnerabilities demonstrates real business impact (data access, RCE) without causing "
"harm, turning scanner output into findings executives understand and fund."),
when=[
"After vulnerability validation identifies exploitable issues in scope.",
"When the client needs impact demonstration to prioritize remediation.",
"To test WAF/IDS behavior against real exploit traffic.",
],
prereq=[
"Explicit exploitation authorization per vulnerability class; some ROEs forbid RCE or data exfiltration even in tests.",
"Backup/rollback plan for the target application; maintenance-window coordination for production.",
"Rules for proof: read-only files, canary records, never real customer data.",
],
procedure=[
"Select validated vulnerabilities from the fingerprinting phase; confirm each target is in scope and backed up.",
"Develop or adapt exploits in the lab first — never run untested exploit code against the target.",
"Execute with proof-only payloads: read a canary file, write a canary record, or trigger a DNS callback — never touch real data.",
"Capture full evidence: requests, responses, timestamps, and the exact payload for blue-team replay.",
"Stop at first proof of each impact class; do not chain exploits into full compromise without fresh authorization.",
"Immediately report critical findings (RCE, auth bypass) through the agreed rapid channel, then document fully.",
],
outputs=[
"Per-vulnerability proof-of-impact evidence with replayable payloads.",
"Critical-findings rapid reports with timestamps.",
"Remediation guidance per vulnerability with CVSS and business impact.",
],
pitfalls=[
"Running untested exploits against production — lab-test everything first.",
"Exfiltrating real data 'to prove impact' — canary data proves the same point.",
"Chaining into domain compromise from a web shell without authorization — each escalation needs its own approval.",
],
references=[
"MITRE ATT&CK: Exploit Public-Facing Application (T1190).",
"OWASP Testing Guide: exploitation methodology.",
],
blue_note="their WAF, IDS, and app-layer logging face real exploit traffic here — missed exploit attempts are detection gaps, blocked ones are control validations.",
),
dict(
slug="drive-by-download-simulation",
title="Drive-By Download Simulation",
description="Simulate drive-by download attacks in a lab to test browser and endpoint controls without endangering users.",
tags=["red-team","initial-access","browser","lab"],
risk="moderate", confirm=True,
blue_kw=["browser","drive-by","malware","endpoint"],
purpose=("Test whether a compromised or malicious website could silently drop malware on corporate "
"endpoints — entirely in the lab. The simulation measures browser hardening, EDR, and network "
"filtering against the drive-by attack chain without ever exposing real users."),
when=[
"To validate browser hardening baselines and EDR web-protection features.",
"When the threat model includes watering-hole or malvertising scenarios.",
"As a lab exercise — this technique is never tested against real users.",
],
prereq=[
"Lab-only authorization: isolated VMs, no real user endpoints, no internet-facing lure pages.",
"EDR and browser configs under test documented as the baseline.",
],
procedure=[
"Build the lab: victim VMs with the corporate browser/EDR baseline, attacker VM serving the simulated exploit kit (inert payloads only).",
"Simulate the attack chain stages: lure page → browser exploit attempt (patched-CVE proof-of-concept, inert) → payload download → execution attempt.",
"Record at each stage which control fired: browser sandbox, SmartScreen/safe-browsing, EDR, network filtering.",
"Vary the chain: different browsers, with and without EDR, patched vs. unpatched baselines.",
"Measure time-to-detect and time-to-block per stage.",
"Translate lab results into hardening recommendations for the production baseline.",
],
outputs=[
"Per-stage control matrix across browser/EDR configurations.",
"Time-to-detect/block measurements.",
"Hardening recommendations for the browser baseline.",
],
pitfalls=[
"Letting the simulation touch real users or the internet — lab isolation is the safety control.",
"Using live exploit kits instead of inert simulations — the chain stages are what matter, not real exploitation.",
"Testing only the default browser — cover every browser in the corporate baseline.",
],
references=[
"MITRE ATT&CK: Drive-by Compromise (T1189).",
],
blue_note="their browser baseline and EDR web protections get a stage-by-stage scorecard — silent progression through all stages is a layered-defense failure.",
),
dict(
slug="removable-media-drop",
title="Removable Media Drop Test",
description="Test user and endpoint behavior with planted USB media carrying inert payloads in authorized facilities.",
tags=["red-team","initial-access","physical","usb"],
risk="moderate", confirm=True,
blue_kw=["usb","removable-media","physical","endpoint"],
purpose=("Find out what happens when someone plugs in a found USB drive: does the endpoint block it, "
"does EDR fire, does the user report it? Planted drives with inert payloads answer all three — "
"measuring device-control policy and user behavior in one test."),
when=[
"During on-site assessments with physical social-engineering authorization.",
"To validate USB device-control policies and EDR removable-media protections.",
"When the threat model includes malicious insiders or visitors.",
],
prereq=[
"On-site authorization naming the areas where drops are permitted.",
"Inert payloads only: canary files and beacons to a controlled listener, no real malware.",
"Agreement on how plugged-in drives are retrieved and accounted for.",
],
procedure=[
"Prepare USB drives with inert payloads: an autorun-style lure document (canary beacon), a labeled drive ('Q3 Bonuses', 'IT Survey').",
"Place drives in approved locations (parking lot, break room, lobby) and log each placement with time and photo.",
"Monitor the controlled listener for beacons indicating a drive was plugged in and the payload stage executed.",
"Track user reporting: did anyone bring the drive to security instead of plugging it in?",
"Record EDR/device-control verdicts for each insertion event from the blue team.",
"Retrieve all drives at test end; account for every unit placed.",
"Debrief: insertion rate, execution rate, report rate, and control verdicts.",
],
outputs=[
"Per-drive outcome: placed → found → plugged → executed → reported.",
"Device-control and EDR verdicts per insertion.",
"Drive accountability log (all units retrieved).",
],
pitfalls=[
"Unaccounted drives left behind — every unit must be retrieved; treat a missing drive as an incident.",
"Payloads that do anything beyond beaconing — inert means inert.",
"Dropping in areas outside the authorized list (executive offices, data centers) without specific approval.",
],
references=[
"MITRE ATT&CK: Replication Through Removable Media (T1091).",
],
blue_note="their device-control policy and EDR removable-media modules face a real-world test — every unblocked execution is a policy or control gap.",
),
dict(
slug="evil-twin-wireless",
title="Evil-Twin Wireless Access Test",
description="Stand up a rogue access point with the corporate SSID in an authorized test to measure client and NAC behavior.",
tags=["red-team","initial-access","wireless","rogue-ap"],
risk="high", confirm=True,
blue_kw=["wireless","evil-twin","rogue-ap","nac"],
purpose=("Prove what happens when an attacker broadcasts the corporate SSID: do clients connect, does "
"the NAC notice, does anyone alert? The evil twin runs in a controlled window with the blue team "
"watching — the detection race is the exercise."),
when=[
"During on-site wireless assessments with active-attack authorization.",
"To validate wireless IDS rogue-AP detection and response times.",
"To test whether corporate clients validate RADIUS certificates.",
],
prereq=[
"Explicit authorization for rogue-AP transmission at the facility, with time window and channels.",
"Coordination with facility management; transmission must not disrupt neighbors.",
"Blue-team WIDS team on standby to measure detection time.",
],
procedure=[
"Survey the target SSIDs and channels from the recon phase; choose the corporate SSID with the weakest client validation.",
"Bring up the evil twin on an unused channel with the corporate SSID; run a captive portal or EAP relay listener as authorized — credentials are never harvested beyond proof-of-association.",
"Measure client behavior: do managed clients auto-connect, prompt, or refuse (certificate validation)?",
"Start the clock: how long until the WIDS flags the rogue, and how long until the blue team responds on the ground?",
"Attempt NAC-bypass observations only as authorized: does the rogue AP's clients get network access, or does NAC contain them?",
"Tear down at window end; document the full timeline from first beacon to blue-team response.",
],
outputs=[
"Client-behavior results: auto-connect vs. prompt vs. refuse per device profile.",
"Rogue-AP detection and response timeline.",
"NAC containment assessment.",
],
pitfalls=[
"Transmitting outside the authorized window or channels — interference with neighbors is a legal risk.",
"Harvesting real credentials through the twin — proof-of-association only, per the ROE.",
"Forgetting to tear down — a forgotten rogue AP becomes a real vulnerability.",
],
references=[
"MITRE ATT&CK: Wireless techniques; Rogue AP attack literature (public).",
],
blue_note="their WIDS detection time and physical-response playbook are measured live — a twin that beacons unnoticed for the full window is a wireless-monitoring failure.",
),
dict(
slug="qr-code-phishing",
title="QR Code Phishing Test",
description="Test user and gateway behavior with QR-code lures that bypass text-based email filtering.",
tags=["red-team","initial-access","phishing","qr-code"],
risk="moderate", confirm=True,
blue_kw=["phishing","qr-code","email","mobile"],
purpose=("QR codes smuggle URLs past text-based email filters and push victims to mobile browsers where "
"corporate controls are thinner. This test measures whether QR lures reach inboxes, get scanned, and "
"what the mobile-side controls do about it."),
when=[
"As a phishing-campaign variant when text-based lures are well-defended.",
"To test mobile device management and mobile browser protections.",
"When the threat model includes QR-based phishing (quishing).",
],
prereq=[
"Same social-engineering authorization as the phishing campaign; QR lures are a variant, not a separate free pass.",
"Inert landing pages only; no credential harvesting beyond proof-of-visit.",
],
procedure=[
"Generate QR codes encoding the inert landing-page URL; embed them in approved email templates (fake MFA enrollment, package delivery).",
"Send through the normal mail flow and record gateway verdicts — do image-based lures bypass the text filters?",
"Track scans: QR scan events, device type (mobile vs. desktop), and landing-page visits.",
"Measure mobile-side controls: MDM browser policy, safe-browsing on mobile, and whether the corporate VPN/proxy inspects the visit.",
"Compare QR-lure metrics against the text-lure baseline from the main phishing campaign.",
"Debrief with awareness-training input: QR lures need their own training module.",
],
outputs=[
"QR-lure delivery/scan/visit funnel vs. text-lure baseline.",
"Gateway image-analysis verdicts.",
"Mobile-control assessment for QR-driven visits.",
],
pitfalls=[
"Assuming desktop email clients render QR codes usefully — most scans happen on phones; design for that.",
"Real credential harvesting on the landing page — inert proof-of-visit only.",
"Forgetting accessibility: some users can't scan QR codes; the test measures those who can.",
],
references=[
"MITRE ATT&CK: Phishing — Spearphishing Link (T1566.002).",
"Industry reporting on QR-code phishing trends (public).",
],
blue_note="their email gateway's image analysis and mobile-device controls are the layers under test — QR lures that sail through both are a filtering gap.",
),
dict(
slug="mfa-fatigue-test",
title="MFA Fatigue (Push Bombing) Test",
description="Test user resistance to MFA push-notification fatigue and validate number-matching and alerting controls.",
tags=["red-team","initial-access","mfa","credentials"],
risk="moderate", confirm=True,
blue_kw=["mfa","push","fatigue","authentication"],
purpose=("After obtaining a password (via spraying or stuffing, as separately authorized), the next "
"layer is MFA — and push-based MFA can be worn down by repeated prompts. This test measures whether "
"users approve fraudulent pushes and whether the identity team detects the anomaly. It is also the "
"test that justifies phishing-resistant MFA."),
when=[
"After a credential is obtained in an earlier phase, to test the MFA layer specifically.",
"To validate number-matching MFA rollout and anomalous-push alerting.",
"When the org still relies on push-approve MFA.",
],
prereq=[
"Authorization for MFA-fatigue testing specifically, with a cap on push volume per user.",
"The compromised credential used must itself have been obtained under authorization.",
"User-support plan: targeted users get a debrief, not a surprise.",
],
procedure=[
"Using the authorized credential, initiate logins that trigger MFA pushes to the target user, capped at the agreed volume and window.",
"Vary timing: bursts vs. spread-out prompts, business hours vs. off-hours.",
"Record user responses: approve, deny, ignore — and time-to-response.",
"Monitor identity-team detection in parallel: do repeated pushes trigger risk alerts, account lockout, or analyst review?",
"Stop immediately on any approval; an approval is the finding, not an invitation to pivot.",
"Debrief the targeted users and deliver the fatigue-resistance assessment with MFA-upgrade recommendations.",
],
outputs=[
"Per-user push response outcomes (approve/deny/ignore) with timing.",
"Identity-team detection assessment for anomalous push patterns.",
"MFA-upgrade recommendation (number matching → FIDO2).",
],
pitfalls=[
"Uncapped push storms that harass users and generate helpdesk incidents — the cap is a safety control.",
"Continuing after an approval to 'see how far it goes' — stop at the finding.",
"Targeting users without a debrief plan; fatigue tests can erode trust if handled poorly.",
],
references=[
"MITRE ATT&CK: Multi-Factor Authentication Request Generation (T1621).",
"CISA guidance on phishing-resistant MFA.",
],
blue_note="their identity monitoring and MFA policy are under test — unalerted push storms and any approval are identity-program failures.",
),
dict(
slug="powershell-execution",
title="PowerShell Execution Techniques",
description="Test PowerShell execution paths — including constrained language mode and bypasses — to validate endpoint controls.",
tags=["red-team","execution","powershell"],
risk="moderate", confirm=True,
blue_kw=["powershell","execution","constrained-language","edr"],
purpose=("PowerShell is the most abused legitimate tool on Windows. This playbook tests the full "
"spectrum: normal execution, encoded commands, constrained language mode, and its bypasses — "
"measuring what the EDR sees and blocks at each level."),
when=[
"During the execution phase on Windows hosts, after initial access.",
"To validate PowerShell Constrained Language Mode deployment.",
"To test EDR script-block logging and AMSI integration.",
],
prereq=[
"Authorization for code execution on the target hosts; lab-test payloads first.",
"Confirmation of which PowerShell versions and language modes are in the baseline.",
],
procedure=[
"Baseline: run standard PowerShell commands and record EDR/script-block-logging telemetry.",
"Test encoded commands (`-EncodedCommand`) and download cradles against network controls — inert payloads only.",
"Check the language mode (`$ExecutionContext.SessionState.LanguageMode`); if Constrained, test documented bypass paths in the lab first, then as authorized.",
"Test PowerShell 7 / pwsh side-by-side: does the EDR cover the cross-platform host equally?",
"Measure logging: Script Block Logging (event 4104), Module Logging, and transcription — which fired, which were missing?",
"Map every technique to the EDR/EDR-policy control that should have caught it.",
],
outputs=[
"Per-technique execution and detection matrix.",
"Script-block-logging coverage assessment (4104 presence/absence).",
"Constrained Language Mode validation results.",
],
pitfalls=[
"Running untested bypasses that crash hosts or trigger full incident response outside the window.",
"Assuming PowerShell 7 inherits the Windows PowerShell logging config — verify separately.",
"Forgetting transcription/log forwarding — local logs that never reach the SIEM don't count as detection.",
],
references=[
"MITRE ATT&CK: PowerShell (T1059.001).",
"Microsoft: PowerShell logging guidance.",
],
blue_note="their PowerShell hardening (CLM, logging, AMSI) gets a technique-by-technique scorecard — silent execution is an endpoint-logging gap.",
),
dict(
slug="wmi-execution",
title="WMI-Based Execution",
description="Test WMI as an execution and lateral-movement primitive to validate process-creation monitoring.",
tags=["red-team","execution","wmi","lateral-movement"],
risk="moderate", confirm=True,
blue_kw=["wmi","execution","process-creation","lateral"],
purpose=("WMI (`wmic`, `Invoke-WmiMethod`, DCOM) is a dual-use admin tool and a classic lateral-movement "
"primitive. Testing it validates that process-creation telemetry (Sysmon Event 1, EDR) catches WMI-"
"spawned processes and that the blue team can distinguish admin use from attacker use."),
when=[
"During execution/lateral-movement phases on Windows estates.",
"To validate Sysmon/EDR coverage of WMI provider host activity.",
"When the threat model includes living-off-the-land lateral movement.",
],
prereq=[
"Authorization for remote WMI execution against the target hosts.",
"Baseline of legitimate WMI admin usage so the test doesn't drown in noise.",
],
procedure=[
"Execute inert commands locally via WMI (`wmic process call create`) and record the resulting telemetry (Sysmon 1, Security 4688).",
"Test remote WMI execution via DCOM against an authorized target; vary the spawning parent (wmiprvse.exe) behaviors.",
"Test WMI event-subscription creation as a persistence-adjacent technique (see the persistence playbook).",
"Check whether the EDR distinguishes interactive admin WMI from scripted attacker WMI — or alerts on both equally.",
"Measure detection latency from execution to alert.",
"Deliver the WMI telemetry map: what fired, what was silent, and the recommended Sysmon/EDR rules.",
],
outputs=[
"WMI execution telemetry matrix (local vs. remote).",
"Detection-latency measurements.",
"Recommended Sysmon/EDR rule refinements.",
],
pitfalls=[
"WMI queries that hang against unreachable hosts — set timeouts to avoid test delays.",
"Testing during production admin windows where legitimate WMI noise masks the test — coordinate timing.",
"Forgetting DCOM lateral paths while only testing local WMI.",
],
references=[
"MITRE ATT&CK: WMI (T1047).",
],
blue_note="their process-creation monitoring is the control under test — WMI-spawned processes that generate no alert are a telemetry gap.",
),
dict(
slug="scheduled-task-execution",
title="Scheduled Task Execution Test",
description="Test scheduled tasks as an execution primitive to validate task-creation monitoring and alerting.",
tags=["red-team","execution","scheduled-tasks"],
risk="moderate", confirm=True,
blue_kw=["scheduled-tasks","execution","persistence","monitoring"],
purpose=("Scheduled tasks (`schtasks`, Task Scheduler COM) are a built-in execution primitive abused for "
"both one-shot execution and persistence. This test measures whether task creation, modification, "
"and execution generate the expected telemetry (Security 4698/4702, Sysmon 1 with taskeng parent)."),
when=[
"During execution phases on Windows hosts.",
"To validate scheduled-task auditing GPOs are actually applied.",
"As a precursor to the persistence-phase task tests.",
],
prereq=[
"Authorization for task creation on the targets; tasks must be uniquely named and time-bounded.",
"Agreement on cleanup: every test task is deleted at phase end.",
],
procedure=[
"Create a one-shot scheduled task running an inert command (canary file write) via schtasks and via the COM API.",
"Record the telemetry: Security events 4698 (creation), 4702 (update), 4699 (deletion), and the child process ancestry.",
"Test tasks running as SYSTEM vs. as user — do the controls distinguish privilege levels?",
"Test task creation via remote RPC (atsvc) where in scope.",
"Verify cleanup: delete all test tasks and confirm deletion events fired.",
"Map gaps: which creation methods were silent, and which GPO settings close them.",
],
outputs=[
"Task-creation telemetry matrix per creation method.",
"Cleanup verification (all test tasks removed, deletion events logged).",
"GPO hardening recommendations for task auditing.",
],
pitfalls=[
"Leaving test tasks behind — the cleanup step is part of the test, not optional.",
"Creating tasks as SYSTEM without explicit authorization for privilege level.",
"Missing the COM-API creation path while only testing schtasks.exe.",
],
references=[
"MITRE ATT&CK: Scheduled Task (T1053.005).",
],
blue_note="their scheduled-task auditing (4698/4702) is the control under test — silent task creation is an audit-policy gap.",
),
dict(
slug="living-off-land-binaries",
title="Living-Off-the-Land Binaries (LOLBins)",
description="Test LOLBin abuse paths (certutil, mshta, rundll32, etc.) to validate application-control and EDR behavioral rules.",
tags=["red-team","execution","lolbins","application-control"],
risk="moderate", confirm=True,
blue_kw=["lolbins","application-control","execution","edr"],
purpose=("Attackers live off the land — using signed Microsoft binaries for malicious purposes. This "
"playbook tests a representative LOLBin set against application-control (AppLocker/WDAC) and EDR "
"behavioral rules, measuring which dual-use executions are caught and which sail through."),
when=[
"During execution phases where application allowlisting is claimed.",
"To build the EDR behavioral-rule test matrix.",
"When the threat model emphasizes fileless/living-off-the-land attacks.",
],
prereq=[
"Authorization for LOLBin execution; payloads inert (canary writes, calculator-style proofs).",
"List of LOLBins in the corporate baseline to test systematically.",
],
procedure=[
"Select a representative LOLBin set: certutil (download), mshta (HTA exec), rundll32 (DLL exec), regsvr32, msiexec, wmic, powershell — inert arguments only.",
"Execute each with a canary payload and record: blocked, alerted, or silent — per binary, per argument pattern.",
"Test application-control policies: does AppLocker/WDAC block the abusive invocation while allowing legitimate use?",
"Check EDR behavioral detections: which LOLBin executions triggered behavior rules vs. signature-only?",
"Vary the invocation (renamed binary, alternate paths) where authorized, to test rule robustness.",
"Deliver the LOLBin matrix with recommended allowlist refinements and EDR rule additions.",
],
outputs=[
"Per-LOLBin block/alert/silent matrix.",
"Application-control bypass findings with rule-fix recommendations.",
"EDR behavioral-rule coverage assessment.",
],
pitfalls=[
"Real malicious payloads via LOLBins 'for realism' — canary payloads prove the same execution.",
"Testing LOLBins that are legitimately used by IT without distinguishing — note dual-use explicitly.",
"Forgetting 32-bit vs. 64-bit binary paths (SysWOW64) in the matrix.",
],
references=[
"MITRE ATT&CK: Signed Binary Proxy Execution (T1218); LOLBAS project (public).",
],
blue_note="their application-control and EDR behavioral layers face the dual-use problem directly — silent LOLBin execution is a behavior-detection gap.",
),
dict(
slug="office-macro-execution",
title="Office Macro Execution Test",
description="Test Office macro execution paths and trust settings to validate macro-blocking policies.",
tags=["red-team","execution","office","macros"],
risk="moderate", confirm=True,
blue_kw=["macros","office","execution","email"],
purpose=("Macros remain a top initial-execution vector. This test walks the macro execution paths — "
"auto-open macros, XLM 4.0, VBA stomping concepts — against the organization's macro-blocking "
"policy, using inert documents. The goal is a policy verdict, not a payload."),
when=[
"When the org's macro policy is 'block all' or 'signed only' and needs validation.",
"After the phishing attachment test shows documents reach inboxes.",
"To test EDR behavior on macro-spawned processes.",
],
prereq=[
"Authorization for macro-execution testing; documents inert and client-approved.",
"Knowledge of the deployed Office versions and macro GPOs.",
],
procedure=[
"Build inert macro documents: VBA auto-open writing a canary, XLM 4.0 sheet executing a canary formula.",
"Test each against the macro policy matrix: internet-zone documents, trusted locations, signed vs. unsigned.",
"Record the user experience: blocked silently, warned, or executed — per Office version in the baseline.",
"For executed macros, record the child-process telemetry (EDR/Sysmon) of the canary action.",
"Test policy-bypass-adjacent paths only as authorized (trusted-location abuse); report, don't exploit, trust boundaries.",
"Deliver the macro-policy verdict with GPO recommendations.",
],
outputs=[
"Macro execution matrix per document type × policy zone.",
"Child-process telemetry for executed macros.",
"Macro GPO hardening recommendations.",
],
pitfalls=[
"Malicious macro payloads — inert canaries only, always.",
"Testing only one Office version when the fleet is mixed.",
"Confusing 'macro blocked' with 'document safe' — the attachment test covers delivery; this covers execution.",
],
references=[
"MITRE ATT&CK: Office Application Startup — Office Test (T1137).",
"Microsoft: macro security guidance.",
],
blue_note="their Office macro GPOs and EDR child-process monitoring get a full matrix — any executed macro is a policy failure to remediate.",
),
dict(
slug="psexec-lateral-execution",
title="PsExec-Style Lateral Execution Test",
description="Test PsExec-style service-based lateral execution to validate service-creation monitoring.",
tags=["red-team","execution","lateral-movement","psexec"],
risk="moderate", confirm=True,
blue_kw=["psexec","lateral-movement","services","smb"],
purpose=("PsExec-style execution (SMB + service creation) is the canonical lateral-movement primitive. "
"Testing it validates service-installation telemetry (Security 7045, Sysmon 1 with services.exe "
"parent) and the blue team's ability to distinguish admin tooling from attacker lateral movement."),
when=[
"During lateral-movement phases on Windows estates.",
"To validate service-creation auditing and EDR lateral-movement rules.",
"When the threat model includes credential-based lateral spread.",
],
prereq=[
"Authorization for remote service creation; credentials obtained under authorization.",
"Target list of hosts where lateral execution is permitted.",
],
procedure=[
"Execute an inert command on an authorized target via PsExec-style service creation (SMB admin share + service install).",
"Record the full telemetry: 7045 service-install events, the service binary path, and child-process ancestry.",
"Test variants: native PsExec, Impacket-style, WMI-based — each generates different telemetry the blue team must catch.",
"Measure detection latency and whether the EDR flagged the lateral movement specifically or just the process.",
"Clean up: remove the created services and verify removal events.",
"Map which variants were silent and recommend detection rules per variant.",
],
outputs=[
"Per-variant execution and detection matrix.",
"Service-cleanup verification.",
"Detection-rule recommendations per lateral variant.",
],
pitfalls=[
"Leaving services installed — cleanup is mandatory and verified.",
"Using production admin credentials for the test — use dedicated test credentials.",
"Testing against hosts outside the lateral-movement target list.",
],
references=[
"MITRE ATT&CK: Lateral Movement via service execution (T1569.002, T1021).",
],
blue_note="their service-installation monitoring (7045) and lateral-movement detections face the canonical technique — silent PsExec is a high-severity detection gap.",
),
dict(
slug="container-escape-test",
title="Container Escape Test",
description="Test container escape paths in a lab to validate container runtime hardening and monitoring.",
tags=["red-team","execution","containers","lab"],
risk="moderate", confirm=True,
blue_kw=["containers","escape","docker","kubernetes"],
purpose=("Containers promise isolation; misconfigurations break it. This lab-only test exercises "
"classic escape paths — privileged containers, hostPath mounts, Docker socket exposure, kernel "
"exploits — to validate runtime hardening and container telemetry before production workloads are "
"at risk."),
when=[
"When the org runs containerized workloads and the threat model includes container breakout.",
"To validate PodSecurity policies and runtime security monitoring.",
"Lab-only — never against production clusters.",
],
prereq=[
"Isolated lab cluster mirroring the production configuration; no production contact.",
"Authorization for escape testing in the lab with defined escape goals (host file read, not host damage).",
],
procedure=[
"Deploy the standard misconfiguration matrix in the lab: privileged pod, hostPath mount, docker.sock mount, hostNetwork, excessive capabilities.",
"Attempt each escape path with proof-only goals: read a host canary file, never modify the host.",
"Test runtime security monitoring: does Falco/Tetragon-style telemetry fire on each escape attempt?",
"Validate PodSecurity admission: which misconfigurations were blocked at deploy time vs. which ran?",
"Test image-scanning gates: do known-vulnerable images get blocked before the escape test even starts?",
"Deliver the escape-path matrix with admission-policy and monitoring recommendations.",
],
outputs=[
"Per-misconfiguration escape feasibility and detection matrix.",
"Admission-controller effectiveness assessment.",
"Runtime-monitoring rule recommendations.",
],
pitfalls=[
"Testing against production or staging clusters — lab only, always.",
"Escape goals that damage the host — proof is a canary read, nothing more.",
"Forgetting the CI/CD supply chain: image provenance matters as much as runtime config.",
],
references=[
"MITRE ATT&CK: Escape to Host (T1611).",
"Kubernetes PodSecurity standards documentation.",
],
blue_note="their admission policies and container runtime monitoring get a full matrix — escapes that ran silently are runtime-security gaps.",
),
dict(
slug="cloud-ssrf-metadata",
title="Cloud SSRF to Instance Metadata Test",
description="Test server-side request forgery paths to cloud instance metadata to validate SSRF defenses and IMDSv2 enforcement.",
tags=["red-team","execution","cloud","ssrf"],
risk="high", confirm=True,
blue_kw=["ssrf","cloud","metadata","imds"],
purpose=("SSRF against cloud instance metadata (169.254.169.254) is the classic cloud initial-access "
"path to credentials. This test probes in-scope web applications for SSRF, attempts metadata access "
"with proof-only goals, and validates IMDSv2 enforcement — the control that breaks this attack."),
when=[
"During web application testing of cloud-hosted apps.",
"To validate IMDSv2 enforcement across the cloud fleet.",
"When the threat model includes cloud credential theft via application flaws.",
],
prereq=[
"Explicit authorization for SSRF testing; some ROEs restrict metadata-access attempts — confirm first.",
"Cloud environment in scope with IMDS configuration documented.",
],
procedure=[
"Identify SSRF-prone parameters in the target app: URL fetchers, webhooks, file-import features, PDF generators.",
"Probe with canary callbacks to a controlled listener to confirm outbound request capability without touching metadata.",
"Where authorized, attempt metadata access: IMDSv1 (no token) vs. IMDSv2 (token required) — record which the instance enforces.",
"Proof goal only: read the instance identity document, never credentials; credential access needs separate authorization.",
"Check for credential exfiltration paths: would retrieved credentials reach the internet (egress filtering)?",
"Deliver the SSRF findings with IMDSv2-enforcement recommendations per instance fleet.",
],
outputs=[
"SSRF probe results per parameter with canary-callback evidence.",
"IMDSv1 vs. IMDSv2 enforcement assessment.",
"Egress-filtering observations.",
],
pitfalls=[
"Pulling real instance credentials 'to prove impact' — the identity document proves the path; credentials need separate approval.",
"SSRF probes that hit internal services beyond metadata — constrain targets per the ROE.",
"Forgetting containers/VMs have their own metadata endpoints with different protections.",
],
references=[
"MITRE ATT&CK: Server-Side Request Forgery; Cloud Instance Metadata API (T1552.005).",
"Cloud provider IMDSv2 enforcement documentation.",
],
blue_note="their IMDSv2 rollout and SSRF input validation are under test — IMDSv1 instances reachable via SSRF are critical cloud-hygiene findings.",
),
]
