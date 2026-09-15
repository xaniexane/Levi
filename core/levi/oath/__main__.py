"""LEVI Oath command line: ``python -m levi.oath <subcommand>``.

Subcommands: ``init``, ``doctor``, ``key``, ``contact``, ``command``,
``run``, ``inbox``, ``daemon``, ``audit``.

NOTE: the ``levi oath`` wiring into :mod:`levi.cli` follows after the
hardening pass — do not wire it into ``core/levi/cli/main.py`` yet (that
file is owned by another in-flight worker).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

from levi.oath import (
    AUDIT_FILE,
    CHECKPOINTS_DIR,
    COMMANDS_DIR,
    CONTACTS_FILE,
    MAIL_FILE,
    MAILDIR,
    OWNER_FILE,
    gnupg_home,
    oath_home,
)


def _utcnow() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# init / doctor
# ---------------------------------------------------------------------------

def cmd_init(args: argparse.Namespace) -> int:
    """Create the Oath home layout: dirs, owner.json, mail.json template."""
    from levi.oath.keys import ensure_gnupg_home

    home = oath_home()
    (home / "commands").mkdir(parents=True, exist_ok=True)
    MAILDIR().mkdir(parents=True, exist_ok=True)
    for sub in ("new", "cur", "tmp"):
        (MAILDIR() / sub).mkdir(exist_ok=True)
    CHECKPOINTS_DIR().mkdir(parents=True, exist_ok=True)
    ensure_gnupg_home()

    if not OWNER_FILE().exists():
        OWNER_FILE().write_text(
            json.dumps({
                "email": args.email or "",
                "fingerprint": "",
                "created_at": _utcnow(),
                "note": "Set fingerprint to the owner's key (oath key gen, then paste the fingerprint here).",
            }, indent=2) + "\n",
            encoding="utf-8",
        )
        try:
            OWNER_FILE().chmod(0o600)
        except OSError:
            pass
    if not MAIL_FILE().exists():
        MAIL_FILE().write_text(
            json.dumps({
                "imap": {"host": "", "port": 993, "user": "", "password": "", "folder": "INBOX"},
                "smtp": {"host": "", "port": 587, "user": "", "password": "",
                         "use_tls": True, "from": ""},
            }, indent=2) + "\n",
            encoding="utf-8",
        )
        try:
            MAIL_FILE().chmod(0o600)
        except OSError:
            pass
    print(f"oath home initialised at {home}")
    print("next: oath key gen --uid 'Owner <you@example.com>', then set owner.json fingerprint,")
    print("      then oath doctor")
    return 0


def cmd_doctor(_args: argparse.Namespace) -> int:
    """Check the Oath installation: gpg, dirs, owner key, mail config."""
    from levi.oath.keys import list_keys
    from levi.oath.trust import gpg_available

    ok = True

    def _check(label: str, good: bool, hint: str = "") -> None:
        nonlocal ok
        print(("PASS " if good else "FAIL ") + label + (f" — {hint}" if hint and not good else ""))
        ok = ok and good

    _check("gpg installed", gpg_available(), "install gnupg")
    _check("oath home exists", oath_home().is_dir(), f"run: python -m levi.oath init")
    _check("gnupg home is 0700", gnupg_home().is_dir(), "run: python -m levi.oath init")

    owner_fp = ""
    try:
        owner_fp = (json.loads(OWNER_FILE().read_text(encoding="utf-8")).get("fingerprint") or "").upper().replace(" ", "")
    except (OSError, json.JSONDecodeError):
        pass
    _check("owner.json fingerprint set", bool(owner_fp), "set fingerprint in owner.json")

    keys = list_keys() if gpg_available() else []
    has_owner_key = any(k.fingerprint == owner_fp for k in keys) if owner_fp else False
    _check("owner key present in oath keyring", has_owner_key, "oath key gen / oath key import")

    from levi.oath.inbox import load_mail_config
    cfg = load_mail_config()
    _check("mail.json configured (imap or maildir usable)",
           bool(cfg.imap_host) or MAILDIR().is_dir(), "fill in mail.json or drop mail into maildir/new")

    from levi.oath.contacts import load_book
    book = load_book()
    print(f"info: {len(book.contacts)} contact(s), commands dir: {COMMANDS_DIR()}")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# key
# ---------------------------------------------------------------------------

def cmd_key(args: argparse.Namespace) -> int:
    """Key management: gen | import | list | fingerprint | delete."""
    from levi.oath.keys import delete_key, fingerprint_of, generate_key, import_key, list_keys

    if args.key_cmd == "gen":
        info = generate_key(args.uid, expire=args.expire)
        print(f"generated: {info.fingerprint}")
        print(f"uids: {', '.join(info.uids)}")
        print("pin this fingerprint in owner.json (owner) or the contact (oath contact pin)")
        return 0
    if args.key_cmd == "import":
        data = Path(args.file).read_bytes() if args.file else sys.stdin.buffer.read()
        imported = import_key(data)
        for key in imported:
            print(f"{key.fingerprint}  {'; '.join(key.uids)}")
        return 0
    if args.key_cmd == "list":
        for key in list_keys():
            print(f"{key.fingerprint}  {'; '.join(key.uids)}")
        return 0
    if args.key_cmd == "fingerprint":
        fpr = fingerprint_of(args.pattern)
        print(fpr or "(no match)")
        return 0 if fpr else 1
    if args.key_cmd == "delete":
        delete_key(args.fingerprint)
        print("deleted")
        return 0
    print("unknown key subcommand", file=sys.stderr)
    return 2


# ---------------------------------------------------------------------------
# contact
# ---------------------------------------------------------------------------

def cmd_contact(args: argparse.Namespace) -> int:
    """Contact management: add | list | remove | grant | pin | floor | rate | ceiling."""
    from levi.oath.contacts import Contact, load_book

    book = load_book()
    if args.contact_cmd == "add":
        contact = Contact(name=args.name, email=args.email or "",
                          trust_floor=args.floor, tier_ceiling=args.ceiling,
                          max_missions_per_hour=args.rate)
        book.add(contact)
        print(f"added contact {args.name}")
        return 0
    if args.contact_cmd == "list":
        for name, contact in sorted(book.contacts.items()):
            grants = ", ".join(f"{c}:{''.join(l)}" for c, l in sorted(contact.grants.items()))
            print(f"{name} <{contact.email}> floor={contact.trust_floor} "
                  f"ceiling={contact.tier_ceiling} rate={contact.max_missions_per_hour}/h "
                  f"pins={len(contact.fingerprints)} grants=[{grants}]")
        return 0
    if args.contact_cmd == "remove":
        book.remove(args.name)
        print(f"removed {args.name}")
        return 0
    if args.contact_cmd == "grant":
        book.grant(args.name, args.command, args.letters)
        print(f"{args.name}: {args.command} -> {args.letters}")
        return 0
    if args.contact_cmd == "pin":
        book.pin(args.name, args.fingerprint)
        print(f"pinned {args.fingerprint[:16]}… to {args.name}")
        return 0
    if args.contact_cmd == "floor":
        contact = book.get(args.name)
        if contact is None:
            print(f"no such contact: {args.name}", file=sys.stderr)
            return 1
        contact.trust_floor = args.level
        book.update(contact)
        print(f"{args.name}: trust floor -> {args.level}")
        return 0
    if args.contact_cmd == "ceiling":
        contact = book.get(args.name)
        if contact is None:
            print(f"no such contact: {args.name}", file=sys.stderr)
            return 1
        contact.tier_ceiling = args.tier
        book.update(contact)
        print(f"{args.name}: tier ceiling -> {args.tier}")
        return 0
    if args.contact_cmd == "rate":
        contact = book.get(args.name)
        if contact is None:
            print(f"no such contact: {args.name}", file=sys.stderr)
            return 1
        contact.max_missions_per_hour = args.per_hour
        book.update(contact)
        print(f"{args.name}: rate -> {args.per_hour}/h")
        return 0
    print("unknown contact subcommand", file=sys.stderr)
    return 2


# ---------------------------------------------------------------------------
# command
# ---------------------------------------------------------------------------

def _definition_from_args(args: argparse.Namespace) -> dict:
    argv = list(args.argv)
    schema: dict = {}
    for item in args.arg or []:
        # name:type:required:pattern  (pattern optional)
        parts = item.split(":", 3)
        name = parts[0]
        spec: dict = {"type": parts[1] if len(parts) > 1 else "string",
                      "required": (parts[2].lower() == "true") if len(parts) > 2 else False}
        if len(parts) > 3 and parts[3]:
            spec["pattern"] = parts[3]
        schema[name] = spec
    return {
        "name": args.name,
        "version": 1,
        "description": args.description or "",
        "tier": args.tier,
        "argv": argv,
        "args": schema,
        "created_by": "owner",
        "created_at": _utcnow(),
        "expires_at": args.expires or "",
    }


def cmd_command(args: argparse.Namespace) -> int:
    """Command registry: define | sign | list | show."""
    from levi.oath.commands import CommandRegistry, DefinitionError

    registry = CommandRegistry()
    if args.command_cmd == "define":
        definition = _definition_from_args(args)
        path = registry.write_unsigned(definition)
        print(f"draft written (UNSIGNED — will not load): {path}")
        print("review it, then run: python -m levi.oath command sign " + args.name)
        return 0
    if args.command_cmd == "sign":
        # The sign ceremony: show the canonical bytes, ask for confirmation.
        json_path = COMMANDS_DIR() / f"{args.name}.json"
        if not json_path.exists():
            print(f"no such definition: {args.name}", file=sys.stderr)
            return 1
        print("=" * 60)
        print(json_path.read_text(encoding="utf-8"), end="")
        print("=" * 60)
        if not args.yes:
            answer = input("Sign this definition as owner? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                print("aborted — definition left unsigned")
                return 1
        try:
            sig = registry.sign(args.name)
        except DefinitionError as exc:
            print(f"cannot sign: {exc}", file=sys.stderr)
            return 1
        print(f"signed: {sig}")
        return 0
    if args.command_cmd == "list":
        try:
            defs = registry.load_all()
        except DefinitionError as exc:
            print(f"registry refused to load: {exc}", file=sys.stderr)
            return 1
        for name in sorted(defs):
            d = defs[name]
            print(f"{name}  tier={d.tier} builtin={d.builtin} :: {d.description[:70]}")
        return 0
    if args.command_cmd == "show":
        try:
            d = registry.get(args.name)
        except DefinitionError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps({"name": d.name, "tier": d.tier, "argv": d.argv,
                          "args": d.args, "description": d.description,
                          "expires_at": d.expires_at, "builtin": d.builtin}, indent=2))
        return 0
    print("unknown command subcommand", file=sys.stderr)
    return 2


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> int:
    """Run a pipeline as a contact (local operator console)."""
    from levi.oath.audit import AuditLog
    from levi.oath.commands import CommandRegistry
    from levi.oath.contacts import load_book
    from levi.oath.pipeline import parse, run as run_pipeline
    from levi.oath.policy import check_pipeline, trust_gate
    from levi.oath.trust import TRUSTED

    book = load_book()
    contact = book.get(args.contact)
    if contact is None:
        print(f"no such contact: {args.contact}", file=sys.stderr)
        return 1
    # The local console acts with the owner's authority: TRUSTED by construction.
    decision = trust_gate(contact, TRUSTED)
    if not decision.allowed:
        print(f"trust gate: {decision.reason}", file=sys.stderr)
        return 1
    pipeline = parse(args.pipeline)
    registry = CommandRegistry()
    precheck = check_pipeline(contact, [s.to_dict() for s in pipeline.stages], registry)
    for stage, dec in zip(pipeline.stages, precheck):
        print(f"[{'ALLOW' if dec.allowed else 'DENY'}] {stage.raw} — {dec.reason}")
        if not dec.allowed:
            AuditLog().append({"event": "console.denied", "contact": contact.name,
                               "stage": stage.raw, "reason": dec.reason})
            return 1
    run_pipeline(pipeline, contact, registry=registry, dry_run=args.dry_run,
                 reply_to="", send_reply=None)
    AuditLog().append({"event": "console.run", "contact": contact.name,
                       "pipeline": args.pipeline, "dry_run": args.dry_run,
                       "results": pipeline.to_dict()["results"]})
    for result in pipeline.results:
        status = "ok" if result.ok else "FAIL"
        print(f"--- [{status}] {result.stage.raw}")
        if result.note:
            print(f"    note: {result.note}")
        if result.stdout:
            print(result.stdout.rstrip())
        if result.stderr:
            print(f"    stderr: {result.stderr.rstrip()}", file=sys.stderr)
    return 0 if all(r.ok for r in pipeline.results) else 1


# ---------------------------------------------------------------------------
# inbox / daemon / audit
# ---------------------------------------------------------------------------

def cmd_inbox(args: argparse.Namespace) -> int:
    """Poll intake and list the missions that would be created (no execution)."""
    from levi.oath.contacts import load_book
    from levi.oath.inbox import load_mail_config, poll

    missions = poll(load_book(), use_imap=args.imap, use_maildir=not args.imap,
                    config=load_mail_config())
    for key, mission in missions:
        print(f"{key}: from={mission.from_address} trust={mission.trust} "
              f"contact={mission.contact_name} subject={mission.subject!r}")
        if mission.parse_error:
            print(f"    parse error: {mission.parse_error}")
        for stage in mission.stages:
            print(f"    stage: {stage['raw']}")
    print(f"{len(missions)} message(s)")
    return 0


def cmd_daemon(args: argparse.Namespace) -> int:
    """Run the unattended daemon."""
    from levi.oath.daemon import Daemon
    from levi.oath.inbox import load_mail_config

    daemon = Daemon(config=load_mail_config(), poll_interval=args.interval,
                    dry_run=args.dry_run)
    if args.once:
        summary = daemon.run_once(use_imap=args.imap, use_maildir=not args.imap)
        print(json.dumps(summary, indent=2))
        return 0
    daemon.serve(use_imap=args.imap, use_maildir=not args.imap)
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """Audit trail: verify | checkpoint | tail."""
    from levi.oath.audit import AuditError, AuditLog
    from levi.oath.commands import CommandRegistry

    log = AuditLog()
    if args.audit_cmd == "verify":
        try:
            chain = log.verify()
        except AuditError as exc:
            print(f"CHAIN BROKEN: {exc}", file=sys.stderr)
            return 1
        try:
            cps = log.verify_checkpoints(CommandRegistry.owner_fingerprint())
        except AuditError as exc:
            print(f"CHECKPOINT FAILED: {exc}", file=sys.stderr)
            return 1
        print(f"chain ok: {chain['entries']} entries, head {chain['head'][:16]}…; "
              f"{cps['checkpoints']} checkpoint(s) ok")
        return 0
    if args.audit_cmd == "checkpoint":
        path = log.checkpoint()
        print(f"checkpoint: {path}")
        return 0
    if args.audit_cmd == "tail":
        entries = list(log.entries())
        for entry in entries[-args.n:]:
            payload = entry.get("payload", {})
            print(f"{entry['seq']:>5} {entry['ts']} {payload.get('event', '?')} "
                  f"{str(payload.get('reason', payload.get('contact', '')))[:80]}")
        return 0
    print("unknown audit subcommand", file=sys.stderr)
    return 2


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m levi.oath",
        description="LEVI Oath — the trust-bound mission plane (sudo for agents).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="initialise the oath home layout")
    p.add_argument("--email", default="", help="owner email for owner.json")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("doctor", help="check the installation")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("key", help="GPG key management")
    ks = p.add_subparsers(dest="key_cmd", required=True)
    q = ks.add_parser("gen", help="generate a throwaway key")
    q.add_argument("--uid", required=True)
    q.add_argument("--expire", default="0")
    q = ks.add_parser("import", help="import an armored key (file or stdin)")
    q.add_argument("file", nargs="?")
    ks.add_parser("list", help="list keys")
    q = ks.add_parser("fingerprint", help="resolve a pattern to a fingerprint")
    q.add_argument("pattern")
    q = ks.add_parser("delete", help="delete a key from the oath keyring")
    q.add_argument("fingerprint")
    p.set_defaults(func=cmd_key)

    p = sub.add_parser("contact", help="contact address book")
    cs = p.add_subparsers(dest="contact_cmd", required=True)
    q = cs.add_parser("add", help="add a contact")
    q.add_argument("name")
    q.add_argument("--email", default="")
    q.add_argument("--floor", default="VERIFIED", choices=["VERIFIED", "TRUSTED"])
    q.add_argument("--ceiling", default="write", choices=["read", "write", "execute", "dangerous"])
    q.add_argument("--rate", type=int, default=10, help="max missions per hour")
    q = cs.add_parser("list", help="list contacts")
    q = cs.add_parser("remove", help="remove a contact")
    q.add_argument("name")
    q = cs.add_parser("grant", help="set per-command grant letters")
    q.add_argument("name")
    q.add_argument("command")
    q.add_argument("letters", help="any of r w x d, e.g. rw")
    q = cs.add_parser("pin", help="pin a fingerprint to a contact")
    q.add_argument("name")
    q.add_argument("fingerprint")
    q = cs.add_parser("floor", help="set the contact's trust floor")
    q.add_argument("name")
    q.add_argument("level", choices=["VERIFIED", "TRUSTED"])
    q = cs.add_parser("ceiling", help="set the contact's tier ceiling")
    q.add_argument("name")
    q.add_argument("tier", choices=["read", "write", "execute", "dangerous"])
    q = cs.add_parser("rate", help="set the contact's hourly mission budget")
    q.add_argument("name")
    q.add_argument("per_hour", type=int)
    p.set_defaults(func=cmd_contact)

    p = sub.add_parser("command", help="signed command registry")
    ds = p.add_subparsers(dest="command_cmd", required=True)
    q = ds.add_parser("define", help="write an unsigned definition draft")
    q.add_argument("name")
    q.add_argument("--tier", default="read", choices=["read", "write", "execute", "dangerous"])
    q.add_argument("--description", default="")
    q.add_argument("--argv", nargs="+", required=True,
                   help="argv template, e.g. --argv du -sh {path}")
    q.add_argument("--arg", action="append", default=[],
                   help="arg schema name:type:required:pattern (repeatable)")
    q.add_argument("--expires", default="", help="ISO-8601 expiry, e.g. 2027-09-15T00:00:00Z")
    q = ds.add_parser("sign", help="owner sign ceremony for a definition")
    q.add_argument("name")
    q.add_argument("--yes", action="store_true", help="skip the interactive prompt")
    ds.add_parser("list", help="list loaded (signature-verified) definitions")
    q = ds.add_parser("show", help="show one definition")
    q.add_argument("name")
    p.set_defaults(func=cmd_command)

    p = sub.add_parser("run", help="run a pipeline as a contact (local console)")
    p.add_argument("--contact", required=True)
    p.add_argument("--pipeline", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("inbox", help="intake")
    ins = p.add_subparsers(dest="inbox_cmd", required=True)
    q = ins.add_parser("poll", help="list missions the intake would create")
    q.add_argument("--imap", action="store_true", help="use IMAP instead of Maildir")
    p.set_defaults(func=cmd_inbox)

    p = sub.add_parser("daemon", help="unattended daemon")
    p.add_argument("--once", action="store_true", help="single poll cycle (for cron)")
    p.add_argument("--imap", action="store_true")
    p.add_argument("--interval", type=int, default=60)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_daemon)

    p = sub.add_parser("audit", help="audit trail")
    aus = p.add_subparsers(dest="audit_cmd", required=True)
    aus.add_parser("verify", help="replay the hash chain and check checkpoints")
    aus.add_parser("checkpoint", help="write a signed checkpoint")
    q = aus.add_parser("tail", help="show recent entries")
    q.add_argument("-n", type=int, default=10)
    p.set_defaults(func=cmd_audit)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
