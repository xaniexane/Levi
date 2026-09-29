"""CLI: python -m levi.demand

Thin entry point over DemandPulse: scan free-text into demand signals,
score opportunities (3-factor worth or the five-factor composite),
and show status. Mirrors ``levi demand``.

Honesty rules are inherited unchanged: five-factor scoring requires a
basis note for every factor (rejected if empty), and every score is
labeled a hypothesis/advisory — never a claim about real demand.

Feed subcommands (score→curate→digest product surface):
  feed    curate stored score cards into a dated digest (optionally scoring
          one new opportunity inline first), dedupe against previous
          digests, store as JSONL
  digest  show the latest stored digest (or --id one)
  watch   mark an opportunity id as watched

Alert subcommands (Copilot-style proactive notifications):
  alerts create|list|delete|enable|disable|run|test

Workflow subcommands (the 10 original DemandPulse workflows, wired to alerts):
  workflows install|list|status|run

Watcher subcommands (poll notification/email/text sources for candidate
unmet-need signals — HYPOTHESIS only, inbound only, never touches alerts):
  watcher run|status|ingest

Direction subcommands (life-coach / personal-refinement sense alongside
scoring — deterministic, transparent, profile is editable data):
  direction       show the direction profile (--reseed to rewrite it from
                  the documented seed; --fit "text" to score one signal)
  coach           render the coach brief from the pulse store

Bridge subcommands (DemandPulse -> DDD: scored signals auto-draft held
outreach drafts — draft-only, never approves, never sends):
  bridge          status|scan|draft|sync-outcomes
"""

from __future__ import annotations

import argparse
import sys

_FEED_COMMANDS = ("feed", "digest", "watch")
_ALERT_COMMANDS = ("alerts",)


def _neighbor_notifier():
    """Attach the NeighborOS notifier so `push`-channel alerts actually
    reach the phone. Inert for alerts on console/file only; returns None
    (push stays "not_configured") if the neighbor tree is unavailable."""
    try:
        from levi.neighbor import notify as notify_mod
        from levi.neighbor import policies as policies_mod
        from levi.neighbor.store import Store as NeighborStore
    except Exception:  # noqa: BLE001 — demand must never break on notify import
        return None
    try:
        nstore = NeighborStore()
        cfg = policies_mod.load_policies(nstore).get("notify", {})
        return notify_mod.Notifier(config=cfg, state_dir=nstore.base)
    except Exception:  # noqa: BLE001
        return None
_WORKFLOW_COMMANDS = ("workflows",)
_STUDIO_COMMANDS = ("studio",)
_MAINT_COMMANDS = ("dedupe",)
_QUARANTINE_COMMANDS = ("quarantine",)
_WATCHER_COMMANDS = ("watcher",)
_OPPORTUNITIES_COMMANDS = ("opportunities",)
_OUTCOMES_COMMANDS = ("outcomes",)
_BRIDGE_COMMANDS = ("bridge",)
_DIRECTION_COMMANDS = ("direction", "coach")


def _flag_for(factor: str) -> str:
    return {
        "demand": "ff_demand",
        "market_size": "ff_market",
        "competition_gap": "ff_gap",
        "trend_velocity": "ff_velocity",
        "entry_feasibility": "ff_feasibility",
    }[factor]


def cmd_run(args) -> int:
    from levi.demand.pulse import DemandPulse

    dp = DemandPulse()
    if args.scan:
        signal = dp.scan_seed(args.scan, segment=args.segment or "general")
        print(f"Signal [{signal.id}] kind={signal.kind}: {signal.need[:80]}")
        if args.title:
            if args.five_factor:
                return _cmd_five_factor(dp, signal.id, args)
            try:
                opp = dp.score_opportunity(
                    signal.id,
                    args.title,
                    demand_score=float(args.demand_score),
                    serviceability=float(args.serviceability),
                    startup_cost=float(args.cost),
                )
            except ValueError as exc:
                print(f"Opportunity scoring rejected: {exc}", file=sys.stderr)
                return 1
            print(f"Opportunity worth={opp.worth:.2f}: {opp.title}")
    elif args.five_factor:
        print(
            'Five-factor scoring needs --scan "..." --title "..." '
            "plus the --ff-* factors.",
            file=sys.stderr,
        )
        return 2
    print(dp.format_status())
    return 0


def _cmd_five_factor(dp, demand_id, args) -> int:
    from levi.demand.scoring import FACTORS, parse_weights

    missing = [f for f in FACTORS if getattr(args, _flag_for(f)) is None]
    if missing:
        print(
            "Five-factor scoring needs values for: "
            + ", ".join(missing)
            + " (flags --ff-demand/--ff-market/--ff-gap/--ff-velocity/"
            "--ff-feasibility, 0-100).",
            file=sys.stderr,
        )
        return 2
    basis = args.ff_basis
    if not basis or not basis.strip():
        print(
            "Five-factor scoring needs --ff-basis: a note on why these "
            "scores were assigned.",
            file=sys.stderr,
        )
        return 2
    weights = None
    if args.ff_weights:
        try:
            weights = parse_weights(args.ff_weights)
        except ValueError as exc:
            print(f"Bad --ff-weights: {exc}", file=sys.stderr)
            return 2
    try:
        factor_vals = {f: (float(getattr(args, _flag_for(f))), basis) for f in FACTORS}
        threshold = float(args.ff_threshold or 75.0)
    except (TypeError, ValueError) as exc:
        print(f"Five-factor scoring rejected: {exc}", file=sys.stderr)
        return 1
    try:
        card = dp.score_five_factor(
            demand_id, args.title, factor_vals, weights=weights, threshold=threshold
        )
    except ValueError as exc:
        print(f"Five-factor scoring rejected: {exc}", file=sys.stderr)
        return 1
    print(card.explain())
    print(dp.format_status())
    return 0


def cmd_feed(args) -> int:
    """Score (optionally) → curate → digest, one run."""
    from levi.demand import feed as feedmod
    from levi.demand.pulse import DemandPulse
    from levi.demand.scoring import FACTORS, parse_weights

    dp = DemandPulse()
    if args.title:
        missing = [f for f in FACTORS if getattr(args, _flag_for(f), None) is None]
        if missing:
            print(
                "Inline scoring needs values for: "
                + ", ".join(missing)
                + " (flags --ff-demand/--ff-market/--ff-gap/--ff-velocity/"
                "--ff-feasibility, 0-100).",
                file=sys.stderr,
            )
            return 2
        basis = args.ff_basis
        if not basis or not basis.strip():
            print(
                "Inline scoring needs --ff-basis: a note on why these "
                "scores were assigned.",
                file=sys.stderr,
            )
            return 2
        weights = None
        if args.ff_weights:
            try:
                weights = parse_weights(args.ff_weights)
            except ValueError as exc:
                print(f"Bad --ff-weights: {exc}", file=sys.stderr)
                return 2
        try:
            factor_vals = {
                f: (float(getattr(args, _flag_for(f))), basis) for f in FACTORS
            }
            threshold = float(args.ff_threshold or 75.0)
        except (TypeError, ValueError) as exc:
            print(f"Inline scoring rejected: {exc}", file=sys.stderr)
            return 1
        seed = args.scan or args.title
        try:
            signal = dp.scan_seed(seed, segment=args.segment or "general")
            card = dp.score_five_factor(
                signal.id,
                args.title,
                factor_vals,
                weights=weights,
                threshold=threshold,
            )
        except ValueError as exc:
            print(f"Inline scoring rejected: {exc}", file=sys.stderr)
            return 1
        print(f"Scored [{card.opportunity_id}] {card.title}: {card.composite:.2f}")

    if not dp.score_cards:
        print(
            "No score cards to curate — seed one with: "
            'python -m levi.demand feed --title "…" --ff-demand 80 … --ff-basis "…"',
            file=sys.stderr,
        )
        return 1
    digest = feedmod.curate(dp.score_cards)
    path = feedmod.store_digest(digest)
    print(feedmod.render_digest(digest))
    print(f"stored: {path}")
    return 0


def cmd_digest(args) -> int:
    """Show the latest stored digest (or --id one)."""
    from levi.demand import feed as feedmod

    digest = feedmod.load_digest(args.id) if args.id else feedmod.load_latest()
    if digest is None:
        print("No digests stored yet — run: python -m levi.demand feed")
        return 1
    print(feedmod.render_digest(digest))
    return 0


def cmd_watch(args) -> int:
    """Mark an opportunity id as watched."""
    from levi.demand import feed as feedmod

    added = feedmod.watch_item(args.item)
    print(f"{'Now watching' if added else 'Already watching'} [{args.item}]")
    return 0


def _quarantine_main(argv) -> int:
    """Subcommand dispatch for: quarantine (signal quality holding pen).

    Dry-run by default. --apply flags low-evidence signals (kept in the
    store, excluded from live views). --unquarantine <id> reverses one.
    Nothing is ever deleted.
    """
    import shutil
    from datetime import datetime, timezone

    ap = argparse.ArgumentParser(
        prog="levi demand quarantine",
        description="Quarantine low-evidence signals: feed-sourced signals "
        "with no item provenance, internal ops aggregates, and "
        "supply-side offers. Quarantined signals stay in the store "
        "(nothing is deleted) but leave the live views. Reversible.",
    )
    ap.add_argument(
        "--apply", action="store_true",
        help="flag the signals for real (default is a dry-run report)",
    )
    ap.add_argument(
        "--unquarantine", default=None, metavar="SIGNAL_ID",
        help="clear one signal's quarantine flags",
    )
    args = ap.parse_args(argv[1:])

    from levi.demand.pulse import DEFAULT, DemandPulse

    if not DEFAULT.exists():
        print("No pulse store yet — nothing to quarantine.")
        return 0
    dp = DemandPulse()
    if args.unquarantine:
        ok = dp.unquarantine(args.unquarantine)
        print(
            f"{'Unquarantined' if ok else 'No signal'} [{args.unquarantine}]"
        )
        return 0 if ok else 1
    if args.apply:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup = DEFAULT.with_name(f"{DEFAULT.name}.bak-{stamp}")
        shutil.copy2(DEFAULT, backup)
        print(f"backup: {backup}")
    report = dp.run_quarantine(dry_run=not args.apply)
    print(
        f"{'would quarantine' if report['dry_run'] else 'quarantined'}: "
        f"{report['quarantined']} signal(s)"
    )
    for reason, n in sorted(
        report["reasons"].items(), key=lambda kv: -kv[1]
    ):
        print(f"  {n:>3d}  {reason}")
    if report["dry_run"]:
        print("(dry run — store untouched; re-run with --apply)")
    else:
        live = len(dp.live_signals())
        print(f"live signals: {live} of {len(dp.signals)}")
    return 0


def _maint_main(argv) -> int:
    """Subcommand dispatch for: dedupe (one-shot store maintenance)."""
    import shutil
    from datetime import datetime, timezone

    ap = argparse.ArgumentParser(
        prog="levi demand dedupe",
        description="One-shot maintenance: back up the pulse store, then "
        "collapse duplicate signals, opportunities and score cards. "
        "Repeats are occurrence metadata (seen_count), never evidence — "
        "confidence is untouched.",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would merge without writing anything",
    )
    args = ap.parse_args(argv[1:])

    from levi.demand.pulse import DEFAULT, DemandPulse

    if not DEFAULT.exists():
        print("No pulse store yet — nothing to dedupe.")
        return 0
    dp = DemandPulse()
    if not args.dry_run:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup = DEFAULT.with_name(f"{DEFAULT.name}.bak-{stamp}")
        shutil.copy2(DEFAULT, backup)
        print(f"backup: {backup}")
    report = dp.dedupe_store(dry_run=args.dry_run)
    for section in ("signals", "opportunities", "score_cards"):
        r = report[section]
        print(
            f"{section:14s} before={r['before']:>4}  after={r['after']:>4}  "
            f"merged={r['merged']:>4}"
        )
    if args.dry_run:
        print("(dry run — store untouched)")
    return 0


def _watcher_main(argv) -> int:
    """Subcommand dispatch for: watcher run|status|ingest (poll ticks)."""
    import json as _json

    ap = argparse.ArgumentParser(
        prog="levi demand watcher",
        description="DemandPulse watcher — poll notification/email/text "
        "sources for candidate unmet-need signals (HYPOTHESIS only, "
        "inbound only, never touches alerts).",
    )
    sub = ap.add_subparsers(dest="action", required=True)
    r = sub.add_parser("run", help="one poll tick (email + eyes headless; device needs agent)")
    r.add_argument("--max", type=int, default=50, help="max Gmail candidates per tick")
    r.add_argument("--budget", type=float, default=240.0, help="tick budget seconds")
    sub.add_parser("status", help="channel health + watermarks (read-only)")
    e = sub.add_parser(
        "eyes",
        help="server-side sensing only: RSS/Atom feeds + Hacker News (headless)",
    )
    esub = e.add_subparsers(dest="eyes_action", required=True)
    er = esub.add_parser("run", help="one eyes tick inside the tick budget")
    er.add_argument("--budget", type=float, default=240.0)
    esub.add_parser("status", help="eye health + feed list (read-only)")
    h = sub.add_parser(
        "hook",
        help="run the local webhook receiver (binds 127.0.0.1 only; "
        "needs DP_HOOK_TOKEN)",
    )
    h.add_argument("--port", type=int, default=8765)
    h.add_argument("--bind", default="127.0.0.1")
    i = sub.add_parser(
        "ingest",
        help="ingest pre-fetched device items (agent runtime feeds "
        "device.invoke results here)",
    )
    i.add_argument("--channel", required=True, choices=("text", "notification"))
    i.add_argument(
        "--items",
        required=True,
        help="JSON array of {id, text, ts?} — e.g. mapped from message.search",
    )
    args = ap.parse_args(argv)

    from levi.demand import watcher as wmod

    if args.action == "status":
        print(_json.dumps(wmod.status(), indent=2))
        return 0
    if args.action == "run":
        receipt = wmod.run(max_n=args.max, budget_s=args.budget)
        print(_json.dumps(receipt, indent=2))
        return 0
    if args.action == "hook":
        from levi.demand import hook as hmod

        try:
            hmod.serve(port=args.port, bind=args.bind)
        except (ValueError, RuntimeError) as exc:
            print(f"hook: {exc}", file=sys.stderr)
            return 2
        return 0
    if args.action == "eyes":
        from levi.demand import eyes as emod

        if args.eyes_action == "status":
            print(_json.dumps(emod.status(), indent=2))
            return 0
        receipt = emod.run_eyes(budget_s=args.budget)
        print(_json.dumps(receipt, indent=2))
        return 0
    # ingest
    try:
        items = _json.loads(args.items)
    except _json.JSONDecodeError as exc:
        print(f"ingest: bad --items JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(items, list):
        print("ingest: --items must be a JSON array", file=sys.stderr)
        return 2
    from levi.demand.pulse import DemandPulse

    state = wmod.WatcherState.load()
    receipt = wmod.ingest_items(DemandPulse(), state, args.channel, items)
    state.save()
    print(_json.dumps(receipt, indent=2))
    return 0


def _opportunities_main(argv) -> int:
    """Subcommand dispatch for: opportunities [--top N] [--json].

    Ranked demand opportunities straight from the store: every signal
    carries its deterministic number (scored at ingest, backfilled by
    ensure_numbers), signals cluster into opportunity rows, rows rank
    by score. No shadow system — the view reads the same store the
    watcher writes.
    """
    import json as _json

    ap = argparse.ArgumentParser(
        prog="levi demand opportunities",
        description="Ranked demand opportunities from scored store signals "
        "(deterministic numbers, rubric in docs/DEMAND_NUMBERS.md).",
    )
    ap.add_argument(
        "--top", type=int, default=10, help="how many ranked rows to show"
    )
    ap.add_argument(
        "--json", action="store_true", help="machine-readable JSON output"
    )
    args = ap.parse_args(argv)

    from levi.demand import numbers as numod
    from levi.demand.pulse import DemandPulse

    dp = DemandPulse()
    rescored = dp.ensure_numbers()
    live = dp.live_signals()
    rows = numod.opportunity_rows(live)
    top = args.top if isinstance(args.top, int) and args.top >= 1 else 10
    rows = rows[:top]
    if args.json:
        print(_json.dumps([r.to_dict() for r in rows], indent=2))
        return 0
    print(numod.render_rows(rows, signal_total=len(live), rescored=rescored))
    nq = len(dp.signals) - len(live)
    if nq:
        print(f"({nq} signal(s) in quarantine — excluded; see `levi demand quarantine`)")
    return 0


def _feed_main(argv) -> int:
    """Subcommand dispatch for: feed | digest | watch."""
    ap = argparse.ArgumentParser(
        prog="levi.demand",
        description="LEVI DemandPulse feed — score→curate→digest, "
        "show digests, watch items",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    feed_p = sub.add_parser(
        "feed", help="curate score cards into a dated digest (JSONL)"
    )
    feed_p.add_argument("--scan", default=None, help="seed text for inline scoring")
    feed_p.add_argument("--segment", default="general")
    feed_p.add_argument(
        "--title", default=None, help="score one opportunity inline before curating"
    )
    feed_p.add_argument("--ff-demand", type=float, default=None)
    feed_p.add_argument("--ff-market", type=float, default=None)
    feed_p.add_argument("--ff-gap", type=float, default=None)
    feed_p.add_argument("--ff-velocity", type=float, default=None)
    feed_p.add_argument("--ff-feasibility", type=float, default=None)
    feed_p.add_argument(
        "--ff-basis", default=None, help="REQUIRED for inline scoring: why these scores"
    )
    feed_p.add_argument("--ff-weights", default=None, help="e.g. 0.3,0.25,0.2,0.15,0.1")
    feed_p.add_argument("--ff-threshold", type=float, default=75.0)
    feed_p.set_defaults(func=cmd_feed)

    dig_p = sub.add_parser("digest", help="show the latest stored digest")
    dig_p.add_argument("--id", default=None, help="show a specific digest id")
    dig_p.set_defaults(func=cmd_digest)

    watch_p = sub.add_parser("watch", help="mark an opportunity id as watched")
    watch_p.add_argument("--item", required=True, help="opportunity_id to watch")
    watch_p.set_defaults(func=cmd_watch)

    args = ap.parse_args(argv)
    return args.func(args)


def _alerts_main(argv) -> int:
    """Subcommand dispatch for: alerts ..."""
    from levi.demand import alerts as alertmod
    from levi.demand.pulse import DemandPulse

    ap = argparse.ArgumentParser(
        prog="levi.demand alerts",
        description="DemandPulse alerts — Copilot-style proactive notifications",
    )
    sub = ap.add_subparsers(dest="action", required=True)

    c = sub.add_parser("create", help="create an alert")
    c.add_argument("--type", dest="kind", required=True, choices=alertmod.ALERT_TYPES)
    c.add_argument("--name", required=True)
    c.add_argument("--time", default="07:00", help="HH:MM local (briefing/reminder)")
    c.add_argument("--recurrence", default="daily", choices=alertmod.RECURRENCE)
    c.add_argument(
        "--dow",
        type=int,
        default=-1,
        help="weekly briefings only: 0=Mon..6=Sun, -1=any day",
    )
    c.add_argument("--at", default="", help="ISO datetime (one-shot reminder)")
    c.add_argument("--threshold", type=float, default=75.0)
    c.add_argument("--worth-bar", type=float, default=0.80)
    c.add_argument("--segment", default="")
    c.add_argument("--message", default="")
    c.add_argument(
        "--channels",
        default="console,file",
        help="comma-separated: console,file,push,email,sms,whatsapp,webhook,"
        "sheets — sms/email/whatsapp/webhook/sheets ride the failover chain "
        "(first confirmed delivery wins); webhook needs "
        "LEVI_ALERT_WEBHOOK_URL, sheets needs LEVI_SHEETS_WEBHOOK_URL",
    )
    c.add_argument("--quiet-start", default=alertmod.DEFAULT_QUIET_START)
    c.add_argument("--quiet-end", default=alertmod.DEFAULT_QUIET_END)
    c.add_argument("--disabled", action="store_true")

    sub.add_parser("list", help="list alerts")

    d = sub.add_parser("delete", help="delete an alert")
    d.add_argument("--id", required=True)

    e = sub.add_parser("enable", help="enable an alert")
    e.add_argument("--id", required=True)

    x = sub.add_parser("disable", help="disable an alert")
    x.add_argument("--id", required=True)

    sub.add_parser("run", help="evaluate due alerts and deliver (cron calls this)")

    t = sub.add_parser("test", help="render a sample card without firing")
    t.add_argument("--id", required=True)

    args = ap.parse_args(argv)
    eng = alertmod.AlertEngine()

    if args.action == "create":
        channels = tuple(c.strip() for c in args.channels.split(",") if c.strip())
        try:
            alert = eng.create(
                args.kind,
                args.name,
                time=args.time,
                recurrence=args.recurrence,
                dow=args.dow,
                at=args.at,
                threshold=args.threshold,
                worth_bar=args.worth_bar,
                segment=args.segment,
                message=args.message,
                channels=channels,
                quiet_start=args.quiet_start,
                quiet_end=args.quiet_end,
                enabled=not args.disabled,
            )
        except ValueError as exc:
            print(f"Alert rejected: {exc}", file=sys.stderr)
            return 1
        print(f"Created [{alert.id}] {alert.type}: {alert.name}")
        return 0

    if args.action == "list":
        if not eng.alerts:
            print("(no alerts — create one with: levi demand alerts create …)")
            return 0
        for a in eng.alerts:
            state = "on" if a.enabled else "off"
            print(f"[{a.id}] {a.type:9s} {state:3s} {a.name}")
        return 0

    if args.action == "delete":
        print("Deleted." if eng.delete(args.id) else "No such alert.")
        return 0 if eng.get(args.id) is None else 1

    if args.action in ("enable", "disable"):
        ok = eng.set_enabled(args.id, args.action == "enable")
        print("Updated." if ok else "No such alert.")
        return 0 if ok else 1

    if args.action == "run":
        dp = DemandPulse()
        notifier = _neighbor_notifier()
        receipt = eng.run(dp, notifier=notifier)
        print(
            f"fired={receipt['fired']} delivered={receipt['delivered']} "
            f"held={receipt['held']} flushed={receipt['flushed']}"
        )
        for ch, states in receipt["channel_status"].items():
            print(f"  {ch}: {', '.join(states)}")
        return 0

    if args.action == "test":
        alert = eng.get(args.id)
        if alert is None:
            print("No such alert.", file=sys.stderr)
            return 1
        event = alertmod.AlertEvent(
            alert_id=alert.id,
            alert_name=alert.name,
            kind=alert.type,
            title="Sample card (test — nothing fired)",
            lines=["This is what the alert card looks like."],
            dedup_key="test",
        )
        print(event.render_card())
        return 0

    return 2


def _workflows_main(argv) -> int:
    """Subcommand dispatch for: workflows install|list|status|run."""
    from levi.demand import workflows as wfmod

    ap = argparse.ArgumentParser(
        prog="levi.demand workflows",
        description="The 10 original DemandPulse workflows, wired into alerts",
    )
    sub = ap.add_subparsers(dest="action", required=True)

    sub.add_parser("install", help="install the 9 alert-backed workflows (idempotent)")
    sub.add_parser("list", help="list the 10 original workflows and their schedules")
    sub.add_parser("status", help="show which workflow alerts are installed/enabled")

    r = sub.add_parser(
        "run", help="run one workflow now (advisory: fetches + evaluates)"
    )
    r.add_argument("--id", type=int, required=True, help="workflow number 1..10")
    r.add_argument("--query", default="ai tools", help="scan query for scan workflows")

    args = ap.parse_args(argv)

    if args.action == "install":
        created = wfmod.install_workflows()
        if not created:
            print("All workflow alerts already installed.")
        for alert in created:
            print(f"Installed [{alert.id}] {alert.type}: {alert.name}")
        return 0

    if args.action == "list":
        for row in wfmod.list_workflows():
            print(
                f"{row['id']:>2}. {row['name']:<36} {row['schedule']:<28} -> {row['alert_kind']}"
            )
        return 0

    if args.action == "status":
        for row in wfmod.workflow_status():
            inst = "installed" if row["installed"] else "missing"
            state = "on" if row["enabled"] else "off"
            print(f"{row['id']:>2}. {row['name']:<36} {inst} {state}")
        return 0

    if args.action == "run":
        try:
            result = wfmod.run_workflow(args.id, query=args.query)
        except ValueError as exc:
            print(f"Workflow rejected: {exc}", file=sys.stderr)
            return 1
        print(
            f"Workflow {result['workflow']}: {result.get('name', 'Signal Correlation Engine')}"
        )
        for key in (
            "signals",
            "clusters",
            "opportunities",
            "fed_into_demandpulse",
            "correlated",
        ):
            if key in result:
                print(f"  {key}: {result[key]}")
        rec = result.get("alert_receipt")
        if rec:
            print(
                f"  alerts fired={rec['fired']} delivered={rec['delivered']} "
                f"held={rec['held']} flushed={rec['flushed']}"
            )
        return 0

    return 2


def _studio_main(argv) -> int:
    """Subcommand dispatch for: studio ingest|score|brief|run|engines."""
    from levi.demand import studio as studiomod

    ap = argparse.ArgumentParser(
        prog="levi.demand studio",
        description="Wave Pulse — content intelligence: ingest signals, "
        "grade them, extract patterns, emit an agent brief. "
        "Grades are hypotheses, never earnings claims.",
    )
    sub = ap.add_subparsers(dest="action", required=True)

    sub.add_parser("engines", help="list available content engines")

    ing = sub.add_parser("ingest", help="fetch signals and store as JSONL")
    ing.add_argument("--source", default="reddit", choices=sorted(studiomod.ADAPTERS))
    ing.add_argument(
        "--query", default="all", help="subreddit for reddit; JSONL path for local"
    )
    ing.add_argument("--limit", type=int, default=25)
    ing.add_argument("--name", required=True, help="dataset name for later steps")

    sc = sub.add_parser("score", help="grade a stored dataset")
    sc.add_argument("--name", required=True)
    sc.add_argument("--threshold", type=float, default=studiomod.GRADE_THRESHOLD)
    sc.add_argument("--top", type=int, default=10)

    br = sub.add_parser("brief", help="patterns + agent brief for a dataset")
    br.add_argument("--name", required=True)
    br.add_argument("--niche", required=True)
    br.add_argument("--threshold", type=float, default=studiomod.GRADE_THRESHOLD)
    br.add_argument(
        "--engine",
        default=None,
        choices=studiomod.list_engines(),
        help="run the brief through a named content engine",
    )

    rn = sub.add_parser("run", help="ingest -> score -> brief, one shot")
    rn.add_argument("--source", default="reddit", choices=sorted(studiomod.ADAPTERS))
    rn.add_argument("--query", default="all")
    rn.add_argument("--limit", type=int, default=25)
    rn.add_argument("--name", required=True)
    rn.add_argument("--niche", required=True)
    rn.add_argument(
        "--engine",
        default=None,
        choices=studiomod.list_engines(),
        help="run the brief through a named content engine",
    )

    args = ap.parse_args(argv)

    if args.action == "engines":
        for key in studiomod.list_engines():
            info = studiomod.engine_info(key)
            print(f"{key}: {info['label']} — {info['platforms']} ({info['kind']})")
        return 0

    def _ingest():
        cls = studiomod.ADAPTERS[args.source]
        adapter = cls(args.query) if args.source == "local" else cls()
        # For local, --query is the JSONL path, not a text filter.
        fetch_query = "" if args.source == "local" else args.query
        try:
            signals = adapter.fetch(fetch_query, args.limit)
        except studiomod.AdapterUnavailable as exc:
            print(f"Ingest unavailable: {exc}", file=sys.stderr)
            return None
        path = studiomod.save_signals(signals, args.name)
        print(f"ingested {len(signals)} signals -> {path}")
        return signals

    if args.action == "ingest":
        return 0 if _ingest() is not None else 1

    if args.action in ("score", "brief", "run"):
        signals = None
        if args.action == "run":
            signals = _ingest()
            if signals is None:
                return 1
        else:
            signals = studiomod.load_signals(args.name)
            if not signals:
                print(
                    f"No dataset [{args.name}] — run: studio ingest --name {args.name} …",
                    file=sys.stderr,
                )
                return 1
        graded = studiomod.rank_signals(signals)
        if args.action in ("score", "run"):
            print(
                f"graded {len(graded)} signals (threshold {args.threshold if args.action == 'score' else studiomod.GRADE_THRESHOLD}):"
            )
            top_n = args.top if args.action == "score" else 5
            for s, g in graded[:top_n]:
                flag = "WINNER" if g.grade >= studiomod.GRADE_THRESHOLD else "      "
                print(
                    f"  {flag} {g.grade:5.1f} [{s.platform}/{s.format}] {s.text[:70]!r} cov={g.coverage:.2f}"
                )
        if args.action in ("brief", "run"):
            threshold = (
                args.threshold if args.action == "brief" else studiomod.GRADE_THRESHOLD
            )
            patterns = studiomod.extract_patterns(graded, min_grade=threshold)
            niche = args.niche
            brief = studiomod.generate_brief(
                niche, graded, patterns, engine=args.engine
            )
            bpath = studiomod.save_brief(brief, args.name)
            print(studiomod.render_brief(brief))
            print(f"saved: {bpath}")
        return 0

    return 2


def _outcomes_main(argv) -> int:
    """Subcommand dispatch for: outcomes report|record|sweep|export|sync."""
    import json as _json
    from pathlib import Path as _Path

    ap = argparse.ArgumentParser(
        prog="levi demand outcomes",
        description="DemandPulse outcome ledger — the self-sharpening loop. "
        "Calibration is advisory only; scoring is never auto-changed (O3).",
    )
    sub = ap.add_subparsers(dest="action", required=True)
    sub.add_parser("report", help="plain-text ledger report (read-only)")
    rec = sub.add_parser("record", help="record Chauncey's verdict on a card")
    rec.add_argument("--id", required=True, help="card_id")
    rec.add_argument(
        "--verdict", required=True, choices=("converted", "missed"))
    rec.add_argument("--note", default="")
    sw = sub.add_parser(
        "sweep", help="mark old unresolved cards 'stale' (explicit maintenance)")
    sw.add_argument("--stale-days", type=int, default=30)
    ex = sub.add_parser(
        "export", help="ledger -> .xlsx (one-way view, O4); .csv fallback")
    ex.add_argument("--out", default=None)
    sub.add_parser(
        "sync",
        help="backfill sighting rows for score cards that predate the ledger",
    )
    args = ap.parse_args(argv)

    from levi.demand import outcomes as omod

    if args.action == "report":
        print(omod.render_report())
        return 0
    if args.action == "record":
        row = omod.record_conversion(args.id, args.verdict, note=args.note)
        print(_json.dumps(row, indent=2))
        return 0
    if args.action == "sweep":
        from levi.demand.pulse import DemandPulse

        receipt = omod.sweep_stale(
            DemandPulse().score_cards, stale_days=args.stale_days)
        print(_json.dumps(receipt, indent=2))
        return 0
    if args.action == "export":
        try:
            out = omod.export_xlsx(
                out=_Path(args.out) if args.out else None)
            print(_json.dumps({"exported": str(out)}, indent=2))
        except ImportError:
            out = omod.export_csv(
                out=_Path(args.out) if args.out else None)
            print(_json.dumps(
                {"exported": str(out), "fallback": "csv (openpyxl missing)"},
                indent=2))
        return 0
    # sync
    from levi.demand.pulse import DemandPulse

    dp = DemandPulse()
    seen = omod.sighted_ids()
    added = 0
    for card in dp.score_cards:
        if card.opportunity_id not in seen:
            omod.record_sighting(card)
            added += 1
    print(_json.dumps(
        {"synced": added, "cards": len(dp.score_cards)}, indent=2))
    return 0


def _bridge_main(argv) -> int:
    """Subcommand dispatch for: bridge status|scan|draft|sync-outcomes.

    The DemandPulse -> DDD bridge. Draft-only by law: nothing here
    approves, sends, or touches the outreach gate.
    """
    ap = argparse.ArgumentParser(
        prog="levi.demand bridge",
        description="DemandPulse -> DDD bridge: scored signals auto-draft "
                    "held DDD outreach drafts (draft-only, never sends).",
    )
    ap.add_argument("--ledger", default=None,
                    help="DDD ledger store path (default: DDD_LEDGER_PATH "
                         "or the live scratch store)")
    import json as _json
    sub = ap.add_subparsers(dest="action", required=True)

    sub.add_parser("status", help="bridge status: signals, verdicts, drafts")

    sc = sub.add_parser("scan",
                        help="auto-draft every unbridged pursue-verdict "
                             "live signal")
    sc.add_argument("--limit", type=int, default=None,
                    help="max signals to check (default: all)")

    dr = sub.add_parser("draft", help="draft one signal by id")
    dr.add_argument("--signal-id", required=True)

    sub.add_parser("sync-outcomes",
                   help="mirror bridged drafts' explicit states "
                        "(approved/send-ready/sent) back onto their "
                        "signals — idempotent")

    args = ap.parse_args(argv)
    from levi.demand import bridge as bmod
    from levi.demand import direction as direction_mod
    from levi.demand.pulse import DemandPulse
    from pathlib import Path as _Path

    ledger_path = _Path(args.ledger) if args.ledger else bmod.default_ledger_path()
    ledger = bmod._load_ledger(ledger_path)
    profile = direction_mod.load_profile()
    dp = DemandPulse()

    if args.action == "status":
        print(bmod.render_status(dp, ledger, profile))
        return 0
    if args.action == "scan":
        receipt = bmod.scan_and_draft(dp, ledger, profile,
                                      limit=args.limit)
        print(_json.dumps(receipt, indent=2))
        return 0
    if args.action == "draft":
        sig = next((s for s in dp.live_signals() if s.id == args.signal_id),
                   None)
        if sig is None:
            print(_json.dumps({"error": "unknown signal id",
                               "signal_id": args.signal_id}))
            return 1
        print(_json.dumps(bmod.draft_for_signal(sig, ledger, profile),
                          indent=2))
        return 0
    if args.action == "sync-outcomes":
        print(_json.dumps(bmod.sync_outcomes(ledger), indent=2))
        return 0
    return 2


def _direction_main(argv) -> int:
    """Subcommand dispatch for: direction | coach."""
    from pathlib import Path as _Path

    ap = argparse.ArgumentParser(
        prog="levi.demand direction|coach",
        description="DemandPulse direction layer — life-coach / "
        "personal-refinement sense. The profile is editable data "
        "(JSON); scoring is deterministic and every score carries "
        "its reasons.",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    d = sub.add_parser("direction", help="show the direction profile")
    d.add_argument(
        "--reseed",
        action="store_true",
        help="rewrite the profile JSON from the documented seed snapshot",
    )
    d.add_argument("--path", default=None, help="profile JSON path override")
    d.add_argument(
        "--fit", default=None, help="score this text against the profile"
    )

    c = sub.add_parser("coach", help="render the coach brief from the pulse store")
    c.add_argument("--path", default=None, help="profile JSON path override")
    c.add_argument("--as-of", default=None, help="label for the brief header")
    c.add_argument(
        "--n", type=int, default=20, help="max recent signals to consider"
    )

    args = ap.parse_args(argv)

    from levi.demand import direction as dmod

    prof_path = _Path(args.path) if args.path else dmod.PROFILE_PATH

    if args.command == "direction":
        if args.reseed:
            out = dmod.reseed_profile(prof_path)
            print(f"profile reseeded -> {out}")
            return 0
        try:
            profile = dmod.load_profile(prof_path)
        except (FileNotFoundError, ValueError) as exc:
            print(f"direction: {exc}", file=sys.stderr)
            return 1
        if args.fit:
            print(dmod.direction_fit(args.fit, profile).explain())
            return 0
        print(f"profile: {prof_path}")
        for item in profile.items:
            print(
                f"- [{item.id}] {item.name}  weight={float(item.weight):.2f}"
            )
            print(f"    why: {item.why}")
            print(f"    terms: {', '.join(item.terms)}")
        print("edit the JSON file to change direction — no code change needed.")
        return 0

    # coach
    try:
        profile = dmod.load_profile(prof_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"coach: {exc}", file=sys.stderr)
        return 1
    from levi.demand.pulse import DemandPulse

    dp = DemandPulse()
    n = args.n if isinstance(args.n, int) and args.n >= 1 else 20
    signals = [
        {"id": s.id, "text": s.need, "opportunity_score": None}
        for s in dp.signals[-n:]
    ]
    pursuits = [
        {
            "id": o.id,
            "title": o.title,
            "demand_id": o.demand_id,
            "opportunity_score": o.worth,
        }
        for o in dp.opportunities
    ]
    print(dmod.coach_brief(profile, signals, pursuits, as_of=args.as_of))
    return 0


def main(argv=None) -> int:
    # Feed + alert + workflow + studio subcommands dispatch first; everything
    # else keeps the legacy flags.
    peek = list(sys.argv[1:] if argv is None else argv)
    if peek and peek[0] in _FEED_COMMANDS:
        return _feed_main(peek)
    if peek and peek[0] in _ALERT_COMMANDS:
        return _alerts_main(peek[1:])
    if peek and peek[0] in _WORKFLOW_COMMANDS:
        return _workflows_main(peek[1:])
    if peek and peek[0] in _STUDIO_COMMANDS:
        return _studio_main(peek[1:])
    if peek and peek[0] in _MAINT_COMMANDS:
        return _maint_main(peek)
    if peek and peek[0] in _QUARANTINE_COMMANDS:
        return _quarantine_main(peek)
    if peek and peek[0] in _WATCHER_COMMANDS:
        return _watcher_main(peek[1:])
    if peek and peek[0] in _OPPORTUNITIES_COMMANDS:
        return _opportunities_main(peek[1:])
    if peek and peek[0] in _OUTCOMES_COMMANDS:
        return _outcomes_main(peek[1:])
    if peek and peek[0] in _DIRECTION_COMMANDS:
        return _direction_main(peek)
    if peek and peek[0] in _BRIDGE_COMMANDS:
        return _bridge_main(peek[1:])
    ap = argparse.ArgumentParser(
        prog="levi.demand",
        description="LEVI DemandPulse — demand signals + opportunity scoring "
        "(mirrors `levi demand`)",
    )
    ap.add_argument("--scan", default=None, help="scan free text into a signal")
    ap.add_argument("--segment", default="general")
    ap.add_argument("--title", default=None, help="score opportunity title")
    ap.add_argument("--demand-score", dest="demand_score", type=float, default=0.6)
    ap.add_argument("--serviceability", type=float, default=0.6)
    ap.add_argument("--cost", type=float, default=0.2)
    ap.add_argument(
        "--five-factor", action="store_true", help="five-factor composite model"
    )
    ap.add_argument("--ff-demand", type=float, default=None)
    ap.add_argument("--ff-market", type=float, default=None)
    ap.add_argument("--ff-gap", type=float, default=None)
    ap.add_argument("--ff-velocity", type=float, default=None)
    ap.add_argument("--ff-feasibility", type=float, default=None)
    ap.add_argument(
        "--ff-basis", default=None, help="REQUIRED: why these scores were assigned"
    )
    ap.add_argument(
        "--ff-weights", default=None, help="e.g. demand=.3,market_size=.25,..."
    )
    ap.add_argument("--ff-threshold", type=float, default=75.0)
    ap.set_defaults(func=cmd_run)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
