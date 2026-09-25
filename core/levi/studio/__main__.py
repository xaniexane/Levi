"""CLI for the Omega Studio consent kit: ``python -m levi.studio ...``.

Subcommands
-----------
- ``policy check --policy FILE --input FILE`` — print allow/deny.
- ``consent request --action A --actor X --resource R [--context JSON]``
- ``consent approve|deny --id ID --by NAME [--reason R]``
- ``consent pending`` — list pending requests as JSON.
- ``consent check --id ID`` — print granted/denied/pending/expired.
- ``audit verify`` — replay the HMAC-signed trail.

State lives under ``~/.levi/studio/`` unless ``--dir`` overrides it.
The default policy (``policy.rego`` in the state dir) denies everything
with side effects unless the actor is the owner — edit it to fit your
house. An absent policy file means DENY ALL: the gate refuses to run
without an explicit policy on disk.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

DEFAULT_POLICY = """\
package consent

# Default-deny: side-effect actions need an explicit allow rule.
default allow = false

# Reads and other non-side-effect actions are fine.
allow {
  input.side_effects == false
}

# The owner may do anything (they can already run the CLI directly).
allow {
  input.actor == "owner"
}

# Nobody untrusted touches side effects, whatever else matches.
deny {
  input.side_effects == true
  input.actor_trust == "untrusted"
}
"""


def _state_dir(args) -> Path:
    return Path(args.dir or os.environ.get("LEVI_STUDIO_DIR")
                or os.path.expanduser("~/.levi/studio"))


def _load_policy(state_dir: Path):
    from levi.studio.policy import Policy, PolicyError

    policy_file = state_dir / "policy.rego"
    if not policy_file.exists():
        print(f"DENY ALL: no policy at {policy_file} — create one first.",
              file=sys.stderr)
        sys.exit(3)
    try:
        return Policy.from_rego(policy_file.read_text(encoding="utf-8"))
    except PolicyError as exc:
        print(f"policy refused to load (fail closed): {exc}", file=sys.stderr)
        sys.exit(3)


def _gate(args):
    from levi.studio.consent import ConsentGate

    state_dir = _state_dir(args)
    state_dir.mkdir(parents=True, exist_ok=True)
    policy = _load_policy(state_dir)
    return ConsentGate(policy, state_dir)


def cmd_policy_check(args) -> int:
    from levi.studio.policy import Policy, PolicyError

    try:
        policy = Policy.from_rego(Path(args.policy).read_text(encoding="utf-8"))
    except PolicyError as exc:
        print(f"policy error: {exc}", file=sys.stderr)
        return 3
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    print(policy.decide(data))
    return 0


def cmd_consent_request(args) -> int:
    gate = _gate(args)
    try:
        context = json.loads(args.context) if args.context else {}
    except json.JSONDecodeError as exc:
        print(f"bad --context JSON: {exc}", file=sys.stderr)
        return 2
    try:
        req = gate.request(args.action, args.actor, args.resource, context)
    except Exception as exc:  # ConsentError
        print(f"request refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(req.to_dict(), indent=2))
    return 0


def cmd_consent_approve(args) -> int:
    gate = _gate(args)
    try:
        req = gate.approve(args.id, args.by)
    except Exception as exc:
        print(f"approve refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(req.to_dict(), indent=2))
    return 0


def cmd_consent_deny(args) -> int:
    gate = _gate(args)
    try:
        req = gate.deny(args.id, args.by, args.reason or "")
    except Exception as exc:
        print(f"deny refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(req.to_dict(), indent=2))
    return 0


def cmd_consent_pending(args) -> int:
    gate = _gate(args)
    print(json.dumps([r.to_dict() for r in gate.pending()], indent=2))
    return 0


def cmd_consent_check(args) -> int:
    gate = _gate(args)
    try:
        req = gate.get(args.id)
    except Exception as exc:
        print(f"denied: {exc}", file=sys.stderr)
        return 1
    print("granted" if gate.is_granted(args.id) else req.status)
    return 0 if gate.is_granted(args.id) else 1


def cmd_audit_verify(args) -> int:
    gate = _gate(args)
    ok, findings = gate.verify_audit()
    for line in findings:
        print(line)
    return 0 if ok else 1


def cmd_init(args) -> int:
    state_dir = _state_dir(args)
    state_dir.mkdir(parents=True, exist_ok=True)
    policy_file = state_dir / "policy.rego"
    if not policy_file.exists():
        policy_file.write_text(DEFAULT_POLICY, encoding="utf-8")
        print(f"wrote default-deny policy to {policy_file}")
    else:
        print(f"policy already exists at {policy_file} (untouched)")
    # Touch the audit trail so the key is generated now, not mid-crisis.
    from levi.studio.audit import AuditTrail

    AuditTrail.open(state_dir / "audit").append("studio.initialized", {})
    print(f"audit trail ready under {state_dir / 'audit'}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="levi.studio",
                                 description="Omega Studio consent kit CLI")
    ap.add_argument("--dir", default=None, help="state dir (default ~/.levi/studio)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("policy-check", help="decide one input against a policy file")
    sp.add_argument("--policy", required=True)
    sp.add_argument("--input", required=True)
    sp.set_defaults(func=cmd_policy_check)

    sc = sub.add_parser("consent", help="human-in-the-loop consent gate")
    cs = sc.add_subparsers(dest="op", required=True)

    r = cs.add_parser("request", help="propose a side-effect action")
    r.add_argument("--action", required=True)
    r.add_argument("--actor", required=True)
    r.add_argument("--resource", required=True)
    r.add_argument("--context", default=None, help="extra JSON context")
    r.set_defaults(func=cmd_consent_request)

    a = cs.add_parser("approve", help="approve a pending request")
    a.add_argument("--id", required=True)
    a.add_argument("--by", required=True)
    a.set_defaults(func=cmd_consent_approve)

    d = cs.add_parser("deny", help="deny a pending request")
    d.add_argument("--id", required=True)
    d.add_argument("--by", required=True)
    d.add_argument("--reason", default="")
    d.set_defaults(func=cmd_consent_deny)

    p = cs.add_parser("pending", help="list pending requests")
    p.set_defaults(func=cmd_consent_pending)

    c = cs.add_parser("check", help="check a request (exit 0 iff granted)")
    c.add_argument("--id", required=True)
    c.set_defaults(func=cmd_consent_check)

    av = sub.add_parser("audit-verify", help="replay the signed audit trail")
    av.set_defaults(func=cmd_audit_verify)

    si = sub.add_parser("init", help="write default policy + init audit trail")
    si.set_defaults(func=cmd_init)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
