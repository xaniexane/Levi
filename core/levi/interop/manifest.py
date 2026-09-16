"""Static capability manifest for LEVI modules.

The existing modules cannot be edited (additive-only), so their
``provides``/``requires`` declarations live here as pure data. Each entry is
a module name → ``{"provides": [...], "requires": [...]}``.

Capability names use the ``<module>.<thing>`` convention so that
``requires`` targets are unambiguous module names — the registry validates
that every ``requires`` target is a registered module (deny-closed).

This file is the single place to update when a module gains or drops a
capability. Future modules that *can* be edited should declare themselves
via :func:`levi.interop.registry.register` at import time instead.
"""

from __future__ import annotations

DECLARATIONS = {
    # -- the substrate: everything reads and writes through here ------------
    "memory-store": {
        "provides": ["memory.write", "memory.read", "memory.list"],
        "requires": [],
    },
    # -- retrieval: the ranker that upgrades every read path ----------------
    "memory-retrieval": {
        "provides": ["memory.retrieval.hybrid", "memory.retrieval.bm25"],
        "requires": ["memory-store"],
    },
    # -- rag: cited answers over the substrate -------------------------------
    "rag": {
        "provides": ["rag.ask", "rag.cited-context"],
        "requires": ["memory-store", "memory-retrieval"],
    },
    # -- agent assistant: prompts and user-context loading -------------------
    "agent-assistant": {
        "provides": ["assistant.prompt", "assistant.user-context"],
        "requires": ["memory-store", "memory-retrieval"],
    },
    # -- bot services: the service registry incl. research-brief ------------
    "bot-services": {
        "provides": ["bot.services", "bot.research-brief"],
        "requires": ["memory-store", "rag", "agent-assistant"],
    },
    # -- growth: baby Levi's harvest → reflect → consolidate → journal loop --
    "growth": {
        "provides": ["growth.journal", "growth.cycle"],
        "requires": ["memory-store"],
    },
    # -- academy: courses → concepts → spaced repetition ---------------------
    "academy": {
        "provides": ["academy.concepts", "academy.sessions"],
        "requires": [],
    },
    # -- bounty: defensive recon findings ------------------------------------
    "bounty": {
        "provides": ["bounty.findings"],
        "requires": [],
    },
    # -- knowledge: dated queryable corpora (courses/news/security) -----------
    "knowledge": {
        "provides": ["knowledge.corpus", "knowledge.news", "knowledge.security"],
        "requires": ["academy", "bounty"],
    },
    # -- oath: identity / trust substrate ------------------------------------
    "oath": {
        "provides": ["oath.identity", "oath.trust"],
        "requires": [],
    },
    # -- organs: Echoverse / Mandella / REIM / RIEM (Builder A) ---------------
    "organs": {
        "provides": [
            "organs.echoverse",
            "organs.mandella",
            "organs.reim",
            "organs.riem",
        ],
        "requires": ["memory-store", "growth"],
    },
}


def load_into(registry) -> None:
    """Register every static declaration into *registry* (a
    :class:`levi.interop.registry.Registry`)."""
    for name, decl in DECLARATIONS.items():
        registry.register(
            name,
            provides=decl.get("provides", ()),
            requires=decl.get("requires", ()),
        )
