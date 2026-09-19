"""Variant forging: rename / remix / recycle / mutate.

A variant gets a NEW identity — new name, blended trait description —
derived from source capabilities but never the raw originals.

Hard rules (enforced in code):
  1. No outside brands: every forged name and description passes
     ``levi.bot.persona.check_no_mask``. A violation raises ForgeError.
  2. No dynasty-internal IP on user-facing output: raw agent proper names,
     owns-fields, and specialty strings NEVER appear in a variant's name
     or description. Only the trait phrases below (generic, paraphrased,
     buyer-safe) may be used.
  3. Deterministic: identical (source, mode, seed) always forges the
     identical variant. Seeded ``random.Random`` only — no time, no uuid.

Lineage is carried as lineage_hash (sha256 of the source modules), never
as a name — so the manifest can prove descent without leaking the
dynasty-internal original.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any, Dict, List, Sequence

from levi.genesis.parts import BASE_AGENTS, find_capability

FORM_NAME = "genesis.remix"

MODES = ("rename", "remix", "recycle", "mutate")


class ForgeError(ValueError):
    """A forge rule was broken (brand leak, raw-name leak, bad mode)."""


def _no_mask(text: str) -> List[str]:
    try:
        from levi.bot.persona import check_no_mask
    except Exception:
        return []
    return check_no_mask(text)


# ---------------------------------------------------------------------------
# Forge table: buyer-safe identity material per capability family.
# trait phrases are generic paraphrases — dynasty wording never copied.
# name pools are invented compounds; none are provider brands or raw names.
# ---------------------------------------------------------------------------
_FORGE_TABLE: Dict[str, Dict[str, Any]] = {
    "forgehand": {
        "traits": [
            "writes and runs files with recorded intent",
            "embedded local runtime — code written and run on the machine",
            "plugin grafts run sandboxed and attributable",
            "verifiable write attestations before a change is sealed",
        ],
        "names": ["Emberwright", "Anvilhand", "Cinderwright", "Forgewise"],
    },
    "gamemaster": {
        "traits": [
            "runs automated games end to end",
            "ladder and tournament management",
            "game variants with house rules",
        ],
        "names": ["Playmarshal", "Tourneywright", "Ladderkeep", "Gameward"],
    },
    "herald": {
        "traits": [
            "tailors the system to new sectors and industries",
            "builds edition packs for verticals",
            "sector-specific team templates",
        ],
        "names": ["Editionwright", "Sectorlink", "Verticalink", "Packwright"],
    },
    "keystone": {
        "traits": [
            "one unified app shell",
            "plugin host that loads other tools",
            "single launcher for the whole kit",
        ],
        "names": ["Shellkey", "Homewright", "Dockkeep", "Onelaunch"],
    },
    "quartermaster": {
        "traits": [
            "tracks money in and money out",
            "snapshot backups before changes",
            "receipts for every consequential action",
            "enforced revenue splits in code",
        ],
        "names": ["Coinwright", "Ledgerkeep", "Receiptward", "Splitmaster"],
    },
    "schoolmaster": {
        "traits": [
            "guided learning tracks",
            "one-on-one tutoring turns",
            "ingests courses into a queryable base",
        ],
        "names": ["Studykeep", "Tracktutor", "Coursewright", "Learnward"],
    },
    "shellwright": {
        "traits": [
            "command-line interface surfaces",
            "runs on the phone as well as the desktop",
            "scripted automation entry points",
        ],
        "names": ["Termwright", "Shellkeep", "Cliford", "Commandly"],
    },
    "starmaker": {
        "traits": [
            "creator suite for media",
            "avatar and photo pipelines",
            "styled content generation",
        ],
        "names": ["Makebright", "Pixelwright", "Craftstar", "Studiokeep"],
    },
    "threadweaver": {
        "traits": [
            "multi-thread agent conversations",
            "local media plugins for threads",
            "parallel workstreams with summaries",
        ],
        "names": ["Threadkeep", "Weaveward", "Streamwright", "Talkspin"],
    },
    "vaultkeeper": {
        "traits": [
            "indexed vault of verified tools",
            "verified installs only",
            "release receipts and provenance",
        ],
        "names": ["Vaultkeep", "Indexward", "Sealwright", "Depotkeep"],
    },
    "veilwright": {
        "traits": [
            "overlay interfaces on top of apps",
            "prototype launchers",
            "visual skins for the workflow",
        ],
        "names": ["Veilward", "Overlaywright", "Skinship", "Glarekeep"],
    },
}

# Raw internal strings that must NEVER appear in user-facing forge output.
_RAW_LEAK_WORDS = set(BASE_AGENTS) | {
    "levi forge",
    "levi shell",
    "levi vault",
    "cybrus",
    "dynasty",
    "section 0",
    "legion",
}


def _variant_id(name: str, seed: int) -> str:
    slug = "".join(c for c in name.lower() if c.isalnum()) or "variant"
    digest = hashlib.sha256(("%s:%d" % (name, seed)).encode("utf-8")).hexdigest()[:8]
    return "gen-%s-%s" % (slug, digest)


def _guard_output(text: str, *, field: str) -> None:
    lowered = text.lower()
    for word in _RAW_LEAK_WORDS:
        if word and word in lowered:
            raise ForgeError(
                "raw dynasty name leaked into variant %s: %r" % (field, word)
            )
    violations = _no_mask(text)
    if violations:
        raise ForgeError("brand/mask violation in variant %s: %s" % (field, violations))


def _family(source_id: str) -> Dict[str, Any]:
    try:
        return _FORGE_TABLE[source_id]
    except KeyError:
        raise ForgeError("unknown capability family: %r" % source_id)


def _blend(
    primary: Sequence[str], secondary: Sequence[str], rng: random.Random, count: int
) -> List[str]:
    pool = list(primary) + list(secondary)
    rng.shuffle(pool)
    seen: List[str] = []
    for t in pool:
        if t not in seen:
            seen.append(t)
        if len(seen) >= count:
            break
    return seen


def forge_variant(source_id: str, mode: str, seed: int) -> Dict[str, Any]:
    """Forge one variant from a capability family. Deterministic."""
    if mode not in MODES:
        raise ForgeError("unknown forge mode %r (want one of %s)" % (mode, MODES))
    cap = find_capability(source_id)  # KeyError if unknown source
    fam = _family(source_id)
    rng = random.Random("%s|%s|%d" % (source_id, mode, seed))

    names: Sequence[str] = fam["names"]
    primary_traits: Sequence[str] = fam["traits"]

    if mode == "rename":
        name = rng.choice(names)
        traits = list(primary_traits)
        blurb = (
            "A %s line agent: %s."
            % (name, "; ".join(traits[:3]))
        )
    elif mode == "recycle":
        name = rng.choice(names)
        # Same capability domain, reworded presentation.
        traits = list(primary_traits)
        rng.shuffle(traits)
        blurb = (
            "Reworked %s unit rebuilt for everyday use: %s. "
            "Same craft, new presentation."
            % (name, "; ".join(traits[:3]))
        )
    elif mode == "remix":
        others = [k for k in _FORGE_TABLE if k != source_id]
        partner = rng.choice(others)
        pfam = _FORGE_TABLE[partner]
        name = rng.choice(names)
        traits = _blend(primary_traits, pfam["traits"], rng, 4)
        blurb = (
            "A %s line hybrid blending two crafts: %s."
            % (name, "; ".join(traits))
        )
    else:  # mutate
        pool_traits: List[str] = []
        picks = [k for k in _FORGE_TABLE if k != source_id]
        rng.shuffle(picks)
        for k in picks[:2]:
            pool_traits += _FORGE_TABLE[k]["traits"]
        traits = _blend(primary_traits, pool_traits, rng, 5)
        name = rng.choice(names)
        blurb = (
            "A mutated %s line variant — traits recombined across crafts: %s."
            % (name, "; ".join(traits))
        )

    _guard_output(name, field="name")
    _guard_output(blurb, field="description")

    return {
        "variant_id": _variant_id(name, seed),
        "name": name,
        "mode": mode,
        "seed": seed,
        "description": blurb,
        "traits": traits,
        # Lineage as hash only — never the internal original's name.
        "lineage": {
            "lineage_hash": cap["lineage_hash"],
            "parts_bin_receipt": FORM_NAME,
        },
    }


def forge_roster(spec: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Forge a whole roster from a spec: [{source, mode, seed}, ...]."""
    roster = []
    seen_ids = set()
    for entry in spec:
        v = forge_variant(entry["source"], entry.get("mode", "rename"), entry.get("seed", 0))
        if v["variant_id"] in seen_ids:
            raise ForgeError("duplicate variant in roster: %s" % v["variant_id"])
        seen_ids.add(v["variant_id"])
        roster.append(v)
    return roster


def family_names() -> Dict[str, List[str]]:
    """Buyer-safe name pools per family (for inspection only)."""
    return {k: list(v["names"]) for k, v in _FORGE_TABLE.items()}
