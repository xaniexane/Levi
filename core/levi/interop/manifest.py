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
    # -- finance: SI-powered paper-trading intelligence (paper-only) -----------
    "finance": {
        "provides": [
            "finance.quote",
            "finance.signals",
            "finance.portfolio",
            "finance.paper-broker",
        ],
        "requires": [],
    },
    # -- forge: LEVI's own code home — local git hosting + collaboration -------
    "forge": {
        "provides": [
            "forge.repos",
            "forge.issues",
            "forge.prs",
            "forge.ci",
            "forge.export",
            "forge.serve",
        ],
        "requires": [],
    },
    # -- operator wave: LEVI's operating layer (signals, creed, ledgers) ------
    # Twelve LEVI-native packages: the graded signal plane, the frozen creed
    # of laws and tone masks, and the ledgers/rituals that make LEVI a
    # reliable operator. All stdlib-only, local-first.
    "signals": {
        "provides": [
            "signals.grades",
            "signals.instincts",
            "signals.focus-mute",
            "signals.active-hours",
        ],
        # wires the nine documented accountability instincts as defaults
        "requires": [
            "commitments",
            "decisions",
            "drift",
            "energy",
            "friction",
            "interruptions",
            "promises",
            "sweeps",
            "teachback",
        ],
    },
    "creed": {
        "provides": [
            "creed.laws",
            "creed.masks",
            "creed.promotion",
        ],
        "requires": [],
    },
    "promises": {
        "provides": [
            "promises.tracker",
            "promises.fulfillment",
        ],
        "requires": [],
    },
    "decisions": {
        "provides": [
            "decisions.journal",
            "decisions.revisit",
        ],
        "requires": [],
    },
    "interruptions": {
        "provides": [
            "interruptions.ledger",
            "interruptions.noise-roi",
        ],
        "requires": [],
    },
    "snapshots": {
        "provides": [
            "snapshots.capture",
            "snapshots.resume",
        ],
        "requires": [],
    },
    "drift": {
        "provides": [
            "drift.tracker",
            "drift.evidence",
        ],
        "requires": [],
    },
    "teachback": {
        "provides": [
            "teachback.model",
            "teachback.corrections",
        ],
        "requires": [],
    },
    "energy": {
        "provides": [
            "energy.tracker",
            "energy.peak-hours",
        ],
        "requires": [],
    },
    "friction": {
        "provides": [
            "friction.log",
            "friction.themes",
        ],
        "requires": [],
    },
    "sweeps": {
        "provides": [
            "sweeps.sweep",
            "sweeps.safe-fix",
        ],
        "requires": [],
    },
    "premortem": {
        "provides": [
            "premortem.ritual",
            "premortem.mitigations",
        ],
        "requires": [],
    },
    # -- copper: scored timed choreography (perpetual-hunt wave-004) ------------
    # The Amiga Copper's pattern, clean-room native: declarative
    # WAIT/EXEC/SKIP instruction scores against a real or simulated clock,
    # zero timers and zero callbacks, with an honest Receipt of every event.
    # For supervision recovery sequences and bounded-simulation replay.
    "copper": {
        "provides": [
            "copper.score",
        ],
        "requires": [],
    },
    # -- verify: pre-digital verification rituals (perpetual-hunt wave-006) -----
    # The desk-machine proof discipline, clean-room native: cast-out-nines /
    # cast-out-elevens digit checks, ledger crossfooting, dual-path agreement,
    # and honest significant figures. Every check returns a deny-closed
    # VerificationReceipt — a failed proof never silently passes.
    "verify": {
        "provides": [
            "verify.checks",
        ],
        "requires": [],
    },
    # -- games: fair-play local games (perpetual-hunt games wave) ---------------
    # Every game passes the Fair Play Charter (charter.py): no paid
    # randomness, no streak punishment, no FOMO timers, free hints,
    # offline-first, portable player-owned saves.
    "games": {
        "provides": [
            "games.charter",
            "games.codebreak",
            "games.daily-cipher",
            "games.hotseat",
            "games.saves",
        ],
        "requires": [],
    },
    # -- telegraph: the telegraph office (perpetual-hunt wave-001) -------------
    # Dead comms protocols reborn as original LEVI works: FidoNet-style
    # store-and-forward envelopes, Telex WRU answerback identity,
    # AppleTalk NBP-style accountless chooser. Envelopes are data, never
    # executed; owner-only dirs; no network daemon or cloud.
    "telegraph": {
        "provides": [
            "telegraph.envelopes",
            "telegraph.identity",
            "telegraph.directory",
        ],
        "requires": [],
    },
    # -- shelf: the share shelf (perpetual-hunt daily 2026-09-16: fallen
    # platforms) ----------------------------------------------------------------
    # Google Reader's shared shelf (share-with-note, starred canon) + Digg's
    # bury as a first-class reversible negative signal, revived as a
    # local-first portable curation desk. Complements feedreader
    # (subscriptions); never re-reads feeds.
    "shelf": {
        "provides": [
            "shelf.items",
            "shelf.bundles",
        ],
        "requires": [],
    },
    # -- feedlab: feed-ranking transparency lab (giant-patterns hunt) --------
    # The giants refuse to disclose how their rankers score you. feedlab
    # inverts the trade: a fully disclosed engagement-bait scoring model
    # applied to the user's OWN posts — every signal, weight, and point
    # contribution visible. Educational simulation; never claims to match
    # any real platform's ranker.
    "feedlab": {
        "provides": [
            "feedlab.rank",
            "feedlab.audit",
            "feedlab.flags",
            "feedlab.compare",
        ],
        "requires": [],
    },
    # -- research: public-source deep-web research (polite, no darknet) -------
    "research": {
        "provides": [
            "research.deepweb",
            "research.sitemaps",
            "research.feeds",
        ],
        "requires": [],
    },
    # -- additions wave: 19 LEVI-native social/craft packages -----------------
    # Built as additions (never rebuilds): portable social fabric and
    # sovereign instruments, stdlib-only, local-first.
    "ephemera": {
        "provides": [
            "ephemera.channels",
            "ephemera.true-delete",
        ],
        "requires": [],
    },
    "feedreader": {
        "provides": [
            "feedreader.reader",
            "feedreader.feeds",
        ],
        "requires": ["research"],
    },
    "liberation": {
        "provides": [
            "liberation.ledger",
            "liberation.hostage-score",
            "liberation.tasks",
        ],
        "requires": [],
    },
    "packs": {
        "provides": [
            "packs.packs",
            "packs.scopes",
        ],
        "requires": [],
    },
    "commitments": {
        "provides": [
            "commitments.devices",
            "commitments.checkin",
        ],
        "requires": [],
    },
    "recap": {
        "provides": [
            "recap.year",
            "recap.digest",
        ],
        "requires": [],
    },
    "classifieds": {
        "provides": [
            "classifieds.listings",
            "classifieds.trust-graph",
        ],
        "requires": [],
    },
    "dials": {
        "provides": [
            "dials.dials",
            "dials.ranking",
        ],
        "requires": [],
    },
    "bridging": {
        "provides": [
            "bridging.legitimacy",
            "bridging.consensus",
        ],
        "requires": [],
    },
    "communities": {
        "provides": [
            "communities.model",
            "communities.portable",
        ],
        "requires": [],
    },
    "threads": {
        "provides": [
            "threads.trees",
            "threads.bridging-rank",
        ],
        "requires": ["bridging"],
    },
    "charters": {
        "provides": [
            "charters.charters",
            "charters.governance",
        ],
        "requires": ["communities"],
    },
    "capproto": {
        "provides": [
            "capproto.protocol",
            "capproto.tokens",
            "capproto.transport",
        ],
        # capability tokens descend from the telescript revival
        "requires": ["revival"],
    },
    "mailtriage": {
        "provides": [
            "mailtriage.triage",
            "mailtriage.replies",
        ],
        "requires": [],
    },
    "vaults": {
        "provides": [
            "vaults.vaults",
            "vaults.retention",
            "vaults.transfer",
        ],
        "requires": [],
    },
    "canvas": {
        "provides": [
            "canvas.artifacts",
            "canvas.workbench",
        ],
        "requires": [],
    },
    "discover": {
        "provides": [
            "discover.digest",
            "discover.rituals",
        ],
        "requires": [],
    },
    "presence": {
        "provides": [
            "presence.rooms",
            "presence.discovery",
        ],
        "requires": [],
    },
    "honestsearch": {
        "provides": [
            "honestsearch.index",
            "honestsearch.rank",
        ],
        "requires": ["research"],
    },
    "recommender": {
        "provides": [
            "recommender.engine",
            "recommender.interest-graph",
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
