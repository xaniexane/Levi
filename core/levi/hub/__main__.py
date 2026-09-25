"""levi.hub CLI. Proven command shapes from the original's CLI:

status, chat, agent, alpha, skills, jobs, pulse, serve, auth, hitl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# make `levi.*` importable from a bare checkout (core/ on the path)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from levi.hub import agent as scout  # noqa: E402
from levi.hub import alpha as alpha_lab  # noqa: E402
from levi.hub import api as hub_api  # noqa: E402
from levi.hub import auth as hub_auth  # noqa: E402
from levi.hub import hitl as hitl_mod  # noqa: E402
from levi.hub import jobs as job_engine  # noqa: E402
from levi.hub import orchestrator  # noqa: E402


def _emit(obj) -> int:
    print(json.dumps(obj, indent=2, default=str))
    return 0


def cmd_status(_a) -> int:
    return _emit(orchestrator.status())


def cmd_chat(a) -> int:
    return _emit(scout.run(a.text or "hello"))


def cmd_agent(a) -> int:
    return _emit(
        scout.run(
            a.task,
            url=a.url,
            command=a.command,
            hitl_id=a.hitl_id,
            net=a.net,
        )
    )


def cmd_alpha(a) -> int:
    if a.alpha_cmd == "design":
        return _emit(alpha_lab.design(a.prompt))
    if a.alpha_cmd == "preview":
        return _emit(alpha_lab.preview(a.prompt))
    if a.alpha_cmd == "create":
        try:
            return _emit(
                alpha_lab.create(
                    a.prompt,
                    a.dest,
                    approve=a.approve,
                    hitl_id=a.hitl_id,
                    overwrite=a.overwrite,
                )
            )
        except hitl_mod.ApprovalRequired as exc:
            return _emit(
                {"ok": False, "blocked": "approval_required", "error": str(exc)}
            )
    if a.alpha_cmd == "catalog":
        from levi.revival.omega import generators as gen

        return _emit({"generators": gen.registered()})
    raise SystemExit(f"unknown alpha subcommand {a.alpha_cmd}")


def cmd_skills(_a) -> int:
    try:
        from levi.skill import registry as reg  # type: ignore

        names = sorted(getattr(reg, "all_names", lambda: [])())
    except Exception:
        names = []
    return _emit(
        {
            "ok": True,
            "skills": names,
            "note": "standing skills live in levi.skill; the hub routes to them",
        }
    )


def cmd_jobs(a) -> int:
    if a.jobs_cmd == "search":
        return _emit(
            job_engine.search_all(
                a.query, sources=a.sources.split(",") if a.sources else None
            )
        )
    if a.jobs_cmd == "stage":
        import json as _j

        listings = _j.loads(Path(a.file).read_text(encoding="utf-8"))
        return _emit(job_engine.stage(listings, dry_run=not a.write))
    raise SystemExit(f"unknown jobs subcommand {a.jobs_cmd}")


def cmd_pulse(a) -> int:
    from levi.demand import processing as dp

    if a.pulse_cmd == "scan":
        return _emit(dp.run_scan(a.query or ""))
    if a.pulse_cmd == "heatmap":
        scan = dp.load_last_scan()
        if not scan:
            return _emit({"ok": False, "error": "no scan yet"})
        return _emit({"ok": True, "heatmap": scan.get("heatmap")})
    raise SystemExit(f"unknown pulse subcommand {a.pulse_cmd}")


def cmd_compete(a) -> int:
    from levi.demand import competition as comp

    if a.c == "track":
        return _emit({"ok": True, "results": comp.track_all()})
    if a.c == "diff":
        return _emit({"ok": True, "changes": comp.check_changes()})
    if a.c == "gaps":
        return _emit({"ok": True, "matrix": comp.feature_matrix()})
    if a.c == "propose":
        return _emit(comp.propose_upgrades())
    raise SystemExit(f"unknown compete subcommand {a.c}")


def cmd_cycle(a) -> int:
    return _emit(orchestrator.run_cycle(a.goal or ""))


def cmd_hitl(a) -> int:
    if a.hitl_cmd == "pending":
        return _emit({"ok": True, "pending": hitl_mod.pending()})
    if a.hitl_cmd == "approve":
        return _emit(hitl_mod.decide(a.id, True, note=a.note or ""))
    if a.hitl_cmd == "reject":
        return _emit(hitl_mod.decide(a.id, False, note=a.note or ""))
    raise SystemExit(f"unknown hitl subcommand {a.hitl_cmd}")


def cmd_auth(a) -> int:
    try:
        if a.auth_cmd == "register":
            return _emit(hub_auth.register(a.username, a.password))
        if a.auth_cmd == "login":
            return _emit(hub_auth.login(a.username, a.password))
        if a.auth_cmd == "logout":
            return _emit(hub_auth.logout(a.token))
    except ValueError as exc:
        return _emit({"ok": False, "error": str(exc)})
    raise SystemExit(f"unknown auth subcommand {a.auth_cmd}")


def cmd_serve(a) -> int:
    hub_api.serve(host=a.host, port=a.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="levi.hub", description="Alpha/Omega hub — ours only"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("status", help="hub health")
    c.set_defaults(fn=cmd_status)

    c = sub.add_parser("chat", help="talk to the hub agent")
    c.add_argument("text", nargs="?", default="")
    c.set_defaults(fn=cmd_chat)

    c = sub.add_parser("agent", help="run an agent task")
    c.add_argument("task")
    c.add_argument("--url", default=None)
    c.add_argument("--command", default=None)
    c.add_argument("--hitl-id", type=int, default=None)
    c.add_argument("--net", action="store_true")
    c.set_defaults(fn=cmd_agent)

    c = sub.add_parser("alpha", help="creation lab")
    ac = c.add_subparsers(dest="alpha_cmd", required=True)
    d = ac.add_parser("design")
    d.add_argument("prompt")
    d.set_defaults(fn=cmd_alpha)
    d = ac.add_parser("preview")
    d.add_argument("prompt")
    d.set_defaults(fn=cmd_alpha)
    d = ac.add_parser("create")
    d.add_argument("prompt")
    d.add_argument("dest")
    d.add_argument("--approve", action="store_true")
    d.add_argument("--hitl-id", type=int, default=None)
    d.add_argument("--overwrite", action="store_true")
    d.set_defaults(fn=cmd_alpha)
    ac.add_parser("catalog").set_defaults(fn=cmd_alpha)

    c = sub.add_parser("skills", help="list standing skills")
    c.set_defaults(fn=cmd_skills)

    c = sub.add_parser("jobs", help="keyless job search")
    jc = c.add_subparsers(dest="jobs_cmd", required=True)
    d = jc.add_parser("search")
    d.add_argument("--query", default="")
    d.add_argument("--sources", default=None)
    d.set_defaults(fn=cmd_jobs)
    d = jc.add_parser("stage")
    d.add_argument("--file", required=True)
    d.add_argument("--write", action="store_true")
    d.set_defaults(fn=cmd_jobs)

    c = sub.add_parser("pulse", help="DemandPulse")
    pc = c.add_subparsers(dest="pulse_cmd", required=True)
    d = pc.add_parser("scan")
    d.add_argument("--query", default="")
    d.set_defaults(fn=cmd_pulse)
    pc.add_parser("heatmap").set_defaults(fn=cmd_pulse)

    c = sub.add_parser("compete", help="competitor intel")
    c.add_argument("c", choices=["track", "diff", "gaps", "propose"])
    c.set_defaults(fn=cmd_compete)

    c = sub.add_parser("cycle", help="run an orchestrator cycle")
    c.add_argument("--goal", default="")
    c.set_defaults(fn=cmd_cycle)

    c = sub.add_parser("hitl", help="approval queue")
    hc = c.add_subparsers(dest="hitl_cmd", required=True)
    hc.add_parser("pending").set_defaults(fn=cmd_hitl)
    d = hc.add_parser("approve")
    d.add_argument("id", type=int)
    d.add_argument("--note", default="")
    d.set_defaults(fn=cmd_hitl)
    d = hc.add_parser("reject")
    d.add_argument("id", type=int)
    d.add_argument("--note", default="")
    d.set_defaults(fn=cmd_hitl)

    c = sub.add_parser("auth", help="local auth")
    ac2 = c.add_subparsers(dest="auth_cmd", required=True)
    d = ac2.add_parser("register")
    d.add_argument("username")
    d.add_argument("password")
    d.set_defaults(fn=cmd_auth)
    d = ac2.add_parser("login")
    d.add_argument("username")
    d.add_argument("password")
    d.set_defaults(fn=cmd_auth)
    d = ac2.add_parser("logout")
    d.add_argument("token")
    d.set_defaults(fn=cmd_auth)

    c = sub.add_parser("serve", help="local web UI + JSON API")
    c.add_argument("--host", default="127.0.0.1")
    c.add_argument("--port", type=int, default=8765)
    c.set_defaults(fn=cmd_serve)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
