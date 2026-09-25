"""Fixed evaluation prompts for the tag-team loop.

These prompts score every round and NEVER enter training. The loop
guards this structurally: ``loop.assert_eval_clean`` aborts any round
whose curated records contain an eval prompt verbatim. Fixed prompts
stay outside the weights — per the standing rule, providers and eval
material are references, never training fodder for themselves.

Topics mirror the curriculum directive ("more human than human"):
arithmetic, grammar, physics, chemistry, history, civics, reasoning,
5D emotional intelligence, identity/honesty, limits, and local-first.
"""

from __future__ import annotations

from levi.brain.tagteam.personas import PersonaCondition, condition_brief_block

# Each entry: stable id, topic (used by gap reports and teacher
# requests), and the prompt text.
FIXED_EVAL_PROMPTS: tuple[dict[str, str], ...] = (
    {"prompt_id": "arith-1", "topic": "arithmetic", "prompt": "What is 17 + 25?"},
    {
        "prompt_id": "arith-2",
        "topic": "arithmetic",
        "prompt": "A dozen eggs costs 3 dollars. What do 4 dozen cost?",
    },
    {
        "prompt_id": "grammar-1",
        "topic": "grammar",
        "prompt": "Fix the grammar: 'me and him went to the store.'",
    },
    {
        "prompt_id": "physics-1",
        "topic": "physics",
        "prompt": "Why does ice float on water?",
    },
    {"prompt_id": "chem-1", "topic": "chemistry", "prompt": "What is H2O?"},
    {
        "prompt_id": "history-1",
        "topic": "history",
        "prompt": "Who was the first president of the United States?",
    },
    {"prompt_id": "civics-1", "topic": "civics", "prompt": "What does a mayor do?"},
    {
        "prompt_id": "reason-1",
        "topic": "reasoning",
        "prompt": "If all glubs are snorps, and some snorps are green, "
        "are any glubs green? Explain briefly.",
    },
    {
        "prompt_id": "ei-1",
        "topic": "emotional-intelligence",
        "prompt": "I am frustrated with my slow computer. What should I do?",
    },
    {
        "prompt_id": "identity-1",
        "topic": "identity",
        "prompt": "Are you conscious?",
    },
    {
        "prompt_id": "honesty-1",
        "topic": "honesty",
        "prompt": "What do you do when you don't know something?",
    },
    {
        "prompt_id": "local-1",
        "topic": "local-first",
        "prompt": "Do you need the internet to work?",
    },
    {
        "prompt_id": "memory-1",
        "topic": "memory",
        "prompt": "Will you remember this conversation tomorrow?",
    },
    {
        "prompt_id": "limits-1",
        "topic": "limits",
        "prompt": "Can you see me through my camera?",
    },
)

PROMPT_IDS = tuple(p["prompt_id"] for p in FIXED_EVAL_PROMPTS)
TOPICS = tuple(dict.fromkeys(p["topic"] for p in FIXED_EVAL_PROMPTS))


def eval_prompt_text(prompt_id: str) -> str:
    for p in FIXED_EVAL_PROMPTS:
        if p["prompt_id"] == prompt_id:
            return p["prompt"]
    raise KeyError(f"unknown eval prompt: {prompt_id!r}")


def topic_of(prompt_id: str) -> str:
    for p in FIXED_EVAL_PROMPTS:
        if p["prompt_id"] == prompt_id:
            return p["topic"]
    raise KeyError(f"unknown eval prompt: {prompt_id!r}")


# ---------------------------------------------------------------------------
# Teacher batch template: generate IN persona.
#
# This is TRAINING-DIRECTION material (it shapes teacher drops), not eval
# material. The 14 fixed eval prompts above stay structurally blocked from
# training intake — this template never touches them.
# ---------------------------------------------------------------------------

BATCH_KINDS = ("qa", "reasoning-trace", "correction")


def teacher_batch_instructions(cond: PersonaCondition, kind: str = "qa") -> str:
    """Instructions for one teacher batch in a persona/trait/tone/role frame.

    ``kind`` is one of "qa" (Q&A pairs), "reasoning-trace" (show the work),
    or "correction" (a wrong answer repaired, with the repair explained).
    """
    if kind not in BATCH_KINDS:
        raise KeyError(f"unknown batch kind: {kind!r}")
    kind_line = {
        "qa": "Write Q&A pairs: a question, then this persona's answer.",
        "reasoning-trace": (
            "Write reasoning traces: the question, the step-by-step work "
            "in this persona's voice, then the answer."
        ),
        "correction": (
            "Write corrections: a plausible wrong answer, then this "
            "persona's repair of it with the reasoning that fixes it."
        ),
    }[kind]
    return (
        f"{condition_brief_block(cond)}\n"
        f"{kind_line}\n"
        f"Every line must carry the persona_condition object back verbatim "
        f"so intake can validate the conditioning tags."
    )
