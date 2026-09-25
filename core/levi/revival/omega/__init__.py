"""omega: Chauncey's Omega Platform, resurrected as LEVI-native organs.

Omega (2026) was Chauncey's all-in-one AI automation platform: a skill
catalog, a job search/apply pipeline, browser automation, HITL checkpoints,
chat, an API, a CLI — and at its heart, **Echo** (the Blueprint Architect:
natural language → architecture blueprint → JSON spec) and **Alpha** (the
no-code compiler: blueprints → working generators), routed through
**Nexus** (multi-model inference with modes and confidence scores).

The platform died as unmaintained code in a Drive archive. What lives on
here is not its code — every module below is written from scratch as
LEVI's own — but its *organs*, the mechanisms that made it his:

- ``blueprint`` (Echo): prompt → product-type detection → architecture
  blueprint → validated JSON spec. Echo designs.
- ``generators`` (Alpha): a registry of product generators that compile a
  blueprint into real scaffolds (webpage, CLI, API, MCP server). Alpha
  builds.
- ``nexus`` (Nexus): mode-aware, confidence-scored routing across
  providers. Nexus chooses.

Already absorbed elsewhere in LEVI (not duplicated here): DemandPulse
scoring lives in ``levi.demand``, the job pipeline tracker lives in
``levi.jobs``, standing skills live in ``levi.skill``.

Deliberately no package-level exports: import the organ you need.
"""
