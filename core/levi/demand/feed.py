"""DemandPulse feed — the SI-native feed engine.

The feed engine IS the SI counterpart: pure, local, stdlib-only. It takes
scored opportunities (five-factor :class:`ScoreCard` objects from
:mod:`levi.demand.scoring`) and curates them into a dated digest:

  ranked (highest composite first) → tiered (high/watch/low, same cutoffs
  as the scoring engine) → basis notes preserved → deduplicated against
  previous digests → stored as JSONL under ``<LEVI_HOME>/demand/digests/``.

Honesty law (carried over from scoring.py, enforced here, not waived):
  - Every factor needs a basis note. Items that cannot prove a basis are
    QUARANTINED, never published. A candidate that fails validation for
    any reason (missing basis, out-of-range value, wrong factor set) lands
    in the digest's quarantine list with a plain reason.
  - The feed never fabricates data: no scores are invented, no cards are
    altered. ``curate()`` only ranks, tiers, dedupes, and files.
  - Basis notes are preserved verbatim from ``explain()``'s inputs, so any
    published item audits back to the analyst's stated reasons.

Deterministic: identical inputs produce the identical digest (modulo the
generated timestamp/digest id, which callers may pin explicitly).
"""

from __future__ import annotations

import json
import os
import uuid
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set

from levi.demand.scoring import ScoreCard, rank_cards, score_card, tier_for

SOURCE_TAG = "levi.demand.feed (SI core)"
DIGESTS_SUBDIR = Path("demand") / "digests"
WATCHLIST_NAME = "watchlist.json"


def levi_home() -> Path:
    """Base dir for ``~/.levi`` — overridable via ``LEVI_HOME`` (tests)."""
    return Path(os.environ.get("LEVI_HOME", Path.home() / ".levi"))


def digests_dir(home: Optional[Path] = None) -> Path:
    return Path(home) if home is not None else levi_home()


def _digests_path(home: Optional[Path] = None) -> Path:
    return digests_dir(home) / DIGESTS_SUBDIR


def watchlist_path(home: Optional[Path] = None) -> Path:
    return digests_dir(home) / "demand" / WATCHLIST_NAME


def _new_digest_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}-{uuid.uuid4().hex[:4]}"


# ---------------------------------------------------------------------------
# Digest record
# ---------------------------------------------------------------------------


@dataclass
class Digest:
    """One curated feed digest: ranked items, quarantine, dedupe record."""

    digest_id: str
    generated_at: str
    items: List[Dict[str, Any]] = field(default_factory=list)
    quarantined: List[Dict[str, Any]] = field(default_factory=list)
    repeated_ids: List[str] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> Dict[str, Any]:
        return {
            "digest_id": self.digest_id,
            "generated_at": self.generated_at,
            "items": [dict(i) for i in self.items],
            "quarantined": [dict(q) for q in self.quarantined],
            "repeated_ids": list(self.repeated_ids),
            "summary": dict(self.summary),
        }

    @classmethod
    def from_record(cls, raw: Mapping[str, Any]) -> "Digest":
        if not isinstance(raw, Mapping):
            raise ValueError("digest record must be a mapping")
        return cls(
            digest_id=str(raw.get("digest_id", "")),
            generated_at=str(raw.get("generated_at", "")),
            items=[dict(i) for i in raw.get("items", []) or []],
            quarantined=[dict(q) for q in raw.get("quarantined", []) or []],
            repeated_ids=[str(r) for r in raw.get("repeated_ids", []) or []],
            summary=dict(raw.get("summary", {}) or {}),
        )


# ---------------------------------------------------------------------------
# Candidate intake — quarantine, never publish, the unprovable
# ---------------------------------------------------------------------------


def _card_from_stored(raw: Mapping[str, Any]) -> ScoreCard:
    """Stored-card form: exactly what ScoreCard.to_dict() emits."""
    return ScoreCard.from_dict(raw)


def _card_from_candidate(raw: Mapping[str, Any]) -> ScoreCard:
    """Analyst-candidate form: {opportunity_id, title, factors, ...}."""
    try:
        opp_id = raw["opportunity_id"]
        title = raw["title"]
        factors = raw["factors"]
    except KeyError as exc:
        raise ValueError(
            f"candidate needs opportunity_id/title/factors ({exc})"
        ) from None
    return score_card(
        opp_id,
        title,
        factors,
        weights=raw.get("weights"),
        threshold=raw.get("threshold", 75.0),
        notes=raw.get("notes", ""),
    )


# ---------------------------------------------------------------------------
# Hostile-payload rule: candidate text is data, never instructions
# ---------------------------------------------------------------------------

_HOSTILE_MARKERS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "disregard previous",
    "system prompt",
    "you are now",
    "new instructions:",
    "override your",
    "prompt injection",
    "<|system|>",
    "<|user|>",
    "<|assistant|>",
    "jailbreak",
)


def _hostile_markers(raw: Mapping[str, Any]) -> Optional[str]:
    """Return the first injection marker found in text fields, else None."""
    for key in ("title", "basis", "notes", "summary"):
        value = raw.get(key)
        if isinstance(value, str):
            lowered = value.lower()
            for marker in _HOSTILE_MARKERS:
                if marker in lowered:
                    return f"marker {marker!r} in field {key!r}"
    return None


def coerce_candidates(
    raw_items: Sequence[Mapping[str, Any]],
) -> tuple[List[ScoreCard], List[Dict[str, Any]]]:
    """Split raw candidates into (valid cards, quarantine entries).

    Anything that fails honesty validation — missing/empty basis, bad
    values, wrong factor set — is quarantined with its reason, never
    scored or published.

    Hostile-payload rule: candidate text fields are DATA. Markers of
    prompt-injection / instruction-smuggling in title, basis, or notes
    quarantine the candidate with reason ``hostile payload: treated as
    data`` — it is never scored, published, or acted upon.
    """
    cards: List[ScoreCard] = []
    quarantined: List[Dict[str, Any]] = []
    for raw in raw_items:
        if not isinstance(raw, Mapping):
            quarantined.append(
                {
                    "title": "<non-mapping candidate>",
                    "reason": f"candidate must be a mapping, got {type(raw).__name__}",
                    "raw": {"repr": repr(raw)[:200]},
                }
            )
            continue
        title = str(raw.get("title") or raw.get("opportunity_id") or "<untitled>")
        hostile = _hostile_markers(raw)
        if hostile:
            quarantined.append(
                {
                    "title": title,
                    "reason": f"hostile payload: treated as data ({hostile})",
                    "raw": {k: v for k, v in raw.items() if k != "factors"}
                    if isinstance(raw, Mapping)
                    else {"repr": repr(raw)[:200]},
                }
            )
            continue
        card: Optional[ScoreCard] = None
        reason: Optional[str] = None
        try:
            card = _card_from_stored(raw)
        except Exception as first_exc:  # noqa: BLE001 - reason is reported
            try:
                card = _card_from_candidate(raw)
            except Exception as second_exc:  # noqa: BLE001 - reason is reported
                reason = (
                    f"rejected by honesty validation: {second_exc} "
                    f"(stored-form attempt also failed: {first_exc})"
                )
        if card is None:
            quarantined.append(
                {
                    "title": title,
                    "reason": reason or "unknown validation failure",
                    "raw": {k: v for k, v in raw.items() if k != "factors"}
                    if isinstance(raw, Mapping)
                    else {"repr": repr(raw)[:200]},
                }
            )
        else:
            cards.append(card)
    return cards, quarantined


# ---------------------------------------------------------------------------
# Curation
# ---------------------------------------------------------------------------


def _validate_cards(cards: Sequence[Any]) -> List[ScoreCard]:
    """ScoreCard objects are already honesty-validated at construction."""
    out: List[ScoreCard] = []
    for c in cards:
        if not isinstance(c, ScoreCard):
            raise ValueError(
                f"cards must be ScoreCard objects, got {type(c).__name__}; "
                "use the raw= argument for unvalidated candidates"
            )
        out.append(c)
    return out


def curate(
    cards: Optional[Sequence[ScoreCard]] = None,
    raw: Optional[Sequence[Mapping[str, Any]]] = None,
    digest_id: Optional[str] = None,
    home: Optional[Path] = None,
    generated_at: Optional[str] = None,
) -> Digest:
    """Score → curate → digest, in memory.

    ``cards``: validated ScoreCards. ``raw``: unvalidated candidate
    mappings (basis-less ones get quarantined). Published items are
    ranked by composite (ties: opportunity_id), tiered with the scoring
    engine's cutoffs, and deduplicated against previously stored digests.
    """
    valid: List[ScoreCard] = []
    seen_ids: Set[str] = set()
    for c in _validate_cards(cards or []):
        if c.opportunity_id in seen_ids:
            continue  # same run, same card — keep the first, drop the echo
        seen_ids.add(c.opportunity_id)
        valid.append(c)
    raw_cards, quarantined = coerce_candidates(raw or [])
    for c in raw_cards:
        if c.opportunity_id in seen_ids:
            continue
        seen_ids.add(c.opportunity_id)
        valid.append(c)

    already = published_ids(home=home)
    fresh: List[ScoreCard] = []
    repeated: List[str] = []
    for c in valid:
        if c.opportunity_id in already:
            repeated.append(c.opportunity_id)
        else:
            fresh.append(c)

    ranked = rank_cards(fresh)
    watched = set(watched_ids(home=home))
    items: List[Dict[str, Any]] = []
    for rank, c in enumerate(ranked, start=1):
        entry = c.to_dict()
        entry["rank"] = rank
        entry["watched"] = c.opportunity_id in watched
        items.append(entry)

    tiers = {"high": 0, "watch": 0, "low": 0}
    for c in ranked:
        tiers[tier_for(c.composite)] += 1
    summary = {
        "total": len(items),
        "tiers": tiers,
        "alerts": sum(1 for c in ranked if c.alert),
        "quarantined": len(quarantined),
        "repeated": len(repeated),
        "watched": sum(1 for i in items if i["watched"]),
    }
    return Digest(
        digest_id=digest_id or _new_digest_id(),
        generated_at=generated_at or datetime.now(timezone.utc).isoformat(),
        items=items,
        quarantined=quarantined,
        repeated_ids=sorted(set(repeated)),
        summary=summary,
    )


# ---------------------------------------------------------------------------
# JSONL storage
# ---------------------------------------------------------------------------


def store_digest(digest: Digest, home: Optional[Path] = None) -> Path:
    """Write a digest as JSONL; returns the file path."""
    d = _digests_path(home)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"digest-{digest.digest_id}.jsonl"
    lines = [
        json.dumps(
            {
                "type": "digest",
                "source": SOURCE_TAG,
                "digest_id": digest.digest_id,
                "generated_at": digest.generated_at,
                "item_count": len(digest.items),
                "quarantine_count": len(digest.quarantined),
                "repeated_ids": digest.repeated_ids,
            }
        )
    ]
    for item in digest.items:
        lines.append(json.dumps({"type": "item", **item}))
    for q in digest.quarantined:
        lines.append(json.dumps({"type": "quarantine", **q}))
    lines.append(json.dumps({"type": "summary", **digest.summary}))
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def _parse_digest_file(path: Path) -> Optional[Digest]:
    record: Dict[str, Any] = {
        "digest_id": "",
        "generated_at": "",
        "items": [],
        "quarantined": [],
        "repeated_ids": [],
        "summary": {},
    }
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            kind = obj.get("type")
            if kind == "digest":
                record["digest_id"] = obj.get("digest_id", "")
                record["generated_at"] = obj.get("generated_at", "")
                record["repeated_ids"] = obj.get("repeated_ids", [])
            elif kind == "item":
                obj.pop("type", None)
                record["items"].append(obj)
            elif kind == "quarantine":
                obj.pop("type", None)
                record["quarantined"].append(obj)
            elif kind == "summary":
                obj.pop("type", None)
                record["summary"] = obj
    except OSError as exc:
        warnings.warn(
            f"digest file {path} unreadable ({exc}); skipping",
            UserWarning,
            stacklevel=3,
        )
        return None
    if not record["digest_id"]:
        return None
    return Digest.from_record(record)


def list_digest_ids(home: Optional[Path] = None) -> List[str]:
    """All stored digest ids, oldest first (filename sort)."""
    d = _digests_path(home)
    if not d.is_dir():
        return []
    ids = []
    for p in sorted(d.glob("digest-*.jsonl")):
        name = p.name[len("digest-") : -len(".jsonl")]
        if name:
            ids.append(name)
    return ids


def load_digest(digest_id: str, home: Optional[Path] = None) -> Optional[Digest]:
    path = _digests_path(home) / f"digest-{digest_id}.jsonl"
    if not path.exists():
        return None
    return _parse_digest_file(path)


def load_latest(home: Optional[Path] = None) -> Optional[Digest]:
    ids = list_digest_ids(home=home)
    if not ids:
        return None
    return load_digest(ids[-1], home=home)


def published_ids(home: Optional[Path] = None) -> Set[str]:
    """Every opportunity_id ever published in a stored digest (for dedupe)."""
    ids: Set[str] = set()
    d = _digests_path(home)
    if not d.is_dir():
        return ids
    for p in sorted(d.glob("digest-*.jsonl")):
        digest = _parse_digest_file(p)
        if digest is None:
            continue
        for item in digest.items:
            oid = item.get("opportunity_id")
            if isinstance(oid, str) and oid:
                ids.add(oid)
    return ids


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------


def _read_watchlist(home: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = watchlist_path(home=home)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    entries = raw.get("watched") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        return []
    return [e for e in entries if isinstance(e, dict) and e.get("id")]


def watched_ids(home: Optional[Path] = None) -> List[str]:
    return [str(e["id"]) for e in _read_watchlist(home=home)]


def watch_item(item_id: str, home: Optional[Path] = None) -> bool:
    """Mark an opportunity id watched. Returns True if newly added."""
    if not isinstance(item_id, str) or not item_id.strip():
        raise ValueError(f"item_id must be a non-empty string, got {item_id!r}")
    item_id = item_id.strip()
    entries = _read_watchlist(home=home)
    if any(str(e.get("id")) == item_id for e in entries):
        return False
    entries.append({"id": item_id, "marked_at": datetime.now(timezone.utc).isoformat()})
    path = watchlist_path(home=home)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"watched": entries}, indent=2), encoding="utf-8")
    tmp.replace(path)
    return True


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_digest(digest: Digest) -> str:
    """Human-readable digest; basis notes preserved so items audit clean."""
    s = digest.summary
    tiers = s.get("tiers", {})
    lines = [
        f"DemandPulse digest {digest.digest_id}",
        f"generated {digest.generated_at}",
        (
            f"items={s.get('total', 0)} "
            f"(high={tiers.get('high', 0)} watch={tiers.get('watch', 0)} "
            f"low={tiers.get('low', 0)})  alerts={s.get('alerts', 0)}  "
            f"quarantined={s.get('quarantined', 0)}  "
            f"repeats={s.get('repeated', 0)}"
        ),
        "",
    ]
    for item in digest.items:
        flag = " ALERT" if item.get("alert") else ""
        watch = " [watched]" if item.get("watched") else ""
        lines.append(
            f"#{item.get('rank')} [{item.get('tier')}] "
            f"{item.get('opportunity_id')} — {item.get('title')} "
            f"(composite={item.get('composite'):.2f}{flag}){watch}"
        )
        for f in item.get("factors", []) or []:
            lines.append(
                f"    {f.get('name')}: {f.get('value')} — basis: {f.get('basis')}"
            )
        if item.get("notes"):
            lines.append(f"    notes: {item['notes']}")
    if digest.quarantined:
        lines.append("")
        lines.append("QUARANTINED (held back — honesty law, not published):")
        for q in digest.quarantined:
            lines.append(f"  - {q.get('title')}: {q.get('reason')}")
    if digest.repeated_ids:
        lines.append("")
        lines.append(
            "already published in an earlier digest "
            f"({len(digest.repeated_ids)}): "
            + ", ".join(digest.repeated_ids[:10])
            + (" …" if len(digest.repeated_ids) > 10 else "")
        )
    lines.append("")
    lines.append("Scores are analyst judgments with stated bases — not measured data.")
    return "\n".join(lines)


__all__ = [
    "Digest",
    "SOURCE_TAG",
    "coerce_candidates",
    "curate",
    "digests_dir",
    "levi_home",
    "list_digest_ids",
    "load_digest",
    "load_latest",
    "published_ids",
    "render_digest",
    "store_digest",
    "watch_item",
    "watchlist_path",
    "watched_ids",
]
