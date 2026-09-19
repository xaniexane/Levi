"""Act two-and-a-half — business analytics for the rescue rail.

The audit finds problems; analytics measures the business. Every metric
is computed from the walked site's own served content — structure,
content completeness, conversion-path clarity, contact friction, and
weight-based performance proxies. The laws are binding:

1. Consent-first: measuring requires the owner's accepted invitation.
   Analytics is OF the business's own site, never ABOUT other people.
2. No third-party anything: no trackers, no beacons, no external
   services, no surveillance. The walk is the whole world.
3. Evidence-only, like the audit: a metric is a deterministic function
   of the walk. Same walk → same numbers, always.
4. Honest numbers: the reveal shows what moved AND what didn't. A
   metric that didn't budge ships with delta 0 and ``target_met``
   false, never smoothed away.

Pipeline fit: audit gains the baseline (``AuditReport.baseline``),
the plan gains numeric targets per item (``RescueItem.target``), and
the reveal gains the verified before/after metric deltas.
"""

from __future__ import annotations

import json
import re
import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import ensure_home, rescue_home
from . import ledger as stone
from .audit import _CONTACT_RE
from .intake import require_consent, validate_costs


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# -- the cost pillar ----------------------------------------------------------
# Cost-cutting is a first-class remodel pillar: the remodel doesn't just
# fix and beautify, it makes the business cheaper to run. Money is
# tracked baseline → target → verified savings, with the same
# evidence-only honesty: every figure is the owner's stated spend,
# labeled "owner-stated". Nothing is invented, nothing is estimated
# silently — a stated figure the owner hasn't confirmed stays labeled
# as the owner's statement, never as a measurement.

#: LEVI-native equivalents the cost pillar may honestly propose.
#: (name fragments, module, what it is). A proposal is only made when
#: the module actually imports — a missing module is never promised.
LEVI_EQUIVALENTS = (
    (
        (
            "zapier",
            "n8n",
            "make.com",
            "integromat",
            "workflow automation",
            "power automate",
        ),
        "levi.automation.flows",
        "workflow engine — node-graph automation on the existing rail",
    ),
    (
        ("airtable", "cloud database", "database hosting", "firebase"),
        "levi.forge.datastore",
        "embedded document store — stdlib sqlite3, receipted writes",
    ),
    (
        ("password manager", "secrets manager", "vault subscription"),
        "levi.cybrus.seal",
        "sealed envelopes — keeper-held keys, tamper-evident",
    ),
    (
        ("support chatbot", "chat widget", "intercom", "chatbot saas"),
        "levi.offline.chain",
        "local-first answer chain — no per-seat SaaS meter running",
    ),
)

COST_ACTIONS = (
    "keep",
    "review",
    "replace",
    "consolidate",
    "drop",
    "rehost",
    "static-first-rebuild",
    "de-containerize",
    "schedule-dont-idle",
    "downsize-the-iron",
    "de-manage-the-database",
)


#: Hosting combo classes from the recovered "Hybrid Cost-Cutting Combos"
#: research (old-school techniques + modern software, ~$0/mo framing).
#: (action, combo label, name fragments, the play.)
#: Each is a DRAFT: the rationale names the combo and the old/new mix,
#: the target stays the owner's stated amount — the owner sets the cut.
#: The report's dollar figures are web-index estimates, not live-verified,
#: so combos carry NO savings numbers, only the direction and the fit-check.
#: A combo fires only on hosting lines, and only after the LEVI_EQUIVALENTS
#: honest-import check (a verifiable in-repo equivalent stays "replace").
HOSTING_COMBOS = (
    (
        "static-first-rebuild",
        "static-first rebuild",
        (
            "vercel",
            "netlify",
            "amplify",
            "cloudflare pages",
            "squarespace",
            "wix",
            "wordpress",
            "site builder",
            "jamstack",
        ),
        "static generator + rsync/rclone + Caddy TLS onto owned/free-tier "
        "hardware — kills the platform subscription and the bandwidth-overage "
        "tail-risk (old: 1990s dumb file-copy deploy; new: Hugo/Eleventy/Astro "
        "+ Caddy)",
    ),
    (
        "de-containerize",
        "de-containerize",
        ("docker", "kubernetes", "k8s", "container", "ecs", "gke", "aks"),
        "single-binary + systemd instead of Docker/K8s — deletes the daemon "
        "and registry bills so everything fits a smaller, cheaper box "
        "(old: CGI discipline, idle costs nothing; new: static binaries, "
        "systemd)",
    ),
    (
        "schedule-dont-idle",
        "schedule, don't idle",
        (
            "always-on",
            "always on",
            "worker",
            "cron job",
            "batch",
            "scheduled",
            "ec2",
            "droplet",
        ),
        "cron/scale-to-zero for intermittent workloads — pay minutes of run "
        "time, not 24/7 idle (old: batch-window thinking; new: schedulers "
        "and scale-to-zero)",
    ),
    (
        "downsize-the-iron",
        "downsize the iron",
        (
            "bare metal",
            "dedicated server",
            "colocation",
            " colo ",
            "tower",
            "rack server",
            "rack-mount",
        ),
        "low-power or repurposed host instead of the power-hungry box — "
        "N100/Pi-class or an old laptop doing the job (old: hardware "
        "frugality; new: low-power parts)",
    ),
    (
        "de-manage-the-database",
        "de-manage the database",
        (
            "rds",
            "aurora",
            "planetscale",
            "neon",
            "supabase",
            "cockroach",
            "managed postgres",
            "managed mysql",
            "managed database",
        ),
        "SQLite + Litestream instead of the managed meter — the database is "
        "a file again, replication ~$1/mo object storage (old: 2000s "
        "embedded ethos; new: modern replication ecosystem). Fires only "
        "when no LEVI-native equivalent claimed it first",
    ),
)


def _hosting_combo_for(name: str) -> Optional[tuple]:
    """Match a hosting line item to one hybrid combo, or None."""
    low = name.lower()
    for action, label, fragments, play in HOSTING_COMBOS:
        if any(frag in low for frag in fragments):
            return action, label, play
    return None


def _module_available(module: str) -> bool:
    try:
        __import__(module)
        return True
    except Exception:
        return False


def cost_baseline(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Total the owner's stated monthly operating spend. Pure math, no
    invention: the input items are already validated + labeled by
    ``intake.validate_costs``."""
    items = list(items or [])
    by_category: Dict[str, float] = {}
    for item in items:
        cat = item.get("category", "other")
        by_category[cat] = round(
            by_category.get(cat, 0.0) + float(item.get("amount_usd_monthly", 0)), 2
        )
    total = round(sum(by_category.values()), 2)
    return {
        "items": items,
        "item_count": len(items),
        "by_category": by_category,
        "total_monthly_usd": total,
        "provenance": "owner-stated",
    }


def _norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _levi_equivalent_for(name: str) -> Optional[Dict[str, str]]:
    low = name.lower()
    for fragments, module, what in LEVI_EQUIVALENTS:
        if any(frag in low for frag in fragments) and _module_available(module):
            return {"module": module, "what": what}
    return None


def propose_cost_targets(
    items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Draft cost-cutting targets from the owner's stated spend.

    Every proposal is a DRAFT the owner approves with the plan — the
    module proposes, the owner disposes. Actions:

    - replace: a LEVI-native equivalent exists in-repo (verified
      importable) — target $0, cancel the subscription after fit check.
    - consolidate: duplicate line items for the same thing — one bill.
    - rehost: HOSTING lines with no combo fit get their rates attacked too
      (the keeper's word: even hosting cost rates). Draft plays the owner
      picks from: right-size the plan, shop cheaper providers, consolidate
      multiple hosting bills to one host, static/local-first LEVI-native
      build where it fits. The target stays the stated amount — the OWNER
      sets the cut on plan approval; the rail never invents a hosting rate.
    - static-first-rebuild / de-containerize / schedule-dont-idle /
      downsize-the-iron / de-manage-the-database: hosting combos from the
      recovered Hybrid Cost-Cutting Combos research (old-school technique
      + modern software). Drafts, owner-approved; rationale names the combo
      and the old/new mix; target stays owner-stated; NO savings numbers
      are claimed (the report's figures are web-index estimates, not
      live-verified). de-manage-the-database fires only where the
      LEVI_EQUIVALENTS honest-import check found nothing (that stays
      "replace" — a verifiable in-repo module outranks the pattern).
    - review: large SaaS/fees lines worth consolidating or renegotiating.
    - drop: $0 lines stay, nothing to cut.
    - keep: everything else — no honest cut proposed.
    """
    items = list(items or [])
    hosting_bills = sum(
        1
        for item in items
        if str(item.get("category", "")).lower() == "hosting"
        and float(item.get("amount_usd_monthly", 0) or 0) > 0
    )
    seen: Dict[str, Dict[str, Any]] = {}
    targets: List[Dict[str, Any]] = []
    for n, item in enumerate(items, 1):
        name = item["name"]
        amount = float(item["amount_usd_monthly"])
        category = item["category"]
        key = _norm_name(name)
        entry: Dict[str, Any] = {
            "id": "cost-%02d" % n,
            "item": name,
            "category": category,
            "current_usd": round(amount, 2),
            "action": "keep",
            "target_usd": round(amount, 2),
            "rationale": "no honest cut proposed — spend stands as stated",
            "provenance": "owner-stated",
            "levi_equivalent": "",
            "combo": "",
            "status": "proposed",
        }
        if amount == 0:
            entry["action"] = "drop"
            entry["rationale"] = "zero spend recorded — nothing to cut"
        elif key in seen:
            first = seen[key]
            entry["action"] = "consolidate"
            entry["target_usd"] = 0.0
            entry["rationale"] = (
                "duplicate of %r — consolidate to one bill" % first["item"]
            )
        else:
            equiv = _levi_equivalent_for(name)
            if equiv:
                entry["action"] = "replace"
                entry["target_usd"] = 0.0
                entry["levi_equivalent"] = equiv["module"]
                entry["rationale"] = (
                    "LEVI-native equivalent in-repo (%s: %s) — verify fit, "
                    "then cancel the subscription" % (equiv["module"], equiv["what"])
                )
            elif category == "hosting":
                # The keeper's word: even hosting cost rates get attacked.
                # Hybrid combos first (drafted, owner-approved); the generic
                # plays stay the fallback for hosting lines no combo fits.
                combo = _hosting_combo_for(name)
                if combo:
                    action, label, play = combo
                    entry["action"] = action
                    entry["combo"] = label
                    entry["rationale"] = (
                        "hosting combo draft %r (hybrid cost-cutting "
                        "method, web-index estimates — no savings numbers "
                        "claimed): %s. Draft only — the owner fit-checks, "
                        "picks, and sets the target on plan approval; the "
                        "target stays owner-stated until then" % (label, play)
                    )
                else:
                    entry["action"] = "rehost"
                    plays = "right-size the plan, shop cheaper providers"
                    if hosting_bills > 1:
                        plays += (
                            ", consolidate %d hosting bills to one host" % hosting_bills
                        )
                    plays += (
                        "; static/local-first LEVI-native build where it "
                        "fits — spend stays owner-stated until the owner "
                        "sets the target"
                    )
                    entry["rationale"] = "hosting rate attack (draft): " + plays
            elif category == "saas" and amount >= 50:
                entry["action"] = "review"
                entry["rationale"] = (
                    "largest SaaS line — consolidate vendors or renegotiate"
                )
            elif category == "fees":
                entry["action"] = "review"
                entry["rationale"] = "fee line — consolidate or renegotiate"
            seen[key] = entry
        targets.append(entry)
    return targets


def cost_savings(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """Verified savings receipt. Both sides are owner-stated figures;
    the receipt labels them as such — verified means the math checks
    and both sides are on the record, not that we metered the spend."""
    b_total = float((before or {}).get("total_monthly_usd", 0) or 0)
    a_total = float((after or {}).get("total_monthly_usd", 0) or 0)
    savings = round(b_total - a_total, 2)
    return {
        "before_monthly_usd": round(b_total, 2),
        "after_monthly_usd": round(a_total, 2),
        "savings_monthly_usd": savings,
        "savings_annual_usd": round(savings * 12, 2),
        "provenance": "owner-stated",
        "note": (
            "both sides owner-stated; savings = before − after, "
            "verified arithmetic on figures the owner put on the record"
        ),
    }


def hosting_savings(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """Hosting-only savings receipt, broken out of the total.

    Same honesty as ``cost_savings``: both sides owner-stated, verified
    arithmetic only. Returns {} when neither side records hosting spend
    — no hosting on the record means no hosting savings to claim.
    """
    b_by = (before or {}).get("by_category") or {}
    a_by = (after or {}).get("by_category") or {}
    if "hosting" not in b_by and "hosting" not in a_by:
        return {}
    b = round(float(b_by.get("hosting", 0) or 0), 2)
    a = round(float(a_by.get("hosting", 0) or 0), 2)
    s = round(b - a, 2)
    return {
        "before_monthly_usd": b,
        "after_monthly_usd": a,
        "savings_monthly_usd": s,
        "savings_annual_usd": round(s * 12, 2),
        "provenance": "owner-stated",
        "note": (
            "hosting category only — owner-stated figures on both "
            "sides, verified arithmetic"
        ),
    }


# -- the metric catalog -------------------------------------------------------
# name: (plain-words description, direction, healthy target, unit).
# "at_least" — healthy means at or above the target.
# "at_most"  — healthy means at or below the target.
# Targets are published tuning judgments, not hidden knobs.

METRIC_CATALOG: Dict[str, tuple] = {
    "reachability": (
        "share of walked pages that answer HTTP 200",
        "at_least",
        1.0,
        "share",
    ),
    "title_coverage": (
        "share of walked pages with a non-empty <title>",
        "at_least",
        1.0,
        "share",
    ),
    "heading_coverage": (
        "share of walked pages with a top-level heading",
        "at_least",
        1.0,
        "share",
    ),
    "contact_presence": (
        "1 if any phone/email found on walked pages, else 0",
        "at_least",
        1.0,
        "presence",
    ),
    "content_completeness": (
        "share of walked pages with >= 200 chars of text",
        "at_least",
        1.0,
        "share",
    ),
    "link_health": (
        "share of link markers that carry a target",
        "at_least",
        1.0,
        "share",
    ),
    "form_completeness": (
        "share of forms with at least one named field",
        "at_least",
        1.0,
        "share",
    ),
    "conversion_path": (
        "0 = no path, 1 = contact info only, 2 = form/booking path present",
        "at_least",
        2.0,
        "ladder",
    ),
    "median_page_weight_kb": (
        "median served-text weight of walked pages (performance proxy)",
        "at_most",
        100.0,
        "kb",
    ),
    "max_page_weight_kb": (
        "heaviest walked page (performance proxy)",
        "at_most",
        300.0,
        "kb",
    ),
}

METRICS = tuple(METRIC_CATALOG)

#: Which audit check drives which metric target on the rescue plan.
CHECK_TARGETS: Dict[str, str] = {
    "reachable": "reachability",
    "has-title": "title_coverage",
    "has-heading": "heading_coverage",
    "contact-visible": "contact_presence",
    "links-resolve": "link_health",
    "forms-described": "form_completeness",
}

_CONTENT_FLOOR_CHARS = 200


def _has_contact(text: str) -> bool:
    return bool(_CONTACT_RE.search(text or ""))


def _has_heading(page: Dict[str, Any]) -> bool:
    """Mirror the audit's has-heading probe, per page."""
    text = page.get("text") or ""
    if re.search(r"(?m)^#{1,2} |^(?:[A-Z][^\n]{2,80})$", text):
        return True
    if "heading" in (page.get("structure") or ""):
        return True
    return bool(re.search(r"(?im)^(#+ .+|.+\n[=-]{3,})$", text))


def _form_fields(form: Any) -> List[Any]:
    return form.get("fields") if isinstance(form, dict) else []


def _link_target(link: Any) -> Optional[str]:
    return link.get("target") if isinstance(link, dict) else link


def measure(walk: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    """Measure the site. Pure, deterministic, stdlib-only, no network.

    The walk is the whole world: every metric is a function of the
    page records. Same walk → same numbers, in any key order.
    """
    if not walk:
        raise ValueError("measure: empty walk — nothing was actually visited")
    pages = [walk[k] for k in sorted(walk)]
    n = len(pages)

    reach = sum(1 for p in pages if p.get("status") == 200)
    titled = sum(1 for p in pages if (p.get("title") or "").strip())
    headed = sum(1 for p in pages if _has_heading(p))
    contact = 1.0 if any(_has_contact(p.get("text") or "") for p in pages) else 0.0
    content = sum(1 for p in pages if len(p.get("text") or "") >= _CONTENT_FLOOR_CHARS)

    links = [link for p in pages for link in (p.get("links") or [])]
    link_ok = sum(1 for link in links if _link_target(link))

    forms = [f for p in pages for f in (p.get("forms") or [])]
    form_ok = sum(1 for f in forms if _form_fields(f))
    has_form_path = 1 if form_ok else 0

    if has_form_path:
        conversion = 2.0
    elif contact:
        conversion = 1.0
    else:
        conversion = 0.0

    weights_kb = [len((p.get("text") or "").encode("utf-8")) / 1024.0 for p in pages]

    def share(x: int, total: int) -> float:
        return round(x / total, 3) if total else 1.0

    return {
        "reachability": share(reach, n),
        "title_coverage": share(titled, n),
        "heading_coverage": share(headed, n),
        "contact_presence": contact,
        "content_completeness": share(content, n),
        "link_health": share(link_ok, len(links)),
        "form_completeness": share(form_ok, len(forms)),
        "conversion_path": conversion,
        "median_page_weight_kb": round(statistics.median(weights_kb), 1),
        "max_page_weight_kb": round(max(weights_kb), 1),
    }


@dataclass
class Baseline:
    """The measured before-state of the business's site.

    ``cost`` is the owner's stated monthly operating spend
    (``cost_baseline`` output) — the money side of the baseline.
    """

    id: str
    invitation_id: str
    business: str
    values: Dict[str, float] = field(default_factory=dict)
    page_count: int = 0
    measured_at: str = ""
    cost: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Baseline":
        data = dict(data)
        known = {
            "id",
            "invitation_id",
            "business",
            "values",
            "page_count",
            "measured_at",
            "cost",
        }
        return cls(**{k: v for k, v in data.items() if k in known})


def _next_id(home) -> str:
    state_path = rescue_home(home) / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        state = {}
    n = int(state.get("baseline_counter", 0)) + 1
    state["baseline_counter"] = n
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return "baseline-%04d" % n


def _baseline_path(home, invitation_id: str, tag: str = "before"):
    name = "baseline.json" if tag == "before" else "baseline_%s.json" % tag
    return ensure_home(home) / "episodes" / invitation_id / name


def baseline_from_walk(
    home,
    invitation_id: str,
    walk: Dict[str, Dict[str, Any]],
    costs: Optional[List[Dict[str, Any]]] = None,
    tag: str = "before",
) -> Baseline:
    """Measure the invited site. Consent is required — analytics is OF
    the business's own site, with the owner's invitation, never ABOUT
    other people and never without consent.

    ``costs`` defaults to the owner's stated spend on the invitation;
    pass explicit items to override (they are validated + labeled).
    ``tag`` namespaces the stored record ("before" vs "after") so the
    after-measurement never overwrites the before-baseline on disk.
    """
    inv = require_consent(home, invitation_id)
    values = measure(walk)
    cost_items = validate_costs(costs) if costs is not None else list(inv.costs)
    baseline = Baseline(
        id=_next_id(home),
        invitation_id=inv.id,
        business=inv.business,
        values=values,
        page_count=len(walk),
        measured_at=_now(),
        cost=cost_baseline(cost_items),
    )
    path = _baseline_path(home, inv.id, tag)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(baseline.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    stone.record(
        home,
        "analytics.baseline",
        inv.id,
        {
            "baseline_id": baseline.id,
            "page_count": baseline.page_count,
            "values": values,
            "stated_monthly_usd": baseline.cost["total_monthly_usd"],
            "cost_items": baseline.cost["item_count"],
        },
    )
    return baseline


def get_baseline(home, invitation_id: str, tag: str = "before") -> Optional[Baseline]:
    path = _baseline_path(home, invitation_id, tag)
    try:
        return Baseline.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (FileNotFoundError, ValueError, OSError):
        return None


def healthy_target(metric: str) -> Dict[str, Any]:
    """What healthy looks like, in numbers, for one metric."""
    desc, direction, target, unit = METRIC_CATALOG[metric]
    return {
        "metric": metric,
        "description": desc,
        "direction": direction,
        "target": target,
        "unit": unit,
    }


def target_for(
    check_id: str, baseline: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """The numeric target for one rescue-plan item, given its check.

    ``baseline`` is the audit's baseline dict (or None). The target
    carries the before-value so the plan states where the business
    starts and what healthy looks like.
    """
    metric = CHECK_TARGETS.get(check_id)
    if metric is None:
        return {}
    spec = healthy_target(metric)
    values = (baseline or {}).get("values", {}) if baseline else {}
    spec["before"] = values.get(metric)
    return spec


def target_met(metric: str, value: float) -> bool:
    """True if the measured value meets the healthy target."""
    _, direction, target, _ = METRIC_CATALOG[metric]
    if direction == "at_least":
        return value >= target
    return value <= target


def metric_deltas(
    before: Dict[str, float], after: Dict[str, float]
) -> List[Dict[str, Any]]:
    """Before/after per metric. Every metric ships — moved or not.

    A metric that didn't budge carries delta 0 and an honest
    ``target_met`` verdict. Nothing is smoothed away.
    """
    deltas = []
    for metric in METRICS:
        b = before.get(metric)
        a = after.get(metric)
        if b is None or a is None:
            continue
        desc, direction, target, unit = METRIC_CATALOG[metric]
        delta = round(a - b, 3)
        deltas.append(
            {
                "metric": metric,
                "description": desc,
                "unit": unit,
                "direction": direction,
                "target": target,
                "before": b,
                "after": a,
                "delta": delta,
                "target_met": target_met(metric, a),
            }
        )
    return deltas


__all__ = [
    "CHECK_TARGETS",
    "COST_ACTIONS",
    "LEVI_EQUIVALENTS",
    "METRIC_CATALOG",
    "METRICS",
    "Baseline",
    "baseline_from_walk",
    "cost_baseline",
    "cost_savings",
    "get_baseline",
    "healthy_target",
    "hosting_savings",
    "measure",
    "metric_deltas",
    "propose_cost_targets",
    "target_for",
    "target_met",
]
