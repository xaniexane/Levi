"""LEVI bot — a bold, high-energy conversational surface over the LEVI core.

100% LEVI: it wears no other brand, borrows no other identity.

Submodules:
- :mod:`levi.bot.persona` — the "spark" voice card, identity answers,
  and the kindness guardrail.
- :mod:`levi.bot.chat` — one-shot :func:`say` and an interactive REPL,
  wired into the agent runtime with an honest offline fallback.
"""

from __future__ import annotations

from levi.bot.persona import (
    PERSONA,
    answer_identity_question,
    check_no_mask,
    kindness_guardrail,
    render_system_prompt,
)

__all__ = [
    "PERSONA",
    "answer_identity_question",
    "check_no_mask",
    "kindness_guardrail",
    "render_system_prompt",
]
