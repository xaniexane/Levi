"""Batch-3 dimension data: scenarios 26-50.

Original defensive blue-team content authored for LEVI. Zero contact with
any external skill repository.
"""

SCENARIOS_C = [
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
            "Missing service DLL hijacking (services with ServiceDll in "
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
            "A trusted industry/partner site serving exploit code or "
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
