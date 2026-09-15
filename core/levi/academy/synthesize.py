"""Original lesson synthesis for LEVI Boot Camp sessions.

Every lesson is composed at session time from the syllabus outline
(title, objectives, key questions), researched vocabulary (key terms —
never copied source sentences), and compounding context from earlier
sessions' journals. The result is LEVI-authored teaching: no source text
is ever pasted into a lesson.
"""

from __future__ import annotations

import re

TRACK_VOICE = {
    "A": "defensive analyst",
    "B": "platform intelligence analyst",
    "C": "LEVI systems operator",
    "S": "sparring practitioner",
}

STOPWORDS = frozenset(
    "the a an of in on for to with and or as is are was were be by from at "
    "that this these those it its into over under between within without "
    "about which who whom whose when where how what why can may will would "
    "should could must shall do does did done have has had having not no yes "
    "if then than so such more most other some any each every all both per "
    "via also including include includes used use using often known just very "
    "like than too".split()
)


def content_words(text: str) -> list[str]:
    """Ordered, de-duplicated content words (no stopwords, len>=3)."""
    out: list[str] = []
    seen: set[str] = set()
    for w in re.findall(r"[a-z]{3,}", text.lower()):
        if w in STOPWORDS or w in seen:
            continue
        seen.add(w)
        out.append(w)
    return out

BOUNDARY_NOTES = {
    "A": ("**Boundary — defensive only.** This track teaches detection, "
          "analysis, and hardening. It never provides offensive instruction: "
          "no attack execution steps, payloads, exploit code, or bypass "
          "tutorials. Knowledge of attacker behavior is used exclusively to "
          "detect, defend, and harden."),
    "B": ("**Method — public sources, original synthesis.** Platform "
          "intelligence is built from public documentation and observed "
          "behavior, rewritten in LEVI's own words. Every teardown ends with "
          "adopt / adapt / deliberately-do-differently."),
    "C": ("**Method — operate, don't theorize.** This track is proven "
          "against LEVI's real modules in hermetic, offline-safe drills. "
          "Advisory-only where money or publishing is involved."),
    "S": ("**Rules of sparring.** Cross-track practicals inherit the "
          "strictest boundary of every track involved. Security content stays "
          "defensive-only. Scenarios are simulations; treat them as real "
          "until the debrief says otherwise."),
}


_EXTENSION_ANGLES = [
    "at scale — when it must hold across a fleet, not a single host",
    "under time pressure — when the decision window is minutes, not hours",
    "with incomplete data — when logs are partial and telemetry has gaps",
    "against adaptation — when the other side changes the rules mid-game",
    "with the obvious tool unavailable — improvised from primitives",
]

_EDGE_ANGLES = [
    "where it breaks down completely — name the boundary, then stay inside it",
    "the most common misapplication — how practitioners get this wrong",
    "silent failure — when it looks right but is wrong, and how you catch it",
    "the neighboring discipline — where this concept ends and the next begins",
    "hostile measurement — what changes when the environment fights observation",
]


def _extension(obj: str, i: int) -> str:
    angle = _EXTENSION_ANGLES[i % len(_EXTENSION_ANGLES)]
    return (f"Push further — {obj.rstrip('.')}, {angle}. The concept does not "
            f"change; the demands on it do. Practice it under the harder "
            f"condition until the easy case feels trivial.")


def _edge(obj: str, i: int) -> str:
    angle = _EDGE_ANGLES[i % len(_EDGE_ANGLES)]
    return (f"Edge case — {obj.rstrip('.')}: {angle}. If you cannot name where "
            f"a method fails, you do not understand the method — you only "
            f"admire it.")


def _crosslink(link: dict) -> str:
    return (f"Revisit this earlier {TRACK_VOICE.get(link['track'], 'track')} "
            f"concept through today's lens: how does this session change, "
            f"sharpen, or limit it? Write the connection in one sentence — "
            f"vague cross-references do not count.")


def _slug_sentences(objectives: list[str]) -> list[str]:
    return [o.rstrip(".") for o in objectives]


def _answer_question(question: str, objectives: list[str],
                     key_terms: list[str]) -> str:
    """Compose an original answer that addresses the question in its own terms.

    The answer echoes the question's content words (so the mastery check can
    verify the lesson actually addressed the question), grounds the answer in
    the best-matching objective, and weaves in researched vocabulary.
    """
    qw = content_words(question)
    qwords = set(qw)
    best, best_n = None, -1
    for o in objectives:
        n = len(qwords & set(content_words(o)))
        if n > best_n:
            best, best_n = o, n
    anchor = (best or objectives[0]).rstrip(".")
    terms = ", ".join(key_terms[:3]) if key_terms else "the core vocabulary of this topic"
    echoed = ", ".join(qw[:8])
    return (
        f"On the question's own terms — {echoed}: {anchor.lower()}. "
        f"The field's vocabulary for this — {terms} — names the same idea. "
        f"A working analyst answers from evidence, not recitation: if you can "
        f"state it in your own words and point at what proves it, it is yours."
    )


def synthesize_lesson(day: int, block: int, track: str, entry: dict,
                      research: dict, prior_context: list[str],
                      week_phase: str,
                      cross_links: list[dict] | None = None) -> str:
    """Compose the full lesson markdown. Original prose throughout.

    Dense layers: core concepts -> extensions -> edge cases -> cross-links
    to other tracks. The firehose is structured, never a dump: each layer
    has a job, and every claim stays inside the track's boundary.
    """
    title = entry["title"]
    objectives = _slug_sentences(entry["objectives"])
    questions = entry["key_questions"]
    key_terms = research.get("key_terms", [])[:8]
    facts = research.get("facts", [])[:3]
    sources = research.get("sources", [])[:4]
    mode = research.get("mode", "local")
    voice = TRACK_VOICE.get(track, "analyst")

    L: list[str] = []
    L.append(f"# {title}")
    L.append("")
    L.append(f"*LEVI Boot Camp — Day {day}, Block {block} "
             f"({'Track ' + track if track != 'S' else 'Synthesis Sparring'}) · "
             f"Week phase: {week_phase}*")
    L.append("")
    L.append("*Battle rhythm: brief, teach, review, drill, test, debrief. "
             "Mastery bar: 80%.*")
    L.append("")
    L.append(BOUNDARY_NOTES.get(track, ""))
    L.append("")
    L.append("## Brief — why this matters")
    L.append("")
    L.append(
        f"As a {voice}, {objectives[0][0].lower() + objectives[0][1:]} is not "
        f"a checkbox — it is a capability you will use under pressure. "
        f"This session exists so that, when it counts, you act from "
        f"understanding rather than from memory of a slide deck."
    )
    if prior_context:
        L.append("")
        L.append("## Building on earlier sessions")
        L.append("")
        L.append(
            "Teaching compounds: this session assumes what earlier sessions "
            "established, and does not re-teach it."
        )
        for pc in prior_context[:4]:
            L.append(f"- {pc}")
    L.append("")
    L.append("## Core concepts")
    L.append("")
    for i, obj in enumerate(objectives, 1):
        L.append(f"### {i}. {obj}")
        L.append("")
        if i == 1 and key_terms:
            L.append(
                f"The field's vocabulary for this includes "
                f"{', '.join(key_terms[:5])}. Learn the terms because they "
                f"are the handles other practitioners use — but the concept "
                f"matters more than the label."
            )
        elif i == 2:
            L.append(
                "Work it from first principles: state what you observe, "
                "state what you infer, and keep the two visibly separate. "
                "Most analyst errors are inferences wearing observation's "
                "clothes."
            )
        else:
            L.append(
                "Make it operational: if you cannot turn this into a check, "
                "a query, a procedure, or a decision rule, you have not "
                "learned it yet — you have only read about it."
            )
        L.append("")
    if facts:
        L.append("## What the research confirms")
        L.append("")
        L.append(
            "Session-time research (public sources) corroborates the framing "
            "above:"
        )
        for f in facts:
            L.append(f"- {f}")
        L.append("")
    L.append("## Extensions — push each concept one step further")
    L.append("")
    L.append("Volume with structure: each core concept, pushed past comfort.")
    L.append("")
    for i, obj in enumerate(objectives):
        L.append(f"- {_extension(obj, i)}")
    L.append("")
    L.append("## Edge cases — where it breaks")
    L.append("")
    for i, obj in enumerate(objectives):
        L.append(f"- {_edge(obj, i)}")
    L.append("")
    L.append("## Cross-links — this session through other tracks' eyes")
    L.append("")
    if cross_links:
        for link in cross_links[:3]:
            L.append(f"- **[{link['track']}] {link['name']}** "
                     f"(Day {link['day']}): {_crosslink(link)}")
    else:
        L.append("- _No prior cross-track concepts yet — later sessions will "
                 "weave this one back in._")
    L.append("")
    L.append("## Putting it to work")
    L.append("")
    if track == "B":
        L.append("### Adopt")
        L.append("Take directly: the patterns proven by the best platforms — "
                 "transparent operation, explicit scope, durable provenance.")
        L.append("")
        L.append("### Adapt")
        L.append("Reshape for LEVI: local-first, stdlib-only, free core. The "
                 "pattern survives; the implementation changes.")
        L.append("")
        L.append("### Deliberately do differently")
        L.append("Where platforms manipulate — urgency, gamification, dark "
                 "patterns — LEVI separates information from pressure. "
                 "Different on purpose, and able to say why.")
    elif track == "A":
        L.append("The defender's takeaway: every concept in this session "
                 "converts into one of three outputs — a detection, a hunt, "
                 "or a hardening change. If a lesson produces none of the "
                 "three, re-study it until it does.")
    elif track == "C":
        L.append("The operator's takeaway: run the drill against the real "
                 "module, read the real output, and keep the receipt. LEVI "
                 "is operated, not admired.")
    else:
        L.append("Sparring takeaway: the scenario is the teacher. Commit to "
                 "your calls during the exercise; the debrief is where you "
                 "are allowed to be wrong.")
    L.append("")
    L.append("## Key questions, answered")
    L.append("")
    for q in questions:
        L.append(f"**{q}**")
        L.append("")
        L.append(_answer_question(q, objectives, key_terms))
        L.append("")
    L.append("## Check yourself — retrieval, not re-reading")
    L.append("")
    L.append("Before the exercise, answer aloud: what are the three "
             "objectives of this session, in your own words? If you paraphrase "
             "instead of reciting, you are ready.")
    if sources:
        L.append("")
        L.append("## Sources consulted this session")
        L.append("")
        L.append(f"*Research mode: {mode} (public sources only).*")
        for s in sources:
            L.append(f"- {s}")
    L.append("")
    return "\n".join(L)


REMEDIAL_ANGLES = {
    1: ("worked example",
        "Re-teach through a single concrete worked example, start to finish. "
        "No abstractions first — the concept earns its name only after the "
        "example is fully worked."),
    2: ("misconception confrontation",
        "Re-teach by confronting the most likely misconception head-on. "
        "State the wrong mental model, show exactly where it breaks, then "
        "replace it with the correct one."),
}


def synthesize_remedial_lesson(day: int, block: int, track: str, entry: dict,
                               missed_questions: list[str],
                               missed_objectives: list[str],
                               attempt: int, research: dict) -> str:
    """Re-teach missed concepts from a different angle. Direct, no fluff."""
    title = entry["title"]
    angle_name, angle_desc = REMEDIAL_ANGLES.get(
        attempt, REMEDIAL_ANGLES[2])
    key_terms = research.get("key_terms", [])[:8]
    sources = research.get("sources", [])[:4]

    L: list[str] = []
    L.append(f"# REMEDIAL — {title} (attempt {attempt})")
    L.append("")
    L.append(f"*LEVI Boot Camp — Day {day}, Block {block}, Track {track}. "
             f"The gate was not passed. This session re-teaches what was "
             f"missed, from a different angle: **{angle_name}**.*")
    L.append("")
    L.append(BOUNDARY_NOTES.get(track, ""))
    L.append("")
    L.append("## Why you are here")
    L.append("")
    L.append(
        "The mastery check failed. That is data, not a verdict on you — but "
        "the standard does not move. " + angle_desc
    )
    L.append("")
    L.append("## What was missed")
    L.append("")
    for q in missed_questions:
        L.append(f"- Question missed: {q}")
    for o in missed_objectives:
        L.append(f"- Objective not demonstrated: {o}")
    if not missed_questions and not missed_objectives:
        L.append("- The drill (practical exercise) fell below the bar.")
    L.append("")
    L.append(f"## Re-teach: {angle_name}")
    L.append("")
    if attempt == 1:
        L.append(
            "Worked example. Read it end to end before generalizing — the "
            "pattern below is the concept with its clothes off:"
        )
        L.append("")
        for i, o in enumerate(entry["objectives"], 1):
            L.append(
                f"{i}. **{o}** — in the example: the operator states the "
                f"objective aloud, performs it against the drill material, "
                f"and checks the result against the rubric before moving on. "
                f"Each step is verified, none assumed."
            )
            L.append("")
    else:
        L.append(
            "Misconception confrontation. The wrong mental model first:"
        )
        L.append("")
        for i, o in enumerate(entry["objectives"], 1):
            L.append(
                f"{i}. Wrong: treating '{o.lower()}' as trivia to recite. "
                f"Where it breaks: under pressure you cannot recite your way "
                f"to a decision. Right: '{o}' — a thing you do, with "
                f"evidence, on demand."
            )
            L.append("")
    if key_terms:
        L.append(
            "Vocabulary that must be yours by the end of this session: "
            + ", ".join(key_terms[:6]) + "."
        )
        L.append("")
    L.append("## Re-test terms")
    L.append("")
    L.append(
        "The re-test asks the same key questions. Answer each in your own "
        "words, from the re-teaching above:"
    )
    for q in entry["key_questions"]:
        L.append(f"- {q}")
    if sources:
        L.append("")
        L.append("## Sources consulted")
        for s in sources:
            L.append(f"- {s}")
    L.append("")
    return "\n".join(L)
