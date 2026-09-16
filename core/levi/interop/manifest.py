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
    # -- methods: 40 forgotten techniques (stdlib-only, local-first) ---------
    "methods": {
        "provides": [
            "methods.ach",
            "methods.bruno",
            "methods.chappe",
            "methods.codebook",
            "methods.colon",
            "methods.commonplace",
            "methods.deming",
            "methods.duplex",
            "methods.edgenotch",
            "methods.florilegia",
            "methods.franklin",
            "methods.ivylee",
            "methods.kardex",
            "methods.kriegsspiel",
            "methods.llull",
            "methods.loci",
            "methods.monitorial",
            "methods.morphological",
            "methods.mundaneum",
            "methods.opsroom",
            "methods.optical",
            "methods.pecia",
            "methods.pinakes",
            "methods.pneumatic",
            "methods.prowords",
            "methods.qcodes",
            "methods.quipu",
            "methods.randgame",
            "methods.ratio",
            "methods.repertory",
            "methods.t5",
            "methods.therbligs",
            "methods.tickler",
            "methods.tironian",
            "methods.triplebook",
            "methods.trivium",
            "methods.triz",
            "methods.uniterm",
            "methods.vsm",
            "methods.waterlogic",
        ],
        "requires": [],
    },
    # -- revival: retired software reborn as original LEVI works (wave 1+2) --
    "revival": {
        "provides": [
            "revival.agenda",
            "revival.arexx",
            "revival.bfs",
            "revival.blackboard",
            "revival.ecco",
            "revival.eros",
            "revival.eurisko",
            "revival.goap",
            "revival.groove",
            "revival.inferno",
            "revival.interlisp",
            "revival.linkbase",
            "revival.mumps",
            "revival.notes",
            "revival.otp",
            "revival.plan9",
            "revival.soar",
            "revival.soups",
            "revival.telescript",
            "revival.xanadu",
        ],
        "requires": [],
    },
    # -- galaxy: ecosystem packaging / registry / install / services ---------
    "galaxy": {
        "provides": [
            "galaxy.packages",
            "galaxy.services",
            "galaxy.install",
            "galaxy.capabilities",
        ],
        "requires": [],
    },
    # -- lifepack: portable LEVI state (export/import/validate) ---------------
    "lifepack": {
        "provides": [
            "lifepack.export",
            "lifepack.import",
            "lifepack.validate",
        ],
        "requires": ["memory-store"],
    },
    # -- bloodstream: the one-turn pipeline + event bus -----------------------
    "bloodstream": {
        "provides": [
            "bloodstream.turn",
            "bloodstream.trace",
            "bloodstream.bus",
            "bloodstream.composites",
            "bloodstream.gate",
        ],
        "requires": ["memory-store", "organs"],
    },
    # -- daemon: control plane — automations, heartbeat, kernel ---------------
    "daemon": {
        "provides": [
            "daemon.automations",
            "daemon.heartbeat",
            "daemon.kernel",
            "daemon.unified",
        ],
        "requires": [],
    },
    # -- perpetual: the never-stops engine — hunt, pulse, supervision ---------
    "perpetual": {
        "provides": [
            "perpetual.hunt",
            "perpetual.pulse",
            "perpetual.supervise",
        ],
        "requires": ["archive"],
    },
    # -- archive: the Smithsonian records (dated queryable corpus) ------------
    "archive": {
        "provides": [
            "archive.records",
            "archive.search",
            "archive.ingest",
        ],
        "requires": [],
    },
    # -- cyber-skills: 823 original defensive blue-team playbooks -------------
    "cyber-skills": {
        "provides": ["skills.cyber-playbooks"],
        "requires": [],
    },
    # -- factory: the production line (constructive software cascade) ---------
    "factory": {
        "provides": [
            "factory.create",
            "factory.projects",
        ],
        "requires": [],
    },
    # -- finance: AI-powered paper-trading intelligence (paper-only) -----------
    "finance": {
        "provides": [
            "finance.quote",
            "finance.signals",
            "finance.portfolio",
            "finance.paper-broker",
        ],
        "requires": [],
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
