"""DemandPulse outcome ledger — self-sharpening (greatness build, 2026-09-22).

The machine of record for what happened AFTER a score card was written:
every card gets a sighting row when scored; Chauncey's verdicts
(converted / missed / stale) are recorded explicitly. Calibration
functions read the ledger and SUGGEST — they never rewrite scoring.

LAWS (law -> guard -> prove; Chauncey 2026-09-22):
  O1 APPEND-ONLY RECORD. The ledger is a local JSONL file (local-first:
     no cloud, no Google Sheets). Rows are appended; the file is never
     rewritten in place. One corrupt line is skipped — it never kills a
     read and never loses its neighbors.
  O2 VERDICTS ARE CHAUNCEY'S. ``record_sighting`` fires automatically when
     a card is scored (the machine noting its own assessment). Events
     converted / missed / stale are recorded ONLY by explicit calls —
     the machine never infers an outcome from silence or pattern.
  O3 CALIBRATION IS ADVISORY. ``effective_markers`` and
     ``suggest_thresholds`` return suggestions as data. They never mutate
     scoring weights, thresholds, or any other module's state. (This
     module must not import scoring/pulse — tests fail the build if it
     does.)
  O4 EXCEL IS A VIEW. ``export_xlsx`` renders JSONL -> .xlsx one way.
     The workbook is a human surface, never the record: edits to the
     .xlsx are not read back. openpyxl is required; without it the
     exporter raises with an honest message and ``export_csv`` is the
     documented fallback.
  O5 MINIMAL DATA. Rows carry card_id, title, composite, tier, segment,
     event, markers, note, ts — and nothing else. No signal bodies, no
     message text, no PII beyond what the score card already holds.

Standing limits honored: nothing here publishes, spends, contacts
anyone, touches alerts, or changes quiet hours. Everything the ledger
says is a HYPOTHESIS-grade assessment until Chauncey confirms it.
"""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Laws as importable constants (so tests can pin them, not just docstrings)

LAWS = (
    "O1 append-only JSONL record",
    "O2 verdicts are Chauncey's (explicit calls only)",
    "O3 calibration is advisory (never mutates scoring)",
    "O4 excel is a one-way view",
    "O5 minimal data (no bodies, no PII)",
)

EVENTS = ("sighting", "converted", "missed", "stale")
TERMINAL_EVENTS = ("converted", "missed", "stale")

# A marker only earns an effectiveness claim after this many RESOLVED
# (converted+missed) cards carried it. Below that: silence, not vibes.
MIN_SIGHTINGS_DEFAULT = 20

# suggest_thresholds() stays silent below this many resolved outcomes.
MIN_RESOLVED_DEFAULT = 10


def _repo_data_dir() -> Path:
    return Path(__file__).resolve().parent / "data"


def ledger_path() -> Path:
    """Machine-of-record path. In-repo, local-first; overridable for tests.

    ``LEVI_OUTCOMES_PATH`` wins when set; otherwise
    ``core/levi/demand/data/demand_outcomes.jsonl`` (gitignored — the
    ledger is durable on disk, not committed).
    """
    env = os.environ.get("LEVI_OUTCOMES_PATH")
    if env:
        return Path(env)
    return _repo_data_dir() / "demand_outcomes.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Writes — append-only


def _append(row: Dict[str, Any], path: Optional[Path] = None) -> Dict[str, Any]:
    p = path or ledger_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    row = dict(row)
    row.setdefault("ts", _now_iso())
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def record_event(
    card_id: str,
    event: str,
    title: str = "",
    composite: Optional[float] = None,
    tier: str = "",
    segment: str = "general",
    markers: Iterable[str] = (),
    note: str = "",
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Append one outcome row. Raises on bad event / empty card_id (O2).

    ``event`` must be one of EVENTS. Duplicate terminal events for one
    card are allowed but flagged: the newest verdict wins in reads
    (``latest_terminal``), and the history stays intact (O1 — the
    ledger never rewrites Chauncey's earlier word).
    """
    if not isinstance(card_id, str) or not card_id.strip():
        raise ValueError(f"card_id must be a non-empty string, got {card_id!r}")
    if event not in EVENTS:
        raise ValueError(f"event must be one of {EVENTS}, got {event!r}")
    if not isinstance(note, str):
        raise ValueError(f"note must be a string, got {type(note).__name__}")
    if composite is not None:
        if (
            isinstance(composite, bool)
            or not isinstance(composite, (int, float))
            or not 0.0 <= float(composite) <= 100.0
        ):
            raise ValueError(
                f"composite must be a number in [0, 100], got {composite!r}"
            )
    return _append(
        {
            "card_id": card_id.strip(),
            "event": event,
            "title": str(title)[:200],
            "composite": None if composite is None else float(composite),
            "tier": str(tier)[:32],
            "segment": str(segment)[:64],
            "markers": sorted({str(m)[:64] for m in markers}),
            "note": str(note)[:500],
        },
        path=path,
    )


def record_sighting(card, markers: Iterable[str] = (),
                     path: Optional[Path] = None) -> Dict[str, Any]:
    """Record that a score card was written (the machine's own assessment).

    ``card`` is a scoring.ScoreCard (duck-typed: opportunity_id, title,
    composite, tier, segment). Called automatically from
    ``DemandPulse.score_five_factor`` — never by hand.
    """
    return record_event(
        card.opportunity_id,
        "sighting",
        title=card.title,
        composite=card.composite,
        tier=card.tier,
        segment=getattr(card, "segment", "general"),
        markers=markers,
        note="auto: card scored",
        path=path,
    )


def record_conversion(
    card_id: str,
    outcome: str,
    note: str = "",
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Record Chauncey's verdict on a card: 'converted' or 'missed'.

    Explicit call only — the machine never infers this (O2).
    """
    if outcome not in ("converted", "missed"):
        raise ValueError(
            f"outcome must be 'converted' or 'missed', got {outcome!r}"
        )
    return record_event(card_id, outcome, note=note, path=path)


def sweep_stale(
    cards: Iterable[Any],
    stale_days: int = 30,
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Mark cards older than ``stale_days`` with no terminal event 'stale'.

    ``cards`` are ScoreCards (duck-typed: opportunity_id, scored_at).
    Explicit maintenance call — the sweep is run by Chauncey or a cron
    he approves, never silently by the scorer. Returns a receipt.
    """
    if isinstance(stale_days, bool) or not isinstance(stale_days, int) \
            or stale_days < 1:
        raise ValueError(f"stale_days must be a positive int, got {stale_days!r}")
    now = datetime.now(timezone.utc)
    terminal = _terminal_by_card(path=path)
    receipt = {"checked": 0, "staled": 0, "staled_ids": []}
    for card in cards:
        cid = str(getattr(card, "opportunity_id", "") or "")
        if not cid or cid in terminal:
            continue
        receipt["checked"] += 1
        try:
            scored = datetime.fromisoformat(str(card.scored_at))
        except (ValueError, TypeError):
            continue
        if scored.tzinfo is None:
            scored = scored.replace(tzinfo=timezone.utc)
        if (now - scored).days >= stale_days:
            record_event(cid, "stale", title=getattr(card, "title", ""),
                         composite=getattr(card, "composite", None),
                         tier=getattr(card, "tier", ""),
                         segment=getattr(card, "segment", "general"),
                         note=f"auto: no verdict after {stale_days}d",
                         path=path)
            receipt["staled"] += 1
            receipt["staled_ids"].append(cid)
    return receipt


# ---------------------------------------------------------------------------
# Reads — corrupt lines skipped, never fatal (O1)


def read_rows(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Read all ledger rows. Bad lines are skipped, never fatal."""
    p = path or ledger_path()
    rows: List[Dict[str, Any]] = []
    if not p.exists():
        return rows
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and row.get("event") in EVENTS:
                rows.append(row)
    return rows


def _terminal_by_card(path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Latest terminal event per card_id (newest verdict wins)."""
    latest: Dict[str, Dict[str, Any]] = {}
    for row in read_rows(path):
        if row.get("event") in TERMINAL_EVENTS:
            latest[row["card_id"]] = row
    return latest


def resolved_pairs(path: Optional[Path] = None) -> List[Tuple[Dict[str, Any], str]]:
    """(sighting row, terminal event) for cards with a verdict.

    A card counts once: its latest sighting paired with its latest
    terminal event. Cards with no sighting row are skipped — a verdict
    without a recorded assessment is not calibrated.
    """
    sightings: Dict[str, Dict[str, Any]] = {}
    for row in read_rows(path):
        if row.get("event") == "sighting":
            sightings[row["card_id"]] = row
    pairs = []
    for cid, term in _terminal_by_card(path).items():
        if cid in sightings:
            pairs.append((sightings[cid], term["event"]))
    return pairs


# ---------------------------------------------------------------------------
# Calibration — advisory only (O3)


def sighted_ids(path: Optional[Path] = None) -> set:
    """Card ids that already have at least one sighting row.

    Used by the ``outcomes sync`` backfill so pre-existing score cards
    get sighting rows without duplicating ones already recorded.
    """
    ids = set()
    for row in read_rows(path):
        if row.get("event") == "sighting" and row.get("card_id"):
            ids.add(row["card_id"])
    return ids


def marker_stats(path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Per need-marker: sightings, resolved, conversion rate.

    Pure read of the ledger. Rates below MIN_SIGHTINGS_DEFAULT resolved
    cards are reported with ``credible: False`` — the number is shown,
    but no claim rides on it.
    """
    stats: Dict[str, Dict[str, Any]] = {}
    for sight, event in resolved_pairs(path):
        for marker in sight.get("markers") or []:
            s = stats.setdefault(
                marker, {"sightings": 0, "converted": 0, "missed": 0}
            )
            s["sightings"] += 1
            if event == "converted":
                s["converted"] += 1
            elif event == "missed":
                s["missed"] += 1
    for marker, s in stats.items():
        resolved = s["converted"] + s["missed"]
        s["resolved"] = resolved
        s["conversion_rate"] = (
            round(s["converted"] / resolved, 3) if resolved else 0.0
        )
        s["credible"] = resolved >= MIN_SIGHTINGS_DEFAULT
    return stats


def effective_markers(
    min_sightings: int = MIN_SIGHTINGS_DEFAULT,
    path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Markers whose conversion rate beats 2x the ledger baseline.

    Advisory list only (O3). A marker needs >= ``min_sightings``
    resolved cards AND a conversion rate at least double the overall
    baseline to be listed. Empty list when the ledger is thin — that
    is the honest answer, not a failure.
    """
    pairs = resolved_pairs(path)
    if not pairs:
        return []
    base_conv = sum(1 for _, e in pairs if e == "converted")
    base_resolved = sum(1 for _, e in pairs if e in ("converted", "missed"))
    baseline = (base_conv / base_resolved) if base_resolved else 0.0
    out = []
    for marker, s in marker_stats(path).items():
        if s["resolved"] >= min_sightings and baseline > 0 \
                and s["conversion_rate"] >= 2 * baseline:
            out.append(
                {
                    "marker": marker,
                    "resolved": s["resolved"],
                    "conversion_rate": s["conversion_rate"],
                    "baseline": round(baseline, 3),
                    "lift": round(s["conversion_rate"] / baseline, 2),
                }
            )
    return sorted(out, key=lambda d: -d["lift"])


def suggest_thresholds(
    min_resolved: int = MIN_RESOLVED_DEFAULT,
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Advisory threshold suggestion from conversion-by-composite deciles.

    Returns a decile table plus ``suggestion``: the lowest composite
    floor whose decile converts at >= 50%, or None with a reason when
    the ledger is too thin. NEVER mutates scoring state (O3) — the
    suggestion is data Chauncey can accept or ignore.
    """
    pairs = resolved_pairs(path)
    resolved = [(s, e) for s, e in pairs if e in ("converted", "missed")]
    report: Dict[str, Any] = {
        "resolved": len(resolved),
        "min_resolved": min_resolved,
        "deciles": [],
        "suggestion": None,
        "reason": "",
    }
    if len(resolved) < min_resolved:
        report["reason"] = (
            f"thin ledger: {len(resolved)} resolved outcomes, "
            f"need {min_resolved} before any suggestion"
        )
        return report
    buckets: Dict[int, Dict[str, int]] = {}
    for sight, event in resolved:
        comp = sight.get("composite")
        if not isinstance(comp, (int, float)):
            continue
        dec = min(int(float(comp) // 10) * 10, 90)
        b = buckets.setdefault(dec, {"n": 0, "converted": 0})
        b["n"] += 1
        if event == "converted":
            b["converted"] += 1
    for dec in sorted(buckets):
        b = buckets[dec]
        report["deciles"].append(
            {
                "floor": dec,
                "n": b["n"],
                "converted": b["converted"],
                "rate": round(b["converted"] / b["n"], 3),
            }
        )
    for d in sorted(report["deciles"], key=lambda x: x["floor"]):
        if d["n"] >= 3 and d["rate"] >= 0.5:
            report["suggestion"] = {
                "threshold": d["floor"],
                "decile_rate": d["rate"],
                "decile_n": d["n"],
            }
            report["reason"] = (
                f"decile {d['floor']}+ converts at {d['rate']:.0%} "
                f"(n={d['n']}); suggestion only — scoring untouched"
            )
            break
    if report["suggestion"] is None:
        report["reason"] = "no decile converts at >= 50% — no suggestion"
    return report


# ---------------------------------------------------------------------------
# Human surface — one-way JSONL -> workbook (O4)


def export_xlsx(path: Optional[Path] = None,
                out: Optional[Path] = None) -> Path:
    """Render the ledger as a local .xlsx workbook (one-way, O4).

    Sheets: 'outcomes' (every row), 'calibration' (marker stats +
    threshold suggestion). Raises an honest ImportError when openpyxl
    is missing — ``export_csv`` is the stdlib fallback.
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise ImportError(
            "export_xlsx needs openpyxl (pip install openpyxl); "
            "use export_csv() for the stdlib fallback"
        ) from exc

    rows = read_rows(path)
    out = out or (
        Path.home() / "workspace" / "your_files" / "demandpulse-outcomes.xlsx"
    )
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "outcomes"
    head_font = Font(bold=True)
    headers = ["ts", "card_id", "title", "composite", "tier", "segment",
               "event", "markers", "note"]
    ws.append(headers)
    for c in ws[1]:
        c.font = head_font
    for r in rows:
        ws.append([
            r.get("ts", ""), r.get("card_id", ""), r.get("title", ""),
            r.get("composite"), r.get("tier", ""), r.get("segment", ""),
            r.get("event", ""), ", ".join(r.get("markers") or []),
            r.get("note", ""),
        ])
    for i, h in enumerate(headers, 1):
        ws.column_dimensions[get_column_letter(i)].width = max(len(h) + 2, 14)
    ws.column_dimensions["C"].width = 32
    ws.column_dimensions["I"].width = 40

    cal = wb.create_sheet("calibration")
    cal.append(["metric", "value"])
    for c in cal[1]:
        c.font = head_font
    stats = marker_stats(path)
    cal.append(["markers tracked", len(stats)])
    for marker, s in sorted(stats.items(), key=lambda kv: -kv[1]["resolved"]):
        cal.append([
            f"marker: {marker}",
            f"resolved={s['resolved']} rate={s['conversion_rate']:.0%} "
            f"credible={s['credible']}",
        ])
    sug = suggest_thresholds(path=path)
    cal.append(["resolved outcomes", sug["resolved"]])
    cal.append(["threshold suggestion",
                json.dumps(sug["suggestion"]) if sug["suggestion"] else "none"])
    cal.append(["reason", sug["reason"]])
    cal.append(["note",
                "Advisory only — the ledger never changes scoring (O3). "
                "The .xlsx is a view; the JSONL is the record (O4)."])
    for i in (1, 2):
        cal.column_dimensions[get_column_letter(i)].width = 28 if i == 1 else 70

    wb.save(out)
    return out


def export_csv(path: Optional[Path] = None,
               out: Optional[Path] = None) -> Path:
    """Stdlib fallback human surface: ledger -> CSV (one-way, O4)."""
    rows = read_rows(path)
    out = Path(out) if out else Path(
        str(ledger_path()).replace(".jsonl", ".csv"))
    out.parent.mkdir(parents=True, exist_ok=True)
    headers = ["ts", "card_id", "title", "composite", "tier", "segment",
               "event", "markers", "note"]
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=headers, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            rr = dict(r)
            rr["markers"] = ", ".join(rr.get("markers") or [])
            w.writerow({h: rr.get(h, "") for h in headers})
    return out


def render_report(path: Optional[Path] = None) -> str:
    """Plain-text ledger summary for the CLI / chat."""
    rows = read_rows(path)
    pairs = resolved_pairs(path)
    lines = [
        "=== DemandPulse outcome ledger ===",
        f"rows={len(rows)}  cards with verdicts={len(pairs)}",
        "",
    ]
    counts: Dict[str, int] = {}
    for r in rows:
        counts[r["event"]] = counts.get(r["event"], 0) + 1
    for ev in EVENTS:
        lines.append(f"  {ev:10s} {counts.get(ev, 0)}")
    lines.append("")
    sug = suggest_thresholds(path=path)
    lines.append(f"resolved outcomes: {sug['resolved']} "
                 f"(min {sug['min_resolved']})")
    lines.append(f"suggestion: {sug['suggestion'] or 'none'}")
    if sug["reason"]:
        lines.append(f"reason: {sug['reason']}")
    eff = effective_markers(path=path)
    lines.append("")
    lines.append(f"effective markers (>{MIN_SIGHTINGS_DEFAULT} resolved, "
                 f"2x baseline): {len(eff)}")
    for e in eff[:10]:
        lines.append(f"  {e['marker']!r}: rate={e['conversion_rate']:.0%} "
                     f"lift={e['lift']}x (n={e['resolved']})")
    lines.append("")
    lines.append("Calibration is advisory — scoring is never auto-changed (O3).")
    return "\n".join(lines)
