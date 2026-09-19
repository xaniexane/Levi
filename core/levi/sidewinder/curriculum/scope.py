"""Scoped views over the curriculum — stdlib only.

A scope is a selector (domains / tracks / levels / ids) plus the full
prerequisite closure beneath it, so every learning path inside the view is
self-contained. Editions (curriculum packs) and agent teams are both built
on scopes: a filtered view over tracks that never dangles.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Set

from levi.sidewinder.curriculum.corpus import Corpus


def _pool_by_id(corpus: Corpus, extra: Iterable[Dict] = ()) -> Dict[str, Dict]:
    pool = list(corpus.entries) + list(extra or ())
    return {e["id"]: e for e in pool}


def closure_ids(by_id: Dict[str, Dict], seeds: Iterable[str]) -> Set[str]:
    """Prerequisite closure over ``seeds`` (ids not in ``by_id`` are ignored)."""
    ids = set(seeds)
    changed = True
    while changed:
        changed = False
        for eid in list(ids):
            entry = by_id.get(eid)
            for pre in entry["prerequisites"] if entry else ():
                if pre not in ids and pre in by_id:
                    ids.add(pre)
                    changed = True
    return ids


def scoped_ids(
    corpus: Corpus,
    extra: Iterable[Dict] = (),
    domains: Iterable[str] = (),
    tracks: Iterable[str] = (),
    levels: Iterable[str] = (),
    ids: Iterable[str] = (),
) -> Set[str]:
    """Ids matching the selector, plus prerequisite closure.

    ``extra``: additional entries (e.g. pack entries) visible for matching
    and prerequisite resolution. An empty selector matches nothing.
    """
    by_id = _pool_by_id(corpus, extra)
    domains, tracks, levels, ids = set(domains), set(tracks), set(levels), set(ids)
    seeds: Set[str] = set()
    if domains or tracks or levels or ids:
        for eid, entry in by_id.items():
            if eid in ids:
                seeds.add(eid)
                continue
            if domains and entry["domain"] not in domains:
                continue
            if tracks and not (set(entry["tracks"]) & tracks):
                continue
            if levels and entry["level"] not in levels:
                continue
            seeds.add(eid)
    return closure_ids(by_id, seeds)


def scoped_corpus(
    corpus: Corpus,
    extra: Iterable[Dict] = (),
    domains: Iterable[str] = (),
    tracks: Iterable[str] = (),
    levels: Iterable[str] = (),
    ids: Iterable[str] = (),
) -> Corpus:
    """The scope as a filtered Corpus view (search/get/progressions work)."""
    by_id = _pool_by_id(corpus, extra)
    ids_set = scoped_ids(corpus, extra=extra, domains=domains, tracks=tracks,
                         levels=levels, ids=ids)
    return Corpus([by_id[eid] for eid in ids_set if eid in by_id])


def filter_corpus(corpus: Corpus, ids: Iterable[str]) -> Corpus:
    """Corpus view restricted to ``ids`` (no closure — ids must be closed)."""
    ids_set = set(ids)
    return Corpus([e for e in corpus.entries if e["id"] in ids_set])
