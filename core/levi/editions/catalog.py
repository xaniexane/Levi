"""The edition catalog: 11 sector editions as data, not code sprawl.

Roster slots select agents by category (never raw ids) so catalog
re-stamping never breaks an edition. Sides: "ai" does procedure,
"si" does purpose; most institutional editions are Hybrid by nature —
the pairing is the product.

Safety boundary is absolute: defensive / authorized purple-team only.
Every edition names its deliberate refusals in `excluded`.
"""

from __future__ import annotations

from typing import Dict, List

from .manifest import DataPosture, EditionManifest, Ring, RosterSlot


def _dp(**kw) -> DataPosture:
    return DataPosture(**kw)


EDUCATION = EditionManifest(
    id="education",
    name="LEVI Education",
    sector="universities, schools, course creators",
    ring=Ring.CLOSED,
    tagline="Course production, assistants, grading — the classroom's team.",
    description=(
        "An institutional edition for universities and schools: course "
        "production pipelines, teaching assistants, and grading assistance "
        "under instructor authority. The AI side holds procedure — rubrics, "
        "schedules, consistency; the SI side brings purpose — lesson "
        "design, Socratic sparring, creative variation."
    ),
    roster=(
        RosterSlot(
            "Learning & Notes",
            (
                "Curriculum Cartographer",
                "Micro-Lesson Smith",
                "Skim-to-Skeleton",
                "Topic Map Weaving",
            ),
            side="si",
            count=2,
            purpose="course design and production",
        ),
        RosterSlot(
            "Learning & Notes",
            ("Exam Drill", "Socratic Sparring Partner", "Source Verifier"),
            side="ai",
            count=2,
            purpose="drills, tutoring, citation checks",
        ),
        RosterSlot(
            "Communication",
            (),
            side="either",
            count=1,
            purpose="announcements, office-hour triage",
        ),
        RosterSlot(
            "Productivity",
            (),
            side="ai",
            count=1,
            purpose="grading workflow under rubric lock",
        ),
    ),
    ai_si_mix="AI-leaning Hybrid: procedure first (rubrics, consistency), "
    "SI for lesson design and creative variation.",
    workflows=(
        "course-production pipeline: source → skeleton → micro-lessons → review",
        "grading assistance: rubric-locked scoring drafts, instructor signs every grade",
        "socratic tutoring sessions with session receipts",
        "reading-queue digests and lecture reaping for instructors",
    ),
    data_posture=_dp(
        residency="institution-local first",
        retention="term-bound; purged on request",
        notes="FERPA-style minimization: no training on student work, ever. "
        "Student data never leaves the institution's deployment.",
    ),
    compliance=(
        "instructor sign-off required on all grades",
        "student data minimized; no behavioral profiling",
        "audit receipts on every grading run",
    ),
    excluded=(
        (
            "automated final grades without instructor sign-off",
            "assists, never decides — the grade is a human act",
        ),
        (
            "student surveillance or attention tracking",
            "the classroom is not a panopticon",
        ),
    ),
    tier_fit="4 to Pro — a 6-operator team template",
    pricing_note=(
        "Institutional seat pricing, 30-60% below comparable ed-tech suites; "
        "no giant sells a no-training-on-student-work guarantee — charge for it."
    ),
)

LAW_ENFORCEMENT = EditionManifest(
    id="law-enforcement",
    name="LEVI Sentinel",
    sector="police, sheriff, investigative units",
    ring=Ring.CLOSED,
    tagline="Paperwork, detective work, forensics support — the lawful assistant.",
    description=(
        "Assists lawful police work: report drafting, evidence-log support, "
        "timeline building, pattern and heat-map analysis, simulation, and a "
        "theory workbench. Analyzes evidence the agency lawfully holds; "
        "chain-of-custody honesty is the product — analysis never alters "
        "source evidence, copies are marked as copies, every finding is "
        "receipted with provenance."
    ),
    roster=(
        RosterSlot(
            "Security & Privacy",
            ("Export consent ledger", "Backup integrity warden"),
            side="ai",
            count=2,
            purpose="evidence integrity and handling logs",
        ),
        RosterSlot(
            "Security & Privacy",
            (),
            side="ai",
            count=1,
            purpose="general security hygiene",
        ),
        RosterSlot(
            "Productivity",
            (),
            side="ai",
            count=2,
            purpose="report drafting, paperwork automation",
        ),
        RosterSlot(
            "Travel & Local",
            (),
            side="si",
            count=2,
            purpose="pattern and heat-map analysis, place-based trends",
        ),
        RosterSlot(
            "Communication",
            (),
            side="either",
            count=1,
            purpose="inter-unit coordination drafts",
        ),
    ),
    ai_si_mix="Balanced Hybrid: AI for paperwork, integrity logs, procedure; "
    "SI for pattern discovery, theory workbenches, simulation.",
    workflows=(
        "report drafting from field notes with review gates",
        "evidence-log assistance with chain-of-custody receipts",
        "timeline building from case materials",
        "pattern/heat-map analysis on places and cases — never persons",
        "theory workbench: competing hypotheses, scored and receipted",
    ),
    data_posture=_dp(
        residency="agency-sovereign; on-premise default",
        retention="case-bound; retention per agency policy, enforced in code",
        notes="Lawful-use attestation at deployment. Warrant-bound handling: "
        "the edition refuses to analyze data outside its lawful scope.",
    ),
    compliance=(
        "chain-of-custody honesty on every artifact",
        "every finding carries provenance and a sealed receipt",
        "audit export ready for discovery and oversight",
    ),
    excluded=(
        (
            "surveillance automation and dragnet identification",
            "patterns on places and cases, never dragnets on people",
        ),
        ("predictive policing of persons", "the edition will not score human beings"),
        (
            "offensive capability of any kind",
            "defensive and authorized analysis only — purple-team law",
        ),
        ("altering source evidence", "analysis copies; the original is untouchable"),
    ),
    tier_fit="Pro to Hybrid — an 8-operator team template",
    pricing_note=(
        "Premium sector surface: no major lab sells a forensics-assistant "
        "edition with chain-of-custody receipts. Charge for what they don't "
        "offer; undercut where comparable tooling exists."
    ),
)

MILITARY = EditionManifest(
    id="military",
    name="LEVI Aegis",
    sector="defense, worldwide deployment",
    ring=Ring.GOVERNMENT,
    tagline="Security-grade AI and SI — Levi worldwide, sovereign.",
    description=(
        "Government-ring edition for defense: hardened, auditable, "
        "sovereign. Defensive and authorized operations support only — "
        "planning assistance, secure communications workflows, system care, "
        "threat-awareness analysis. Twelve-gate hardening checklist "
        "required before any deployment."
    ),
    roster=(
        RosterSlot(
            "Security & Privacy",
            (),
            side="ai",
            count=2,
            purpose="defensive posture, integrity watch",
        ),
        RosterSlot(
            "System & Device Care",
            (),
            side="ai",
            count=2,
            purpose="fleet system care, update marshaling",
        ),
        RosterSlot(
            "Communication",
            (),
            side="either",
            count=1,
            purpose="secure coordination workflows",
        ),
        RosterSlot(
            "Travel & Local",
            (),
            side="si",
            count=1,
            purpose="logistics pattern awareness",
        ),
    ),
    ai_si_mix="AI-leaning Hybrid under strict gates: procedure dominates; "
    "SI bounded to logistics and planning support.",
    workflows=(
        "defensive threat-awareness briefings from authorized feeds",
        "secure communications and coordination workflows",
        "fleet system-care and update marshaling",
        "planning assistance with sealed receipts",
    ),
    data_posture=_dp(
        residency="sovereign; air-gap capable",
        retention="mission-bound; sovereign purge authority",
        notes="Twelve-gate hardening checklist mandatory. The deployer holds "
        "the off-switch; no update can remove it.",
    ),
    compliance=(
        "all twelve government-ring hardening gates green",
        "penetration review before promotion",
        "sovereign off-switch under deployer control",
    ),
    excluded=(
        (
            "autonomous targeting or weapons direction",
            "absolutely never — the edition cannot aim, fire, or decide force",
        ),
        (
            "offensive cyber capability",
            "defensive and authorized only, without exception",
        ),
        (
            "autonomous engagement decisions",
            "humans decide; the edition assists and records",
        ),
    ),
    tier_fit="Prime to Supra — sovereign deployment is the product",
    pricing_note=(
        "Highest rentable power below Supra. Sovereignty, auditability, and "
        "the twelve gates are incomparable surfaces — price them as such."
    ),
)

GOVERNMENT = EditionManifest(
    id="government",
    name="LEVI Civitas",
    sector="political, administrative, civic",
    ring=Ring.GOVERNMENT,
    tagline="Political and security-grade AI and SI — auditable to the root.",
    description=(
        "Government-ring edition for civic administration: constituent "
        "workflows, records handling, inter-office coordination, and "
        "decision-support with unbroken provenance. Every consequential "
        "action is sealed, receipted, and FOIA-ready. Nothing the edition "
        "does obscures how a decision was made."
    ),
    roster=(
        RosterSlot(
            "Communication",
            (),
            side="ai",
            count=2,
            purpose="constituent correspondence drafts, coordination",
        ),
        RosterSlot(
            "Productivity",
            (),
            side="ai",
            count=2,
            purpose="records workflows, briefing production",
        ),
        RosterSlot(
            "Security & Privacy",
            (),
            side="ai",
            count=1,
            purpose="handling hygiene, integrity watch",
        ),
        RosterSlot(
            "Finance & Money",
            (),
            side="ai",
            count=1,
            purpose="budget tracking assistance",
        ),
    ),
    ai_si_mix="AI-dominant: procedure, records, and provenance first; "
    "SI in a bounded advisory seat for policy option-weaving.",
    workflows=(
        "constituent correspondence with review gates",
        "briefing production from source materials",
        "records handling with retention enforcement",
        "decision-support memos with full provenance chains",
    ),
    data_posture=_dp(
        residency="sovereign per jurisdiction",
        retention="records-schedule bound, enforced in code",
        notes="FOIA-ready audit export. Decision provenance is never "
        "obscured — the trail is the product's memory of itself.",
    ),
    compliance=(
        "all twelve government-ring hardening gates green",
        "records retention enforced in code, not policy docs",
        "audit export in human-readable form",
    ),
    excluded=(
        (
            "anything that obscures decision provenance",
            "a government that can't show its work can't use this edition",
        ),
        ("surveillance of constituents", "service, not watching"),
    ),
    tier_fit="Prime to Supra — sovereign deployment is the product",
    pricing_note=(
        "Sovereign-grade pricing: auditability and no-training attestation "
        "are incomparable. Undercut generic gov-tech where comparable."
    ),
)

HEALTHCARE = EditionManifest(
    id="healthcare",
    name="LEVI Mercy",
    sector="hospitals, clinics, care teams",
    ring=Ring.CLOSED,
    tagline="Assists clinicians. Never decides.",
    description=(
        "For hospitals and care teams: scheduling support, documentation "
        "assistance, shift coordination, patient-flow awareness, and "
        "wellness support tooling. Privacy-first and local-first; no training "
        "on patient data, ever. Assists clinicians — never diagnoses, never "
        "triages, never decides care."
    ),
    roster=(
        RosterSlot(
            "Health & Fitness",
            (),
            side="ai",
            count=2,
            purpose="wellness support, scheduling-adjacent routines",
        ),
        RosterSlot(
            "Health & Fitness",
            (),
            side="either",
            count=1,
            purpose="care-team coordination support",
        ),
        RosterSlot(
            "Communication",
            (),
            side="ai",
            count=1,
            purpose="coordination drafts, handoff notes",
        ),
        RosterSlot(
            "Productivity", (), side="ai", count=1, purpose="documentation assistance"
        ),
        RosterSlot(
            "Security & Privacy",
            (),
            side="ai",
            count=1,
            purpose="privacy hygiene, access watch",
        ),
    ),
    ai_si_mix="AI-dominant Hybrid: procedure and privacy first; SI bounded "
    "to scheduling and workflow creativity — never clinical judgment.",
    workflows=(
        "documentation assistance from clinician notes",
        "shift and schedule coordination support",
        "patient-flow awareness dashboards (aggregate, de-identified)",
        "handoff-note drafting with clinician review",
    ),
    data_posture=_dp(
        residency="facility-local; on-premise default",
        retention="minimum necessary; purge on schedule",
        notes="No training on patient data — enforced in code, attested at "
        "release. Minimum-necessary access on every workflow.",
    ),
    compliance=(
        "minimum-necessary data access",
        "clinician review on all documentation output",
        "audit receipts on every run",
    ),
    excluded=(
        (
            "diagnosis or diagnostic suggestions",
            "assists clinicians; the judgment is theirs alone",
        ),
        ("triage automation", "no machine orders the queue of the sick"),
        ("training on patient data", "never — this refusal is the selling point"),
    ),
    tier_fit="Pro to Hybrid — a 6-operator team template",
    pricing_note=(
        "Premium surface: a no-training, local-first clinical assistant is "
        "incomparable. Price the guarantee, undercut generic admin tooling."
    ),
)

FIRST_RESPONDERS = EditionManifest(
    id="first-responders",
    name="LEVI Beacon",
    sector="fire, EMS, rescue, emergency management",
    ring=Ring.CLOSED,
    tagline="Works when everything else is down.",
    description=(
        "For first responders: coordination support, incident-note capture, "
        "routing awareness, equipment checks, and offline-capable reference. "
        "Built for degraded mode — when the network is gone, the edition "
        "still serves from local state. Assists; humans dispatch, humans "
        "decide."
    ),
    roster=(
        RosterSlot(
            "Communication",
            (),
            side="ai",
            count=2,
            purpose="coordination drafts, incident-note capture",
        ),
        RosterSlot(
            "Travel & Local",
            (),
            side="either",
            count=1,
            purpose="routing awareness from local maps",
        ),
        RosterSlot(
            "Health & Fitness",
            ("First Aid Kit Auditor", "Emergency Card Updater"),
            side="ai",
            count=1,
            purpose="readiness checks",
        ),
        RosterSlot(
            "System & Device Care",
            (),
            side="ai",
            count=1,
            purpose="device readiness, offline integrity",
        ),
    ),
    ai_si_mix="AI-dominant: reliability and procedure first; SI for "
    "improvised coordination when plans break.",
    workflows=(
        "incident-note capture with timestamps and receipts",
        "equipment and readiness checklists",
        "offline reference from local state",
        "coordination drafts for multi-unit response",
    ),
    data_posture=_dp(
        residency="device-local; syncs only when the responder allows",
        retention="incident-bound",
        notes="Degraded-mode first: full function without network. "
        "Local state is the source of truth in the field.",
    ),
    compliance=(
        "offline capability verified before release",
        "human dispatch authority never delegated",
        "incident receipts with timestamps",
    ),
    excluded=(
        ("dispatch authority", "humans dispatch — the edition suggests, never orders"),
        (
            "network-dependent critical paths",
            "if it needs the cloud to save a life, it doesn't ship",
        ),
    ),
    tier_fit="4 to Pro — a 5-operator team template",
    pricing_note=(
        "Appeal pricing for public-safety agencies; volume over margin. "
        "Reliability is the surface no giant sells."
    ),
)

LEGAL = EditionManifest(
    id="legal",
    name="LEVI Counsel",
    sector="law firms, in-house counsel, legal aid",
    ring=Ring.CLOSED,
    tagline="Assists counsel. Never practices.",
    description=(
        "For legal practice: document workflows, research assistance, "
        "deadline tracking, billing support, and brief-drafting under "
        "attorney review. Privilege-aware confidentiality; no training on "
        "client matter, ever. Assists counsel — never gives legal advice as "
        "authority, never files, never decides."
    ),
    roster=(
        RosterSlot(
            "Productivity",
            (),
            side="ai",
            count=2,
            purpose="document workflows, deadline tracking",
        ),
        RosterSlot(
            "Learning & Notes",
            ("Source Verifier", "Skim-to-Skeleton"),
            side="ai",
            count=1,
            purpose="research assistance",
        ),
        RosterSlot(
            "Communication",
            (),
            side="ai",
            count=1,
            purpose="correspondence drafts under review",
        ),
        RosterSlot(
            "Finance & Money",
            ("Invoice Bloodhound", "Mileage Log Scribe"),
            side="ai",
            count=1,
            purpose="billing support",
        ),
    ),
    ai_si_mix="AI-dominant: procedure, precision, and privilege first; SI "
    "in a bounded seat for argument-weaving under attorney review.",
    workflows=(
        "document drafting with attorney review gates",
        "research assistance with cited sources",
        "deadline and docket tracking",
        "billing support from time records",
    ),
    data_posture=_dp(
        residency="firm-local; on-premise default",
        retention="matter-bound; client purge authority",
        notes="Privilege-aware: client matter never trains models, never "
        "leaves the firm's deployment without explicit instruction.",
    ),
    compliance=(
        "attorney review gates on all substantive output",
        "privilege-aware handling throughout",
        "no training on client matter — enforced and attested",
    ),
    excluded=(
        (
            "unauthorized practice of law",
            "assists counsel; the advice is the attorney's",
        ),
        (
            "filing or service without attorney sign-off",
            "the edition drafts; counsel acts",
        ),
    ),
    tier_fit="4 to Pro — a 5-operator team template",
    pricing_note=(
        "Premium surface: privilege-aware, no-training legal assistance is "
        "incomparable. Undercut generic legal-tech subscriptions 30-60%."
    ),
)

NONPROFIT = EditionManifest(
    id="nonprofit",
    name="LEVI Commons",
    sector="charities, NGOs, community orgs",
    ring=Ring.CLOSED,
    tagline="The mission's team, at the mission's price.",
    description=(
        "For nonprofits and community organizations: outreach support, "
        "donor correspondence, grant-tracking assistance, volunteer "
        "coordination, and impact reporting. Appeal pricing — volume over "
        "margin — because the sector that gives the most should pay the "
        "least for leverage."
    ),
    roster=(
        RosterSlot(
            "Productivity",
            (),
            side="ai",
            count=2,
            purpose="grant tracking, operations support",
        ),
        RosterSlot(
            "Communication",
            (),
            side="either",
            count=1,
            purpose="outreach and donor correspondence drafts",
        ),
        RosterSlot(
            "Finance & Money",
            ("Charity Tithe Tracker", "Budget Nightly Tally"),
            side="ai",
            count=1,
            purpose="stewardship tracking",
        ),
        RosterSlot(
            "Social & Content",
            (),
            side="si",
            count=1,
            purpose="impact storytelling, creative outreach",
        ),
    ),
    ai_si_mix="Balanced Hybrid: AI for stewardship and procedure; SI for "
    "storytelling and creative outreach.",
    workflows=(
        "grant deadline tracking and application support",
        "donor correspondence drafts with review",
        "volunteer coordination support",
        "impact reporting from program data",
    ),
    data_posture=_dp(
        residency="org-local first",
        retention="donor-defined; purge on request",
        notes="Donor data is stewarded, never exploited. No training on "
        "donor or beneficiary data.",
    ),
    compliance=(
        "donor data minimization",
        "review gates on external communications",
        "transparent impact receipts",
    ),
    excluded=(
        ("donor-data exploitation or enrichment", "stewardship, not extraction"),
        (
            "manipulative fundraising automation",
            "the mission persuades honestly or not at all",
        ),
    ),
    tier_fit="2 to 4 — a 5-operator team template at appeal pricing",
    pricing_note=(
        "Deepest appeal pricing in the lineup: volume over margin, per the "
        "doctrine. The sector's goodwill is the marketing."
    ),
)

BUSINESS = EditionManifest(
    id="business",
    name="LEVI Enterprise",
    sector="companies, teams, founders",
    ring=Ring.CLOSED,
    tagline="The working edition — the whole office as a team.",
    description=(
        "The general business edition: operations, finance support, "
        "communications, security hygiene, and content workflows. The "
        "default institutional team — where most organizations land, and "
        "the edition the roster game was built around."
    ),
    roster=(
        RosterSlot(
            "Productivity",
            (),
            side="ai",
            count=2,
            purpose="operations, task and calendar workflows",
        ),
        RosterSlot(
            "Finance & Money",
            (),
            side="ai",
            count=1,
            purpose="bookkeeping support, spend awareness",
        ),
        RosterSlot(
            "Communication",
            (),
            side="either",
            count=1,
            purpose="internal and external correspondence",
        ),
        RosterSlot(
            "Security & Privacy",
            (),
            side="ai",
            count=1,
            purpose="security hygiene, access watch",
        ),
        RosterSlot(
            "Social & Content",
            (),
            side="si",
            count=1,
            purpose="content and brand workflows",
        ),
    ),
    ai_si_mix="Balanced Hybrid: the catch made concrete — AI runs the "
    "office, SI grows it.",
    workflows=(
        "operations and task workflows",
        "bookkeeping support and spend awareness",
        "correspondence drafting with review",
        "content production pipelines",
    ),
    data_posture=_dp(
        residency="org-local first; cloud only by choice",
        retention="org-defined",
        notes="Company data never trains shared models. Department "
        "separation available per deployment.",
    ),
    compliance=(
        "review gates on external communications",
        "audit receipts on financial workflows",
        "department data separation on request",
    ),
    excluded=(
        ("deceptive automation and dark patterns", "growth without deceit"),
        ("employee surveillance", "the team is assisted, not watched"),
    ),
    tier_fit="Pro — a 6-operator team template",
    pricing_note=(
        "The volume tier: 30-60% below comparable business AI suites. "
        "The roster game itself is the differentiator."
    ),
)

INDUSTRIAL = EditionManifest(
    id="industrial",
    name="LEVI Forge",
    sector="plants, field operations, logistics",
    ring=Ring.CLOSED,
    tagline="Fail-closed. Human hands on every lever.",
    description=(
        "For industrial and field operations: equipment monitoring support, "
        "maintenance scheduling, safety checklists, logistics awareness, and "
        "shift coordination. Fail-closed defaults everywhere; human "
        "in-the-loop on any physical-world action. The edition suggests, "
        "schedules, and records — it never operates machinery."
    ),
    roster=(
        RosterSlot(
            "System & Device Care",
            (),
            side="ai",
            count=2,
            purpose="monitoring support, maintenance scheduling",
        ),
        RosterSlot(
            "Smart Home & IoT",
            (),
            side="ai",
            count=2,
            purpose="sensor-awareness workflows, alert triage drafts",
        ),
        RosterSlot(
            "Security & Privacy",
            (),
            side="ai",
            count=1,
            purpose="operational security hygiene",
        ),
    ),
    ai_si_mix="AI-dominant: procedure, checklists, and fail-closed logic; "
    "SI bounded to scheduling creativity and anomaly curiosity.",
    workflows=(
        "maintenance scheduling from equipment signals",
        "safety checklist enforcement with sign-offs",
        "alert triage drafts for human operators",
        "shift coordination support",
    ),
    data_posture=_dp(
        residency="site-local; on-premise default",
        retention="operational; incident-bound extension",
        notes="Sensor data stays on site. Safety events are receipted "
        "immutably and never auto-resolved.",
    ),
    compliance=(
        "fail-closed defaults on every workflow",
        "HITL on any physical-world action",
        "safety events receipted immutably",
    ),
    excluded=(
        (
            "autonomous control of safety-critical systems",
            "the edition never operates machinery — human hands on levers",
        ),
        (
            "auto-resolution of safety events",
            "a flagged hazard stays flagged until a human clears it",
        ),
    ),
    tier_fit="Pro to Hybrid — a 5-operator team template",
    pricing_note=(
        "Premium industrial surface: fail-closed HITL automation with "
        "immutable safety receipts is incomparable. Price the guarantee."
    ),
)

OPEN_CREATIONAL = EditionManifest(
    id="open-creational",
    name="LEVI Open Creational",
    sector="everyone — outside minds, integrators, dreamers",
    ring=Ring.OPEN_CREATIONAL,
    tagline="The mold, not the cast. Run free.",
    description=(
        "The open-creational ring's edition: the manifest schema, the "
        "roster format, the ring policy, and an edition template — "
        "structure and architecture only. Outside minds author editions, "
        "propose rosters, build integrations, and send plans upstream. No "
        "agent implementations, no curated rosters, no sector workflows "
        "ship here. Bare minimal source; let them run free."
    ),
    roster=(),
    ai_si_mix="Unspecified — the community chooses its own mix.",
    workflows=(
        "author an edition against the open schema",
        "propose roster templates for community review",
        "build integrations against the roster format",
    ),
    data_posture=_dp(
        residency="wherever the community deploys",
        notes="The open ring carries no sector data and no implementations "
        "to leak it with.",
    ),
    compliance=(
        "editions proposed here must still name their refusals",
        "the safety boundary binds every ring: defensive only",
    ),
    excluded=(
        ("agent implementations", "structure only — the how stays in the closed ring"),
        (
            "curated sector rosters and workflows",
            "the cast is the dynasty's; the mold is everyone's",
        ),
        ("weights, prompts, crown jewels", "never leave, in any ring"),
    ),
    tier_fit="Entry and above — the on-ramp to the whole game",
    pricing_note=(
        "Free as in structure. The open ring is the top of the funnel: "
        "every outside edition that proves itself is a candidate for the "
        "closed catalog — and a future customer."
    ),
)

EDITIONS: Dict[str, EditionManifest] = {
    e.id: e
    for e in (
        EDUCATION,
        LAW_ENFORCEMENT,
        MILITARY,
        GOVERNMENT,
        HEALTHCARE,
        FIRST_RESPONDERS,
        LEGAL,
        NONPROFIT,
        BUSINESS,
        INDUSTRIAL,
        OPEN_CREATIONAL,
    )
}


def list_editions() -> List[EditionManifest]:
    return list(EDITIONS.values())


def get_edition(edition_id: str) -> EditionManifest:
    return EDITIONS[edition_id]


def editions_for_ring(ring: Ring) -> List[EditionManifest]:
    return [e for e in EDITIONS.values() if e.ring is ring]
