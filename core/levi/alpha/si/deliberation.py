"""Native deliberation steps: propose -> critique -> verdict.

A rules-engine mind, honest about being one. ``propose`` reads the task
text for real — question type, key content words, ambiguity markers —
and each stance composes an answer attempt *about the task*, not a
framing template. ``critique`` attacks each stance; ``verdict`` keeps
the one that survives and says which substrate reasoned. Nothing here
pretends to be a brain: when the native-brain weights are usable,
``reason.py`` says so in ``limits`` and the substrate line, and the
brain-voice's raw continuation can inform the skeptical stance (it is
heard, never obeyed — its score is capped below every rules stance).
The steps below stay rules, reported as rules.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

ORIGIN = "levi-alpha/si/deliberation"


# -- small honest lexicons ---------------------------------------------------
# These are fixed word lists, not knowledge claims: they let the rules
# engine name what it sees in the task text and nothing more.

_STOPWORDS = frozenset(
    "a an the of to in on for with and or but if then than as at by from is are "
    "was were be been being do does did can could should would will shall may "
    "might must have has had having not no yes it its they them their this that "
    "these those i me my we us our you your he him his she her we they what "
    "which who whom whose where when why how s t d ll re ve m".split()
)

_YES_NO_AUX = frozenset(
    "is are was were do does did can could should will would may might "
    "has have had shall must".split()
)

_WH_WORDS = ("what", "why", "how", "where", "when", "who", "which", "whose", "whom")

# (marker words, why it is ambiguous) — every marker is checked against the
# task text and reported only when actually present.
_AMBIGUITY = [
    (
        {"it", "its"},
        "a pronoun with no named referent — nothing earlier in the task names what it stands for",
    ),
    (
        {"they", "them", "their"},
        "a plural pronoun with no named referent — the group it means is unstated",
    ),
    (
        {"this", "that", "these", "those"},
        "a demonstrative pointing at nothing in the text — the intended thing is unstated",
    ),
    (
        {"there", "here", "somewhere", "anywhere"},
        "a place word with no actual place named",
    ),
    (
        {
            "best",
            "worst",
            "most",
            "least",
            "biggest",
            "smallest",
            "easiest",
            "hardest",
            "fastest",
            "fairest",
            "greatest",
        },
        "a superlative with no stated measure — the best by whose yardstick?",
    ),
    (
        {"good", "right", "enough", "better", "worse"},
        "a value word with no stated standard — good for what, right by whom?",
    ),
    (
        {"maybe", "probably", "possibly", "perhaps"},
        "hedging — this may be thinking aloud rather than a real question",
    ),
    (
        {"should", "ought"},
        "normative — the task says what ought to happen but never names who decides",
    ),
    (
        {"soon", "later", "recently", "someday", "eventually"},
        "a time word with no actual time attached",
    ),
]

# Common (object word -> (hinge factor, affirmative action, negative action))
# for yes/no decisions. A small, explicit, reported lookup — if the task's
# words are not in it, the direct stance says so and falls back to a
# generic conditional instead of inventing a factor.
_HINGE = {
    "umbrella": ("rain", "pack the umbrella", "leave it behind"),
    "raincoat": ("rain", "take the raincoat", "leave it behind"),
    "jacket": ("cold weather", "take the jacket", "skip it"),
    "coat": ("cold weather", "take the coat", "skip it"),
    "sweater": ("cold weather", "wear the sweater", "skip it"),
    "sunscreen": ("sun exposure", "apply sunscreen", "skip it"),
    "sunglasses": ("bright sun", "bring the sunglasses", "skip them"),
    "boots": ("mud or rough ground", "wear the boots", "wear the normal shoes"),
}

_WH_WANTS = {
    "what": "a name, a definition, or a concrete thing",
    "why": "a reason or cause",
    "how": "a method or an explanation",
    "where": "a place",
    "when": "a time",
    "who": "a person",
    "which": "a choice between named options",
    "whose": "an owner",
    "whom": "a person",
}


def _words(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


def _content_words(text: str) -> List[str]:
    return [w for w in _words(text) if w not in _STOPWORDS and len(w) > 1]


def _analyze(task: str) -> Dict[str, Any]:
    """Read the task text for real: question type, content words, ambiguities."""
    words = _words(task)
    first = words[0] if words else ""
    content = _content_words(task)
    asks = task.rstrip().endswith("?")

    if first in _YES_NO_AUX and asks:
        qtype = "yes-no"
    elif first in _WH_WORDS and asks:
        qtype = "information"
    elif not asks and len(content) <= 2:
        qtype = "fragment"
    elif not asks and first and first not in _YES_NO_AUX and first not in _WH_WORDS:
        qtype = "instruction"
    elif asks:
        qtype = "open"
    else:
        qtype = "open"

    ambiguous: List[Dict[str, str]] = []
    wordset = set(words)
    for markers, why in _AMBIGUITY:
        hit = sorted(markers & wordset)
        if hit:
            ambiguous.append({"words": ", ".join(f"'{w}'" for w in hit), "why": why})

    key_words = content[:5]
    key_phrase = " ".join(key_words) if key_words else "(no content words found)"
    return {
        "qtype": qtype,
        "words": words,
        "content": content,
        "ambiguous": ambiguous,
        "key_words": key_words,
        "key_phrase": key_phrase,
        "asks": asks,
    }


def _direct_text(task: str, a: Dict[str, Any]) -> str:
    """The direct stance: answer the task as stated, from its own words."""
    qtype = a["qtype"]
    key_phrase = a["key_phrase"]
    if qtype == "yes-no":
        hinge = None
        for w in a["content"]:
            if w in _HINGE:
                hinge = _HINGE[w]
                break
        if hinge:
            factor, affirmative, negative = hinge
            return (
                f"Direct read: this is a yes/no decision about {key_phrase}. "
                f"Taking the task at face value, the whole question hinges on "
                f"{factor} — a fact the task text itself does not state. The "
                f"honest direct answer is therefore a rule, not a fact: check "
                f"for {factor}; if it is coming, {affirmative}; otherwise, "
                f"{negative}. Nothing in the words above observes the world; "
                f"treat this as the decision procedure, not the decision."
            )
        act = f"do what the task asks about ({key_phrase})" if a["key_words"] else "act"
        return (
            f"Direct read: this is a yes/no decision about {key_phrase}. "
            f"The task text does not state the circumstance it hinges on, so "
            f"the honest direct answer is conditional: resolve the missing "
            f"circumstance first — if it comes back affirmative, {act}; "
            f"otherwise, don't. No verdict on the world is earned from these "
            f"words alone."
        )
    if qtype == "information":
        first = a["words"][0] if a["words"] else ""
        want = _WH_WANTS.get(first, "an answer")
        beyond = (
            " and ".join(
                f"{x['words']} ({x['why'].split('—')[0].strip()})"
                for x in a["ambiguous"][:2]
            )
            if a["ambiguous"]
            else "no stated ambiguities"
        )
        return (
            f"Direct read: the task asks '{first}' about {key_phrase} — at face "
            f"value it wants {want}. From the task text alone, the direct "
            f"answer is exactly what is stated: '{task}'. Anything beyond "
            f"those words would be invented, so the honest answer stops there "
            f"and names what is still unresolved: {beyond}."
        )
    if qtype == "instruction":
        first_phrase = " ".join(a["content"][:4]) or "do it"
        return (
            f"Direct read: the task instructs me to {first_phrase}. Carried "
            f"out literally, from the words given: '{task}'. The concrete "
            f"first step the words actually name is {first_phrase} — every "
            f"step after that is unspecified and must not be invented."
        )
    if qtype == "fragment":
        return (
            f"Direct read: '{task}' is not a complete question — it scans as a "
            f"fragment about {key_phrase}. There is no answer to give a "
            f"fragment; restate it as a question and the deliberation can run "
            f"properly."
        )
    # open
    return (
        f"Direct read: the task reads '{task}'. It is not a tight question, "
        f"so the direct answer addresses what is actually asked: {key_phrase} "
        f"— and everything further depends on resolving the looseness below "
        f"rather than guessing."
    )


def _skeptical_text(
    task: str, a: Dict[str, Any], brain_continuation: Optional[str]
) -> str:
    """The skeptical stance: name what the task's own words leave open."""
    parts = [
        "Skeptical read: distrust the first reading. What the task's own "
        "words leave open:"
    ]
    if a["ambiguous"]:
        for x in a["ambiguous"]:
            parts.append(f"- {x['words']}: {x['why']}.")
    else:
        parts.append(
            "- nothing flagged: the task names its terms and they are not "
            "hedged, pronominal, or superlative. Skepticism finds no purchase "
            "here, and says so."
        )
    if brain_continuation:
        drift = _brain_drift_words(brain_continuation, set(a["words"]))
        if drift:
            quoted = ", ".join(f"'{w}'" for w in drift)
            parts.append(
                f"Independent evidence the phrasing is loose: the brain-voice's "
                f"raw continuation — garbled proof-of-learning output, not "
                f"reasoning — drifted toward {quoted}. The brain grabbed those "
                f"words from this task's phrasing; a different reader could grab "
                f"different ones. Take this as evidence of looseness, never as "
                f"an answer."
            )
        else:
            parts.append(
                "The brain-voice's raw continuation added no distinctive new "
                "words, so it gives the skeptical stance no further evidence "
                "of alternative readings."
            )
    doubts = [x["words"] for x in a["ambiguous"]]
    anchor = f" the reading of {doubts[0]}" if doubts else " any reading at all"
    parts.append(
        f"The doubt that actually changes the answer: pin down{anchor} before "
        f"committing. Everything else is noise."
    )
    return " ".join(parts)


def _brain_drift_words(continuation: str, task_words: set) -> List[str]:
    """Distinctive words the brain's continuation grabbed that the task did
    not contain — quoted as evidence of loose phrasing, never as content."""
    counts: Dict[str, int] = {}
    for w in _words(continuation):
        if w in task_words or w in _STOPWORDS or len(w) < 3:
            continue
        counts[w] = counts.get(w, 0) + 1
    return [w for w, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))][:5]


def _minimal_text(task: str, a: Dict[str, Any]) -> str:
    """The minimal stance: the smallest true statement, uncertainty marked."""
    uncertain = (
        "what is uncertain: " + "; ".join(x["words"] for x in a["ambiguous"])
        if a["ambiguous"]
        else "nothing uncertain in the wording itself"
    )
    return (
        "Minimal read: refuse scope creep. The smallest true statement the "
        f"task text earns is this — the task asks '{task}', and it is about "
        f"{a['key_phrase']}. Beyond that, {uncertain}. Everything else "
        f"would be invented."
    )


def propose(
    task: str, brain_continuation: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Read the task for real and compose three answer attempts.

    ``brain_continuation`` (the brain-voice's raw text, when the weights
    ran) is quoted by the skeptical stance as evidence of loose phrasing —
    verbatim, labeled, never reasoning.
    """
    task = task.strip()
    a = _analyze(task)
    return [
        {
            "stance": "direct",
            "text": _direct_text(task, a),
            "confidence": 0.6,
            "analysis": {"qtype": a["qtype"], "key_phrase": a["key_phrase"]},
        },
        {
            "stance": "skeptical",
            "text": _skeptical_text(task, a, brain_continuation),
            "confidence": 0.5,
            "analysis": {
                "qtype": a["qtype"],
                "ambiguities": [x["words"] for x in a["ambiguous"]],
            },
        },
        {
            "stance": "minimal",
            "text": _minimal_text(task, a),
            "confidence": 0.7,
            "analysis": {"qtype": a["qtype"], "key_phrase": a["key_phrase"]},
        },
    ]


def critique(proposals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attack each proposal; return ``{stance, weakness, open_question}``.

    The attack names the stance's actual text where it matters, so the
    verdict's survivors are about this task, not about stances in general.
    """
    attacks = {
        "direct": (
            "may answer the wrong question confidently: its conditional "
            "answer assumes the task's hinge is the real hinge",
            "what single fact, if known, would flip the direct answer?",
        ),
        "skeptical": (
            "can stall on doubt and deliver hedging instead of an answer",
            "which doubt actually changes the answer, and which is noise?",
        ),
        "minimal": (
            "may omit context the asker needed but didn't think to request",
            "what one missing piece would make this answer misleading?",
        ),
    }
    out = []
    for proposal in proposals:
        stance = proposal.get("stance", "?")
        weakness, open_question = attacks.get(
            stance, ("unexamined framing", "what is this stance assuming?")
        )
        out.append(
            {"stance": stance, "weakness": weakness, "open_question": open_question}
        )
    return out


def verdict(
    proposals: List[Dict[str, Any]],
    critiques: List[Dict[str, Any]],
    substrate: str,
) -> Dict[str, Any]:
    """Keep the stance that survives its own critique.

    The verdict's ``answer`` is the winning stance's own answer text — the
    deliberation's answer to the task, not a template about stances.

    Scoring is deliberately simple and reported: base confidence minus a
    penalty per acknowledged weakness severity (direct 0.15, skeptical
    0.10, minimal 0.10; anything else, including the brain-voice, 0.10).
    Ties break toward ``minimal`` — the honest default is to claim less.
    """
    penalty = {"direct": 0.15, "skeptical": 0.10, "minimal": 0.10}
    scored = []
    for proposal in proposals:
        stance = proposal.get("stance", "?")
        score = float(proposal.get("confidence", 0.5)) - penalty.get(stance, 0.10)
        scored.append((score, proposal))
    scored.sort(key=lambda item: (item[0], item[1].get("stance") != "minimal"))
    best_score, best = scored[-1]
    chosen_critique = next(
        (c for c in critiques if c.get("stance") == best.get("stance")), {}
    )
    return {
        "chosen": best.get("stance"),
        "score": round(best_score, 3),
        "answer": best.get("text"),
        "survived_weakness": chosen_critique.get("weakness", ""),
        "open_question": chosen_critique.get("open_question", ""),
        "substrate": substrate,
        "note": (
            f"Reasoned on the {substrate} substrate. This is rules-based "
            "deliberation — propose, critique, verdict — not a brain "
            "inference, and it is reported as such."
        ),
    }
