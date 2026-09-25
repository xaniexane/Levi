"""The ONE shared skill pool for all of Legion — plus Nanobit.

Chauncey's orders (2026-09-22): "add what you have to nano bit and legion",
"let all of legion have a skill pool", "they all use [it]". One pool,
shared — no per-member copies. Every legion crew member and Nanobit resolve
skills through ``get_pool()``, the same singleton object.

NAMING: every name introduced here is PROVISIONAL and awaits Chauncey's
word — the pool, the module, the "backend" flag vocabulary, the id scheme,
and the ``I / II / III`` rank names.

HONEST BACKEND FLAGS (discovery always surfaces these):
- ``platform-native``: executable locally with stdlib / repo internals,
  no external service. (4 skills)
- ``playbook-only``: pure guidance/framework — usable as instructions now,
  no backend needed. (47 skills)
- ``needs-wiring``: requires a real connector, credential, device, or
  external service that does not exist in this repo yet. Discovery labels
  these; they are NEVER presented as executable. (29 skills)

RANK LADDERS: every skill carries a depth ladder (I/II/III) — sub-ranks
below, upper ranks above — merged from ``ranks.py`` at load. A missing
ladder fails loudly.

MEMBER MASTERY: members (Legion crew seat keys / roles, see
``levi.legion.team``) hold skills at ranks; ``mastery`` resolves what a
member can execute. In-memory registry with a documented path to
persistence — no database.

CROSS-DOMAIN LINKING: ``cross_domain_links`` finds skills in OTHER
categories sharing concepts with the anchor — one thing recognized in a
whole other domain, dots connected. Same-category excluded by definition.

ENGINE MAPPING: ``engine_map`` maps Chauncey's Omega engines (proposed /
essence from his screenshots, NOT canon) to pool skills — honest links,
explicit unmapped findings, never silent. See ``engine_map`` for the
source-status warning.

Data-driven: skills are plain dicts in ``definitions.py`` — no
hand-wired per-skill code paths. Adding a skill means adding a dict
(plus its ladder in ``ranks.py``).
"""

from . import mastery
from .engine_map import (
    ENGINE_INVARIANTS,
    coverage_report,
    engines_for,
    skills_for_engine,
    unmapped_engines,
)
from .pool import (
    BACKENDS,
    INVARIANTS,
    SkillPool,
    cross_domain_links,
    find_skill,
    get_pool,
    list_skills,
    ranks_for,
    skill_at,
    skills_for,
)
from .ranks import RANKS

__all__ = [
    "BACKENDS",
    "ENGINE_INVARIANTS",
    "INVARIANTS",
    "RANKS",
    "SkillPool",
    "coverage_report",
    "cross_domain_links",
    "engines_for",
    "find_skill",
    "get_pool",
    "list_skills",
    "mastery",
    "ranks_for",
    "skill_at",
    "skills_for",
    "skills_for_engine",
    "unmapped_engines",
]
