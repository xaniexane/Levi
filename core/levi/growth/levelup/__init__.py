"""Nanobit + Legion level-up training layer.

The training-game layer on top of the baby Levi growth loop
(harvest -> reflect -> consolidate -> journal): scored replies and
questions award EXP through a hash-chained receipt ledger, levels are
a pure function of cumulative EXP, daily question goals rotate across
the 11 SOXI subjects with monotone topic progression, and level-ups
are journaled.

Honest boundary: this scores and motivates training — it does not
train brain weights itself. "Can do now" vs "needs more training".
"""

from __future__ import annotations

from .adjudication import (
    active_abilities,
    active_penalties,
    adjudication_path,
    append_adj,
    confiscated_exp,
    earned_tokens,
    read_adj,
    verify_adj,
)
from .anticheat import (
    MAX_DAILY_QUOTA,
    MAX_QUESTION_EXP,
    MAX_REPLIES_PER_DAY,
    MAX_REPLY_EXP,
    apply_penalty,
    daily_cap,
    detect,
    effective_exp,
    levels_after_penalty,
    locate_tamper,
    reverse_penalty,
)
from .exp import award_reply, reply_exp, score_reply
from .goals import (
    SUBJECTS,
    answer_question,
    ensure_goal,
    get_goal,
    next_topic,
    plan_subjects,
    topic_counter,
)
from .intensity import INTENSITY_MULTIPLIERS, INTENSITY_NAMES, multiplier, name
from .levels import (
    exp_to_next,
    level_for,
    maybe_level_up,
    threshold,
)
from .multistep import award_question, question_exp
from .receipts import (
    award_exp,
    entity_total,
    ledger_path,
    levelup_dir,
    read_receipts,
    verify_chain,
)
from .unlocks import ABILITIES, ability_status, maybe_unlock

__all__ = [
    "ABILITIES",
    "SUBJECTS",
    "INTENSITY_MULTIPLIERS",
    "INTENSITY_NAMES",
    "MAX_DAILY_QUOTA",
    "MAX_QUESTION_EXP",
    "MAX_REPLIES_PER_DAY",
    "MAX_REPLY_EXP",
    "ability_status",
    "active_abilities",
    "active_penalties",
    "adjudication_path",
    "answer_question",
    "append_adj",
    "apply_penalty",
    "award_exp",
    "award_question",
    "award_reply",
    "confiscated_exp",
    "daily_cap",
    "detect",
    "earned_tokens",
    "effective_exp",
    "ensure_goal",
    "entity_total",
    "exp_to_next",
    "get_goal",
    "ledger_path",
    "level_for",
    "levels_after_penalty",
    "levelup_dir",
    "locate_tamper",
    "maybe_level_up",
    "maybe_unlock",
    "multiplier",
    "name",
    "next_topic",
    "plan_subjects",
    "question_exp",
    "read_adj",
    "read_receipts",
    "reply_exp",
    "reverse_penalty",
    "score_reply",
    "threshold",
    "topic_counter",
    "verify_adj",
    "verify_chain",
]
