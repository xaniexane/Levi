"""thread-sense: conversational proprioception for LEVI.

Most chatbots remember the last N turns. LEVI feels the *shape* of the
conversation — living threads whose salience decays and reignites, entities
with lightweight coreference, open loops the organism owes, and semantic
recall over its own history. An immune sense flags contradictions.

Components:
    state   -- DialogueState: threads, entities, open loops, session facts
    recall  -- semantic recall over the conversation's own history
    guard   -- contradiction sense (flags, never censors)
    render  -- compact prompt block + the conversation constellation
"""

from levi.convo.state import DialogueState
from levi.convo.recall import recall_turns
from levi.convo.guard import check_contradictions, extract_claims
from levi.convo.render import render_block, render_constellation

__all__ = [
    "DialogueState",
    "recall_turns",
    "check_contradictions",
    "extract_claims",
    "render_block",
    "render_constellation",
]
