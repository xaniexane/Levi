"""CLI for the engagement layer: ``levi engage ...``.

Surveys + campaigns, all local. Opt-in required before anything engages
the user; every question skippable; frequency user-controlled.
"""

from __future__ import annotations

import argparse
import json

from . import campaigns as _c
from . import surveys as _s
from . import voting as _v
from .campaigns import view_campaign
from .prefs import FREQUENCIES, Prefs, get_prefs, save_prefs
from .store import EngagementStore
from .surveys import run_interactive, take_survey
from .voting import VERBS, cast_favorite, cast_proposal, run_ballot_interactive


def register_engage_parser(sub) -> None:
    eg = sub.add_parser("engage", help="surveys + campaigns (opt-in, local, skippable)")
    cmds = eg.add_subparsers(dest="engage_cmd")

    cmds.add_parser("opt-in", help="opt in to surveys + campaigns")
    cmds.add_parser("opt-out", help="opt out entirely (prefs kept, nothing prompts)")
    f = cmds.add_parser("frequency", help="how often to surface new items")
    f.add_argument("level", choices=FREQUENCIES, help="off | daily | weekly")
    cmds.add_parser("prefs", help="show current engagement prefs")
    cmds.add_parser("list", help="surveys + campaigns and their status")
    t = cmds.add_parser("take", help="take a survey interactively")
    t.add_argument("survey_id", help="survey id (see: engage list)")
    a = cmds.add_parser("answer", help="answer a survey non-interactively")
    a.add_argument("survey_id", help="survey id")
    a.add_argument("--json", required=True, help='answers as JSON, e.g. \'{"q1":"2"}\'')
    c = cmds.add_parser("campaign", help="view a campaign")
    c.add_argument("campaign_id", help="campaign id (see: engage list)")
    d = cmds.add_parser("dismiss", help="dismiss a campaign for good")
    d.add_argument("campaign_id", help="campaign id")
    cmds.add_parser("stats", help="aggregate engagement counts (metadata only)")
    cmds.add_parser("ballots", help="list ballots (tagged ai/si/both)")
    v = cmds.add_parser("vote", help="vote on a ballot")
    v.add_argument("ballot_id", help="ballot id (see: engage ballots)")
    v.add_argument("--pick", default=None, help="non-interactive pick (option or number)")
    p = cmds.add_parser("propose", help="vote add/remove/change/integrate + text")
    p.add_argument("verb", choices=VERBS, help="add | remove | change | integrate")
    p.add_argument("text", nargs="+", help="the proposal")
    cmds.add_parser("results", help="per-track vote results (aggregate counts)")
    cmds.add_parser("proposals", help="proposals ranked by vote weight + request ids")


def chat_handle(line: str) -> str:
    """Companion-chat handler for /engage. Returns text to print."""
    parts = line.strip().split()
    store = EngagementStore()
    prefs = get_prefs()
    if len(parts) == 1 or parts[1] == "list":
        if not prefs.opted_in:
            return "engagement is opt-in — run `levi engage opt-in` (or /engage opt-in) to join."
        out = ["surveys:"]
        done = set(store.completed_surveys())
        for sid, s in _s.SURVEYS.items():
            out.append(f"  {sid} [{'done' if sid in done else 'new'}] [{s.track}] {s.title}")
        out.append("ballots:")
        for bid, b in _v.BALLOTS.items():
            cur = store.current_vote(bid)
            mark = f"voted: {cur[:30]}" if cur else "open"
            out.append(f"  {bid} [{b.track}] [{mark}] {b.title}")
        return "\n".join(out)
    if parts[1] == "opt-in":
        prefs.opted_in = True
        save_prefs(prefs)
        return "opted in — surveys, campaigns, and ballots may surface per your frequency."
    if parts[1] == "opt-out":
        prefs.opted_in = False
        save_prefs(prefs)
        return "opted out — nothing will prompt you."
    if parts[1] == "vote" and len(parts) > 2:
        if not prefs.opted_in:
            return "opt-in first: /engage opt-in"
        ballot = _v.get_ballot(parts[2])
        if not ballot:
            return f"unknown ballot: {parts[2]}"
        result = run_ballot_interactive(ballot, store)
        return "vote recorded." if result.get("ok") else "backed out — nothing recorded."
    if parts[1] == "results":
        return _render_results(store)
    return "usage: /engage [list|opt-in|opt-out|vote <id>|results]"


def _render_results(store: EngagementStore) -> str:
    tallies = store.vote_tallies()
    if not tallies:
        return "no votes yet — ballots are open (see: engage ballots)."
    lines = ["vote results (aggregate counts, per track):"]
    for track in ("ai", "si", "both"):
        track_ballots = [b for b in _v.BALLOTS.values() if b.track == track]
        if not track_ballots:
            continue
        lines.append(f"  [{track}]")
        for b in track_ballots:
            counts = tallies.get(b.id, {})
            if not counts:
                lines.append(f"    {b.id}: no votes yet")
                continue
            inner = ", ".join(f"{opt[:28]}×{n}" for opt, n in sorted(counts.items()))
            lines.append(f"    {b.id}: {inner}")
    return "\n".join(lines)


def _need_opt_in(prefs: Prefs) -> bool:
    if not prefs.opted_in:
        print("not opted in — run `levi engage opt-in` first (your call, always).")
        return True
    return False


def cmd_engage(args) -> None:
    """Engagement: surveys + campaigns."""
    cmd = getattr(args, "engage_cmd", None)
    store = EngagementStore()
    prefs = get_prefs()

    if cmd == "opt-in":
        prefs.opted_in = True
        save_prefs(prefs)
        print("opted in. surveys + campaigns may surface per your frequency.")
        print("opt out anytime: `levi engage opt-out`. answers stay on this machine.")
        return
    if cmd == "opt-out":
        prefs.opted_in = False
        save_prefs(prefs)
        print("opted out. nothing will prompt you. your stored answers stay local.")
        return
    if cmd == "frequency":
        prefs.frequency = args.level
        save_prefs(prefs)
        print(f"frequency: {args.level}")
        return
    if cmd == "prefs":
        print(f"opted_in:  {prefs.opted_in}")
        print(f"frequency: {prefs.frequency}")
        print(f"last_prompt: {prefs.last_prompt or '(never)'}")
        return

    if _need_opt_in(prefs):
        return

    if cmd == "list":
        done = set(store.completed_surveys())
        dismissed = set(store.dismissed_campaigns())
        print("surveys:")
        for sid, s in _s.SURVEYS.items():
            mark = "done" if sid in done else "new"
            print(f"  {sid:14} [{mark}] [{s.track}] {s.title} — {s.tagline}")
        print("campaigns:")
        for cid, c in _c.CAMPAIGNS.items():
            mark = "dismissed" if cid in dismissed else "new"
            print(f"  {cid:14} [{mark}] {c.title} — {c.tagline}")
        return
    if cmd == "take":
        survey = _s.get_survey(args.survey_id)
        if not survey:
            print(f"unknown survey: {args.survey_id} (see: engage list)")
            return
        run_interactive(survey, store)
        return
    if cmd == "answer":
        survey = _s.get_survey(args.survey_id)
        if not survey:
            print(f"unknown survey: {args.survey_id} (see: engage list)")
            return
        try:
            answers = json.loads(args.json)
        except (json.JSONDecodeError, ValueError):
            print("bad --json (must be an object)")
            return
        if not isinstance(answers, dict):
            print("bad --json (must be an object)")
            return
        result = take_survey(survey, {str(k): str(v) for k, v in answers.items()}, store)
        print(f"recorded: {result['answered']}/{result['total']} answered, {result['skipped']} skipped")
        print(survey.outro)
        return
    if cmd == "campaign":
        campaign = _c.get_campaign(args.campaign_id)
        if not campaign:
            print(f"unknown campaign: {args.campaign_id} (see: engage list)")
            return
        view_campaign(campaign, store)
        return
    if cmd == "dismiss":
        store.record_campaign(args.campaign_id, seen=0, completed=False)
        print(f"dismissed {args.campaign_id} — it won't surface again.")
        return
    if cmd == "stats":
        tallies = store.aggregate_tallies()
        if not tallies:
            print("no engagement activity yet (answers stay local; this shows counts only).")
            return
        print("engagement tallies (aggregate counts, never individual answers):")
        for key, counts in sorted(tallies.items()):
            inner = ", ".join(f"{opt}×{n}" for opt, n in sorted(counts.items()))
            print(f"  {key}: {inner}")
        return
    if cmd == "ballots":
        for bid, b in _v.BALLOTS.items():
            cur = store.current_vote(bid)
            mark = f"voted: {cur[:30]}" if cur else "open"
            print(f"  {bid:14} [{b.track:4}] [{b.kind:9}] [{mark}] {b.title} — {b.tagline}")
        return
    if cmd == "vote":
        ballot = _v.get_ballot(args.ballot_id)
        if not ballot:
            print(f"unknown ballot: {args.ballot_id} (see: engage ballots)")
            return
        if ballot.kind == "proposals":
            print("ship-it takes proposals — use: engage propose <add|remove|change|integrate> <text>")
            return
        if args.pick is not None:
            result = cast_favorite(ballot, args.pick, store)
            print("vote counted." if result.get("ok") else f"  {result.get('error')}")
            return
        run_ballot_interactive(ballot, store)
        return
    if cmd == "propose":
        result = cast_proposal(args.verb, " ".join(args.text), store)
        if result.get("ok"):
            print(f"proposal logged (weight ×{result['weight']}, request #{result['request_id']}).")
            print("weighted input on the request box — open for triage, never auto-built.")
        else:
            print(f"  {result.get('error')}")
        return
    if cmd == "results":
        print(_render_results(store))
        return
    if cmd == "proposals":
        props = store.proposals()
        if not props:
            print("no proposals yet — vote one: engage propose <verb> <text>")
            return
        print("proposals by vote weight (request box ids):")
        for p in props:
            print(f"  ×{p['weight']}  [request #{p['request_id']}] {p['proposal']}")
        return
    print("usage: levi engage opt-in|opt-out|frequency|prefs|list|take|answer|campaign|dismiss|stats|ballots|vote|propose|results|proposals")
