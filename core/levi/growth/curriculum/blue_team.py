"""Blue-team curriculum for LEVI's growth study hall.

Structured, defensive-only lessons that baby Levi studies through
``levi.growth.study``: for each lesson the study hall builds a
cloze-style recall question, retrieves the lesson by topic cue, and
scores what fraction of the key terms come back. That score is a
recall-integrity proxy, NOT a measure of understanding — see
``levi.growth.study``.

Contract: each lesson is a dict with exactly these keys:

    id         stable lesson key, e.g. ``"bt-map-1"`` (unique)
    topic      one of ``BLUE_TEAM_TOPICS`` (exact spelling; the study
               hall's ``recall_by_topic`` unions every lesson under the
               cued topic, so consistent spelling is load-bearing)
    kind       one of ``BLUE_TEAM_KINDS``:
               ``"concept"``, ``"procedure"``, ``"checklist"``, ``"scenario"``
    text       the teachable statement, self-contained, 2-6 sentences
    taught_by  provenance of the lesson. One of:
               * ``"academy:<concept-id>"`` — a LEVI Boot Camp syllabus
                 objective, e.g. ``"academy:AD01B1O1"`` = track A, day 01,
                 block 1, objective 1 (see ``levi.academy.concepts``
                 ``extract_concepts`` for the ID scheme, and
                 ``core/levi/academy/syllabus.json`` for the objectives);
               * ``"boot-camp:session-1"`` — boot-camp session 1, which is
                 day 1 block 1 track A, "The Defender's Map"
                 (``core/levi/academy/schedule.json`` cadence);
               * ``"security-catalog:<domain-id>"`` — a defensive domain
                 from the offline security catalog
                 (``core/levi/knowledge/security/catalog.json``, validated
                 by ``core/levi/knowledge/security/catalog.py``);
               * ``"levi-docs:<doc>"`` / ``"levi:<module>"`` — LEVI's own
                 docs and modules, e.g. ``docs/GROWTH.md``,
                 ``core/levi/growth/study.py``.

Provenance note: every lesson below is grounded in existing repo
content — the Boot Camp syllabus (defensive analyst track A, platform
track B, LEVI-domain track C), the 81-domain defensive security
catalog, and LEVI's growth/study modules. Nothing here is an attack
how-to: the content is detection, analysis, and hardening concepts
only, matching the defensive-only boundary the catalog and the
syllabus both declare. Where the repo was silent, no claim was made.

This list is intentionally separate from the founder seed
``LESSONS`` (Chauncey + Rex teachings) so both curricula keep their
own validation and topic sets. Anything that wants to quiz baby Levi
on this material passes it explicitly, e.g.
``run_quiz(lessons=BLUE_TEAM_LESSONS)``.
"""

from __future__ import annotations

#: Lesson kinds accepted by this curriculum.
BLUE_TEAM_KINDS = frozenset({"concept", "procedure", "checklist", "scenario"})

#: The six topic groups. Exact strings — study hall topic recall is
#: case-insensitive but spelling-sensitive.
BLUE_TEAM_TOPICS = (
    "The Defender's Map",
    "Telemetry and Detection Engineering",
    "Triage and Incident Response",
    "Malware, OSINT, and Threat Intelligence",
    "Hardening Fundamentals",
    "LEVI Domain Mastery",
)

#: 30 defensive lessons, 5 per topic, 2-6 sentences each.
BLUE_TEAM_LESSONS: list[dict[str, str]] = [
    # ------------------------------------------------------------------
    # The Defender's Map — boot-camp session 1 (day 1, block 1, track A)
    # ------------------------------------------------------------------
    {
        "id": "bt-map-1",
        "topic": "The Defender's Map",
        "kind": "concept",
        "text": (
            "MITRE ATT&CK is a defender's coverage map, not an attacker's "
            "menu. A defender maps each deployed detection onto the "
            "techniques it covers, then looks for the tactics with thin or "
            "missing coverage. The map's value is the gap analysis: it shows "
            "where the next detection dollar should go."
        ),
        "taught_by": "academy:AD01B1O1",
    },
    {
        "id": "bt-map-2",
        "topic": "The Defender's Map",
        "kind": "concept",
        "text": (
            "MITRE D3FEND is the countermeasure companion to ATT&CK: it "
            "catalogs defensive techniques that pair with the offensive "
            "techniques ATT&CK describes. For any ATT&CK technique a defender "
            "maps, D3FEND offers candidate countermeasures such as network "
            "traffic filtering or credential hardening. Using both keeps the "
            "defense paired to the threat model instead of ad hoc."
        ),
        "taught_by": "academy:AD01B1O2",
    },
    {
        "id": "bt-map-3",
        "topic": "The Defender's Map",
        "kind": "procedure",
        "text": (
            "The evidence-first analyst loop runs: observe, hypothesize, "
            "verify. First, observe what the telemetry actually says without "
            "narrating beyond it. Then form the smallest hypothesis the "
            "observation supports, and verify by pulling independent "
            "evidence — a second log source, a known-good baseline, a "
            "corroborating indicator. Evidence comes first; the conclusion "
            "never leads the data."
        ),
        "taught_by": "academy:AD01B1O3",
    },
    {
        "id": "bt-map-4",
        "topic": "The Defender's Map",
        "kind": "scenario",
        "text": (
            "An endpoint alert fires for suspected credential dumping on a "
            "finance workstation at 2 a.m. Walk the evidence-first loop: "
            "observe the raw process and command-line telemetry before "
            "deciding anything. Hypothesize the smallest story — an admin "
            "script, or a real dump — and verify against a second source "
            "such as authentication logs or a known-good process baseline. "
            "Escalate only when independent evidence agrees."
        ),
        "taught_by": "boot-camp:session-1",
    },
    {
        "id": "bt-map-5",
        "topic": "The Defender's Map",
        "kind": "checklist",
        "text": (
            "Coverage-review checklist: every in-scope ATT&CK technique is "
            "mapped to at least one detection; techniques with no detection "
            "are ranked by adversary likelihood and business impact; each "
            "detection names the log source it depends on; any detection "
            "that stopped firing after a log change is flagged as silent "
            "coverage loss; the review itself is dated and re-run on a "
            "schedule. A coverage map that is never re-checked is a "
            "snapshot, not a defense."
        ),
        "taught_by": "boot-camp:session-1",
    },
    # ------------------------------------------------------------------
    # Telemetry and Detection Engineering
    # ------------------------------------------------------------------
    {
        "id": "bt-tel-1",
        "topic": "Telemetry and Detection Engineering",
        "kind": "concept",
        "text": (
            "Defenders inventory telemetry from four sources: endpoint, "
            "network, identity, and cloud. Each source proves different "
            "things — endpoint shows what ran on a host, network shows what "
            "moved between systems, identity shows who authenticated, and "
            "cloud shows what the control plane did. Choosing the right "
            "source starts from the investigative question, not from the "
            "dashboard that is open."
        ),
        "taught_by": "academy:AD02B1O1",
    },
    {
        "id": "bt-tel-2",
        "topic": "Telemetry and Detection Engineering",
        "kind": "concept",
        "text": (
            "Detection engineering is the lifecycle of a detective control: "
            "idea, draft, test, production, tune. A detection is "
            "production-ready only after it has been tested against "
            "lab-generated attack telemetry, not just imagined. Untended "
            "detections accumulate detection debt — rules that are noisy, "
            "stale, or silently blind — so coverage is reviewed on a "
            "schedule, not once."
        ),
        "taught_by": "security-catalog:detection-engineering",
    },
    {
        "id": "bt-tel-3",
        "topic": "Telemetry and Detection Engineering",
        "kind": "procedure",
        "text": (
            "A Sigma detection-as-code rule has three parts: logsource, "
            "detection, and condition. The logsource declares which telemetry "
            "the rule consumes; the detection section holds the selection "
            "logic; the condition combines selections into the final alert "
            "criterion. Because Sigma is vendor-agnostic, the same rule "
            "draft ports across SIEM platforms instead of locking the team "
            "into one."
        ),
        "taught_by": "academy:AD04B1O1",
    },
    {
        "id": "bt-tel-4",
        "topic": "Telemetry and Detection Engineering",
        "kind": "checklist",
        "text": (
            "Detection-health checklist: rule coverage is mapped to a "
            "technique framework; true-positive and false-positive rates "
            "are tracked per rule; mean time to detect is measured; rules "
            "that stopped firing after a log source change raise an alert "
            "as silent coverage loss; every rule is version-controlled and "
            "mapped to the technique it covers. A rule nobody measures is a "
            "hope, not a control."
        ),
        "taught_by": "security-catalog:detection-engineering",
    },
    {
        "id": "bt-tel-5",
        "topic": "Telemetry and Detection Engineering",
        "kind": "scenario",
        "text": (
            "A credential-access detection that fired weekly goes quiet for "
            "a month with no tuning change on record. The likely cause is "
            "not a safer network — it is a log source change upstream. "
            "Treat silence as a signal: confirm the sensor still ships the "
            "fields the rule consumes, re-test the rule against fresh lab "
            "telemetry, and restore coverage before the gap becomes an "
            "incident."
        ),
        "taught_by": "security-catalog:detection-engineering",
    },
    # ------------------------------------------------------------------
    # Triage and Incident Response
    # ------------------------------------------------------------------
    {
        "id": "bt-ir-1",
        "topic": "Triage and Incident Response",
        "kind": "concept",
        "text": (
            "Incident response runs in phases: preparation, detection, "
            "containment, eradication, and recovery. Incidents are a matter "
            "of when, not if, so the quality of the response determines the "
            "blast radius. Preparation — tested playbooks, centralized "
            "logging, and pre-authorized containment actions — is what "
            "makes the later phases fast."
        ),
        "taught_by": "security-catalog:incident-response",
    },
    {
        "id": "bt-ir-2",
        "topic": "Triage and Incident Response",
        "kind": "procedure",
        "text": (
            "Triage priority is set by three factors: severity, fidelity, "
            "and asset value. Work the queue highest-priority first without "
            "dropping criticals, and write triage notes another analyst can "
            "act on — what was observed, what was ruled out, and what the "
            "next step is. Alert fatigue is fought with better fidelity, "
            "never with skipped queues."
        ),
        "taught_by": "academy:AD05B1O1",
    },
    {
        "id": "bt-ir-3",
        "topic": "Triage and Incident Response",
        "kind": "concept",
        "text": (
            "Mean time to detect and mean time to contain are the core "
            "health metrics of an incident response capability. They "
            "measure the team, not the tooling: faster detection shrinks "
            "the window an adversary has to operate. Track them over time "
            "and treat a rising trend as the incident before the incident."
        ),
        "taught_by": "security-catalog:incident-response",
    },
    {
        "id": "bt-ir-4",
        "topic": "Triage and Incident Response",
        "kind": "checklist",
        "text": (
            "First-responder evidence checklist: every incident note carries "
            "timestamps, sources, and a confidence level; digital evidence "
            "keeps a chain of custody from the very first response action; "
            "forensic copies use write-blocked imaging so originals are "
            "untouched; logging is centralized with tamper-evident "
            "retention. Findings feed future detection: each investigation "
            "should produce new indicators and name the telemetry that was "
            "missing."
        ),
        "taught_by": "security-catalog:forensics",
    },
    {
        "id": "bt-ir-5",
        "topic": "Triage and Incident Response",
        "kind": "scenario",
        "text": (
            "An impossible-travel logon alert fires: the same account "
            "authenticates from two continents minutes apart. Treat it as "
            "a trigger for the IR playbook, not a conclusion — VPN "
            "exit nodes and travel both produce benign versions of this "
            "pattern. Verify with a second signal, such as the device "
            "posture or a failed MFA challenge, before containment. "
            "Record the decision either way so the next analyst inherits "
            "the context."
        ),
        "taught_by": "security-catalog:incident-response",
    },
    # ------------------------------------------------------------------
    # Malware, OSINT, and Threat Intelligence
    # ------------------------------------------------------------------
    {
        "id": "bt-ti-1",
        "topic": "Malware, OSINT, and Threat Intelligence",
        "kind": "concept",
        "text": (
            "Malware analysis turns an unknown binary into actionable "
            "intelligence: what it does, how to detect it, and how to "
            "remove it. Static and dynamic analysis each reveal different "
            "behaviors, and every analysis should end as new indicators — "
            "file hashes, command-and-control domains and IPs, persistence "
            "mechanisms. All analysis happens in isolated sandboxes or "
            "air-gapped VMs, never on production hosts."
        ),
        "taught_by": "security-catalog:malware-analysis",
    },
    {
        "id": "bt-ti-2",
        "topic": "Malware, OSINT, and Threat Intelligence",
        "kind": "procedure",
        "text": (
            "Run self-OSINT to discover what attackers already know about "
            "the organization. Search breach dumps and paste sites for "
            "organizational credentials, scan public code repositories for "
            "leaked secrets, and monitor certificate transparency and DNS "
            "for lookalike domains targeting the brand. Every exposure "
            "found is remediated — rotate the secret, request the takedown "
            "— not just noted."
        ),
        "taught_by": "security-catalog:osint",
    },
    {
        "id": "bt-ti-3",
        "topic": "Malware, OSINT, and Threat Intelligence",
        "kind": "concept",
        "text": (
            "Indicator discipline keeps threat feeds useful: indicators "
            "are ingested into enforcement points automatically, scored "
            "by confidence, prioritized by sector relevance, and expired "
            "when stale. Indicator matching is always paired with "
            "behavioral detection, because a feed alone cannot catch what "
            "has no known signature. Measure feeds by true positives in "
            "your own environment, not by volume."
        ),
        "taught_by": "security-catalog:ioc",
    },
    {
        "id": "bt-ti-4",
        "topic": "Malware, OSINT, and Threat Intelligence",
        "kind": "scenario",
        "text": (
            "A honeypot alert fires: someone authenticated against a "
            "honey account that no legitimate user should touch. Any "
            "interaction with a honeypot is malicious by definition, so "
            "this alert is confirmed activity requiring investigation — "
            "never tuning. Review the collected attacker telemetry, rotate "
            "the honey credentials, and check whether the same actor "
            "touched production systems. Honeypots yield high-fidelity "
            "alerts precisely because they have no legitimate traffic."
        ),
        "taught_by": "security-catalog:honeypots",
    },
    {
        "id": "bt-ti-5",
        "topic": "Malware, OSINT, and Threat Intelligence",
        "kind": "checklist",
        "text": (
            "Intelligence operationalization checklist: subscribe to "
            "sector-relevant feeds; every intel item maps to a blocking or "
            "detection control with an expiry date; confirmed indicators "
            "reach the firewall, DNS, and EDR promptly; findings are "
            "shared with peer groups in anonymized form; success is "
            "measured by decisions changed, not reports consumed. "
            "Intelligence that never reaches a control is trivia."
        ),
        "taught_by": "security-catalog:threat-intelligence",
    },
    # ------------------------------------------------------------------
    # Hardening Fundamentals
    # ------------------------------------------------------------------
    {
        "id": "bt-hard-1",
        "topic": "Hardening Fundamentals",
        "kind": "concept",
        "text": (
            "Multi-factor authentication makes a leaked password "
            "insufficient on its own, which is why self-OSINT so often "
            "finds exposed credentials: the exposure matters less when "
            "the password is only one of two required factors. Enforce MFA "
            "on every externally reachable account, with phishing-resistant "
            "factors for the highest-value targets. A password alone is a "
            "single point of failure."
        ),
        "taught_by": "security-catalog:osint",
    },
    {
        "id": "bt-hard-2",
        "topic": "Hardening Fundamentals",
        "kind": "concept",
        "text": (
            "Defense in depth layers controls so no single failure is "
            "fatal: segmentation contains lateral movement, centralized "
            "logging preserves the evidence trail, and least-privilege "
            "limits what any compromised account can reach. Each layer "
            "buys the defenders time and the adversary cost. Design "
            "controls assuming breach, not assuming prevention."
        ),
        "taught_by": "security-catalog:incident-response",
    },
    {
        "id": "bt-hard-3",
        "topic": "Hardening Fundamentals",
        "kind": "procedure",
        "text": (
            "Centralize logging with tamper-evident retention adequate to "
            "the threat model. Forward every security-relevant source — "
            "endpoint, network, identity, honeypots — to the SIEM so "
            "investigators have one timeline to work from. Restrict who "
            "can alter or purge logs, because an adversary who can edit "
            "the logs can erase the investigation."
        ),
        "taught_by": "security-catalog:forensics",
    },
    {
        "id": "bt-hard-4",
        "topic": "Hardening Fundamentals",
        "kind": "checklist",
        "text": (
            "Ransomware-readiness checklist: tested playbooks exist for "
            "ransomware, account compromise, and data theft; backups are "
            "isolated from the production network and restore-tested; "
            "containment actions are pre-authorized so nobody waits for "
            "permission mid-incident; tabletop exercises run quarterly. "
            "The first time a playbook is opened should never be during "
            "the incident it was written for."
        ),
        "taught_by": "security-catalog:incident-response",
    },
    {
        "id": "bt-hard-5",
        "topic": "Hardening Fundamentals",
        "kind": "scenario",
        "text": (
            "Self-OSINT surfaces a lookalike domain one character off the "
            "company's, with a fresh certificate and a login page clone. "
            "This is a phishing staging site: submit it to the takedown "
            "process, block the domain at DNS and proxy, and alert staff "
            "with the exact URL so reports come in. Afterwards, add the "
            "lookalike pattern to the monitoring that found it. Speed of "
            "takedown is the metric."
        ),
        "taught_by": "security-catalog:osint",
    },
    # ------------------------------------------------------------------
    # LEVI Domain Mastery
    # ------------------------------------------------------------------
    {
        "id": "bt-levi-1",
        "topic": "LEVI Domain Mastery",
        "kind": "concept",
        "text": (
            "LEVI runs a tool-using agentic loop over a tool registry: the "
            "loop proposes actions, and a human-in-the-loop gate approves "
            "consequential execution before anything irreversible happens. "
            "Every tool call is traceable end to end, so an operator can "
            "reconstruct exactly what the loop did and why. The gate is "
            "not a suggestion — it is where autonomy stops and "
            "accountability starts."
        ),
        "taught_by": "academy:CD01B1O2",
    },
    {
        "id": "bt-levi-2",
        "topic": "LEVI Domain Mastery",
        "kind": "concept",
        "text": (
            "LEVI's core is local-first and stdlib-only: no paid APIs, no "
            "cloud dependency for the core loop, running on owned "
            "hardware. That makes the marginal cost of producing one more "
            "LEVI effectively zero, which is the economic basis for a free "
            "core. Cloud capability exists as an option the user reaches "
            "for, never as a dependency the core assumes."
        ),
        "taught_by": "levi-docs:AGENT.md",
    },
    {
        "id": "bt-levi-3",
        "topic": "LEVI Domain Mastery",
        "kind": "procedure",
        "text": (
            "The growth loop runs harvest, then reflect, then consolidate, "
            "then journal. Harvest collects new experiences read-only; "
            "reflect turns them into candidate learnings by rules first, "
            "model only when reachable; consolidate writes learnings to "
            "memory, corroborating near-duplicates instead of duplicating "
            "them; journal appends every cycle to the baby book. A "
            "per-source watermark makes each cycle idempotent — nothing "
            "is ever re-learned twice."
        ),
        "taught_by": "levi-docs:GROWTH.md",
    },
    {
        "id": "bt-levi-4",
        "topic": "LEVI Domain Mastery",
        "kind": "concept",
        "text": (
            "The study hall's self-quiz is a crude recall proxy, not a "
            "measure of understanding. It checks whether taught material "
            "is still intact and retrievable by topic cue — like a student "
            "reciting back — by scoring what fraction of a lesson's key "
            "terms come back. Scores trend in the journal so Chauncey can "
            "see the line over time; the honesty is in naming the limit."
        ),
        "taught_by": "levi:study.py",
    },
    {
        "id": "bt-levi-5",
        "topic": "LEVI Domain Mastery",
        "kind": "checklist",
        "text": (
            "Growth safety-rails checklist: growth writes only to the "
            "memory store as growth-tagged entries and to the journal — "
            "never to tools, policy, identity, or the charter; reflection "
            "may not produce sentience or subjective-experience claims; "
            "the founder can always forget a learning with parental "
            "control. Development stages are a pure function of "
            "consolidated learnings: engagement copy, never a cognitive "
            "claim."
        ),
        "taught_by": "levi:study.py",
    },
]


def validate_blue_team_lessons(
    lessons: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Validate a blue-team lesson list; return it unchanged when clean.

    Raises ValueError on the first structural problem: wrong key set,
    empty text, duplicate id, unknown kind, or unknown topic.
    """
    if not isinstance(lessons, list):
        raise ValueError(
            "validate_blue_team_lessons: expected a list, got %s"
            % type(lessons).__name__
        )
    seen: set[str] = set()
    for i, lesson in enumerate(lessons):
        where = "lesson #%d" % i
        if not isinstance(lesson, dict):
            raise ValueError("%s: expected a dict" % where)
        keys = set(lesson)
        if keys != {"id", "topic", "kind", "text", "taught_by"}:
            raise ValueError(
                "%s: keys must be exactly {id, topic, kind, text, taught_by}, "
                "got %s" % (where, sorted(keys))
            )
        lid = lesson["id"]
        if not isinstance(lid, str) or not lid.strip():
            raise ValueError("%s: id must be a non-empty string" % where)
        if lid in seen:
            raise ValueError("%s: duplicate id %r" % (where, lid))
        seen.add(lid)
        if lesson["topic"] not in BLUE_TEAM_TOPICS:
            raise ValueError(
                "%s: unknown topic %r (expected one of %s)"
                % (where, lesson["topic"], list(BLUE_TEAM_TOPICS))
            )
        if lesson["kind"] not in BLUE_TEAM_KINDS:
            raise ValueError(
                "%s: unknown kind %r (expected one of %s)"
                % (where, lesson["kind"], sorted(BLUE_TEAM_KINDS))
            )
        text = lesson["text"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError("%s: text must be a non-empty string" % where)
        taught_by = lesson["taught_by"]
        if not isinstance(taught_by, str) or not taught_by.strip():
            raise ValueError("%s: taught_by must be a non-empty string" % where)
    return lessons


#: The validated curriculum — importable as ``BLUE_TEAM_LESSONS``.
BLUE_TEAM_LESSONS = validate_blue_team_lessons(BLUE_TEAM_LESSONS)
