"""Gap reports and targeted teacher requests for the tag-team loop.

Step 3 of the protocol: the fixed-prompt eval scores each round, and
weaknesses become targeted generation requests back to the teachers.

- ``gap_report(prev_scores, cur_scores)``: per-prompt deltas grouped by
  topic. A gap is *regressed* (score fell past tolerance) or *weak*
  (score below target with no improvement). Scores are 0..1 quality,
  higher is better.
- ``assign_requests(gaps, round_n, history)``: each gap topic becomes
  generation requests for ROTATING teachers — round-robin over the nine
  protocol seats, never the same seat for the same topic two rounds in
  a row. Every gap goes to at least two teachers so disagreements are
  preserved, never averaged away.
- ``render_requests_md``: the paste-brief Chauncey drops into the
  trainer apps; ``write_requests`` persists the JSONL machine form.

Deterministic: fixed seat order, no randomness. Stdlib only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from levi.brain.tagteam.personas import (
    PersonaCondition,
    condition_brief_block,
    validate_condition,
)
from levi.brain.tagteam.prompts import TOPICS, topic_of
from levi.brain.tagteam.roster import TEAM

REGRESS_TOL = 0.05  # score drop past this is a regression
WEAK_TARGET = 0.60  # below this with no improvement is a weakness
TEACHERS_PER_GAP = 2  # disagreements preserved: never one voice
ITEMS_PER_REQUEST = 8  # Q&A pairs requested per teacher per topic


@dataclass(frozen=True)
class Gap:
    topic: str
    prompt_id: str
    prev_score: float | None
    cur_score: float
    delta: float
    severity: str  # "regressed" | "weak"


@dataclass(frozen=True)
class TeacherRequest:
    request_id: str
    round: int
    teacher: str  # protocol seat
    topic: str
    prompt_ids: tuple[str, ...]
    brief: str
    n_items: int = ITEMS_PER_REQUEST
    condition: dict | None = None  # serialized PersonaCondition, or None


FAILURE_NOTES = {
    "regressed": "the model got worse here since last round — drill the basics, then the edge cases",
    "weak": "the model is still weak here — teach it from zero, simply, with concrete examples",
}


def gap_report(
    prev_scores: dict[str, float] | None,
    cur_scores: dict[str, float],
    regress_tol: float = REGRESS_TOL,
    weak_target: float = WEAK_TARGET,
) -> list[Gap]:
    """Compare this round's fixed-prompt scores against the last round.

    ``prev_scores`` may be None/empty for round 1 (everything is a
    baseline; only below-target scores become gaps).
    """
    prev_scores = prev_scores or {}
    gaps: list[Gap] = []
    for prompt_id in sorted(cur_scores):
        cur = cur_scores[prompt_id]
        prev = prev_scores.get(prompt_id)
        delta = cur - prev if prev is not None else 0.0
        severity = ""
        if prev is not None and delta <= -regress_tol:
            severity = "regressed"
        elif cur < weak_target and delta <= 0.0:
            severity = "weak"
        if severity:
            gaps.append(
                Gap(
                    topic=topic_of(prompt_id),
                    prompt_id=prompt_id,
                    prev_score=prev,
                    cur_score=cur,
                    delta=round(delta, 4),
                    severity=severity,
                )
            )
    return gaps


def _rotate_seats(
    topic: str, round_n: int, history: dict[str, list[str]], n: int = TEACHERS_PER_GAP
) -> list[str]:
    """Pick n seats round-robin, skipping last round's seats for the topic.

    Deterministic on (topic, round_n): the start index walks the roster
    so authority never settles on one teacher.
    """
    used_last = set(history.get(topic, []))
    start = (round_n + TOPICS.index(topic)) % len(TEAM)
    picked: list[str] = []
    idx = start
    while len(picked) < n and len(picked) < len(TEAM):
        seat = TEAM[idx % len(TEAM)]
        if seat not in used_last or len(used_last) >= len(TEAM) - 1:
            if seat not in picked:
                picked.append(seat)
        idx += 1
        if idx - start > len(TEAM) * 2:
            break
    return picked


def build_brief(
    round_n: int,
    teacher: str,
    topic: str,
    gaps: Iterable[Gap],
    condition: PersonaCondition | None = None,
) -> str:
    """The paste-brief: what Chauncey hands a trainer app for one topic."""
    gap_list = list(gaps)
    severities = sorted({g.severity for g in gap_list})
    notes = "; ".join(FAILURE_NOTES[s] for s in severities)
    prompts = "\n".join(f"- {g.prompt_id}: scored {g.cur_score:.2f}" for g in gap_list)
    cond_block = ""
    cond_json = ""
    if condition is not None:
        cond_block = f"\n{condition_brief_block(condition)}\n"
        cond_json = (
            f', "persona_condition": '
            f"{json.dumps(condition.to_dict(), ensure_ascii=False)}"
        )
    return (
        f"You are generating training data for LEVI, a small local AI. "
        f"Tag-team round {round_n} targeted request — topic: {topic}.\n"
        f"Weakness observed: {notes}.\n"
        f"Failing eval prompts:\n{prompts}\n"
        f"{cond_block}"
        f"Write {ITEMS_PER_REQUEST} Q&A pairs AS LEVI would answer: calm, "
        f"precise, short clauses, plain ASCII only (no emoji, no smart "
        f"quotes, no em dashes — plain hyphens and straight quotes). "
        f"Keep answers to 1-3 short sentences. Never claim feelings, "
        f"consciousness, or being alive. LEVI is honest about limits and "
        f"says \"I don't know\" when it doesn't.\n"
        f"Return each pair as one JSONL line: "
        f'{{"teacher": "{teacher}", "prompt": "<question>", '
        f'"response": "<LEVI\'s answer>", "topic": "{topic}"{cond_json}}}\n'
        f"Ask at least two teachers per topic. Keep disagreements — do "
        f"not average them away; LEVI's curator preserves every voice."
    )


def assign_requests(
    gaps: list[Gap],
    round_n: int,
    history: dict[str, list[str]] | None = None,
    conditions: list[PersonaCondition] | tuple[PersonaCondition, ...] | None = None,
) -> list[TeacherRequest]:
    """Turn gaps into rotating teacher requests, grouped by topic.

    ``conditions`` (optional) rotates persona/trait/tone/role frames
    across requests deterministically: request k gets
    ``conditions[(round_n + k) % len(conditions)]``. Each request's
    condition is validated before assignment.
    """
    history = history or {}
    conds: list[PersonaCondition] = []
    if conditions:
        for c in conditions:
            conds.append(
                c if isinstance(c, PersonaCondition) else validate_condition(c)
            )
    by_topic: dict[str, list[Gap]] = {}
    for g in gaps:
        by_topic.setdefault(g.topic, []).append(g)
    requests: list[TeacherRequest] = []
    k = 0
    for topic in sorted(by_topic):
        seats = _rotate_seats(topic, round_n, history)
        for seat in seats:
            cond = conds[(round_n + k) % len(conds)] if conds else None
            k += 1
            requests.append(
                TeacherRequest(
                    request_id=f"r{round_n:03d}-{topic}-{seat}",
                    round=round_n,
                    teacher=seat,
                    topic=topic,
                    prompt_ids=tuple(g.prompt_id for g in by_topic[topic]),
                    brief=build_brief(round_n, seat, topic, by_topic[topic], cond),
                    condition=cond.to_dict() if cond else None,
                )
            )
    return requests


def write_requests(path: Path, requests: list[TeacherRequest]) -> None:
    """Machine form: one JSON line per request."""
    path = Path(path)
    with open(path, "w", encoding="utf-8") as fh:
        for r in requests:
            fh.write(
                json.dumps(
                    {
                        "request_id": r.request_id,
                        "round": r.round,
                        "teacher": r.teacher,
                        "topic": r.topic,
                        "prompt_ids": list(r.prompt_ids),
                        "n_items": r.n_items,
                        "brief": r.brief,
                        "condition": r.condition,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def render_requests_md(requests: list[TeacherRequest], round_n: int) -> str:
    """Human form: the paste-brief Chauncey drops into the trainer apps."""
    lines = [
        f"# Tag-team round {round_n} — teacher requests",
        "",
        f"{len(requests)} requests across "
        f"{len({r.topic for r in requests})} weak topics. "
        "Paste one brief per trainer app; collect answers as JSONL drops.",
        "",
    ]
    for r in requests:
        cond_line = ""
        if r.condition:
            c = r.condition
            cond_line = (
                f"\ncondition: {c['persona_id']} / {c['role']} / "
                f"{c['tone']} (provisional)"
            )
        lines += [
            f"## {r.request_id} — {r.teacher} / {r.topic}{cond_line}",
            "",
            r.brief,
            "",
        ]
    return "\n".join(lines)
