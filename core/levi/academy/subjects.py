"""Academy subject catalog — the curriculum beyond defensive analysis.

Twenty subjects, each blue-team framed, each mapped to a real
exercise runner (:mod:`levi.academy.session_exercises`). Entries are
shaped exactly like syllabus day entries — ``{title, objectives,
key_questions, exercise_type}`` — so they slot into the existing
syllabus/ladder/lesson machinery via :func:`as_track` and
:func:`merge_into` (which copies, never mutates, the syllabus).

The purple-team subject is authorization-gated: no named human
approver and explicit scope, no drill. Own systems only, always.

Provenance (remix law — studied, rebuilt natively, in our own words):

- Subjects 15–20 are organized against the NIST Cybersecurity Framework
  2.0 outcome functions — Govern (GV), Identify (ID), Protect (PR),
  Detect (DE), Respond (RS), Recover (RC) — and the Function →
  Category → Subcategory shape (ref: nist.gov/cyberframework, Feb 2024).
- Work-role framing follows the NICE Workforce Framework's task-statement
  logic (what a defender must be able to *do*, not just know).
- Every objective uses a measurable Bloom's-taxonomy (revised) verb —
  remember/define, understand/explain, apply/execute, analyze/deconstruct,
  evaluate/critique, create/design — so each one is assessable.

:func:`study_plan` wires the catalog to the methods: spaced-repetition
reviews per objective, an interleaved session mixing two subjects,
and a Feynman drill per objective.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from levi.academy import methods as _methods
from levi.academy.differentiators import _seal

TRACK_KEY = "D"
TRACK_NAME = "Fieldcraft & Canon"


def _subject(
    subject_id: str,
    title: str,
    description: str,
    objectives: List[str],
    key_questions: List[str],
    exercise_type: str,
    defense_note: str,
    requires_authorization: bool = False,
) -> Dict[str, Any]:
    assert len(objectives) == 3, "three objectives per subject"
    assert len(key_questions) == 3, "three key questions per subject"
    return {
        "id": subject_id,
        "title": title,
        "description": description,
        "objectives": list(objectives),
        "key_questions": list(key_questions),
        "exercise_type": exercise_type,
        "defense_note": defense_note,
        "requires_authorization": requires_authorization,
    }


SUBJECTS: List[Dict[str, Any]] = [
    _subject(
        "threat-intel",
        "Threat Intelligence for Defenders",
        "Turn threat intel into defensive action: collection, analysis, and dissemination that hardens the estate.",
        [
            "Distinguish strategic, operational, and tactical intel and say who consumes each",
            "Evaluate an intel report for actionability: what changes on receipt",
            "Write a defender's intel requirement that drives collection, not curiosity",
        ],
        [
            "What makes threat intel 'actionable' instead of interesting?",
            "How does the intel cycle differ for a defender versus an analyst-vendor?",
            "When is sharing intel with peers the defensive move?",
        ],
        "intel-brief",
        "Intel serves the defense: every report ends in a hardening action or it is trivia.",
    ),
    _subject(
        "osint-defense",
        "Defensive OSINT Tradecraft",
        "Open-source intelligence turned inward: find your own exposure before anyone else does.",
        [
            "Run an external footprint review of an organization using only public sources",
            "Distinguish exposure that is a finding from exposure that is noise",
            "Write a takedown/remediation request for exposed sensitive data",
        ],
        [
            "What can a stranger learn about us without touching our systems?",
            "Which exposures are actually exploitable, and which are just visible?",
            "Where is the line between defensive OSINT and intrusive collection?",
        ],
        "hunt-hypothesis",
        "Defensive OSINT looks outward only to protect inward — own footprint first, "
        "never target individuals, respect robots.txt and terms of service.",
    ),
    _subject(
        "forensics",
        "Digital Forensics Fundamentals",
        "Evidence-first investigation: preserve, acquire, analyze, report — in that order.",
        [
            "Explain the order of volatility and why it dictates collection order",
            "Preserve chain of custody from first touch to final report",
            "Reconstruct a timeline from mixed log sources without inventing gaps",
        ],
        [
            "Why does collection order matter more than collection speed?",
            "What breaks chain of custody, and how do you prove it held?",
            "How do you report what the timeline does NOT show?",
        ],
        "detection-sketch",
        "Forensics is for the defense and the record: preservation before analysis, "
        "always; findings stated with confidence levels, never asserted past the evidence.",
    ),
    _subject(
        "malware-triage",
        "Behavioral Malware Triage (Safe)",
        "Triage suspicious files by static indicators and behavioral reasoning — never by execution.",
        [
            "Extract static indicators (hashes, strings, imports, entropy) without executing the sample",
            "Reason about likely behavior from indicators: what would this do if run",
            "Write a triage verdict with confidence and next steps for the IR team",
        ],
        [
            "What can static analysis prove that dynamic analysis cannot — and vice versa?",
            "Why is 'just run it and see' never the triage move?",
            "What separates a confident verdict from a guess with indicators?",
        ],
        "triage",
        "SAFETY LAW: static analysis only. Never execute an untrusted sample; there is "
        "no sandbox here, so behavioral reasoning stays on paper. Handling live malware "
        "outside an isolated lab is forbidden.",
    ),
    _subject(
        "traffic-analysis",
        "Network Traffic Analysis",
        "Read the wire like a defender: baselines, anomalies, and the story packets tell.",
        [
            "Establish a traffic baseline and name what 'normal' looks like for a segment",
            "Spot beaconing, tunneling, and exfiltration patterns in flow data",
            "Correlate a network anomaly with endpoint and identity telemetry before calling it",
        ],
        [
            "What does normal look like here — and how do you know?",
            "Which is more suspicious: volume anomaly or timing anomaly?",
            "When does an anomaly become an incident?",
        ],
        "triage",
        "The wire is evidence, not accusation: correlate before escalating; every "
        "anomaly gets a benign hypothesis first.",
    ),
    _subject(
        "secure-code-review",
        "Secure Code Review",
        "Read code like an attacker thinks and a defender fixes: find the flaw, prescribe the fix.",
        [
            "Spot injection, auth, and crypto flaws in a review pass with a checklist",
            "Rank findings by exploitability and blast radius, not by cleverness",
            "Write a finding a developer can act on: location, impact, fix, verification",
        ],
        [
            "What makes a code finding actionable versus academic?",
            "How do you review for logic flaws checklists miss?",
            "When is 'this is fine' the correct review verdict?",
        ],
        "hardening-check",
        "Review to harden, not to shame: findings come with fixes and verification "
        "steps; severity follows exploitability, not drama.",
    ),
    _subject(
        "se-defense",
        "Social-Engineering Defense",
        "The human is the perimeter: recognize manipulation and build the culture that resists it.",
        [
            "Deconstruct a phishing lure: hook, pretext, urgency, and call to action",
            "Design a verification habit that survives urgency and authority pressure",
            "Run a blameless debrief after a click — the reporter is the hero",
        ],
        [
            "Why do smart people click? What does that tell you about 'awareness training'?",
            "What makes a verification habit actually used under pressure?",
            "How do you measure SE resilience without punishing reporters?",
        ],
        "comparison",
        "Defense, never deception practice on the unwilling: simulations are announced "
        "in policy, consented in employment terms, and always blameless. Never "
        "manipulative — the morals hold on every track.",
    ),
    _subject(
        "crypto-literacy",
        "Cryptography Literacy",
        "Enough cryptography to choose correctly and spot nonsense: primitives, modes, and failure patterns.",
        [
            "Match primitives to jobs: hashing vs encryption vs signatures vs KDFs",
            "Name the classic failure modes: ECB, hardcoded keys, homebrew crypto, RNG failures",
            "Evaluate a 'secure' claim: what is proven, what is asserted, what is missing",
        ],
        [
            "Why is 'military-grade encryption' a meaningless claim?",
            "What breaks first in real cryptosystems — the math or the plumbing?",
            "When is rolling your own crypto ever acceptable? (Never. Say why.)",
        ],
        "coverage-map",
        "Literacy, not implementation: use vetted libraries, never hand-rolled "
        "primitives; the academy's own sealing is documented construction, not a recommendation.",
    ),
    _subject(
        "cloud-posture",
        "Cloud Posture",
        "The cloud is someone else's computer with your misconfigurations: identity, storage, and logging done right.",
        [
            "Audit identity: least privilege, no long-lived keys where roles fit",
            "Lock down storage: public buckets, encryption, and access logging",
            "Verify the detective layer: CloudTrail-style logging on, alerting wired, tested",
        ],
        [
            "What is the cloud equivalent of 'the front door is open'?",
            "Why does identity become the perimeter in cloud?",
            "How do you prove logging would catch the thing you fear?",
        ],
        "hardening-check",
        "Harden the configuration, not the provider: misconfiguration is the "
        "vulnerability class; the fix is policy-as-code and verified defaults.",
    ),
    _subject(
        "privacy-engineering",
        "Privacy Engineering",
        "Build systems that don't need to be trusted with data they never collect.",
        [
            "Apply data minimization to a feature spec: what can we not collect",
            "Explain the difference between anonymization, pseudonymization, and wishful thinking",
            "Design a retention and deletion story a regulator — and a user — would believe",
        ],
        [
            "What is the cheapest data breach? (The data you never held.)",
            "Why does 'anonymized' so often mean 're-identifiable'?",
            "How do you prove deletion actually happened?",
        ],
        "comparison",
        "Privacy is a defensive discipline: minimize, then protect what remains. "
        "Local-first is the strongest privacy posture — the academy's own.",
    ),
    _subject(
        "purple-team",
        "Purple-Team vs Our Own Systems (Authorized)",
        "Adversarial testing against our own systems, with explicit authorization — the red lens serving the blue mission.",
        [
            "Scope an authorized test: systems, techniques, time window, and abort conditions",
            "Execute a controlled technique and capture defender-visible telemetry",
            "Write the purple report: what the blue team saw, missed, and must change",
        ],
        [
            "What separates authorized testing from an attack? (Paper, scope, and abort.)",
            "How do you test detection without breaking production?",
            "What does the blue team need most from a purple exercise?",
        ],
        "module-drill",
        "AUTHORIZATION LAW: a named human approver and explicit scope are required "
        "before any drill runs — own systems only, abort conditions written first. "
        "Defensive blue-team only; offensive material is never integrated.",
        requires_authorization=True,
    ),
    _subject(
        "incident-report",
        "Incident-Report Writing",
        "Write the report the incident deserves: timeline, impact, root cause, and remediation — no fog.",
        [
            "Build a minute-level timeline with sourced entries and marked gaps",
            "State impact honestly: confirmed, probable, and unknown — labeled",
            "Write remediation as verifiable actions with owners and dates",
        ],
        [
            "What does a good timeline prove that a narrative cannot?",
            "How do you report uncertainty without sounding uncertain?",
            "Who is the report for, and what decision must it enable?",
        ],
        "intel-brief",
        "The report serves the defense and the record: no blame, no fog, no "
        "invented precision. Unknowns are labeled, not hidden.",
    ),
    _subject(
        "stakeholder-briefing",
        "Briefing Non-Technical Stakeholders",
        "Translate security into decisions: risk in business language, options with trade-offs, a recommendation.",
        [
            "Convert a technical finding into a business-risk statement without jargon",
            "Present options with costs and trade-offs, then make a recommendation",
            "Handle the hard questions: 'are we safe?' answered honestly",
        ],
        [
            "What does the stakeholder need to decide — and what do they not need to know?",
            "How do you say 'we don't know' to an executive without losing trust?",
            "When is a one-page brief better than a twenty-slide deck?",
        ],
        "intel-brief",
        "Honesty scales up: never launder uncertainty into confidence for an "
        "audience that can't check your work. The morals hold in the boardroom.",
    ),
    _subject(
        "levi-canon",
        "LEVI Canon Operator Training",
        "Operate the organism: organs, the receipt doctrine, the money law, and the gates that never open.",
        [
            "Name the organs and their jobs: DemandPulse senses outward, Oracle weighs inward",
            "Apply the receipt doctrine: Plan → Preview → Permission → Execute → Verify → Receipt",
            "State the money law: Cybrus alone handles money; everything else fails closed",
        ],
        [
            "What does 'finish well = receipt' require of every consequential act?",
            "Why do minor actions run and major actions escalate — who decides?",
            "What never happens without Chauncey's explicit authorization?",
        ],
        "platform-teardown",
        "Canon is law, not lore: the operator enforces the gates — no push without "
        "authorization, no money outside Cybrus, no masks, LEVI in the spotlight.",
    ),
    # -- Reinforcement wave (2026-09-19): six blue-team subjects, researched
    # against NIST CSF 2.0's six outcome functions and the NICE workforce
    # task logic, objectives written with measurable Bloom verbs. Own words.
    _subject(
        "supply-chain-defense",
        "Supply-Chain Defense",
        "Your vendors are your attack surface: map supplier risk, demand evidence, and build so a compromised dependency can't become your breach.",
        [
            "Classify supplier risk: which vendors can reach your data, builds, or customers — and what breaks if each one turns hostile",
            "Evaluate a vendor's security evidence: questionnaire answers versus artifacts you can actually verify",
            "Design a dependency containment plan: pinned versions, verified artifacts, and blast-radius limits for a hostile update",
        ],
        [
            "Where does your trust in a supplier actually live — the contract, the artifact, or the habit?",
            "What is the difference between a vendor you trust and a vendor you can survive?",
            "How do you detect a compromised dependency before it executes?",
        ],
        "intel-brief",
        "Verify, then trust: the chain is guilty until the artifact proves "
        "innocent. Inventories exist for defense — know every dependency so a "
        "hostile update has nowhere to hide. (CSF: Govern/supply-chain risk, "
        "Identify/risk assessment.)",
    ),
    _subject(
        "insider-risk",
        "Insider-Risk Awareness",
        "The threat with a badge: recognize how legitimate access becomes a vector, and build controls that protect people and data without turning the workplace into a panopticon.",
        [
            "Distinguish malicious, compromised, and careless insider patterns — different causes, different controls",
            "Design least-privilege access reviews that catch drift without punishing legitimate work",
            "Explain a blameless offboarding and access-revocation workflow that holds up under real time pressure",
        ],
        [
            "Why do most insider incidents trace to access nobody reviewed rather than malice?",
            "How do you watch for insider risk without destroying the trust a team runs on?",
            "What happens to access in the first hour after someone leaves — and who owns it?",
        ],
        "comparison",
        "Defend people and data together: monitoring is consented, "
        "policy-backed, and minimal — never surveillance theater, never "
        "punishment dressed as security. (CSF: Protect/access control & "
        "awareness; NICE risk-assessment task logic.)",
    ),
    _subject(
        "incident-command",
        "Incident-Command Basics",
        "Chaos has an org chart: run an incident with clear roles, one decision-maker, and comms that don't make things worse.",
        [
            "Name the incident roles — commander, comms, scribe, technical lead — and state exactly what each one owns",
            "Execute a tabletop escalation: declare the incident, contain the comms blast radius, and keep a decision log",
            "Critique an incident timeline: find where command broke down and say what recovers it",
        ],
        [
            "Why does every incident need exactly one commander?",
            "What goes in the decision log that the chat thread doesn't capture?",
            "When does an event become an incident — and who gets to decide?",
        ],
        "tabletop",
        "Command serves the response: authority is for decisions, not blame. "
        "Drills run on our own systems, scheduled and blameless. "
        "(CSF: Respond/incident management & mitigation.)",
    ),
    _subject(
        "secure-baseline",
        "Secure-Baseline Engineering",
        "Defaults are destiny: define the hardened baseline every system starts from, and make drift visible the day it happens.",
        [
            "Define a secure baseline: the settings every host, image, and account starts with — and why each one is there",
            "Implement a drift check: compare a live system against baseline and report exactly what moved",
            "Assess an exception request: when a deviation from baseline is justified, and what compensates for it",
        ],
        [
            "Why do secure defaults beat secure instructions every time?",
            "What is the difference between a baseline and a wish list?",
            "How do you keep baselines current without breaking the fleet every Tuesday?",
        ],
        "hardening-check",
        "Harden your own estate: baselines are for our systems, never aimed "
        "outward. A deviation is a decision — written down, compensated, "
        "reviewed. (CSF: Protect/platform security.)",
    ),
    _subject(
        "threat-hunting",
        "Threat-Hunting Fundamentals",
        "Don't wait for the alert: form hypotheses about how an intruder would hide here, then go prove yourself wrong.",
        [
            "Formulate a hunt hypothesis from an intel report: the actor, the technique, and where it would show in our telemetry",
            "Execute a hypothesis-driven hunt across logs and endpoints, documenting every pivot win or lose",
            "Deconstruct a failed hunt: what the negative result still taught about our visibility gaps",
        ],
        [
            "What separates hunting from alert triage?",
            "How do you hunt with no intel feed — what do you hypothesize from?",
            "When do you stop a hunt — and what does 'done' mean when you found nothing?",
        ],
        "hunt-hypothesis",
        "Hunt your own estate with authorized access: hypotheses first, tools "
        "second. A negative result is still a result — it maps what you "
        "cannot see. (CSF: Detect/continuous monitoring & event analysis; "
        "NICE threat-analysis task logic.)",
    ),
    _subject(
        "recovery-drills",
        "Recovery & Continuity Drills",
        "Backups you never tested are rumors: prove you can rebuild, in order, under time pressure, before the incident does it for you.",
        [
            "Design a recovery order: what comes back first, what waits, and who decides",
            "Execute a restore drill against the clock and document everything that broke the plan",
            "Evaluate backup integrity: how you know the restore point isn't compromised too",
        ],
        [
            "What is the difference between having backups and being able to recover?",
            "How do you test recovery without risking production?",
            "Who declares 'we're back' — and what evidence backs the declaration?",
        ],
        "module-drill",
        "Recovery is defense completed: drills run on our own systems, "
        "scheduled, blameless — the plan is what gets graded, never the "
        "people. (CSF: Recover/plan execution & communication.)",
    ),
]

_SUBJECTS_BY_ID = {s["id"]: s for s in SUBJECTS}


def get_subject(subject_id: str) -> Dict[str, Any]:
    """Fetch one subject by id. Raises KeyError when unknown."""
    try:
        return _SUBJECTS_BY_ID[subject_id]
    except KeyError:
        raise KeyError(f"unknown subject {subject_id!r}") from None


def subject_ids() -> List[str]:
    return [s["id"] for s in SUBJECTS]


def syllabus_entries() -> List[Tuple[str, Dict[str, Any]]]:
    """(subject_id, day-entry) pairs shaped exactly like syllabus day entries."""
    return [
        (
            s["id"],
            {
                "title": s["title"],
                "objectives": list(s["objectives"]),
                "key_questions": list(s["key_questions"]),
                "exercise_type": s["exercise_type"],
            },
        )
        for s in SUBJECTS
    ]


def as_track() -> Dict[str, Any]:
    """The catalog as a syllabus track, ready to merge."""
    return {
        "name": TRACK_NAME,
        "days": {str(i + 1): entry for i, (_, entry) in enumerate(syllabus_entries())},
    }


def merge_into(syllabus: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of ``syllabus`` with this catalog merged as a new track.

    Copies, never mutates — the caller's syllabus dict is untouched.
    Raises ValueError if the track key is already taken.
    """
    merged = copy.deepcopy(syllabus)
    tracks = merged.setdefault("tracks", {})
    if TRACK_KEY in tracks:
        raise ValueError(
            f"syllabus already has track {TRACK_KEY!r} — refusing to overwrite"
        )
    tracks[TRACK_KEY] = as_track()
    names = merged.setdefault("track_names", {})
    names[TRACK_KEY] = TRACK_NAME
    return merged


# ---------------------------------------------------------------------------
# Purple-team authorization gate
# ---------------------------------------------------------------------------


def _auth_dir(home: Optional[Path] = None) -> Path:
    base = os.environ.get("LEVI_HOME") or str(Path.home() / ".levi")
    d = (
        (Path(home) if home is not None else Path(base).expanduser())
        / "academy"
        / "purple_auth"
    )
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def _write_json(path: Path, record: Dict[str, Any]) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _utcnow(now: Optional[float] = None) -> str:
    ts = now if now is not None else time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def authorize_purple_team(
    learner_id: str,
    scope: str,
    approver: str,
    home: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Record a named human approver's authorization for purple-team drills.

    ``scope`` names the systems, techniques, time window, and abort
    conditions. The record is Veil-sealed — tamper-evident.
    """
    if not learner_id or not learner_id.strip():
        raise ValueError("learner_id must be non-empty")
    if not scope or not scope.strip():
        raise ValueError(
            "scope must be non-empty — systems, techniques, window, abort conditions"
        )
    if not approver or not approver.strip():
        raise ValueError("approver must be non-empty — a named human, not a role")
    auth_id = uuid.uuid4().hex[:12]
    payload = {
        "auth_id": auth_id,
        "learner_id": learner_id,
        "scope": scope.strip(),
        "approver": approver.strip(),
        "authorized_at": _utcnow(now),
    }
    context = f"purple-auth:{learner_id}:{auth_id}"
    envelope = _seal.seal_dict(payload, context, home)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in learner_id)
    _write_json(
        _auth_dir(home) / f"{safe}.json",
        {"payload": payload, "envelope": envelope, "context": context},
    )
    return {
        "auth_id": auth_id,
        "learner_id": learner_id,
        "approver": approver.strip(),
        "authorized": True,
    }


def check_purple_authorization(
    learner_id: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Verify purple-team authorization. Raises PermissionError when absent.

    A tampered authorization record fails loudly (SealError) rather than
    passing quietly.
    """
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in learner_id)
    path = _auth_dir(home) / f"{safe}.json"
    if not path.exists():
        raise PermissionError(
            f"no purple-team authorization for learner {learner_id!r} — "
            "a named human approver must authorize scope first"
        )
    record = json.loads(path.read_text(encoding="utf-8"))
    payload = _seal.open_dict(record["envelope"], record["context"], home)
    if payload != record["payload"]:
        raise _seal.SealError("purple-team authorization payload mismatch — tampered")
    return payload


# ---------------------------------------------------------------------------
# Study plans — subjects wired to methods
# ---------------------------------------------------------------------------


def study_plan(
    learner_id: str,
    subject_id: str,
    mix_with: Optional[str] = None,
    home: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Build a method-driven study plan for a subject.

    - spaced-repetition reviews, one per objective (skills are
      ``<subject_id>:objective-<i>``), layered on the decay model;
    - one interleaved session mixing this subject's objectives with
      another subject's (no blocked chapters);
    - one Feynman drill per objective (teach it back).
    """
    subject = get_subject(subject_id)
    if mix_with is None:
        others = [s["id"] for s in SUBJECTS if s["id"] != subject_id]
        mix_with = others[0]
    partner = get_subject(mix_with)
    if subject["requires_authorization"]:
        check_purple_authorization(learner_id, home)
    reviews = [
        _methods.next_review(
            learner_id, f"{subject_id}:objective-{i}", home=home, now=now
        )
        for i in range(len(subject["objectives"]))
    ]
    session = _methods.interleave(
        [
            {"subject_id": subject_id, "items": list(subject["objectives"])},
            {"subject_id": partner["id"], "items": list(partner["objectives"])},
        ],
        per_subject=3,
    )
    drills = [
        _methods.feynman_drill(obj, [obj, subject["title"]])
        for obj in subject["objectives"]
    ]
    return {
        "learner_id": learner_id,
        "subject_id": subject_id,
        "mixed_with": partner["id"],
        "reviews": reviews,
        "interleaved_session": session,
        "feynman_drills": drills,
        "exercise_type": subject["exercise_type"],
    }
