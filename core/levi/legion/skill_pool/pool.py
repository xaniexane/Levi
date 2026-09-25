"""The ONE shared Legion skill pool — singleton, every member resolves
through the same object. No per-member registries, no copies.

LAW-GUARD-PROVE — the invariants, declared first, enforced in code,
proved by the test suite (never claimed beyond what the tests check):

1. every skill carries a non-empty name, description, and at least one
   trigger keyword;
2. the pool is singleton-shared: ``get_pool() is get_pool()``, and every
   legion crew member plus Nanobit resolve through that one object;
3. discovery ALWAYS surfaces the backend flag — a ``needs-wiring`` skill
   is never presented as executable (``executable_now`` is False and the
   flag is in every result);
6. every skill carries a complete ordered rank ladder (I/II/III);
   ranks merge at load and a missing ladder fails loudly;
7. mastery records only valid ranks inside a skill's ladder — setting
   an out-of-ladder rank fails loudly;
8. cross-domain links are ALWAYS cross-category — same-category skills
   are excluded by definition.

NAMING: all names here are PROVISIONAL and await Chauncey's word —
including the ``I / II / III`` rank names.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .definitions import SKILL_DEFINITIONS
from .ranks import RANKS, SKILL_RANKS

BACKENDS = ("platform-native", "playbook-only", "needs-wiring")

INVARIANTS = (
    "every skill has non-empty name, description, and >=1 trigger",
    "pool is singleton-shared across all legion members and nanobit",
    "find_skill always surfaces the backend flag; needs-wiring never presented as executable",
    "nanobit resolves through this pool, never a private copy",
    "every skill has a complete ordered rank ladder (I/II/III)",
    "mastery rank always within the skill's ladder bounds",
    "cross-domain links are always cross-category",
)

# category -> human domain label used by skills_for
_CATEGORY_LABELS = {
    "comms": "communication and messaging",
    "media": "media creation and content",
    "business": "business and professional work",
    "shopping-travel": "shopping and travel",
    "health": "health and food",
    "files-device": "files and device",
    "dev": "development",
    "learning": "learning and research",
    "meta": "agent meta-capabilities",
    "money-music": "money and music",
    "law": "law and legal work",
    "document-creation": "document creation and authoring",
    "therapeutic": "therapeutic wellness methods",
    "life-balance": "life balance and time management",
}


def _validate(defn: Dict[str, Any]) -> Dict[str, Any]:
    """Enforce invariants 1 and 6 at load: reject (loudly) any definition
    that lacks a name, description, trigger, a legal backend flag, or a
    complete ordered rank ladder."""
    missing = [
        k
        for k in ("id", "name", "description", "category", "backend", "triggers")
        if k not in defn
    ]
    if missing:
        raise ValueError(f"skill definition missing keys {missing}: {defn.get('id')!r}")
    if not str(defn["name"]).strip():
        raise ValueError(f"skill {defn['id']!r} has an empty name")
    if not str(defn["description"]).strip():
        raise ValueError(f"skill {defn['id']!r} has an empty description")
    if not defn["triggers"]:
        raise ValueError(f"skill {defn['id']!r} has no trigger keywords")
    if defn["backend"] not in BACKENDS:
        raise ValueError(
            f"skill {defn['id']!r} has illegal backend {defn['backend']!r}"
        )
    ladder = SKILL_RANKS.get(defn["id"])
    if ladder is None:
        raise ValueError(
            f"skill {defn['id']!r} has no rank ladder in ranks.py — "
            "every skill needs one (invariant 6)"
        )
    if len(ladder) != len(RANKS) or any(not str(r).strip() for r in ladder):
        raise ValueError(
            f"skill {defn['id']!r} has an incomplete rank ladder — "
            f"expected {len(RANKS)} non-empty rungs {RANKS}"
        )
    skill = dict(defn)
    skill["ranks"] = [
        {"rank": rank, "description": rung}
        for rank, rung in zip(RANKS, ladder, strict=True)
    ]
    return skill


# Words too generic to count as a shared "concept" when bridging domains.
_STOPWORDS = frozenset(
    """
    the a an of to for in on and or with is are be by from as at it its
    this that when use your you my me i we our they them their his her
    how what which who not no so do does can will into over under through
    about across between out up down than then also any all more most such
    other some one two new real full own same too very just like get make
    take keep set put run work using used useful needs need should could
    would there here these those than too very can will just don should now
    never always often usually really actually quite rather within without
    during while where why because since until unless although though
    however therefore thus hence plus via etc thing things something
    anything nothing everything part parts way ways much many well back
    still even ever building before questions question task tasks help
    based ask asked want wants give gives given going goes come comes
    start starts first last next every each either neither both few key
    event events end ends side sides
    """.split()
)

_WORD_RE = re.compile(r"[a-z0-9]+")


def _words(text: str) -> set:
    """Significant lowercase words from free text."""
    return {
        w
        for w in _WORD_RE.findall((text or "").lower())
        if len(w) > 2 and w not in _STOPWORDS
    }


def _concepts(skill: Dict[str, Any]) -> set:
    """A skill's concept fingerprint: significant words from its name,
    triggers, and description. Used for cross-domain bridging."""
    parts = [skill.get("name", ""), skill.get("description", "")]
    parts.extend(skill.get("triggers") or ())
    return _words(" ".join(parts))


class SkillPool:
    """The shared pool. Construct once via ``get_pool()``; consumers
    never instantiate their own."""

    def __init__(self, definitions: List[Dict[str, Any]]) -> None:
        seen = set()
        self._skills: List[Dict[str, Any]] = []
        for raw in definitions:
            skill = _validate(raw)
            if skill["id"] in seen:
                raise ValueError(f"duplicate skill id {skill['id']!r}")
            seen.add(skill["id"])
            self._skills.append(skill)

    # -- discovery ------------------------------------------------------

    def list_skills(self) -> List[Dict[str, Any]]:
        """Every skill in the pool, as dicts. Backend flag always present."""
        return [dict(s) for s in self._skills]

    def get(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """Fetch one skill by id; None when unknown."""
        for s in self._skills:
            if s["id"] == skill_id:
                return dict(s)
        return None

    def find_skill(
        self,
        task_text: str,
        include_needs_wiring: bool = True,
    ) -> List[Dict[str, Any]]:
        """Match skills to a task description by trigger keywords.

        Returns scored matches, best first. Every result carries its
        ``backend`` flag and ``executable_now`` — a ``needs-wiring`` skill
        is labeled, never presented as executable (invariant 3).
        """
        text = (task_text or "").lower()
        if not text.strip():
            return []
        scored = []
        for s in self._skills:
            hits = sum(1 for kw in s["triggers"] if kw in text)
            if hits:
                scored.append((hits, s))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        results = []
        for hits, s in scored:
            if s["backend"] == "needs-wiring" and not include_needs_wiring:
                continue
            entry = dict(s)
            entry["match_score"] = hits
            entry["executable_now"] = s["backend"] != "needs-wiring"
            results.append(entry)
        return results

    def skills_for(self, role_or_domain: str) -> List[Dict[str, Any]]:
        """Skills for a crew role or domain. Category match first
        (e.g. 'business', 'media', 'comms'); falls back to keyword
        search when the domain names no category."""
        domain = (role_or_domain or "").lower().strip()
        if not domain:
            return []
        for category, label in _CATEGORY_LABELS.items():
            if (
                domain == category
                or domain in label
                or category in domain.replace(" ", "-")
            ):
                return [dict(s) for s in self._skills if s["category"] == category]
        return self.find_skill(domain)

    def backend_counts(self) -> Dict[str, int]:
        """Honest breakdown: how many skills per backend flag."""
        counts = {b: 0 for b in BACKENDS}
        for s in self._skills:
            counts[s["backend"]] += 1
        return counts

    # -- rank ladders ---------------------------------------------------

    def ranks_for(self, skill_id: str) -> Optional[List[Dict[str, str]]]:
        """The skill's ordered rank ladder — [{"rank", "description"}]
        for rungs I, II, III. None when the skill is unknown."""
        skill = self.get(skill_id)
        if skill is None:
            return None
        return [dict(r) for r in skill["ranks"]]

    def skill_at(self, skill_id: str, rank: str) -> Dict[str, Any]:
        """The skill shaped to one rung of its ladder: the base skill
        plus ``active_rank`` and ``rank_description``. Unknown skills and
        out-of-ladder ranks fail loudly (invariant 7)."""
        skill = self.get(skill_id)
        if skill is None:
            raise ValueError(f"unknown skill {skill_id!r}")
        rung = str(rank or "").upper().strip()
        if rung not in RANKS:
            raise ValueError(
                f"rank {rank!r} is outside the ladder {RANKS} for skill {skill_id!r}"
            )
        shaped = dict(skill)
        shaped["active_rank"] = rung
        shaped["rank_description"] = dict(
            next(r for r in skill["ranks"] if r["rank"] == rung)
        )["description"]
        return shaped

    # -- cross-domain pattern linking -----------------------------------

    def cross_domain_links(
        self, skill_id_or_query: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find skills in DIFFERENT categories that share concepts with
        the anchor — recognizing one thing in a whole other domain and
        connecting the dots.

        Anchor resolution: a skill id anchors directly; otherwise the
        query's top ``find_skill`` matches anchor it; when nothing
        matches, the query's own words anchor the search. Same-category
        skills are EXCLUDED by definition (invariant 8). Every result
        notes the shared concept words and the anchor it bridges from.
        """
        key = (skill_id_or_query or "").strip()
        if not key:
            return []
        anchors: List[Tuple[Optional[Dict[str, Any]], set]] = []
        direct = self.get(key)
        if direct is not None:
            anchors.append((direct, _concepts(direct)))
        else:
            matches = self.find_skill(key)[:3]
            if matches:
                anchors.extend((m, _concepts(m)) for m in matches)
            else:
                anchors.append((None, _words(key)))  # query-word pseudo-anchor
        best: Dict[str, Dict[str, Any]] = {}
        for anchor, awords in anchors:
            anchor_id = anchor["id"] if anchor else "query"
            anchor_cat = anchor["category"] if anchor else None
            for cand in self._skills:
                if anchor is not None and cand["category"] == anchor_cat:
                    continue  # invariant 8: cross-category only
                if anchor is not None and cand["id"] == anchor["id"]:
                    continue
                shared = sorted(awords & _concepts(cand))
                if not shared:
                    continue
                entry = best.get(cand["id"])
                if entry is None or len(shared) > len(entry["shared_patterns"]):
                    best[cand["id"]] = {
                        "skill": dict(cand),
                        "shared_patterns": shared,
                        "anchor": anchor_id,
                        "anchor_category": anchor_cat,
                    }
        ranked = sorted(
            best.values(),
            key=lambda e: (-len(e["shared_patterns"]), e["skill"]["id"]),
        )
        return ranked[: max(limit, 0)]


_pool: Optional[SkillPool] = None


def get_pool() -> SkillPool:
    """The singleton pool — the SAME object for every caller, always.
    Every legion member and Nanobit resolve through this function."""
    global _pool
    if _pool is None:
        _pool = SkillPool(SKILL_DEFINITIONS)
    return _pool


# convenience aliases so callers need not touch the object
def list_skills() -> List[Dict[str, Any]]:
    return get_pool().list_skills()


def find_skill(
    task_text: str, include_needs_wiring: bool = True
) -> List[Dict[str, Any]]:
    return get_pool().find_skill(task_text, include_needs_wiring=include_needs_wiring)


def skills_for(role_or_domain: str) -> List[Dict[str, Any]]:
    return get_pool().skills_for(role_or_domain)


def ranks_for(skill_id: str) -> Optional[List[Dict[str, str]]]:
    """A skill's ordered rank ladder (I, II, III). None when unknown."""
    return get_pool().ranks_for(skill_id)


def skill_at(skill_id: str, rank: str) -> Dict[str, Any]:
    """A skill shaped to one rung of its ladder. Fails loudly on
    unknown skills or out-of-ladder ranks."""
    return get_pool().skill_at(skill_id, rank)


def cross_domain_links(skill_id_or_query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Skills in OTHER categories sharing concepts with the anchor —
    connecting the dots across domains. Same-category excluded."""
    return get_pool().cross_domain_links(skill_id_or_query, limit=limit)
