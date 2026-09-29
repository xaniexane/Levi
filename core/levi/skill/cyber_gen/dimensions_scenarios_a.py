"""Batch-3 dimension data: threat scenarios 1-25.

Original defensive blue-team content authored for LEVI. Zero contact with
any external skill repository.
"""

SCENARIOS_A = [
    {
        "slug": "credential-stuffing",
        "title": "Credential Stuffing",
        "threat": (
            "Attackers replay username/password pairs stolen from third-party "
            "breaches against your login endpoints, betting on password reuse. "
            "It shows up as high-volume failed logons from distributed IPs, "
            "occasionally followed by a small number of successful takeovers."
        ),
        "signals": [
            "Authentication logs show a spike in failed logons (often 100s per "
            "minute) from many source IPs against a single login endpoint, "
            "with a low success rate and common password patterns.",
            "Successful logons immediately followed by password or MFA changes, "
            "mailbox rule creation, or impossible-travel alerts for the same "
            "account within minutes.",
            "WAF/bot-management flags distributed requests with identical "
            "user-agent strings, headless-browser markers, or known "
            "credential-stuffing tool signatures.",
        ],
        "analysis": [
            "Separate spray from stuffing: stuffing reuses many passwords per "
            "username from breach corpora; confirm by checking whether the "
            "attempted passwords appear in public breach datasets.",
            "For each successful post-stuffing logon, inventory session "
            "actions: read mail rules, forwarding addresses, OAuth grants, and "
            "API keys created in the 24 hours after compromise.",
        ],
        "harden": [
            "Enforce MFA everywhere and block legacy/basic authentication; "
            "stuffing dies against phishing-resistant MFA.",
            "Deploy breached-password screening at password set/change time "
            "and rate-limit plus device-fingerprint login endpoints.",
        ],
        "pitfalls": [
            "Blocking single IPs is whack-a-mole against botnets; block on "
            "behavior (velocity, fingerprint) rather than address.",
            "Forcing a fleet-wide password reset without confirming which "
            "accounts were actually taken over burns goodwill and teaches "
            "users to pick weaker passwords.",
        ],
        "mitre": "T1110.004 (Credential Access: Brute Force: Credential Stuffing)",
        "risk": "low",
        "tags": ["identity", "authentication"],
    },
    {
        "slug": "password-spraying",
        "title": "Password Spraying",
        "threat": (
            "Attackers try a small set of common passwords against many "
            "usernames, staying under per-account lockout thresholds. It is "
            "quieter than stuffing and specifically tuned to evade lockout "
            "policies, often running for days or weeks."
        ),
        "signals": [
            "A handful of failed logons per account (1-3) spread across "
            "hundreds of accounts from one or a few IPs, repeating on a "
            "schedule — the classic low-and-slow pattern.",
            "The same few passwords attempted everywhere (SeasonYear!, "
            "Company123, Password1); check by aggregating failed-logon "
            "password hashes where your IdP logs them.",
            "Spray bursts correlated with newly published password lists or "
            "timed to holidays/weekends when response is slower.",
        ],
        "analysis": [
            "Reconstruct the spray window: first-seen to last-seen per source "
            "IP, and list every account with even one success inside the "
            "window — those are confirmed or suspected takeovers.",
            "Check whether sprayed accounts share traits (same OU, same "
            "onboarding batch, service accounts) to find how the username "
            "list was built.",
        ],
        "harden": [
            "Smart lockout (soft lockout with increasing delays) plus "
            "alerting on distributed low-volume failures, not just lockouts.",
            "Rename or disable default/guessable service accounts and require "
            "MFA or certificate auth for all interactive logons.",
        ],
        "pitfalls": [
            "Per-account lockout thresholds alone will not catch spraying; "
            "you need cross-account velocity detection.",
            "Treating one success as an isolated incident misses the "
            "campaign — always scope the full spray window.",
        ],
        "mitre": "T1110.003 (Credential Access: Brute Force: Password Spraying)",
        "risk": "low",
        "tags": ["identity", "authentication"],
    },
    {
        "slug": "phishing-credential-harvest",
        "title": "Phishing Credential Harvest",
        "threat": (
            "Users are lured to lookalike login pages (often via adversary-in-"
            "the-middle kits that relay MFA) and submit credentials. The "
            "defender's job: find who clicked, who submitted, and whether "
            "sessions were hijacked even where MFA appeared to hold."
        ),
        "signals": [
            "Email gateway logs show a burst of messages with lookalike "
            "domains, newly registered domains, or QR-code lures pointing at "
            "a credential-harvest kit URL.",
            "Proxy/DNS logs show visits to the kit domain followed within "
            "minutes by logons from unusual IPs or impossible-travel pairs "
            "for the same user.",
            "AiTM kits leave telltales: logon session created without a "
            "matching MFA challenge event, or token replay from datacenter "
            "IP ranges.",
        ],
        "analysis": [
            "Pull the kit URL from the email, fetch it in a sandbox, and "
            "extract the credential-post endpoint and any session-cookie "
            "exfiltration to scope which submissions completed.",
            "For each submitter, check for concurrent sessions: revoke all "
            "refresh tokens and list OAuth app consents granted in the "
            "phish window.",
        ],
        "harden": [
            "Move to phishing-resistant MFA (FIDO2/WebAuthn); TOTP and push "
            "MFA fall to AiTM relay.",
            "Publish the kit's domains/URLs to DNS and email blocklists and "
            "run a targeted re-phish drill on the affected department.",
        ],
        "pitfalls": [
            "Resetting the password without revoking sessions leaves the "
            "attacker logged in via stolen tokens.",
            "Blaming the clicker instead of fixing the control gap guarantees "
            "a repeat with a better lure.",
        ],
        "mitre": "T1566.002 (Initial Access: Phishing: Spearphishing Link)",
        "risk": "low",
        "tags": ["email", "phishing"],
    },
    {
        "slug": "business-email-compromise",
        "title": "Business Email Compromise",
        "threat": (
            "Attackers operate inside a compromised mailbox (or a lookalike "
            "domain) to redirect payments, harvest invoices, or pivot to "
            "executives. Dwell time is often weeks; the fraud, not the "
            "malware, is the payload."
        ),
        "signals": [
            "Mailbox audit logs show inbox rules created to move or delete "
            "messages containing 'invoice', 'payment', 'wire', or executive "
            "names — the classic BEC rule footprint.",
            "Outbound messages to finance vendors from a slightly altered "
            "domain, or a legitimate mailbox suddenly sending payment-change "
            "requests with urgent tone.",
            "Logons to the mailbox from foreign IPs or anonymizing VPNs "
            "followed by long read-only sessions (the attacker learning the "
            "payment workflow before striking).",
        ],
        "analysis": [
            "Export all inbox/transport rules for the affected mailbox and "
            "diff against a known-good baseline; BEC rules often hide with "
            "names like ';' or whitespace.",
            "Trace every payment instruction the mailbox sent in the dwell "
            "window: which were acted on, which bank details changed, and "
            "whether funds are recallable.",
        ],
        "harden": [
            "Require out-of-band (voice/video) verification for any payment "
            "detail change, no exceptions, and alert on new inbox rules "
            "fleet-wide.",
            "Enable mailbox audit logging with 1-year retention and block "
            "automatic forwarding to external addresses tenant-wide.",
        ],
        "pitfalls": [
            "Focusing only on the compromised mailbox while the attacker "
            "already harvested the vendor's thread and will re-target from "
            "another account.",
            "Treating a lookalike-domain BEC as an IT problem alone — finance "
            "process change is the actual fix.",
        ],
        "mitre": "T1566 (Initial Access: Phishing) leading to collection/fraud",
        "risk": "low",
        "tags": ["email", "fraud"],
    },
    {
        "slug": "ransomware-encryption",
        "title": "Ransomware Encryption",
        "threat": (
            "Ransomware encrypts files and demands payment, usually after days "
            "of dwell time spent disabling recovery. Speed of isolation "
            "decides whether you lose one host or the fleet. Never pay without "
            "a deliberate, documented decision process."
        ),
        "signals": [
            "EDR fires on mass file rename/extension changes, vssadmin "
            "delete shadows, bcdedit recovery disabling, or known ransomware "
            "process names within seconds of each other.",
            "Ransom notes (README, DECRYPT files) appearing in multiple "
            "directories, wallpaper changes, or a sudden burst of encrypted "
            "file extensions across shares.",
            "Precursor activity in the prior 72 hours: disabled EDR tamper "
            "protection, cleared event logs, or backup job failures and "
            "backup-server logons from unusual accounts.",
        ],
        "analysis": [
            "Identify the variant from the note text, extension, and ransom "
            "portal; check public decryptor availability before any recovery "
            "decision — some variants have free decryptors.",
            "Reconstruct the entry vector (phishing, exposed RDP/VPN, software "
            "vulnerability) and the dwell timeline: first access, privilege "
            "escalation, backup targeting, detonation.",
        ],
        "harden": [
            "Immutable, offline-tested backups with alerting on backup "
            "tampering; network segmentation so one host cannot reach all "
            "shares.",
            "EDR tamper protection locked, application allowlisting on "
            "servers, and RDP/VPN behind MFA with geo restrictions.",
        ],
        "pitfalls": [
            "Rebuilding from backups that the attacker already found and "
            "poisoned — verify backup integrity and isolation first.",
            "Paying the ransom without confirming the decryptor works and "
            "without legal/regulatory review of sanctions exposure.",
        ],
        "mitre": "T1486 (Impact: Data Encrypted for Impact)",
        "risk": "moderate",
        "tags": ["malware", "ransomware"],
    },
    {
        "slug": "double-extortion-ransomware",
        "title": "Double-Extortion Ransomware",
        "threat": (
            "Data is exfiltrated BEFORE encryption, so the attacker can leak it "
            "even if you restore from backups. The investigation must answer "
            "what was stolen, not just what was encrypted — breach "
            "notification clocks start on exfiltration."
        ),
        "signals": [
            "Large outbound transfers (tens of GB) to cloud storage, file "
            "shares, or anonymized endpoints in the days before encryption, "
            "often via rclone, MEGAsync, or custom tooling.",
            "Staging directories with archived/renamed sensitive data "
            "(databases, file shares zipped) and data-leak-site monitoring "
            "hits for your organization name.",
            "The ransom note references specific stolen files or threatens "
            "publication with a countdown timer.",
        ],
        "analysis": [
            "Quantify the exfil: source directories, file types, record "
            "counts, and whether regulated data (PII, PHI, card data) was "
            "included — this drives notification obligations.",
            "Preserve exfiltration logs (proxy, firewall, DLP, cloud audit) "
            "as evidence; they are also the proof of what did and did not "
            "leave.",
        ],
        "harden": [
            "DLP egress policies on sensitive data stores plus alerting on "
            "bulk archive creation and large outbound transfers.",
            "Same ransomware baseline as single-extortion, plus a practiced "
            "breach-notification runbook with legal counsel on speed dial.",
        ],
        "pitfalls": [
            "Declaring victory after restoring from backup while stolen data "
            "sits on a leak site — the extortion continues.",
            "Starting the notification clock at encryption time instead of at "
            "first confirmed exfiltration.",
        ],
        "mitre": "T1486 + T1048 (Exfiltration Over Alternative Protocol)",
        "risk": "moderate",
        "tags": ["malware", "ransomware", "exfiltration"],
    },
    {
        "slug": "wiper-malware",
        "title": "Wiper Malware",
        "threat": (
            "Wipers destroy data and systems without a ransom option — "
            "recovery depends entirely on backups the attacker could not "
            "reach. Some wipers masquerade as ransomware; treat any "
            "'ransomware' that fails to provide working decryption as a "
            "suspected wiper."
        ),
        "signals": [
            "Mass file overwrite with garbage or zeroed content, MBR/partition "
            "table destruction, or firmware-level bricking without any "
            "credible ransom note or working decryptor.",
            "Drivers loaded for raw disk access (e.g., legitimate disk tools "
            "abused) immediately before the destruction phase.",
            "Prior targeting of backup infrastructure and domain controllers "
            "suggests intent to prevent any recovery.",
        ],
        "analysis": [
            "Determine wiper vs ransomware: attempt decryption with the "
            "provided key in an isolated lab; failure plus destructive "
            "overwrite patterns indicates wiper intent.",
            "Map the blast radius by host role: which systems can be rebuilt "
            "from gold images versus which held unique data now lost.",
        ],
        "harden": [
            "Offline, immutable backups stored out of reach of domain "
            "credentials, with tested bare-metal restore procedures.",
            "Boot integrity (Secure Boot, measured boot) and driver "
            "allowlisting to block raw-disk access tooling.",
        ],
        "pitfalls": [
            "Assuming negotiation is possible — wipers have no decryptor, "
            "and every hour spent 'negotiating' is an hour not rebuilding.",
            "Restoring from the same compromised backup infrastructure the "
            "wiper already touched.",
        ],
        "mitre": "T1485 (Impact: Data Destruction)",
        "risk": "moderate",
        "tags": ["malware", "destruction"],
    },
    {
        "slug": "cryptominer-intrusion",
        "title": "Cryptominer Intrusion",
        "threat": (
            "Unauthorized miners burn CPU/GPU and cloud spend, and — more "
            "importantly — prove an attacker has code execution on your "
            "assets. Treat every miner as a foothold to investigate, not just "
            "a performance problem."
        ),
        "signals": [
            "Sustained high CPU/GPU on hosts or cloud instances with no "
            "business workload, especially at night/weekends, plus connections "
            "to known mining pools on Stratum ports.",
            "Cloud billing spikes for compute in regions you do not use, or "
            "new instances launched by unfamiliar principals.",
            "EDR detections for xmrig or similar binaries, scheduled tasks "
            "re-fetching miner payloads, or WMI persistence entries.",
        ],
        "analysis": [
            "Trace the miner's persistence and delivery: the initial access "
            "vector (exposed service, weak SSH, vulnerable app) matters more "
            "than the miner itself.",
            "Check for dual-use: many miner campaigns also exfiltrate "
            "credentials or deploy additional payloads — sweep for those.",
        ],
        "harden": [
            "Close the entry vector (patch the exploited service, enforce "
            "key-based SSH, remove internet exposure), then block mining pool "
            "domains at DNS.",
            "Cloud: budget alerts, SCPs denying expensive instance types and "
            "unused regions, and alerting on new access keys.",
        ],
        "pitfalls": [
            "Killing the miner without removing persistence — it returns on "
            "reboot or on schedule.",
            "Writing it off as 'just a miner' without investigating the "
            "initial access that delivered it.",
        ],
        "mitre": "T1496 (Impact: Resource Hijacking)",
        "risk": "low",
        "tags": ["malware", "cloud"],
    },
    {
        "slug": "dns-tunneling",
        "title": "DNS Tunneling",
        "threat": (
            "DNS tunneling smuggles data or C2 inside DNS queries, abusing a "
            "protocol almost every network allows outbound. Detection hinges "
            "on query shape (length, entropy, volume, record types), not on "
            "blocklists."
        ),
        "signals": [
            "Long, high-entropy subdomains (often 50+ chars) in DNS logs, "
            "unusual record types (TXT, NULL) at volume, or a single host "
            "generating thousands of queries to one domain.",
            "Beacon-like regularity in query timing to an obscure domain, or "
            "DNS queries for domains registered within the last 30 days.",
            "Responses with abnormally large TXT records relative to the "
            "query — data coming back down the tunnel.",
        ],
        "analysis": [
            "Decode a sample of tunneled queries/responses in a sandbox to "
            "determine direction and content: C2 instructions, exfiltrated "
            "data, or both.",
            "Identify patient zero by earliest query timestamp, then hunt "
            "laterally: tunneling tools are often deployed to multiple hosts.",
        ],
        "harden": [
            "Force all DNS through logged, filtered resolvers; block direct "
            "port-53 egress from endpoints and alert on non-standard DNS "
            "ports.",
            "Deploy DNS-layer security with tunneling heuristics and sinkhole "
            "confirmed tunnel domains.",
        ],
        "pitfalls": [
            "Blocking the domain without finding the implant — the attacker "
            "rotates domains faster than you blocklist.",
            "Ignoring DNS over HTTPS (DoH): tunneled traffic inside DoH is "
            "invisible to passive DNS monitoring — log at the endpoint.",
        ],
        "mitre": "T1071.004 (Command and Control: DNS)",
        "risk": "low",
        "tags": ["network", "dns", "c2"],
    },
    {
        "slug": "dns-fast-flux",
        "title": "DNS Fast-Flux",
        "threat": (
            "Fast-flux networks rotate DNS answers across many compromised "
            "hosts every few minutes, making malicious infrastructure hard to "
            "takedown. Defenders detect the flux pattern itself: low TTLs, "
            "high answer churn, and geographically scattered A records."
        ),
        "signals": [
            "DNS answers with TTLs under 300 seconds rotating across dozens "
            "of IPs in unrelated ASNs and countries for a single domain.",
            "Short-lived domains (registered days ago) resolving to "
            "residential or compromised-server IPs with no legitimate "
            "business relationship.",
            "Endpoint connections to flux domains correlating with malware "
            "detonations or phishing kit infrastructure.",
        ],
        "analysis": [
            "Profile the flux: record TTL, unique IPs per hour, ASN/country "
            "spread, and name-server patterns to fingerprint the specific "
            "flux service or kit.",
            "Pivot from the domain to find sibling infrastructure: shared "
            "name servers, registration patterns, and certificate overlaps.",
        ],
        "harden": [
            "DNS response policy zones (RPZ) blocking confirmed flux domains, "
            "plus alerting on sub-300s TTL answers at the resolver.",
            "Feed flux indicators into the proxy and firewall for automatic "
            "blocking of newly observed flux nodes.",
        ],
        "pitfalls": [
            "Blocking individual flux IPs — they churn in minutes; block the "
            "domain pattern and the detection logic instead.",
            "Confusing legitimate CDN behavior (low TTL, many IPs) with flux; "
            "require the ASN-scatter plus short-domain-age combination.",
        ],
        "mitre": "T1568.002 (Command and Control: Domain Generation Algorithms)",
        "risk": "low",
        "tags": ["network", "dns", "c2"],
    },
    {
        "slug": "c2-beaconing",
        "title": "C2 Beaconing",
        "threat": (
            "Compromised hosts check in with attacker infrastructure on a "
            "schedule — the heartbeat of an intrusion. Beaconing detection is "
            "statistical: regularity, jitter analysis, and connection "
            "uniformity reveal what signatures miss."
        ),
        "signals": [
            "Outbound connections at fixed intervals (e.g., every 60s) with "
            "consistent byte counts to an external host — visible in NetFlow "
            "or proxy logs as metronomic traffic.",
            "Long-lived sessions to IPs with no domain, newly registered "
            "domains, or domains with no legitimate business purpose.",
            "Jittered but statistically regular timing: inter-arrival times "
            "clustering around a mean with small variance.",
        ],
        "analysis": [
            "Compute inter-arrival statistics on the suspect flows; true "
            "beacons show low variance even with jitter, unlike human "
            "browsing.",
            "Capture the beacon payload in a sandbox detonation to identify "
            "the implant family and its tasking protocol.",
        ],
        "harden": [
            "Egress filtering: default-deny outbound with allowlisted "
            "destinations for servers; alert on direct-to-IP connections.",
            "TLS inspection (where lawful and disclosed) or JA3/JA4 "
            "fingerprinting to catch beaconing inside encrypted channels.",
        ],
        "pitfalls": [
            "Chasing the C2 IP instead of the implant — infrastructure is "
            "disposable, the foothold is what matters.",
            "Assuming encrypted traffic cannot be analyzed: timing, size, "
            "and destination metadata still betray beacons.",
        ],
        "mitre": "T1071.001 (Command and Control: Web Protocols)",
        "risk": "low",
        "tags": ["network", "c2"],
    },
    {
        "slug": "data-exfiltration",
        "title": "Data Exfiltration",
        "threat": (
            "Sensitive data leaving the network — the moment an intrusion "
            "becomes a breach. Quantifying WHAT left is more important than "
            "blocking the channel after the fact; notification obligations "
            "depend on the data, not the technique."
        ),
        "signals": [
            "Egress spikes: large uploads to external hosts, cloud storage, "
            "or paste sites from servers that normally receive more than "
            "they send.",
            "Staging activity: large archives (zip/7z/rar) created in temp "
            "directories, database dumps, or mailbox exports shortly before "
            "the transfer.",
            "DLP alerts on regulated data patterns (SSN, card numbers, PHI "
            "formats) in outbound traffic, or DNS/ICMP exfil at low volume.",
        ],
        "analysis": [
            "Reconstruct the exfil set: source paths, file types, record "
            "counts, and data classification — involve legal early for "
            "notification scoping.",
            "Preserve full packet/proxy logs of the transfer; they prove "
            "what left and are evidence for regulators and law enforcement.",
        ],
        "harden": [
            "DLP policies with blocking on bulk sensitive-data egress, plus "
            "alerting on archive creation and database dump commands.",
            "Segment sensitive data stores so a single compromised host "
            "cannot reach the crown jewels.",
        ],
        "pitfalls": [
            "Stopping the transfer but never determining what was in it — "
            "you cannot scope a breach on 'we blocked something'.",
            "Forgetting cloud audit logs: exfil via sanctioned SaaS "
            "(personal Drive, Dropbox) bypasses network DLP.",
        ],
        "mitre": "T1048 (Exfiltration Over Alternative Protocol)",
        "risk": "moderate",
        "tags": ["exfiltration", "dlp"],
    },
    {
        "slug": "insider-data-theft",
        "title": "Insider Data Theft",
        "threat": (
            "A trusted user steals data — often before resignation. Unlike "
            "external attacks there is no malware to find; detection relies "
            "on behavioral baselines: access volume, off-hours activity, and "
            "personal-storage uploads. Handle with HR and legal from the start."
        ),
        "signals": [
            "A user accessing far more files or records than their role "
            "baseline, especially in the 30 days before resignation or "
            "termination.",
            "Bulk downloads to USB, personal cloud uploads, or emailing "
            "attachments to personal addresses from a corporate account.",
            "Off-hours access to repositories the user never touched before, "
            "or permission changes granting themselves broader access.",
        ],
        "analysis": [
            "Build a 90-day access timeline for the user: volume, data "
            "sensitivity, destination (USB serial, cloud account, personal "
            "email) — coordinate collection with HR/legal to stay compliant.",
            "Determine business justification for each anomaly with the "
            "user's manager before concluding malice; over-collection without "
            "cause creates liability.",
        ],
        "harden": [
            "UEBA baselines with alerting on pre-resignation access spikes; "
            "disable USB mass storage or enforce encryption + logging.",
            "Immediate deprovisioning workflow: access revoked at the moment "
            "of termination notice, not end of day.",
        ],
        "pitfalls": [
            "Investigating without HR/legal involvement — privacy and "
            "employment law exposure is real.",
            "Confronting the user before evidence is preserved; they will "
            "delete local copies first.",
        ],
        "mitre": "T1005 (Collection: Data from Local System) — insider context",
        "risk": "low",
        "tags": ["insider", "dlp"],
    },
    {
        "slug": "privilege-escalation-sudo",
        "title": "Linux Privilege Escalation",
        "threat": (
            "Attackers turn a low-privilege Linux foothold into root via sudo "
            "misconfigurations, SUID binaries, kernel exploits, or writable "
            "service files. Harden the escalation paths and you contain most "
            "Linux intrusions at the beachhead."
        ),
        "signals": [
            "Sudo invocations of unusual binaries, sudoers file reads by "
            "non-admins, or successful sudo from accounts that never used it "
            "before.",
            "Execution of known privesc enumeration scripts (LinPEAS-style), "
            "SUID binary abuse, or kernel exploit artifacts in logs.",
            "New entries in sudoers.d, unexpected SUID bits, or service "
            "files modified by non-root users.",
        ],
        "analysis": [
            "Identify the exact escalation primitive: which misconfiguration "
            "or vulnerability was used, and whether it is systemic across the "
            "fleet or host-specific.",
            "Check for persistence installed with the new privileges: new "
            "SSH keys in root's authorized_keys, cron jobs, or systemd units.",
        ],
        "harden": [
            "Least-privilege sudoers (no NOPASSWD, no wildcards), remove SUID "
            "from unnecessary binaries, and keep kernels patched.",
            "Centralized sudo logging (sudoreplay) with alerting on first-"
            "time sudo use per account.",
        ],
        "pitfalls": [
            "Cleaning the host without fixing the fleet-wide sudoers "
            "misconfiguration that enabled it.",
            "Assuming container escape is out of scope — check whether the "
            "foothold was a container with host mounts.",
        ],
        "mitre": "T1548.003 (Privilege Escalation: Sudo and Sudo Caching)",
        "risk": "low",
        "tags": ["linux", "privilege-escalation"],
    },
    {
        "slug": "privilege-escalation-windows",
        "title": "Windows Privilege Escalation",
        "threat": (
            "From standard user to SYSTEM/Administrator via unquoted service "
            "paths, writable service binaries, AlwaysInstallElevated, token "
            "manipulation, or kernel exploits. Windows privesc is usually a "
            "misconfiguration the attacker read, not a zero-day they brought."
        ),
        "signals": [
            "Service creation or modification events (7045/4697) pointing at "
            "user-writable paths, or processes spawning as SYSTEM from "
            "unexpected parents.",
            "Registry writes to AlwaysInstallElevated keys, accessibility "
            "binary replacement (sethc/utilman), or token duplication API "
            "patterns in EDR telemetry.",
            "Enumeration tooling: whoami /priv, accesschk, or PowerShell "
            "privesc scripts running before the escalation.",
        ],
        "analysis": [
            "Pin down the primitive: unquoted path, weak service ACL, "
            "scheduled task with stored creds, or kernel CVE — then check "
            "how many fleet hosts share it.",
            "Review what the elevated access touched: SAM/LSASS access "
            "after escalation means credential theft followed.",
        ],
        "harden": [
            "Fix service ACLs and paths fleet-wide, disable "
            "AlwaysInstallElevated, and enforce signed-driver and LSA "
            "protection policies.",
            "Patch cadence for privilege-escalation CVEs treated as critical, "
            "not 'local only'.",
        ],
        "pitfalls": [
            "Reimaging one host while the GPO-deployed misconfiguration "
            "recreates the hole on every rebuild.",
            "Missing that the attacker already dumped credentials post-"
            "escalation — scope the follow-on theft, not just the privesc.",
        ],
        "mitre": "T1068 (Privilege Escalation: Exploitation for Privilege Escalation)",
        "risk": "low",
        "tags": ["windows", "privilege-escalation"],
    },
    {
        "slug": "lateral-movement-smb",
        "title": "SMB Lateral Movement",
        "threat": (
            "Attackers move host-to-host over SMB using stolen credentials — "
            "PsExec-style service creation, admin shares, or WMI. In a flat "
            "network, one compromised workstation becomes the whole domain "
            "in hours."
        ),
        "signals": [
            "SMB sessions from a workstation to many other hosts in a short "
            "window, especially to ADMIN$ or C$ shares the user never "
            "touches normally.",
            "Service creation events (7045) with service binaries in "
            "ADMIN$\\system32, or 4624 type-3 logons with the same account "
            "across dozens of hosts.",
            "EDR process trees showing services.exe spawning cmd/powershell "
            "shortly after a remote SMB session.",
        ],
        "analysis": [
            "Map the movement graph: source host, credential used, target "
            "hosts, timestamps — this is the incident's skeleton.",
            "Determine which credential enabled it (stolen hash, ticket, or "
            "plaintext) to know what must be rotated enterprise-wide.",
        ],
        "harden": [
            "Segment the network (workstation-to-workstation SMB blocked), "
            "deploy LAPS for unique local admin passwords, and restrict "
            "lateral logon rights via tiered admin model.",
            "Disable SMBv1 everywhere; require SMB signing.",
        ],
        "pitfalls": [
            "Cleaning patient zero while the attacker's beachheads on hosts "
            "3, 7, and 12 remain active.",
            "Rotating the compromised account's password but not the "
            "kerberos tickets/hashes already stolen from it.",
        ],
        "mitre": "T1021.002 (Lateral Movement: SMB/Windows Admin Shares)",
        "risk": "low",
        "tags": ["windows", "lateral-movement"],
    },
    {
        "slug": "lateral-movement-rdp",
        "title": "RDP Lateral Movement",
        "threat": (
            "RDP is both an admin tool and the attacker's favorite lateral "
            "highway. Compromised credentials plus unrestricted RDP equals "
            "domain-wide movement that looks almost legitimate in the logs."
        ),
        "signals": [
            "4624 type-10 (RDP) logons from a workstation to servers or other "
            "workstations outside the user's normal admin pattern.",
            "RDP sessions at unusual hours, from hosts the account never "
            "logged into before, or with clipboard/drive redirection moving "
            "tools onto the target.",
            "TerminalServices-LocalSessionManager events (21/25) on targets "
            "without a matching helpdesk ticket or change record.",
        ],
        "analysis": [
            "Correlate RDP logons with the source host's compromise timeline "
            "to distinguish attacker sessions from legitimate admin work.",
            "Check for credential harvesting on each RDP target: LSASS "
            "access or SAM reads following the session indicate theft.",
        ],
        "harden": [
            "RDP restricted to jump hosts/bastions with MFA; Network Level "
            "Authentication enforced; no direct workstation-to-server RDP.",
            "Dedicated admin accounts (no daily-use accounts with admin "
            "rights) and RDP session recording on jump hosts.",
        ],
        "pitfalls": [
            "Allowing 'temporary' RDP exceptions that become permanent "
            "lateral paths.",
            "Missing RDP-based movement because you only hunted SMB — "
            "attackers use whatever is open.",
        ],
        "mitre": "T1021.001 (Lateral Movement: Remote Desktop Protocol)",
        "risk": "low",
        "tags": ["windows", "lateral-movement"],
    },
    {
        "slug": "lateral-movement-winrm",
        "title": "WinRM Lateral Movement",
        "threat": (
            "Windows Remote Management gives attackers remote PowerShell on "
            "any host where WinRM is enabled — quieter than PsExec, built "
            "into the OS, and often left on by default in enterprises."
        ),
        "signals": [
            "WinRM operational log (Microsoft-Windows-WinRM/Operational) "
            "showing connections from non-admin workstations, or wsmprovhost "
            "spawning powershell with encoded commands.",
            "Event 4624 type-3 logons to the WinRM port (5985/5986) from "
            "hosts outside the management subnet.",
            "PowerShell remoting sessions (event 400/800) executing "
            "reconnaissance or credential-access commands.",
        ],
        "analysis": [
            "Extract the remote commands from PowerShell operational logs "
            "(4104) on the target to see exactly what the attacker ran.",
            "Inventory which hosts have WinRM enabled and reachable — the "
            "attack surface is every one of them.",
        ],
        "harden": [
            "Restrict WinRM to management hosts via host firewall and GPO; "
            "disable where not needed.",
            "Require JEA (Just Enough Administration) constrained endpoints "
            "so even allowed remoting cannot run arbitrary commands.",
        ],
        "pitfalls": [
            "Forgetting WinRM over HTTPS (5986) when firewalling only 5985.",
            "PowerShell logging gaps: without module/script-block logging, "
            "remote commands are invisible — enable both.",
        ],
        "mitre": "T1021.006 (Lateral Movement: Windows Remote Management)",
        "risk": "low",
        "tags": ["windows", "lateral-movement"],
    },
    {
        "slug": "kerberoasting",
        "title": "Kerberoasting",
        "threat": (
            "Attackers request service tickets for SPN accounts and crack "
            "them offline to recover service-account passwords — no alerts "
            "on the DC, because requesting tickets is normal. The defense is "
            "making those passwords uncrackable and the requests visible."
        ),
        "signals": [
            "A single account requesting an unusual number of service tickets "
            "(4769) with RC4 encryption for many different SPNs in a short "
            "window.",
            "Ticket requests for SPNs from accounts with no business need, "
            "or requests at odd hours from a workstation (not a server).",
            "Subsequent use of a cracked service account: logons from "
            "unexpected hosts or privilege changes for that account.",
        ],
        "analysis": [
            "List every SPN targeted and assess the crackability of each "
            "service account's password (length, complexity, age).",
            "If a service account was cracked, treat it as full compromise: "
            "inventory everything that account could touch.",
        ],
        "harden": [
            "Service accounts: 25+ character random passwords, or better, "
            "group Managed Service Accounts (gMSA) with automatic rotation.",
            "Alert on RC4 ticket requests and on any account requesting "
            "tickets for more than N distinct SPNs per hour.",
        ],
        "pitfalls": [
            "Rotating the password but leaving the SPN on a weak account — "
            "the attacker just roasts it again.",
            "Missing that the cracked service account may have been used to "
            "request MORE tickets (roast chaining).",
        ],
        "mitre": "T1558.003 (Credential Access: Kerberoasting)",
        "risk": "moderate",
        "tags": ["identity", "active-directory"],
    },
    {
        "slug": "asreproasting",
        "title": "ASREPRoasting",
        "threat": (
            "Accounts with Kerberos pre-authentication disabled can have "
            "their AS-REP responses requested by anyone and cracked offline — "
            "no authentication needed at all. One misconfigured user account "
            "is enough."
        ),
        "signals": [
            "4768 (TGT request) events where pre-authentication was not used, "
            "from external or unexpected hosts, for accounts flagged "
            "DONT_REQ_PREAUTH.",
            "Enumeration of such accounts (LDAP queries for "
            "userAccountControl flags) preceding the roast requests.",
            "Later logons with the cracked credentials from attacker hosts.",
        ],
        "analysis": [
            "Enumerate all accounts with pre-auth disabled (the full roast-"
            "able population) — the fix is one checkbox per account, so find "
            "them all.",
            "Check whether any of those accounts are privileged or service "
            "accounts; prioritize accordingly.",
        ],
        "harden": [
            "Enable Kerberos pre-authentication on every account; audit for "
            "the flag regularly — it gets re-disabled by legacy app "
            "troubleshooting.",
            "Alert on 4768 without pre-auth from any source.",
        ],
        "pitfalls": [
            "Fixing the roasted account but not scanning for the other 40 "
            "accounts with the same misconfiguration.",
            "Assuming pre-auth-disabled accounts are always legacy — verify "
            "before re-enabling to avoid breaking production auth.",
        ],
        "mitre": "T1558.004 (Credential Access: AS-REP Roasting)",
        "risk": "low",
        "tags": ["identity", "active-directory"],
    },
    {
        "slug": "dcsync-attack",
        "title": "DCSync Attack",
        "threat": (
            "With replication rights, an attacker impersonates a domain "
            "controller and pulls password hashes for ANY account — including "
            "krbtgt — via normal replication traffic. It looks like DC-to-DC "
            "chatter, which is why it evades naive monitoring."
        ),
        "signals": [
            "4662 (directory object access) on the domain root or krbtgt "
            "account by a principal that is not a real domain controller.",
            "Replication traffic (DRS) originating from a non-DC host, or a "
            "DC requesting replication far outside the normal schedule.",
            "Newly granted DS-Replication-Get-Changes rights (especially "
            "Get-Changes-All) to users, groups, or computers.",
        ],
        "analysis": [
            "Identify which account performed the sync and which hashes were "
            "pulled — a krbtgt pull means the entire domain's Kerberos trust "
            "must be reset (double krbtgt rotation).",
            "Review how the attacker gained replication rights: compromised "
            "admin, delegated rights sprawl, or ACL abuse.",
        ],
        "harden": [
            "Audit and strip replication rights to the minimum; alert on any "
            "grant of Get-Changes-All.",
            "Monitor 4662 on sensitive objects and baseline legitimate "
            "replication sources.",
        ],
        "pitfalls": [
            "Resetting user passwords but not the krbtgt — golden tickets "
            "forged from a stolen krbtgt survive password resets.",
            "Missing that DCSync needs only replication rights, not Domain "
            "Admin — delegated-rights sprawl is the usual enabler.",
        ],
        "mitre": "T1003.006 (Credential Access: DCSync)",
        "risk": "moderate",
        "tags": ["identity", "active-directory"],
    },
    {
        "slug": "golden-ticket",
        "title": "Golden Ticket Attack",
        "threat": (
            "Forged Kerberos TGTs using the stolen krbtgt hash grant "
            "unrestricted, long-lived domain access that survives password "
            "resets. Detection relies on ticket anomalies: impossible "
            "lifetimes, wrong encryption, or logons that bypass the DC."
        ),
        "signals": [
            "TGTs with lifetimes far exceeding domain policy (e.g., 10 "
            "years), RC4-encrypted tickets in an AES-enforced domain, or "
            "tickets for accounts that never authenticated (no 4768).",
            "4769 service-ticket requests referencing a TGT the DC never "
            "issued, or logons from hosts with no corresponding interactive "
            "session.",
            "The krbtgt account's own anomalous activity following a DCSync "
            "event.",
        ],
        "analysis": [
            "Confirm via ticket inspection (klist, network capture): "
            "lifetime, encryption type, and client name mismatches prove "
            "forgery.",
            "Scope everything done under forged tickets — assume full domain "
            "compromise until proven otherwise.",
        ],
        "harden": [
            "Rotate the krbtgt password TWICE (to invalidate both current "
            "and previous hash) after any suspected compromise.",
            "Enforce AES Kerberos encryption and alert on RC4 tickets and "
            "anomalous ticket lifetimes.",
        ],
        "pitfalls": [
            "Rotating krbtgt only once — the N-1 hash remains valid and the "
            "golden ticket still works.",
            "Treating it as an account incident instead of a domain-trust "
            "incident; the response scope is the whole forest.",
        ],
        "mitre": "T1558.001 (Credential Access: Golden Ticket)",
        "risk": "moderate",
        "tags": ["identity", "active-directory"],
    },
    {
        "slug": "pass-the-hash",
        "title": "Pass-the-Hash",
        "threat": (
            "Stolen NTLM hashes authenticate without the password ever being "
            "cracked. It is invisible to password monitoring because no "
            "password is used — defense means killing NTLM where possible "
            "and watching for its telltale logon patterns."
        ),
        "signals": [
            "4624 type-3/9 logons using NTLM where Kerberos is expected, "
            "especially from workstations to servers with admin accounts.",
            "Logon sessions with no interactive activity but successful "
            "authentication, or the same hash authenticating from multiple "
            "hosts simultaneously.",
            "NTLM audit logs showing authentication for accounts that should "
            "be Kerberos-only.",
        ],
        "analysis": [
            "Determine hash source: LSASS dump, SAM extraction, or DCSync — "
            "each implies a different prior compromise to remediate.",
            "List every host the hash authenticated to; each is a foothold "
            "until reimaged or verified clean.",
        ],
        "harden": [
            "Reduce NTLM usage (audit mode first, then restrict), deploy "
            "Credential Guard, and use unique local admin passwords (LAPS).",
            "Deny network logon for privileged accounts from workstations "
            "(tiered admin model).",
        ],
        "pitfalls": [
            "Resetting the password without considering that the attacker "
            "may have dumped the NEW hash too if still present.",
            "Disabling NTLM blindly and breaking legacy apps — audit first, "
            "restrict second.",
        ],
        "mitre": "T1550.002 (Lateral Movement: Pass the Hash)",
        "risk": "low",
        "tags": ["identity", "lateral-movement"],
    },
    {
        "slug": "token-impersonation",
        "title": "Token Impersonation",
        "threat": (
            "Attackers steal or duplicate Windows access tokens to act as "
            "another user — often SYSTEM — without knowing any password. EDR "
            "sees odd parent/child relationships and token-privilege "
            "enabling that legitimate software rarely performs."
        ),
        "signals": [
            "Processes enabling SeDebugPrivilege or SeImpersonatePrivilege "
            "outside of known admin tooling, or unexpected token duplication "
            "API sequences in EDR telemetry.",
            "A low-privilege process spawning children as SYSTEM or as "
            "another logged-on user without a legitimate service path.",
            "Named-pipe impersonation patterns (PrintSpooler-style) from "
            "non-printer processes.",
        ],
        "analysis": [
            "Trace the token source: which process's token was stolen, and "
            "did that source process itself get compromised first?",
            "Check what the impersonated context accessed — file, registry, "
            "and network actions taken as the victim identity.",
        ],
        "harden": [
            "Remove SeImpersonatePrivilege from service accounts that do not "
            "need it; patch print-spooler-class vulnerabilities promptly.",
            "Run services as low-privilege virtual accounts instead of "
            "SYSTEM or network service where possible.",
        ],
        "pitfalls": [
            "Assuming token theft requires admin — some impersonation "
            "primitives work from lower privilege.",
            "Missing that a stolen token can be replayed on OTHER hosts via "
            "remote authentication.",
        ],
        "mitre": "T1134 (Privilege Escalation: Access Token Manipulation)",
        "risk": "low",
        "tags": ["windows", "privilege-escalation"],
    },
]

SCENARIOS_B = [
    {
        "slug": "ad-acl-abuse",
        "title": "Active Directory ACL Abuse",
        "threat": (
            "Attackers abuse delegated Active Directory permissions — "
            "WriteDacl, GenericAll, ForceChangePassword — to escalate without "
            "exploits. These are legitimate rights granted too broadly, so "
            "detection means auditing WHO can do WHAT, continuously."
        ),
        "signals": [
            "4662 events showing writes to security descriptors (WriteDacl / "
            "WriteOwner) on privileged groups, OUs, or the AdminSDHolder "
            "container.",
            "Password resets (4724) performed by non-helpdesk accounts, or "
            "new ACEs granting GenericAll over high-value targets.",
            "BloodHound-style LDAP enumeration (large object reads) "
            "preceding the ACL change — the attacker mapping attack paths.",
        ],
        "analysis": [
            "Diff the object's ACL before and after: which principal gained "
            "which right, and was it granted through nested group "
            "membership?",
            "Map the attack path the new right enables (e.g., GenericAll on "
            "a group -> add self -> Domain Admin) to scope the blast radius.",
        ],
        "harden": [
            "Least-privilege delegation: no GenericAll/WriteDacl outside "
            "Domain Admins; regular ACL audits with alerting on changes to "
            "protected objects.",
            "Enable AdminSDHolder protection checks and monitor for SDPROP "
            "inconsistencies.",
        ],
        "pitfalls": [
            "One-time ACL cleanup without continuous monitoring — delegation "
            "sprawl regrows within months.",
            "Forgetting nested groups: the dangerous ACE is often three "
            "group-nestings away from the attacker.",
        ],
        "mitre": "T1098 (Persistence: Account Manipulation)",
        "risk": "low",
        "tags": ["identity", "active-directory"],
    },
    {
        "slug": "gpo-abuse",
        "title": "Group Policy Abuse",
        "threat": (
            "Group Policy deploys to every machine in scope — including "
            "attacker-planted scheduled tasks, scripts, and software. A "
            "malicious GPO is a domain-wide persistence and execution "
            "platform; monitor GPO changes like code deployments."
        ),
        "signals": [
            "5136/5137 directory-service changes creating or modifying GPOs, "
            "especially new immediate scheduled tasks, startup scripts, or "
            "software installation policies.",
            "SYSVOL replication of unexpected scripts/executables, or GPO "
            "version number jumps without a change ticket.",
            "Mass host behavior change correlating with GP refresh cycles "
            "(new persistence appearing fleet-wide simultaneously).",
        ],
        "analysis": [
            "Inspect the GPO's full settings and linked scripts; determine "
            "the deployment scope (which OUs) to size the affected fleet.",
            "Check GPO backup/version history to find when the malicious "
            "change was introduced and by whom.",
        ],
        "harden": [
            "Restrict GPO edit rights to a break-glass group, require change "
            "tickets, and alert on any GPO modification in real time.",
            "Regular GPO backup and diffing; treat SYSVOL as monitored "
            "code, not static config.",
        ],
        "pitfalls": [
            "Deleting the malicious GPO without removing the persistence it "
            "already deployed to thousands of hosts.",
            "Missing GPO-based deployment because you hunted only local "
            "persistence mechanisms.",
        ],
        "mitre": "T1484.001 (Persistence: Domain Policy Modification: Group Policy Modification)",
        "risk": "low",
        "tags": ["identity", "active-directory", "persistence"],
    },
    {
        "slug": "scheduled-task-persistence",
        "title": "Scheduled Task Persistence",
        "threat": (
            "Scheduled tasks are the most common Windows persistence: they "
            "survive reboots, run as SYSTEM, and hide among thousands of "
            "legitimate tasks. Hunt for tasks with odd actions, odd "
            "principals, or creation outside change windows."
        ),
        "signals": [
            "4698 (scheduled task created) with actions pointing at temp "
            "directories, encoded PowerShell, or LOLBins, especially running "
            "as SYSTEM.",
            "Tasks with misleading names mimicking legitimate ones "
            "(e.g., 'GoogleUpdateTaskMachineUA' in the wrong path), or tasks "
            "created outside maintenance windows.",
            "Task XML in C:\\Windows\\System32\\Tasks with recent "
            "timestamps but no corresponding change record.",
        ],
        "analysis": [
            "Export the task XML and inspect actions, triggers, principals, "
            "and conditions — the full task definition is the evidence.",
            "Determine creation vector: who/what created it (user, GPO, "
            "remote RPC) to find the still-active access path.",
        ],
        "harden": [
            "Alert on 4698/4702 fleet-wide; restrict task creation rights "
            "and audit tasks running as SYSTEM quarterly.",
            "Application allowlisting so the task's payload cannot execute "
            "even if the task persists.",
        ],
        "pitfalls": [
            "Deleting the task but leaving the payload binary — many "
            "implants re-create their task on next execution.",
            "Trusting the task name; always inspect the action path and "
            "hash.",
        ],
        "mitre": "T1053.005 (Persistence: Scheduled Task)",
        "risk": "low",
        "tags": ["windows", "persistence"],
    },
    {
        "slug": "registry-persistence",
        "title": "Registry Persistence",
        "threat": (
            "Run keys, services, Winlogon helpers, and COM hijacks give "
            "attackers reboot-surviving execution with minimal footprint. "
            "Baseline the autoruns on gold images; alert on deviations, not "
            "on the mechanism's existence."
        ),
        "signals": [
            "Writes to Run/RunOnce keys, Winlogon Userinit/Shell values, or "
            "service ImagePath entries pointing at unusual binaries.",
            "Sysmon event 13 (registry value set) on autorun locations by "
            "non-installer processes, or new services with suspicious "
            "binaries.",
            "Autoruns deltas: new entries appearing between baseline scans "
            "on hosts with no software-change record.",
        ],
        "analysis": [
            "Capture the referenced binary: hash, signature, and sandbox "
            "detonation to confirm malicious intent.",
            "Check the same autorun locations across the fleet — registry "
            "persistence is often deployed identically to many hosts.",
        ],
        "harden": [
            "Scheduled Autoruns/Sysmon baselining with alerting on new "
            "persistence entries; restrict registry write rights for "
            "standard users.",
            "Code-signing requirements for binaries launched from autorun "
            "locations.",
        ],
        "pitfalls": [
            "Cleaning the registry value while the dropper that restores it "
            "still runs on a schedule.",
            "Overlooking user-hive (HKCU) persistence during a 'system-only' "
            "triage.",
        ],
        "mitre": "T1112 (Defense Evasion: Modify Registry) for persistence",
        "risk": "low",
        "tags": ["windows", "persistence"],
    },
    {
        "slug": "wmi-persistence",
        "title": "WMI Persistence",
        "threat": (
            "WMI event subscriptions trigger payloads on system events "
            "(timers, logons) with no visible scheduled task or service. "
            "They are fileless, stealthy, and missed by autorun tools that "
            "do not enumerate the WMI repository."
        ),
        "signals": [
            "New __EventFilter/__EventConsumer/__FilterToConsumerBinding "
            "instances in the WMI repository, especially ActiveScript or "
            "CommandLine consumers with encoded commands.",
            "WmiPrvSE.exe spawning powershell/cmd at odd times, or WMI "
            "operational log entries for subscription creation.",
            "Persistence that survives task/service cleanup — the classic "
            "sign the mechanism is WMI-based.",
        ],
        "analysis": [
            "Enumerate all event subscriptions (Get-WMIObject -Namespace "
            "root\\subscription) and inspect each consumer's command line.",
            "Correlate subscription creation time with the initial compromise "
            "to confirm it is attacker-planted, not admin tooling.",
        ],
        "harden": [
            "Alert on WMI subscription creation events; restrict WMI "
            "namespace permissions to administrators.",
            "Include WMI repository enumeration in the standard persistence "
            "hunt checklist.",
        ],
        "pitfalls": [
            "Declaring a host clean after checking tasks/services/registry "
            "but never looking at WMI subscriptions.",
            "Removing the consumer but leaving the filter and binding, which "
            "error silently and get recreated by the implant.",
        ],
        "mitre": "T1047 (Execution: Windows Management Instrumentation)",
        "risk": "low",
        "tags": ["windows", "persistence"],
    },
    {
        "slug": "service-persistence",
        "title": "Malicious Service Persistence",
        "threat": (
            "Attackers install or hijack Windows services for SYSTEM-level, "
            "reboot-surviving execution. Services are trusted by admins, so "
            "malicious ones hide with plausible names — verify the binary, "
            "not the display name."
        ),
        "signals": [
            "7045 (service installed) with ImagePath in user-writable or temp "
            "directories, unsigned binaries, or names mimicking legit "
            "services.",
            "Existing service ImagePath changed (7045 with same name, new "
            "binary) or service binary replaced on disk.",
            "Services running as SYSTEM that were recently created and have "
            "no vendor documentation or change record.",
        ],
        "analysis": [
            "Hash and detonate the service binary; check its signature "
            "status and first-seen date in threat intel.",
            "Review the service account: LocalSystem services have maximum "
            "impact — scope accordingly.",
        ],
        "harden": [
            "Alert on all 7045 events; require change tickets for new "
            "services and run services as least-privilege virtual accounts.",
            "Service binary paths on read-only or admin-writable locations "
            "only.",
        ],
        "pitfalls": [
            "Stopping the service without deleting it — it restarts on "
            "reboot.",
            "Missing service DLL hijacking (Services with ServiceDll in "
            "writable paths) while hunting only EXE-based services.",
        ],
        "mitre": "T1543.003 (Persistence: Windows Service)",
        "risk": "low",
        "tags": ["windows", "persistence"],
    },
    {
        "slug": "dll-hijacking",
        "title": "DLL Hijacking",
        "threat": (
            "Applications loading DLLs from insecure paths let attackers plant "
            "a malicious DLL that executes with the application's "
            "privileges. Detection focuses on DLL loads from writable "
            "directories and known-vulnerable applications."
        ),
        "signals": [
            "Sysmon event 7 (image loaded) showing DLLs loaded from temp, "
            "downloads, or user-writable directories by privileged processes.",
            "New DLL files appearing alongside application executables, "
            "especially with names matching system DLLs.",
            "Application crashes or behavior changes after a DLL appears in "
            "its directory.",
        ],
        "analysis": [
            "Verify the loading order: confirm the planted DLL shadows a "
            "legitimate one via PATH or application-directory precedence.",
            "Check the DLL's exports and behavior in a sandbox — many "
            "hijack DLLs proxy the original to stay stealthy.",
        ],
        "harden": [
            "Applications should use absolute paths and SafeDllSearchMode; "
            "remove user-writable directories from the DLL search order.",
            "Monitored application directories: alert on new DLLs in "
            "program installation paths.",
        ],
        "pitfalls": [
            "Deleting the DLL without fixing the insecure load order — the "
            "hole remains for the next attacker.",
            "Assuming signed applications are immune; the signature covers "
            "the EXE, not the DLL it loads.",
        ],
        "mitre": "T1574.001 (Persistence: DLL Search Order Hijacking)",
        "risk": "low",
        "tags": ["windows", "persistence"],
    },
    {
        "slug": "process-injection",
        "title": "Process Injection",
        "threat": (
            "Malware hides inside legitimate processes via injection "
            "(CreateRemoteThread, APC, process hollowing), blending with "
            "normal activity. Memory-focused detection — EDR telemetry and "
            "targeted memory analysis — is the answer; disk forensics alone "
            "misses it."
        ),
        "signals": [
            "EDR alerts on cross-process memory writes (CreateRemoteThread, "
            "NtQueueApcThread) from unusual sources, or hollowed processes "
            "(image path mismatches the in-memory PE).",
            "Legitimate processes (explorer, svchost) making unexpected "
            "network connections or spawning children they never normally do.",
            "Sysmon event 8 (CreateRemoteThread) and event 10 "
            "(ProcessAccess) with suspicious granted-access masks.",
        ],
        "analysis": [
            "Capture process memory before killing anything; extract the "
            "injected payload for family identification.",
            "Trace the injector: which process performed the injection and "
            "how did IT get compromised (the delivery chain).",
        ],
        "harden": [
            "EDR with behavioral blocking on injection primitives; "
            "application control to prevent the initial injector from "
            "running.",
            "Protected Process Light (PPL) for critical processes like "
            "LSASS to raise the injection bar.",
        ],
        "pitfalls": [
            "Killing the host process without capturing memory — the payload "
            "exists only in RAM and the evidence is gone.",
            "Whitelisting the injected process because its NAME is "
            "legitimate; verify the in-memory image, not the filename.",
        ],
        "mitre": "T1055 (Defense Evasion: Process Injection)",
        "risk": "low",
        "tags": ["windows", "malware"],
    },
    {
        "slug": "lolbins-abuse",
        "title": "Living-off-the-Land Binaries Abuse",
        "threat": (
            "Attackers use built-in tools (certutil, bitsadmin, mshta, "
            "rundll32, wmic) for download, execution, and exfiltration — no "
            "malware to signature. Defense is behavioral: baseline normal "
            "LOLBin usage and alert on anomalous parents, arguments, and "
            "network activity."
        ),
        "signals": [
            "LOLBins spawned by Office apps, browsers, or scripts with "
            "network arguments (certutil -urlcache, bitsadmin /transfer) — "
            "parents that never legitimately drive them.",
            "Encoded or obfuscated arguments, downloads to temp/appdata, or "
            "LOLBin-initiated outbound connections.",
            "Rare LOLBins (mshta, regsvr32, cmstp) executing at all in "
            "environments that never use them legitimately.",
        ],
        "analysis": [
            "Reconstruct the full command line — the arguments reveal intent "
            "(download URL, payload path, execution method).",
            "Check whether the LOLBin fetched a second stage; if so, the "
            "investigation continues at the downloaded payload.",
        ],
        "harden": [
            "Application control policies blocking LOLBin network/download "
            "primitives where unused; constrained language mode for "
            "PowerShell.",
            "Alert rules per LOLBin with parent/argument allowlists tuned "
            "from a 30-day baseline.",
        ],
        "pitfalls": [
            "Blocking a LOLBin outright and breaking admin workflows — "
            "constrain by parent and argument, not by existence.",
            "Missing LOLBin use on Linux/macOS (curl, wget, python) while "
            "hunting Windows only.",
        ],
        "mitre": "T1218 (Defense Evasion: System Binary Proxy Execution)",
        "risk": "low",
        "tags": ["windows", "defense-evasion"],
    },
    {
        "slug": "powershell-abuse",
        "title": "Malicious PowerShell Abuse",
        "threat": (
            "PowerShell is the attacker's Swiss-army knife: encoded commands, "
            "in-memory execution, credential theft, lateral movement. Deep "
            "script-block and module logging turns it from a blind spot into "
            "one of your richest telemetry sources."
        ),
        "signals": [
            "Event 4104 (script block logging) with encoded commands "
            "(-enc/-e), Invoke-Mimikatz/Invoke-Shellcode patterns, or "
            "obfuscation (heavy string concatenation, char codes).",
            "PowerShell spawned by Office, browsers, or WMI with hidden "
            "window styles, or AMSI bypass patterns in the script text.",
            "Module logging showing credential-access or AD-enumeration "
            "cmdlets from non-admin workstations.",
        ],
        "analysis": [
            "Decode every obfuscated layer — the final script reveals the "
            "true objective (many 'downloaders' are actually ransomware "
            "staging).",
            "Correlate the PowerShell session with its parent to find the "
            "delivery vector (macro, scheduled task, remote session).",
        ],
        "harden": [
            "Enable script-block logging, module logging, and transcription "
            "fleet-wide; forward to the SIEM with alerting.",
            "Constrained Language Mode + WDAC/Applocker; disable PowerShell "
            "v2.",
        ],
        "pitfalls": [
            "Logging PowerShell without a SIEM pipeline to analyze it — "
            "4104 events are high-volume and useless unsearched.",
            "Assuming -noprofile -w hidden is always malicious; admins use "
            "it too — baseline first.",
        ],
        "mitre": "T1059.001 (Execution: PowerShell)",
        "risk": "low",
        "tags": ["windows", "execution"],
    },
    {
        "slug": "macro-malware",
        "title": "Malicious Office Macro Malware",
        "threat": (
            "Weaponized documents use macros (or legacy DDE/XLM) to execute "
            "payloads when opened. The email lure gets the click; the macro "
            "does the work. Block macros from the internet and the whole "
            "class collapses."
        ),
        "signals": [
            "Office spawning powershell, cmd, wscript, or mshta (child "
            "process anomalies), especially from documents in temp/downloads.",
            "Email gateway detections for documents with VBA/XLM content "
            "from external senders, or sandbox detonations flagging macro "
            "behavior.",
            "AMSI/EDR alerts on macro-executed encoded commands.",
        ],
        "analysis": [
            "Extract and deobfuscate the macro in a sandbox; identify the "
            "C2 or download URL for blocking and scoping.",
            "Check who else received the lure email — macro campaigns are "
            "rarely single-target.",
        ],
        "harden": [
            "Block macros in files from the internet (Mark of the Web "
            "policy); disable XLM macros entirely.",
            "Email sandboxing with detonation for all Office attachments "
            "from external sources.",
        ],
        "pitfalls": [
            "Users enabling macros because the lure says 'Enable content to "
            "view' — user training must cover this exact prompt.",
            "Forgetting legacy formats: XLM and DDE execute without 'macros' "
            "in the modern sense.",
        ],
        "mitre": "T1204.002 (Execution: Malicious File)",
        "risk": "low",
        "tags": ["email", "malware"],
    },
    {
        "slug": "drive-by-download",
        "title": "Drive-By Download",
        "threat": (
            "Visiting a compromised or malicious page silently downloads "
            "malware via browser or plugin exploits. Patching and browser "
            "isolation remove the opportunity; proxy logs reveal the "
            "exposure."
        ),
        "signals": [
            "Browser spawning unexpected child processes or writing "
            "executables to temp/downloads without user download action.",
            "Proxy logs showing visits to compromised sites followed by "
            "executable downloads, often via redirect chains.",
            "Exploit-kit patterns: rapid plugin version probing, obfuscated "
            "JavaScript, then payload fetch.",
        ],
        "analysis": [
            "Reconstruct the redirect chain from proxy logs to identify the "
            "compromised page or malvertising source.",
            "Determine whether the payload executed: browser process tree "
            "and EDR execution events after the download timestamp.",
        ],
        "harden": [
            "Automatic browser and OS patching; remove or sandbox legacy "
            "plugins (Java, Flash-era); consider browser isolation for "
            "high-risk users.",
            "Proxy blocking of newly observed executable downloads by "
            "policy.",
        ],
        "pitfalls": [
            "Assuming the user 'must have clicked something' — drive-bys "
            "need no click, so user interviews mislead.",
            "Cleaning the endpoint without blocking the compromised site "
            "that will re-infect the next visitor.",
        ],
        "mitre": "T1189 (Initial Access: Drive-by Compromise)",
        "risk": "low",
        "tags": ["network", "malware"],
    },
    {
        "slug": "watering-hole",
        "title": "Watering Hole Attack",
        "threat": (
            "Attackers compromise websites your targets frequent, turning "
            "trusted browsing into infection. Detection is epidemiological: "
            "multiple infections sharing one browsing history overlap."
        ),
        "signals": [
            "Several hosts infected with the same payload whose proxy "
            "histories share a common site visited shortly before each "
            "infection.",
            "A trusted industry/partner site serving malicious scripts or "
            "redirects (verified via sandbox fetch).",
            "Infections clustered by department or role matching the "
            "compromised site's audience.",
        ],
        "analysis": [
            "Confirm the watering hole by fetching the suspect site in a "
            "sandbox and capturing the injected code.",
            "Enumerate all visitors to the site in the compromise window — "
            "the exposed population, not just the infected.",
        ],
        "harden": [
            "Notify the site owner; block the malicious URLs/paths (not "
            "necessarily the whole domain) at the proxy.",
            "Browser isolation or strict content policies for high-value "
            "targets who frequent niche industry sites.",
        ],
        "pitfalls": [
            "Treating each infection as independent and missing the common "
            "source — always compare browsing histories across cases.",
            "Blocking the entire legitimate domain permanently instead of "
            "the injected path, breaking business access.",
        ],
        "mitre": "T1189 (Initial Access: Drive-by Compromise) — watering hole variant",
        "risk": "low",
        "tags": ["network", "malware"],
    },
    {
        "slug": "supply-chain-compromise",
        "title": "Supply Chain Compromise",
        "threat": (
            "Trusted software updates or vendor components carry the "
            "attacker's payload — the hardest vector to prevent, because the "
            "malware arrives signed and expected. Defense shifts to "
            "verification, segmentation, and vendor scrutiny."
        ),
        "signals": [
            "A signed, trusted application suddenly exhibiting C2 "
            "communication or spawning unexpected children after an update.",
            "Threat intel or vendor advisory naming a specific product "
            "version as compromised.",
            "Anomalous behavior correlated tightly with a software update "
            "timestamp across many hosts.",
        ],
        "analysis": [
            "Identify the trojanized version and enumerate every host that "
            "installed it — the exposure list defines the response scope.",
            "Determine what the implanted component could access (its "
            "privilege level and data reach) to bound the impact.",
        ],
        "harden": [
            "Software allowlisting with version pinning; staged update "
            "rollouts with behavioral monitoring before fleet-wide deploy.",
            "Vendor risk assessments, SBOM requirements, and network "
            "segmentation limiting what any single application can reach.",
        ],
        "pitfalls": [
            "Assuming signed = safe; supply-chain malware is signed by "
            "definition.",
            "Delaying response waiting for the vendor's statement while the "
            "implant remains active.",
        ],
        "mitre": "T1195 (Initial Access: Supply Chain Compromise)",
        "risk": "low",
        "tags": ["supply-chain", "malware"],
    },
    {
        "slug": "api-abuse",
        "title": "Public API Abuse",
        "threat": (
            "Exposed APIs are probed for injection, broken auth, and excessive "
            "data exposure. API abuse looks like legitimate traffic at "
            "volume — detection needs API-aware logging (endpoint, "
            "parameters, auth context), not just web logs."
        ),
        "signals": [
            "High-rate 4xx/5xx sequences against API endpoints indicating "
            "fuzzing, or single clients enumerating object IDs sequentially.",
            "Authenticated API calls accessing other users' objects (BOLA/IDOR "
            "patterns) or returning bulk data far beyond normal use.",
            "Known attack strings (SQLi, SSTI payloads) in API parameters.",
        ],
        "analysis": [
            "Replay the suspect API sessions to determine exactly which "
            "records were accessed — the breach scope is the data returned, "
            "not the requests made.",
            "Check whether the abused endpoint lacks authorization checks "
            "versus a credentialed attacker using stolen tokens.",
        ],
        "harden": [
            "Positive-security API gateway policies: schema validation, "
            "rate limits per client, and authorization checks on every "
            "object reference.",
            "Comprehensive API audit logging with the authenticated identity "
            "on every call.",
        ],
        "pitfalls": [
            "WAF-only defense: most API abuse is semantically valid HTTP "
            "that no signature catches.",
            "Logging without the auth context — you cannot distinguish "
            "attack from customer without knowing WHO called.",
        ],
        "mitre": "T1190 (Initial Access: Exploit Public-Facing Application)",
        "risk": "low",
        "tags": ["web", "api"],
    },
    {
        "slug": "session-hijacking",
        "title": "Web Session Hijacking",
        "threat": (
            "Stolen session cookies let attackers ride authenticated web "
            "sessions without credentials or MFA. Cookie theft via infostealer "
            "or XSS is the usual source; concurrent-session anomalies are the "
            "usual signal."
        ),
        "signals": [
            "The same session active from two geographies or ASNs "
            "simultaneously, or a session suddenly continuing from a "
            "datacenter IP.",
            "Session created without a fresh authentication event (cookie "
            "replay), or user-agent/IP changing mid-session.",
            "Infostealer execution on the user's device shortly before the "
            "anomalous session.",
        ],
        "analysis": [
            "Determine the theft vector: device compromise (cookie files "
            "exfiltrated) versus application XSS — the fix differs.",
            "Inventory actions taken in the hijacked session: data viewed, "
            "settings changed, transactions performed.",
        ],
        "harden": [
            "Short session lifetimes, binding sessions to device/IP "
            "characteristics, and step-up auth for sensitive actions.",
            "HttpOnly + Secure + SameSite cookies; consider token binding "
            "where supported.",
        ],
        "pitfalls": [
            "Invalidating the password but not the session — the hijacker "
            "stays logged in.",
            "Missing that the user's DEVICE is compromised; the next "
            "session gets stolen too until the infostealer is removed.",
        ],
        "mitre": "T1539 (Credential Access: Steal Web Session Cookie)",
        "risk": "low",
        "tags": ["web", "identity"],
    },
    {
        "slug": "mfa-fatigue",
        "title": "MFA Fatigue Attack",
        "threat": (
            "Attackers with a stolen password spam push notifications until "
            "the victim approves one out of annoyance or confusion. The "
            "defense is push hygiene: number matching, context display, and "
            "rate limits on prompts."
        ),
        "signals": [
            "Dozens of MFA push prompts to one user in minutes, especially "
            "at odd hours, followed by a single approval.",
            "An approval immediately followed by session activity from an "
            "unusual IP or device enrollment changes.",
            "Helpdesk reports of users 'getting lots of MFA prompts' in the "
            "days before the incident.",
        ],
        "analysis": [
            "Reconstruct the prompt storm: count, timing, and the approving "
            "event — then inventory the attacker's post-approval actions.",
            "Check whether the attacker registered a new MFA method during "
            "the session (persistence via second factor).",
        ],
        "harden": [
            "Number matching on all push MFA, show login context (app, "
            "location), and rate-limit prompts per user.",
            "Move high-risk users to phishing-resistant MFA (FIDO2) which "
            "cannot be fatigue-approved.",
        ],
        "pitfalls": [
            "Assuming an approved push means a legitimate user — approval "
            "is exactly what the attacker engineered.",
            "Not checking for newly registered MFA methods, which survive "
            "password resets.",
        ],
        "mitre": "T1621 (Credential Access: MFA Request Generation)",
        "risk": "low",
        "tags": ["identity", "authentication"],
    },
    {
        "slug": "oauth-consent-phishing",
        "title": "OAuth Consent Phishing",
        "threat": (
            "Users grant a malicious app OAuth permissions, giving the "
            "attacker persistent API access to mailbox, files, or directory "
            "— no password needed, survives password resets, invisible in "
            "logon logs."
        ),
        "signals": [
            "New enterprise app registrations or OAuth consent grants for "
            "apps with vague names, especially requesting Mail.Read or "
            "Files.ReadWrite.All.",
            "Consent grants by users outside any change process, or apps "
            "verified by unknown publishers.",
            "API-driven mailbox/file access patterns (Graph API) with no "
            "corresponding interactive logon.",
        ],
        "analysis": [
            "Inventory every permission the malicious app holds and every "
            "API call it made — the data accessed defines the breach.",
            "Check for admin-consent abuse: was the app granted tenant-wide "
            "access by a compromised admin?",
        ],
        "harden": [
            "Require admin consent for third-party apps; maintain an "
            "allowlist of approved publishers.",
            "Alert on new app registrations and high-privilege consent "
            "grants; review app inventory quarterly.",
        ],
        "pitfalls": [
            "Resetting the user's password and declaring victory while the "
            "OAuth grant keeps working.",
            "Overlooking that the app may have been granted access by an "
            "ADMIN — scope tenant-wide, not per-user.",
        ],
        "mitre": "T1528 (Credential Access: Steal Application Access Token)",
        "risk": "low",
        "tags": ["identity", "cloud", "oauth"],
    },
    {
        "slug": "container-escape",
        "title": "Container Escape",
        "threat": (
            "A compromised container breaks out to the host via privileged "
            "mode, hostPath mounts, or kernel exploits — turning one "
            "application breach into full node control. Harden the container "
            "boundary and monitor for escape primitives."
        ),
        "signals": [
            "Containers running privileged or with hostPath mounts to "
            "sensitive host paths, especially created outside normal "
            "deployments.",
            "Host-level processes spawned by container runtimes, or "
            "unexpected writes to host paths from container contexts.",
            "Kernel exploit artifacts or abuse of host namespaces (nsenter-"
            "style) inside container workloads.",
        ],
        "analysis": [
            "Determine the escape primitive: misconfiguration (privileged, "
            "hostPath, hostPID) versus kernel CVE — the fix differs.",
            "Assess node compromise: if escaped, the node is hostile — "
            "cordon, drain, and rebuild it; do not trust in-place cleaning.",
        ],
        "harden": [
            "Never run privileged containers; drop capabilities, use "
            "read-only root filesystems, and enforce via admission "
            "controllers (OPA/Kyverno).",
            "Keep container hosts patched; escape CVEs are patched at the "
            "host kernel, not in the image.",
        ],
        "pitfalls": [
            "Rebuilding the container while the compromised node keeps "
            "serving the attacker's workloads.",
            "Assuming non-privileged means safe — hostPath mounts and "
            "capabilities can be equally fatal.",
        ],
        "mitre": "T1611 (Escape to Host)",
        "risk": "low",
        "tags": ["containers", "kubernetes"],
    },
    {
        "slug": "kubernetes-rbac-abuse",
        "title": "Kubernetes RBAC Abuse",
        "threat": (
            "Overly broad Kubernetes roles let attackers escalate from a "
            "compromised pod to cluster admin. RBAC misconfigurations are "
            "the Kubernetes equivalent of AD delegation sprawl — audit them "
            "the same way."
        ),
        "signals": [
            "Pods or service accounts using cluster-admin or wildcard "
            "roles, especially ones created outside GitOps pipelines.",
            "Kubernetes audit logs showing service accounts listing secrets "
            "cluster-wide or creating privileged pods.",
            "New ClusterRoleBindings granting powerful roles to default or "
            "application service accounts.",
        ],
        "analysis": [
            "Map effective permissions per service account: which can read "
            "secrets, create pods, or exec into others — that is the blast "
            "radius.",
            "Check whether the abused binding was created by the attacker "
            "or pre-existing misconfiguration.",
        ],
        "harden": [
            "Least-privilege RBAC, no wildcards, no cluster-admin for apps; "
            "manage bindings via GitOps with PR review.",
            "Enable and ship Kubernetes audit logs; alert on secret access "
            "and binding changes.",
        ],
        "pitfalls": [
            "Fixing the abused binding but leaving 50 other wildcard roles "
            "in place.",
            "Forgetting that a compromised pod with cloud credentials can "
            "pivot from k8s RBAC to cloud IAM.",
        ],
        "mitre": "T1609 (Container Administration Command)",
        "risk": "low",
        "tags": ["containers", "kubernetes"],
    },
    {
        "slug": "cloud-console-takeover",
        "title": "Cloud Console Takeover",
        "threat": (
            "Stolen cloud credentials used in the web console give attackers "
            "point-and-click infrastructure control. Console logons from "
            "unusual locations followed by IAM changes are the classic "
            "takeover sequence."
        ),
        "signals": [
            "CloudTrail/Entra sign-in logs showing console logons from new "
            "countries or anonymizing services for privileged users.",
            "IAM policy changes, new access keys, or new users created "
            "within minutes of the anomalous logon.",
            "Disabling of CloudTrail/logging or deletion of log data — the "
            "attacker covering tracks.",
        ],
        "analysis": [
            "Reconstruct the full API call sequence after takeover: what "
            "was created, modified, exfiltrated, or destroyed.",
            "Check for persistence: new IAM users, roles with trust "
            "policies pointing outward, or modified instance user-data.",
        ],
        "harden": [
            "Phishing-resistant MFA on all console users, especially root/ "
            "break-glass; SCPs preventing logging disablement.",
            "Alert on IAM changes and console logons from new locations; "
            "immutable log archiving to a separate account.",
        ],
        "pitfalls": [
            "Rotating the compromised user's keys but missing the backdoor "
            "IAM role the attacker created.",
            "Trusting the account's own logs after the attacker had admin — "
            "verify against the immutable archive.",
        ],
        "mitre": "T1078 (Persistence: Valid Accounts) — cloud console",
        "risk": "low",
        "tags": ["cloud", "identity"],
    },
    {
        "slug": "cicd-pipeline-abuse",
        "title": "CI/CD Pipeline Abuse",
        "threat": (
            "Compromised build pipelines inject malicious code into artifacts "
            "or exfiltrate secrets from build environments. Pipelines hold "
            "production credentials AND ship code — treat them as tier-zero "
            "assets."
        ),
        "signals": [
            "Pipeline runs triggered outside normal commits, modified build "
            "scripts, or runners executing unexpected network calls.",
            "Secrets accessed by pipeline jobs that never needed them, or "
            "new pipeline variables containing exfil endpoints.",
            "Artifacts whose hashes differ from reproducible-build "
            "expectations.",
        ],
        "analysis": [
            "Diff the pipeline definition against the last known-good "
            "version; identify exactly which jobs were tampered with.",
            "Determine which secrets the compromised jobs could read and "
            "rotate all of them — assume exposure.",
        ],
        "harden": [
            "Pipeline definitions in version control with required reviews; "
            "ephemeral, isolated runners; OIDC-based short-lived credentials "
            "instead of stored secrets.",
            "Separate build and deploy permissions; sign artifacts and "
            "verify signatures at deploy.",
        ],
        "pitfalls": [
            "Cleaning the pipeline but shipping artifacts it already "
            "poisoned — quarantine recent builds.",
            "Long-lived cloud credentials stored as pipeline secrets; rotate "
            "and replace with OIDC federation.",
        ],
        "mitre": "T1195.002 (Supply Chain: Compromise Software Supply Chain)",
        "risk": "low",
        "tags": ["supply-chain", "devops"],
    },
    {
        "slug": "secrets-in-code",
        "title": "Secrets in Code",
        "threat": (
            "API keys, passwords, and tokens committed to repositories get "
            "scraped by attackers (and by every future repo reader). A "
            "committed secret is a compromised secret — rotate first, clean "
            "history second."
        ),
        "signals": [
            "Secret-scanning alerts (push protection or historical scan) "
            "flagging keys, tokens, or private keys in commits.",
            "Anomalous API usage billed to a key that appears in a "
            "repository, or commits adding '.env' files.",
            "Public repository exposure: any secret ever pushed public is "
            "considered harvested.",
        ],
        "analysis": [
            "For each exposed secret: determine its privileges and check "
            "usage logs for unauthorized use since exposure.",
            "Check git history depth: secrets in old commits are still "
            "exposed to anyone with repo access.",
        ],
        "harden": [
            "Rotate the secret FIRST, then purge from history; enable push "
            "protection and pre-commit secret scanning.",
            "Move all secrets to a vault with dynamic/short-lived "
            "credentials; no static secrets in code, ever.",
        ],
        "pitfalls": [
            "Deleting the commit without rotating — the secret is already "
            "copied.",
            "Scanning only main branch; secrets hide in feature branches, "
            "PRs, and forks.",
        ],
        "mitre": "T1552.001 (Credential Access: Credentials In Files)",
        "risk": "low",
        "tags": ["devops", "secrets"],
    },
    {
        "slug": "backup-tampering",
        "title": "Backup Tampering",
        "threat": (
            "Attackers delete, encrypt, or corrupt backups before the main "
            "attack so recovery is impossible. Backup systems are targeted "
            "FIRST in modern ransomware — monitor them as the crown jewels "
            "they are."
        ),
        "signals": [
            "Backup job deletions, retention policy changes, or repository "
            "credential changes outside change windows.",
            "Backup admin console logons from unusual accounts or hosts, or "
            "mass snapshot deletions in cloud backup vaults.",
            "Backup integrity check failures or sudden drops in restorable "
            "recovery points.",
        ],
        "analysis": [
            "Determine which recovery points were destroyed versus merely "
            "marked deleted — cloud soft-delete and immutable vaults may "
            "still hold copies.",
            "Identify how the attacker reached the backup system: shared "
            "credentials, unpatched console, or compromised admin.",
        ],
        "harden": [
            "Immutable backup storage (object lock / immutable vaults) with "
            "separate credentials and MFA on the backup console.",
            "Alert on ANY backup deletion or policy change; test restores "
            "monthly and verify integrity, not just job success.",
        ],
        "pitfalls": [
            "Backups on the same domain credentials as production — the "
            "attacker uses the same keys on both.",
            "Monitoring backup job success but never testing an actual "
            "restore.",
        ],
        "mitre": "T1490 (Impact: Inhibit System Recovery)",
        "risk": "moderate",
        "tags": ["backup", "ransomware"],
    },
    {
        "slug": "log-tampering",
        "title": "Log Tampering",
        "threat": (
            "Attackers clear or alter logs to blind defenders — event log "
            "clears, audit policy disabling, or timestomping. The tampering "
            "itself is evidence: treat cleared logs as confirmation of "
            "malicious activity, not as missing data."
        ),
        "signals": [
            "Event 1102 (audit log cleared) or 104 (log cleared), audit "
            "policy changes disabling categories, or gaps in otherwise "
            "continuous log streams.",
            "Timestomped files (MFT timestamps inconsistent with sequence "
            "numbers) or syslog gaps from specific hosts.",
            "SIEM agent uninstalls or forwarding configuration changes.",
        ],
        "analysis": [
            "The clear event's timestamp bounds the attacker's active "
            "window — focus forensic effort just before it.",
            "Recover from redundant sources: EDR cloud telemetry, network "
            "logs, and central syslog often survive local clears.",
        ],
        "harden": [
            "Forward logs off-host in real time to tamper-evident central "
            "storage; alert on 1102/104 immediately.",
            "Protect the SIEM pipeline itself: separate credentials, "
            "integrity monitoring on forwarders.",
        ],
        "pitfalls": [
            "Treating 'no logs' as 'no evidence of compromise' — absence "
            "after tampering IS the evidence.",
            "Relying solely on host logs; always have an independent "
            "telemetry path (network, EDR cloud).",
        ],
        "mitre": "T1070 (Defense Evasion: Indicator Removal)",
        "risk": "low",
        "tags": ["forensics", "defense-evasion"],
    },
    {
        "slug": "firmware-rootkit",
        "title": "Firmware Rootkit",
        "threat": (
            "Malware in UEFI/BIOS or device firmware survives OS reinstalls "
            "and disk replacements. Rare but devastating — detection needs "
            "firmware measurement (TPM attestation) and dedicated scanning, "
            "not standard AV."
        ),
        "signals": [
            "CHIPSEC or firmware-scanner findings of modified UEFI modules, "
            "unexpected DXE drivers, or Secure Boot disabled without "
            "authorization.",
            "TPM attestation failures or PCR values deviating from the "
            "known-good baseline for the hardware model.",
            "Persistence surviving full disk wipe and OS reinstall — the "
            "hallmark symptom.",
        ],
        "analysis": [
            "Dump the firmware image (with authorization) and diff against "
            "the vendor's known-good image for the exact board and version.",
            "Determine the implant's capabilities: network, persistence "
            "mechanism, and whether it targets other hosts (some spread via "
            "firmware update mechanisms).",
        ],
        "harden": [
            "Enable Secure Boot + TPM measured boot fleet-wide; lock BIOS "
            "with admin passwords and signed firmware updates only.",
            "Reflash from known-good vendor images (not from within the "
            "compromised OS) and replace hardware that cannot be cleanly "
            "reflashed.",
        ],
        "pitfalls": [
            "Reinstalling the OS repeatedly while the firmware implant "
            "re-infects each build.",
            "Running firmware scans from the potentially compromised OS — "
            "use offline/BIOS-level tooling.",
        ],
        "mitre": "T1542 (Persistence: Pre-OS Boot: System Firmware)",
        "risk": "moderate",
        "tags": ["firmware", "persistence"],
    },
]
