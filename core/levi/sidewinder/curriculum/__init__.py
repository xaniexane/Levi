"""The COURSE: training curriculum (content layer).

This package is the curriculum — what trains agents — as distinct from the
platform (``levi.sidewinder.platform``), which is the infrastructure that
delivers it. Contents:

* ``schema`` — entry schema + the crisis-domain law.
* ``corpus`` — JSONL loader, dedup, keyword search.
* ``progressions`` — leveled progressions, learning paths, graph checks.
* ``scope`` — selector + prerequisite-closure views (editions, teams).
* ``editions`` — manifest-driven curriculum packs (career fields).
* ``growth`` — batch growth pipeline: the content engine.
* ``corpus/`` — the data: domain-sharded JSONL entries.
* ``seeds/`` — intake queue, roadmap, writer stubs.
* ``edition_packs/`` — edition manifests (Chauncey authors these).
"""

from __future__ import annotations
