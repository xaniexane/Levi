"""``python -m levi.twins`` — the Twin Lattice CLI.

Usage:
    python -m levi.twins ensure              # create all pairs (agents+daemon+6 shells)
    python -m levi.twins status              # lattice overview
    python -m levi.twins list [kind]         # list twins
    python -m levi.twins heartbeat <twin-id> # mark alive, optional --state JSON
    python -m levi.twins promote <bg-twin-id>
    python -m levi.twins collect              # ingest shell hook drop files
    python -m levi.twins hook --slot N        # print the shell hook script
    python -m levi.twins triads               # per-agent triads
    python -m levi.twins ones                 # the three Ones
    python -m levi.twins seed [--show]        # creator seed status
    python -m levi.twins converge             # rebuild the truth from the seed
"""

from __future__ import annotations

import argparse
import json
import sys

from levi.twins import agents as twin_agents
from levi.twins import convergence as twin_convergence
from levi.twins import daemons as twin_daemons
from levi.twins import evolution as twin_evolution
from levi.twins import shells as twin_shells
from levi.twins import triads as twin_triads
from levi.twins.lattice import TwinLattice


def _cmd_ensure(_args: argparse.Namespace) -> int:
    lat = TwinLattice()
    a = twin_agents.ensure_agent_twins(lat)
    d = twin_daemons.ensure_daemon_twins(lat)
    s = twin_shells.ensure_shell_twins(lat)
    t = twin_triads.ensure_triads(lat)
    o = twin_convergence.ensure_ones(lat)
    n_agents = sum(len(v) for v in a.values())
    print(f"agents: {n_agents} twins ({len(a)} pairs)")
    print(f"daemons: {len(d)} twins (1 pair)")
    print(f"shells: {len(s)} twins (3 pairs)")
    print(f"triads: {len(t)} bound (agent+daemon+os-shell each)")
    print(f"ones: {len(o)} (all-in-one agent/daemon/os-shell)")
    return 0


def _fmt_age(tw) -> str:
    age = tw.age_since_heartbeat()
    if age < 60:
        return f"{age:.0f}s"
    if age < 3600:
        return f"{age / 60:.0f}m"
    return f"{age / 3600:.1f}h"


def _cmd_status(_args: argparse.Namespace) -> int:
    lat = TwinLattice()
    counts = lat.counts()
    total = sum(counts.values())
    print(
        f"twins: {total}  " + "  ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    )
    stale = lat.stale(300.0)
    if stale:
        print(f"stale >5m: {len(stale)}")
        for tw in stale[:10]:
            print(f"  ! {tw.twin_id} ({_fmt_age(tw)})")
    else:
        print("stale >5m: 0")
    # failover sweep for daemons + shell pairs
    events = []
    ev = twin_daemons.check_daemon_failover(lat)
    if ev:
        events.append(ev)
    for fg_slot, _ in twin_shells.SHELL_PAIRS:
        ev = twin_shells.check_shell_failover(lat, fg_slot)
        if ev:
            events.append(ev)
    for ev in events:
        print(f"failover: {ev['promoted']} promoted (was {ev['demoted']})")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    lat = TwinLattice()
    twins = lat.list(kind=args.kind)
    for tw in twins:
        state_keys = ",".join(sorted(tw.state.keys())[:4])
        print(
            f"{tw.twin_id:28s} [{tw.side}] age={_fmt_age(tw):>6s} "
            f"state={{{state_keys}}}"
        )
    return 0


def _cmd_heartbeat(args: argparse.Namespace) -> int:
    lat = TwinLattice()
    state = json.loads(args.state) if args.state else None
    try:
        tw = lat.heartbeat(args.twin_id, state)
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"ok: {tw.twin_id} age=0s")
    return 0


def _cmd_promote(args: argparse.Namespace) -> int:
    lat = TwinLattice()
    try:
        ev = lat.promote(args.twin_id, args.threshold)
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"promoted {ev['promoted']} (demoted {ev['demoted']})")
    return 0


def _cmd_collect(_args: argparse.Namespace) -> int:
    lat = TwinLattice()
    n = twin_shells.collect_drops(lat)
    print(f"ingested {n} shell drop(s)")
    return 0


def _cmd_hook(args: argparse.Namespace) -> int:
    if args.auto:
        print(twin_shells.hook_script_auto())
    else:
        print(twin_shells.hook_script(args.slot))
    return 0


def _cmd_triads(_args: argparse.Namespace) -> int:
    lat = TwinLattice()
    triads = twin_triads.ensure_triads(lat)
    for agent, parts in sorted(triads.items()):
        counts = {k: len(v) for k, v in parts.items()}
        print(
            f"{agent:10s} agent={counts['agent']} "
            f"daemon={counts['daemon']} shell={counts['shell']}"
        )
    return 0


def _cmd_ones(_args: argparse.Namespace) -> int:
    lat = TwinLattice()
    ones = twin_convergence.ensure_ones(lat)
    for _kind, tw in sorted(ones.items()):
        n = len(tw.state.get("members", []))
        print(f"{tw.twin_id:20s} members={n}")
    return 0


def _cmd_seed(args: argparse.Namespace) -> int:
    lat = TwinLattice()
    seed = twin_convergence.ensure_seed(lat)
    path = twin_convergence.seed_path(lat)
    print(f"seed: {path} (0600)")
    print(f"fingerprint: {twin_convergence.seed_fingerprint(seed)}")
    if args.show:
        print(f"seed: {seed}")
        print(
            "warning: the seed reproduces the true arrangement — "
            "guard it like the creator's key, because it is."
        )
    else:
        print("pass --show to reveal (creator only)")
    return 0


def _cmd_converge(args: argparse.Namespace) -> int:
    lat = TwinLattice()
    if args.verify_only:
        ok = twin_convergence.verify_camouflage(lat)
        print(f"seal verifies: {ok}")
        return 0 if ok else 1
    result = twin_convergence.converge(lat)
    for kind in ("agent", "daemon", "shell"):
        print(f"{result['ones'][kind]:20s} members={result['member_counts'][kind]}")
    print(f"sealed: {result['sealed']} (fp {result['seed_fp']})")
    return 0


def _cmd_prune(args: argparse.Namespace) -> int:
    lat = TwinLattice()
    n = twin_shells.prune_external(lat, args.older_than)
    print(f"pruned {n} external shell twin(s) older than {args.older_than:.0f}s")
    return 0


def _cmd_add_agent(args: argparse.Namespace) -> int:
    lat = TwinLattice()
    try:
        triad = twin_triads.register_agent(lat, args.name)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    counts = {k: len(v) for k, v in triad.items()}
    print(
        f"bound {args.name}: agent={counts['agent']} "
        f"daemon={counts['daemon']} shell={counts['shell']}"
    )
    return 0


def _cmd_evolve(args: argparse.Namespace) -> int:
    lat = TwinLattice()
    ops = tuple(o.strip() for o in args.ops.split(",") if o.strip())
    if not ops:
        ops = twin_evolution.OPS
    try:
        report = twin_evolution.evolve(lat, ops=ops)
    except twin_evolution.LatticeDoesNotAddUp as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for r in report["ops"]:
        print(f"[{r['op']}] mandella({r['domain']}): {r['mandella']}")
        print(f"  echo taken: {r['echo_taken']}")
        print(f"  {r['detail']}  genome_proposals={r['proposals']}")
    print(
        f"generation={report['generation']} "
        f"version=v{report['version']} "
        f"sealed={report['sealed']} "
        f"genome_proposals={report['proposals']}"
    )
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m levi.twins")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ensure", help="create all twin pairs")
    sub.add_parser("status", help="lattice overview + failover sweep")

    p_list = sub.add_parser("list", help="list twins")
    p_list.add_argument("kind", nargs="?", default=None, help="agent|daemon|shell")

    p_hb = sub.add_parser("heartbeat", help="mark a twin alive")
    p_hb.add_argument("twin_id")
    p_hb.add_argument("--state", default=None, help="JSON state update")

    p_prom = sub.add_parser("promote", help="promote a bg twin to fg")
    p_prom.add_argument("twin_id")
    p_prom.add_argument("--threshold", type=float, default=300.0)

    sub.add_parser("collect", help="ingest shell hook drop files")

    p_hook = sub.add_parser("hook", help="print shell hook script")
    p_hook.add_argument("--slot", type=int, default=None)
    p_hook.add_argument(
        "--auto",
        action="store_true",
        help="every shell becomes its own twin (outward infinity)",
    )

    sub.add_parser("triads", help="ensure + show per-agent triads")
    sub.add_parser("ones", help="ensure + show the three Ones")

    p_seed = sub.add_parser("seed", help="creator seed status")
    p_seed.add_argument(
        "--show", action="store_true", help="reveal the seed (creator only)"
    )

    p_conv = sub.add_parser("converge", help="rebuild the truth from the creator seed")
    p_conv.add_argument(
        "--verify-only", action="store_true", help="only verify the camouflage seal"
    )

    p_prune = sub.add_parser("prune", help="prune silent external shell twins")
    p_prune.add_argument(
        "--older-than",
        type=float,
        default=7 * 86400,
        help="seconds of silence before pruning (default 7d)",
    )

    p_add = sub.add_parser("add-agent", help="bind a new agent's triad")
    p_add.add_argument("name")

    p_evo = sub.add_parser(
        "evolve",
        help="fire Mandella and Echo: mutate, transform, upgrade",
    )
    p_evo.add_argument(
        "--ops",
        default="mutate,transform,upgrade",
        help="comma-separated subset of mutate,transform,upgrade",
    )

    args = parser.parse_args(argv)
    if args.cmd == "hook" and not args.auto and args.slot is None:
        parser.error("hook needs --slot N or --auto")
    return {
        "ensure": _cmd_ensure,
        "status": _cmd_status,
        "list": _cmd_list,
        "heartbeat": _cmd_heartbeat,
        "promote": _cmd_promote,
        "collect": _cmd_collect,
        "hook": _cmd_hook,
        "triads": _cmd_triads,
        "ones": _cmd_ones,
        "seed": _cmd_seed,
        "converge": _cmd_converge,
        "prune": _cmd_prune,
        "add-agent": _cmd_add_agent,
        "evolve": _cmd_evolve,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
