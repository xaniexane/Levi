"""CLI: python -m levi.services.shield <command> ...

authorize --client C --contact N --role R --assets a,b --windows w
          --categories wireless,network --by NAME --expires YYYY-MM-DD
          --confirm "I AUTHORIZE THIS SECURITY ASSESSMENT"
plan <auth-id> --type TYPE --targets t1,t2 [--objective TEXT]
finding <auth-id> --plan PLAN --target T --severity S --title T
        --evidence E --playbook SKILL_ID
harden <auth-id>                 # build the hardening plan from findings
verify <auth-id> <action-id> --note TEXT
report <auth-id> --plan-json PATH
offer <auth-id> --provider P --title T --client C [--type cyber-audit]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _split(raw: str) -> list:
    return [p.strip() for p in (raw or "").split(",") if p.strip()]


def cmd_authorize(a) -> int:
    from levi.services.shield.authorization import CONFIRMATION_PHRASE, grant_authorization

    auth = grant_authorization(
        client=a.client,
        authorized_contact=a.contact,
        contact_role=a.role,
        scope_assets=_split(a.assets),
        testing_windows=_split(a.windows),
        permitted_categories=_split(a.categories),
        exclusions=_split(a.exclusions or ""),
        authorized_by=a.by,
        expires_at=a.expires,
        confirmation=a.confirm,
    )
    print(f"authorized: {auth.auth_id} for {auth.client} (expires {auth.expires_at})")
    print(f"confirmation phrase required: {CONFIRMATION_PHRASE!r}")
    return 0


def cmd_plan(a) -> int:
    from levi.services.shield.assess import plan_assessment

    plan = plan_assessment(
        a.auth_id,
        assessment_type=a.type,
        targets=_split(a.targets),
        objective=a.objective or "",
    )
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


def cmd_finding(a) -> int:
    from levi.services.shield.assess import FindingsRegister

    finding = FindingsRegister().record(
        a.auth_id,
        plan_id=a.plan,
        target=a.target,
        severity=a.severity,
        title=a.title,
        evidence=a.evidence,
        playbook_id=a.playbook,
    )
    print(f"recorded: {finding.finding_id} [{finding.severity}] {finding.title}")
    return 0


def cmd_harden(a) -> int:
    from levi.services.shield.assess import FindingsRegister
    from levi.services.shield.harden import build_hardening_plan

    findings = FindingsRegister().list(a.auth_id)
    actions = build_hardening_plan(a.auth_id, findings)
    for action in actions:
        print(f"p{action.priority} [{action.action_type}] {action.action_id}: {action.title}")
    return 0


def cmd_verify(a) -> int:
    from levi.services.shield.harden import HardeningStore

    action = HardeningStore().verify_action(a.auth_id, a.action_id, a.note)
    print(f"verified: {action.action_id} ({action.status})")
    return 0


def cmd_report(a) -> int:
    from levi.services.shield.report import build_report, executive_summary

    plan = json.loads(Path(a.plan_json).read_text(encoding="utf-8"))
    sealed = build_report(a.auth_id, plan)
    print(executive_summary(sealed))
    print(f"report_id: {sealed['report_id']} seal: {sealed['seal'][:16]}...")
    return 0


def cmd_offer(a) -> int:
    from levi.services.shield.service import offer_shield

    offering = offer_shield(
        provider=a.provider,
        title=a.title,
        client=a.client,
        auth_id=a.auth_id,
        service_type=a.type,
    )
    print(f"offered: {offering.offering_id} [{offering.service_type}]")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="levi.services.shield")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("authorize")
    p.add_argument("--client", required=True)
    p.add_argument("--contact", required=True)
    p.add_argument("--role", required=True)
    p.add_argument("--assets", required=True)
    p.add_argument("--windows", required=True)
    p.add_argument("--categories", required=True)
    p.add_argument("--exclusions", default="")
    p.add_argument("--by", required=True)
    p.add_argument("--expires", required=True)
    p.add_argument("--confirm", required=True)
    p.set_defaults(func=cmd_authorize)

    p = sub.add_parser("plan")
    p.add_argument("auth_id")
    p.add_argument("--type", required=True)
    p.add_argument("--targets", required=True)
    p.add_argument("--objective", default="")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("finding")
    p.add_argument("auth_id")
    p.add_argument("--plan", required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--severity", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--evidence", required=True)
    p.add_argument("--playbook", required=True)
    p.set_defaults(func=cmd_finding)

    p = sub.add_parser("harden")
    p.add_argument("auth_id")
    p.set_defaults(func=cmd_harden)

    p = sub.add_parser("verify")
    p.add_argument("auth_id")
    p.add_argument("action_id")
    p.add_argument("--note", required=True)
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("report")
    p.add_argument("auth_id")
    p.add_argument("--plan-json", required=True)
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("offer")
    p.add_argument("auth_id")
    p.add_argument("--provider", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--client", required=True)
    p.add_argument("--type", default="cyber-audit")
    p.set_defaults(func=cmd_offer)

    a = ap.parse_args(argv)
    try:
        return a.func(a)
    except Exception as exc:  # noqa: BLE001 - CLI surfaces the refusal
        print(f"refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
