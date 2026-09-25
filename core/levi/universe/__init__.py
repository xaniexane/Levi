"""The universe architecture: LEVI's theme-park map in code.

Canon source: docs/LEXICON.md, "The ultimate goal" (Chauncey's word,
2026-09-20) — the universe, the hub, software reimagined, "totally the
keeper's. Like an AI theme park." The large groupings of intelligence
forms take their names from the Legion.

Canon -> module map (nothing here renames anything; names are Chauncey's):

- The park itself          -> this package (``levi.universe``)
- Omega: the entrance and
  the platform            -> ``entrance`` (wraps the Omega revival organs:
                           ``levi.revival.omega.reasoning`` /
                           ``levi.revival.omega.nexus`` / blueprint /
                           generators). Alpha built it and keeps it
                           running -> the builder's deliberation enters
                           through the same call path.
- Alpha: the builder       -> the build crew rides inside ``entrance``
                           (``levi.alpha.reason`` + the Omega generators
                           as Alpha's build organ); see
                           ``entrance.build_crew()``.
- The star: a role, not
  a name — the overall
  companion, the chat,
  the mascot              -> ``star``. The role is filled by the product
                           companion, which bears Rex's name and persona
                           (Chauncey's word, 2026-09-20).
- The large groupings of
  intelligence forms       -> ``groupings``. Forms take their names from
                           the Legion: hives, schools, packs, herds,
                           flocks. Registry is propose-only — essences
                           only, names are Chauncey's; the eleven stay
                           sealed (no names, no order).

Everything in one, offline-first: the entrance's call path runs through
the real Omega organs; the registry and the star role are stdlib-only.
"""

from . import entrance, groupings, star

__all__ = ["entrance", "groupings", "star"]

# The park's fixed nodes: canon name -> module path. A second source of
# truth would rot; this table is the map and the docstring above is its
# prose twin.
PARK_MAP = {
    "park": "levi.universe",
    "entrance": "levi.universe.entrance",  # Omega: entrance and platform
    "builder": "levi.alpha.reason + levi.revival.omega.generators",
    "star": "levi.universe.star",  # the star: a role, not a name
    "groupings": "levi.universe.groupings",  # Legion groupings registry
}
