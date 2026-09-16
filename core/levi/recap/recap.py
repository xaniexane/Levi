"""Local annual recap — Wrapped-style cards computed on-device.

Spotify Wrapped mines your year to make you advertise Spotify. The
recap is the product; you are the ad surface. LEVI Recap inverts it:
the *same* delight (totals, streaks, top categories, milestones,
shareable cards) computed entirely on-device from a JSONL event source
you own, rendered as text and standalone HTML cards. Nothing leaves the
machine. Share the card if you want — the data never had to travel to
make it.

EVENT SCHEMA (one JSON object per line):

    {"ts": "2026-03-14T09:30:00", "category": "reading",
     "kind": "session", "label": "Dune", "value": 45, "unit": "minutes"}

- ts: ISO-8601 datetime (required)
- category: free string, e.g. "reading", "coding", "music" (required)
- kind: free string, e.g. "session", "checkin" (required)
- label: what it was (optional)
- value: numeric magnitude (optional, default 1)
- unit: e.g. "minutes", "pages", "km" (optional)

Stats computed: per-category totals, active days, longest active-day
streak, top categories by events and by value, busiest month/day-of-week,
milestones (first event, 100th/500th/1000th event, biggest single day),
per-category "top label" by accumulated value.

:func:`sample_events` generates a deterministic synthetic year for tests
and demos — clearly labeled synthetic, never mixed with real data.
"""

from __future__ import annotations

import html
import json
import os
import random
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

ENC = "utf-8"


def recap_home(home: "str | os.PathLike[str] | None" = None) -> Path:
    base = Path(home) if home is not None else Path(os.path.expanduser("~"))
    return base / ".levi" / "recap"


class RecapError(Exception):
    pass


def _parse_ts(raw: str) -> datetime:
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        raise RecapError("bad ts %r — use ISO-8601" % raw)


def load_events(path: "str | os.PathLike[str]") -> List[Dict[str, Any]]:
    """Load + validate a JSONL event source. Raises RecapError on bad rows."""
    events = []
    p = Path(path)
    if not p.exists():
        raise RecapError("no event file: %s" % p)
    for i, line in enumerate(p.read_text(encoding=ENC).splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RecapError("line %d: bad JSON (%s)" % (i, exc))
        if not isinstance(row, dict):
            raise RecapError("line %d: must be an object" % i)
        if row.get("synthetic"):
            continue  # sample-generator marker line, not an event
        for key in ("ts", "category", "kind"):
            if key not in row:
                raise RecapError("line %d: missing %r" % (i, key))
        row["_dt"] = _parse_ts(str(row["ts"]))
        row["_day"] = row["_dt"].date().isoformat()
        row["_value"] = float(row.get("value", 1))
        events.append(row)
    events.sort(key=lambda r: r["_dt"])
    return events


def compute_stats(events: List[Dict[str, Any]],
                  year: Optional[int] = None) -> Dict[str, Any]:
    """Compute recap stats. All local, all honest — counts are real."""
    if year is not None:
        events = [e for e in events if e["_dt"].year == year]
    if not events:
        return {"events": 0, "empty": True}
    days = sorted({e["_day"] for e in events})
    # longest active-day streak
    longest, run, prev = 0, 0, None
    for d in days:
        dd = date.fromisoformat(d)
        run = run + 1 if (prev and dd == prev + timedelta(days=1)) else 1
        longest = max(longest, run)
        prev = dd
    by_cat = Counter(e["category"] for e in events)
    by_cat_value: Dict[str, float] = defaultdict(float)
    for e in events:
        by_cat_value[e["category"]] += e["_value"]
    by_month = Counter(e["_dt"].strftime("%Y-%m") for e in events)
    by_dow = Counter(e["_dt"].strftime("%A") for e in events)
    per_day_value: Dict[str, float] = defaultdict(float)
    for e in events:
        per_day_value[e["_day"]] += e["_value"]
    biggest_day = max(per_day_value.items(), key=lambda kv: kv[1])
    top_labels: Dict[str, Any] = {}
    label_value: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for e in events:
        if e.get("label"):
            label_value[e["category"]][str(e["label"])] += e["_value"]
    for cat, labels in label_value.items():
        top = max(labels.items(), key=lambda kv: kv[1])
        top_labels[cat] = {"label": top[0], "value": round(top[1], 1)}
    milestones = [
        {"at": events[0]["_day"], "text": "first event: %s" % (events[0].get("label") or events[0]["kind"])},
    ]
    for n in (100, 500, 1000, 5000):
        if len(events) >= n:
            milestones.append({"at": events[n - 1]["_day"],
                               "text": "%dth event recorded" % n})
    year_label = year or "%d–%d" % (events[0]["_dt"].year, events[-1]["_dt"].year)
    return {
        "events": len(events),
        "year": year_label,
        "active_days": len(days),
        "longest_streak_days": longest,
        "first_day": days[0], "last_day": days[-1],
        "top_categories_by_events": by_cat.most_common(5),
        "top_categories_by_value": sorted(
            ((c, round(v, 1)) for c, v in by_cat_value.items()),
            key=lambda kv: kv[1], reverse=True)[:5],
        "units": sorted({str(e.get("unit", "")) for e in events if e.get("unit")}),
        "busiest_month": by_month.most_common(1)[0] if by_month else None,
        "busiest_weekday": by_dow.most_common(1)[0] if by_dow else None,
        "biggest_day": {"day": biggest_day[0], "value": round(biggest_day[1], 1)},
        "top_labels": top_labels,
        "milestones": milestones,
        "empty": False,
    }


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def render_text(stats: Dict[str, Any]) -> str:
    if stats.get("empty"):
        return "No events — nothing to recap. (Feed it a JSONL event file first.)"
    L = []
    L.append("=== LEVI RECAP %s ===" % stats["year"])
    L.append("%d events across %d active days (%s → %s)" % (
        stats["events"], stats["active_days"],
        stats["first_day"], stats["last_day"]))
    L.append("longest daily streak: %d days" % stats["longest_streak_days"])
    L.append("")
    L.append("top categories (by events):")
    for cat, n in stats["top_categories_by_events"]:
        L.append("  %-18s %d" % (cat, n))
    if stats["top_categories_by_value"]:
        L.append("top categories (by value):")
        for cat, v in stats["top_categories_by_value"]:
            L.append("  %-18s %s" % (cat, v))
    if stats["busiest_month"]:
        L.append("busiest month: %s (%d events)" % stats["busiest_month"])
    if stats["busiest_weekday"]:
        L.append("busiest weekday: %s (%d events)" % stats["busiest_weekday"])
    bd = stats["biggest_day"]
    L.append("biggest day: %s (%s)" % (bd["day"], bd["value"]))
    if stats["top_labels"]:
        L.append("favorites:")
        for cat, t in stats["top_labels"].items():
            L.append("  %s: %s (%s)" % (cat, t["label"], t["value"]))
    L.append("milestones:")
    for m in stats["milestones"]:
        L.append("  %s — %s" % (m["at"], m["text"]))
    L.append("")
    L.append("(computed on-device from your own data — nothing left the machine)")
    return "\n".join(L)


_CARD_CSS = """
body{background:#0b0b12;color:#f2f0ff;font-family:system-ui,sans-serif;
margin:0;display:flex;justify-content:center;padding:32px}
.card{max-width:520px;width:100%;background:linear-gradient(135deg,#1a1033,#0d2b45);
border-radius:24px;padding:36px;box-shadow:0 20px 60px rgba(0,0,0,.5)}
.kicker{letter-spacing:.3em;font-size:12px;color:#9d8cff}
h1{font-size:40px;margin:.2em 0}
.big{font-size:56px;font-weight:800;color:#ffd166}
.row{display:flex;gap:16px;margin:16px 0}
.stat{flex:1;background:rgba(255,255,255,.06);border-radius:16px;padding:16px}
.stat .n{font-size:28px;font-weight:700}
.stat .l{font-size:12px;color:#b9b3d9}
li{margin:4px 0}.foot{margin-top:24px;font-size:12px;color:#8f8aa8}
"""


def render_html(stats: Dict[str, Any], title: str = "My Year in Review") -> str:
    """Standalone HTML card — inline CSS, zero external assets/requests."""
    if stats.get("empty"):
        body = "<p>No events — nothing to recap.</p>"
    else:
        cats = "".join(
            "<li>%s — %d events</li>" % (html.escape(c), n)
            for c, n in stats["top_categories_by_events"])
        miles = "".join(
            "<li>%s — %s</li>" % (html.escape(m["at"]), html.escape(m["text"]))
            for m in stats["milestones"])
        body = """
<div class="row">
  <div class="stat"><div class="n">{events}</div><div class="l">events</div></div>
  <div class="stat"><div class="n">{days}</div><div class="l">active days</div></div>
  <div class="stat"><div class="n">{streak}</div><div class="l">day streak</div></div>
</div>
<h3>Top categories</h3><ul>{cats}</ul>
<h3>Milestones</h3><ul>{miles}</ul>
""".format(events=stats["events"], days=stats["active_days"],
           streak=stats["longest_streak_days"], cats=cats, miles=miles)
    return """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>{css}</style></head>
<body><div class="card">
<div class="kicker">LEVI RECAP · {year} · ON-DEVICE</div>
<h1>{title}</h1>
{body}
<div class="foot">Computed locally from your own data. Nothing left the machine.</div>
</div></body></html>""".format(
        title=html.escape(title), css=_CARD_CSS,
        year=html.escape(str(stats.get("year", ""))), body=body)


# ---------------------------------------------------------------------------
# sample generator (deterministic synthetic data for tests/demos)
# ---------------------------------------------------------------------------

def sample_events(path: "str | os.PathLike[str]", year: int = 2026,
                  n: int = 400, seed: int = 7) -> Path:
    """Write a deterministic SYNTHETIC year of events. Labeled synthetic."""
    rng = random.Random(seed)
    cats = [("reading", "session", "minutes", ["Dune", "Project Hail Mary", "essays"]),
            ("coding", "session", "minutes", ["levi", "side project"]),
            ("running", "run", "km", ["morning loop", "trail"]),
            ("music", "listen", "minutes", ["jazz", "ambient"])]
    p = Path(path)
    with p.open("w", encoding=ENC) as fh:
        fh.write('{"synthetic": true, "note": "generated sample data — not real activity"}\n')
        for _ in range(n):
            cat, kind, unit, labels = rng.choice(cats)
            day = date(year, 1, 1) + timedelta(days=rng.randrange(0, 300))
            fh.write(json.dumps({
                "ts": datetime(day.year, day.month, day.day,
                               rng.randrange(6, 23),
                               rng.randrange(0, 60)).isoformat(),
                "category": cat, "kind": kind,
                "label": rng.choice(labels),
                "value": round(rng.uniform(10, 120), 1) if unit != "km"
                else round(rng.uniform(2, 15), 1),
                "unit": unit,
            }) + "\n")
    return p
