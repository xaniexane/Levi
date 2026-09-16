"""LEVI academy skill pack for the 30-day 24/7 program.

Read-only, INFO-risk skills the agent can use:

- ``academy_detection_advisor`` — detection-engineering plans (defensive)
- ``academy_hunt_hypothesis`` — falsifiable hunt hypotheses (defensive)
- ``academy_hardening_check`` — hardening verification (defensive)
- ``academy_session_brief`` — syllabus outline + taught lesson for a day/block
- ``academy_status_brief`` — program progress summary
- ``academy_teardown_brief`` — platform teardown template (adopt/adapt/differ)

``ACADEMY_SKILLS`` is registered in ``levi.skill.registry.SkillRegistry``.
All handlers are pure functions of their inputs — no network, no system
changes, no offensive content. Track A content stays defensive-only.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from levi.skill.registry import Skill, SkillRisk

ACADEMY_DIR = Path(__file__).resolve().parent.parent / "academy"


def _data_dir() -> Path:
    return Path(os.environ.get("LEVI_ACADEMY_DIR", Path.home() / ".levi" / "academy"))


def _syllabus() -> dict:
    return json.loads((ACADEMY_DIR / "syllabus.json").read_text(encoding="utf-8"))


def _detection_advisor(args: Dict[str, Any] | None = None) -> str:
    args = args or {}
    behavior = (args.get("behavior") or "suspicious process execution").strip()
    logsource = (args.get("logsource") or "process_creation (windows)").strip()
    plan = {
        "behavior": behavior,
        "method": "detection-engineering lifecycle: idea -> prototype on "
        "historical data -> tune against normal traffic -> "
        "experimental -> stable -> maintain",
        "log_source_first": logsource,
        "sigma_sketch_shape": {
            "title": f"Detect {behavior}",
            "status": "experimental",
            "logsource": logsource,
            "detection": {
                "selection": "<field conditions matching the behavior>",
                "filter_known_good": "<explicit exclusions: admin tools, deploy systems>",
                "condition": "selection and not filter_known_good",
            },
            "falsepositives": ["<name what else triggers this before deploying>"],
            "level": "high (set after tuning)",
        },
        "tuning": [
            "baseline normal in this environment first",
            "aggregate: single events vs bursts",
            "track precision per rule; retire what degrades",
        ],
        "coverage": "tag the rule with the ATT&CK technique it covers",
    }
    return json.dumps(plan, indent=2)


def _hunt_hypothesis(args: Dict[str, Any] | None = None) -> str:
    args = args or {}
    topic = (args.get("topic") or "lateral movement").strip()
    location = (args.get("location") or "server subnet").strip()
    hypothesis = {
        "title": f"Hunt: {topic}",
        "hypothesis": (
            f"An adversary may be conducting {topic} in {location}, "
            "which would leave identifiable traces in the telemetry "
            "listed below."
        ),
        "able": {
            "actor": args.get("actor") or "intruder with valid credentials",
            "behavior": topic,
            "location": location,
            "evidence": args.get("evidence")
            or "authentication + process telemetry for the behavior",
        },
        "loop": [
            "prepare (hypothesis + ABLE + data check)",
            "execute (start broad, narrow iteratively, timebox)",
            "validate (corroborate with a second source)",
            "act (escalate / document baseline / write detection)",
            "document (queries, findings, conclusion)",
        ],
        "rule": "no evidence available -> not a hunt, a research project",
    }
    return json.dumps(hypothesis, indent=2)


def _hardening_check(args: Dict[str, Any] | None = None) -> str:
    args = args or {}
    items = args.get("checklist") or [
        "unneeded services disabled",
        "MFA enforced for remote access",
        "script execution constrained",
        "centralized logging with retention",
        "unique local admin credentials per host",
    ]
    report = {
        "method": "baseline verification: adopt a baseline, adapt with "
        "documented exceptions, verify continuously — hardening decays",
        "layers": [
            "remove what is not needed",
            "restrict the rest to least privilege",
            "enable protective controls (logging, MFA, execution control)",
        ],
        "checklist": [
            {
                "check": c,
                "verdict": "UNASSESSED",
                "note": "verify against live configuration",
            }
            for c in items
        ],
        "drift_rule": "any deviation from baseline is a finding until "
        "documented as an exception",
    }
    return json.dumps(report, indent=2)


def _session_brief(args: Dict[str, Any] | None = None) -> str:
    args = args or {}
    try:
        day = int(args.get("day", 1))
        block = int(args.get("block", 1))
    except (TypeError, ValueError):
        return "academy_session_brief: day and block must be integers."
    if not (1 <= day <= 30 and 1 <= block <= 4):
        return "academy_session_brief: day 1-30, block 1-4."
    syl = _syllabus()
    track = syl["block_map"][str(block)]
    entry = syl["tracks"][track]["days"][str(day)]
    brief = {
        "day": day,
        "block": block,
        "track": track,
        "track_name": syl["track_names"][track],
        "boundary": syl["track_boundaries"][track],
        "title": entry["title"],
        "objectives": entry["objectives"],
        "key_questions": entry["key_questions"],
        "exercise_type": entry["exercise_type"],
    }
    lesson_path = _data_dir() / "lessons" / f"d{day}b{block}.md"
    if lesson_path.exists():
        brief["taught_lesson"] = lesson_path.read_text(
            encoding="utf-8", errors="replace"
        )
    else:
        brief["taught_lesson"] = None
        brief["note"] = "Session not yet taught; lesson is synthesized at session time."
    return json.dumps(brief, indent=2, ensure_ascii=False)


def _status_brief(_: Dict[str, Any] | None = None) -> str:
    path = _data_dir() / "progress.json"
    if not path.exists():
        return json.dumps(
            {
                "program": "LEVI Boot Camp 30-day",
                "status": "not started",
                "sessions_completed": 0,
            }
        )
    prog = json.loads(path.read_text(encoding="utf-8"))
    done = prog.get("completed", [])
    per_track = {"A": 0, "B": 0, "C": 0, "S": 0}
    for sid in done:
        try:
            n = (int(sid[1:].split("b")[0]) - 1) * 4 + int(sid.split("b")[1])
            per_track[{1: "A", 2: "B", 3: "C", 0: "S"}[n % 4]] += 1
        except Exception:
            continue
    return json.dumps(
        {
            "program": "LEVI Boot Camp 30-day 24/7",
            "sessions_completed": len(done),
            "sessions_total": 120,
            "day": min(len(done) // 4 + 1, 30),
            "per_track": per_track,
            "graduated": prog.get("graduated", False),
        },
        indent=2,
    )


def _teardown_brief(args: Dict[str, Any] | None = None) -> str:
    args = args or {}
    platform = (args.get("platform") or "the platform under study").strip()
    return json.dumps(
        {
            "platform": platform,
            "template": {
                "pattern": "the core loop: what the platform does, for whom, repeatedly",
                "mechanics": "how it operates: interaction model, capability pattern, data flow",
                "performance": "how it performs: speed to value, trust kept, failure cost",
                "adopt": "take directly — proven patterns worth copying",
                "adapt": "reshape for LEVI: local-first, stdlib-only, free core",
                "differ": "deliberately diverge where platforms manipulate or centralize — with reasons",
            },
            "rule": "public sources only; original synthesis, never copied text",
        },
        indent=2,
    )


def _build() -> List[Skill]:
    return [
        Skill(
            id="academy_detection_advisor",
            name="Detection Engineering Advisor",
            description="Drafts a detection-engineering plan for a behavior: "
            "lifecycle, log source, Sigma sketch shape, tuning.",
            category="academy",
            risk_level=SkillRisk.INFO,
            tags=["detection-engineering", "sigma", "defensive"],
            handler=_detection_advisor,
        ),
        Skill(
            id="academy_hunt_hypothesis",
            name="Hunt Hypothesis Generator",
            description="Builds a structured, falsifiable hunt hypothesis in "
            "ABLE format with the hunt loop.",
            category="academy",
            risk_level=SkillRisk.INFO,
            tags=["threat-hunting", "hypothesis", "defensive"],
            handler=_hunt_hypothesis,
        ),
        Skill(
            id="academy_hardening_check",
            name="Hardening Verification Checker",
            description="Verifies a hardening checklist against baseline "
            "layers; treats drift as findings.",
            category="academy",
            risk_level=SkillRisk.INFO,
            tags=["hardening", "baseline", "defensive"],
            handler=_hardening_check,
        ),
        Skill(
            id="academy_session_brief",
            name="Academy Session Brief",
            description="Syllabus outline plus taught lesson for any academy "
            "day/block (args: day 1-30, block 1-4).",
            category="academy",
            risk_level=SkillRisk.INFO,
            tags=["curriculum", "training"],
            handler=_session_brief,
        ),
        Skill(
            id="academy_status_brief",
            name="Academy Status Brief",
            description="Program progress: sessions completed, per-track "
            "counts, current day, graduation state.",
            category="academy",
            risk_level=SkillRisk.INFO,
            tags=["curriculum", "training", "status"],
            handler=_status_brief,
        ),
        Skill(
            id="academy_teardown_brief",
            name="Platform Teardown Template",
            description="Adopt/adapt/differ teardown template for platform "
            "intelligence work (arg: platform).",
            category="academy",
            risk_level=SkillRisk.INFO,
            tags=["platform-intelligence", "teardown"],
            handler=_teardown_brief,
        ),
    ]


ACADEMY_SKILLS: List[Skill] = _build()
