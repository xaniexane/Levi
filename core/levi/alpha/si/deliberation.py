"""Native deliberation steps: propose -> critique -> verdict.

A rules-engine mind, honest about being one. ``propose`` frames the task
three ways; ``critique`` attacks each framing; ``verdict`` keeps the
framing that survives and says which substrate reasoned. Nothing here
pretends to be a brain — when the native-brain weights are usable,
``reason.py`` says so in ``limits`` and the substrate line; the steps
below stay rules, reported as rules.
"""

from __future__ import annotations

from typing import Any, Dict, List

ORIGIN = "levi-alpha/si/deliberation"


def propose(task: str) -> List[Dict[str, Any]]:
    """Frame the task three ways. Returns three ``{stance, text, confidence}``."""
    task = task.strip()
    return [
        {
            "stance": "direct",
            "text": (
                "Take the task at face value and answer it as stated: "
                f"{task}. Lead with the most useful direct answer, then the "
                "shortest supporting reasoning."
            ),
            "confidence": 0.6,
        },
        {
            "stance": "skeptical",
            "text": (
                "Distrust the first reading. Ask what the task might really "
                f"be after — what ambiguous words in {task!r} could flip the "
                "answer, what the asker would regret if I guessed wrong, and "
                "what a safer interpretation would change."
            ),
            "confidence": 0.5,
        },
        {
            "stance": "minimal",
            "text": (
                "Refuse scope creep. Answer only what was asked, nothing "
                "more: the smallest true statement that satisfies the task, "
                "with anything uncertain marked as uncertain."
            ),
            "confidence": 0.7,
        },
    ]


def critique(proposals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attack each proposal; return ``{stance, weakness, open_question}``."""
    attacks = {
        "direct": (
            "may answer the wrong question confidently if the task is "
            "ambiguous or underspecified",
            "what is the single most likely misreading of this task?",
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

    Scoring is deliberately simple and reported: base confidence minus a
    penalty per acknowledged weakness severity (direct 0.15, skeptical
    0.10, minimal 0.10). Ties break toward ``minimal`` — the honest
    default is to claim less.
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
