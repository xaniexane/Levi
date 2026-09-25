"""DemandPulse → topic/angle selection for the King content machine.

scan → score → surface feeds the pipeline: the top-ranked DemandPulse
signals become the source text that ``social.build_pack()`` turns into
platform packs. Deterministic and transparent — every shipped pack names
the exact demand signal it came from; no invented topics.

Reuses the training generator's proven patterns
(``your_files/generator-improved/generate_levi_fixed.py``):

* round engine — every pack stamped with a round label + UTC ``ts``;
* dedup — an explicit seen-set (in-run, optionally persisted) so no
  angle ships twice;
* construction-time quality gate — ``validate_static()`` checks every
  list once at import/startup, and ``passes_gate()`` scores every draft
  (relevance to the demand signal + voice match) before it ships.

Honest contract
---------------
* Read-only on DemandPulse output: this module only reads the
  ``demand_pulse.json`` file. It never writes to the demand store.
* Drafts only. Packs go through the existing review queue; the
  approve/post gates are unchanged. Nothing here touches the network.
* If the DemandPulse schema is mid-refactor, ``read_demand_pulse`` is
  tolerant: missing keys become empty lists, unknown kinds rank lowest.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# -- construction-time lists (validated once by validate_static) ----------

#: Signal kinds, best evidence first. Unknown kinds rank below all of these.
KIND_RANK = {"OBSERVED": 3, "INFERENCE": 2, "HYPOTHESIS": 1}

STOPWORDS = [
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "need",
    "needs",
    "help",
    "are",
    "was",
    "were",
    "has",
    "have",
    "had",
    "will",
    "would",
    "could",
    "should",
    "there",
    "their",
    "they",
    "them",
    "then",
    "than",
    "when",
    "what",
    "which",
    "who",
    "whom",
    "how",
    "why",
    "not",
    "but",
    "all",
    "any",
    "can",
    "just",
    "now",
    "get",
    "got",
    "anyone",
    "someone",
    "something",
    "thing",
    "things",
    "into",
    "over",
    "under",
    "about",
    "after",
    "before",
    "between",
    "through",
    "during",
    "again",
    "once",
    "here",
]

#: Chauncey's builder voice, lifted from his shipped captions. A draft
#: must echo this voice to pass the gate.
VOICE_WORDS = [
    "mine",
    "building",
    "build",
    "local",
    "offline",
    "own",
    "cloud",
    "rent",
    "raising",
    "answers",
    "loop",
    "ship",
    "flip",
    "ladder",
    "permission",
    "start",
    "giants",
    "records",
    "machines",
    "trained",
    "ugly",
    "rung",
    "marketplace",
    "small",
    "break",
    "fix",
]

#: Reused from the training generator: no provider names, no
#: consciousness/feeling claims in generated text.
BANNED = re.compile(
    r"(?i)(as an ai\b|i feel\b|i am conscious|consciousness|i'm sorry|"
    r"openai|anthropic|google gemini|microsoft copilot|meta ai|chatgpt|Muse\b)"
)

#: Gate bar: composite score (0-100) a draft must reach to ship.
GATE_THRESHOLD = 70.0

#: Max keywords carried from a signal into a draft.
MAX_KEYWORDS = 6

DEFAULT_DEMAND_PATH = Path.home() / ".levi" / "demand_pulse.json"


def validate_static() -> None:
    """Construction-time gate: validate every list once.

    Mirrors ``generate_levi_fixed.validate_static`` — every combinatorial
    product of these lists inherits the guarantees. Raises SystemExit on
    violation.
    """
    for name, lst in [("STOPWORDS", STOPWORDS), ("VOICE_WORDS", VOICE_WORDS)]:
        if len(lst) != len(set(lst)):
            raise SystemExit(f"duplicate entries in {name}")
        for s in lst:
            if not s:
                raise SystemExit(f"empty entry in {name}")
            try:
                s.encode("ascii")
            except UnicodeEncodeError:
                raise SystemExit(f"non-ascii entry in {name}: {s!r}") from None
            if "  " in s:
                raise SystemExit(f"double space in {name}: {s!r}")
    for kind, rank in KIND_RANK.items():
        if not isinstance(rank, int) or rank <= 0:
            raise SystemExit(f"bad rank for kind {kind!r}")
    if not (0 < GATE_THRESHOLD <= 100):
        raise SystemExit(f"GATE_THRESHOLD out of band: {GATE_THRESHOLD}")
    try:
        BANNED.search("smoke test")
    except re.error as exc:
        raise SystemExit(f"BANNED regex broken: {exc}") from None


validate_static()


# -- demand reading -------------------------------------------------------


def read_demand_pulse(path: Optional[Path] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Read DemandPulse scan→score→surface output. Read-only; tolerant.

    Returns ``{"signals": [...], "opportunities": [...], "score_cards": [...]}``.
    Missing file or missing keys → empty lists (never raises on shape).
    """
    src = Path(path) if path else DEFAULT_DEMAND_PATH
    data: Dict[str, List[Dict[str, Any]]] = {
        "signals": [],
        "opportunities": [],
        "score_cards": [],
    }
    try:
        raw = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return data
    if not isinstance(raw, dict):
        return data
    for key in data:
        val = raw.get(key)
        if isinstance(val, list):
            data[key] = [v for v in val if isinstance(v, dict)]
    return data


def extract_keywords(text: str, limit: int = MAX_KEYWORDS) -> List[str]:
    """Deterministic keyword extraction: lowercase, strip punctuation,
    drop stopwords, keep tokens >= 3 chars, dedupe preserving order."""
    if not isinstance(text, str):
        return []
    words = re.findall(r"[a-z0-9]+", text.lower())
    stop = set(STOPWORDS)
    seen: List[str] = []
    for w in words:
        if len(w) >= 3 and w not in stop and w not in seen:
            seen.append(w)
        if len(seen) >= limit:
            break
    return seen


# -- candidate ranking ----------------------------------------------------


def _signal_priority(sig: Dict[str, Any]) -> float:
    kind = str(sig.get("kind", "")).upper()
    kind_score = KIND_RANK.get(kind, 0) / 3.0
    try:
        conf = float(sig.get("confidence", 0) or 0)
    except (TypeError, ValueError):
        conf = 0.0
    try:
        seen_n = int(sig.get("seen_count", 0) or 0)
    except (TypeError, ValueError):
        seen_n = 0
    return (
        0.4 * kind_score
        + 0.4 * max(0.0, min(1.0, conf))
        + 0.2 * min(1.0, seen_n / 100.0)
    )


def _as_float(val: Any) -> float:
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0


def rank_candidates(data: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Rank every demand item into one deterministic candidate list.

    Each candidate: ``signal_id``, ``kind`` ("signal"|"opportunity"|
    "score_card"), ``text``, ``keywords``, ``priority``. Sorted by
    (-priority, kind, signal_id) — fully deterministic, no randomness.
    """
    cands: List[Dict[str, Any]] = []
    for sig in data.get("signals", []):
        text = str(sig.get("need", "") or "")
        cands.append(
            {
                "signal_id": str(sig.get("id", "?")),
                "kind": "signal",
                "text": text,
                "keywords": extract_keywords(text),
                "priority": _signal_priority(sig),
            }
        )
    for opp in data.get("opportunities", []):
        text = str(opp.get("title", "") or "")
        cands.append(
            {
                "signal_id": str(opp.get("id", "?")),
                "kind": "opportunity",
                "text": text,
                "keywords": extract_keywords(text),
                "priority": max(0.0, min(1.0, _as_float(opp.get("worth")))),
            }
        )
    for card in data.get("score_cards", []):
        text = str(card.get("title", "") or "")
        cands.append(
            {
                "signal_id": str(card.get("opportunity_id", "?")),
                "kind": "score_card",
                "text": text,
                "keywords": extract_keywords(text),
                "priority": max(
                    0.0, min(1.0, _as_float(card.get("composite")) / 100.0)
                ),
            }
        )
    cands.sort(key=lambda c: (-c["priority"], c["kind"], c["signal_id"]))
    return cands


# -- draft construction ---------------------------------------------------


def candidate_source_text(cand: Dict[str, Any]) -> str:
    """Build the source text for ``build_pack`` from a demand candidate.

    Voiced in his register and embedding the signal's keywords by
    construction — the gate then *verifies* the construction held.
    """
    kws = cand.get("keywords") or []
    k1 = kws[0] if len(kws) > 0 else "work"
    k2 = kws[1] if len(kws) > 1 else k1
    k3 = kws[2] if len(kws) > 2 else k2
    need = (cand.get("text") or "").strip()
    lines = [
        f"{k1.title()} — mine, built local.",
        "",
        f"Raw signal from the demand scan: {need}"
        if need
        else "Raw signal from the demand scan.",
        f"I'm building for {k1} and {k2} — on my own machines, my own records, "
        "no cloud rent, no API keys. Nobody hands you "
        f"{k3}. You build it rung by rung. The loop is the game: "
        "ship, break, fix, ship again.",
    ]
    return "\n".join(lines)


def candidate_title(cand: Dict[str, Any]) -> str:
    kws = cand.get("keywords") or []
    if len(kws) >= 2:
        return f"Demand: {kws[0]} {kws[1]}"
    if kws:
        return f"Demand: {kws[0]}"
    return "Demand signal"


# -- quality gate ---------------------------------------------------------


def score_draft(caption: str, keywords: List[str]) -> Dict[str, float]:
    """Score a draft caption: relevance to the demand signal (55%) +
    voice match to his builder register (45%). Pure function."""
    low = caption.lower()
    kws = [k for k in (keywords or []) if k]
    rel_hits = sum(1 for k in kws if k.lower() in low)
    relevance = 100.0 * rel_hits / max(1, len(kws))
    voice_hits = sum(1 for w in VOICE_WORDS if w in low)
    voice = min(100.0, voice_hits * 12.0)
    composite = round(0.55 * relevance + 0.45 * voice, 1)
    return {
        "relevance": round(relevance, 1),
        "voice": round(voice, 1),
        "composite": composite,
    }


def passes_gate(
    caption: str,
    keywords: List[str],
    platform: str,
    threshold: float = GATE_THRESHOLD,
) -> Dict[str, Any]:
    """Per-draft gate: banned-phrase scan, keyword relevance, voice,
    and platform fit. Returns ``{"pass": bool, "score": {...}, "reasons": [...]}``."""
    from .social import PLATFORMS

    reasons: List[str] = []
    if BANNED.search(caption):
        reasons.append("banned phrase in caption")
    score = score_draft(caption, keywords)
    if score["composite"] < threshold:
        reasons.append(
            f"composite {score['composite']} below gate {threshold} "
            f"(relevance {score['relevance']}, voice {score['voice']})"
        )
    spec = PLATFORMS.get(platform)
    if spec is None:
        return {
            "pass": False,
            "score": score,
            "reasons": [f"unknown platform {platform!r}"],
        }
    limit = spec.get("caption_max")
    if limit is not None and len(caption) > limit:
        reasons.append(f"caption {len(caption)} chars exceeds {platform} max {limit}")
    return {"pass": not reasons, "score": score, "reasons": reasons}


def utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stamp_round(pack: Dict[str, Any], round_label: str, ts: str) -> Dict[str, Any]:
    """Stamp the training generator's round engine onto a pack."""
    pack["round"] = round_label
    pack["ts"] = ts
    return pack


# -- dedup -----------------------------------------------------------------


def pack_fingerprint(platform: str, caption: str) -> str:
    """Normalized fingerprint: no repeated angles ship in a run."""
    norm = " ".join(caption.lower().split())
    return f"{platform}::{norm}"


class DedupLedger:
    """Explicit seen-set. Optionally persisted as JSONL for cross-run dedup."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._seen: set = set()
        self.path = Path(path) if path else None
        if self.path and self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    self._seen.add(line)

    def seen(self, fingerprint: str) -> bool:
        return fingerprint in self._seen

    def add(self, fingerprint: str) -> None:
        self._seen.add(fingerprint)
        if self.path:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(fingerprint + "\n")

    def __len__(self) -> int:
        return len(self._seen)


# -- pipeline ---------------------------------------------------------------


def generate_dp_packs(
    platforms: tuple = ("x", "facebook", "tiktok"),
    per_platform: int = 1,
    demand_path: Optional[Path] = None,
    round_label: str = "dp-1",
    ts: Optional[str] = None,
    ledger: Optional[DedupLedger] = None,
    threshold: float = GATE_THRESHOLD,
) -> Dict[str, Any]:
    """DemandPulse scan → score → surface → platform packs.

    Deterministic: candidates ranked by (-priority, kind, id), platforms
    in given order, no randomness. Every shipped pack carries
    ``demand_signal_id``, ``signal_kind``, ``signal_text``, ``score``,
    ``round``, ``ts``. Rejected drafts are reported, never silently dropped.
    """
    from .social import assert_pack_clean, build_pack

    stamp = ts or utc_ts()
    data = read_demand_pulse(demand_path)
    candidates = rank_candidates(data)
    # NOTE: explicit None-check — DedupLedger defines __len__, so a bare
    # `ledger or DedupLedger()` would discard an empty-but-live ledger.
    seen = ledger if ledger is not None else DedupLedger()
    packs: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    dupes = 0

    for platform in platforms:
        shipped = 0
        for cand in candidates:
            if shipped >= per_platform:
                break
            source = candidate_source_text(cand)
            title = candidate_title(cand)
            try:
                pack = build_pack(source, platform=platform, title=title)
            except ValueError as exc:
                rejected.append(
                    {
                        "demand_signal_id": cand["signal_id"],
                        "platform": platform,
                        "reason": f"build_pack: {exc}",
                    }
                )
                continue
            fp = pack_fingerprint(platform, str(pack["caption"]))
            if seen.seen(fp):
                dupes += 1
                continue
            gate = passes_gate(
                str(pack["caption"]), cand["keywords"], platform, threshold
            )
            if not gate["pass"]:
                rejected.append(
                    {
                        "demand_signal_id": cand["signal_id"],
                        "platform": platform,
                        "reason": "; ".join(gate["reasons"]),
                        "score": gate["score"],
                    }
                )
                continue
            assert_pack_clean(pack)  # same contract as King.social
            pack["demand_signal_id"] = cand["signal_id"]
            pack["signal_kind"] = cand["kind"]
            pack["signal_text"] = cand["text"]
            pack["score"] = gate["score"]
            stamp_round(pack, round_label, stamp)
            seen.add(fp)
            packs.append(pack)
            shipped += 1

    return {
        "packs": packs,
        "rejected": rejected,
        "dupes_skipped": dupes,
        "round": round_label,
        "ts": stamp,
        "candidates_considered": len(candidates),
    }
