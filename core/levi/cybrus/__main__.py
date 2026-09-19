"""Cybrus CLI — ``python -m levi.cybrus`` and the ``levi cybrus`` hook.

Subcommands: status, account create/list/set-password, vault store/get/list/
generate/oauth-store/oauth-get/oauth-list/oauth-refresh/oauth-revoke,
token issue/rotate/revoke, apikey create/list/revoke, route list/
add-external/remove-external/grant, qid parse, approve, deny, approvals
pending, audit tail/verify, device enroll/trust/list.

Secrets are NEVER taken via argv: the vault secret, master password, and
account passwords are read with ``getpass`` (prompt, no echo). Plaintext
tokens are printed exactly once at issuance/rotation.

``approve`` / ``deny`` are authenticated: they require ``--identity`` plus
a getpass password verified through ``gateway.auth()`` — the verified
identity is recorded in the decision's ``by`` field and in the audit log.
There is no anonymous path to decide a pending approval.

All ``levi.cybrus`` imports happen lazily inside functions (never at module
top) so this CLI works standalone even while sibling engine modules are
still landing on the shared branch.
"""

from __future__ import annotations

import argparse
import getpass
import importlib
import sys
import time
from pathlib import Path


def _mod(name: str):
    """Import ``levi.cybrus.<name>``, standalone-safe.

    The package ``__init__`` imports every sibling engine, so a mid-flight
    ``__init__`` (sibling modules still landing) breaks plain imports. On
    failure, fall back to a lightweight package stub — real ``__path__``,
    no ``__init__`` execution — so submodule imports resolve to the real
    files on disk. Raises a clear error when the module file itself has
    not landed yet.
    """
    fullname = f"levi.cybrus.{name}"
    try:
        return importlib.import_module(fullname)
    except ImportError:
        pass
    target = Path(__file__).resolve().parent / f"{name}.py"
    if not target.is_file():
        raise SystemExit(
            f"error: cybrus module {name!r} has not landed yet (expected {target})"
        )
    import types

    pkg_name = "levi.cybrus"
    if pkg_name not in sys.modules:
        stub = types.ModuleType(pkg_name)
        stub.__path__ = [str(Path(__file__).resolve().parent)]
        sys.modules[pkg_name] = stub
    return importlib.import_module(fullname)


def _short(entry_id: str) -> str:
    return entry_id[:8]


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def _cmd_status() -> int:
    policy = _mod("policy")
    approval = _mod("approval")
    audit = _mod("audit")
    devices = _mod("devices")

    pe = policy.PolicyEngine()
    ae = approval.ApprovalEngine()
    au = audit.AuditEngine()
    dv = devices.DeviceTrust()

    ok, bad = au.verify()
    chain = "OK" if ok else f"BROKEN at record {bad}"

    devs = dv.list()
    trust_counts = {level: 0 for level in devices.TRUST_LEVELS}
    for d in devs:
        trust_counts[d["trust"]] = trust_counts.get(d["trust"], 0) + 1

    print("Cybrus — Security & Identity Layer (local, defensive)")
    print(f"  policy:    {len(pe.list_rules())} rules (default-deny, deny-wins)")
    print(f"  approvals: {len(ae.pending())} pending")
    print(f"  audit:     {au.count()} records, hash chain {chain}")
    print(
        "  devices:   %d enrolled (%s)"
        % (
            len(devs),
            ", ".join(f"{n} {level}" for level, n in trust_counts.items()),
        )
    )
    try:
        identities = _mod("identity").IdentityStore().list()
        print(f"  identities: {len(identities)} accounts")
    except SystemExit as exc:
        print(f"  identities: unavailable ({exc})")
    return 0


# ---------------------------------------------------------------------------
# account (identity)
# ---------------------------------------------------------------------------


def _cmd_account(args) -> int:
    identity = _mod("identity")
    store = identity.IdentityStore()
    cmd = args.account_cmd or "list"
    if cmd == "create":
        try:
            rec = store.create(args.name, tier=args.tier)
        except (ValueError, identity.TierError) as exc:
            print(f"account create failed: {exc}")
            return 2
        print(
            f"created account {rec['name']} (id {_short(rec['id'])}, tier {rec['tier']})"
        )
        return 0
    if cmd == "list":
        recs = store.list()
        if not recs:
            print("no accounts")
            return 0
        for rec in recs:
            cred = "credential set" if rec.get("credential") else "no credential"
            print(
                f"{rec['name']}  [{_short(rec['id'])}]  tier={rec['tier']} "
                f"status={rec['status']}  {cred}"
            )
        return 0
    if cmd == "set-password":
        return _cmd_account_set_password(args)
    print(f"unknown account command: {cmd}")
    return 2


def _cmd_account_set_password(args) -> int:
    """Set (or change) an identity's password. Prompts via getpass — never
    argv. Only the PBKDF2 hash reference is persisted; the plaintext is
    never logged, audited, or stored.

    Fail-closed: when a credential already exists, the current password
    must be proven first — a bare shell session cannot silently reset
    someone else's credential.
    """
    identity = _mod("identity")
    factory_mod = _mod("factory")
    audit_mod = _mod("audit")
    store = identity.IdentityStore()
    rec = store.get(args.name)
    if rec is None:
        print(f"unknown identity: {args.name}")
        return 2
    existing = store.get_credential(rec["id"])
    if existing is not None:
        current = getpass.getpass(f"Current password for {args.name} (never echoed): ")
        if not factory_mod.verify_password(current, existing):
            print("error: current password is incorrect")
            return 2
    new_password = getpass.getpass(
        f"New password for {args.name} (min 16 chars, never echoed): "
    )
    if not new_password or len(new_password) < 16:
        print("error: password must be at least 16 characters")
        return 2
    confirm = getpass.getpass("Confirm new password: ")
    if new_password != confirm:
        print("error: passwords do not match")
        return 2
    store.set_credential(rec["id"], factory_mod.hash_password(new_password))
    audit_mod.AuditEngine().append(
        "account.credential_set", args.name, {"id": rec["id"][:8]}
    )
    print(f"credential set for {args.name}")
    return 0


# ---------------------------------------------------------------------------
# vault
# ---------------------------------------------------------------------------


def _open_vault():
    """Unlock the credential vault. Master password via getpass prompt —
    never argv, never stored. Returns ``(vault, passphrase)`` — the
    passphrase lets OAuth/identity layers open the same vault."""
    vault_mod = _mod("vault")
    master = getpass.getpass("Vault master password: ")
    if not master:
        raise SystemExit("error: master password is required")
    return vault_mod.CredentialVault(master), master


def _open_oauth_vault(master):
    """Open the OAuth token layer on the same vault passphrase."""
    return _mod("vault").OAuthVault(master)


def _cmd_vault(args) -> int:
    try:
        vault, master = _open_vault()
    except SystemExit as exc:
        print(exc)
        return 2
    cmd = args.vault_cmd or "list"
    try:
        if cmd == "store":
            secret = getpass.getpass(
                f"Secret for {args.service}/{args.username} (never echoed): "
            )
            if not secret:
                print("error: secret is required")
                return 2
            vault.store(args.service, args.username, secret)
            print(f"stored secret for {args.service}/{args.username}")
            return 0
        if cmd == "get":
            try:
                secret = vault.get(args.service, args.username)
            except KeyError:
                print(f"no secret stored for {args.service}/{args.username}")
                return 1
            print(secret)
            return 0
        if cmd == "list":
            services = vault.list_services()
            if not services:
                print("vault is empty")
                return 0
            for service in services:
                print(service)
            return 0
        if cmd == "generate":
            password = _mod("vault").generate_password(args.length)
            print("generated password (shown once — store it now):")
            print(password)
            return 0
        if cmd == "oauth-store":
            return _cmd_vault_oauth_store(args, master)
        if cmd == "oauth-get":
            return _cmd_vault_oauth_get(args, master)
        if cmd == "oauth-list":
            return _cmd_vault_oauth_list(args, master)
        if cmd == "oauth-refresh":
            return _cmd_vault_oauth_refresh(args, master)
        if cmd == "oauth-revoke":
            return _cmd_vault_oauth_revoke(args, master)
    except AttributeError as exc:
        print(f"error: vault module API mismatch ({exc}) — see levi/cybrus/vault.py")
        return 2
    print(f"unknown vault command: {cmd}")
    return 2


def _cmd_vault_oauth_store(args, master) -> int:
    vault_mod = _mod("vault")
    access = getpass.getpass("OAuth access token (never echoed): ")
    if not access:
        print("error: access token is required")
        return 2
    refresh = getpass.getpass("OAuth refresh token (optional, Enter to skip): ")
    ov = _open_oauth_vault(master)
    try:
        meta = ov.store_token(
            args.provider,
            args.identity,
            access,
            refresh_token=refresh or None,
            scopes=args.scope or [],
            expires_in=args.expires_in,
        )
    except vault_mod.OAuthError as exc:
        print(f"oauth store failed: {exc}")
        return 2
    print(f"stored OAuth token for {args.provider}/{args.identity}")
    print(f"  scopes:     {', '.join(meta['scopes']) if meta['scopes'] else '(none)'}")
    print(f"  expires_at: {meta['expires_at'] or 'never'}")
    return 0


def _cmd_vault_oauth_get(args, master) -> int:
    vault_mod = _mod("vault")
    ov = _open_oauth_vault(master)
    try:
        record = ov.get_token(args.provider, args.identity, requester=args.identity)
    except vault_mod.OAuthError as exc:
        print(f"oauth get failed: {exc}")
        return 1
    expired = "EXPIRED" if vault_mod.OAuthVault.is_expired(record) else "valid"
    print(f"provider:      {record['provider']}")
    print(f"identity:      {record['identity']}")
    print(f"scopes:        {', '.join(record['scopes']) if record['scopes'] else '(none)'}")
    print(f"status:        {expired}")
    print(f"refresh_count: {record['refresh_count']}")
    print("access token (handle with care):")
    print(record["access_token"])
    return 0


def _cmd_vault_oauth_list(args, master) -> int:
    ov = _open_oauth_vault(master)
    tokens = ov.list_tokens(identity=args.identity)
    if not tokens:
        print("no OAuth tokens stored" + (f" for {args.identity}" if args.identity else ""))
        return 0
    for t in tokens:
        status = "EXPIRED" if t["expired"] else "valid"
        print(
            f"{t['provider']}/{t['identity']} "
            f"[scopes: {', '.join(t['scopes']) if t['scopes'] else '(none)'}] "
            f"{status} refreshes={t['refresh_count']}"
        )
    return 0


def _cmd_vault_oauth_refresh(args, master) -> int:
    vault_mod = _mod("vault")
    access = getpass.getpass("New OAuth access token (never echoed): ")
    if not access:
        print("error: access token is required")
        return 2
    refresh = getpass.getpass("New OAuth refresh token (optional, Enter to keep old): ")
    ov = _open_oauth_vault(master)
    try:
        meta = ov.record_refresh(
            args.provider,
            args.identity,
            requester=args.identity,
            new_access_token=access,
            new_refresh_token=refresh or None,
            expires_in=args.expires_in,
        )
    except vault_mod.OAuthError as exc:
        print(f"oauth refresh failed: {exc}")
        return 1
    print(f"refreshed OAuth token for {args.provider}/{args.identity}")
    print(f"  refresh_count: {meta['refresh_count']}")
    print(f"  expires_at:    {meta['expires_at'] or 'never'}")
    return 0


def _cmd_vault_oauth_revoke(args, master) -> int:
    vault_mod = _mod("vault")
    ov = _open_oauth_vault(master)
    try:
        ov.revoke(args.provider, args.identity, requester=args.identity)
    except vault_mod.OAuthError as exc:
        print(f"oauth revoke failed: {exc}")
        return 1
    print(f"revoked OAuth token for {args.provider}/{args.identity}")
    return 0


# ---------------------------------------------------------------------------
# token
# ---------------------------------------------------------------------------


def _split_token_result(result):
    """Token issue/rotate returns the plaintext exactly once — either as a
    ``(token_id, plaintext)`` tuple or a dict carrying both."""
    if isinstance(result, tuple) and len(result) == 2:
        return result[0], result[1]
    if isinstance(result, dict):
        tid = result.get("id") or result.get("token_id")
        plain = result.get("token") or result.get("plaintext")
        return tid, plain
    raise SystemExit(
        "error: token engine returned an unrecognized shape "
        f"({type(result).__name__}) — see levi/cybrus/tokens.py"
    )


def _cmd_token(args) -> int:
    tokens_mod = _mod("tokens")
    engine = tokens_mod.TokenEngine()
    cmd = args.token_cmd
    try:
        if cmd == "issue":
            scopes = list(args.scope or [])
            result = engine.issue(scopes=scopes, ttl_seconds=args.ttl)
            tid, plain = _split_token_result(result)
            print(f"token id: {tid}")
            print(f"scopes: {', '.join(scopes) if scopes else '(none)'}")
            print("SAVE THIS TOKEN NOW — it is shown exactly once:")
            print(plain)
            return 0
        if cmd == "rotate":
            result = engine.rotate(args.id)
            tid, plain = _split_token_result(result)
            print(f"rotated token {tid} — old value is dead")
            print("SAVE THIS TOKEN NOW — it is shown exactly once:")
            print(plain)
            return 0
        if cmd == "revoke":
            engine.revoke(args.id)
            print(f"revoked token {args.id}")
            return 0
    except AttributeError as exc:
        print(f"error: token engine API mismatch ({exc}) — see levi/cybrus/tokens.py")
        return 2
    except tokens_mod.TokenError as exc:
        print(f"token {cmd} failed: {exc}")
        return 2
    print(f"unknown token command: {cmd}")
    return 2


# ---------------------------------------------------------------------------
# approvals — the human gate (authenticated: no anonymous self-approval)
# ---------------------------------------------------------------------------


def _authenticate_human(identity_name: str) -> str:
    """Authenticate the human behind a HITL decision.

    Returns the *verified* identity name, which the caller records in the
    decision's ``by`` field. Fail-closed: a missing ``--identity``, an
    unknown or suspended identity, an empty password, or a bad credential
    all abort with exit 2 — there is no anonymous path to approve or deny.

    The password is prompted via ``getpass`` (never argv) and checked with
    ``gateway.auth()`` against the stored PBKDF2 hash reference; the
    plaintext is never logged, audited, or persisted.
    """
    gateway_mod = _mod("gateway")
    name = (identity_name or "").strip()
    if not name:
        print("error: --identity <name> is required (who is deciding?)")
        raise SystemExit(2)
    password = getpass.getpass(f"Password for {name} (never echoed): ")
    if not password:
        print("error: password is required")
        raise SystemExit(2)
    try:
        gateway_mod.CybrusGateway().auth(name, password)
    except gateway_mod.GatewayAuthError:
        print(f"error: authentication failed for {name!r} — decision refused")
        raise SystemExit(2) from None
    return name


def _cmd_approve(args) -> int:
    approval = _mod("approval")
    audit_mod = _mod("audit")
    identity = _authenticate_human(args.identity)
    engine = approval.ApprovalEngine()
    try:
        entry = engine.approve(args.id, by=identity)
    except (KeyError, ValueError) as exc:
        print(f"approve failed: {exc}")
        return 2
    audit_mod.AuditEngine().append(
        "approval.approved",
        identity,
        {
            "id": entry["id"][:8],
            "action": entry["action"],
            "subject": entry["subject"],
            "resource": entry["resource"],
            "risk": entry["risk"],
        },
    )
    print(
        f"approved {_short(entry['id'])}: {entry['action']} "
        f"({entry['subject']} → {entry['resource']}, risk {entry['risk']}) "
        f"by {identity}"
    )
    return 0


def _cmd_deny(args) -> int:
    approval = _mod("approval")
    audit_mod = _mod("audit")
    identity = _authenticate_human(args.identity)
    engine = approval.ApprovalEngine()
    try:
        entry = engine.deny(args.id, reason=args.reason or "", by=identity)
    except (KeyError, ValueError) as exc:
        print(f"deny failed: {exc}")
        return 2
    audit_mod.AuditEngine().append(
        "approval.denied",
        identity,
        {
            "id": entry["id"][:8],
            "action": entry["action"],
            "subject": entry["subject"],
            "resource": entry["resource"],
            "risk": entry["risk"],
            "reason": args.reason or "",
        },
    )
    print(f"denied {_short(entry['id'])}: {entry['action']} by {identity}")
    return 0


def _cmd_approvals(args) -> int:
    approval = _mod("approval")
    engine = approval.ApprovalEngine()
    cmd = args.approvals_cmd or "pending"
    if cmd == "pending":
        pendings = engine.pending()
        if not pendings:
            print("no pending approvals")
            return 0
        for entry in pendings:
            print(
                f"[{_short(entry['id'])}] {entry['action']} — "
                f"{entry['subject']} → {entry['resource']} "
                f"(risk {entry['risk']}, expires {entry['expires_at']})"
            )
        return 0
    print(f"unknown approvals command: {cmd}")
    return 2


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------


def _cmd_audit(args) -> int:
    audit = _mod("audit")
    engine = audit.AuditEngine()
    cmd = args.audit_cmd or "tail"
    if cmd == "tail":
        records = engine.tail(args.n)
        if not records:
            print("audit log is empty")
            return 0
        for rec in records:
            print(
                f"[{rec['seq']}] {rec['ts']} {rec['event']} "
                f"actor={rec['actor']} details={rec['details']}"
            )
        return 0
    if cmd == "verify":
        ok, bad = engine.verify()
        if ok:
            print(f"audit chain OK ({engine.count()} records)")
            return 0
        print(f"audit chain BROKEN at record {bad} — investigate before trusting")
        return 1
    print(f"unknown audit command: {cmd}")
    return 2


# ---------------------------------------------------------------------------
# device
# ---------------------------------------------------------------------------


def _cmd_device(args) -> int:
    devices = _mod("devices")
    trust = devices.DeviceTrust()
    cmd = args.device_cmd or "list"
    if cmd == "enroll":
        try:
            rec = trust.enroll(args.id, args.name)
        except ValueError as exc:
            print(f"device enroll failed: {exc}")
            return 2
        print(f"enrolled device {rec['id']} ({rec['name']}) as untrusted")
        return 0
    if cmd == "trust":
        try:
            rec = trust.set_trust(args.id, args.level)
        except (KeyError, ValueError) as exc:
            print(f"device trust failed: {exc}")
            return 2
        print(f"device {rec['id']} trust → {rec['trust']}")
        return 0
    if cmd == "list":
        devs = trust.list()
        if not devs:
            print("no devices enrolled")
            return 0
        for dev in devs:
            print(f"{dev['id']}  {dev['name']}  trust={dev['trust']}")
        return 0
    print(f"unknown device command: {cmd}")
    return 2


# ---------------------------------------------------------------------------
# apikey (gateway — vault-stored named API keys)
# ---------------------------------------------------------------------------


def _open_gateway():
    """Construct a CybrusGateway with the vault unlocked (master password
    via getpass prompt — never argv, never stored)."""
    gateway = _mod("gateway")
    master = getpass.getpass("Vault master password: ")
    if not master:
        raise SystemExit("error: master password is required")
    return gateway.CybrusGateway(vault_passphrase=master)


def _cmd_apikey(args) -> int:
    gateway_mod = _mod("gateway")
    try:
        gw = _open_gateway()
    except SystemExit as exc:
        print(exc)
        return 2
    cmd = args.apikey_cmd or "list"
    try:
        if cmd == "create":
            name, secret = gw.create_api_key(args.name, list(args.scope or []))
            print(f"api key: {name}")
            print(f"scopes: {', '.join(args.scope) if args.scope else '(none)'}")
            print("SAVE THIS KEY NOW — it is shown exactly once:")
            print(secret)
            return 0
        if cmd == "list":
            keys = gw.list_api_keys()
            if not keys:
                print("no api keys")
                return 0
            for entry in keys:
                print(
                    f"{entry['name']}  scopes={','.join(entry['scopes'])} "
                    f"created={entry['created_at']}"
                )
            return 0
        if cmd == "revoke":
            gw.revoke_api_key(args.name)
            print(f"revoked api key {args.name}")
            return 0
    except KeyError as exc:
        print(exc)
        return 1
    except gateway_mod.GatewayError as exc:
        print(f"apikey {cmd} failed: {exc}")
        return 2
    print(f"unknown apikey command: {cmd}")
    return 2


# ---------------------------------------------------------------------------
# route (gateway — the sole external gateway, control plane only)
# ---------------------------------------------------------------------------


def _cmd_route(args) -> int:
    router_mod = _mod("router")
    cmd = args.route_cmd
    if cmd == "list":
        reg = router_mod.RouteRegistry()
        table = reg.list_routes()
        print("internal routes (first-class, always available):")
        for r in table["internal"]:
            print(f"  {r['name']} — {r['description']}")
        print("external routes (deliberate additions only):")
        if not table["external"]:
            print("  (none registered)")
        for r in table["external"]:
            print(
                f"  {r['provider']} [scope: {r['scope']}] "
                f"approved_by={r['approved_by']} added={r['added_at'][:10]}"
            )
        return 0
    if cmd in ("add-external", "remove-external"):
        gateway_mod = _mod("gateway")
        try:
            gw = _open_gateway()
        except SystemExit as exc:
            print(exc)
            return 2
        password = getpass.getpass(f"Password for {args.actor} (never echoed): ")
        if not password:
            print("error: password is required")
            return 2
        try:
            gw.auth(args.actor, password)
        except gateway_mod.GatewayAuthError as exc:
            print(f"route update failed: {exc}")
            return 2
        reg = router_mod.RouteRegistry()
        try:
            if cmd == "add-external":
                record = reg.add_external(
                    args.provider,
                    scope=args.scope,
                    approved_by=args.actor,
                    reason=args.reason,
                )
            else:
                reg.remove_external(args.provider, by=args.actor)
                print(f"removed external route {args.provider}")
                return 0
        except router_mod.RouteError as exc:
            print(f"route update failed: {exc}")
            return 2
        print(f"registered external route {record['provider']} [scope: {record['scope']}]")
        print("  external crossings are marked and audit-logged")
        return 0
    if cmd != "grant":
        print(f"unknown route command: {cmd}")
        return 2
    gateway_mod = _mod("gateway")
    try:
        gw = _open_gateway()
    except SystemExit as exc:
        print(exc)
        return 2
    password = getpass.getpass(f"Password for {args.actor} (never echoed): ")
    if not password:
        print("error: password is required")
        return 2
    try:
        gw.auth(args.actor, password)
    except gateway_mod.GatewayAuthError as exc:
        print(f"route grant failed: {exc}")
        return 2
    try:
        grant = gw.route_external(args.destination, args.actor, args.purpose)
    except gateway_mod.ApprovalRequired as exc:
        print(f"approval required: {exc}")
        print("a verified human must approve it first, e.g.:")
        print(f"  levi cybrus approve {exc.approval_id[:8]} --identity <your-name>")
        print("then retry this command")
        return 3
    except (gateway_mod.PolicyDenied, gateway_mod.GatewayError) as exc:
        print(f"route grant failed: {exc}")
        return 2
    print(f"grant issued: {grant['grant_id'][:8]}")
    print(f"  actor:       {grant['actor']}")
    print(f"  destination: {grant['destination']}")
    print(f"  purpose:     {grant['purpose']}")
    remaining = int(grant["expires_at"] - time.time())
    print(f"  expires in:  {remaining}s")
    print("SAVE THIS GRANT TOKEN NOW — it is shown exactly once:")
    print(grant["token"])
    return 0


# ---------------------------------------------------------------------------
# qid (QID addressing)
# ---------------------------------------------------------------------------


def _cmd_qid(args) -> int:
    qid_mod = _mod("qid")
    cmd = args.qid_cmd
    if cmd != "parse":
        print(f"unknown qid command: {cmd}")
        return 2
    try:
        qid = qid_mod.QID.parse(args.qid)
    except ValueError as exc:
        print(f"qid parse failed: {exc}")
        return 2
    print(f"qid:         {qid}")
    print(f"  shell:       {qid.shell} (1..21)")
    print(f"  form:        {qid.form} (1..315)")
    print(f"  logic_state: {qid.logic_state} (1..13)")
    print(f"  recursion:   {qid.recursion} (0..10^30)")
    phase = qid.phase_name()
    state = qid.state_name()
    print(f"  phase:       {phase if phase else '(spec table not loaded)'}")
    print(f"  state:       {state if state else '(spec table not loaded)'}")
    return 0


def _cmd_money(args) -> int:
    money_mod = _mod("money")
    cmd = getattr(args, "money_cmd", None) or "status"
    gw = money_mod.MoneyGateway()
    if cmd == "status":
        st = money_mod.status()
        print(f"law:            {st['law']}")
        print(f"active rails:   {st['active_rails']}")
        print(f"execute:        {st['execute_posture']}")
        print(f"live rails:     {st['live_rails_exist']}")
        return 0
    if cmd == "rails":
        rails = gw.list_rails()
        if not rails:
            print("no money rails registered (fail-closed: nothing can move money)")
            return 0
        for r in rails:
            print(f"{r.name}: provider={r.provider} approved_by={r.approved_by} status={r.status}")
        return 0
    if cmd == "audit":
        for e in gw.audit_log():
            print(f"{e.get('ts')} {e.get('event')} {e.get('plan_id', e.get('name', ''))}")
        return 0
    print(f"unknown money command: {cmd}")
    return 2


# ---------------------------------------------------------------------------
# registration (mirrors levi/jobs/cli.py: register_*_parser + cmd_*)
# ---------------------------------------------------------------------------


def _register_commands(cy) -> None:
    """Add the cybrus subcommands (status/account/vault/token/apikey/route/
    qid/approve/deny/approvals/audit/device) to an already-created
    ``cybrus`` parser."""
    cmds = cy.add_subparsers(dest="cybrus_cmd")

    cmds.add_parser(
        "status", help="governance overview: policy, approvals, audit, devices"
    )

    ap = cmds.add_parser("account", help="identity accounts")
    asub = ap.add_subparsers(dest="account_cmd")
    ac = asub.add_parser("create", help="create an identity account")
    ac.add_argument("name", help="account name")
    ac.add_argument(
        "--tier",
        default="starter",
        help="tier: founder (keeper-bound) | starter | pro (default: starter)",
    )
    asub.add_parser("list", help="list identity accounts")
    asp = asub.add_parser(
        "set-password",
        help="set/change an identity's password (prompted, never argv)",
    )
    asp.add_argument("name", help="identity name")

    vp = cmds.add_parser("vault", help="encrypted credential vault")
    vsub = vp.add_subparsers(dest="vault_cmd")
    vs = vsub.add_parser("store", help="store a secret (prompted, never argv)")
    vs.add_argument("service", help="service name")
    vs.add_argument("username", help="username")
    vg = vsub.add_parser("get", help="retrieve a secret (prints to stdout)")
    vg.add_argument("service", help="service name")
    vg.add_argument("username", help="username")
    vsub.add_parser("list", help="list stored services (names only, never secrets)")
    vg2 = vsub.add_parser("generate", help="generate a strong password (shown once)")
    vg2.add_argument("--length", type=int, default=24, help="password length >= 12 (default: 24)")
    vo = vsub.add_parser("oauth-store", help="store an OAuth token set (tokens prompted, never argv)")
    vo.add_argument("provider", help="provider name, e.g. github")
    vo.add_argument("--identity", required=True, help="owning identity")
    vo.add_argument("--scope", action="append", default=[], help="OAuth scope (repeatable)")
    vo.add_argument("--expires-in", type=int, default=None, help="access token lifetime in seconds")
    vog = vsub.add_parser("oauth-get", help="retrieve an OAuth token (containment: identity only)")
    vog.add_argument("provider", help="provider name")
    vog.add_argument("--identity", required=True, help="owning identity")
    vol = vsub.add_parser("oauth-list", help="list OAuth tokens (metadata only, never token values)")
    vol.add_argument("--identity", default=None, help="filter to one identity")
    vor = vsub.add_parser("oauth-refresh", help="record a provider refresh (metadata tracked)")
    vor.add_argument("provider", help="provider name")
    vor.add_argument("--identity", required=True, help="owning identity")
    vor.add_argument("--expires-in", type=int, default=None, help="new access token lifetime in seconds")
    vov = vsub.add_parser("oauth-revoke", help="revoke (delete) an OAuth token set")
    vov.add_argument("provider", help="provider name")
    vov.add_argument("--identity", required=True, help="owning identity")

    tp = cmds.add_parser("token", help="scoped API tokens")
    tsub = tp.add_subparsers(dest="token_cmd")
    ti = tsub.add_parser("issue", help="issue a token (plaintext shown once)")
    ti.add_argument(
        "--scope",
        action="append",
        required=True,
        help="scope to grant (repeatable; at least one required)",
    )
    ti.add_argument(
        "--ttl",
        type=int,
        default=30 * 86400,
        help="time-to-live in seconds (default: 30 days)",
    )
    tr = tsub.add_parser("rotate", help="rotate a token (old value dies)")
    tr.add_argument("id", help="token id")
    tv = tsub.add_parser("revoke", help="revoke a token")
    tv.add_argument("id", help="token id")

    apv = cmds.add_parser(
        "approve",
        help="approve a pending high-risk action (requires --identity + password)",
    )
    apv.add_argument("id", help="approval id (or unique prefix)")
    apv.add_argument(
        "--identity",
        required=True,
        help="your identity name — password is prompted, never argv",
    )
    dp = cmds.add_parser(
        "deny",
        help="deny a pending high-risk action (requires --identity + password)",
    )
    dp.add_argument("id", help="approval id (or unique prefix)")
    dp.add_argument(
        "--identity",
        required=True,
        help="your identity name — password is prompted, never argv",
    )
    dp.add_argument("--reason", default="", help="why it was denied")

    app = cmds.add_parser("approvals", help="approval ledger")
    appsub = app.add_subparsers(dest="approvals_cmd")
    appsub.add_parser("pending", help="list pending approvals")

    aup = cmds.add_parser("audit", help="tamper-evident audit log")
    ausub = aup.add_subparsers(dest="audit_cmd")
    at = ausub.add_parser("tail", help="show recent audit records")
    at.add_argument("-n", type=int, default=20, help="records to show")
    ausub.add_parser("verify", help="verify the audit hash chain")

    dvp = cmds.add_parser("device", help="device trust")
    dvsub = dvp.add_subparsers(dest="device_cmd")
    de = dvsub.add_parser("enroll", help="enroll a device (starts untrusted)")
    de.add_argument("id", help="device id")
    de.add_argument("name", help="device name")
    dt = dvsub.add_parser("trust", help="set a device's trust level")
    dt.add_argument("id", help="device id")
    dt.add_argument("level", choices=["untrusted", "known", "trusted"])
    dvsub.add_parser("list", help="list enrolled devices")

    kp = cmds.add_parser("apikey", help="vault-stored named API keys")
    ksub = kp.add_subparsers(dest="apikey_cmd")
    kc = ksub.add_parser("create", help="create a named API key (shown once)")
    kc.add_argument("name", help="key name")
    kc.add_argument(
        "--scope",
        action="append",
        required=True,
        help="scope to grant (repeatable; at least one required)",
    )
    ksub.add_parser("list", help="list API keys (names and scopes only)")
    kr = ksub.add_parser("revoke", help="revoke a named API key")
    kr.add_argument("name", help="key name")

    rp = cmds.add_parser("route", help="platform API router: internal first-class, external by special request")
    rsub = rp.add_subparsers(dest="route_cmd")
    rsub.add_parser("list", help="list internal + registered external routes")
    ra = rsub.add_parser("add-external", help="register an external provider (deliberate, human-approved)")
    ra.add_argument("provider", help="external provider name")
    ra.add_argument("--scope", required=True, help="scope of the external route")
    ra.add_argument("--reason", required=True, help="why this external route is needed")
    ra.add_argument("--actor", required=True, help="authenticated identity approving the addition")
    rr = rsub.add_parser("remove-external", help="decommission an external route")
    rr.add_argument("provider", help="external provider name")
    rr.add_argument("--actor", required=True, help="authenticated identity removing it")
    rg = rsub.add_parser("grant", help="request a short-lived routing grant")
    rg.add_argument("destination", help="external destination")
    rg.add_argument("--purpose", required=True, help="why this route is needed")
    rg.add_argument("--actor", required=True, help="authenticated identity name")

    qp = cmds.add_parser("qid", help="QID addressing (address of thought)")
    qsub = qp.add_subparsers(dest="qid_cmd")
    qparse = qsub.add_parser("parse", help="parse and validate a QID")
    qparse.add_argument("qid", help='qid string, e.g. "3.42.7.0"')

    mp = cmds.add_parser("money", help="Cybrus money gateway — the only path for money movement")
    msub = mp.add_subparsers(dest="money_cmd")
    msub.add_parser("status", help="the money law, rail count, fail-closed posture")
    msub.add_parser("rails", help="list registered money rails (references, never core)")
    msub.add_parser("audit", help="tail the money-gateway audit log (metadata only)")


def register_cybrus_parser(sub) -> None:
    """Hook for the ``levi`` CLI: registers ``levi cybrus ...``."""
    cy = sub.add_parser(
        "cybrus",
        help="Cybrus security & identity layer: policy, approvals, audit, devices",
    )
    _register_commands(cy)


def cmd_cybrus(args: argparse.Namespace) -> int:
    cmd = getattr(args, "cybrus_cmd", None) or "status"
    if cmd == "status":
        return _cmd_status()
    if cmd == "account":
        return _cmd_account(args)
    if cmd == "vault":
        return _cmd_vault(args)
    if cmd == "token":
        return _cmd_token(args)
    if cmd == "apikey":
        return _cmd_apikey(args)
    if cmd == "route":
        return _cmd_route(args)
    if cmd == "qid":
        return _cmd_qid(args)
    if cmd == "money":
        return _cmd_money(args)
    if cmd == "approve":
        return _cmd_approve(args)
    if cmd == "deny":
        return _cmd_deny(args)
    if cmd == "approvals":
        return _cmd_approvals(args)
    if cmd == "audit":
        return _cmd_audit(args)
    if cmd == "device":
        return _cmd_device(args)
    print(f"unknown cybrus command: {cmd}")
    return 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="levi.cybrus",
        description="Cybrus — LEVI's Security & Identity Layer (local, defensive)",
    )
    # Same subcommands as `levi cybrus`, without the extra nesting level.
    _register_commands(parser)
    args = parser.parse_args(argv)
    return cmd_cybrus(args)


if __name__ == "__main__":
    sys.exit(main())
