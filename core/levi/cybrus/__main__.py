"""Cybrus CLI — ``python -m levi.cybrus`` and the ``levi cybrus`` hook.

Subcommands: status, account create/list/set-password, vault store/get/list/
generate/import-csv/import-receipt/oauth-store/oauth-get/oauth-list/
oauth-refresh/oauth-revoke,
token issue/rotate/revoke, apikey create/list/revoke, route list/
add-external/remove-external/grant, qid parse, broker provision/activate/
list/rotate/retire/apikey-store/apikey-get/apikey-list/apikey-revoke/
oauth-start/oauth-callback/oauth-complete/oauth-refresh/oauth-status/status,
money status/rails/audit, approve, deny, approvals pending, audit
tail/verify, device enroll/trust/list.

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
        if cmd == "import-csv":
            return _cmd_vault_import_csv(args, vault)
        if cmd == "import-receipt":
            return _cmd_vault_import_receipt(vault)
    except AttributeError as exc:
        print(f"error: vault module API mismatch ({exc}) — see levi/cybrus/vault.py")
        return 2
    print(f"unknown vault command: {cmd}")
    return 2


def _cmd_vault_import_csv(args, vault) -> int:
    """Import a Google Passwords CSV: counts only, never secrets (L1).

    On success prints exactly one line via ``vault_import.describe_import``
    — ``imported=%d duplicates=%d invalid=%d services=%d`` plus
    `` — no changes applied`` when zero rows were imported (L9: a no-op
    never looks like a silent success). On failure prints
    ``error: import failed: <reason>`` and returns 1; the vault is left
    untouched (the importer validates the whole CSV before any write).
    The vault is already open (master passphrase via getpass in
    ``_open_vault`` — never argv). The CSV path comes from argv, which
    is fine: a file path is not a secret.
    """
    vi = _mod("vault_import")
    try:
        counts = vi.import_google_csv(args.csv_path, vault)
    except (vi.CsvImportError, vi.VaultError, ValueError) as exc:
        print(f"error: import failed: {exc}")
        return 1
    print(vi.describe_import(counts))
    return 0


def _cmd_vault_import_receipt(vault) -> int:
    """Metadata-only receipt: counts + service names (same order as ``list``).

    Entry counts come from a read-only load of the entry store — no write
    pass. NEVER prints usernames, URLs, or secrets (L1).

    Honesty note: ``csv-import-fallbacks`` counts service names carrying
    the importer's ``csv-import-`` fallback prefix. It cannot distinguish
    a hand-stored service that happens to reuse that prefix — the count
    is exact for what the name carries, not for how the service got there.
    """
    entries = vault._load_entries()  # read-only: no save follows
    services = sorted(entries)
    fallbacks = sum(1 for s in services if s.startswith("csv-import-"))
    total_entries = sum(len(entries[s]) for s in services)
    print(
        "services=%d entries=%d csv-import-fallbacks=%d"
        % (len(services), total_entries, fallbacks)
    )
    for service in services:
        print(service)
    return 0


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
    guard_mod = _mod("device_guard")
    devices = _mod("devices")
    guard = guard_mod.DeviceGuard()
    cmd = args.device_cmd or "list"
    if cmd == "enroll":
        # First sighting: enroll untrusted + raise the alert (LEFT-GUARD).
        try:
            record, approval_id = guard.sighting(
                args.id, args.name, fingerprint=getattr(args, "fingerprint", None)
            )
        except ValueError as exc:
            print(f"device enroll failed: {exc}")
            return 2
        print(f"enrolled device {record['id']} ({record['name']}) as untrusted")
        print(
            f"ALERT: new device sighted — approval raised: {approval_id[:8]} "
            f"(levi cybrus approve {approval_id[:8]}, then "
            f"levi cybrus device trust {record['id']} <level>)"
        )
        return 0
    if cmd == "request":
        try:
            approval_id = guard.request_trust(args.id, getattr(args, "level", "known"))
        except (KeyError, ValueError) as exc:
            print(f"device request failed: {exc}")
            return 2
        print(
            f"trust-grant approval raised for {args.id} -> {getattr(args, 'level', 'known')}: "
            f"{approval_id[:8]} (levi cybrus approve {approval_id[:8]}, then "
            f"levi cybrus device trust {args.id} <level>)"
        )
        return 0
    if cmd == "trust":
        # Promotion consumes a human-approved approval, single-use.
        try:
            record = guard.grant(args.id, args.level, getattr(args, "approval", ""))
        except devices.TrustGrantError as exc:
            print(f"device trust refused: {exc}")
            return 2
        except (KeyError, ValueError) as exc:
            print(f"device trust failed: {exc}")
            return 2
        print(f"device {record['id']} trust → {record['trust']}")
        return 0
    if cmd == "seen":
        try:
            result = guard.seen(args.id, fingerprint=getattr(args, "fingerprint", None))
        except KeyError as exc:
            print(f"device seen failed: {exc}")
            return 2
        if result["status"] == "spoof_suspect":
            print(
                f"ALERT: device {args.id} fingerprint mismatch — demoted to "
                f"untrusted, re-approval raised: {result['approval_id'][:8]}"
            )
            return 1
        print(f"device {args.id}: {result['status']} (trust={result['trust']})")
        return 0
    if cmd == "challenge":
        try:
            result = guard.challenge(args.id, getattr(args, "reason", ""))
        except KeyError as exc:
            print(f"device challenge failed: {exc}")
            return 2
        print(
            f"device {args.id} challenged → untrusted; re-approval raised: "
            f"{result['approval_id'][:8]}"
        )
        return 0
    if cmd == "decay":
        receipts = guard.sweep_decay()
        if not receipts:
            print("no stale devices demoted")
            return 0
        for r in receipts:
            print(
                f"{r['device_id']}: {r['from']} → {r['to']} "
                f"(stale {r['stale_days']}d)"
            )
        return 0
    if cmd == "revoke":
        try:
            guard.revoke(args.id, getattr(args, "reason", ""))
        except KeyError as exc:
            print(f"device revoke failed: {exc}")
            return 2
        print(f"device {args.id} revoked")
        return 0
    if cmd == "verify":
        bad = guard.verify_consistency()
        if not bad:
            print("device registry consistent with audit receipts")
            return 0
        print("ALERT: device registry inconsistent with audit receipts:")
        for b in bad:
            print(f"  {b['device_id']}: trust={b['trust']} (no grant receipt)")
        return 1
    if cmd == "list":
        devs = guard.list()
        if not devs:
            print("no devices enrolled")
            return 0
        for dev in devs:
            pending = f" approval={dev['pending_approval_id'][:8]}" if dev.get("pending_approval_id") else ""
            print(
                f"{dev['id']}  {dev['name']}  trust={dev['trust']}  "
                f"last_seen={dev['last_seen']}  fp={'bound' if dev.get('fingerprint_bound') else 'none'}{pending}"
            )
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


def _cmd_watchdog(args) -> int:
    import json as _json

    watchdog = _mod("watchdog")
    cmd = getattr(args, "watchdog_cmd", None) or "sweep"
    if cmd == "sweep":
        receipt = watchdog.sweep()
        print(_json.dumps(receipt, indent=2, default=str))
        return 1 if receipt["blind_count"] else 0
    if cmd == "watch":
        watchdog.Watchdog().watch(interval_seconds=args.interval)
        return 0
    if cmd == "status":
        print(_json.dumps(watchdog.describe_posture(), indent=2))
        barks = watchdog.recent_barks(5)
        print(f"recent barks: {len(barks)}")
        return 0
    if cmd == "tail":
        for b in watchdog.recent_barks(args.n):
            d = b.get("details", {})
            print(f"{b.get('ts')} {d.get('direction')}/{d.get('signal')} "
                  f"{d.get('severity')} {d.get('evidence_hash','')[:12]}")
        return 0
    print(f"unknown watchdog command: {cmd}")
    return 2


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
# broker (third-party credential broker — the automated Bitwarden)
# ---------------------------------------------------------------------------


def _open_broker():
    """Construct a CredentialBroker with the vault unlocked (master password
    via getpass prompt — never argv, never stored)."""
    broker = _mod("broker")
    master = getpass.getpass("Vault master password: ")
    if not master:
        raise SystemExit("error: master password is required")
    return broker.CredentialBroker(master)


def _broker_approval_required(exc) -> int:
    print(f"approval required: {exc}")
    print("a verified human must approve it first, e.g.:")
    print(f"  levi cybrus approve {exc.approval_id[:8]} --identity <your-name>")
    print("then retry this command")
    return 3


def _cmd_broker_provision(args, br, broker_mod) -> int:
    try:
        record, password = br.provision(
            args.platform,
            args.signup_url,
            identity=args.identity,
            username=args.username,
        )
    except broker_mod.BrokerApprovalRequired as exc:
        return _broker_approval_required(exc)
    except broker_mod.BrokerError as exc:
        print(f"broker provision failed: {exc}")
        return 2
    print(f"provisioned {record['platform']}/{record['username']} (id {record['id'][:8]})")
    print(f"  signup url: {record['signup_url']}")
    print("  complete the signup on the site, then run:")
    print(f"    levi cybrus broker activate {record['id'][:8]} --identity {record['identity']}")
    print("SAVE THIS PASSWORD NOW — it is shown exactly once:")
    print(password)
    return 0


def _cmd_broker(args) -> int:
    broker_mod = _mod("broker")
    try:
        br = _open_broker()
    except SystemExit as exc:
        print(exc)
        return 2
    cmd = args.broker_cmd
    try:
        if cmd == "provision":
            return _cmd_broker_provision(args, br, broker_mod)
        if cmd == "activate":
            record = br.activate(args.account_id, identity=args.identity)
            print(f"activated {record['platform']}/{record['username']} (id {record['id'][:8]})")
            return 0
        if cmd == "list":
            accounts = br.list_accounts(identity=args.identity)
            if not accounts:
                print("no broker accounts" + (f" for {args.identity}" if args.identity else ""))
                return 0
            for acc in accounts:
                print(
                    f"{acc['id'][:8]}  {acc['platform']}/{acc['username']} "
                    f"identity={acc['identity']} status={acc['status']}"
                )
            return 0
        if cmd == "rotate":
            try:
                record, password = br.rotate(args.account_id, identity=args.identity)
            except broker_mod.BrokerApprovalRequired as exc:
                return _broker_approval_required(exc)
            print(f"rotated password for {record['platform']}/{record['username']}")
            print("SAVE THIS PASSWORD NOW — it is shown exactly once:")
            print(password)
            return 0
        if cmd == "retire":
            try:
                record = br.retire(args.account_id, identity=args.identity)
            except broker_mod.BrokerApprovalRequired as exc:
                return _broker_approval_required(exc)
            print(f"retired {record['platform']}/{record['username']} (vault entry deleted)")
            return 0
        if cmd == "apikey-store":
            key_material = getpass.getpass(
                f"API key for {args.platform}/{args.label} (never echoed): "
            )
            if not key_material:
                print("error: api key is required")
                return 2
            try:
                record = br.store_key(
                    args.platform,
                    args.label,
                    key_material,
                    identity=args.identity,
                    scopes=args.scope or [],
                    retrieval_method=args.method,
                )
            except broker_mod.BrokerApprovalRequired as exc:
                return _broker_approval_required(exc)
            print(f"stored api key {record['platform']}/{record['label']} (id {record['id'][:8]})")
            print(f"  retrieval method: {record['retrieval_method']}")
            return 0
        if cmd == "apikey-get":
            try:
                key_material = br.retrieve_key(args.label, identity=args.identity)
            except broker_mod.BrokerApprovalRequired as exc:
                return _broker_approval_required(exc)
            print(f"api key {args.label} (handle with care):")
            print(key_material)
            return 0
        if cmd == "apikey-list":
            keys = br.list_keys(identity=args.identity)
            if not keys:
                print("no broker api keys" + (f" for {args.identity}" if args.identity else ""))
                return 0
            for k in keys:
                print(
                    f"{k['id'][:8]}  {k['platform']}/{k['label']} "
                    f"identity={k['identity']} status={k['status']} "
                    f"method={k['retrieval_method']} "
                    f"scopes={','.join(k['scopes']) if k['scopes'] else '(none)'}"
                )
            return 0
        if cmd == "apikey-revoke":
            try:
                record = br.revoke_key(args.label, identity=args.identity)
            except broker_mod.BrokerApprovalRequired as exc:
                return _broker_approval_required(exc)
            print(f"revoked api key {record['platform']}/{record['label']}")
            return 0
        if cmd == "oauth-start":
            try:
                result = br.oauth_start(
                    args.platform,
                    args.client_id,
                    args.authorize_url,
                    args.redirect_url,
                    identity=args.identity,
                    scopes=args.scope or [],
                )
            except broker_mod.BrokerApprovalRequired as exc:
                return _broker_approval_required(exc)
            print(f"oauth flow started: {result['flow_id'][:8]} ({args.platform})")
            print("open this URL in your browser to authorize:")
            print(result["authorization_url"])
            print("then capture the redirect code with:")
            print(
                f"  levi cybrus broker oauth-callback {result['flow_id'][:8]} "
                f"--identity {args.identity} --state {result['state']}"
            )
            return 0
        if cmd == "oauth-callback":
            code = getpass.getpass("Authorization code from the redirect (never echoed): ")
            if not code:
                print("error: authorization code is required")
                return 2
            result = br.oauth_callback(
                args.flow_id, code, args.state, identity=args.identity
            )
            print(f"flow {result['flow_id'][:8]}: {result['status']}")
            print("exchange the code for tokens in your browser/client, then run:")
            print(
                f"  levi cybrus broker oauth-complete {result['flow_id'][:8]} "
                f"--identity {args.identity}"
            )
            return 0
        if cmd == "oauth-complete":
            access = getpass.getpass("Access token (never echoed): ")
            if not access:
                print("error: access token is required")
                return 2
            refresh = getpass.getpass("Refresh token (optional, Enter to skip): ")
            try:
                meta = br.oauth_complete(
                    args.flow_id,
                    identity=args.identity,
                    access_token=access,
                    refresh_token=refresh or None,
                    expires_in=args.expires_in,
                )
            except broker_mod.BrokerApprovalRequired as exc:
                return _broker_approval_required(exc)
            print(f"flow {meta['flow_id'][:8]}: {meta['status']} ({meta['platform']})")
            print(f"  scopes:     {', '.join(meta['scopes']) if meta['scopes'] else '(none)'}")
            print(f"  expires_at: {meta['expires_at'] or 'never'}")
            return 0
        if cmd == "oauth-refresh":
            access = getpass.getpass("New access token (never echoed): ")
            if not access:
                print("error: access token is required")
                return 2
            refresh = getpass.getpass("New refresh token (optional, Enter to keep old): ")
            try:
                meta = br.oauth_refresh(
                    args.flow_id,
                    identity=args.identity,
                    new_access_token=access,
                    new_refresh_token=refresh or None,
                    expires_in=args.expires_in,
                )
            except broker_mod.BrokerApprovalRequired as exc:
                return _broker_approval_required(exc)
            print(f"flow {meta['flow_id'][:8]}: {meta['status']} (refresh #{meta['refresh_count']})")
            return 0
        if cmd == "oauth-status":
            flows = br.oauth_status(identity=args.identity)
            if not flows:
                print("no oauth flows" + (f" for {args.identity}" if args.identity else ""))
                return 0
            for f in flows:
                due = "REFRESH-DUE" if f["needs_refresh"] else "ok"
                print(
                    f"{f['flow_id'][:8]}  {f['platform']} identity={f['identity']} "
                    f"status={f['status']} refresh={due}"
                )
            return 0
        if cmd == "status":
            st = br.status(identity=args.identity)
            print("Cybrus credential broker (third-party platforms)")
            print(f"  accounts:  {st['accounts']}")
            print(f"  api keys:  {st['api_keys']}")
            print(f"  oauth:     {st['oauth_flows']} flows "
                  f"({', '.join(f'{k}={v}' for k, v in st['oauth_by_status'].items()) or 'none'})")
            print(f"  refresh-due: {st['oauth_refresh_due']}")
            return 0
    except broker_mod.BrokerError as exc:
        print(f"broker {cmd} failed: {exc}")
        return 2
    print(f"unknown broker command: {cmd}")
    return 2


# ---------------------------------------------------------------------------
# founder (broker founder edition — live provisioning, FL1/FL8)
# ---------------------------------------------------------------------------


def _open_founder(args):
    """Open (FounderBroker, FounderSession).

    Secrets via getpass prompts only — never argv, never stored. The
    session authenticates the service identity through the gateway; every
    provisioning transition below derives its identity from it (FL1).
    """
    fmod = _mod("broker_founder")
    fgmod = _mod("founder_gateway")
    gwmod = _mod("gateway")
    master = getpass.getpass("Vault master password: ")
    if not master:
        raise SystemExit("error: master password is required")
    identity = args.identity
    if not identity:
        raise SystemExit("error: --identity is required (the service identity, e.g. chauncey-ops)")
    credential = getpass.getpass(f"Password for {identity}: ")
    if not credential:
        raise SystemExit("error: identity password is required")
    gateway = gwmod.CybrusGateway(vault_passphrase=master)
    try:
        session = fgmod.FounderSession.authenticate(identity, credential, gateway=gateway)
    except fgmod.FounderSessionError as exc:
        raise SystemExit(f"error: {exc}")
    broker = fmod.FounderBroker(master)
    return broker, session, fmod, fgmod


def _founder_approval_required(exc) -> int:
    print(f"approval required: {exc}")
    print("a verified human must approve it first, e.g.:")
    print(f"  levi cybrus approve {exc.approval_id[:8]} --identity <your-name>")
    print("then retry this command")
    return 3


def _cmd_founder(args) -> int:
    cmd = args.founder_cmd
    if cmd in ("provision", "mint", "execute", "resume", "step-ok", "activate"):
        broker, session, fmod, fgmod = _open_founder(args)
    else:
        fmod = _mod("broker_founder")
        fgmod = _mod("founder_gateway")
        broker, session = None, None
    try:
        if cmd == "provision":
            contact = input("Contact phone/email for verification: ").strip()
            if not contact:
                print("error: contact is required")
                return 2
            try:
                plan = broker.provision_plan(
                    args.platform, session=session, username=args.username, contact=contact
                )
            except fmod.BrokerApprovalRequired as exc:
                return _founder_approval_required(exc)
            print(f"planned {plan['platform']} for {plan['username']} (plan {plan['plan_id'][:8]})")
            print(f"  steps: {plan['step_count']}  digest: {plan['step_digest']}")
            print("next:")
            print(f"  levi cybrus founder mint {plan['plan_id'][:8]} --identity {args.identity}")
            return 0
        if cmd == "plans":
            # Read-side: the vault is never opened (lazy). A dummy passphrase
            # keeps construction honest without touching secrets.
            br = fmod.FounderBroker("unopened")
            plans = br.list_plans(identity=args.identity)
            if not plans:
                print("no founder plans" + (f" for {args.identity}" if args.identity else ""))
                return 0
            for pl in plans:
                print(f"{pl['plan_id'][:8]}  {pl['platform']}  {pl['username']}  status={pl['status']}")
            return 0
        if cmd == "plan":
            br = fmod.FounderBroker("unopened")
            pl = br.get_plan(_resolve_plan_id(br, args.plan_id), identity=args.identity)
            print(f"plan {pl['plan_id'][:8]}: {pl['platform']} for {pl['username']}")
            print(f"  status: {pl['status']}  steps: {pl['step_count']}  digest: {pl['step_digest']}")
            return 0
        if cmd == "status":
            br = fmod.FounderBroker("unopened")
            st = br.status(identity=args.identity)
            print("Cybrus broker founder edition (live provisioning)")
            print(f"  plans: {st['plans']}  by status: {st['by_status']}")
            print(f"  platforms: {', '.join(st['platforms'])}")
            return 0
        if cmd == "mint":
            try:
                plan, password = broker.mint_credential(_resolve_plan_id(broker, args.plan_id), session=session)
            except fmod.BrokerApprovalRequired as exc:
                return _founder_approval_required(exc)
            print(f"credential minted for plan {plan['plan_id'][:8]} (status: {plan['status']})")
            print("SAVE THIS PASSWORD NOW — it is shown exactly once:")
            print(password)
            print("next:")
            print(f"  levi cybrus founder execute {plan['plan_id'][:8]} --identity {args.identity}")
            return 0
        if cmd == "execute":
            opmod = _mod("broker_operator")
            try:
                broker.begin_execution(_resolve_plan_id(broker, args.plan_id), session=session)
            except fmod.BrokerApprovalRequired as exc:
                return _founder_approval_required(exc)
            channel = opmod.BrowserTaskChannel()  # unbound until the operator binds a driver (FL6)
            try:
                result = broker.run_to_checkpoint(
                    _resolve_plan_id(broker, args.plan_id), channel, session=session
                )
            except opmod.OperatorChannelError as exc:
                print(f"plan is executing; operator channel: {exc}")
                print("bind a browser-task executor to drive the signup, or drive it by hand:")
                print(f"  levi cybrus founder resume <plan> --checkpoint <id> --identity {args.identity}")
                return 4
            return _print_checkpoint_or_done(result, args)
        if cmd == "resume":
            plan_id = _resolve_plan_id(broker, args.plan_id)
            current = broker.next_step(plan_id, session=session)
            if current.get("done"):
                print("plan already complete — run 'activate' to register it")
                return 0
            kind = current.get("checkpoint")
            checkpoint_id = current.get("id")
            if args.checkpoint and args.checkpoint != checkpoint_id:
                print(f"error: current checkpoint is {checkpoint_id!r}, not {args.checkpoint!r}")
                return 2
            payload, attested = _build_checkpoint_payload(kind, args)
            if payload is None:
                return 2
            try:
                plan = broker.human_input(
                    plan_id, checkpoint_id, payload, session=session, human_attestation=attested
                )
            except fmod.BrokerApprovalRequired as exc:
                return _founder_approval_required(exc)
            except fmod.FounderTermsRefused as exc:
                print(f"terms refused: {exc}")
                return 2
            print(f"checkpoint {checkpoint_id!r} satisfied (plan {plan['plan_id'][:8]}, status: {plan['status']})")
            return 0
        if cmd == "step-ok":
            plan_id = _resolve_plan_id(broker, args.plan_id)
            note = args.note or ""
            try:
                plan = broker.report_step(plan_id, args.step, True, note, session=session)
            except fmod.FounderPlanFailed as exc:
                print(f"plan failed: {exc}")
                return 2
            print(f"step {args.step!r} recorded ok (plan {plan['plan_id'][:8]}, status: {plan['status']})")
            return 0
        if cmd == "activate":
            try:
                result = broker.complete_execution(_resolve_plan_id(broker, args.plan_id), session=session)
            except fmod.BrokerApprovalRequired as exc:
                return _founder_approval_required(exc)
            print(f"plan complete: {result['platform']} account {result['username']} is now active")
            print(f"  broker account id: {result['account_id'][:8]}")
            return 0
    except fmod.BrokerError as exc:
        print(f"founder {cmd} failed: {exc}")
        return 2
    except fgmod.FounderSessionError as exc:
        print(f"founder {cmd} failed: session: {exc}")
        return 2
    print(f"unknown founder command: {cmd}")
    return 2


def _resolve_plan_id(broker, plan_id):
    """Accept a full plan id or a unique prefix."""
    fmod = _mod("broker_founder")
    plans = broker.list_plans()
    matches = [p for p in plans if p["plan_id"].startswith(plan_id)]
    if not matches:
        raise fmod.FounderBrokerError(f"unknown founder plan id: {plan_id!r}")
    if len(matches) > 1:
        raise fmod.FounderBrokerError(
            f"ambiguous plan prefix {plan_id!r}: {len(matches)} plans match"
        )
    return matches[0]["plan_id"]


def _print_checkpoint_or_done(result, args) -> int:
    if result.get("done"):
        print("all steps consumed — activate the plan to register the account:")
        print(f"  levi cybrus founder activate <plan> --identity {args.identity}")
        return 0
    print(f"checkpoint {result['id']!r} ({result.get('checkpoint')}): {result.get('description')}")
    print("resume it with:")
    base = f"levi cybrus founder resume <plan> --checkpoint {result['id']} --identity {args.identity}"
    kind = result.get("checkpoint")
    if kind == "verification_code":
        print("  " + base + "  (you will be prompted for the code)")
    elif kind == "terms_acceptance":
        print("  " + base + " --attest-human  (read the terms yourself first)")
    elif kind == "identity_kyc":
        print("  " + base + " --provided  (after entering your details in your own browser)")
    elif kind == "payment_link":
        print("  " + base + " --linked   (or --skipped)")
    return 0


def _build_checkpoint_payload(kind, args):
    """Build the human_input payload from CLI flags. Returns (payload, attested)."""
    if kind == "verification_code":
        code = getpass.getpass("Verification code (from your device): ").strip()
        if not code:
            print("error: a code is required")
            return None, False
        return {"code": code}, False
    if kind == "terms_acceptance":
        if not args.attest_human:
            print("error: pass --attest-human only after YOU have read and accepted the terms")
            print("the broker never accepts terms on your behalf")
            return None, False
        return {"accepted": True}, True
    if kind == "identity_kyc":
        if not args.provided:
            print("error: pass --provided after entering your details in your own browser session")
            return None, False
        return {"provided": True}, False
    if kind == "payment_link":
        if args.linked and args.skipped:
            print("error: --linked and --skipped are mutually exclusive")
            return None, False
        if args.linked:
            return {"linked": True}, False
        if args.skipped:
            return {"skipped": True}, False
        print("error: pass --linked or --skipped")
        return None, False
    print(f"error: unknown checkpoint kind {kind!r}")
    return None, False


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
    vic = vsub.add_parser(
        "import-csv", help="import a Google Password Manager CSV (counts only, never secrets)"
    )
    vic.add_argument("csv_path", help="path to the Google Passwords CSV export")
    vsub.add_parser(
        "import-receipt",
        help="metadata-only import receipt (counts + service names, never secrets)",
    )

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
    de = dvsub.add_parser("enroll", help="enroll a device (starts untrusted; raises the alert)")
    de.add_argument("id", help="device id")
    de.add_argument("name", help="device name")
    de.add_argument("--fingerprint", default=None, help="bind a device fingerprint on first sight")
    dr = dvsub.add_parser("request", help="raise a trust-grant approval for a device")
    dr.add_argument("id", help="device id")
    dr.add_argument("--level", default="known", choices=["untrusted", "known", "trusted"], help="requested trust level")
    dt = dvsub.add_parser("trust", help="promote a device (consumes a human-approved approval, single-use)")
    dt.add_argument("id", help="device id")
    dt.add_argument("level", choices=["untrusted", "known", "trusted"])
    dt.add_argument("--approval", required=True, help="approved device.trust_grant approval id")
    ds = dvsub.add_parser("seen", help="heartbeat for a device (fingerprint mismatch demotes + re-alerts)")
    ds.add_argument("id", help="device id")
    ds.add_argument("--fingerprint", default=None, help="presented device fingerprint")
    dc = dvsub.add_parser("challenge", help="demote a device to untrusted and re-raise the alert")
    dc.add_argument("id", help="device id")
    dc.add_argument("--reason", default="", help="why the device was challenged")
    dvsub.add_parser("decay", help="demote stale devices (trusted->known at 30d, known->untrusted at 60d)")
    drv = dvsub.add_parser("revoke", help="remove a device (audited)")
    drv.add_argument("id", help="device id")
    drv.add_argument("--reason", default="", help="why the device was revoked")
    dvsub.add_parser("verify", help="cross-check registry trust against audit grant receipts")
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

    wd = cmds.add_parser("watchdog", help="Quetta-Pan watchdog: four-direction anomaly monitor")
    wdsub = wd.add_subparsers(dest="watchdog_cmd")
    wdsub.add_parser("sweep", help="run one poll pass over the four directions, barking anomalies")
    www = wdsub.add_parser("watch", help="foreground poll loop (no daemon persistence)")
    www.add_argument("--interval", type=float, default=300.0, help="seconds between sweeps")
    wdsub.add_parser("status", help="honest backend posture of the watchdog")
    wt = wdsub.add_parser("tail", help="show recent watchdog barks")
    wt.add_argument("-n", type=int, default=20, help="barks to show")

    mp = cmds.add_parser("money", help="Cybrus money gateway — the only path for money movement")
    msub = mp.add_subparsers(dest="money_cmd")
    msub.add_parser("status", help="the money law, rail count, fail-closed posture")
    msub.add_parser("rails", help="list registered money rails (references, never core)")
    msub.add_parser("audit", help="tail the money-gateway audit log (metadata only)")

    bp = cmds.add_parser(
        "broker",
        help="third-party credential broker: provisioned accounts, external API keys, OAuth flows",
    )
    bsub = bp.add_subparsers(dest="broker_cmd")
    bprov = bsub.add_parser(
        "provision",
        help="provision a third-party account record (human-gated; password shown once)",
    )
    bprov.add_argument("--platform", required=True, help="platform name, e.g. github")
    bprov.add_argument("--signup-url", required=True, help="the platform's signup URL")
    bprov.add_argument("--identity", required=True, help="owning identity")
    bprov.add_argument("--username", default=None, help="login username on the platform (default: identity)")
    bact = bsub.add_parser(
        "activate",
        help="mark a provisioned account active (signup confirmed on the site)",
    )
    bact.add_argument("account_id", help="broker account id (or unique prefix)")
    bact.add_argument("--identity", required=True, help="owning identity")
    blist = bsub.add_parser("list", help="list broker accounts (metadata only)")
    blist.add_argument("--identity", default=None, help="filter to one identity")
    brot = bsub.add_parser(
        "rotate", help="rotate an account password (human-gated; shown once)"
    )
    brot.add_argument("account_id", help="broker account id (or unique prefix)")
    brot.add_argument("--identity", required=True, help="owning identity")
    bret = bsub.add_parser(
        "retire", help="retire an account (human-gated; vault entry deleted)"
    )
    bret.add_argument("account_id", help="broker account id (or unique prefix)")
    bret.add_argument("--identity", required=True, help="owning identity")
    bks = bsub.add_parser(
        "apikey-store",
        help="record a third-party API key (human-gated; key prompted, never argv)",
    )
    bks.add_argument("--platform", required=True, help="platform name")
    bks.add_argument("--label", required=True, help="key label")
    bks.add_argument("--identity", required=True, help="owning identity")
    bks.add_argument("--scope", action="append", default=[], help="key scope (repeatable)")
    bks.add_argument(
        "--method",
        default="console",
        choices=["console", "cli", "api", "import"],
        help="how the key was obtained (default: console)",
    )
    bkg = bsub.add_parser(
        "apikey-get",
        help="retrieve a recorded API key (human-gated, owner only)",
    )
    bkg.add_argument("--label", required=True, help="key label")
    bkg.add_argument("--identity", required=True, help="owning identity")
    bkl = bsub.add_parser("apikey-list", help="list recorded API keys (metadata only)")
    bkl.add_argument("--identity", default=None, help="filter to one identity")
    bkr = bsub.add_parser(
        "apikey-revoke", help="revoke a recorded API key (human-gated)"
    )
    bkr.add_argument("--label", required=True, help="key label")
    bkr.add_argument("--identity", required=True, help="owning identity")
    bos = bsub.add_parser(
        "oauth-start",
        help="start an OAuth2 authorization-code flow (human-gated; PKCE/S256)",
    )
    bos.add_argument("--platform", required=True, help="platform name")
    bos.add_argument("--client-id", required=True, help="OAuth client id")
    bos.add_argument("--authorize-url", required=True, help="provider authorization endpoint")
    bos.add_argument("--redirect-url", required=True, help="registered redirect URI")
    bos.add_argument("--identity", required=True, help="owning identity")
    bos.add_argument("--scope", action="append", default=[], help="OAuth scope (repeatable)")
    boc = bsub.add_parser(
        "oauth-callback",
        help="capture the authorization code from the provider redirect",
    )
    boc.add_argument("flow_id", help="oauth flow id (or unique prefix)")
    boc.add_argument("--identity", required=True, help="owning identity")
    boc.add_argument("--state", required=True, help="state returned by the provider")
    bcmp = bsub.add_parser(
        "oauth-complete",
        help="store the exchanged token set (human-gated; tokens prompted, never argv)",
    )
    bcmp.add_argument("flow_id", help="oauth flow id (or unique prefix)")
    bcmp.add_argument("--identity", required=True, help="owning identity")
    bcmp.add_argument("--expires-in", type=int, default=None, help="access token lifetime in seconds")
    brf = bsub.add_parser(
        "oauth-refresh",
        help="record a provider token refresh (human-gated; tokens prompted, never argv)",
    )
    brf.add_argument("flow_id", help="oauth flow id (or unique prefix)")
    brf.add_argument("--identity", required=True, help="owning identity")
    brf.add_argument("--expires-in", type=int, default=None, help="new access token lifetime in seconds")
    bst = bsub.add_parser("oauth-status", help="oauth flow states (metadata only)")
    bst.add_argument("--identity", default=None, help="filter to one identity")
    bsub.add_parser("status", help="broker overview: accounts, keys, flows, refresh-due")

    fp = cmds.add_parser(
        "founder",
        help="broker founder edition: live provisioning plans with human checkpoints",
    )
    fsub = fp.add_subparsers(dest="founder_cmd")
    fprov = fsub.add_parser(
        "provision",
        help="create a live-provisioning plan (session-authenticated, human-gated)",
    )
    fprov.add_argument("--platform", required=True, choices=["cashapp", "paypal"], help="platform to provision")
    fprov.add_argument("--username", default=None, help="login username on the platform (default: identity)")
    fprov.add_argument("--identity", required=True, help="service identity (e.g. chauncey-ops)")
    fsub.add_parser("plans", help="list provisioning plans (metadata only)").add_argument(
        "--identity", default=None, help="filter to one identity"
    )
    fplan = fsub.add_parser("plan", help="show one plan (metadata only)")
    fplan.add_argument("plan_id", help="plan id (or unique prefix)")
    fplan.add_argument("--identity", default=None, help="filter to one identity")
    fsub.add_parser("status", help="founder broker overview").add_argument(
        "--identity", default=None, help="filter to one identity"
    )
    fmint = fsub.add_parser("mint", help="mint the plan password (session-authenticated, human-gated; shown once)")
    fmint.add_argument("plan_id", help="plan id (or unique prefix)")
    fmint.add_argument("--identity", required=True, help="service identity")
    fexec = fsub.add_parser(
        "execute",
        help="begin execution and drive to the first human checkpoint (needs a bound browser-task driver, else honest stop)",
    )
    fexec.add_argument("plan_id", help="plan id (or unique prefix)")
    fexec.add_argument("--identity", required=True, help="service identity")
    fstep = fsub.add_parser(
        "step-ok",
        help="report a machine step done by hand (plan fidelity enforced)",
    )
    fstep.add_argument("plan_id", help="plan id (or unique prefix)")
    fstep.add_argument("--step", required=True, help="step id just performed")
    fstep.add_argument("--note", default="", help="short outcome note (no secrets)")
    fstep.add_argument("--identity", required=True, help="service identity")
    fres = fsub.add_parser(
        "resume",
        help="satisfy the current human checkpoint and resume (human-gated)",
    )
    fres.add_argument("plan_id", help="plan id (or unique prefix)")
    fres.add_argument("--checkpoint", default=None, help="checkpoint id (must match the current one)")
    fres.add_argument("--identity", required=True, help="service identity")
    fres.add_argument("--attest-human", action="store_true", help="I personally read and accepted the terms (terms checkpoints only)")
    fres.add_argument("--provided", action="store_true", help="identity details entered in my own browser (identity checkpoints only)")
    fres.add_argument("--linked", action="store_true", help="payment method linked (payment checkpoints)")
    fres.add_argument("--skipped", action="store_true", help="payment linking skipped (payment checkpoints)")
    fact = fsub.add_parser(
        "activate",
        help="complete the plan and register the live account active (human-gated)",
    )
    fact.add_argument("plan_id", help="plan id (or unique prefix)")
    fact.add_argument("--identity", required=True, help="service identity")


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
    if cmd == "watchdog":
        return _cmd_watchdog(args)
    if cmd == "money":
        return _cmd_money(args)
    if cmd == "broker":
        return _cmd_broker(args)
    if cmd == "founder":
        return _cmd_founder(args)
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
