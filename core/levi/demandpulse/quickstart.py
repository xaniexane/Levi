"""Zero-config quickstart — Google Alerts' simplicity, our way.

One call: keyword set in, watch alerts installed, digest path out.
No account, no dashboard onboarding, no funnel. Everything lands in the
product's own home (``~/.levi/demandpulse/`` by default, overridable with
the DEMANDPULSE_HOME env var for tests and bundles).

What quickstart does (all offline, all reversible):
  1. creates the product home layout (alert store, outbox, filters)
  2. writes filters.json — the auditable include/exclude keyword sets
     (Mention-grade precision, readable back, no query language)
  3. installs the engine's 10 workflow alerts into an ISOLATED alert store
     (idempotent — reinstalling never duplicates)
  4. creates one watch alert bound to the keyword set
  5. returns a receipt: every step, timing, paths, and the price line

It never touches the network and never touches the user's real
``levi demand`` alert store — the product's store is its own file.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from levi.demand.alerts import AlertEngine
from levi.demand.workflows import install_workflows

ENV_HOME = "DEMANDPULSE_HOME"
DEFAULT_DIRNAME = ("demandpulse",)

FILTERS_FILENAME = "filters.json"
ALERTS_FILENAME = "alerts.json"
OUTBOX_DIRNAME = "outbox"


def product_home(home: Optional[Path] = None) -> Path:
    """The product's data home. ``home`` wins, then DEMANDPULSE_HOME, then
    ~/.levi/demandpulse/."""
    if home is not None:
        return Path(home)
    env = os.environ.get(ENV_HOME)
    if env:
        return Path(env)
    return Path.home() / ".levi" / "demandpulse"


def filters_path(home: Optional[Path] = None) -> Path:
    return product_home(home) / FILTERS_FILENAME


def alerts_path(home: Optional[Path] = None) -> Path:
    return product_home(home) / ALERTS_FILENAME


def outbox_dir(home: Optional[Path] = None) -> Path:
    return product_home(home) / OUTBOX_DIRNAME


def write_filters(
    keywords: Sequence[str],
    exclude: Sequence[str] = (),
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Write the auditable keyword filter set. Sorted + deduped so the file
    is diffable; the alert definition logs the same sets."""
    include = sorted({k.strip().lower() for k in keywords if k and k.strip()})
    if not include:
        raise ValueError("quickstart needs at least one keyword")
    excluded = sorted({e.strip().lower() for e in exclude if e and e.strip()})
    record = {
        "include": include,
        "exclude": excluded,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "note": "auditable filter set — precision without a query language",
    }
    path = filters_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(record, indent=2), encoding="utf-8")
    tmp.replace(path)
    return record


def _keyword_watch_name(include: Sequence[str]) -> str:
    shown = ", ".join(include[:3])
    suffix = f" +{len(include) - 3} more" if len(include) > 3 else ""
    return f"Quickstart watch: {shown}{suffix}"


def quickstart(
    keywords: Sequence[str],
    exclude: Sequence[str] = (),
    home: Optional[Path] = None,
    install_engine_workflows: bool = True,
) -> Dict[str, Any]:
    """Run the zero-config quickstart. Returns a receipt dict."""
    from levi.demandpulse.product import (
        PRICE_CURRENCY,
        PRICE_MONTHLY,
        PRODUCT_NAME,
        PRODUCT_VERSION,
    )

    started = time.monotonic()
    steps: List[Dict[str, Any]] = []
    home_path = product_home(home)

    def step(name: str, detail: str) -> None:
        steps.append({"name": name, "detail": detail})

    # 1. layout
    outbox_dir(home_path).mkdir(parents=True, exist_ok=True)
    step("layout", f"product home ready at {home_path}")

    # 2. filters
    filters = write_filters(keywords, exclude, home_path)
    step(
        "filters",
        f"include={filters['include']} exclude={filters['exclude']} "
        f"-> {filters_path(home_path).name}",
    )

    # 3. workflow alerts into the isolated store
    engine = AlertEngine(path=alerts_path(home_path))
    installed: List[str] = []
    if install_engine_workflows:
        created = install_workflows(engine)
        installed = [a.name for a in created]
        step(
            "workflows",
            f"{len(engine.alerts)} alerts in store ({len(installed)} newly installed)",
        )
    else:
        step("workflows", "skipped by caller")

    # 4. keyword watch alert bound to the filter set
    watch_name = _keyword_watch_name(filters["include"])
    existing = [a for a in engine.alerts if a.name == watch_name]
    if existing:
        watch = existing[0]
        step("watch", f"already installed: {watch_name}")
    else:
        watch = engine.create(
            "watch",
            watch_name,
            recurrence="daily",
            time="07:00",
            segment=",".join(filters["include"]),
            message=f"include={filters['include']} exclude={filters['exclude']}",
            channels=("console", "file"),
        )
        step("watch", f"installed: {watch_name} (id {watch.id})")

    finished = time.monotonic()
    return {
        "product": PRODUCT_NAME,
        "version": PRODUCT_VERSION,
        "home": str(home_path),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": round(finished - started, 3),
        "steps": steps,
        "filters": filters,
        "alerts_in_store": len(engine.alerts),
        "newly_installed_workflows": installed,
        "watch_alert": watch_name,
        "price": (
            f"${PRICE_MONTHLY:.0f}/month ({PRICE_CURRENCY}) — "
            "not charged in this build (payments owner-gated)"
        ),
    }


def status(home: Optional[Path] = None) -> Dict[str, Any]:
    """Smoke-check the product home: layout, filters, alert store."""
    from levi.demandpulse.product import PRODUCT_NAME, PRODUCT_VERSION

    home_path = product_home(home)
    report: Dict[str, Any] = {
        "product": PRODUCT_NAME,
        "version": PRODUCT_VERSION,
        "home": str(home_path),
        "home_exists": home_path.exists(),
        "filters_present": filters_path(home_path).exists(),
        "outbox_present": outbox_dir(home_path).exists(),
        "alert_count": 0,
        "ok": False,
    }
    if alerts_path(home_path).exists():
        try:
            engine = AlertEngine(path=alerts_path(home_path))
            report["alert_count"] = len(engine.alerts)
        except Exception:
            report["alert_count"] = -1
    report["ok"] = bool(
        report["home_exists"]
        and report["filters_present"]
        and report["alert_count"] >= 0
    )
    return report
