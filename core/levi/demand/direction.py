"""DemandPulse direction layer — life-coach / personal-refinement sense.

Sits alongside the engine's opportunity scoring: where scoring asks
"how strong is this signal?", direction asks "does it point where
Chauncey is actually headed?" The two combine into a verdict
(pursue / watch / drop) with the math shown, and a plain-speech coach
brief renders where he's headed, what's aligned, what's drift, and one
rule-derived refinement nudge.

INVARIANTS (law-guard-prove — enforced by the tests in
tests/test_demand_direction.py):
  1. Deterministic: the same signal text + the same profile produces the
     identical score, every time. No randomness, no hidden state, no
     clock reads inside scoring paths.
  2. Transparent: every direction-fit score carries its reasons — which
     direction items matched, which terms fired, the arithmetic. No
     black-box numbers.
  3. Real signals only: direction never invents signals; it only
     re-weights what the engine actually sensed (DemandSignal /
     Opportunity / ScoreCard records passed in by the caller).
  4. Profile is data, not fate: the direction profile lives in an
     editable JSON data file
     (core/levi/demand/data/direction.json). His word edits the file;
     scoring reads the file, never code constants. ``build_seed_profile``
     is a one-time documented snapshot of his stated goals (sourced from
     ~/workspace/goals/*/GOAL.md on 2026-09-23) used only by
     ``direction --reseed`` to (re)write that file. After seeding, the
     JSON file is the source of truth.
  5. No network in scoring: scoring paths are pure functions of
     (signal text, profile). stdlib only.

Advisory: a fit score describes alignment with stated direction; it
executes nothing and moves no money.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

PROFILE_PATH = Path(__file__).resolve().parent / "data" / "direction.json"

_WEIGHT_EPS = 1e-9

# Verdict bands on the combined score (0.5 * opportunity + 0.5 * fit).
VERDICT_PURSUE = 0.65  # combined >= 0.65 -> pursue
VERDICT_WATCH = 0.40  # combined >= 0.40 -> watch, else drop

# Coach-brief bands.
ALIGNED_FIT = 0.5  # signal fit >= 0.5 counts as aligned
DRIFT_FIT = 0.3  # pursuit fit < 0.3 counts as drift


@dataclass(frozen=True)
class DirectionItem:
    """One named direction: weight + match terms + the why in his words."""

    id: str
    name: str
    weight: float
    terms: Tuple[str, ...]
    why: str

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError(f"direction id must be a non-empty string, got {self.id!r}")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("direction name must be a non-empty string")
        if (
            isinstance(self.weight, bool)
            or not isinstance(self.weight, (int, float))
            or not 0.0 <= float(self.weight) <= 1.0
        ):
            raise ValueError(
                f"direction {self.id!r}: weight must be a number in [0, 1], "
                f"got {self.weight!r}"
            )
        if not self.terms or not isinstance(self.terms, (tuple, list)):
            raise ValueError(
                f"direction {self.id!r}: terms must be a non-empty list"
            )
        for t in self.terms:
            if not isinstance(t, str) or not t.strip():
                raise ValueError(
                    f"direction {self.id!r}: every term must be a non-empty "
                    f"string, got {t!r}"
                )
        if not isinstance(self.why, str) or not self.why.strip():
            raise ValueError(
                f"direction {self.id!r}: why is required — a direction "
                "without his stated reason is rejected"
            )
        object.__setattr__(self, "terms", tuple(t.strip().lower() for t in self.terms))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "weight": float(self.weight),
            "terms": list(self.terms),
            "why": self.why,
        }


@dataclass(frozen=True)
class DirectionProfile:
    """The editable direction profile: a weighted set of directions."""

    items: Tuple[DirectionItem, ...]

    def __post_init__(self) -> None:
        if not self.items:
            raise ValueError("profile must contain at least one direction item")
        ids = [i.id for i in self.items]
        if len(set(ids)) != len(ids):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            raise ValueError(f"direction ids must be unique; duplicates: {dupes}")
        total = sum(float(i.weight) for i in self.items)
        if abs(total - 1.0) > _WEIGHT_EPS:
            raise ValueError(
                f"direction weights must sum to 1.0, got {total:.6f}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {"items": [i.to_dict() for i in self.items]}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "DirectionProfile":
        if not isinstance(raw, Mapping):
            raise ValueError("profile must be a mapping with an 'items' list")
        items = raw.get("items")
        if not isinstance(items, list):
            raise ValueError("profile mapping needs an 'items' list")
        return cls(
            items=tuple(
                DirectionItem(
                    id=d["id"],
                    name=d["name"],
                    weight=d["weight"],
                    terms=tuple(d["terms"]),
                    why=d["why"],
                )
                for d in items
            )
        )

    def save(self, path: Union[str, Path] = PROFILE_PATH) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        tmp.replace(path)
        return path

    @classmethod
    def load(cls, path: Union[str, Path] = PROFILE_PATH) -> "DirectionProfile":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"direction profile not found at {path} — seed it with: "
                "python -m levi.demand direction --reseed"
            )
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"direction profile at {path} is not valid JSON: {exc}"
            ) from None
        return cls.from_dict(raw)


def build_seed_profile() -> DirectionProfile:
    """One-time snapshot of his stated goals as of 2026-09-23.

    Sourced from the Description fields of ~/workspace/goals/*/GOAL.md —
    his words, encoded as match terms, nothing invented. Used ONLY by
    ``direction --reseed`` to (re)write the JSON data file; scoring
    paths never call this. After seeding, edit the JSON file — his word
    changes the file, code never hardcodes his life.
    """
    return DirectionProfile(
        items=(
            DirectionItem(
                id="levi-self-sufficiency",
                name="LEVI self-sufficiency",
                weight=0.25,
                terms=(
                    "offline", "local-first", "self-sufficient", "train",
                    "training", "brain", "weights", "records", "provider",
                    "on-device", "termux", "synthetic intelligence",
                ),
                why=(
                    "His standing mission: 'Success in SI where AI fails' — "
                    "learn off the big models now, need them never."
                ),
            ),
            DirectionItem(
                id="demandpulse-product",
                name="DemandPulse as product and compass",
                weight=0.20,
                terms=(
                    "demandpulse", "demand", "signal", "scoring", "customer",
                    "product", "direction", "compass", "pulse", "opportunity",
                ),
                why=(
                    "Ship DemandPulse as the $6 customer product; Chauncey "
                    "2026-09-23: DemandPulse is the main source of direction "
                    "on long absences."
                ),
            ),
            DirectionItem(
                id="baby-levi-growth",
                name="Baby LEVI growth loop",
                weight=0.15,
                terms=(
                    "growth", "harvest", "reflect", "consolidate", "journal",
                    "memory", "learn", "nightly", "boot camp",
                ),
                why=(
                    "Nightly 3:19 AM CDT harvest→reflect→consolidate→journal; "
                    "growth writes only learnings and journal entries."
                ),
            ),
            DirectionItem(
                id="legion-universe",
                name="Legion universe launch",
                weight=0.15,
                terms=(
                    "legion", "creature", "creatures", "ip", "nft", "launch",
                    "universe", "coin", "ascent", "card",
                ),
                why="Push his creature and creation IP out under Legion — for we are many.",
            ),
            DirectionItem(
                id="originals-lineage",
                name="Originals and lineage",
                weight=0.15,
                terms=(
                    "original", "originals", "lineage", "recovery", "archive",
                    "preserve", "provenance", "grok", "chat history",
                ),
                why=(
                    "Originals-first rule: pull his originals before drafting "
                    "anything; nothing-thrown-away law."
                ),
            ),
            DirectionItem(
                id="dynasty-production",
                name="Dynasty program production",
                weight=0.10,
                terms=(
                    "dynasty", "mvp", "production", "rollout", "wave",
                    "agent", "agents", "hardening",
                ),
                why=(
                    "Five-phase dynasty program: the eleven-agent wave, ten "
                    "MVPs, production hardening with money and rollout."
                ),
            ),
        )
    )


def _check01(name: str, value: float) -> float:
    """Public-boundary 0-1 check: rejects garbage, never silently clamps."""
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not 0.0 <= float(value) <= 1.0
    ):
        raise ValueError(f"{name} must be a number in [0, 1], got {value!r}")
    return float(value)


def _signal_text(signal: Union[str, Any]) -> str:
    """Extract the text to score: a raw string, or a DemandSignal's need."""
    if isinstance(signal, str):
        text = signal
    else:
        need = getattr(signal, "need", None)
        if not isinstance(need, str):
            raise ValueError(
                "signal must be a string or carry a string .need attribute, "
                f"got {type(signal).__name__}"
            )
        text = need
    if not text.strip():
        raise ValueError("signal text must be a non-empty string")
    return text


def _matched_terms(text: str, terms: Tuple[str, ...]) -> List[str]:
    """Terms firing in ``text``: case-insensitive whole-word/phrase match.

    Deterministic: terms are checked in profile order, matches returned
    sorted for stable output.
    """
    lowered = text.lower()
    hits = []
    for term in terms:
        if re.search(r"\b" + re.escape(term) + r"\b", lowered):
            hits.append(term)
    return sorted(hits)


@dataclass(frozen=True)
class FitResult:
    """The auditable result of scoring one signal against the profile."""

    signal_text: str
    score: float
    reasons: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_text": self.signal_text,
            "score": self.score,
            "reasons": [dict(r) for r in self.reasons],
        }

    def explain(self) -> str:
        lines = [
            f"direction-fit score={self.score:.4f}",
            f"signal: {self.signal_text[:100]}",
        ]
        for r in self.reasons:
            if r.get("item") is None:
                lines.append(f"  note: {r['note']}")
                continue
            lines.append(
                f"  [{r['item']}] {r['name']}: weight={r['weight']:.2f} "
                f"item_fit={r['item_fit']:.4f} contrib={r['contribution']:.4f}"
            )
            lines.append(f"    terms matched: {', '.join(r['terms_matched'])}")
        return "\n".join(lines)


def direction_fit(
    signal: Union[str, Any], profile: DirectionProfile
) -> FitResult:
    """Score a sensed signal's alignment with the direction profile.

    Pure function: same text + same profile -> identical result.
    score = sum over items of weight_i * (matched_terms_i / total_terms_i),
    so it always lands in [0, 1]. Every result carries >= 1 reason.
    """
    if not isinstance(profile, DirectionProfile):
        raise ValueError(
            f"profile must be a DirectionProfile, got {type(profile).__name__}"
        )
    text = _signal_text(signal)
    reasons: List[Dict[str, Any]] = []
    total = 0.0
    for item in profile.items:
        hits = _matched_terms(text, item.terms)
        item_fit = len(hits) / len(item.terms)
        contrib = float(item.weight) * item_fit
        total += contrib
        if hits:
            reasons.append(
                {
                    "item": item.id,
                    "name": item.name,
                    "weight": round(float(item.weight), 4),
                    "terms_matched": hits,
                    "item_fit": round(item_fit, 4),
                    "contribution": round(contrib, 4),
                }
            )
    if not reasons:
        reasons.append(
            {
                "item": None,
                "name": None,
                "note": "no direction terms matched in signal text",
            }
        )
    return FitResult(
        signal_text=text[:300], score=round(total, 4), reasons=tuple(reasons)
    )


def verdict(opportunity_score: float, fit_score: float) -> Dict[str, Any]:
    """Combine the engine's opportunity score with direction fit.

    combined = 0.5 * opportunity_score + 0.5 * fit_score.
    Bands: combined >= 0.65 -> pursue; >= 0.40 -> watch; else drop.
    The math is returned in the result so the verdict is auditable.
    """
    opp = _check01("opportunity_score", opportunity_score)
    fit = _check01("fit_score", fit_score)
    combined = round(0.5 * opp + 0.5 * fit, 4)
    if combined >= VERDICT_PURSUE:
        label = "pursue"
    elif combined >= VERDICT_WATCH:
        label = "watch"
    else:
        label = "drop"
    return {
        "opportunity_score": opp,
        "direction_fit": fit,
        "combined": combined,
        "math": f"0.5*{opp:.4f} + 0.5*{fit:.4f} = {combined:.4f}",
        "verdict": label,
    }


def coach_brief(
    profile: DirectionProfile,
    signals: List[Mapping[str, Any]],
    pursuits: List[Mapping[str, Any]],
    as_of: Optional[str] = None,
) -> str:
    """Render the plain-speech coach brief. Pure: no clock, no I/O.

    ``signals``: sensed items, each {"id", "text", "opportunity_score"}.
    ``pursuits``: what he's actively pursuing, each {"title",
    "opportunity_score"}.

    Nudge rule (stated in the output): the highest direction-fit sensed
    signal with no active pursuit. Rule-derived, never invented.
    """
    if not isinstance(profile, DirectionProfile):
        raise ValueError(
            f"profile must be a DirectionProfile, got {type(profile).__name__}"
        )
    for name, seq in (("signals", signals), ("pursuits", pursuits)):
        if not isinstance(seq, (list, tuple)):
            raise ValueError(f"{name} must be a list, got {type(seq).__name__}")

    def _fit_of(text: str) -> float:
        return direction_fit(text, profile).score

    def _opp_of(entry: Mapping[str, Any]) -> Optional[float]:
        raw = entry.get("opportunity_score")
        if raw is None:
            return None  # unscored: shown as-is, never invented
        return _check01("opportunity_score", raw)

    headed = sorted(profile.items, key=lambda i: (-float(i.weight), i.id))[:3]

    scored_signals = []
    for s in signals:
        if not isinstance(s, Mapping) or not str(s.get("text", "")).strip():
            raise ValueError(f"signal entries need non-empty 'text': {s!r}")
        scored_signals.append(
            {
                "id": str(s.get("id", "")),
                "text": str(s["text"]),
                "fit": _fit_of(str(s["text"])),
                "opportunity_score": _opp_of(s),
            }
        )
    scored_signals.sort(key=lambda e: (-e["fit"], e["id"]))

    aligned = [e for e in scored_signals if e["fit"] >= ALIGNED_FIT]

    drift = []
    for p in pursuits:
        if not isinstance(p, Mapping) or not str(p.get("title", "")).strip():
            raise ValueError(f"pursuit entries need non-empty 'title': {p!r}")
        fit = _fit_of(str(p["title"]))
        if fit < DRIFT_FIT:
            drift.append(
                {"title": str(p["title"]), "fit": fit,
                 "opportunity_score": _opp_of(p)}
            )
    drift.sort(key=lambda e: (e["fit"], e["title"]))

    pursuit_texts = {str(p.get("title", "")).strip().lower() for p in pursuits}
    pursuit_ids = {str(p.get("id", "")).strip().lower() for p in pursuits}
    pursuit_signal_ids = {
        str(p.get(k, "")).strip().lower()
        for p in pursuits
        for k in ("signal_id", "demand_id")
    }
    linked = pursuit_ids | pursuit_signal_ids
    unpursued = [
        e
        for e in scored_signals
        if e["text"].strip().lower() not in pursuit_texts
        and e["id"].strip().lower() not in linked
    ]
    nudge: Optional[Dict[str, Any]] = unpursued[0] if unpursued else None

    lines = []
    head = "=== Direction coach brief ==="
    if as_of:
        head += f"  ({as_of})"
    lines.append(head)
    lines.append("")
    lines.append("Where you're headed:")
    for item in headed:
        lines.append(
            f"  - {item.name} (weight {float(item.weight):.2f}): {item.why}"
        )
    lines.append("")
    if aligned:
        lines.append("What's aligned (fit >= 0.50):")
        for e in aligned:
            opp = e["opportunity_score"]
            v = verdict(opp, e["fit"])["verdict"] if opp is not None else "unscored"
            opp_s = f"{opp:.2f}" if opp is not None else "--"
            lines.append(
                f"  - [{e['id'] or 'noid'}] fit={e['fit']:.2f} "
                f"opp={opp_s} -> {v}: "
                f"{e['text'][:90]}"
            )
    else:
        lines.append("What's aligned: nothing sensed right now at fit >= 0.50.")
    lines.append("")
    if drift:
        lines.append("What's drift (pursuing, fit < 0.30):")
        for e in drift:
            opp = e["opportunity_score"]
            opp_s = f"{opp:.2f}" if opp is not None else "--"
            lines.append(
                f"  - fit={e['fit']:.2f} opp={opp_s}: "
                f"{e['title'][:90]}"
            )
    else:
        lines.append("What's drift: none — everything pursued points with you.")
    lines.append("")
    lines.append("One refinement nudge:")
    lines.append("  (rule: highest direction-fit sensed signal with no active pursuit)")
    if nudge is not None and nudge["fit"] >= ALIGNED_FIT:
        matched = [
            r["name"]
            for r in direction_fit(nudge["text"], profile).reasons
            if r.get("item") is not None
        ]
        nopp = nudge["opportunity_score"]
        nopp_s = f"{nopp:.2f}" if nopp is not None else "unscored"
        lines.append(
            f"  Consider pursuing [{nudge['id'] or 'noid'}]: "
            f"fit={nudge['fit']:.2f}, opportunity={nopp_s}."
        )
        lines.append(f"  It matches: {', '.join(matched)}.")
        lines.append(f"  Signal: {nudge['text'][:120]}")
    else:
        lines.append(
            "  No unpursued aligned signal right now — nothing to add. "
            "If drift is listed above, that's the prune list."
        )
    lines.append("")
    lines.append(
        "Fit scores are alignment with your stated direction — advisory only."
    )
    return "\n".join(lines)


def reseed_profile(path: Union[str, Path] = PROFILE_PATH) -> Path:
    """(Re)write the JSON data file from the documented seed snapshot."""
    return build_seed_profile().save(path)


def load_profile(path: Union[str, Path] = PROFILE_PATH) -> DirectionProfile:
    """Load the direction profile from its JSON data file."""
    return DirectionProfile.load(path)
