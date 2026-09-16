"""Weekly digest generator: seeded serendipity + anti-filter-bubble rules.

The digest is deliberately NOT optimized. Selection works in passes:

1. **Eligibility**: drop items picked in the last ``no_repeat_weeks``
   (history in ``<home>/history.json``).
2. **Unseen preference**: items never picked before sort before
   previously-picked ones — the ritual surfaces the neglected, not the
   popular. (There is no popularity signal at all; "unseen" is the only
   bias, and it points outward.)
3. **Seeded shuffle**: within each preference tier, order is a
   random shuffle with an EXPLICIT seed (default: derived from the week
   label, so a week is reproducible; overridable via ``--seed``). The
   seed is printed in the digest — the randomness is inspectable.
4. **Diversity caps**: at most ``per_kind_cap`` items of one kind and
   ``per_tag_cap`` items sharing a tag. When a pick would break a cap,
   it is skipped with the reason recorded.

Every pick carries a ``why`` line: ``seeded serendipity``, ``unseen
item``, or ``diversity fill`` — honest about the mechanism, never
pretending to "know what you'll love".

Output: markdown digest, written to ``<home>/digests/<week>.md`` and
returned as text. Shareable as a plain file — no account, no platform.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .items import DiscoverError

__all__ = [
    "Digest",
    "generate_digest",
    "current_week_label",
    "default_home",
    "week_seed",
]

PICKS_PER_DIGEST = 7
PER_KIND_CAP = 2
PER_TAG_CAP = 3
NO_REPEAT_WEEKS = 8


def default_home() -> Path:
    override = os.environ.get("LEVI_HOME")
    base = Path(override) if override else Path(os.path.expanduser("~/.levi"))
    return base / "discover"


def current_week_label(today: Optional[date] = None) -> str:
    today = today or date.today()
    iso_year, iso_week, _ = today.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def week_seed(week_label: str) -> int:
    """Deterministic seed from the week label — reproducible rituals."""
    digest = hashlib.sha256(f"levi-discover:{week_label}".encode()).hexdigest()
    return int(digest[:16], 16)


class Digest(Dict[str, Any]):
    """The generated digest (dict with week/seed/picks/reasons)."""


def _history_path(home: Path) -> Path:
    return home / "history.json"


def _load_history(home: Path) -> Dict[str, List[str]]:
    path = _history_path(home)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_history(home: Path, history: Dict[str, List[str]]) -> None:
    home.mkdir(parents=True, exist_ok=True)
    path = _history_path(home)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(history, indent=2), encoding="utf-8")
    tmp.replace(path)


def _recently_picked(history: Dict[str, List[str]], week_label: str,
                     window: int = NO_REPEAT_WEEKS) -> set[str]:
    """Ids picked in the recent window of week labels (lexicographic ≈ chronological)."""
    if window <= 0:
        return set()
    weeks = sorted(history)
    recent = [w for w in weeks if w <= week_label][-window:]
    out: set[str] = set()
    for w in recent:
        out.update(history[w])
    return out


def generate_digest(
    items: List[Dict[str, Any]],
    week_label: str,
    home: Optional[Path] = None,
    *,
    seed: Optional[int] = None,
    count: int = PICKS_PER_DIGEST,
    per_kind_cap: int = PER_KIND_CAP,
    per_tag_cap: int = PER_TAG_CAP,
    no_repeat_weeks: int = NO_REPEAT_WEEKS,
) -> Tuple[Digest, str]:
    """Generate the week's digest. Returns (digest, markdown)."""
    if not items:
        raise DiscoverError("generate_digest: no items to pick from")
    home = Path(home) if home else default_home()
    home.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(home, 0o700)
    except OSError:
        pass
    seed = week_seed(week_label) if seed is None else seed
    rng = random.Random(seed)

    history = _load_history(home)
    if week_label in history:
        raise DiscoverError(
            f"digest for {week_label} already exists "
            f"({home}/digests/{week_label}.md) — delete it to regenerate"
        )
    blocked = _recently_picked(history, week_label, window=no_repeat_weeks)
    ever_picked = {i for ids in history.values() for i in ids}

    eligible = [it for it in items if it["id"] not in blocked]
    if not eligible:
        raise DiscoverError(
            "every item was picked in the recent window — "
            "nothing eligible; use --seed to force a different shuffle or "
            "lower the no-repeat window"
        )
    unseen = [it for it in eligible if it["id"] not in ever_picked]
    seen_before = [it for it in eligible if it["id"] in ever_picked]
    unseen_ids = {it["id"] for it in unseen}
    rng.shuffle(unseen)
    rng.shuffle(seen_before)
    ordered = unseen + seen_before  # outward bias, then randomness

    picks: List[Dict[str, Any]] = []
    kind_counts: Dict[str, int] = {}
    tag_counts: Dict[str, int] = {}
    skipped = 0
    for it in ordered:
        if len(picks) >= count:
            break
        kind = it["kind"]
        if kind_counts.get(kind, 0) >= per_kind_cap:
            skipped += 1
            continue
        tags = it["tags"]
        if any(tag_counts.get(t, 0) >= per_tag_cap for t in tags):
            skipped += 1
            continue
        why = ("unseen item — surfacing the neglected"
               if it["id"] in unseen_ids else "seeded serendipity")
        picks.append({**it, "why": why})
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        for t in tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1

    digest: Digest = Digest({
        "week": week_label,
        "seed": seed,
        "generated_at": time.time(),
        "picks": picks,
        "corpus_size": len(items),
        "eligible": len(eligible),
        "skipped_by_diversity_caps": skipped,
        "rules": {
            "per_kind_cap": per_kind_cap,
            "per_tag_cap": per_tag_cap,
            "no_repeat_weeks": no_repeat_weeks,
            "mechanism": "seeded shuffle + unseen preference + diversity caps; no engagement signals exist",
        },
    })
    markdown = _render_markdown(digest)

    digests_dir = home / "digests"
    digests_dir.mkdir(parents=True, exist_ok=True)
    (digests_dir / f"{week_label}.md").write_text(markdown, encoding="utf-8")
    history[week_label] = [p["id"] for p in picks]
    _save_history(home, history)
    return digest, markdown


def _render_markdown(digest: Digest) -> str:
    lines = [
        f"# Discover Weekly — {digest['week']}",
        "",
        f"_A ritual over your own corpus. Seed `{digest['seed']}` — reproducible, "
        "inspectable randomness. No engagement signals were used or exist._",
        "",
        f"_{digest['eligible']} eligible of {digest['corpus_size']} items; "
        f"{digest['skipped_by_diversity_caps']} skipped by diversity caps._",
        "",
    ]
    for i, p in enumerate(digest["picks"], 1):
        tags = " ".join(f"#{t}" for t in p["tags"])
        lines.append(f"## {i}. {p['title']}")
        lines.append(f"*{p['kind']} · {p['source']}* {tags}".rstrip())
        if p.get("blurb"):
            lines.append(f"> {p['blurb']}")
        if p.get("added_at"):
            lines.append(f"_in your corpus since {p['added_at']}_")
        lines.append(f"_why this is here: {p['why']}_")
        lines.append("")
    lines += [
        "---",
        "_LEVI discover: the anti-Discover-Weekly. Your library, your ritual, "
        "no catalog license, no filter bubble._",
    ]
    return "\n".join(lines).rstrip() + "\n"
