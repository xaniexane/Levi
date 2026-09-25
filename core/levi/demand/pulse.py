"""
DemandPulse — demand / gap / opportunity perception (subsystem, not the whole of LEVI).

Three engine families (activated on demand by the daemon, not all-at-once):
  - Demand engines: surface unmet needs
  - Opportunity engines: score serviceability vs cost
  - (Service engines live in income factory)

Outputs are HYPOTHESIS / INFERENCE until verified in corpus as OBSERVED.
"""

from __future__ import annotations

import hashlib
import json
import math
import warnings
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


from levi.demand.scoring import (
    DEFAULT_THRESHOLD,
    FactorInput,
    ScoreCard,
    rank_cards,
    score_card,
)
from levi.demand.dedup import (
    find_duplicate,
    near_duplicate,
    normalize_text,
)
from levi.demand import numbers as _numbers


DEFAULT = Path.home() / ".levi" / "demand_pulse.json"


def _ledger_sight(card, demand_id: str, source: str) -> None:
    """Best-effort sighting row for a new/replaced score card (O1/O2).

    The ledger is advisory infrastructure: this never raises and never
    mutates the score. Verdicts (``converted``/``missed``) are recorded
    only by explicit calls — scoring never invents them. The ledger row
    carries the card's own fields (card_id/title/composite/tier/segment);
    ``demand_id``/``source`` are available to the caller for audit logs,
    not stored (O5 minimal fields).
    """
    try:
        from levi.demand import outcomes as _outcomes

        _outcomes.record_sighting(card)
    except Exception:
        pass


@dataclass
class DemandSignal:
    id: str
    need: str
    segment: str = "general"
    evidence: str = ""
    confidence: float = 0.4  # low until observed
    kind: str = "HYPOTHESIS"  # OBSERVED | INFERENCE | HYPOTHESIS
    seen_count: int = 1  # occurrence metadata, NOT evidence: repeats never
    # raise confidence (see _register_signal)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    source: str = "scan"  # where the signal was sensed: scan|email|text|notification
    number: Optional[float] = None  # deterministic demand number 0-100
    # (levi.demand.numbers); scored at registration, rescored on merges.
    # None = not yet scored (pre-numbers store). Scoring never changes
    # kind/confidence — N4 tier preserved.
    # --- provenance (quality build 2026-09-24) ---
    # ``origin`` is the first source item this signal was mined from
    # ({"ref": <id>} | {"link": <url>, ...}); ``origins`` accumulates one
    # entry per DISTINCT source item merged in via dedup. A signal with no
    # origins cannot be traced back to anything observed — the frequency
    # factor then falls back to seen_count and says so in its basis.
    origin: Optional[Dict[str, str]] = None
    origins: List[Dict[str, str]] = field(default_factory=list)
    # --- quarantine ---
    # Quarantined signals are kept (nothing is ever deleted) but excluded
    # from live views. Set only by run_quarantine(); cleared by
    # unquarantine(). Reversible, receipted.
    quarantined: bool = False
    quarantine_reason: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError(f"signal id must be a non-empty string, got {self.id!r}")
        if not isinstance(self.need, str) or not self.need.strip():
            raise ValueError("signal need must be a non-empty string")
        if not isinstance(self.segment, str) or not self.segment.strip():
            raise ValueError(
                f"signal segment must be a non-empty string, got {self.segment!r}"
            )
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not math.isfinite(self.confidence)
            or not 0.0 <= self.confidence <= 1.0
        ):
            raise ValueError(
                f"signal confidence must be a number in [0, 1], got {self.confidence!r}"
            )
        if self.kind not in ("OBSERVED", "INFERENCE", "HYPOTHESIS"):
            raise ValueError(
                f"signal kind must be OBSERVED/INFERENCE/HYPOTHESIS, got {self.kind!r}"
            )
        if (
            isinstance(self.seen_count, bool)
            or not isinstance(self.seen_count, int)
            or self.seen_count < 1
        ):
            raise ValueError(
                f"signal seen_count must be a positive integer, "
                f"got {self.seen_count!r}"
            )
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError(
                f"signal source must be a non-empty string, got {self.source!r}"
            )
        if self.number is not None and (
            isinstance(self.number, bool)
            or not isinstance(self.number, (int, float))
            or not math.isfinite(self.number)
            or not 0.0 <= self.number <= 100.0
        ):
            raise ValueError(
                f"signal number must be None or a number in [0, 100], "
                f"got {self.number!r}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Opportunity:
    id: str
    demand_id: str
    title: str
    demand_score: float
    serviceability: float
    startup_cost: float  # 0–1 abstract (0 = free-first feasible)
    notes: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError(
                f"opportunity id must be a non-empty string, got {self.id!r}"
            )
        if not isinstance(self.demand_id, str) or not self.demand_id.strip():
            raise ValueError(
                f"opportunity demand_id must be a non-empty string, "
                f"got {self.demand_id!r}"
            )
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("opportunity title must be a non-empty string")
        for name in ("demand_score", "serviceability", "startup_cost"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0.0 <= value <= 1.0
            ):
                raise ValueError(
                    f"opportunity {name} must be a number in [0, 1], got {value!r}"
                )

    @property
    def worth(self) -> float:
        # high demand, high serviceability, low cost
        return (
            self.demand_score * 0.4
            + self.serviceability * 0.4
            + (1.0 - self.startup_cost) * 0.2
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["worth"] = round(self.worth, 3)
        return d


class DemandPulse:
    def __init__(self, path: Optional[Path] = None):
        if path is not None and not isinstance(path, (str, Path)):
            raise ValueError(
                f"path must be a str/Path or None, got {type(path).__name__}"
            )
        self.path = Path(path) if path else DEFAULT
        self.signals: List[DemandSignal] = []
        self.opportunities: List[Opportunity] = []
        self.score_cards: List[ScoreCard] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("top level must be an object")
            for kind, cls, attr in (
                ("signals", DemandSignal, "signals"),
                ("opportunities", Opportunity, "opportunities"),
            ):
                items = raw.get(kind) or []
                if not isinstance(items, list):
                    raise ValueError(f"{kind!r} must be a list")
                kept = []
                for s in items:
                    if not isinstance(s, dict):
                        continue
                    try:
                        kept.append(
                            cls(
                                **{
                                    k: v
                                    for k, v in s.items()
                                    if k in cls.__dataclass_fields__
                                }
                            )
                        )
                    except Exception:
                        continue  # one corrupt entry must not kill the rest
                setattr(self, attr, kept)
            self.score_cards = []
            cards = raw.get("score_cards") or []
            if not isinstance(cards, list):
                raise ValueError("'score_cards' must be a list")
            for c in cards:
                try:
                    self.score_cards.append(ScoreCard.from_dict(c))
                except Exception:
                    continue
        except Exception as exc:
            warnings.warn(
                f"demand pulse file {self.path} is unreadable "
                f"({type(exc).__name__}); starting empty. "
                "Back up or delete the file to silence this warning.",
                UserWarning,
                stacklevel=3,
            )
            self.signals = []
            self.opportunities = []
            self.score_cards = []

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "signals": [s.to_dict() for s in self.signals[-100:]],
            "opportunities": [o.to_dict() for o in self.opportunities[-100:]],
            "score_cards": [c.to_dict() for c in self.score_cards[-100:]],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def _check01(self, name: str, value: float) -> float:
        """Public-boundary 0-1 score check: rejects garbage, no silent clamping."""
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError(f"{name} must be a number in [0, 1], got {value!r}")
        value = float(value)
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be in [0, 1], got {value!r}")
        return value

    @staticmethod
    def _origin_key(origin: Optional[Dict[str, str]]) -> Optional[str]:
        if not isinstance(origin, dict):
            return None
        ref = str(origin.get("ref") or origin.get("link") or "").strip()
        return ref or None

    def _merge_origin(self, sig: DemandSignal,
                      origin: Optional[Dict[str, str]]) -> None:
        """Fold a newly seen source item into a surviving signal.

        Distinct items accumulate in ``origins`` (deduped by ref/link);
        repeats of an already-known item change nothing. This is what the
        frequency factor counts — real corroboration, not re-poll bumps.
        """
        key = self._origin_key(origin)
        if key is None:
            return
        if sig.origin is None:
            sig.origin = dict(origin)
        known = {self._origin_key(o) for o in sig.origins}
        if key not in known:
            sig.origins.append(dict(origin))

    def _register_signal(self, sig: DemandSignal) -> DemandSignal:
        """Store ``sig`` unless a dupe already exists in its (segment, source).

        Exact normalized match or conservative near-dup (see
        levi.demand.dedup) -> the existing signal's ``seen_count`` is
        bumped, the new origin is merged into ``origins``, and the
        existing signal is returned. Volume is occurrence metadata, not
        evidence: confidence and kind are never touched by a repeat.
        Dedup is scoped by (segment, source) so a need sensed in email
        and the same need sensed in text keep their source labels
        instead of collapsing into one. Every registration path
        (scan_seed, workflows) funnels through here so dupes cannot
        enter by another door.
        """
        norm = normalize_text(sig.need)
        dup_id = find_duplicate(
            norm,
            [
                (s.id, normalize_text(s.need))
                for s in self.signals
                if s.segment == sig.segment and s.source == sig.source
            ],
        )
        if dup_id is not None:
            for s in self.signals:
                if s.id == dup_id:
                    s.seen_count += 1
                    self._merge_origin(s, sig.origin)
                    return s
        self._merge_origin(sig, sig.origin)
        self.signals.append(sig)
        return sig

    def scan_seed(
        self,
        text: str,
        segment: str = "general",
        source: str = "scan",
        origin: Optional[Dict[str, str]] = None,
    ) -> DemandSignal:
        """Register a demand signal from user/context text (not invented market data).

        ``origin`` is the source item the text was mined from
        (``{"ref": <id>}`` or ``{"link": <url>, ...}``). When present, the
        signal's ``evidence`` reads ``observed:<source>`` — the signal
        traces back to a real observed item. Without it, ``evidence``
        stays ``user_or_context_seed`` (manual scans) and the signal is
        later quarantinable as untraceable.

        Idempotent: scanning text already in the store (exact or near-dupe,
        same segment AND same source) returns the existing signal with
        ``seen_count`` bumped and the new origin merged into ``origins``.
        Confidence stays 0.35 — repeats are not corroboration. ``source``
        labels where the need was sensed (scan|email|text|notification)
        and is preserved by the dedup scope.
        """
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"text must be a non-empty string, got {text!r}")
        if not isinstance(segment, str) or not segment.strip():
            raise ValueError(f"segment must be a non-empty string, got {segment!r}")
        if not isinstance(source, str) or not source.strip():
            raise ValueError(f"source must be a non-empty string, got {source!r}")
        if origin is not None and not isinstance(origin, dict):
            raise ValueError(f"origin must be a dict or None, got {type(origin).__name__}")
        t = text.strip()
        segment = segment.strip()
        source = source.strip()
        # id is a content hash over (segment, source, text): the dedup
        # scope is (segment, source), so the id must be unique across it.
        # (2026-09-24: the old text-only hash collided for the same need
        # sensed in two channels, giving two rows the same id.)
        hid = hashlib.sha256(
            f"{segment}\x00{source}\x00{t}".encode()
        ).hexdigest()[:8]
        sig = DemandSignal(
            id=hid,
            need=t[:300],
            segment=segment,
            evidence=(
                f"observed:{source}" if origin is not None
                else "user_or_context_seed"
            ),
            confidence=0.35,
            kind="HYPOTHESIS",
            source=source,
            origin=dict(origin) if origin is not None else None,
        )
        kept = self._register_signal(sig)
        # Every signal gets its number at registration (N2 deterministic;
        # recomputed on re-registration so the frequency factor tracks
        # distinct items). Never touches kind/confidence — N4.
        kept.number = self._score_signal(kept).composite
        self._persist()
        return kept

    def _score_signal(
        self, sig: DemandSignal, now: Optional[datetime] = None
    ):
        """Score one signal with live store context (deterministic).

        - frequency counts DISTINCT observed source items (``origins``),
          not re-poll bumps; legacy signals without origins fall back to
          seen_count and the basis says so.
        - source_diversity counts distinct channels across the near-dupe
          cluster in the store (cross-channel corroboration).
        - the composite is calibrated by the source channel's observed
          reliability (0.75x–1.25x, neutral 1.0x at 0.5).
        Never touches kind/confidence — N4.
        """
        origins = [o for o in (sig.origins or []) if isinstance(o, dict)]
        if origins:
            n_items, legacy = len(origins), False
        else:
            n_items, legacy = sig.seen_count, True
        norm = normalize_text(sig.need)
        channels = {sig.source}
        for s in self.signals:
            if s.id == sig.id or s.quarantined:
                continue
            if near_duplicate(norm, normalize_text(s.need)):
                channels.add(s.source)
        return _numbers.score_signal(
            sig,
            now=now,
            distinct_items=n_items,
            legacy_items=legacy,
            distinct_sources=len(channels),
            source_reliability=self.channel_reliability(sig.source),
        )

    def channel_reliability(self, channel: str) -> float:
        """Observed reliability of a source channel, 0..1.

        = kept / candidates from the watcher's extraction-yield counters:
        of the sentences that carried a need marker, how many survived
        the quality gates. Fewer than 10 samples -> 0.5 (stated neutral
        prior, never a fake precision). Never raises; 0.5 on any failure.
        Deterministic given the watcher state file.
        """
        try:
            from levi.demand.watcher import WatcherState

            st = WatcherState.load()
            q = (st.channels.get(channel) or {}).get("quality") or {}
            cands = int(q.get("candidates", 0) or 0)
            kept = int(q.get("kept", 0) or 0)
            if cands >= 10:
                return max(0.0, min(1.0, kept / cands))
        except Exception:
            pass
        return 0.5

    def live_signals(self) -> List[DemandSignal]:
        """Signals not in quarantine — the set every surfacing view reads."""
        return [s for s in self.signals if not s.quarantined]

    # --- quarantine ----------------------------------------------------
    # Deterministic rules; nothing is ever deleted (the nothing-thrown-away
    # law). Quarantined signals stay in the store with their reason and are
    # excluded from live views. Reversible via unquarantine().

    _QUARANTINE_FEED_SOURCES = frozenset(
        {"rss", "hn", "facebook", "reddit", "stackoverflow", "github",
         "arxiv", "jobs"}
    )

    def _quarantine_reason(self, sig: DemandSignal) -> Optional[str]:
        import re as _re

        if sig.quarantined:
            return None  # already held; don't double-count
        if (
            sig.source in self._QUARANTINE_FEED_SOURCES
            and not sig.origins
            and sig.evidence == "user_or_context_seed"
        ):
            return (
                "legacy feed signal: no item provenance — cannot be "
                "traced back to an observed source item"
            )
        if _re.match(r"^(engagement:|survey\s+|ops:)", sig.need,
                     _re.IGNORECASE):
            return "internal ops aggregate, not market demand"
        if _re.search(
            r"\b(i can build|hire me|my services|for hire|"
            r"what i can build|let me build)\b",
            sig.need, _re.IGNORECASE,
        ):
            return "supply-side offer, not demand"
        return None

    def run_quarantine(self, dry_run: bool = False) -> Dict[str, Any]:
        """Apply the quarantine rules to the store.

        dry_run=True reports what WOULD be quarantined without touching
        anything. Otherwise flags are set, persisted, and receipted.
        Returns {"quarantined": n, "dry_run": bool, "reasons": {...},
        "ids": [...]}.
        """
        from collections import Counter

        reasons: Counter = Counter()
        ids: List[str] = []
        for sig in self.signals:
            reason = self._quarantine_reason(sig)
            if reason is None:
                continue
            reasons[reason] += 1
            ids.append(sig.id)
            if not dry_run:
                sig.quarantined = True
                sig.quarantine_reason = reason
        if not dry_run and ids:
            self._persist()
        return {
            "quarantined": len(ids),
            "dry_run": dry_run,
            "reasons": dict(reasons),
            "ids": ids,
        }

    def unquarantine(self, signal_id: str) -> bool:
        """Clear a signal's quarantine flags (reversible). True if found."""
        for sig in self.signals:
            if sig.id == signal_id:
                sig.quarantined = False
                sig.quarantine_reason = ""
                self._persist()
                return True
        return False

    def ensure_numbers(self, now: Optional[datetime] = None) -> int:
        """Score every signal that lacks a number (pre-numbers store).

        Returns how many were scored; persists once when > 0. Deterministic:
        re-running scores nothing new.
        """
        count = 0
        for s in self.signals:
            n = s.number
            if (
                n is None
                or isinstance(n, bool)
                or not isinstance(n, (int, float))
                or not math.isfinite(n)
            ):
                s.number = self._score_signal(s, now=now).composite
                count += 1
        if count:
            self._persist()
        return count

    def score_opportunity(
        self,
        demand_id: str,
        title: str,
        demand_score: float = 0.5,
        serviceability: float = 0.5,
        startup_cost: float = 0.3,
        notes: str = "",
    ) -> Opportunity:
        """Score an opportunity; scores must already be on the 0-1 scale.

        Idempotent: the same demand_id + title is the same opportunity and
        returns the existing record instead of appending a twin. (The id is
        built from stripped values so "Shift planner" and "Shift planner "
        do not become two opportunities.)

        Wrong types, non-finite values, and out-of-range numbers are
        all rejected — a public boundary never silently clamps garbage
        into a plausible-looking score.
        """
        if not isinstance(demand_id, str) or not demand_id.strip():
            raise ValueError(f"demand_id must be a non-empty string, got {demand_id!r}")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title must be a non-empty string")
        if not isinstance(notes, str):
            raise ValueError(f"notes must be a string, got {type(notes).__name__}")
        demand_s = demand_id.strip()
        title_s = title.strip()
        opp_id = hashlib.sha256(f"{demand_s}{title_s}".encode()).hexdigest()[:8]
        for o in self.opportunities:
            if o.id == opp_id:
                return o
        opp = Opportunity(
            id=opp_id,
            demand_id=demand_s,
            title=title_s,
            demand_score=self._check01("demand_score", demand_score),
            serviceability=self._check01("serviceability", serviceability),
            startup_cost=self._check01("startup_cost", startup_cost),
            notes=notes,
        )
        self.opportunities.append(opp)
        self._persist()
        from levi.demand import cybrus_alliance as _alliance

        _alliance.audit_mutation(
            "demandpulse.opportunity_scored",
            {
                "opportunity_id": opp.id,
                "demand_id": demand_s,
                "title": title_s,
                "worth": round(opp.worth, 3),
            },
        )
        return opp

    def _check_n(self, name: str, n: int) -> int:
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise ValueError(f"{name} must be a positive integer, got {n!r}")
        return n

    def top_opportunities(self, n: int = 5) -> List[Opportunity]:
        n = self._check_n("n", n)
        return sorted(self.opportunities, key=lambda o: -o.worth)[:n]

    def score_five_factor(
        self,
        demand_id: str,
        title: str,
        factors: Dict[str, FactorInput],
        weights: Optional[Dict[str, float]] = None,
        threshold: float = DEFAULT_THRESHOLD,
        notes: str = "",
    ) -> ScoreCard:
        """Score an opportunity on the five-factor model.

        ``factors`` maps each factor name to a FactorScore, a
        ``(value, basis)`` pair, or a ``{"value":.., "basis":..}`` mapping.
        Every factor requires a non-empty basis — the honesty guardrail.
        Pure scoring; the card is then persisted.

        Self-sharpening (greatness build, 2026-09-22): every newly
        created or replaced card records a ``sighting`` row in the
        outcome ledger (``levi.demand.outcomes``) — best-effort, never
        raising, never mutating the score. Verdicts are recorded only
        by explicit calls, never inferred here.

        Idempotent: scoring the same demand_id + title twice yields one
        card. The key uses the normalized title so "Shift planner" and
        "shift  planner" do not become two cards. When a re-score carries
        a higher composite, it replaces the older card (stronger stated
        assessment wins); otherwise the existing card stands.
        """
        if not isinstance(demand_id, str) or not demand_id.strip():
            raise ValueError(f"demand_id must be a non-empty string, got {demand_id!r}")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title must be a non-empty string")
        demand_s = demand_id.strip()
        title_s = title.strip()
        demand = next((s for s in self.signals if s.id == demand_s), None)
        segment = demand.segment if demand is not None else "general"
        card_key = hashlib.sha256(
            f"{demand_s}|{normalize_text(title_s)}ff".encode()
        ).hexdigest()[:8]
        card = score_card(
            card_key,
            title_s,
            factors,
            weights=weights,
            threshold=threshold,
            notes=notes,
            segment=segment,
        )
        for i, existing in enumerate(self.score_cards):
            if existing.opportunity_id == card_key:
                if card.composite > existing.composite:
                    self.score_cards[i] = card
                    self._persist()
                    from levi.demand import cybrus_alliance as _alliance

                    _alliance.audit_mutation(
                        "demandpulse.card_scored",
                        {
                            "opportunity_id": card.opportunity_id,
                            "title": title_s,
                            "composite": card.composite,
                            "tier": card.tier,
                            "replaced": True,
                        },
                    )
                    _ledger_sight(
                        card, demand_id=demand_s,
                        source=demand.source if demand is not None else "manual",
                    )
                    return card
                return existing
        self.score_cards.append(card)
        self._persist()
        from levi.demand import cybrus_alliance as _alliance2

        _alliance2.audit_mutation(
            "demandpulse.card_scored",
            {
                "opportunity_id": card.opportunity_id,
                "title": title_s,
                "composite": card.composite,
                "tier": card.tier,
                "replaced": False,
            },
        )
        _ledger_sight(
            card, demand_id=demand_s,
            source=demand.source if demand is not None else "manual",
        )
        return card

    def top_score_cards(self, n: int = 5) -> List[ScoreCard]:
        n = self._check_n("n", n)
        return rank_cards(self.score_cards)[:n]

    def dedupe_store(self, dry_run: bool = False) -> Dict[str, Any]:
        """One-shot maintenance: collapse duplicate signals, opportunities,
        and score cards already in the store.

        Signals: same segment + (exact normalized match or conservative
        near-dup) -> keep the earliest, fold ``seen_count`` into it.
        Opportunities: same id -> keep first.
        Score cards: same (normalized title, normalized segment) -> keep
        the highest composite (earliest wins ties). Same-titled cards from
        different segments stay separate — "Shift planner" for the general
        segment is a different assessment than "Shift planner" for the
        enterprise segment. Titles are analyst-chosen labels for one
        opportunity within one segment; differing assessments filed under
        one title+segment collapse to the strongest.

        Returns a report dict with before/after counts. With
        ``dry_run=True`` nothing is mutated or persisted. The caller
        (``levi demand dedupe``) is responsible for backing up the store
        file before calling with ``dry_run=False``.
        """
        report: Dict[str, Any] = {"dry_run": dry_run}

        sig_before = len(self.signals)
        kept_signals: List[DemandSignal] = []
        merged_signals = 0
        for s in self.signals:  # oldest first; earliest wins
            norm = normalize_text(s.need)
            target = None
            for k in kept_signals:
                if k.segment != s.segment:
                    continue
                knorm = normalize_text(k.need)
                if knorm == norm or near_duplicate(norm, knorm):
                    target = k
                    break
            if target is None:
                kept_signals.append(s)
            else:
                target.seen_count += s.seen_count
                # seen_count feeds the frequency factor — rescore the merge.
                target.number = _numbers.score_signal(target).composite
                merged_signals += 1
        report["signals"] = {
            "before": sig_before,
            "after": len(kept_signals),
            "merged": merged_signals,
        }

        opp_before = len(self.opportunities)
        seen_opp = set()
        kept_opps: List[Opportunity] = []
        for o in self.opportunities:
            if o.id in seen_opp:
                continue
            seen_opp.add(o.id)
            kept_opps.append(o)
        report["opportunities"] = {
            "before": opp_before,
            "after": len(kept_opps),
            "merged": opp_before - len(kept_opps),
        }

        card_before = len(self.score_cards)
        best: Dict[Tuple[str, str], ScoreCard] = {}
        order: List[Tuple[str, str]] = []
        for c in self.score_cards:
            key = (normalize_text(c.title), normalize_text(c.segment))
            if key not in best:
                best[key] = c
                order.append(key)
            elif c.composite > best[key].composite:
                best[key] = c
        kept_cards = [best[k] for k in order]
        report["score_cards"] = {
            "before": card_before,
            "after": len(kept_cards),
            "merged": card_before - len(kept_cards),
        }

        if not dry_run:
            self.signals = kept_signals
            self.opportunities = kept_opps
            self.score_cards = kept_cards
            self._persist()
        return report

    def format_status(self) -> str:
        lines = [
            "=== DemandPulse ===",
            f"signals={len(self.signals)}  opportunities={len(self.opportunities)}",
            "",
        ]
        for o in self.top_opportunities(5):
            lines.append(
                f"  worth={o.worth:.2f}  {o.title}  (cost={o.startup_cost:.2f} svc={o.serviceability:.2f})"
            )
        if self.score_cards:
            lines.append("")
            lines.append("five-factor score cards:")
            for c in self.top_score_cards(5):
                flag = " ALERT" if c.alert else ""
                lines.append(f"  {c.composite:6.2f} [{c.tier}]{flag}  {c.title}")
        if not self.opportunities and not self.score_cards:
            lines.append('  (none — seed with: levi demand --scan "…")')
        lines.append("")
        lines.append("Labels are HYPOTHESIS until verified OBSERVED in corpus.")
        return "\n".join(lines)
