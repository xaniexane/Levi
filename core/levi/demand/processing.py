"""DemandPulse Layers 2-3 — processing, heuristic scoring, industry heatmap.

Ports layers 2 and 3 of the original ``omega_demandpulse.py`` exactly:
  - Layer 2 ``process_signals``: clusters on ``industry|type|keyword``,
    multi-source validation boost.
  - Layer 3 ``score_cluster``/``score_all``: the original's five-factor
    formulas with the blueprint weights (30/25/20/15/10) and the 75
    threshold. These factors are *derived from signal counts* — a
    prototype heuristic, not analyst judgment.

Honesty contract (LEVI law, kept explicit here):
  - Signals from ingest.py carry ``label: "OBSERVED"`` (real fetched text).
  - Clusters carry ``label: "INFERENCE"`` (grouping is our inference).
  - Scored clusters carry ``label: "HYPOTHESIS"`` — the factors are
    count-derived heuristics, never measurements. For scores that carry
    an analyst's stated basis, use ``levi.demand.scoring`` (basis-required
    five-factor scoring) instead.
  - Nothing here invents market data; a score describes an assessment.

Weights/thresholds are read from ``levi.demand.scoring``'s canonical
constants — they are used, never redefined here, so the two cannot drift.

stdlib-only. Advisory: scoring executes nothing and touches no money.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from levi.demand.ingest import INDUSTRIES, ingest_signals
from levi.demand.scoring import DEFAULT_THRESHOLD, DEFAULT_WEIGHTS

# Original blueprint threshold bands, kept verbatim.
PRIORITY_HIGH = 75.0
PRIORITY_MEDIUM = 50.0

# Heatmap bands from the original blueprint.
HEAT_GREEN = 65.0
HEAT_YELLOW = 45.0

DEFAULT_SCAN_PATH = Path.home() / ".levi" / "demandpulse_scan.json"

_HEURISTIC_BASIS = (
    "prototype heuristic: factors derived from signal counts, not analyst "
    "assessment — HYPOTHESIS. Use levi.demand.scoring for basis-required scoring."
)


def process_signals(signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Layer 2 — Signal Processing Pipeline (original logic, kept verbatim).

    Clusters on ``industry|signal_type|first_keyword``; a cluster seen in
    two or more sources gets the multi-source validation boost (confidence
    raised to high). Output clusters are labeled INFERENCE.
    """
    clusters: Dict[str, List[Dict[str, Any]]] = {}
    for sig in signals:
        if not isinstance(sig, dict):
            continue
        kw_list = sig.get("keywords") or ["general"]
        kw = kw_list[0] if kw_list else "general"
        key = f"{sig.get('industry', '?')}|{sig.get('signal_type', '?')}|{kw}"
        clusters.setdefault(key, []).append(sig)

    processed: List[Dict[str, Any]] = []
    for _key, group in clusters.items():
        theme = (group[0].get("summary", "") or "")[:80]
        multi_source = len({s.get("source") for s in group}) >= 2
        processed.append(
            {
                "cluster_id": uuid.uuid4().hex[:12],
                "theme": theme,
                "industry": group[0].get("industry", ""),
                "signal_type": group[0].get("signal_type", ""),
                "signal_count": len(group),
                "multi_source_validated": multi_source,
                "confidence": "high"
                if multi_source
                else group[0].get("confidence", "low"),
                "label": "INFERENCE",  # grouping is our inference over OBSERVED signals
                "signals": group,
            }
        )
    return processed


def _factors(cluster: Dict[str, Any]) -> Dict[str, float]:
    """Original count-derived factor formulas (prototype heuristic)."""
    n = int(cluster.get("signal_count", 0) or 0)
    multi = bool(cluster.get("multi_source_validated", False))
    signals = cluster.get("signals", []) or []

    demand = min(100.0, 40.0 + n * 8.0 + (15.0 if multi else 0.0))
    market = min(100.0, 35.0 + len(signals) * 6.0)
    competition = min(
        100.0, 55.0 + (10.0 if cluster.get("signal_type") == "pain_point" else 0.0)
    )
    velocity = min(100.0, 30.0 + n * 10.0)
    feasibility = min(
        100.0,
        70.0
        if cluster.get("industry")
        in ("Technology / SaaS", "Services / Trades", "Education / EdTech")
        else 55.0,
    )
    return {
        "demand": demand,
        "market_size": market,
        "competition_gap": competition,
        "trend_velocity": velocity,
        "entry_feasibility": feasibility,
    }


def score_cluster(
    cluster: Dict[str, Any],
    weights: Optional[Mapping[str, float]] = None,
) -> Dict[str, Any]:
    """Layer 3 — original five-factor opportunity scoring (heuristic).

    Uses the canonical blueprint weights from ``levi.demand.scoring``
    (30/25/20/15/10) and the 75 threshold; bands: >=75 high, >=50 medium,
    else low. Labeled HYPOTHESIS with an explicit basis note explaining
    the factors are count-derived, not assessed.
    """
    w = dict(weights) if weights is not None else dict(DEFAULT_WEIGHTS)
    factors = _factors(cluster)
    composite = round(
        sum(factors[k] * w.get(k, DEFAULT_WEIGHTS[k]) for k in factors), 1
    )

    if composite >= PRIORITY_HIGH:
        priority = "high"
    elif composite >= PRIORITY_MEDIUM:
        priority = "medium"
    else:
        priority = "low"

    return {
        "id": uuid.uuid4().hex[:12],
        "name": cluster.get("theme", ""),
        "industry": cluster.get("industry", ""),
        "signal_type": cluster.get("signal_type", ""),
        "composite_score": composite,
        "priority": priority,
        "factors": factors,
        "weights": w,
        "signal_count": cluster.get("signal_count", 0),
        "multi_source_validated": cluster.get("multi_source_validated", False),
        "status": "new",
        "signals": cluster.get("signals", []),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "notes": "",
        "label": "HYPOTHESIS",  # count-derived heuristic, not a measurement
        "basis": _HEURISTIC_BASIS,
        "threshold": DEFAULT_THRESHOLD,
        "above_threshold": composite >= DEFAULT_THRESHOLD,
    }


def score_all(
    clusters: List[Dict[str, Any]],
    weights: Optional[Mapping[str, float]] = None,
) -> List[Dict[str, Any]]:
    """Score every cluster, sorted by composite descending."""
    return sorted(
        (score_cluster(c, weights) for c in clusters),
        key=lambda o: -o["composite_score"],
    )


def industry_heatmap(
    opportunities: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Industry heat map — green/yellow/gray per the original blueprint.

    Bands: avg composite >= 65 green, >= 45 yellow, else gray. Sectors with
    no opportunities are gray with count 0.
    """
    heat: Dict[str, Dict[str, Any]] = {}
    for industry in INDUSTRIES:
        sector = [o for o in opportunities if o.get("industry") == industry]
        if not sector:
            heat[industry] = {"score": 0, "count": 0, "heat": "gray", "top": None}
            continue
        avg = sum(float(o.get("composite_score", 0.0)) for o in sector) / len(sector)
        top = max(sector, key=lambda o: float(o.get("composite_score", 0.0)))
        if avg >= HEAT_GREEN:
            level = "green"
        elif avg >= HEAT_YELLOW:
            level = "yellow"
        else:
            level = "gray"
        heat[industry] = {
            "score": round(avg, 1),
            "count": len(sector),
            "heat": level,
            "top": top.get("name"),
        }
    return heat


def run_scan(
    query: str,
    weights: Optional[Mapping[str, float]] = None,
    focus_industries: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Full 4-layer scan pipeline: ingest → process → score → command center.

    The last scan is persisted (best-effort, never raises) so workflow 8
    (Signal Correlation Engine) can re-correlate stored signals later.
    """
    signals = ingest_signals(query, focus_industries)
    clusters = process_signals(signals)
    opportunities = score_all(clusters, weights)
    heatmap = industry_heatmap(opportunities)

    source_counts: Dict[str, int] = {}
    for sig in signals:
        src = sig.get("source", "?")
        source_counts[src] = source_counts.get(src, 0) + 1

    result = {
        "query": query,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "sources_live": source_counts,
        "layers": {
            "ingestion": {
                "sources_active": len(source_counts),
                "signals_raw": len(signals),
            },
            "processing": {"clusters": len(clusters)},
            "scoring": {"opportunities": len(opportunities)},
            "command_center": {"ready": True},
        },
        "pipeline_counts": {
            "high": sum(1 for o in opportunities if o["priority"] == "high"),
            "medium": sum(1 for o in opportunities if o["priority"] == "medium"),
            "low": sum(1 for o in opportunities if o["priority"] == "low"),
        },
        "signals": signals,
        "clusters": clusters,
        "opportunities": opportunities,
        "heatmap": heatmap,
        "top_opportunity": opportunities[0] if opportunities else None,
    }

    try:
        DEFAULT_SCAN_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = DEFAULT_SCAN_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(result, indent=2), encoding="utf-8")
        tmp.replace(DEFAULT_SCAN_PATH)
    except Exception:
        pass  # persistence is a convenience, never a failure
    return result


def load_last_scan(path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Return the last persisted scan result, or None when absent/corrupt."""
    scan_path = Path(path) if path else DEFAULT_SCAN_PATH
    try:
        data = json.loads(scan_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None
