# Grey team topics — chunk 1: provisioning (10) + setup (10)

GREY_1 = [
dict(
slug="range-provisioning-runbook",
title="Range Provisioning Runbook",
description="Provision isolated exercise ranges on demand with network, identity, and logging baselines.",
tags=["grey-team","provisioning","range","infrastructure"],
risk="low", confirm=False,
purpose=("Every exercise starts with a range: isolated networks, domain infrastructure, logging "
"pipelines, and target estates. This runbook standardizes provisioning so ranges are reproducible, "
"isolated from production, and instrumented before the first red action."),
when=[
"Before any red-team exercise or cyber range event.",
"When standing up persistent training ranges.",
"To rebuild a range after a destructive exercise.",
],
prereq=[
"Virtualization or cloud capacity allocated to the range program.",
"Network isolation design approved (no production routes).",
"License inventory for OS and tooling.",
],
procedure=[
"Allocate the range network segments per the exercise design (red, blue, grey, target VLANs/VPCs).",
"Deploy identity infrastructure: lab domain controllers, test users, service accounts — all clearly labeled.",
"Deploy logging: SIEM forwarder, Sysmon configs, audit policies on every host before any exercise traffic.",
"Deploy the target estate: workstations, servers, and services matching the exercise scenario.",
"Verify isolation: no routes to production, DNS contained, egress controlled and logged.",
"Snapshot the pristine range state (see the snapshot playbooks) before handover.",
"Hand over to the exercise director with the range-readiness checklist signed.",
],
outputs=[
"Provisioned range with network map.",
"Isolation-verification evidence.",
"Pristine-state snapshot reference.",
"Range-readiness checklist.",
],
pitfalls=[
"Provisioning without the logging baseline — exercise traffic without telemetry is wasted.",
"DNS or routes leaking to production — verify isolation actively, don't assume.",
"Skipping the pristine snapshot — you can't reset what you never captured.",
],
references=[
"NIST SP 800-115 (testing guidance); range-operations literature.",
],
exercise_note="This is the foundation every exercise stands on — a range provisioned without isolation verification or logging baselines invalidates everything built on it.",
),
dict(
slug="cloud-range-provisioning",
title="Cloud Range Provisioning",
description="Provision cloud-based exercise ranges with account isolation and cost guardrails.",
tags=["grey-team","provisioning","cloud","range"],
risk="low", confirm=False,
purpose=("Cloud ranges spin up fast and tear down clean — if the accounts, guardrails, and cost "
"controls are right. This runbook provisions cloud exercise environments with hard isolation from "
"production accounts and spend limits that can't surprise anyone."),
when=[
"For cloud-focused exercises (cloud red-team, IAM attack paths).",
"When physical lab capacity is unavailable.",
"For distributed exercises with remote participants.",
],
prereq=[
"Cloud organization with a dedicated range OU/account, separate from production.",
"Cost alerts and hard spend caps configured before provisioning.",
"IaC templates for the range reviewed.",
],
procedure=[
"Create the range accounts under the dedicated OU with SCPs denying production access and expensive services.",
"Deploy via IaC: VPCs, subnets, IAM roles, logging (CloudTrail/audit) enabled in all regions from minute one.",
"Configure cost alerts at 50/80/100% of the exercise budget; set hard caps where the platform allows.",
"Deploy the target cloud estate: canary data, test identities, vulnerable-by-design resources per the scenario.",
"Verify isolation: no trust to production accounts, no shared networking.",
"Tag everything with the exercise codename and auto-expiry date.",
"Hand over with the cloud-range checklist; schedule the teardown job.",
],
outputs=[
"Provisioned cloud range with IaC state.",
"Isolation and guardrail verification.",
"Cost-alert configuration evidence.",
"Teardown schedule.",
],
pitfalls=[
"Range accounts under the production OU — SCPs must deny the crossover explicitly.",
"No spend cap — a crypto-mining scenario or a mistake becomes a bill.",
"Forgetting to enable audit logging in all regions — partial logging is a gap.",
],
references=[
"Cloud provider documentation (Organizations/SCP, CloudTrail, budgets).",
],
exercise_note="Cloud ranges trade lab fidelity for speed and teardown cleanliness — the guardrails (isolation, cost, logging) are what make the trade safe.",
),
dict(
slug="endpoint-fleet-provisioning",
title="Endpoint Fleet Provisioning",
description="Provision Windows and Linux endpoint fleets with standardized baselines and agents.",
tags=["grey-team","provisioning","endpoints","fleet"],
risk="low", confirm=False,
purpose=("Exercises need realistic endpoint fleets: domain-joined workstations with users, EDR agents, "
"and logging — built identically every time. This runbook standardizes fleet provisioning from "
"gold images so the range is reproducible."),
when=[
"For endpoint-focused exercises (EDR validation, ransomware drills).",
"When the scenario needs user-workstation realism.",
"To rebuild fleets between exercise iterations.",
],
prereq=[
"Gold images for each OS/persona (user workstation, server, admin jump box).",
"EDR/agent installers and policies for the range.",
"Domain-join automation and test-user roster.",
],
procedure=[
"Clone endpoints from gold images per the exercise roster (counts per persona).",
"Domain-join and place in the correct OUs; apply the range GPO baseline.",
"Install and verify EDR agents, Sysmon, and audit policies; confirm check-in to the range console.",
"Create test-user profiles with realistic data (canary documents, browser history) per the scenario.",
"Verify the logging pipeline: each endpoint's events reaching the SIEM.",
"Snapshot the fleet baseline before exercise traffic.",
"Hand over with the fleet inventory and health checklist.",
],
outputs=[
"Provisioned endpoint fleet with inventory.",
"Agent/logging health verification.",
"Fleet baseline snapshot reference.",
],
pitfalls=[
"Gold images with expired passwords or broken trust — validate the image before cloning at scale.",
"EDR agents that never check in — verify, don't assume.",
"Identical hostnames breaking the scenario — unique naming per the roster.",
],
references=[
"Endpoint-management documentation; EDR deployment guides.",
],
exercise_note="Fleet realism determines exercise realism — identical, healthy, logged endpoints are the grey team's product.",
),
dict(
slug="ad-lab-provisioning",
title="Active Directory Lab Provisioning",
description="Provision lab Active Directory forests with realistic structure and intentional weaknesses.",
tags=["grey-team","provisioning","active-directory","lab"],
risk="low", confirm=False,
purpose=("AD exercises need a forest that looks real: OUs, groups, GPOs, trusts, and the intentional "
"misconfigurations the scenario calls for. This runbook builds it reproducibly from IaC/scripts, "
"never by hand-tweaking a snowflake domain."),
when=[
"For AD-focused exercises (kerberos attacks, trust abuse, DCSync).",
"When the scenario needs multi-domain or trust topologies.",
"To rebuild AD between exercise iterations.",
],
prereq=[
"AD deployment scripts/IaC reviewed and version-controlled.",
"Scenario's intentional-weakness list (what's misconfigured on purpose).",
"Lab DNS and network segments ready.",
],
procedure=[
"Deploy the forest: root domain, child domains/trusts per the scenario topology.",
"Build the OU structure, security groups, and GPO baselines from the versioned scripts.",
"Create user, service, and admin accounts per the roster — with the scenario's password hygiene (weak where intended, documented).",
"Apply the intentional misconfigurations from the scenario list — each one ticketed and documented as deliberate.",
"Enable the auditing the exercise needs: AD DS auditing, LDAP logging, DC event forwarding.",
"Verify replication health and the blue team's visibility before handover.",
"Snapshot the DCs; hand over with the AD design document.",
],
outputs=[
"Provisioned AD forest with design doc.",
"Intentional-weakness register (deliberate vs. real).",
"Replication and auditing health check.",
"DC snapshot reference.",
],
pitfalls=[
"Hand-tweaked domains nobody can rebuild — script everything.",
"Intentional weaknesses undocumented — the blue team must know what's deliberate.",
"Production password vaults or real data in the lab — never.",
],
references=[
"Microsoft AD DS deployment documentation.",
],
exercise_note="A lab domain is a stage set — realistic enough to exercise in, documented enough to rebuild, and never confused with production.",
),
dict(
slug="network-segmentation-build",
title="Exercise Network Segmentation Build",
description="Build segmented exercise networks with controlled choke points and monitoring.",
tags=["grey-team","provisioning","network","segmentation"],
risk="low", confirm=False,
purpose=("Exercise networks need the segmentation the scenario demands — user segments, server "
"segments, DMZ, red-team ingress — with taps and choke points the grey team controls. This runbook "
"builds it."),
when=[
"For network-focused exercises (lateral movement, segmentation validation).",
"When the scenario tests firewall rules between segments.",
"To rebuild network topology between iterations.",
],
prereq=[
"Network design document for the exercise.",
"Firewall/router capacity (virtual or physical).",
"Monitoring taps or SPAN ports planned.",
],
procedure=[
"Build the segments per the design: addressing, VLANs, inter-segment firewall rules.",
"Deploy the choke points: all inter-segment traffic through grey-team-controlled firewalls with logging.",
"Place network taps/SPAN for the blue team's NDR and the grey team's exercise monitoring.",
"Deploy the scenario services per segment (user services, crown-jewel servers, internet simulator).",
"Verify the ruleset: test each allowed/denied path and log the results.",
"Document the as-built topology; hand over with the firewall ruleset.",
],
outputs=[
"As-built network topology.",
"Firewall ruleset with path-test results.",
"Tap/monitoring placement map.",
],
pitfalls=[
"Untested deny rules — verify the blocks, don't assume the firewall did it.",
"No taps on the choke points — exercise traffic without network telemetry.",
"Internet simulator leaking to real internet — contain it.",
],
references=[
"NIST SP 800-41 (firewall guidance); network-security literature.",
],
exercise_note="The network is the exercise's physics — every segment, rule, and tap the grey team builds determines what the red and blue teams can prove.",
),
dict(
slug="internet-simulator-provisioning",
title="Internet Simulator Provisioning",
description="Provision a simulated internet for closed ranges with fake external services.",
tags=["grey-team","provisioning","simulation","internet"],
risk="low", confirm=False,
purpose=("Closed ranges can't reach the real internet — so the grey team simulates it: fake DNS, fake "
"web services, simulated C2 infrastructure, fake update servers. This runbook builds the simulator "
"so exfiltration and C2 exercises have somewhere to go."),
when=[
"For closed/air-gapped ranges.",
"For C2 and exfiltration exercises needing external destinations.",
"To keep exercise traffic off the real internet.",
],
prereq=[
"Closed-range network design with the simulator segment.",
"Service list: what the scenario needs (DNS, HTTP, mail, cloud APIs).",
],
procedure=[
"Deploy the simulator host(s): DNS resolver with exercise zones, web servers with canary content.",
"Simulate the scenario's external services: C2 endpoints, exfil destinations, phishing infrastructure.",
"Configure range DNS to resolve through the simulator; sinkhole everything else with logging.",
"Verify containment: simulator traffic never leaves the range.",
"Instrument the simulator: full request logging for the blue team's analysis.",
"Hand over with the simulator service catalog.",
],
outputs=[
"Simulator service catalog.",
"Containment-verification evidence.",
"Simulator logging verification.",
],
pitfalls=[
"Simulator with a real upstream resolver — that's a leak, not a simulator.",
"Unlogged simulator services — the blue team needs the simulator's logs too.",
"Phishing infrastructure in the simulator confusing real users — label everything.",
],
references=[
"Range-operations literature; DNS RPZ documentation.",
],
exercise_note="The simulated internet is where exercise attacks land — contained, logged, and unmistakably fake.",
),
dict(
slug="identity-synthetic-users",
title="Synthetic Identity Provisioning",
description="Provision synthetic users, service accounts, and personas for exercise realism.",
tags=["grey-team","provisioning","identity","personas"],
risk="low", confirm=False,
purpose=("Exercises need people: users with mailboxes and files, admins with habits, service accounts "
"with SPNs. This runbook provisions synthetic identities — realistic, clearly labeled, and scoped "
"to the range — so red-team targeting and blue-team UEBA have something real to work with."),
when=[
"For any exercise needing user realism.",
"For phishing and social-engineering scenarios (synthetic targets).",
"For UEBA/anomaly-detection exercises needing behavioral baselines.",
],
prereq=[
"Persona roster for the scenario (roles, privileges, behaviors).",
"Identity infrastructure (AD/lab IdP) ready.",
],
procedure=[
"Create the persona accounts per the roster: naming convention marking them synthetic.",
"Build behavioral baselines: logon patterns, mailbox content, file activity — scripted where possible.",
"Create service accounts with the scenario's SPNs and documented password hygiene.",
"Provision mailboxes, home drives, and cloud identities per the scenario.",
"Document the persona catalog: who exists, what they do, what's deliberate.",
"Hand over with the identity inventory; schedule deprovisioning with range teardown.",
],
outputs=[
"Persona catalog with behaviors.",
"Identity inventory.",
"Deprovisioning schedule.",
],
pitfalls=[
"Synthetic users indistinguishable from real ones — naming and documentation must mark them.",
"Realistic mailboxes with real sensitive content — canary content only.",
"Service accounts with passwords that leak into real vaults — range-scoped secrets only.",
],
references=[
"Identity-management literature; UEBA baseline guidance.",
],
exercise_note="Synthetic people make the exercise real — labeled clearly enough that nobody confuses the stage with the world.",
),
dict(
slug="vulnerable-service-deployment",
title="Vulnerable Service Deployment",
description="Deploy intentionally vulnerable services per scenario with safety containment.",
tags=["grey-team","provisioning","vulnerable","services"],
risk="low", confirm=False,
purpose=("Some scenarios need vulnerable targets: unpatched services, misconfigured apps, weak "
"credentials — deliberately deployed, documented, and contained. This runbook deploys them safely.",
),
when=[
"For exploitation-focused exercises.",
"When the scenario's attack path starts at a vulnerable service.",
"For vulnerability-management validation exercises.",
],
prereq=[
"Scenario's vulnerability list with intended attack paths.",
"Containment verification (no production routes).",
"Blue-team awareness of which vulnerabilities are deliberate.",
],
procedure=[
"Deploy the vulnerable services per the scenario list — version-pinned, documented.",
"Apply the intended misconfigurations; ticket each as deliberate.",
"Verify containment: vulnerable services unreachable outside the range.",
"Instrument: full logging on vulnerable hosts (the exploitation must be visible).",
"Brief the blue team: which vulnerabilities are deliberate and which paths are in scope.",
"Hand over with the vulnerability register.",
],
outputs=[
"Vulnerable-service inventory with versions.",
"Deliberate-misconfiguration register.",
"Containment and logging verification.",
],
pitfalls=[
"Vulnerable services reachable from production or the internet — containment first.",
"Undocumented vulnerabilities — the blue team wastes the exercise chasing stage props.",
"Vulnerable services with real data — canary data only.",
],
references=[
"Vulnerability-management literature; CVE documentation.",
],
exercise_note="Vulnerable-by-design targets are stage props — documented, contained, and never mistaken for real findings.",
),
dict(
slug="logging-pipeline-provisioning",
title="Exercise Logging Pipeline Provisioning",
description="Provision the exercise logging pipeline: collection, forwarding, and retention.",
tags=["grey-team","provisioning","logging","siem"],
risk="low", confirm=False,
purpose=("An exercise without telemetry is theater. This runbook provisions the logging pipeline "
"before any exercise traffic: endpoint forwarding, network taps, cloud audit streams, and the SIEM "
"workspace — with retention covering the exercise plus analysis time."),
when=[
"Before every exercise, as part of range provisioning.",
"When standing up persistent range logging.",
"To rebuild logging between iterations.",
],
prereq=[
"SIEM capacity for the exercise data volume.",
"Log-source inventory from the range design.",
"Retention policy for exercise data.",
],
procedure=[
"Deploy forwarders/agents on all range hosts; verify event flow per source.",
"Configure network-tap/SPAN ingestion and cloud-audit streams.",
"Build the exercise SIEM workspace: indices, dashboards, and the exercise codename tag.",
"Verify end-to-end: generate canary events on each source type and confirm SIEM arrival with latency measurement.",
"Configure retention: exercise data kept for the analysis window, then purged per policy.",
"Hand over with the logging-health dashboard and source inventory.",
],
outputs=[
"Log-source inventory with health status.",
"Canary-event verification per source.",
"Latency measurements.",
"Retention configuration.",
],
pitfalls=[
"Exercise traffic before logging verification — the first red action with no telemetry is lost data.",
"Retention shorter than the analysis window — keep data until the report is done.",
"No canary verification — 'forwarding configured' isn't 'forwarding working'.",
],
references=[
"NIST SP 800-92 (log management).",
],
exercise_note="Telemetry is the exercise's memory — provisioned and verified before anything happens, or the exercise never really happened.",
),
dict(
slug="exercise-data-seeding",
title="Exercise Data Seeding",
description="Seed canary data across the range: documents, credentials, and tripwires.",
tags=["grey-team","provisioning","canary","data"],
risk="low", confirm=False,
purpose=("Exercises need data worth stealing and tripwires worth tripping: canary documents on "
"shares, canary credentials in vaults, canary tokens in code. This provisioning plants the data "
"layer the red team hunts and the blue team defends — all fake, all tracked."),
when=[
"During range provisioning, after endpoints and shares exist.",
"For data-theft and DLP exercises.",
"To plant tripwires for detection validation.",
],
prereq=[
"Canary-data generation tooling.",
"Range file shares, mailboxes, and repos ready.",
"Canary registry: every planted item recorded.",
],
procedure=[
"Generate canary data: documents with canary patterns, fake credentials, API tokens, PII-shaped fakes.",
"Plant per the scenario map: shares, endpoints, mailboxes, repos, cloud storage.",
"Plant tripwires: canary files with alerting (canary tokens that beacon when used).",
"Record every planted item in the canary registry: location, type, expected alerts.",
"Verify plantings: spot-check that canary files exist and tripwires fire.",
"Hand over the canary registry to the white cell (sealed from red and blue as the scenario dictates).",
],
outputs=[
"Canary registry with locations and types.",
"Tripwire verification results.",
"Sealed registry handover.",
],
pitfalls=[
"Unregistered canary data — every planted item tracked, no exceptions.",
"Canary credentials that work on real systems — range-scoped only.",
"Tripwires the blue team doesn't know are tripwires — coordinate per the scenario's secrecy rules.",
],
references=[
"Canary-token literature; deception literature.",
],
exercise_note="Canary data is the exercise's bait and tripwire — planted deliberately, registered completely, and never real.",
),
dict(
slug="exercise-artifact-repository",
title="Exercise Artifact Repository Setup",
description="Set up the artifact repository for exercise plans, findings, and reports.",
tags=["grey-team","setup","artifacts","repository"],
risk="low", confirm=False,
purpose=("Exercises generate plans, rules of engagement, findings, timelines, and reports — all of "
"which need versioning, access control, and retention. This setup creates the exercise's document "
"home before the exercise starts."),
when=[
"At exercise kickoff, before planning artifacts accumulate.",
"For exercise programs needing cross-exercise trending.",
],
prereq=[
"Exercise codename and classification level.",
"Participant roster with roles (for access control).",
],
procedure=[
"Create the exercise workspace: plans, ROE, findings, timelines, reports sections.",
"Apply access control per role: red sees red, blue sees blue, grey sees all, observers see the white-card view.",
"Set up finding templates and severity scales for consistent reporting.",
"Configure retention and archival policy for exercise artifacts.",
"Brief participants on where things live and the naming conventions.",
],
outputs=[
"Exercise workspace with access control.",
"Finding/report templates.",
"Retention policy.",
],
pitfalls=[
"Findings in chat threads instead of the repository — centralize from day one.",
"Wrong access control leaking red plans to blue (or vice versa) — verify permissions.",
"No retention policy — exercise data lingering indefinitely.",
],
references=[
"Exercise-management literature.",
],
exercise_note="The repository is the exercise's institutional memory — set up before the first finding, or findings live in chat history.",
),
dict(
slug="rules-of-engagement-setup",
title="Rules of Engagement Setup",
description="Draft, approve, and publish exercise rules of engagement.",
tags=["grey-team","setup","roe","governance"],
risk="low", confirm=False,
purpose=("The ROE is the exercise's contract: what's in scope, what's forbidden, who authorizes what, "
"and what happens when something goes wrong. This setup produces a signed ROE before any red "
"action — no ROE, no exercise."),
when=[
"During exercise planning, before any execution.",
"When scope changes mid-exercise (ROE amendment).",
],
prereq=[
"Exercise objectives and scope proposal.",
"Stakeholder list for approvals.",
"Legal/HR review where required.",
],
procedure=[
"Draft the ROE: scope (hosts, accounts, networks), authorized techniques, forbidden actions, time windows.",
"Define the authorization chain: who approves what, how fast, and the emergency-stop authority.",
"Define handling rules: credentials, sensitive data, destructive techniques, production-adjacent systems.",
"Route for approvals: exercise director, system owners, legal/HR as needed — collect signatures.",
"Publish the signed ROE to the artifact repository; brief all participants.",
"Establish the amendment process for mid-exercise scope changes.",
],
outputs=[
"Signed rules of engagement.",
"Authorization chain with contacts.",
"Amendment process.",
],
pitfalls=[
"Verbal ROE — if it isn't signed, it isn't the ROE.",
"Forbidden actions left vague — enumerate them.",
"No emergency-stop authority defined — define it before you need it.",
],
references=[
"Penetration-testing ROE literature; PTES.",
],
exercise_note="The ROE is what makes red-team work a professional exercise instead of an incident — signed before anything runs.",
),
dict(
slug="exercise-network-time-sync",
title="Exercise Time Synchronization Setup",
description="Establish authoritative time sync across the range for timeline correlation.",
tags=["grey-team","setup","ntp","forensics"],
risk="low", confirm=False,
purpose=("Timelines are the exercise's evidence, and timelines need synchronized clocks. This setup "
"establishes authoritative NTP across the range so red actions, blue detections, and logs correlate "
"to the second."),
when=[
"During range setup, before exercise traffic.",
"When timeline disputes arise (retroactive fix is impossible — do it first).",
],
prereq=[
"Range network with an NTP source (simulator or upstream, documented).",
],
procedure=[
"Designate the authoritative NTP source for the range; document its stratum and source.",
"Configure all range hosts, network devices, and the SIEM to sync to it.",
"Verify offset on a sample of hosts (chrony/ntp sources, event-log timestamps).",
"Document the time zone policy (UTC everywhere recommended).",
"Re-verify at exercise start and after any range reset.",
],
outputs=[
"NTP design with source documentation.",
"Offset-verification results.",
"Time-zone policy.",
],
pitfalls=[
"Hosts syncing to different sources — one authority, no exceptions.",
"Assuming virtualization host time is correct — verify the whole chain.",
"Time-zone soup in timelines — UTC everywhere.",
],
references=[
"NTP documentation; forensic-timeline literature.",
],
exercise_note="A second of clock skew is a timeline dispute — synchronized time is the cheapest forensic control there is.",
),
dict(
slug="red-team-infrastructure-setup",
title="Red Team Infrastructure Setup",
description="Set up red-team attack infrastructure: C2, phishing, and tooling hosts.",
tags=["grey-team","setup","red-team","infrastructure"],
risk="low", confirm=False,
purpose=("The red team needs its own infrastructure: C2 servers, phishing domains, payload hosting, "
"tooling — built by the grey team to keep it contained, logged, and separate from real attacker "
"infrastructure. This setup builds it."),
when=[
"Before red-team execution phases.",
"For phishing scenarios needing mail infrastructure.",
],
prereq=[
"ROE authorizing the red infrastructure.",
"Isolated red-team network segment.",
"Canary domains and certificates.",
],
procedure=[
"Deploy the red-team segment: attack hosts, C2 servers (canary), payload staging.",
"Set up phishing infrastructure: canary domains, mail relay, landing pages — all clearly labeled.",
"Configure egress from the red segment through grey-team monitoring (all red traffic logged).",
"Issue the red team their access: VPN/jump credentials, tooling, the ROE boundaries.",
"Verify containment: red infrastructure can't reach production or the real internet beyond the simulator.",
"Hand over with the infrastructure inventory and monitoring confirmation.",
],
outputs=[
"Red-team infrastructure inventory.",
"Egress-monitoring verification.",
"Containment verification.",
],
pitfalls=[
"Red infrastructure with real internet egress — contain it.",
"Phishing domains that could confuse real users — canary naming, limited scope.",
"Unlogged red traffic — the grey team monitors its own red segment.",
],
references=[
"Red-team infrastructure literature (public).",
],
exercise_note="Red-team infrastructure is a stage weapon — functional, contained, monitored, and unmistakably exercise-owned.",
),
dict(
slug="blue-team-workspace-setup",
title="Blue Team Workspace Setup",
description="Set up the blue-team defense workspace: SIEM views, comms, and playbooks.",
tags=["grey-team","setup","blue-team","workspace"],
risk="low", confirm=False,
purpose=("The blue team needs their battle station: SIEM access with exercise views, communication "
"channels, IR playbooks, and the escalation paths. This setup builds it before the first alert.",
),
when=[
"Before blue-team execution phases.",
"For SOC-validation exercises.",
],
prereq=[
"Blue-team roster and roles.",
"SIEM exercise workspace from the logging pipeline.",
],
procedure=[
"Provision SIEM access with exercise-specific views, dashboards, and saved searches.",
"Set up communication channels: incident channel, escalation contacts, bridge details.",
"Load the IR playbooks being tested and the exercise's inject schedule (sealed until execution).",
"Configure alerting: exercise alerts routed to the blue team, tuned per the scenario.",
"Verify the blue team can see the range telemetry but not the red team's plans (access-control check).",
"Hand over with the workspace guide and comms plan.",
],
outputs=[
"Blue-team workspace with views and dashboards.",
"Communications plan.",
"Access-control verification.",
],
pitfalls=[
"Blue team with red-team visibility (or vice versa) — verify the access split.",
"Missing comms plan — the first incident without a bridge is chaos.",
"Playbooks loaded but untested — walk one before execution.",
],
references=[
"Incident-response literature; SOC operations guides.",
],
exercise_note="The blue team's workspace is their instrument panel — built and verified before the first alert, not during it.",
),
dict(
slug="white-cell-setup",
title="White Cell (Exercise Control) Setup",
description="Stand up the white cell: exercise control, adjudication, and safety monitoring.",
tags=["grey-team","setup","white-cell","control"],
risk="low", confirm=False,
purpose=("The white cell directs the exercise: controls the scenario, adjudicates disputes, monitors "
"safety, and calls the stops. This setup stands up the control function with its tools, "
"communications, and authorities before execution."),
when=[
"Before any multi-team exercise.",
"When the scenario needs dynamic control (injects, adjudication).",
],
prereq=[
"Exercise director designated with stop authority.",
"Scenario and inject schedule.",
"Monitoring feeds (grey-team visibility into red and blue).",
],
procedure=[
"Stand up the control workspace: scenario timeline, team-status boards, comms to all teams.",
"Load the inject schedule and adjudication criteria; seal red-team-sensitive material.",
"Establish the safety-monitoring feeds: range health, ROE-compliance watch, participant welfare.",
"Define the pause/stop procedures and rehearse the stop call once.",
"Brief all teams on the white cell's role: who to call, for what, how fast.",
"Hand over control to the exercise director at exercise start.",
],
outputs=[
"White-cell workspace and comms plan.",
"Sealed inject schedule.",
"Pause/stop procedures (rehearsed).",
],
pitfalls=[
"No rehearsed stop call — the first real stop shouldn't be the first practice.",
"White cell without independent monitoring — control needs its own feeds.",
"Unsealed injects leaking to teams — seal and verify.",
],
references=[
"Exercise-control literature; military white-cell doctrine (public).",
],
exercise_note="The white cell is the exercise's conscience and circuit breaker — stood up with authority before anything runs.",
),
dict(
slug="participant-onboarding",
title="Exercise Participant Onboarding",
description="Onboard exercise participants: briefings, access, and conduct agreements.",
tags=["grey-team","setup","onboarding","participants"],
risk="low", confirm=False,
purpose=("Participants need briefing, access, and clear conduct rules before the exercise — not "
"discovered mid-scenario. This onboarding gets everyone ready, badged, and bound by the ROE."),
when=[
"Before exercise execution, after planning.",
"When new participants join mid-exercise.",
],
prereq=[
"Participant roster with roles and clearances.",
"ROE signed; NDA/conduct agreements ready.",
],
procedure=[
"Brief each team on the scenario, objectives, ROE, and conduct expectations.",
"Provision access: accounts, VPN, workspace, comms channels — per role.",
"Collect signed conduct agreements and ROE acknowledgments.",
"Run the communications check: every participant reachable on the exercise channels.",
"Brief the safety procedures: how to report a problem, who can stop the exercise.",
"Record onboarding completion per participant.",
],
outputs=[
"Onboarding checklist per participant.",
"Signed acknowledgments.",
"Access-provisioning record.",
],
pitfalls=[
"Unbriefed participants discovering the ROE mid-exercise — brief everyone, no exceptions.",
"Access provisioned late — access before the start, not during.",
"Missing acknowledgments — collect them before execution.",
],
references=[
"Exercise-management literature.",
],
exercise_note="Onboarding is the exercise's social contract — everyone briefed, badged, and bound before the clock starts.",
),
dict(
slug="scenario-load-and-validation",
title="Scenario Load and Validation",
description="Load the exercise scenario and validate it end-to-end before execution.",
tags=["grey-team","setup","scenario","validation"],
risk="low", confirm=False,
purpose=("The scenario — attack paths, injects, objectives — must work before the exercise starts. "
"This validation walks the scenario end-to-end in the range: every attack path executable, every "
"inject deliverable, every detection reachable — fixing the stage before the audience arrives."),
when=[
"After range provisioning, before exercise execution.",
"When the scenario changes (re-validate).",
],
prereq=[
"Scenario document with attack paths and injects.",
"Provisioned range with logging verified.",
],
procedure=[
"Walk each red attack path in the range: verify the vulnerabilities exist, the paths execute, the canary objectives are reachable.",
"Validate each inject: deliverability, timing, and the expected team response surface.",
"Verify the blue team's detection opportunities: does the telemetry for each path actually flow?",
"Check the timing: does the scenario fit the exercise window?",
"Fix or cut what doesn't work; document deviations from the scenario document.",
"Sign off scenario-readiness with the exercise director.",
],
outputs=[
"Scenario-validation report with deviations.",
"Timing analysis.",
"Readiness sign-off.",
],
pitfalls=[
"Unvalidated scenarios — the exercise discovers the broken path live.",
"Skipping the blue-team detection check — a path with no telemetry is a wasted path.",
"No timing check — scenarios that don't fit the window.",
],
references=[
"Exercise-design literature.",
],
exercise_note="Scenario validation is the dress rehearsal — every path walked, every inject tested, before the clock starts.",
),
dict(
slug="comms-plan-setup",
title="Exercise Communications Plan Setup",
description="Establish exercise communications: channels, schedules, and escalation paths.",
tags=["grey-team","setup","communications"],
risk="low", confirm=False,
purpose=("Exercises run on communications: team channels, control nets, escalation paths, and the "
"schedule that keeps everyone synchronized. This setup builds the comms plan before execution.",
),
when=[
"During exercise planning.",
"For distributed exercises especially.",
],
prereq=[
"Participant roster and roles.",
"Communication tooling (chat, bridge, radio as applicable).",
],
procedure=[
"Define the nets: team channels, white-cell control net, observer net, emergency net.",
"Publish the communications schedule: check-ins, sync points, hot-wash timing.",
"Document escalation paths: incident → white cell → exercise director → stakeholders.",
"Test every channel before the exercise (comms check).",
"Define EMCON-style rules if the scenario needs them (when teams go quiet).",
"Hand over the comms card to every participant.",
],
outputs=[
"Communications plan with nets and schedules.",
"Escalation-path documentation.",
"Comms-check results.",
],
pitfalls=[
"Untested channels — the comms check is mandatory.",
"No emergency net — define it before the emergency.",
"Escalation paths that end in voicemail — verify humans answer.",
],
references=[
"Exercise-management literature; incident-comms guides.",
],
exercise_note="Communications are the exercise's nervous system — built, tested, and carded before the first transmission.",
),
dict(
slug="exercise-calendar-scheduling",
title="Exercise Calendar and Scheduling",
description="Schedule the exercise: phases, windows, blackouts, and stakeholder notifications.",
tags=["grey-team","setup","scheduling"],
risk="low", confirm=False,
purpose=("Exercises need calendars: phase windows, blackout periods, maintenance conflicts, and "
"stakeholder notifications. This scheduling deconflicts the exercise with reality before it collides.",
),
when=[
"During exercise planning.",
"When phases have hard time constraints.",
],
prereq=[
"Exercise phase plan with durations.",
"Organizational calendar (change freezes, holidays, maintenance).",
"Stakeholder notification list.",
],
procedure=[
"Map phases to calendar windows with buffers between them.",
"Deconflict: change freezes, business peaks, maintenance windows, other exercises.",
"Define blackout periods (no exercise traffic) and quiet hours.",
"Notify stakeholders: system owners, SOC, helpdesk, leadership — with the exercise codename and contacts.",
"Publish the master schedule; establish the change process for slips.",
"Confirm the schedule at the final planning sync.",
],
outputs=[
"Master exercise schedule.",
"Deconfliction record.",
"Stakeholder-notification log.",
],
pitfalls=[
"Undeconflicted exercises colliding with change freezes — check the calendar.",
"Stakeholders learning about the exercise from an alert — notify first.",
"No buffers between phases — schedules slip, buffers absorb.",
],
references=[
"Exercise-management literature.",
],
exercise_note="The calendar is where the exercise meets reality — deconflicted before it starts, or reality deconflicts it for you.",
),
]
