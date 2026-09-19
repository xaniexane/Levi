"""``levi automation`` CLI: browser plans, primitive registry, safety summary.

Plans and descriptions only — nothing here executes automation.
"""

from __future__ import annotations

import argparse

from .browser import emit_termux_helper, format_plan, plan_browser_job
from .primitives import list_primitives, match_nl


def register_automation_parser(sub) -> None:
    ap = sub.add_parser("automation", help="Automation plans + primitive registry")
    cmds = ap.add_subparsers(dest="automation_cmd")

    plan_p = cmds.add_parser(
        "plan", help="build a browser-automation plan (no execution)"
    )
    plan_p.add_argument(
        "--goal", required=True, help="what the automation should achieve"
    )
    plan_p.add_argument("--url", default="about:blank", help="target URL")
    plan_p.add_argument(
        "--field", action="append", default=[], help="form field (repeatable)"
    )

    emit_p = cmds.add_parser("emit", help="emit the Termux helper for a plan")
    emit_p.add_argument("--goal", required=True, help="plan goal")
    emit_p.add_argument("--url", default="about:blank", help="target URL")

    prim_p = cmds.add_parser("primitives", help="list automation primitives")
    prim_p.add_argument("--band", choices=["green", "yellow", "red"], default=None)

    match_p = cmds.add_parser("match", help="map a phrase to primitives")
    match_p.add_argument("text", help="natural-language request")

    cmds.add_parser("safety", help="print the automation safety summary")

    bots_p = cmds.add_parser("minions", help="list the LEVI automation minion catalog")
    bots_p.add_argument("--category", default=None, help="filter by category")
    bots_p.add_argument("--trigger", default=None, help="filter by trigger text")
    bots_p.add_argument("--hitl", default=None, help="filter by HITL type")

    bot_p = cmds.add_parser("minion", help="show one minion's detail")
    bot_p.add_argument("minion_id", help="minion id (see `minions`)")

    dry_p = cmds.add_parser("dry-run", help="preview a minion run (never executes)")
    dry_p.add_argument("minion_id", help="minion id (see `minions`)")
    dry_p.add_argument("--summary", default="", help="event summary text")
    dry_p.add_argument(
        "--payload",
        default="{}",
        help='event payload as JSON, e.g. \'{"time": "06:45"}\'',
    )

    run_p = cmds.add_parser(
        "run", help="run a minion (dry-run default; --live executes for real)"
    )
    run_p.add_argument("minion_id", help="minion id (see `minions`)")
    run_p.add_argument("--summary", default="", help="event summary text")
    run_p.add_argument(
        "--payload",
        default="{}",
        help='event payload as JSON, e.g. \'{"time": "06:45"}\'',
    )
    run_p.add_argument(
        "--live",
        action="store_true",
        help="execute for real: prints the preview, asks explicit permission, "
        "then runs every step through its permission gate",
    )

    cmds.add_parser("routines", help="list recorded routines")
    rec_p = cmds.add_parser(
        "record", help="record a routine from a harvested session ('watch me once')"
    )
    rec_p.add_argument("--name", default=None, help="routine name")
    rec_p.add_argument(
        "--from-session", required=True, help="session id to distill the routine from"
    )
    play_p = cmds.add_parser("play", help="play a routine back (permission-gated)")
    play_p.add_argument("routine_id", help="routine id (see `routines`)")
    play_p.add_argument(
        "--live",
        action="store_true",
        help="execute steps for real (still permission-gated; runs through the automation executor)",
    )
    play_p.add_argument(
        "--yes",
        action="store_true",
        help="approve every permission gate (only for safe dry-runs you fully trust)",
    )


def _cmd_routines(args: argparse.Namespace) -> int:
    from .routines import list_routines

    routines = list_routines()
    for r in routines:
        print(
            f"{r.id} | {r.name} | {len(r.steps)} step(s) | "
            f"played {r.playback_count}x | source: {r.source}"
        )
    print(f"{len(routines)} routine(s)")
    return 0


def _cmd_record(args: argparse.Namespace) -> int:
    from .routines import record_from_session

    try:
        routine = record_from_session(args.from_session, name=args.name)
    except ValueError as exc:
        print(f"cannot record: {exc}")
        return 1
    print(f"recorded routine {routine.id} ({len(routine.steps)} step(s))")
    for step in routine.steps:
        print(f"  - {step.label} [{step.minion_id or 'note'}]")
    print("Every step will hit a permission gate at playback.")
    return 0


def _console_responder(request):
    """Interactive yes/no gate responder. Non-tty stdin denies (fail-closed)."""
    import sys

    try:
        if not sys.stdin.isatty():
            return {"decision": "denied", "reason": "non-interactive stdin"}
        answer = input(
            f"[gate:{request.kind.value}] {request.prompt} — approve? [y/N] "
        )
    except (EOFError, KeyboardInterrupt):
        return {"decision": "denied", "reason": "no answer"}
    if answer.strip().lower() in ("y", "yes"):
        return {"decision": "approved"}
    return {"decision": "denied", "reason": "user declined at the console"}


def _cmd_play(args: argparse.Namespace) -> int:
    from .hitl import auto_approve
    from .routines import play_routine

    responder = auto_approve if args.yes else _console_responder
    try:
        run = play_routine(args.routine_id, responder=responder, dry_run=not args.live)
    except KeyError as exc:
        print(exc)
        return 1
    for note in run.step_notes:
        print(note)
    print(run.note)
    return 0 if run.ok else 2


def cmd_automation(args: argparse.Namespace) -> int:
    cmd = getattr(args, "automation_cmd", None) or "safety"

    if cmd == "plan":
        plan = plan_browser_job(args.goal, url=args.url, fields=args.field)
        print(format_plan(plan))
        return 0

    if cmd == "minions":
        return _cmd_minions(args)
    if cmd == "minion":
        return _cmd_minion(args)
    if cmd == "dry-run":
        return _cmd_dry_run(args)
    if cmd == "run":
        return _cmd_run(args)
    if cmd == "routines":
        return _cmd_routines(args)
    if cmd == "record":
        return _cmd_record(args)
    if cmd == "play":
        return _cmd_play(args)

    if cmd == "emit":
        plan = plan_browser_job(args.goal, url=args.url)
        print(emit_termux_helper(plan))
        return 0

    if cmd == "primitives":
        for p in list_primitives(args.band):
            hitl = " HITL" if p.hitl_required else ""
            print(f"{p.id} [{p.band}]{hitl} {p.name} — {p.description}")
        return 0

    if cmd == "match":
        found = match_nl(args.text)
        if not found:
            print("no primitive match")
            return 0
        for p in found:
            hitl = " HITL" if p.hitl_required else ""
            print(f"{p.id} [{p.band}]{hitl} {p.name}")
        return 0

    print(
        "LEVI automation: plans only, never silent execution.\n"
        "Green = user-initiated. Yellow = HITL each run. Red = full HITL,\n"
        "and login/captcha/2FA/payments/banking stay manual — always.\n"
        "See docs/AUTOMATION_SAFETY.md."
    )
    return 0


# ---------------------------------------------------------------------------
# Minion catalog commands (LEVI-native automation minions)
# ---------------------------------------------------------------------------


def _cmd_minions(args: argparse.Namespace) -> int:
    from .minions import MINIONS, by_category, search

    minions = MINIONS
    if args.category:
        minions = by_category(args.category)
    if args.trigger:
        minions = [b for b in search(args.trigger) if b in minions]
    if args.hitl:
        want = args.hitl.strip().lower()
        minions = [b for b in minions if b.hitl_type.strip().lower() == want]
    for b in minions:
        flag = " [INCOMPLETE]" if b.incomplete else ""
        print(f"{b.id} | {b.category} / {b.subcategory}{flag}")
        print(
            f"    trigger: {b.trigger} | condition: {b.condition} | HITL: {b.hitl_type}"
        )
    print(f"{len(minions)} minion(s)")
    return 0


def _cmd_minion(args: argparse.Namespace) -> int:
    from .minions import MINIONS, find_minion

    minion = find_minion(MINIONS, args.minion_id)
    if minion is None:
        print(f"unknown minion id: {args.minion_id}")
        return 1
    tag = " [INCOMPLETE — intake row was truncated]" if minion.incomplete else ""
    print(f"{minion.id}{tag}")
    for label, value in (
        ("category", minion.category),
        ("subcategory", minion.subcategory),
        ("trigger", minion.trigger),
        ("condition", minion.condition),
        ("android", minion.android_tool),
        ("windows", minion.windows_tool),
        ("mac", minion.mac_tool),
        ("chrome ext", minion.chrome_extension),
        ("bridge", minion.bridge),
        ("usb auto-launch", minion.usb_auto_launch),
        ("HITL type", minion.hitl_type),
        ("rite", minion.example_rite),
        ("notes", minion.notes),
        ("origin", minion.origin),
    ):
        print(f"  {label}: {value}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    """Run one minion. Dry-run default; --live executes for real.

    --live prints the preview first and requires explicit permission,
    then every step still passes its own permission gate. A denied gate
    stops the run fail-closed before anything executes.
    """
    import json
    import sys

    from .minions import MINIONS, find_minion
    from .engine import TriggerEvent, dry_run, run_minion

    try:
        payload = json.loads(args.payload)
    except json.JSONDecodeError as exc:
        print(f"bad --payload JSON: {exc}")
        return 1
    minion = find_minion(MINIONS, args.minion_id)
    if minion is None:
        print(f"unknown minion id: {args.minion_id}")
        return 1
    event = TriggerEvent(
        kind="manual", summary=args.summary or args.minion_id, payload=payload
    )
    if not args.live:
        print(dry_run(args.minion_id, event, MINIONS).render())
        return 0
    # --live: preview first, explicit permission, then execute with real gates.
    print("PREVIEW (dry-run):")
    print(dry_run(args.minion_id, event, MINIONS).render())
    try:
        answer = (
            input(
                "Execute this minion LIVE, with a permission gate on every step? [y/N] "
            )
            if sys.stdin.isatty()
            else ""
        )
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if answer.strip().lower() not in ("y", "yes"):
        print("not executed — no permission given")
        return 2
    receipt = run_minion(minion, event, responder=_console_responder, dry_run=False)
    print(receipt.render())
    return 0 if receipt.ok else 2


def _cmd_dry_run(args: argparse.Namespace) -> int:
    import json

    from .minions import MINIONS
    from .engine import TriggerEvent, dry_run

    try:
        payload = json.loads(args.payload)
    except json.JSONDecodeError as exc:
        print(f"bad --payload JSON: {exc}")
        return 1
    try:
        receipt = dry_run(
            args.minion_id,
            TriggerEvent(
                kind="manual", summary=args.summary or args.minion_id, payload=payload
            ),
            MINIONS,
        )
    except KeyError as exc:
        print(exc)
        return 1
    print(receipt.render())
    return 0


# ---------------------------------------------------------------------------
# ``levi automate`` — IFTTT-style workflow creator
# ---------------------------------------------------------------------------


def register_automate_parser(sub) -> None:
    ap = sub.add_parser(
        "automate", help="IFTTT-style workflow creator: when THIS, do THAT"
    )
    cmds = ap.add_subparsers(dest="automate_cmd")

    c_p = cmds.add_parser("create", help="build a workflow (guided or with flags)")
    c_p.add_argument("--name", default=None, help="workflow name")
    c_p.add_argument(
        "--trigger",
        choices=["manual", "schedule", "webhook-in"],
        default=None,
        help="trigger type",
    )
    c_p.add_argument("--cron", default=None, help="cron schedule (schedule trigger)")
    c_p.add_argument("--path", default=None, help="webhook path (webhook-in trigger)")
    c_p.add_argument(
        "--action",
        action="append",
        default=[],
        help='repeatable: KIND:LABEL[;key=value;...] e.g. "minion:Digest;minion_id=productivity-email-digest-01"',
    )
    c_p.add_argument("--condition", default=None, help="condition expression")
    c_p.add_argument("--yes", action="store_true", help="skip the confirm prompt")

    cmds.add_parser("list", help="list saved workflows")

    s_p = cmds.add_parser("show", help="show a workflow's mermaid + steps")
    s_p.add_argument("flow_id", help="workflow id (see `list`)")

    r_p = cmds.add_parser(
        "run", help="run a workflow (dry-run by default; --live executes)"
    )
    r_p.add_argument("flow_id", help="workflow id (see `list`)")
    r_p.add_argument(
        "--live",
        action="store_true",
        help="execute for real: dry-run preview first, explicit permission, "
        "then every minion node passes its own gate",
    )

    d_p = cmds.add_parser("delete", help="delete a saved workflow")
    d_p.add_argument("flow_id", help="workflow id (see `list`)")
    d_p.add_argument("--yes", action="store_true", help="skip the confirm prompt")


def _parse_action_arg(text: str) -> dict:
    """Parse 'KIND:LABEL[;key=value;...]' into an action dict."""
    parts = text.split(";")
    head = parts[0]
    if ":" not in head:
        raise ValueError(f"bad --action {text!r}: want KIND:LABEL")
    kind, _, label = head.partition(":")
    kind, label = kind.strip(), label.strip()
    if not kind or not label:
        raise ValueError(f"bad --action {text!r}: want KIND:LABEL")
    config = {}
    for chunk in parts[1:]:
        if "=" not in chunk:
            raise ValueError(f"bad --action {text!r}: config chunk {chunk!r}")
        key, _, value = chunk.partition("=")
        config[key.strip()] = value.strip()
    return {"kind": kind, "label": label, "config": config}


def _prompt(text: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    try:
        answer = input(f"{text}{hint}: ").strip()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    return answer or default


def _prompt_actions_interactive() -> list:
    """Loop: kind + label + key config values until the user is done."""
    from .creator import ACTION_KINDS

    print(f"action kinds: {', '.join(ACTION_KINDS)}")
    actions = []
    while True:
        kind = _prompt("action kind (blank to finish)")
        if not kind:
            break
        label = _prompt("action label")
        config = {}
        print("config key=value pairs (blank key to finish this action):")
        while True:
            key = _prompt("  key")
            if not key:
                break
            config[key] = _prompt("  value")
        actions.append({"kind": kind, "label": label, "config": config})
        print(f"  added [{kind}] {label}")
    return actions


def _cmd_automate_create(args: argparse.Namespace) -> int:
    import sys

    from .creator import (
        FlowBuildError,
        build_workflow,
        render_preview,
        save_workflow,
    )

    interactive = (
        args.name is None
        and args.trigger is None
        and not args.action
        and args.condition is None
        and sys.stdin.isatty()
    )

    if interactive:
        ttype = _prompt("trigger type (manual/schedule/webhook-in)", "manual")
        trigger_spec = {"trigger_type": ttype or "manual"}
        if trigger_spec["trigger_type"] == "schedule":
            trigger_spec["cron"] = _prompt("cron schedule", "0 9 * * *")
        elif trigger_spec["trigger_type"] == "webhook-in":
            trigger_spec["path"] = _prompt("webhook path", "/hook")
        actions = _prompt_actions_interactive()
        condition = _prompt("condition expression (blank for none)")
        name = _prompt("workflow name", "my-workflow")
    else:
        if not args.name or not args.trigger or not args.action:
            print(
                "non-interactive create needs --name, --trigger, and --action; "
                "or run with a tty for the guided flow"
            )
            return 1
        trigger_spec = {"trigger_type": args.trigger}
        if args.cron:
            trigger_spec["cron"] = args.cron
        if args.path:
            trigger_spec["path"] = args.path
        try:
            actions = [_parse_action_arg(a) for a in args.action]
        except ValueError as exc:
            print(exc)
            return 1
        condition = args.condition
        name = args.name

    try:
        flow = build_workflow(name, trigger_spec, actions, condition=condition or None)
    except FlowBuildError as exc:
        print(f"cannot build workflow: {exc}")
        return 1

    if not args.yes and sys.stdin.isatty():
        print(render_preview(flow))
        if _prompt("save this workflow? (y/N)", "N").lower() not in ("y", "yes"):
            print("not saved")
            return 2
    try:
        path = save_workflow(flow)
    except FlowBuildError as exc:
        print(f"cannot save workflow: {exc}")
        return 1
    print(f"saved workflow {flow['id']} -> {path}")
    print(render_preview(flow))
    return 0


def _cmd_automate_list(args: argparse.Namespace) -> int:
    from .flows import list_flows

    flows_list = list_flows()
    for f in flows_list:
        print(f"{f['id']} | {f['name']} | {f['nodes']} node(s)")
    print(f"{len(flows_list)} workflow(s)")
    return 0


def _cmd_automate_show(args: argparse.Namespace) -> int:
    from .creator import render_preview
    from .flows import FlowError, load_flow

    try:
        flow = load_flow(args.flow_id)
    except FlowError as exc:
        print(exc)
        return 1
    print(render_preview(flow))
    return 0


def _cmd_automate_run(args: argparse.Namespace) -> int:
    import sys

    from .flows import FlowError, load_flow, run_flow
    from .hitl import auto_approve

    try:
        flow = load_flow(args.flow_id)
    except FlowError as exc:
        print(exc)
        return 1
    if not args.live:
        receipt = run_flow(flow, responder=auto_approve, dry_run=True)
        print(receipt.render())
        return 0 if receipt.ok else 2
    # --live: dry-run preview first, explicit permission, then live.
    preview = run_flow(flow, responder=auto_approve, dry_run=True)
    print("PREVIEW (dry-run):")
    print(preview.render())
    try:
        answer = (
            input("Execute this workflow LIVE? [y/N] ") if sys.stdin.isatty() else ""
        )
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if answer.strip().lower() not in ("y", "yes"):
        print("not executed — no permission given")
        return 2
    receipt = run_flow(flow, responder=_console_responder, dry_run=False)
    print(receipt.render())
    return 0 if receipt.ok else 2


def _cmd_automate_delete(args: argparse.Namespace) -> int:
    import sys

    from .flows import delete_flow

    if not args.yes and sys.stdin.isatty():
        if _prompt(f"delete workflow {args.flow_id!r}? (y/N)", "N").lower() not in (
            "y",
            "yes",
        ):
            print("not deleted")
            return 2
    if delete_flow(args.flow_id):
        print(f"deleted {args.flow_id}")
        return 0
    print(f"unknown workflow id: {args.flow_id}")
    return 1


def cmd_automate(args: argparse.Namespace) -> int:
    cmd = getattr(args, "automate_cmd", None) or "list"
    if cmd == "create":
        return _cmd_automate_create(args)
    if cmd == "list":
        return _cmd_automate_list(args)
    if cmd == "show":
        return _cmd_automate_show(args)
    if cmd == "run":
        return _cmd_automate_run(args)
    if cmd == "delete":
        return _cmd_automate_delete(args)
    print(f"unknown automate command: {cmd}")
    return 1
