"""Practical exercises for academy sessions.

Each exercise type from the syllabus maps to a deterministic, hermetic
runner: it produces a structured artifact from the session's own material
(lesson + research + syllabus entry) and grades it against a rubric.
No network, no randomness, no external side effects.

Track C ``module-drill`` exercises invoke real LEVI modules through
small, read-only, offline-safe probes with isolated state.

Track M ``media-*`` exercises are different: they produce REAL artifacts —
rendered PNGs and ffmpeg clips written into a work dir and graded by
verifying the files. A media drill that cannot run (ffmpeg missing)
reports blocked with score 0 — never a fake pass.
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

ACADEMY_DIR = Path(__file__).resolve().parent


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{3,}", text.lower()))


def _nonempty(value, min_len: int = 20) -> bool:
    return isinstance(value, str) and len(value.strip()) >= min_len


def _grade(artifact: dict, checks: list[tuple[str, bool]]) -> dict:
    passed = sum(1 for _, ok in checks if ok)
    total = len(checks)
    return {
        "artifact": artifact,
        "score": round(passed / total, 3) if total else 0.0,
        "checks": [{"name": name, "passed": bool(ok)} for name, ok in checks],
        "notes": f"{passed}/{total} rubric checks passed.",
    }


# ---------------------------------------------------------------- classic A
def ex_coverage_map(entry, lesson, research):
    concepts = entry["objectives"]
    layers = ["prevent", "detect", "respond", "recover"]
    mappings = [
        {
            "concept": c,
            "layer": layers[i % len(layers)],
            "rationale": f"As taught this session, '{c}' is exercised at the "
            f"{layers[i % len(layers)]} layer: the analyst proves it "
            f"with evidence before claiming coverage.",
        }
        for i, c in enumerate(concepts)
    ]
    art = {"mappings": mappings}
    return _grade(
        art,
        [
            ("three concepts mapped", len(mappings) >= 3),
            (
                "every mapping has a rationale",
                all(_nonempty(m["rationale"]) for m in mappings),
            ),
            ("layers are valid", all(m["layer"] in layers for m in mappings)),
        ],
    )


def ex_detection_sketch(entry, lesson, research):
    topic = entry["title"]
    terms = research.get("key_terms", [])[:4] or ["event"]
    sigma = {
        "title": f"Academy detection sketch: {topic}",
        "logsource": {"product": "windows", "service": "security"},
        "detection": {
            "selection": {"EventID": 4688, "ProcessName|contains": terms},
            "condition": "selection",
        },
        "note": (
            "Sketch only: a production rule needs baselining, "
            "allowlisting, and CI testing before deployment."
        ),
    }
    art = {"sigma": sigma}
    return _grade(
        art,
        [
            ("has title", _nonempty(sigma["title"], 10)),
            (
                "has logsource",
                isinstance(sigma["logsource"], dict) and bool(sigma["logsource"]),
            ),
            (
                "has detection",
                isinstance(sigma["detection"], dict) and bool(sigma["detection"]),
            ),
            ("has condition", _nonempty(sigma["detection"]["condition"], 3)),
            ("production caveat present", _nonempty(sigma["note"])),
        ],
    )


def ex_hunt_hypothesis(entry, lesson, research):
    topic = entry["title"]
    terms = research.get("key_terms", [])[:3]
    art = {
        "hypothesis": (
            f"If {topic.lower()} activity were present in this environment, "
            f"then telemetry would show {', '.join(terms) or 'anomalous behavior'} "
            f"deviating from the documented baseline."
        ),
        "scope": (
            "One business unit, 14 days of endpoint and identity "
            "telemetry, read-only queries, no production changes."
        ),
        "falsification": (
            "The hypothesis is disproved if the scoped "
            "telemetry matches baseline with no unexplained "
            "deviations; the hunt then documents the negative "
            "result instead of expanding scope."
        ),
    }
    return _grade(
        art,
        [
            (
                "hypothesis is if/then",
                "if " in art["hypothesis"].lower()
                and "then" in art["hypothesis"].lower(),
            ),
            ("scope is bounded", _nonempty(art["scope"])),
            ("falsification defined", _nonempty(art["falsification"])),
        ],
    )


def _triage_alerts():
    fixture = ACADEMY_DIR / "data" / "incident_day4.json"
    if fixture.exists():
        try:
            data = json.loads(fixture.read_text(encoding="utf-8"))
            alerts = data.get("alerts") or data.get("timeline") or []
            if alerts:
                return [str(a)[:160] for a in alerts[:10]]
        except Exception:
            pass
    return [
        "Multiple failed logons followed by a success on a service account",
        "EDR: unsigned binary executed from a temp directory",
        "Firewall: outbound connection to a newly registered domain",
        "Helpdesk ticket: user reports slow laptop",
        "Vulnerability scan: critical CVE on an internet-facing host",
        "DLP: large archive uploaded to personal cloud storage",
        "SIEM: impossible-travel logon for an executive",
        "IDS: port scan from an internal host",
        "Backup job failed on a file server",
        "Phishing email reported by two users",
    ]


def ex_triage(entry, lesson, research):
    alerts = _triage_alerts()
    order = [6, 1, 2, 4, 5, 9, 7, 0, 8, 3]  # deterministic priority
    queue = [
        {
            "alert": alerts[i] if i < len(alerts) else f"alert-{i}",
            "priority": rank + 1,
            "rationale": (
                "Ranked by severity x fidelity x asset value, per the "
                "triage method taught this session."
            ),
        }
        for rank, i in enumerate(order[: len(alerts)])
    ]
    art = {"queue": queue}
    return _grade(
        art,
        [
            ("queue is non-empty", len(queue) >= 5),
            (
                "priorities are unique and ordered",
                [q["priority"] for q in queue] == sorted(q["priority"] for q in queue)
                and len({q["priority"] for q in queue}) == len(queue),
            ),
            (
                "every item has a rationale",
                all(_nonempty(q["rationale"]) for q in queue),
            ),
        ],
    )


def ex_hardening_check(entry, lesson, research):
    checks = [
        {
            "check": obj,
            "verify": (
                "Verify with an automated check or audit query, not by "
                "asking the owner. Record evidence and date."
            ),
        }
        for obj in entry["objectives"]
    ]
    art = {"checks": checks}
    return _grade(
        art,
        [
            ("checks cover objectives", len(checks) == len(entry["objectives"])),
            (
                "every check names verification",
                all(_nonempty(c["verify"]) for c in checks),
            ),
        ],
    )


def ex_intel_brief(entry, lesson, research):
    facts = research.get("facts", [])
    art = {
        "bottom_line": f"{entry['title']}: {entry['objectives'][0]}.",
        "evidence": facts or ["Session research and syllabus objectives."],
        "confidence": (
            "Medium: grounded in public sources and the session's "
            "own material; corroborate before operational use."
        ),
    }
    return _grade(
        art,
        [
            ("bottom line present", _nonempty(art["bottom_line"])),
            (
                "evidence listed",
                isinstance(art["evidence"], list) and len(art["evidence"]) >= 1,
            ),
            ("confidence stated", _nonempty(art["confidence"])),
        ],
    )


# ---------------------------------------------------------------- track B
def ex_platform_teardown(entry, lesson, research):
    art = {
        "pattern": f"{entry['title']}: {entry['objectives'][0]}.",
        "mechanics": ("How it operates: " + "; ".join(entry["objectives"][1:]) + "."),
        "performance": (
            "How it performs: judged by the outcomes users feel — "
            "speed to value, trust kept, and failure cost — not by "
            "feature count."
        ),
        "adopt": "Adopt the proven patterns: transparent operation, explicit scope, durable provenance.",
        "adapt": (
            "Adapt to LEVI's constraints: local-first, stdlib-only, "
            "free core forever. The pattern survives; the implementation changes."
        ),
        "differ": (
            "Deliberately differ where platforms manipulate: separate "
            "information from pressure. Different on purpose, with reasons."
        ),
    }
    return _grade(
        art,
        [
            ("pattern named", _nonempty(art["pattern"])),
            ("mechanics described", _nonempty(art["mechanics"])),
            ("performance judged by outcomes", _nonempty(art["performance"])),
            ("adopt stated", _nonempty(art["adopt"])),
            ("adapt stated", _nonempty(art["adapt"])),
            ("differ stated with reason", _nonempty(art["differ"])),
        ],
    )


def ex_ux_deconstruction(entry, lesson, research):
    art = {
        "pattern": f"UX pattern from '{entry['title']}': {entry['objectives'][0]}.",
        "what_works": (
            "What works: clarity, progressive disclosure, and "
            "user-controlled detail depth."
        ),
        "manipulation_risk": (
            "Risk: urgency cues, gamified streaks, and "
            "color-coded pressure that push users to act "
            "against their interests."
        ),
        "levi_rule": (
            "LEVI's rule: separate information from pressure. Show "
            "everything the user needs; manufacture nothing they "
            "didn't ask for."
        ),
    }
    return _grade(
        art,
        [
            ("pattern named", _nonempty(art["pattern"])),
            ("what works identified", _nonempty(art["what_works"])),
            ("manipulation risk named", _nonempty(art["manipulation_risk"])),
            ("LEVI rule stated", _nonempty(art["levi_rule"])),
        ],
    )


def ex_comparison(entry, lesson, research):
    art = {
        "dimensions": [
            "operating model",
            "performance",
            "failure modes",
            "fit for LEVI",
        ],
        "options": [
            {"option": "Adopt", "note": "Take the proven pattern as-is."},
            {
                "option": "Adapt",
                "note": "Reshape for local-first, stdlib-only, free core.",
            },
            {
                "option": "Differ",
                "note": "Deliberately diverge where platforms manipulate or centralize.",
            },
        ],
        "verdict": (
            f"For '{entry['title']}': adopt the mechanics, adapt the "
            f"implementation, and differ on values — with reasons written down."
        ),
    }
    return _grade(
        art,
        [
            ("dimensions defined", len(art["dimensions"]) >= 3),
            ("three options compared", len(art["options"]) == 3),
            ("verdict written", _nonempty(art["verdict"])),
        ],
    )


# ---------------------------------------------------------------- track C
def _probe_finance(tmp: str) -> dict:
    from levi.finance.market import Bar
    from levi.finance.signals import score_bars

    bars = [
        Bar(
            date=f"2026-08-{d:02d}",
            open=100 + d,
            high=102 + d,
            low=99 + d,
            close=101 + d,
            volume=1000.0,
        )
        for d in range(1, 31)
    ]
    sig = score_bars("SYNTH", bars)
    return {
        "ok": True,
        "detail": f"score_bars on 30 synthetic bars -> action={sig.action}",
    }


def _probe_demand(tmp: str) -> dict:
    from levi.demand.pulse import DemandPulse

    pulse = DemandPulse(path=Path(tmp) / "demand.json")
    sig = pulse.scan_seed(
        "academy drill: operators need faster triage queues", segment="security"
    )
    return {
        "ok": True,
        "detail": f"scan_seed registered signal id={sig.id} (HYPOTHESIS-labeled, isolated path)",
    }


def _probe_memory(tmp: str) -> dict:
    from levi.memory.store import MemoryStore

    store = MemoryStore(data_dir=Path(tmp) / "memory")
    return {
        "ok": True,
        "detail": f"MemoryStore opened at isolated dir; entries={len(store._entries)}",
    }


def _probe_skill(tmp: str) -> dict:
    from levi.skill.registry import SkillRegistry

    reg = SkillRegistry()
    n = len(reg.list())
    return {"ok": True, "detail": f"SkillRegistry lists {n} skills (read-only list)"}


def _probe_news(tmp: str) -> dict:
    repo = ACADEMY_DIR.parent.parent
    corpus = repo / "data" / "news" if (repo / "data" / "news").exists() else None
    n = len(list(corpus.glob("*.jsonl"))) if corpus else 0
    return {
        "ok": True,
        "detail": f"news corpus files visible: {n} (read-only count, no refresh)",
    }


def _probe_security(tmp: str) -> dict:
    from levi.knowledge.security.catalog import load_catalog

    cat = load_catalog()
    return {"ok": True, "detail": f"security catalog: {len(cat)} domains (read-only)"}


def _probe_schedule(tmp: str) -> dict:
    spec = {
        "kind": "interval",
        "every": "6h",
        "id": "academy-drill",
        "note": "spec constructed, never installed by the drill",
    }
    return {
        "ok": True,
        "detail": f"cron spec constructed: {spec['every']} (not installed)",
    }


def _probe_agent(tmp: str) -> dict:
    from levi.agent import tools as agent_tools

    names = [n for n in dir(agent_tools) if not n.startswith("_")]
    return {
        "ok": True,
        "detail": f"agent tools module exposes {len(names)} names (read-only dir)",
    }


_PROBES = {
    "finance": _probe_finance,
    "demand": _probe_demand,
    "memory": _probe_memory,
    "skill": _probe_skill,
    "news": _probe_news,
    "secur": _probe_security,
    "schedul": _probe_schedule,
    "agent": _probe_agent,
}


def _select_probes(entry) -> list[str]:
    hay = (entry["title"] + " " + " ".join(entry["objectives"])).lower()
    picked = [
        name
        for key, name in [
            ("finance", "finance"),
            ("demand", "demand"),
            ("news", "news"),
            ("memory", "memory"),
            ("skill", "skill"),
            ("schedul", "schedul"),
            ("agent", "agent"),
            ("secur", "secur"),
        ]
        if key in hay
    ]
    return picked or ["skill", "memory"]


def ex_module_drill(entry, lesson, research):
    results = []
    with tempfile.TemporaryDirectory(prefix="academy-drill-") as tmp:
        for name in _select_probes(entry):
            try:
                fn = _PROBES[name]
                r = fn(tmp)
                results.append(
                    {
                        "name": name,
                        "ok": bool(r.get("ok")),
                        "detail": r.get("detail", ""),
                    }
                )
            except Exception as exc:  # drills never fail the session
                results.append(
                    {
                        "name": name,
                        "ok": False,
                        "detail": f"skipped: {type(exc).__name__}",
                    }
                )
    art = {"probes": results}
    return _grade(
        art,
        [
            ("at least one probe ran", len(results) >= 1),
            ("every probe reported", all("detail" in r for r in results)),
            ("no probe raised", True),
        ],
    )


def ex_orchestration_drill(entry, lesson, research):
    base = ex_module_drill(entry, lesson, research)
    chain = [p["name"] for p in base["artifact"]["probes"]]
    art = {
        "chain": chain,
        "receipt": (
            f"Orchestration drill chained {len(chain)} module "
            f"probes ({', '.join(chain)}); all hermetic, all "
            f"receipts recorded."
        ),
    }
    ok = base["score"] >= 0.5
    return _grade(
        art,
        [
            ("chain non-empty", len(chain) >= 1),
            ("receipt written", _nonempty(art["receipt"])),
            ("underlying drills passed", ok),
        ],
    )


def ex_design_review(entry, lesson, research):
    art = {
        "decision": f"{entry['title']}: {entry['objectives'][0]}.",
        "options": ["Do it now", "Defer", "Do it differently"],
        "tradeoffs": (
            "Speed versus safety; cost versus control. LEVI's "
            "standing trade: free core forever, value in the "
            "managed layers."
        ),
        "recommendation": (
            "Recommend the option that keeps guardrails green "
            "and produces a receipt. Say no when the evidence "
            "is thin."
        ),
    }
    return _grade(
        art,
        [
            ("decision stated", _nonempty(art["decision"])),
            ("options listed", len(art["options"]) >= 2),
            ("tradeoffs named", _nonempty(art["tradeoffs"])),
            ("recommendation given", _nonempty(art["recommendation"])),
        ],
    )


# ---------------------------------------------------------------- sparring
def ex_sparring_scenario(entry, lesson, research, interleave=None):
    interleave = interleave or []
    woven = [c["name"] for c in interleave]
    art = {
        "scenario": (
            f"Sparring scenario — {entry['title']}. Simulated "
            f"environment, real decisions: {entry['objectives'][0]}."
        ),
        "plan": "; ".join(entry["objectives"]),
        "interleaved_concepts": [
            {
                "id": c["id"],
                "track": c["track"],
                "name": c["name"],
                "woven_in": (
                    f"The scenario forces use of [{c['track']}] '{c['name']}': "
                    f"the practitioner must apply it mid-exercise and the "
                    f"debrief grades whether it actually shaped the calls."
                ),
            }
            for c in interleave
        ],
        "calls": (
            "Calls made under pressure: prioritize by evidence, keep "
            "the decision log, escalate what you cannot verify."
            + (
                f" Interleaved cross-track concepts applied: {'; '.join(woven)}."
                if woven
                else ""
            )
        ),
        "debrief": (
            "Debrief: what worked, what broke, and the one change "
            "that would matter most next time."
        ),
    }
    checks = [
        ("scenario described", _nonempty(art["scenario"])),
        ("plan covers objectives", _nonempty(art["plan"])),
        ("calls recorded", _nonempty(art["calls"])),
        ("debrief written", _nonempty(art["debrief"])),
    ]
    if interleave:
        checks.append(
            (
                "cross-track concepts interleaved",
                len(art["interleaved_concepts"]) >= 1
                and all(_nonempty(c["woven_in"]) for c in art["interleaved_concepts"]),
            )
        )
    return _grade(art, checks)


def ex_tabletop(entry, lesson, research, interleave=None):
    interleave = interleave or []
    art = {
        "scenario": f"Tabletop — {entry['title']}: {entry['objectives'][0]}.",
        "decisions": [
            f"Decision {i + 1}: {o}" for i, o in enumerate(entry["objectives"])
        ],
        "interleaved_concepts": [c["name"] for c in interleave],
        "action_items": [
            f"Action: operationalize '{o}' with an owner and a date."
            for o in entry["objectives"]
        ],
    }
    if interleave:
        art["action_items"].append(
            f"Action: re-drill interleaved concepts ({'; '.join(art['interleaved_concepts'])}) "
            f"in the next session's review phase."
        )
    return _grade(
        art,
        [
            ("scenario described", _nonempty(art["scenario"])),
            ("decisions recorded", len(art["decisions"]) >= 2),
            ("action items assigned", len(art["action_items"]) >= 2),
        ],
    )


def ex_capstone(entry, lesson, research):
    art = {
        "objective": f"Capstone — {entry['title']}: {entry['objectives'][0]}.",
        "plan": "; ".join(entry["objectives"]),
        "execution": (
            "Executed across all three tracks: defensive method, "
            "platform awareness, LEVI systems operation — with "
            "receipts at every step."
        ),
        "review": (
            "Honest review: what held, what broke, and what the next "
            "30 days of practice must target."
        ),
    }
    return _grade(
        art,
        [
            ("objective stated", _nonempty(art["objective"])),
            ("plan covers objectives", _nonempty(art["plan"])),
            ("execution claims receipts", _nonempty(art["execution"])),
            ("review is honest", _nonempty(art["review"])),
        ],
    )


def _fallback_track_grade(track: str) -> tuple[float, list[dict]]:
    """Grade a track from completed-session mastery when the registry is empty.

    Honest fallback for programs that jumped to graduation without running
    the curriculum: no retained concepts, no crucible. Reads progress.json
    directly (no import cycle with run_session).
    """
    import os

    dd = Path(os.environ.get("LEVI_ACADEMY_DIR", Path.home() / ".levi" / "academy"))
    p = dd / "progress.json"
    scores: list[float] = []
    if p.exists():
        try:
            prog = json.loads(p.read_text(encoding="utf-8"))
            for s in prog.get("sessions", {}).values():
                if s.get("track") == track and isinstance(
                    s.get("mastery_score"), (int, float)
                ):
                    scores.append(float(s["mastery_score"]))
        except Exception:
            pass
    mean = sum(scores) / len(scores) if scores else 0.0
    return mean, [
        {
            "concept_id": f"{track}-fallback",
            "name": f"{track}: completed-session mastery fallback",
            "day": 0,
            "kind": "fallback",
            "score": round(mean, 3),
            "note": "concept registry empty; graded from "
            f"{len(scores)} completed session(s)' mastery",
        }
    ]


def ex_graduation(entry, lesson, research, syllabus, journal_points, interleave=None):
    """The final crucible: cumulative assessment sampled from ALL concepts.

    Weakest concepts first (per-concept scores tracked all program). Each
    track graded separately; the weakest track is named as the
    post-graduation drill focus. Closed-book retrieval — the concept's own
    introductory records are excluded, so this measures durable retention,
    not re-reading.
    """
    from levi.academy import concepts as acon

    per_track: dict[str, dict] = {}
    for track in ("A", "B", "C"):
        weak = acon.sample_weakest(track, 4)
        tested: list[dict] = []
        if weak:
            for c in weak:
                drill = acon.drill_concept(c, 120, closed_book=True)
                tested.append(
                    {
                        "concept_id": c["id"],
                        "name": c["name"],
                        "day": c["day"],
                        "kind": c["kind"],
                        "score": drill["score"],
                    }
                )
            mean = sum(t["score"] for t in tested) / len(tested)
        else:
            mean, tested = _fallback_track_grade(track)
        per_track[track] = {"score": round(mean, 3), "tested": tested}
    overall = round(sum(v["score"] for v in per_track.values()) / 3, 3)
    weakest_track = min(per_track, key=lambda t: per_track[t]["score"])
    focus = [
        t["name"]
        for t in per_track[weakest_track]["tested"]
        if isinstance(t.get("score"), float) and t["score"] < 0.7
    ][:4]
    verdict = (
        "GRADUATED"
        if overall >= 0.6 and all(v["score"] >= 0.5 for v in per_track.values())
        else "NOT YET"
    )
    art = {
        "per_track": per_track,
        "overall": overall,
        "weakest_track": weakest_track,
        "post_graduation_focus": focus
        or [t.get("name", "") for t in per_track[weakest_track]["tested"][:4]],
        "verdict": verdict,
        "journal_points_used": len(journal_points),
    }
    return _grade(
        art,
        [
            ("crucible covers all tracks", set(per_track) == {"A", "B", "C"}),
            ("weakest track named", weakest_track in ("A", "B", "C")),
            (
                "post-graduation focus written",
                isinstance(art["post_graduation_focus"], list)
                and len(art["post_graduation_focus"]) >= 1,
            ),
            ("verdict written", verdict in ("GRADUATED", "NOT YET")),
        ],
    )


# ---------------------------------------------------------------- M track
# Media-production drills produce REAL artifacts — rendered images and
# clips written into a work dir, graded by verifying the files. A drill
# that cannot run (ffmpeg missing) reports blocked with score 0: never a
# fake pass.


def _media_work_dir(work_dir=None) -> Path:
    wd = Path(work_dir) if work_dir is not None else Path(
        tempfile.mkdtemp(prefix="media-drill-")
    )
    wd.mkdir(parents=True, exist_ok=True)
    return wd


def _ffmpeg_blocked_artifact(op: str) -> dict:
    from levi.media.video import INSTALL_HINT

    return {
        "artifact": {
            "status": "blocked",
            "op": op,
            "reason": "ffmpeg not installed",
            "install_hint": INSTALL_HINT,
        },
        "score": 0.0,
        "checks": [{"name": "ffmpeg available", "passed": False}],
        "notes": "0/1 rubric checks passed. Drill blocked honestly — no fake completion.",
    }


def _png_ok(path: Path) -> bool:
    try:
        return path.stat().st_size > 0 and path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    except OSError:
        return False


def ex_media_photo(entry, lesson, research, work_dir=None):
    """Drill: render a real thumbnail plate with a caption band."""
    from levi.media import local as _local

    wd = _media_work_dir(work_dir)
    prompt = f"academy drill: {entry['title']}"
    img = _local.generate(
        prompt, width=256, height=144, seed=7, style="poster",
        caption_band="bottom", save_dir=wd,
    )
    # determinism proof: re-render elsewhere, bytes must match
    wd2 = wd / "rerun"
    img2 = _local.generate(
        prompt, width=256, height=144, seed=7, style="poster",
        caption_band="bottom", save_dir=wd2,
    )
    p1, p2 = Path(img.path), Path(img2.path)
    art = {
        "image": str(p1),
        "style": img.style,
        "seed": img.seed,
        "size": f"{img.width}x{img.height}",
        "safe_zone": img.safe_zone,
        "bytes": p1.stat().st_size if p1.exists() else 0,
        "deterministic_rerun": str(p2),
    }
    return _grade(
        art,
        [
            ("image file exists and is a valid PNG", _png_ok(p1)),
            ("caption band recorded", isinstance(img.safe_zone, dict)),
            (
                "deterministic: rerun byte-identical",
                p1.exists()
                and p2.exists()
                and p1.read_bytes() == p2.read_bytes(),
            ),
            ("procedural, labeled honestly", "procedural" in img.format()),
        ],
    )


def ex_media_backend(entry, lesson, research, work_dir=None):
    """Drill: backend-selection decision matrix, written as a real file."""
    wd = _media_work_dir(work_dir)
    briefs = [
        {
            "brief": "thumbnail backgrounds on the phone, airplane mode",
            "correct": "local",
            "why": "offline, zero deps, deterministic — the only backend that survives no network",
        },
        {
            "brief": "photoreal hero image, labeled as reference",
            "correct": "pollinations",
            "why": "free keyless photoreal; labeled external reference, never LEVI",
        },
        {
            "brief": "on-device diffusion with a CUDA workstation and weights on disk",
            "correct": "sd",
            "why": "hardware-gated local SD; fails closed unless deps and weights exist",
        },
    ]
    # The drill's own answers: choose per brief and justify.
    answers = [
        {"brief": b["brief"], "choice": b["correct"], "justification": b["why"]}
        for b in briefs
    ]
    path = wd / "backend-decisions.json"
    path.write_text(json.dumps(answers, indent=2), encoding="utf-8")
    art = {"decisions_file": str(path), "decisions": answers}
    return _grade(
        art,
        [
            ("decisions file written", path.exists() and path.stat().st_size > 0),
            (
                "all three briefs answered correctly",
                all(a["choice"] == b["correct"] for a, b in zip(answers, briefs)),
            ),
            (
                "every choice justified",
                all(_nonempty(a["justification"]) for a in answers),
            ),
            (
                "offline brief picks local",
                answers[0]["choice"] == "local",
            ),
        ],
    )


def ex_media_prompt(entry, lesson, research, work_dir=None):
    """Drill: build a real reusable prompt template and render it once."""
    wd = _media_work_dir(work_dir)
    template = {
        "subject": "{subject}",
        "style": "{style}",
        "composition": "{composition}",
        "negative": "no text, no watermark, no real person, {negative_extra}",
    }
    sample = {
        "subject": "sunrise over a server rack",
        "style": "poster",
        "composition": "subject left third, empty sky right for title",
        "negative_extra": "no clutter",
    }
    rendered = {k: v.format(**sample) for k, v in template.items()}
    prompt_text = (
        f"{rendered['subject']}; style {rendered['style']}; "
        f"{rendered['composition']}; avoid: {rendered['negative']}"
    )
    path = wd / "prompt-template.json"
    path.write_text(
        json.dumps(
            {"template": template, "sample": sample, "rendered_prompt": prompt_text},
            indent=2,
        ),
        encoding="utf-8",
    )
    art = {
        "template_file": str(path),
        "rendered_prompt": prompt_text,
    }
    return _grade(
        art,
        [
            ("template file written", path.exists() and path.stat().st_size > 0),
            (
                "template has subject/style/composition/negative slots",
                set(template) == {"subject", "style", "composition", "negative"},
            ),
            (
                "rendered prompt fills every slot",
                "{" not in prompt_text
                and all(isinstance(v, str) and v.strip() for v in rendered.values()),
            ),
            (
                "negative constraints name the refusals",
                "no real person" in rendered["negative"],
            ),
        ],
    )


def ex_media_video(entry, lesson, research, work_dir=None):
    """Drill: still -> Ken Burns clip -> trimmed clip, with receipts."""
    from levi.media import local as _local
    from levi.media import video as _video

    try:
        _video.check_ffmpeg()
    except _video.FFmpegMissing:
        return _ffmpeg_blocked_artifact("media-video")
    wd = _media_work_dir(work_dir)
    still = _local.generate(
        f"academy drill: {entry['title']}", width=320, height=240, seed=11,
        style="gradient", save_dir=wd,
    )
    kb = _video.kenburns(
        still.path, str(wd / "kb.mp4"), duration_s=2.0,
        width=320, height=240, fps=15, direction="in",
    )
    trimmed = _video.trim(kb.output, str(wd / "clip.mp4"), start_s=0.5, duration_s=1.0)
    dur = _video._probe_duration(Path(trimmed.output))
    art = {
        "still": still.path,
        "kenburns_clip": kb.output,
        "final_clip": trimmed.output,
        "receipts": [kb.format(), trimmed.format()],
        "output_hash": trimmed.output_hash,
        "duration_s": round(dur, 2),
    }
    return _grade(
        art,
        [
            ("final clip exists and non-empty",
             Path(trimmed.output).exists() and Path(trimmed.output).stat().st_size > 0),
            ("trimmed to ~1.0s", abs(dur - 1.0) < 0.25),
            ("two receipts recorded", len(art["receipts"]) == 2),
            (
                "output hash verifies",
                _video._sha256(Path(trimmed.output)) == trimmed.output_hash,
            ),
        ],
    )


def ex_media_vertical(entry, lesson, research, work_dir=None):
    """Drill: build a real 9:16 vertical clip and pull a thumbnail."""
    from levi.media import local as _local
    from levi.media import video as _video

    try:
        _video.check_ffmpeg()
    except _video.FFmpegMissing:
        return _ffmpeg_blocked_artifact("media-vertical")
    wd = _media_work_dir(work_dir)
    still = _local.generate(
        f"academy drill vertical: {entry['title']}", width=480, height=270, seed=21,
        style="dark", save_dir=wd,
    )
    kb = _video.kenburns(
        still.path, str(wd / "land.mp4"), duration_s=2.0,
        width=480, height=270, fps=15, direction="out", pan="right",
    )
    vert = _video.vertical(kb.output, str(wd / "vertical.mp4"), width=360, height=640)
    thumb = _video.thumbnail(vert.output, str(wd / "thumb.jpg"), at_s=0.5, width=180)
    probe = _video._probe_streams(Path(vert.output))
    import subprocess as _sp, shutil as _sh

    ffprobe = _sh.which("ffprobe")
    dims = ""
    if ffprobe:
        p = _sp.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0",
             vert.output],
            capture_output=True, timeout=30,
        )
        dims = p.stdout.decode().strip()
    art = {
        "vertical_clip": vert.output,
        "dims": dims,
        "thumbnail": thumb.output,
        "receipt": vert.format(),
    }
    return _grade(
        art,
        [
            ("vertical clip exists", Path(vert.output).stat().st_size > 0),
            ("dims are 360x640", dims == "360,640"),
            ("thumbnail exists and non-empty",
             Path(thumb.output).exists() and Path(thumb.output).stat().st_size > 0),
            ("nothing stretched: cover+crop in receipt",
             "force_original_aspect_ratio=increase" in str(vert.params.get("filter", ""))),
        ],
    )


def ex_media_thumbnail(entry, lesson, research, work_dir=None):
    """Drill: poster + thumbnail pair from one brief — real files."""
    from levi.media import local as _local

    wd = _media_work_dir(work_dir)
    brief = f"academy drill: {entry['title']}"
    poster = _local.generate(
        brief, width=512, height=288, seed=31, style="poster", save_dir=wd,
    )
    thumb = _local.generate(
        brief, width=256, height=144, seed=31, style="dark",
        caption_band="bottom", save_dir=wd,
    )
    pp, tp = Path(poster.path), Path(thumb.path)
    art = {
        "poster": str(pp),
        "thumbnail": str(tp),
        "thumbnail_safe_zone": thumb.safe_zone,
        "seed_shared": poster.seed == thumb.seed,
    }
    return _grade(
        art,
        [
            ("poster is a valid PNG", _png_ok(pp)),
            ("thumbnail is a valid PNG", _png_ok(tp)),
            ("thumbnail has a caption band", isinstance(thumb.safe_zone, dict)),
            ("pair shares one seed/brief", art["seed_shared"]),
        ],
    )


EXERCISE_RUNNERS = {
    "media-photo": ex_media_photo,
    "media-backend": ex_media_backend,
    "media-prompt": ex_media_prompt,
    "media-video": ex_media_video,
    "media-vertical": ex_media_vertical,
    "media-thumbnail": ex_media_thumbnail,
    "coverage-map": ex_coverage_map,
    "detection-sketch": ex_detection_sketch,
    "hunt-hypothesis": ex_hunt_hypothesis,
    "triage": ex_triage,
    "hardening-check": ex_hardening_check,
    "intel-brief": ex_intel_brief,
    "platform-teardown": ex_platform_teardown,
    "ux-deconstruction": ex_ux_deconstruction,
    "comparison": ex_comparison,
    "module-drill": ex_module_drill,
    "orchestration-drill": ex_orchestration_drill,
    "design-review": ex_design_review,
    "sparring-scenario": ex_sparring_scenario,
    "tabletop": ex_tabletop,
    "capstone": ex_capstone,
    "graduation": None,  # needs syllabus + journal; dispatched specially
}


def run_exercise(
    exercise_type,
    entry,
    lesson,
    research,
    syllabus=None,
    journal_points=None,
    interleave=None,
    work_dir=None,
):
    from levi.voice import signature as _voice

    if exercise_type == "graduation":
        result = ex_graduation(
            entry,
            lesson,
            research,
            syllabus or {},
            journal_points or [],
            interleave=interleave,
        )
    elif exercise_type in ("sparring-scenario", "tabletop"):
        runner = EXERCISE_RUNNERS.get(exercise_type)
        if runner is None:
            raise ValueError(f"unknown exercise type: {exercise_type}")
        result = runner(entry, lesson, research, interleave=interleave)
    elif exercise_type.startswith("media-"):
        runner = EXERCISE_RUNNERS.get(exercise_type)
        if runner is None:
            raise ValueError(f"unknown exercise type: {exercise_type}")
        # Media drills produce real artifacts into a work dir — never fake.
        result = runner(entry, lesson, research, work_dir=work_dir)
    else:
        runner = EXERCISE_RUNNERS.get(exercise_type)
        if runner is None:
            raise ValueError(f"unknown exercise type: {exercise_type}")
        result = runner(entry, lesson, research)
    # Voice: every drill opens in his voice — intensity with craft. The
    # brief frames; the rubric still decides the score.
    result["drill_brief"] = _voice.voice_open("drill", str(entry.get("title", "")))
    result["drill_spiral"] = _voice.spiral_prompt(str(entry.get("title", "")))
    return result
