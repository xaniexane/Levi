# Red team topics — chunk 1: reconnaissance (12)
# Each dict: slug, title, description, tags, risk, confirm, blue_kw (priority-ordered),
# purpose, when, prereq (extra beyond the standard authorization lines), procedure,
# outputs, pitfalls, references, blue_note.

RED_1 = [
dict(
slug="passive-recon-osint",
title="Passive Reconnaissance and OSINT",
description="Gather intelligence on a target organization without touching its systems: domains, people, technology stack, and exposure.",
tags=["red-team","reconnaissance","osint","passive"],
risk="low", confirm=False,
blue_kw=["osint","reconnaissance","threat-intel","passive"],
purpose=("Map the target's public footprint before any active testing begins. Passive reconnaissance "
"collects domains, IP ranges, employee names, technology choices, and leaked credentials from public "
"sources only — no packets sent to target infrastructure. The output is the target profile that scopes "
"every later active phase and keeps it inside authorization."),
when=[
"At the start of any authorized assessment, to define scope from public data before active scanning.",
"When the rules of engagement forbid active probing and only passive collection is allowed.",
"To build phishing pretexts and target lists from job postings, social media, and conference talks.",
"To find credential leaks, exposed documents, and forgotten subdomains the blue team should have found first.",
],
prereq=[
"Scope document listing which organizations, domains, and brands are in-bounds for collection.",
"Agreement on what counts as public: search engines, certificate logs, code repos, social media — never pretexted access.",
],
procedure=[
"Enumerate the organization's domain portfolio: start from the primary domain, then pull certificate transparency logs (crt.sh) for all certificates issued to the org and its variants.",
"Resolve each discovered name passively via public DNS history (SecurityTrails-style records, DNSDumpster) — never query the target's nameservers directly in this phase.",
"Harvest employee names, roles, and emails from LinkedIn, conference speaker lists, and GitHub org membership; build the target list for later social-engineering tests.",
"Search code repositories (GitHub, GitLab) for the org's name plus secrets keywords; record any live API keys, tokens, or internal hostnames — report immediately, do not use them.",
"Check breach corpora (HaveIBeenPwned, DeHashed-style sources) for employee credentials that password-spraying tests will later validate against policy.",
"Map the technology stack from job postings (\"we use Okta, CrowdStrike, Palo Alto\"), Wappalyzer-style public scans others published, and vendor case studies.",
"Collect all findings into a target profile: domains, IPs (from public BGP/ASN data), key personnel, tech stack, and third-party exposure — hand this to the blue team as the recon report card.",
],
outputs=[
"Target profile document: domains, subdomains, IP ranges, personnel, tech stack.",
"List of public exposures (leaked creds, exposed docs, forgotten assets) with timestamps.",
"Scoped target list for the active phases, each entry tied to an in-scope asset.",
],
pitfalls=[
"Drifting into active probing (port scans, direct DNS queries) during a passive-only phase — log every query source.",
"Collecting on out-of-scope entities with similar names; verify org affiliation before recording.",
"Using discovered credentials instead of reporting them — that crosses from recon into unauthorized access.",
],
references=[
"MITRE ATT&CK: Gather Victim Identity Information (T1589), Search Open Technical Databases (T1596).",
"OWASP: public OSINT guidance for penetration testing.",
],
blue_note="the blue team's own OSINT and exposure monitoring should have found the same public footprint first — every finding here is a gap in their external attack-surface management.",
),
dict(
slug="dns-enumeration",
title="DNS Enumeration",
description="Enumerate a target's DNS footprint — zone transfers, record types, and brute-forced names — to map infrastructure the blue team must defend.",
tags=["red-team","reconnaissance","dns"],
risk="moderate", confirm=True,
blue_kw=["dns","enumeration","reconnaissance"],
purpose=("Turn a domain name into an infrastructure map. DNS enumeration attempts zone transfers, "
"queries every record type, and brute-forces likely hostnames to reveal mail servers, VPN endpoints, "
"dev systems, and cloud assets. Everything found becomes a candidate target for later phases — and a "
"finding for the blue team if it was exposed unintentionally."),
when=[
"Early in the active recon phase, after passive collection has defined the domain set.",
"When testing whether the organization's DNS servers permit zone transfers (AXFR).",
"To discover forgotten dev/staging hostnames that never made it into asset inventory.",
"Before phishing tests, to identify mail exchangers and SPF/DKIM/DMARC posture.",
],
prereq=[
"Written authorization naming the domains and nameservers in scope.",
"Rate limits agreed: DNS brute-forcing can look like a DoS against small authoritative servers.",
],
procedure=[
"Attempt a zone transfer (AXFR) against each authoritative nameserver: `dig axfr @ns1.target.com target.com`. Record success or refusal — a successful transfer is itself a finding.",
"Query all standard record types (A, AAAA, MX, TXT, SRV, CNAME, NS, SOA) and note TTLs, mail exchangers, and TXT records leaking internal tooling.",
"Run DNS brute-forcing with a curated wordlist (subdomains-top1mil style) against the domain, throttled to the agreed rate; resolve candidates and fingerprint responses.",
"Probe for DNS zone walking on DNSSEC-signed zones (NSEC enumeration) to recover the full zone contents without brute force.",
"Check for subdomain takeover candidates: CNAME records pointing at deprovisioned cloud services (S3, Azure, Heroku, GitHub Pages).",
"Validate every discovered hostname: resolve, check HTTP response, and classify (prod, dev, forgotten, third-party) before adding it to the target list.",
"Deliver the DNS map to the blue team with each record annotated: expected, forgotten, or misconfigured.",
],
outputs=[
"Complete DNS record inventory per in-scope domain, including AXFR result.",
"List of brute-forced hostnames with classification and HTTP fingerprints.",
"Subdomain-takeover candidates with proof of dangling CNAME.",
],
pitfalls=[
"Aggressive brute-forcing tripping the target's rate limits or looking like an attack from an unrecognized source — stay inside the agreed rate and source IPs.",
"Treating wildcard DNS responses as real hosts; always verify with a canary query.",
"Forgetting to test the secondary/hidden nameservers, not just the primaries.",
],
references=[
"MITRE ATT&CK: Gather Victim Network Information — DNS (T1590.002).",
"OWASP Testing Guide: DNS enumeration.",
],
blue_note="their DNS monitoring and asset inventory should account for every name found — AXFR success or dangling CNAMEs are blue-team misconfigurations to fix.",
),
dict(
slug="subdomain-discovery",
title="Subdomain Discovery",
description="Discover subdomains via certificate logs, brute-forcing, and search engines to expose forgotten assets for the blue team to inventory.",
tags=["red-team","reconnaissance","subdomain"],
risk="moderate", confirm=True,
blue_kw=["subdomain","asset-discovery","reconnaissance"],
purpose=("Find every subdomain — including the forgotten dev, staging, and marketing sites the "
"organization lost track of. Subdomain discovery combines certificate-transparency mining, "
"brute-forcing, search-engine dorking, and alt-DNS sources. Each forgotten subdomain is a potential "
"initial-access vector and a blue-team inventory gap."),
when=[
"During active recon, to build the full web-attack surface before application testing.",
"When the org has undergone M&A and inherited unknown DNS estates.",
"To feed takeover testing: every CNAME to an external service is a candidate.",
"As a purple-team exercise: compare red's discovered list against blue's CMDB.",
],
prereq=[
"Authorization covering the parent domains; discovered subdomains of the same org are in scope by definition.",
"Agreed wordlists and throttling for brute-force phases.",
],
procedure=[
"Pull certificate transparency logs for the target domains (crt.sh, censys-style CT search) and extract every dNSName — this usually yields the largest initial set.",
"Run subdomain brute-forcing with a tiered wordlist (small, then large) using massdns or gobuster-style tools at the agreed rate; resolve and keep only live names.",
"Query search engines with site: dorks and pull results from VirusTotal/URLScan-style passive sources for historical subdomains.",
"Attempt DNS zone transfers and NSEC walking as a secondary source (see the DNS enumeration playbook).",
"Probe each live subdomain with HTTP/HTTPS, record status codes, titles, and server banners; screenshot the interesting ones.",
"Classify each finding: production, staging/dev, marketing, forgotten, third-party-hosted, takeover-candidate.",
"Hand the classified inventory to the blue team — the delta between this list and their CMDB is the exercise score.",
],
outputs=[
"Classified subdomain inventory with HTTP fingerprints and screenshots of interest.",
"Takeover-candidate list with dangling-service evidence.",
"CMDB delta report for the blue team.",
],
pitfalls=[
"Counting wildcard-DNS artifacts as real subdomains — verify with randomized canary labels.",
"Stopping at CT logs; the long tail of forgotten assets usually comes from brute-forcing.",
"Scanning third-party-hosted subdomains aggressively — respect the hosting provider's acceptable-use terms in the ROE.",
],
references=[
"MITRE ATT&CK: Gather Victim Network Information — Domain Properties (T1590.002).",
"OWASP: subdomain enumeration methodology.",
],
blue_note="their external asset inventory should already contain every name found — the delta is the measurable outcome of this test.",
),
dict(
slug="certificate-transparency-mining",
title="Certificate Transparency Mining",
description="Mine public certificate transparency logs for a target's domains to reveal infrastructure without sending a single packet to the target.",
tags=["red-team","reconnaissance","certificate-transparency","passive"],
risk="low", confirm=False,
blue_kw=["certificate","transparency","reconnaissance","passive"],
purpose=("Certificate transparency logs are a public, append-only record of every certificate issued "
"for a domain. Mining them reveals subdomains, internal hostnames accidentally exposed, cloud "
"front-ends, and partner integrations — entirely passively. It is often the single highest-yield "
"passive technique available."),
when=[
"During passive recon, before any active phase begins.",
"When the ROE restricts active probing but public data mining is allowed.",
"To find internal hostnames (vpn-internal, jira-dev) leaked into public certificates.",
"To monitor for rogue certificates issued for the org's domains (defensive use too).",
],
prereq=[
"Scope limited to the target's domains and obvious variants.",
"No target contact occurs, so authorization is for collection and reporting only.",
],
procedure=[
"Query crt.sh for `%.target.com` and export the full certificate list, including expired certificates — old certs reveal retired infrastructure worth checking.",
"Extract every unique dNSName, normalize (strip wildcards), and deduplicate into a candidate subdomain list.",
"Repeat against at least one second CT source (Censys, Google's CT search) to catch log-sharding gaps.",
"Flag internal-looking names (intranet, vpn, dev, staging, mgmt, backup) and names pointing at SaaS/cloud providers.",
"Cross-reference with the passive DNS history to date each name's first and last sighting.",
"Deliver the CT-derived inventory to the blue team with a note on which internal names should never have been in public certificates.",
],
outputs=[
"Deduplicated subdomain/hostname list sourced purely from CT logs.",
"Internal-name exposure findings with certificate serials as evidence.",
"Historical view: first/last seen dates per name.",
],
pitfalls=[
"CT logs lag issuance by hours — very new certs may be missing; re-query before active phases.",
"Pre-certificates and duplicates inflate counts; deduplicate on the parsed dNSName set.",
"Assuming CT coverage is complete — some private CAs don't log; combine with other passive sources.",
],
references=[
"MITRE ATT&CK: Search Open Technical Databases — CT logs (T1596.005).",
"RFC 6962: Certificate Transparency.",
],
blue_note="their certificate inventory and issuance policy should already track every name found — internal hostnames in public certs are a policy failure to remediate.",
),
dict(
slug="network-scanning-nmap",
title="Network Scanning with Nmap",
description="Scan in-scope networks with Nmap to map live hosts, open ports, and services — the foundation every later phase builds on.",
tags=["red-team","reconnaissance","scanning","nmap"],
risk="moderate", confirm=True,
blue_kw=["network-scanning","nmap","reconnaissance","port-scan"],
purpose=("Produce the authoritative map of what is reachable and listening inside the authorized scope: "
"live hosts, open TCP/UDP ports, service banners, and OS guesses. Done carefully, the scan stays "
"inside the agreed rate and window; done carelessly it looks like an attack and disrupts fragile "
"hosts. The scan output feeds vulnerability validation and targeting for the whole exercise."),
when=[
"At the start of active testing against a network range, after scope is signed.",
"When the blue team wants to measure whether their IDS/IPS detects and alerts on scanning.",
"To validate the asset inventory: the scan finds the hosts nobody documented.",
"Before any exploitation phase — you cannot test what you have not mapped.",
],
prereq=[
"Written authorization with exact IP ranges/CIDRs, scan window, and rate limits.",
"Exclusion list: fragile hosts (OT, medical, legacy) that must not be scanned aggressively or at all.",
"Blue-team notification procedure for the scan window, per the ROE.",
],
procedure=[
"Start with host discovery only (`nmap -sn`) across the in-scope ranges to build the live-host list without touching ports.",
"Run a top-ports SYN scan (`nmap -sS --top-ports 1000`) at the agreed timing template (T2/T3 for fragile environments, never T5).",
"Follow up with full-port scans on hosts of interest and UDP top-ports on infrastructure hosts (DNS, SNMP, VPN).",
"Version-detect (`-sV`) and OS-detect (`-O`) the listening services; save all output in all three formats (`-oA scanname`).",
"Run safe NSE scripts only (`--script safe` or `default` minus intrusive) for banner and misconfiguration checks — no exploit scripts without explicit authorization.",
"Correlate results: flag unexpected open ports (database ports on web servers, management interfaces on user VLANs) as findings.",
"Deliver the scan report with the exact commands, timestamps, and rate used, so the blue team can match it against their IDS alerts.",
],
outputs=[
"Host/port/service inventory in machine-readable (XML/grepable) and human-readable formats.",
"Anomaly list: unexpected open ports and services per host.",
"Scan telemetry summary (packets, duration, rate) for blue-team detection matching.",
],
pitfalls=[
"Full-speed scans against fragile or OT networks — always start slow and honor the exclusion list.",
"Forgetting UDP: DNS, SNMP, and VPN services hide there and are frequently the way in.",
"Leaving default NSE scripts that are intrusive; audit the script set before running.",
],
references=[
"MITRE ATT&CK: Network Service Discovery (T1046), Remote System Discovery (T1018).",
"Nmap documentation: timing templates and scan types.",
],
blue_note="their IDS/IPS should have fired on the scan itself — the scan report doubles as a detection-validation artifact for their network monitoring.",
),
dict(
slug="service-fingerprinting",
title="Service Fingerprinting",
description="Identify exact services and versions behind open ports to target vulnerability validation precisely and avoid blind exploitation.",
tags=["red-team","reconnaissance","fingerprinting"],
risk="moderate", confirm=True,
blue_kw=["service","fingerprint","banner","version"],
purpose=("Turn 'port 443 open' into 'nginx 1.18.0 on Ubuntu with a 2019 OpenSSL'. Precise service "
"fingerprinting lets later phases test only vulnerabilities that plausibly apply, which keeps the "
"exercise safe and credible. It also exposes version-disclosure misconfigurations the blue team "
"should have suppressed."),
when=[
"Immediately after port scanning, before any vulnerability validation.",
"When the blue team claims banner obfuscation is in place — verify it.",
"To build the version inventory that vulnerability mapping consumes.",
],
prereq=[
"Authorization covering the scanned hosts; fingerprinting is active probing.",
"Same rate/window constraints as the network scan phase.",
],
procedure=[
"Run Nmap version detection (`-sV --version-intensity 5`) against all open ports found in the scan phase.",
"Manually verify ambiguous results: pull HTTP headers, TLS certificates, SMTP/FTP/SSH banners, and SMB dialects by hand.",
"Check for version-disclosure headers (Server, X-Powered-By) and verbose error pages that leak stack details.",
"Fingerprint web applications with technology-detection tools and manual inspection (cookies, JS bundles, HTML comments).",
"Record exact product + version + OS guess per service in a structured inventory.",
"Map each version to known CVEs (offline database, never live exploit-db queries from the range) to build the candidate vulnerability list.",
"Flag information-disclosure findings (verbose banners, debug endpoints) separately — they are blue-team hardening gaps even before any exploitation.",
],
outputs=[
"Service/version inventory per host with confidence notes.",
"Candidate vulnerability map (version → CVE) for the exploitation phase.",
"Information-disclosure findings with evidence.",
],
pitfalls=[
"Trusting a single banner — load balancers and WAFs lie; verify behind them where in scope.",
"Version-intensity 9+ probes can crash fragile services; keep intensity moderate on unknown hosts.",
"Confusing honeypot banners with real services; note anomalies for the blue team.",
],
references=[
"MITRE ATT&CK: Network Service Discovery (T1046).",
"OWASP: fingerprinting web application frameworks.",
],
blue_note="every version disclosed is a hardening input — their baseline should suppress banners and their vuln-management should already track these versions.",
),
dict(
slug="cloud-asset-discovery",
title="Cloud Asset Discovery",
description="Discover a target's cloud assets — storage buckets, apps, functions, and APIs — from public sources and naming conventions.",
tags=["red-team","reconnaissance","cloud"],
risk="moderate", confirm=True,
blue_kw=["cloud","asset-discovery","s3","storage"],
purpose=("Organizations lose track of cloud assets faster than any other infrastructure. This "
"playbook discovers S3 buckets, Azure blobs, GCP buckets, cloud apps, and serverless endpoints "
"belonging to the target using naming conventions, certificate logs, and public enumeration — "
"without touching the target's own accounts."),
when=[
"When the target is known to be cloud-heavy (job postings, tech stack say AWS/Azure/GCP).",
"To find misconfigured storage and exposed cloud apps before the application-testing phase.",
"As input to takeover and misconfiguration testing.",
],
prereq=[
"Authorization covering the target's cloud footprint; discovered assets of the same org are in scope.",
"ROE note: only read public metadata — never attempt to write to or list private bucket contents beyond confirming exposure.",
],
procedure=[
"Generate candidate bucket/storage names from the org's domains, brands, and product names (permutations with dev/staging/backup suffixes).",
"Check each candidate for existence and public-listability using HEAD/GET requests; record which allow listing vs. which merely exist.",
"For listable buckets, inventory only the object keys (names), never download private content beyond a single canary file to prove exposure.",
"Mine certificate logs and passive DNS for cloud-fronted hostnames (*.cloudfront.net, *.azurewebsites.net, *.appspot.com) tied to the org.",
"Enumerate the org's public cloud apps: check for exposed management consoles, unauthenticated APIs, and serverless endpoints.",
"Classify every asset: intended-public, misconfigured, or forgotten; screenshot and timestamp the evidence.",
"Report misconfigurations to the blue team immediately (they are live exposures), and fold the asset list into the test scope.",
],
outputs=[
"Cloud asset inventory with exposure classification per asset.",
"Misconfigured-storage findings with timestamped evidence (reported immediately).",
"Cloud app/API attack surface list for later phases.",
],
pitfalls=[
"Downloading private data from an open bucket to 'prove' exposure — one canary file is enough; more is a data-handling incident.",
"Bucket-name permutations can collide with unrelated third parties; verify ownership signals before claiming.",
"Forgetting regional endpoints — a bucket may exist in a region your tool didn't check.",
],
references=[
"MITRE ATT&CK: Gather Victim Network Information — Cloud (T1590.005).",
"Cloud provider docs: storage access logging and public-access blocks.",
],
blue_note="their cloud security posture management should have flagged every misconfigured asset found — each one is a CSPM coverage gap.",
),
dict(
slug="exposed-service-review",
title="Exposed Service Review",
description="Review the target's internet-exposed services via third-party scan data to find forgotten RDP, databases, and management interfaces.",
tags=["red-team","reconnaissance","exposure"],
risk="low", confirm=False,
blue_kw=["exposure","shodan","internet-facing","scan-data"],
purpose=("Use third-party internet scan datasets (the Shodan/Censys model) to review what the target "
"exposes to the internet — without scanning it yourself. Forgotten RDP, databases, Elasticsearch, "
"and management interfaces show up here first. This is the cheapest high-value recon available and "
"entirely passive."),
when=[
"During passive recon, to prioritize which exposed services deserve active testing.",
"When the ROE forbids active scanning but third-party data review is allowed.",
"Quarterly as a purple-team hygiene check: has the exposure changed?",
],
prereq=[
"Scope: the target's netblocks and domains; third-party data only, no direct probing in this phase.",
],
procedure=[
"Query internet-scan datasets for the target's ASN/netblocks; pull banners for all exposed services.",
"Filter for high-risk exposures: RDP (3389), SMB (445), databases (3306/5432/27017/6379), Elasticsearch (9200), management (22 with default creds hints, 8080, 8443).",
"Check each exposure's banner for default credentials indicators, version disclosure, and honeypot signatures.",
"Cross-reference exposures against the blue team's declared internet footprint — anything undeclared is a finding.",
"Prioritize the exposure list by exploitability and data sensitivity for the active testing phases.",
"Deliver the exposure review with screenshots and first-seen dates from the scan datasets.",
],
outputs=[
"Prioritized internet-exposure inventory with banners and first-seen dates.",
"Undeclared-exposure findings (in scan data but not in the blue team's footprint).",
"Targeting priority list for active phases.",
],
pitfalls=[
"Stale scan data — verify critical exposures are still live before building test plans on them.",
"Honeypots in scan datasets — note them; the blue team may be running deception you should account for.",
"Confusing CDN/WAF IPs with origin infrastructure.",
],
references=[
"MITRE ATT&CK: Gather Victim Network Information (T1590).",
"Internet-scan dataset documentation (Shodan/Censys query syntax).",
],
blue_note="their external attack-surface program should produce this same list continuously — any delta is a monitoring gap, not just a finding.",
),
dict(
slug="personnel-osint",
title="Personnel OSINT for Pretexting",
description="Build targeted personnel profiles from public sources to craft believable pretexts for authorized social-engineering tests.",
tags=["red-team","reconnaissance","osint","social-engineering"],
risk="low", confirm=False,
blue_kw=["osint","personnel","pretexting","social-engineering"],
purpose=("Social-engineering tests succeed or fail on pretext quality, and pretext quality comes from "
"personnel OSINT: who works where, who reports to whom, what projects they discuss publicly, what "
"their writing style looks like. This playbook builds those profiles from public sources only, "
"producing the raw material for authorized phishing and vishing tests."),
when=[
"Before any authorized phishing, vishing, or physical social-engineering test.",
"To identify high-value targets (finance, IT admins, executives) within scope.",
"To test whether the org's public footprint makes pretexting trivially easy.",
],
prereq=[
"Social-engineering authorization in the ROE: named techniques allowed, target groups, and no-go topics (medical, family emergencies).",
"Agreement that no pretext will impersonate law enforcement, and no real credentials will be harvested beyond proof-of-click.",
],
procedure=[
"Enumerate in-scope personnel from LinkedIn, company team pages, and conference programs; record name, role, manager hints, and tenure.",
"Build org-chart approximations from reporting-line hints in bios (\"reports to the CISO\", team sizes).",
"Collect writing-style samples from public posts and talks for pretext realism (tone, jargon, signature blocks).",
"Identify opportune pretexts: new-hire onboarding, IT helpdesk, vendor invoices, conference follow-ups — all tied to real public facts.",
"Rank targets by role sensitivity and public exposure; submit the target list for client approval before any contact.",
"Document which public sources yielded each profile element — this becomes the blue team's awareness-training material.",
],
outputs=[
"Approved target list with role sensitivity rankings.",
"Pretext dossiers per target: public facts, plausible scenario, approved contact method.",
"Source map showing which public disclosures enabled each pretext (training input).",
],
pitfalls=[
"Contacting anyone before the target list is approved — the ROE approval is the control.",
"Using non-public or hacked data sources for profiling; stay strictly public.",
"Pretexts that cause real distress (layoffs, emergencies) — banned by any sane ROE; keep them boring and professional.",
],
references=[
"MITRE ATT&CK: Gather Victim Identity Information (T1589), Phishing (T1566).",
"Social-Engineer Framework: OSINT methodology (public).",
],
blue_note="the source map doubles as their security-awareness curriculum — every public disclosure that enabled a pretext is a coaching opportunity, not just a test setup step.",
),
dict(
slug="wireless-recon",
title="Wireless Reconnaissance",
description="Survey wireless networks around authorized facilities to find rogue APs, weak encryption, and misconfigured enterprise Wi-Fi.",
tags=["red-team","reconnaissance","wireless"],
risk="moderate", confirm=True,
blue_kw=["wireless","wifi","rogue-ap","reconnaissance"],
purpose=("Map the wireless landscape in and around the authorized facility: corporate SSIDs, guest "
"networks, rogue access points, and neighboring networks that could be attack vectors. Wireless is "
"often the soft perimeter — this survey tells the blue team what their airspace actually looks like."),
when=[
"During on-site assessments where wireless is in scope.",
"To hunt rogue APs and evil twins before the wireless attack phase.",
"To validate WPA2-Enterprise configuration and certificate validation behavior.",
],
prereq=[
"On-site authorization with the physical areas and times defined.",
"Passive monitoring only in this phase — no deauthentication or association without the attack-phase authorization.",
"Local radio regulations acknowledged (passive receive is fine; transmission rules vary).",
],
procedure=[
"Perform a passive wardrive/walkthrough with a monitor-mode adapter, recording SSIDs, BSSIDs, channels, signal strength, and encryption types (use kismet/airodump-ng style tooling).",
"Identify the corporate SSIDs and map their coverage, channel overlap, and signal leakage outside the facility.",
"Flag rogue APs: BSSIDs broadcasting corporate SSIDs that are not in the blue team's AP inventory.",
"Capture WPA handshakes passively only where authorized for later offline analysis — never force deauthentications in the recon phase.",
"Test enterprise Wi-Fi behavior from a client perspective: does the supplicant validate the RADIUS certificate, or will it connect to any AP with the right SSID?",
"Correlate findings with the blue team's wireless inventory and produce the rogue-AP list with locations and signal data.",
],
outputs=[
"Wireless survey map: SSIDs, BSSIDs, encryption, signal heatmap.",
"Rogue AP findings with location estimates.",
"Enterprise Wi-Fi misconfiguration notes (cert validation, weak EAP methods).",
],
pitfalls=[
"Accidentally transmitting (probing, associating) during a passive-only phase — use monitor mode and verify no TX.",
"Capturing neighboring networks' traffic content — record metadata only, per the ROE and local law.",
"Missing 5/6 GHz bands — survey all bands the facility uses.",
],
references=[
"MITRE ATT&CK: Network Service Discovery via wireless (T1046); Rogue AP techniques.",
"Wi-Fi Alliance: enterprise configuration guidance.",
],
blue_note="their wireless IDS should corroborate the rogue-AP list — rogues found by red but missed by WIDS are a detection gap.",
),
dict(
slug="ad-recon-anonymous",
title="Anonymous Active Directory Recon",
description="Enumerate Active Directory anonymously (null sessions, LDAP binds) to measure what an unauthenticated attacker can learn.",
tags=["red-team","reconnaissance","active-directory"],
risk="moderate", confirm=True,
blue_kw=["active-directory","ldap","enumeration","anonymous"],
purpose=("Measure exactly how much AD intelligence an unauthenticated attacker can gather: null-session "
"shares, anonymous LDAP binds, and unauthenticated RPC endpoints. The less available anonymously, "
"the harder the attacker's first step. Every anonymous disclosure is a hardening finding."),
when=[
"Early in internal assessments, before credentialed access is obtained.",
"To validate that anonymous LDAP binds and null sessions are disabled as policy requires.",
"As a baseline: re-run after hardening to prove the disclosures are gone.",
],
prereq=[
"Authorization for the AD environment; anonymous techniques only in this phase.",
"Agreement that any credentials discovered will be reported, not used, until the credentialed phase is authorized.",
],
procedure=[
"Test null-session access to IPC$ and enumerate accessible shares with smbclient-style tooling.",
"Attempt anonymous LDAP binds and enumerate the naming contexts, then pull user/computer objects where allowed.",
"Query unauthenticated RPC endpoints (epmapper) for exposed interfaces.",
"Enumerate domain password policy, lockout policy, and Kerberos policy via anonymous-accessible attributes.",
"Document every object and attribute readable without credentials, with the exact query used.",
"Report the anonymous disclosure inventory to the blue team as hardening findings before proceeding to credentialed phases.",
],
outputs=[
"Anonymous disclosure inventory: shares, LDAP objects, policies readable without auth.",
"Exact queries/commands used, for blue-team reproduction.",
"Hardening recommendations per disclosure (GPO settings to change).",
],
pitfalls=[
"Using any discovered credential in this phase — report it and wait for the credentialed phase.",
"Assuming 'anonymous bind failed' means secure — verify with multiple tools; some servers fail binds but still leak via other endpoints.",
"Overlooking IPv6 LDAP and alternate DCs — test all domain controllers in scope.",
],
references=[
"MITRE ATT&CK: Permission Groups Discovery (T1069), Account Discovery (T1087).",
"Microsoft: hardening LDAP signing and channel binding guidance.",
],
blue_note="their AD hardening baseline should make this inventory nearly empty — every entry is a GPO or configuration fix with a known remediation.",
),
dict(
slug="web-technology-fingerprinting",
title="Web Technology Fingerprinting",
description="Fingerprint web applications' frameworks, CMS, and third-party components to scope application testing and flag outdated stacks.",
tags=["red-team","reconnaissance","web","fingerprinting"],
risk="low", confirm=False,
blue_kw=["web","fingerprint","cms","technology"],
purpose=("Identify the frameworks, CMS platforms, JavaScript libraries, and third-party integrations "
"behind each in-scope web application. Precise fingerprinting focuses application testing on the "
"right vulnerability classes and flags end-of-life components before a single payload is sent."),
when=[
"After subdomain discovery, before web application testing begins.",
"When the blue team wants an inventory of their public web stack versions.",
"To detect shadow IT: CMS instances nobody in IT recognizes.",
],
prereq=[
"Passive-leaning: headers, HTML, JS bundles, and public responses only — no aggressive crawling in this phase.",
"In-scope application list from the subdomain inventory.",
],
procedure=[
"Collect HTTP response headers, cookies, HTML meta tags, and JavaScript bundle names for each application.",
"Identify CMS/framework signatures (wp-content, Drupal headers, Next.js markers, Laravel cookies) and record versions where disclosed.",
"Inventory third-party scripts and integrations (analytics, chat widgets, payment processors) — each is supply-chain surface.",
"Check version disclosure against EOL databases; flag end-of-life frameworks as findings immediately.",
"Note debug endpoints, exposed .git directories, and backup files visible in responses.",
"Produce the per-application technology inventory with EOL flags and shadow-IT candidates.",
],
outputs=[
"Per-application technology inventory with versions and confidence.",
"EOL/outdated component findings with CVE mapping.",
"Shadow-IT candidates (unrecognized CMS instances).",
],
pitfalls=[
"Version guessing from a single header — corroborate with at least two signals.",
"Missing single-page apps where the stack hides in JS bundles — inspect the bundles.",
"Forgetting mobile API backends that share the same domain — test the API surface too.",
],
references=[
"MITRE ATT&CK: Gather Victim Network Information (T1590).",
"OWASP: fingerprinting web application frameworks.",
],
blue_note="their web-asset inventory and patch program should already reflect these versions — EOL components found here are patch-management gaps.",
),
]
