"""Income batch D — data-products. Slots 61-72.

Twelve ORIGINAL automated income generators, each building a real local
data product from user-supplied input (params) or a bundled deterministic
sample fixture: CSVs, ledgers, plans, reports. Stdlib only. No network,
no paid APIs, no third-party code, no scraping. Every line original.

Each ``_run_*`` honors ``dry_run``: dry runs report what WOULD be written
and touch no deliverable files (only the engine's run log writes).
Artifacts land under ``<levi_home>/.levi/income/work/<id>/``.

Pricing doctrine (Chauncey, 2026-09-17): no free core, entry $1-5,
~30-60% below the giants. Quoted amounts are pricing advice only —
income is recorded solely by Chauncey via engine.record_income with
basis="confirmed". The engine never invents income.
"""

from __future__ import annotations

import csv
import io
import re
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

from levi.income.engine import Generator, WorkReport, register

__all__ = ["register_batch_d"]


# ---------------------------------------------------------------------------
# Shared helpers (batch-D internal)
# ---------------------------------------------------------------------------

def _anchor(params: Dict[str, Any], key: str) -> date:
    """Anchor date from params (YYYY-MM-DD) or today."""
    raw = (params or {}).get(key)
    if raw:
        return datetime.strptime(str(raw), "%Y-%m-%d").date()
    return date.today()


def _csv(header: List[str], rows: List[List[Any]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


def _work_dir(ctx: Dict[str, Any], gid: str) -> Path:
    home = ctx.get("levi_home") or Path.home()
    return Path(home) / ".levi" / "income" / "work" / gid


def _emit(
    ctx: Dict[str, Any],
    gid: str,
    files: Dict[str, str],
    quoted: float,
    notes: str,
) -> WorkReport:
    """Write artifacts (real run) or report what would be written (dry run)."""
    if ctx.get("dry_run"):
        return WorkReport(
            generator_id=gid,
            produced=[f"would write {name}" for name in files],
            quoted_amount_usd=quoted,
            notes=notes + " (dry-run: no deliverable files written)",
        )
    d = _work_dir(ctx, gid)
    d.mkdir(parents=True, exist_ok=True)
    produced = []
    for name, text in files.items():
        p = d / name
        p.write_text(text, encoding="utf-8")
        produced.append(str(p))
    return WorkReport(
        generator_id=gid,
        produced=produced,
        quoted_amount_usd=quoted,
        notes=notes,
    )


def _money(x: float) -> str:
    return f"${x:,.2f}"


def _daterange(start: date, days: int):
    for d in range(days):
        yield start + timedelta(days=d)


# ---------------------------------------------------------------------------
# 61. habit-tracker-kit — habit-tracking CSV + streak summary
# ---------------------------------------------------------------------------

_HABITS_SAMPLE = [
    {"name": "read-20min", "target_per_week": 5},
    {"name": "walk-30min", "target_per_week": 5},
    {"name": "no-soda", "target_per_week": 7},
    {"name": "meditate-10min", "target_per_week": 4},
]


def _habit_completions(habits, start, days, user_map):
    """Deterministic sample completions (~70%) unless user supplied dates."""
    out = {}
    for hi, h in enumerate(habits):
        name = h["name"]
        if user_map and name in user_map:
            out[name] = set(user_map[name])
            continue
        done = set()
        for d, day in enumerate(_daterange(start, days)):
            if ((d * 3 + hi * 5) % 10) < 7:
                done.add(day.isoformat())
        out[name] = done
    return out


def _streaks(done: set, start: date, days: int) -> Tuple[int, int, int]:
    total = run = longest = 0
    for day in _daterange(start, days):
        if day.isoformat() in done:
            run += 1
            total += 1
            longest = max(longest, run)
        else:
            run = 0
    return total, run, longest  # completions, current streak, longest streak


def _run_habit_tracker(ctx):
    gid = "habit-tracker-kit"
    params = ctx.get("params") or {}
    habits = params.get("habits") or _HABITS_SAMPLE
    days = int(params.get("days", 30))
    end = _anchor(params, "end")
    start = end - timedelta(days=days - 1)
    fixture = "habits" not in params
    completions = _habit_completions(habits, start, days, params.get("completions"))

    day_rows, streak_rows, summary = [], [], []
    summary.append("HABIT TRACKER — streak summary")
    summary.append(f"window: {start} .. {end} ({days} days)")
    summary.append("")
    for h in habits:
        name = h["name"]
        target = int(h.get("target_per_week", 5))
        done = completions[name]
        total, cur, longest = _streaks(done, start, days)
        rate = round(100.0 * total / max(1, days), 1)
        on_pace = "yes" if rate >= round(100.0 * target / 7, 1) else "no"
        for day in _daterange(start, days):
            day_rows.append([day.isoformat(), name, 1 if day.isoformat() in done else 0])
        streak_rows.append([name, target, days, total, rate, cur, longest, on_pace])
        summary.append(
            f"- {name}: {total}/{days} ({rate}%), current streak {cur}d, "
            f"longest {longest}d, target {target}/wk, on pace: {on_pace}"
        )
    summary.append("")
    summary.append("sample fixture" if fixture else "built from your inputs")

    files = {
        "habits.csv": _csv(["date", "habit", "done"], day_rows),
        "streaks.csv": _csv(
            ["habit", "target_per_week", "days_tracked", "completions",
             "completion_rate_pct", "current_streak", "longest_streak", "on_pace"],
            streak_rows,
        ),
        "habit_summary.txt": "\n".join(summary) + "\n",
    }
    return _emit(ctx, gid, files, 3.0,
                 f"Habit tracker kit: {len(habits)} habits x {days} days; "
                 + ("sample fixture" if fixture else "user-supplied habits"))


# ---------------------------------------------------------------------------
# 62. budget-ledger-builder — zero-based budget ledger
# ---------------------------------------------------------------------------

_BUDGET_INCOME_SAMPLE = [
    {"source": "paycheck", "amount": 2800.00},
    {"source": "side gig", "amount": 450.00},
]
_BUDGET_EXPENSE_SAMPLE = [
    {"name": "rent", "amount": 950.00, "category": "housing"},
    {"name": "groceries", "amount": 320.00, "category": "food"},
    {"name": "bus pass", "amount": 60.00, "category": "transport"},
    {"name": "electric", "amount": 85.00, "category": "utilities"},
    {"name": "internet", "amount": 55.00, "category": "utilities"},
    {"name": "fun money", "amount": 120.00, "category": "fun"},
    {"name": "card payment", "amount": 200.00, "category": "debt"},
]


def _run_budget_ledger(ctx):
    gid = "budget-ledger-builder"
    params = ctx.get("params") or {}
    income = params.get("income") or _BUDGET_INCOME_SAMPLE
    expenses = params.get("expenses") or _BUDGET_EXPENSE_SAMPLE
    month = str(params.get("month") or date.today().strftime("%Y-%m"))
    fixture = "income" not in params and "expenses" not in params

    total_in = round(sum(float(i["amount"]) for i in income), 2)
    total_out = round(sum(float(e["amount"]) for e in expenses), 2)
    remainder = round(total_in - total_out, 2)

    lines, n = [], 0
    for i in income:
        n += 1
        lines.append([n, month, i["source"], "income", "income", f"{float(i['amount']):.2f}"])
    by_cat = defaultdict(float)
    for e in expenses:
        n += 1
        amt = float(e["amount"])
        by_cat[e.get("category", "other")] += amt
        lines.append([n, month, e["name"], e.get("category", "other"), "expense", f"{amt:.2f}"])

    summary = ["ZERO-BASED BUDGET LEDGER", f"month: {month}", ""]
    summary.append(f"total income:   {_money(total_in)}")
    summary.append(f"total expenses: {_money(total_out)}")
    summary.append("by category:")
    for cat in sorted(by_cat):
        summary.append(f"  {cat}: {_money(by_cat[cat])}")
    if remainder >= 0:
        n += 1
        lines.append([n, month, "savings (auto-assigned)", "savings", "assign", f"{remainder:.2f}"])
        summary.append(f"remainder -> savings: {_money(remainder)}")
        summary.append("zero-based check: PASS — every dollar assigned")
        check = "PASS"
    else:
        summary.append(f"SHORTFALL: {_money(-remainder)} — trim expenses before this budget balances")
        summary.append("zero-based check: FAIL — spending exceeds income")
        check = "FAIL"

    files = {
        "ledger.csv": _csv(["line", "month", "entry", "category", "kind", "amount"], lines),
        "budget_summary.txt": "\n".join(summary) + "\n",
    }
    return _emit(ctx, gid, files, 2.0,
                 f"Zero-based ledger for {month}: income {_money(total_in)}, "
                 f"check {check}; " + ("sample fixture" if fixture else "user inputs"))


# ---------------------------------------------------------------------------
# 63. price-watchlist — manual-entry price tracker with change alerts
# ---------------------------------------------------------------------------

_WATCH_SAMPLE = [
    {"name": "coffee beans 1kg", "unit": "bag", "alert_below": 14.00, "alert_drop_pct": 15.0,
     "prices": [["2026-08-20", 16.50], ["2026-08-27", 16.00], ["2026-09-03", 16.20],
                ["2026-09-10", 15.80], ["2026-09-17", 13.20]]},
    {"name": "eggs (dozen)", "unit": "dozen", "alert_below": 3.00, "alert_drop_pct": 20.0,
     "prices": [["2026-08-20", 4.20], ["2026-08-27", 4.35], ["2026-09-03", 4.10],
                ["2026-09-10", 4.25], ["2026-09-17", 4.30]]},
    {"name": "usb-c cable 2m", "unit": "each", "alert_below": 8.00, "alert_drop_pct": 25.0,
     "prices": [["2026-08-20", 11.99], ["2026-08-27", 11.99], ["2026-09-03", 10.49],
                ["2026-09-10", 10.49], ["2026-09-17", 7.49]]},
]


def _run_price_watchlist(ctx):
    gid = "price-watchlist"
    params = ctx.get("params") or {}
    items = params.get("items") or _WATCH_SAMPLE
    fixture = "items" not in params

    price_rows, report, alerts = [], ["PRICE WATCHLIST", ""], []
    for it in items:
        name, unit = it["name"], it.get("unit", "each")
        below = float(it.get("alert_below", 0) or 0)
        drop_pct = float(it.get("alert_drop_pct", 15) or 15)
        prices = sorted((str(d), float(p)) for d, p in it["prices"])
        for d, p in prices:
            price_rows.append([name, d, f"{p:.2f}", unit])
        first, last = prices[0][1], prices[-1][1]
        lo, hi = min(p for _, p in prices), max(p for _, p in prices)
        chg = round(100.0 * (last - first) / first, 1) if first else 0.0
        report.append(f"{name} ({unit}): now {_money(last)}, window {_money(first)} -> {_money(last)} "
                      f"({chg:+.1f}%), low {_money(lo)}, high {_money(hi)}")
        if below and last < below:
            alerts.append(f"TARGET HIT: {name} at {_money(last)} is below your {_money(below)} target")
        if chg <= -drop_pct:
            alerts.append(f"DROP ALERT: {name} fell {abs(chg):.1f}% (threshold {drop_pct}%)")
    report.append("")
    report.append("ALERTS" if alerts else "no alerts — all prices within your thresholds")
    report.extend(f"- {a}" for a in alerts)

    files = {
        "prices.csv": _csv(["item", "date", "price", "unit"], price_rows),
        "watchlist_report.txt": "\n".join(report) + "\n",
    }
    return _emit(ctx, gid, files, 3.0,
                 f"Price watchlist: {len(items)} items, {len(alerts)} alerts; "
                 + ("sample fixture" if fixture else "user price entries"))


# ---------------------------------------------------------------------------
# 64. reading-log-atlas — reading log + stats (pace, genres, ratings)
# ---------------------------------------------------------------------------

_READING_SAMPLE = [
    {"title": "The Left Hand of Darkness", "author": "Le Guin", "genre": "sci-fi",
     "pages": 304, "started": "2026-08-01", "finished": "2026-08-12", "rating": 5},
    {"title": "Thinking, Fast and Slow", "author": "Kahneman", "genre": "nonfiction",
     "pages": 499, "started": "2026-08-13", "finished": "2026-08-30", "rating": 4},
    {"title": "The Hobbit", "author": "Tolkien", "genre": "fantasy",
     "pages": 310, "started": "2026-09-01", "finished": "2026-09-08", "rating": 5},
    {"title": "Atomic Habits", "author": "Clear", "genre": "nonfiction",
     "pages": 320, "started": "2026-09-09", "finished": "2026-09-16", "rating": 4},
    {"title": "Dune", "author": "Herbert", "genre": "sci-fi",
     "pages": 688, "started": "2026-09-17", "finished": "", "rating": ""},
]


def _run_reading_log(ctx):
    gid = "reading-log-atlas"
    params = ctx.get("params") or {}
    books = params.get("books") or _READING_SAMPLE
    fixture = "books" not in params

    log_rows, report = [], ["READING LOG ATLAS", ""]
    finished = [b for b in books if b.get("finished")]
    reading = [b for b in books if not b.get("finished")]
    total_pages = sum(int(b.get("pages", 0) or 0) for b in finished)
    ratings = [int(b["rating"]) for b in finished if str(b.get("rating", "")).strip()]

    pace = 0.0
    if finished:
        starts = [b["started"] for b in finished if b.get("started")]
        ends = [b["finished"] for b in finished]
        span = (max(ends) > min(starts)) and (
            datetime.strptime(max(ends), "%Y-%m-%d").date()
            - datetime.strptime(min(starts), "%Y-%m-%d").date()).days or 1
        pace = round(total_pages / max(1, span), 1)

    genres = defaultdict(list)
    for b in finished:
        if str(b.get("rating", "")).strip():
            genres[b.get("genre", "unknown")].append(int(b["rating"]))

    for b in books:
        status = "finished" if b.get("finished") else "reading"
        log_rows.append([b.get("title", ""), b.get("author", ""), b.get("genre", ""),
                         b.get("pages", ""), b.get("started", ""), b.get("finished", ""),
                         b.get("rating", ""), status])
    report.append(f"books finished: {len(finished)} | currently reading: {len(reading)}")
    report.append(f"pages finished: {total_pages} | pace: {pace} pages/day")
    if ratings:
        report.append(f"average rating: {round(statistics.mean(ratings), 2)}/5 over {len(ratings)} rated")
    report.append("genres (finished):")
    for g in sorted(genres):
        rs = genres[g]
        report.append(f"  {g}: {len(rs)} books, avg rating {round(statistics.mean(rs), 2)}/5")
    if reading:
        report.append("now reading:")
        report.extend(f"  {b.get('title','')} — {b.get('author','')} ({b.get('pages','?')} pages)" for b in reading)

    files = {
        "reading_log.csv": _csv(["title", "author", "genre", "pages", "started",
                                  "finished", "rating", "status"], log_rows),
        "reading_stats.txt": "\n".join(report) + "\n",
    }
    return _emit(ctx, gid, files, 2.0,
                 f"Reading atlas: {len(books)} books, {len(finished)} finished, "
                 f"pace {pace} ppd; " + ("sample fixture" if fixture else "user book list"))


# ---------------------------------------------------------------------------
# 65. workout-planner-pack — workout plans from goals/equipment/days
# ---------------------------------------------------------------------------

_EXERCISES = {
    "bodyweight": ["push-ups", "bodyweight squats", "reverse lunges", "plank hold",
                   "glute bridges", "superman holds", "mountain climbers", "burpees",
                   "pike push-ups", "side planks"],
    "dumbbells": ["db bench press", "db rows", "goblet squats", "db overhead press",
                  "romanian deadlifts", "db curls", "triceps kickbacks", "db lunges",
                  "renegade rows", "db flyes"],
    "bands": ["band chest press", "band rows", "band squats", "band overhead press",
              "band pull-aparts", "band deadlifts", "band bicep curls", "band lateral walks",
              "band tricep pushdowns", "band good mornings"],
    "full-gym": ["barbell bench press", "barbell squat", "deadlift", "overhead press",
                 "lat pulldown", "leg press", "cable rows", "dumbbell bench",
                 "leg curl", "face pulls"],
}
_SESSION_TEMPLATES = {
    "strength": [("Upper", 4, "6-8", 90, "+1 rep per lift vs last week"),
                 ("Lower", 4, "6-8", 90, "+1 rep per lift vs last week"),
                 ("Full body", 3, "8-10", 75, "add one set to the first lift")],
    "conditioning": [("Circuit A", 3, "40s work", 30, "+5s work interval"),
                     ("Circuit B", 3, "40s work", 30, "+5s work interval")],
    "mobility": [("Flow A", 2, "60s hold", 15, "+10s hold time"),
                 ("Flow B", 2, "60s hold", 15, "+10s hold time")],
    "general": [("Mix A", 3, "10-12", 60, "+1 rep per movement"),
                ("Mix B", 3, "10-12", 60, "+1 rep per movement"),
                ("Mix C", 3, "10-12", 60, "+1 rep per movement")],
}


def _run_workout_planner(ctx):
    gid = "workout-planner-pack"
    params = ctx.get("params") or {}
    goal = str(params.get("goal", "general")).lower()
    if goal not in _SESSION_TEMPLATES:
        goal = "general"
    equipment = str(params.get("equipment", "bodyweight")).lower()
    if equipment not in _EXERCISES:
        equipment = "bodyweight"
    days_pw = max(2, min(6, int(params.get("days_per_week", 3))))
    weeks = max(1, min(12, int(params.get("weeks", 4))))
    fixture = not any(k in params for k in ("goal", "equipment", "days_per_week"))

    lib = _EXERCISES[equipment]
    sessions = _SESSION_TEMPLATES[goal]
    plan_rows, overview = [], []
    overview.append("WORKOUT PLANNER PACK")
    overview.append(f"goal: {goal} | equipment: {equipment} | "
                    f"{days_pw} days/week x {weeks} weeks")
    overview.append("progression: follow the weekly note on each session")
    overview.append("")
    for wk in range(1, weeks + 1):
        for dy in range(1, days_pw + 1):
            sname, sets, reps, rest, prog = sessions[(dy - 1) % len(sessions)]
            for i in range(5):
                ex = lib[(i + wk + dy) % len(lib)]
                note = "" if wk == 1 else prog
                plan_rows.append([wk, dy, sname, ex, sets, reps, rest, note])
    overview.append(f"total sessions: {weeks * days_pw} | exercises per session: 5")
    overview.append("rest days are training too — sleep, protein, water.")

    files = {
        "workout_plan.csv": _csv(["week", "day", "session", "exercise", "sets",
                                   "reps", "rest_sec", "progression_note"], plan_rows),
        "plan_overview.txt": "\n".join(overview) + "\n",
    }
    return _emit(ctx, gid, files, 4.0,
                 f"Workout pack: {goal}/{equipment}, {days_pw}d x {weeks}w, "
                 f"{len(plan_rows)} rows; " + ("sample defaults" if fixture else "user inputs"))


# ---------------------------------------------------------------------------
# 66. meal-prep-planner — weekly meal plans + grocery list from pantry
# ---------------------------------------------------------------------------

_RECIPES = [
    {"name": "black bean tacos", "ingredients": ["tortillas", "black beans", "rice", "onion", "salsa"],
     "tags": ["vegetarian", "low-cost"], "cost": 1.80},
    {"name": "veggie stir fry", "ingredients": ["rice", "frozen veg", "soy sauce", "eggs", "garlic"],
     "tags": ["vegetarian", "low-cost"], "cost": 1.60},
    {"name": "chicken rice bowls", "ingredients": ["chicken breast", "rice", "frozen veg", "soy sauce"],
     "tags": ["high-protein"], "cost": 2.90},
    {"name": "tuna pasta", "ingredients": ["pasta", "tuna", "olive oil", "garlic", "frozen veg"],
     "tags": ["high-protein", "low-cost"], "cost": 2.10},
    {"name": "oatmeal + peanut butter", "ingredients": ["oats", "peanut butter", "banana"],
     "tags": ["vegetarian", "low-cost"], "cost": 0.90},
    {"name": "egg fried rice", "ingredients": ["rice", "eggs", "frozen veg", "soy sauce", "onion"],
     "tags": ["vegetarian", "low-cost"], "cost": 1.40},
    {"name": "lentil soup", "ingredients": ["lentils", "onion", "carrot", "garlic", "rice"],
     "tags": ["vegetarian", "low-cost"], "cost": 1.20},
    {"name": "chicken quesadillas", "ingredients": ["tortillas", "chicken breast", "cheese", "salsa"],
     "tags": ["high-protein"], "cost": 2.70},
    {"name": "bean chili", "ingredients": ["black beans", "rice", "onion", "salsa", "garlic"],
     "tags": ["vegetarian", "low-cost"], "cost": 1.50},
    {"name": "pasta marinara", "ingredients": ["pasta", "canned tomatoes", "garlic", "olive oil"],
     "tags": ["vegetarian", "low-cost"], "cost": 1.30},
    {"name": "greek yogurt bowl", "ingredients": ["yogurt", "banana", "oats", "peanut butter"],
     "tags": ["vegetarian", "high-protein"], "cost": 1.70},
    {"name": "beef tacos", "ingredients": ["tortillas", "ground beef", "onion", "salsa", "rice"],
     "tags": ["high-protein"], "cost": 3.10},
]
_PANTRY_SAMPLE = ["rice", "eggs", "onion", "garlic", "tortillas", "salsa",
                  "peanut butter", "oats", "frozen veg", "soy sauce"]


def _run_meal_prep(ctx):
    gid = "meal-prep-planner"
    params = ctx.get("params") or {}
    diet = str(params.get("diet", "any")).lower()
    pantry = set(str(p).lower() for p in (params.get("pantry") or _PANTRY_SAMPLE))
    days = max(1, min(14, int(params.get("days", 7))))
    meals_pd = max(1, min(4, int(params.get("meals_per_day", 3))))
    fixture = "pantry" not in params and "diet" not in params

    def diet_ok(r):
        if diet == "vegetarian":
            return "vegetarian" in r["tags"]
        if diet == "high-protein":
            return "high-protein" in r["tags"]
        if diet == "low-cost":
            return r["cost"] <= 2.00
        return True

    pool = [r for r in _RECIPES if diet_ok(r)] or _RECIPES
    scored = []
    for r in pool:
        ings = [i.lower() for i in r["ingredients"]]
        overlap = sum(1 for i in ings if i in pantry) / len(ings)
        scored.append((overlap, r["cost"], r))
    scored.sort(key=lambda t: (-t[0], t[1]))

    meals = ["breakfast", "lunch", "dinner", "snack"][:meals_pd]
    plan_rows, grocery = [], Counter()
    total_cost = 0.0
    slot = 0
    for d in range(1, days + 1):
        for m in meals:
            overlap, _, r = scored[slot % len(scored)]
            slot += 1
            plan_rows.append([d, m, r["name"], f"{round(100 * overlap)}%"])
            total_cost += r["cost"]
            for i in r["ingredients"]:
                if i.lower() not in pantry:
                    grocery[i] += 1

    grocery_rows = [[ing, cnt] for ing, cnt in sorted(grocery.items())]
    overview = ["MEAL PREP PLANNER",
                f"diet: {diet} | pantry items on hand: {len(pantry)}",
                f"plan: {days} days x {meals_pd} meals = {len(plan_rows)} meals",
                f"est. weekly food cost: {_money(total_cost)}",
                f"grocery list: {len(grocery_rows)} items to buy",
                "",
                "cook once, eat twice — batch the grains and proteins."]

    files = {
        "meal_plan.csv": _csv(["day", "meal", "recipe", "pantry_overlap"], plan_rows),
        "grocery_list.csv": _csv(["ingredient", "meals_needing"], grocery_rows),
        "meal_overview.txt": "\n".join(overview) + "\n",
    }
    return _emit(ctx, gid, files, 4.0,
                 f"Meal plan: {len(plan_rows)} meals, {len(grocery_rows)} groceries, "
                 f"est {_money(total_cost)}; " + ("sample pantry" if fixture else "user pantry"))


# ---------------------------------------------------------------------------
# 67. invoice-aging-tracker — AR aging buckets + follow-up list
# ---------------------------------------------------------------------------

_INVOICE_SAMPLE = [
    {"id": "INV-101", "client": "Acme Co", "issued": "2026-07-01", "due": "2026-07-31",
     "amount": 1200.00, "paid": 1200.00},
    {"id": "INV-102", "client": "Acme Co", "issued": "2026-08-05", "due": "2026-09-04",
     "amount": 800.00, "paid": 0.00},
    {"id": "INV-103", "client": "Beta LLC", "issued": "2026-06-10", "due": "2026-07-10",
     "amount": 450.00, "paid": 0.00},
    {"id": "INV-104", "client": "Gamma Inc", "issued": "2026-05-01", "due": "2026-05-31",
     "amount": 2300.00, "paid": 0.00},
    {"id": "INV-105", "client": "Beta LLC", "issued": "2026-08-20", "due": "2026-09-19",
     "amount": 620.00, "paid": 0.00},
    {"id": "INV-106", "client": "Delta Co", "issued": "2026-09-01", "due": "2026-10-01",
     "amount": 310.00, "paid": 0.00},
    {"id": "INV-107", "client": "Gamma Inc", "issued": "2026-08-15", "due": "2026-09-14",
     "amount": 975.00, "paid": 400.00},
]
_AGING_ACTIONS = [
    (91, "90+", "escalate: collections call this week"),
    (61, "61-90", "phone call — firm but friendly"),
    (31, "31-60", "firm reminder email with the invoice attached"),
    (1, "1-30", "polite reminder email"),
]


def _run_invoice_aging(ctx):
    gid = "invoice-aging-tracker"
    params = ctx.get("params") or {}
    invoices = params.get("invoices") or _INVOICE_SAMPLE
    as_of = _anchor(params, "as_of")
    fixture = "invoices" not in params

    open_inv = []
    for inv in invoices:
        bal = round(float(inv["amount"]) - float(inv.get("paid", 0) or 0), 2)
        if bal <= 0:
            continue
        due = datetime.strptime(str(inv["due"]), "%Y-%m-%d").date()
        overdue = (as_of - due).days
        bucket, action = "current", "on track — no action"
        for thresh, bname, act in _AGING_ACTIONS:
            if overdue >= thresh:
                bucket, action = bname, act
                break
        open_inv.append((inv["id"], inv["client"], str(inv["issued"]), str(inv["due"]),
                         bal, overdue, bucket, action))

    open_inv.sort(key=lambda r: -r[5])  # oldest first
    aging_rows = [[i, c, iss, due, f"{b:.2f}", od, bk, ac]
                  for i, c, iss, due, b, od, bk, ac in open_inv]
    buckets = Counter(r[6] for r in aging_rows)
    clients = defaultdict(float)
    for r in aging_rows:
        clients[r[1]] += float(r[4])
    ar_total = round(sum(float(r[4]) for r in aging_rows), 2)

    fu = ["INVOICE AGING + FOLLOW-UPS", f"as of: {as_of}", ""]
    fu.append(f"open invoices: {len(aging_rows)} | AR outstanding: {_money(ar_total)}")
    fu.append("by bucket:")
    for b in ["current", "1-30", "31-60", "61-90", "90+"]:
        n = buckets.get(b, 0)
        tot = round(sum(float(r[4]) for r in aging_rows if r[6] == b), 2)
        fu.append(f"  {b}: {n} invoices, {_money(tot)}")
    fu.append("per client:")
    for c in sorted(clients):
        fu.append(f"  {c}: {_money(clients[c])}")
    fu.append("follow-up list (oldest first):")
    for i, c, _, due, b, od, bk, ac in open_inv:
        fu.append(f"  {i} {c} — {_money(b)}, {od}d overdue [{bk}]: {ac}")

    files = {
        "aging.csv": _csv(["invoice_id", "client", "issued", "due", "balance",
                            "days_overdue", "bucket", "suggested_action"], aging_rows),
        "followups.txt": "\n".join(fu) + "\n",
    }
    return _emit(ctx, gid, files, 5.0,
                 f"AR aging: {len(aging_rows)} open, {_money(ar_total)} outstanding; "
                 + ("sample fixture" if fixture else "user invoice CSV"))


# ---------------------------------------------------------------------------
# 68. content-calendar-forge — 30-day content calendar from themes
# ---------------------------------------------------------------------------

_CONTENT_THEMES_SAMPLE = ["levi build log", "budget tips", "indie hacking notes"]
_CONTENT_CHANNELS_SAMPLE = ["blog", "newsletter", "social"]
_CONTENT_FORMATS = ["how-to guide", "personal story", "listicle", "opinion take",
                    "roundup", "tutorial", "behind-the-scenes", "myth-buster"]


def _run_content_calendar(ctx):
    gid = "content-calendar-forge"
    params = ctx.get("params") or {}
    themes = [str(t) for t in (params.get("themes") or _CONTENT_THEMES_SAMPLE)]
    channels = [str(c) for c in (params.get("channels") or _CONTENT_CHANNELS_SAMPLE)]
    days = max(7, min(90, int(params.get("days", 30))))
    start = _anchor(params, "start")
    fixture = "themes" not in params and "channels" not in params

    cal_rows, notes = [], []
    notes.append("CONTENT CALENDAR FORGE")
    notes.append(f"{days} days from {start} | themes: {', '.join(themes)}")
    notes.append(f"channels: {', '.join(channels)}")
    notes.append("rotation: round-robin themes x channels x formats (deterministic)")
    notes.append("")
    for i in range(days):
        d = start + timedelta(days=i)
        theme = themes[i % len(themes)]
        channel = channels[(i // len(themes)) % len(channels)]
        fmt = _CONTENT_FORMATS[i % len(_CONTENT_FORMATS)]
        title = f"{fmt.title()} #{i + 1}: {theme}"
        cal_rows.append([d.isoformat(), channel, theme, fmt, title, "planned"])
    ch_count = Counter(r[1] for r in cal_rows)
    th_count = Counter(r[2] for r in cal_rows)
    notes.append("per channel: " + ", ".join(f"{c} x{n}" for c, n in sorted(ch_count.items())))
    notes.append("per theme: " + ", ".join(f"{t} x{n}" for t, n in sorted(th_count.items())))

    files = {
        "content_calendar.csv": _csv(["date", "channel", "theme", "format",
                                       "working_title", "status"], cal_rows),
        "calendar_notes.txt": "\n".join(notes) + "\n",
    }
    return _emit(ctx, gid, files, 3.0,
                 f"Content calendar: {days} days, {len(themes)} themes, "
                 f"{len(channels)} channels; " + ("sample themes" if fixture else "user themes"))


# ---------------------------------------------------------------------------
# 69. kpi-dashboard-text — text-mode KPI dashboard (trends, deltas)
# ---------------------------------------------------------------------------

def _kpi_series(base, slope, wiggle, n=14):
    return [round(base + i * slope + ((i * 7) % wiggle) - wiggle / 2, 2) for i in range(n)]


def _spark(values):
    bars = "▁▂▃▄▅▆▇█"
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    return "".join(bars[min(7, int((v - lo) / span * 7))] for v in values)


def _run_kpi_dashboard(ctx):
    gid = "kpi-dashboard-text"
    params = ctx.get("params") or {}
    metrics = params.get("metrics")
    if not metrics:
        metrics = {
            "site_visits": _kpi_series(820, 12, 40),
            "revenue_usd": _kpi_series(145, 3.5, 22),
            "email_subs": _kpi_series(310, 6, 18),
        }
        fixture = True
    else:
        fixture = False

    dash = ["KPI DASHBOARD (text mode)", ""]
    metric_rows = []
    for name, series in metrics.items():
        vals = [float(v) for v in series]
        latest = vals[-1]
        ref7 = vals[-8] if len(vals) >= 8 else vals[0]
        ref0 = vals[0]
        d7 = round(latest - ref7, 2)
        p7 = round(100.0 * d7 / ref7, 1) if ref7 else 0.0
        d0 = round(latest - ref0, 2)
        p0 = round(100.0 * d0 / ref0, 1) if ref0 else 0.0
        verdict = "up" if p7 > 5 else ("down" if p7 < -5 else "flat")
        arrow = {"up": "^", "down": "v", "flat": "-"}[verdict]
        avg = round(statistics.mean(vals), 2)
        dash.append(f"[{name}] {arrow} {verdict.upper()}")
        dash.append(f"  latest: {latest} | 7d: {d7:+} ({p7:+.1f}%) | "
                    f"span: {d0:+} ({p0:+.1f}%)")
        dash.append(f"  min {min(vals)} / max {max(vals)} / avg {avg}")
        dash.append(f"  trend: {_spark(vals)}")
        dash.append("")
        metric_rows.append([name, latest, d7, p7, d0, p0, verdict])

    files = {
        "kpi_dashboard.txt": "\n".join(dash).rstrip() + "\n",
        "kpi_metrics.csv": _csv(["metric", "latest", "delta_7d", "pct_7d",
                                  "delta_span", "pct_span", "trend"], metric_rows),
    }
    return _emit(ctx, gid, files, 4.0,
                 f"KPI dashboard: {len(metrics)} metrics; "
                 + ("sample series" if fixture else "user metric CSVs"))


# ---------------------------------------------------------------------------
# 70. survey-tally-engine — tally survey responses into a results report
# ---------------------------------------------------------------------------

_SURVEY_SAMPLE_Q = "What is your biggest money leak?"
_SURVEY_SAMPLE_R = ["eating out", "eating out", "subscriptions", "eating out",
                    "impulse shopping", "subscriptions", "eating out", "coffee runs",
                    "subscriptions", "impulse shopping", "eating out", "late fees",
                    "subscriptions", "eating out"]


def _run_survey_tally(ctx):
    gid = "survey-tally-engine"
    params = ctx.get("params") or {}
    question = str(params.get("question") or _SURVEY_SAMPLE_Q)
    responses = [str(r) for r in (params.get("responses") or _SURVEY_SAMPLE_R)]
    fixture = "responses" not in params

    report = ["SURVEY TALLY", f"question: {question}", f"responses: {len(responses)}", ""]
    numeric = True
    nums = []
    for r in responses:
        try:
            nums.append(float(r.strip()))
        except ValueError:
            numeric = False
            break

    if numeric and nums:
        mean = round(statistics.mean(nums), 2)
        med = round(statistics.median(nums), 2)
        report.append("scale question detected — numeric summary:")
        report.append(f"  mean {mean} | median {med} | min {min(nums)} | max {max(nums)}")
        buckets = Counter(round(v) for v in nums)
        rows = [[str(k), c, round(100.0 * c / len(nums), 1)]
                for k, c in sorted(buckets.items(), key=lambda kv: (-kv[1], kv[0]))]
    else:
        tally = Counter(r.strip() for r in responses if r.strip())
        rows = [[ans, c, round(100.0 * c / len(responses), 1)]
                for ans, c in sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))]
        report.append("answer tallies (most common first):")
        for ans, c, pct in rows:
            report.append(f"  {ans}: {c} ({pct}%)")
        if rows:
            top_ans, top_c, top_pct = rows[0]
            if top_pct >= 50:
                verdict = f"clear consensus: '{top_ans}' holds {top_pct}%"
            elif top_pct >= 30:
                verdict = f"leading answer: '{top_ans}' at {top_pct}%"
            else:
                verdict = "no consensus — the field is split"
            report.append(verdict)
            report.append(f"distinct answers: {len(rows)}")

    files = {
        "survey_results.csv": _csv(["answer", "count", "pct"], rows),
        "survey_report.txt": "\n".join(report) + "\n",
    }
    return _emit(ctx, gid, files, 2.0,
                 f"Survey tally: {len(responses)} responses, {len(rows)} distinct; "
                 + ("sample fixture" if fixture else "user responses"))


# ---------------------------------------------------------------------------
# 71. inventory-ledger-kit — small-business inventory tracker
# ---------------------------------------------------------------------------

_INVENTORY_SAMPLE = [
    {"sku": "SKU-001", "name": "candles (soy 8oz)", "on_hand": 42, "reorder_point": 20,
     "unit_cost": 3.10, "supplier": "WaxWorks"},
    {"sku": "SKU-002", "name": "wax melts 6pk", "on_hand": 15, "reorder_point": 25,
     "unit_cost": 1.85, "supplier": "WaxWorks"},
    {"sku": "SKU-003", "name": "reed diffusers", "on_hand": 0, "reorder_point": 12,
     "unit_cost": 4.40, "supplier": "ScentCo"},
    {"sku": "SKU-004", "name": "gift boxes", "on_hand": 60, "reorder_point": 30,
     "unit_cost": 0.95, "supplier": "PackRight"},
    {"sku": "SKU-005", "name": "labels (roll)", "on_hand": 8, "reorder_point": 10,
     "unit_cost": 6.20, "supplier": "PackRight"},
    {"sku": "SKU-006", "name": "room spray", "on_hand": 25, "reorder_point": 15,
     "unit_cost": 2.75, "supplier": "ScentCo"},
]


def _run_inventory_ledger(ctx):
    gid = "inventory-ledger-kit"
    params = ctx.get("params") or {}
    items = params.get("items") or _INVENTORY_SAMPLE
    fixture = "items" not in params

    inv_rows, reorder = [], []
    total_value = 0.0
    for it in items:
        sku, name = it["sku"], it["name"]
        on_hand = int(it["on_hand"])
        rp = int(it["reorder_point"])
        cost = float(it["unit_cost"])
        value = round(on_hand * cost, 2)
        total_value += value
        status = "out" if on_hand == 0 else ("low" if on_hand <= rp else "ok")
        order_qty = max(0, rp * 2 - on_hand) if status != "ok" else 0
        inv_rows.append([sku, name, on_hand, rp, status, f"{cost:.2f}",
                         f"{value:.2f}", order_qty, it.get("supplier", "")])
        if order_qty:
            reorder.append((sku, name, order_qty, round(order_qty * cost, 2),
                            it.get("supplier", "")))

    total_value = round(total_value, 2)
    reorder_cost = round(sum(r[3] for r in reorder), 2)
    rl = ["INVENTORY LEDGER — REORDER LIST", ""]
    rl.append(f"SKUs tracked: {len(items)} | inventory value: {_money(total_value)}")
    rl.append(f"items to reorder: {len(reorder)} | est. reorder cost: {_money(reorder_cost)}")
    rl.append("")
    for sku, name, qty, line_cost, sup in sorted(reorder, key=lambda r: -r[3]):
        rl.append(f"  {sku} {name}: order {qty} from {sup} — {_money(line_cost)}")
    if not reorder:
        rl.append("nothing to reorder — stock is healthy")

    files = {
        "inventory.csv": _csv(["sku", "name", "on_hand", "reorder_point", "status",
                                "unit_cost", "stock_value", "suggested_order_qty",
                                "supplier"], inv_rows),
        "reorder_list.txt": "\n".join(rl) + "\n",
    }
    return _emit(ctx, gid, files, 5.0,
                 f"Inventory: {len(items)} SKUs, value {_money(total_value)}, "
                 f"{len(reorder)} to reorder; " + ("sample fixture" if fixture else "user items"))


# ---------------------------------------------------------------------------
# 72. subscription-auditor — finds forgotten subscriptions in a statement
# ---------------------------------------------------------------------------

_STATEMENT_SAMPLE = [
    ("2026-07-02", "STREAMFLIX", 15.99), ("2026-08-02", "STREAMFLIX", 15.99),
    ("2026-09-02", "STREAMFLIX", 15.99),
    ("2026-07-05", "CLOUDBOX PRO", 9.99), ("2026-08-05", "CLOUDBOX PRO", 9.99),
    ("2026-09-05", "CLOUDBOX PRO", 9.99),
    ("2026-07-12", "CITY GYM", 35.00), ("2026-08-12", "CITY GYM", 35.00),
    ("2026-07-15", "MUSIC+", 10.99), ("2026-08-15", "MUSIC+", 10.99),
    ("2026-09-15", "MUSIC+", 10.99),
    ("2025-09-20", "DOMAINREG", 18.00), ("2026-09-20", "DOMAINREG", 18.00),
    ("2026-07-08", "GROCERY MART", 86.42), ("2026-08-21", "GROCERY MART", 112.10),
    ("2026-09-11", "GROCERY MART", 94.77), ("2026-07-19", "GAS N GO", 42.00),
    ("2026-08-28", "GAS N GO", 38.50), ("2026-09-03", "COFFEE KIOSK", 5.75),
    ("2026-09-14", "COFFEE KIOSK", 6.25), ("2026-09-16", "BOOKSTORE", 24.99),
]


def _norm_desc(desc: str) -> str:
    s = re.sub(r"[^a-z ]", " ", desc.lower())
    return re.sub(r"\s+", " ", s).strip()


def _run_subscription_auditor(ctx):
    gid = "subscription-auditor"
    params = ctx.get("params") or {}
    rows = params.get("statement") or [
        {"date": d, "description": desc, "amount": amt}
        for d, desc, amt in _STATEMENT_SAMPLE
    ]
    fixture = "statement" not in params

    groups = defaultdict(list)
    for r in rows:
        groups[(_norm_desc(str(r["description"])), round(float(r["amount"]), 2))].append(
            datetime.strptime(str(r["date"]), "%Y-%m-%d").date())

    subs, one_off_total = [], 0.0
    for (name, amt), dates in groups.items():
        dates.sort()
        if len(dates) >= 2 and (dates[-1] - dates[0]).days >= 20:
            gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
            med = statistics.median(gaps)
            if 25 <= med <= 35:
                cadence, annual = "monthly", round(amt * 12, 2)
            elif 350 <= med <= 380:
                cadence, annual = "yearly", round(amt, 2)
            else:
                cadence = "irregular"
                span = max(1, (dates[-1] - dates[0]).days)
                annual = round(amt * len(dates) * 365.0 / span, 2)
            subs.append([name, f"{amt:.2f}", cadence, len(dates),
                         dates[0].isoformat(), dates[-1].isoformat(), f"{annual:.2f}"])
        else:
            one_off_total += amt * len(dates)

    subs.sort(key=lambda s: -float(s[6]))
    monthly_burn = 0.0
    for s in subs:
        amt, cadence = float(s[1]), s[2]
        monthly_burn += amt if cadence == "monthly" else amt / 12 if cadence == "yearly" \
            else float(s[6]) / 12
    monthly_burn = round(monthly_burn, 2)
    yearly = round(monthly_burn * 12, 2)

    rep = ["SUBSCRIPTION AUDIT", f"statement rows scanned: {len(rows)}", ""]
    rep.append(f"recurring charges found: {len(subs)}")
    rep.append(f"estimated monthly burn: {_money(monthly_burn)}")
    rep.append(f"projected yearly cost: {_money(yearly)}")
    rep.append(f"one-off spending in window: {_money(round(one_off_total, 2))}")
    rep.append("subscriptions (costliest first):")
    for name, amt, cadence, n, first, last, annual in subs:
        rep.append(f"  {name}: {_money(float(amt))}/{cadence}, {n}x "
                   f"({first}..{last}) — {_money(float(annual))}/yr")
    if subs:
        rep.append(f"top leak: {subs[0][0]} at {_money(float(subs[0][6]))}/yr — "
                   "cancel or downgrade if unused")

    files = {
        "subscriptions.csv": _csv(["name", "amount", "cadence", "occurrences",
                                    "first_seen", "last_seen", "annual_cost"], subs),
        "audit_report.txt": "\n".join(rep) + "\n",
    }
    return _emit(ctx, gid, files, 3.0,
                 f"Subscription audit: {len(subs)} recurring, {_money(monthly_burn)}/mo burn; "
                 + ("sample fixture" if fixture else "user statement"))


# ---------------------------------------------------------------------------
# Batch registration — slots 61-72
# ---------------------------------------------------------------------------

_BATCH_D = [
    ("habit-tracker-kit", "Habit Tracker Kit",
     "Habit-tracking CSV + streak summary (current/longest streaks, pace vs target) "
     "from a habit list or the bundled sample.",
     _run_habit_tracker, 61, 3.0),
    ("budget-ledger-builder", "Budget Ledger Builder",
     "Zero-based budget ledger: every dollar assigned to income, expenses, or "
     "savings, with a pass/fail balance check.",
     _run_budget_ledger, 62, 2.0),
    ("price-watchlist", "Price Watchlist",
     "Manual-entry price tracker (no scraping): per-item trends, lows/highs, "
     "and drop/target alerts from your own price entries.",
     _run_price_watchlist, 63, 3.0),
    ("reading-log-atlas", "Reading Log Atlas",
     "Reading log CSV + stats: pace (pages/day), genre breakdown, average "
     "rating, currently-reading shelf.",
     _run_reading_log, 64, 2.0),
    ("workout-planner-pack", "Workout Planner Pack",
     "Workout plans from goal/equipment/days-per-week: session rotation, "
     "sets x reps, and weekly progression notes.",
     _run_workout_planner, 65, 4.0),
    ("meal-prep-planner", "Meal Prep Planner",
     "Weekly meal plan + grocery list from pantry inputs: recipes ranked by "
     "pantry overlap, diet filters, cost estimate.",
     _run_meal_prep, 66, 4.0),
    ("invoice-aging-tracker", "Invoice Aging Tracker",
     "AR aging buckets (current/1-30/31-60/61-90/90+) with a prioritized "
     "follow-up list and per-client rollups from an invoice CSV.",
     _run_invoice_aging, 67, 5.0),
    ("content-calendar-forge", "Content Calendar Forge",
     "30-day content calendar from theme inputs: round-robin themes x "
     "channels x formats with working titles.",
     _run_content_calendar, 68, 3.0),
    ("kpi-dashboard-text", "KPI Dashboard (Text)",
     "Text-mode KPI dashboard: latest values, 7-day/span deltas, min/max/avg, "
     "trend verdicts, and ASCII sparklines from metric series.",
     _run_kpi_dashboard, 69, 4.0),
    ("survey-tally-engine", "Survey Tally Engine",
     "Tallies survey responses into a results report: ranked frequencies, "
     "consensus verdict, numeric stats for scale questions.",
     _run_survey_tally, 70, 2.0),
    ("inventory-ledger-kit", "Inventory Ledger Kit",
     "Small-business inventory tracker: stock status, reorder points, "
     "suggested order quantities, and inventory valuation.",
     _run_inventory_ledger, 71, 5.0),
    ("subscription-auditor", "Subscription Auditor",
     "Finds forgotten subscriptions in a manually-imported statement CSV: "
     "recurring-charge detection, cadence, monthly burn, yearly projection.",
     _run_subscription_auditor, 72, 3.0),
]


def register_batch_d() -> List[str]:
    """Register all 12 batch-D generators (idempotent within one process)."""
    from levi.income.engine import REGISTRY
    ids = []
    for gid, name, desc, run, slot, price in _BATCH_D:
        if gid in REGISTRY._ids:
            ids.append(gid)
            continue
        register(
            Generator(id=gid, name=name, kind="data-product",
                      description=desc, run=run,
                      version="1.0.0", entry_price_usd=price),
            slot=slot,
        )
        ids.append(gid)
    return ids


register_batch_d()
