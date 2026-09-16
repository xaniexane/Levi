"""Tests for LEVI Oath (core/levi/oath/).

Hermetic: every test runs under a tmp ``$LEVI_OATH_HOME`` and a shared
throwaway ``$LEVI_OATH_GNUPGHOME`` (one key minted per module); no network
(``socket.connect`` blocked), no user HOME writes.  Tests that need the
``gpg`` binary are skipped when it is absent.
"""

import email
import json
import os
import shutil
import socket
import subprocess
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import pytest

from levi.oath import COMMANDS_DIR, MAILDIR, OWNER_FILE, oath_home

GPG = shutil.which("gpg")
needs_gpg = pytest.mark.skipif(GPG is None, reason="gpg not installed")


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def no_network(monkeypatch):
    """Block all TCP connects; gpg's local agent still works."""

    def _blocked(self, addr, *a, **k):
        raise RuntimeError("network disabled in tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    yield


@pytest.fixture(scope="module")
def gpg_home(tmp_path_factory):
    """Module-scoped throwaway keyring with one test key."""
    if GPG is None:
        pytest.skip("gpg not installed")
    home = tmp_path_factory.mktemp("oath-gnupg")
    old = os.environ.get("LEVI_OATH_GNUPGHOME")
    os.environ["LEVI_OATH_GNUPGHOME"] = str(home)
    from levi.oath.keys import ensure_gnupg_home, generate_key

    ensure_gnupg_home()
    info = generate_key("Oath Test Owner <oath-test@example.com>")
    yield {"home": home, "fingerprint": info.fingerprint, "uid": info.uids[0]}
    if old is None:
        os.environ.pop("LEVI_OATH_GNUPGHOME", None)
    else:
        os.environ["LEVI_OATH_GNUPGHOME"] = old


@pytest.fixture
def hermetic_home(tmp_path, monkeypatch):
    """Function-scoped hermetic Oath home (no gpg needed)."""
    home = tmp_path / "oath-home"
    monkeypatch.setenv("LEVI_OATH_HOME", str(home))
    monkeypatch.setenv("LEVI_OATH_UNATTENDED", "1")  # non-interactive gpg signing
    return home


@pytest.fixture
def oath_env(hermetic_home, gpg_home):
    """Function-scoped hermetic Oath home wired to the module keyring."""
    return {"home": hermetic_home, **gpg_home}


def _owner_json(fingerprint: str) -> None:
    OWNER_FILE().parent.mkdir(parents=True, exist_ok=True)
    OWNER_FILE().write_text(json.dumps({"fingerprint": fingerprint}) + "\n")


def _clearsign(data: bytes) -> bytes:
    from levi.oath.keys import gpg_sign_args, run_gpg

    proc = run_gpg(*gpg_sign_args(), "--armor", "--clearsign", input_bytes=data)
    return proc.stdout


def _clearsigned_email(from_addr: str, subject: str, body: str) -> bytes:
    blob = _clearsign(body.encode("utf-8"))
    headers = (
        f"From: {from_addr}\r\nSubject: {subject}\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n\r\n"
    ).encode("utf-8")
    return headers + blob


def _mime_signed_email(from_addr: str, subject: str, body: str) -> bytes:
    from levi.oath.keys import gpg_sign_args, run_gpg

    data = body.replace("\n", "\r\n").encode("utf-8")
    proc = run_gpg(*gpg_sign_args(), "--armor", "--detach-sign", input_bytes=data)
    sig = proc.stdout
    msg = MIMEMultipart("signed", protocol="application/pgp-signature")
    msg["From"] = from_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    msg.attach(MIMEText(sig.decode("utf-8"), "pgp-signature"))
    return msg.as_bytes()


def _drop_mail(raw: bytes, name: str = "mission.eml") -> None:
    new = MAILDIR() / "new"
    new.mkdir(parents=True, exist_ok=True)
    (new / name).write_bytes(raw)


def _add_alice(book_fixture_grants: dict, **kw):
    from levi.oath.contacts import Contact, load_book

    book = load_book()
    contact = Contact(
        name="alice",
        email="alice@example.com",
        fingerprints=kw.pop("fingerprints", []),
        grants=book_fixture_grants,
        **kw,
    )
    book.add(contact)
    return contact


def _define_and_sign(
    name: str, argv: list, args: dict, tier: str, *, signer: str, expires_at: str = ""
) -> Path:
    """Write a definition draft and run the owner sign ceremony with an
    explicit signing key (never gpg's default-key choice)."""
    from levi.oath.commands import CommandRegistry

    registry = CommandRegistry()
    registry.write_unsigned(
        {
            "name": name,
            "version": 1,
            "description": f"test command {name}",
            "tier": tier,
            "argv": argv,
            "args": args,
            "created_by": "owner",
            "created_at": "2026-09-15T00:00:00Z",
            "expires_at": expires_at,
        }
    )
    return registry.sign(name, key_fingerprint=signer)


MARK_ARGV = [
    sys.executable,
    "-c",
    "import pathlib,sys; pathlib.Path(sys.argv[1]).write_text('ran')",
    "{flag}",
]
MARK_ARGS = {"flag": {"type": "string", "required": True, "pattern": r"^[\w\-./]+$"}}


# ---------------------------------------------------------------------------
# trust classification
# ---------------------------------------------------------------------------


@needs_gpg
def test_trust_unsigned_is_unverified(oath_env, no_network):
    from levi.oath.trust import UNVERIFIED, classify_message

    msg = email.message_from_bytes(b"From: a@b.c\nSubject: hi\n\nhello\n")
    assert classify_message(msg).level == UNVERIFIED


@needs_gpg
def test_trust_valid_signature_unpinned_is_verified(oath_env, no_network):
    from levi.oath.trust import VERIFIED, classify_message

    raw = _clearsigned_email("mallory@example.com", "hi", "cmd:noop\n")
    result = classify_message(email.message_from_bytes(raw))
    assert result.level == VERIFIED
    assert result.signer_fingerprint == oath_env["fingerprint"]


@needs_gpg
def test_trust_pinned_signature_is_trusted(oath_env, no_network):
    from levi.oath.trust import TRUSTED, classify_message

    raw = _clearsigned_email("alice@example.com", "hi", "cmd:noop\n")
    result = classify_message(
        email.message_from_bytes(raw), pins=[oath_env["fingerprint"].lower()]
    )
    assert result.level == TRUSTED
    assert result.detail.startswith("valid signature from a pinned")


@needs_gpg
def test_trust_tampered_signature_is_untrusted(oath_env, no_network):
    from levi.oath.trust import UNTRUSTED, classify_message

    raw = _clearsigned_email("alice@example.com", "hi", "cmd:noop\n")
    tampered = raw.replace(b"cmd:noop", b"cmd:EVIL")
    result = classify_message(email.message_from_bytes(tampered))
    assert result.level == UNTRUSTED


@needs_gpg
def test_trust_pgp_mime_multipart_signed(oath_env, no_network):
    from levi.oath.trust import VERIFIED, classify_message, extract_signed_parts

    raw = _mime_signed_email("alice@example.com", "mission", "cmd:noop\n")
    msg = email.message_from_bytes(raw)
    assert len(extract_signed_parts(msg)) == 1
    result = classify_message(msg)
    assert result.level == VERIFIED
    assert result.signed_bytes.strip() == b"cmd:noop"


# ---------------------------------------------------------------------------
# keys
# ---------------------------------------------------------------------------


@needs_gpg
def test_keys_generate_and_list(oath_env, no_network):
    from levi.oath.keys import fingerprint_of, generate_key, list_keys

    info = generate_key("Oath Second <second@example.com>")
    assert len(info.fingerprint) >= 40
    assert fingerprint_of("second@example.com") == info.fingerprint
    assert any(k.fingerprint == info.fingerprint for k in list_keys())


@needs_gpg
def test_keys_import_roundtrip(oath_env, no_network):
    from levi.oath.keys import (
        delete_key,
        fingerprint_of,
        generate_key,
        import_key,
        run_gpg,
    )

    info = generate_key("Oath Import <import@example.com>")
    proc = run_gpg("--armor", "--export-secret-keys", info.fingerprint)
    assert b"BEGIN PGP PRIVATE KEY BLOCK" in proc.stdout
    delete_key(info.fingerprint)
    assert fingerprint_of(info.fingerprint) is None
    imported = import_key(proc.stdout)
    assert any(k.fingerprint == info.fingerprint for k in imported)


# ---------------------------------------------------------------------------
# contacts
# ---------------------------------------------------------------------------


def test_contacts_roundtrip(hermetic_home):
    from levi.oath.contacts import load_book

    contact = _add_alice(
        {"disk-usage": ["r"]},
        fingerprints=["A" * 40],
        trust_floor="TRUSTED",
        tier_ceiling="execute",
        max_missions_per_hour=5,
    )
    book = load_book()
    back = book.get("alice")
    assert back is not None and back.email == "alice@example.com"
    assert back.trust_floor == "TRUSTED" and back.tier_ceiling == "execute"
    assert back.grants == {"disk-usage": ["r"]}
    assert back.fingerprints == ["A" * 40]
    assert book.find_by_email("ALICE@example.com") is not None
    assert book.find_by_fingerprint("a" * 40).name == "alice"


def test_contacts_floor_cannot_drop_below_verified(hermetic_home):
    from levi.oath.contacts import Contact

    with pytest.raises(ValueError):
        Contact(name="bob", trust_floor="UNVERIFIED")
    with pytest.raises(ValueError):
        Contact(name="bob", grants={"x": ["q"]})


# ---------------------------------------------------------------------------
# signed command registry
# ---------------------------------------------------------------------------


@needs_gpg
def test_unsigned_definition_is_refused(oath_env, no_network):
    from levi.oath.commands import CommandRegistry, DefinitionError

    _owner_json(oath_env["fingerprint"])
    registry = CommandRegistry()
    registry.write_unsigned(
        {
            "name": "unsigned-cmd",
            "version": 1,
            "tier": "read",
            "argv": ["/bin/echo", "{word}"],
            "args": {},
            "created_by": "owner",
            "created_at": "2026-01-01T00:00:00Z",
        }
    )
    with pytest.raises(DefinitionError, match="missing detached signature"):
        registry.load_all()


@needs_gpg
def test_signed_definition_loads(oath_env, no_network):
    from levi.oath.commands import CommandRegistry

    _owner_json(oath_env["fingerprint"])
    _define_and_sign(
        "say",
        ["/bin/echo", "{word}"],
        {"word": {"type": "string", "required": True}},
        "read",
        signer=oath_env["fingerprint"],
    )
    definition = CommandRegistry().get("say")
    assert definition.tier == "read"
    assert definition.render({"word": "hi"}) == ["/bin/echo", "hi"]


@needs_gpg
def test_tampered_definition_is_refused(oath_env, no_network):
    from levi.oath.commands import CommandRegistry, DefinitionError

    _owner_json(oath_env["fingerprint"])
    _define_and_sign(
        "fragile", ["/bin/echo", "x"], {}, "read", signer=oath_env["fingerprint"]
    )
    path = COMMANDS_DIR() / "fragile.json"
    raw = path.read_bytes().replace(b"/bin/echo", b"/bin/EVIL")
    path.write_bytes(raw)
    with pytest.raises(DefinitionError, match="bad signature"):
        CommandRegistry().load_all()


@needs_gpg
def test_expired_definition_is_refused(oath_env, no_network):
    from levi.oath.commands import CommandRegistry, DefinitionError

    _owner_json(oath_env["fingerprint"])
    _define_and_sign(
        "old",
        ["/bin/echo", "x"],
        {},
        "read",
        signer=oath_env["fingerprint"],
        expires_at="2020-01-01T00:00:00Z",
    )
    with pytest.raises(DefinitionError, match="expired"):
        CommandRegistry().load_all()


@needs_gpg
def test_wrong_signer_is_refused(oath_env, no_network):
    from levi.oath.commands import CommandRegistry, DefinitionError
    from levi.oath.keys import generate_key

    other = generate_key("Oath Attacker <attacker@example.com>")
    _owner_json(other.fingerprint)  # owner pins the ATTACKER key...
    # ...but the definition is signed by the test-owner key -> mismatch
    _define_and_sign(
        "mismatch", ["/bin/echo", "x"], {}, "read", signer=oath_env["fingerprint"]
    )
    with pytest.raises(DefinitionError, match="not by the owner"):
        CommandRegistry().load_all()


def test_arg_validation_rejects_shell_and_bad_patterns(hermetic_home):
    from levi.oath.commands import CommandDefinition, DefinitionError

    definition = CommandDefinition(
        name="say",
        argv=["/bin/echo", "{word}"],
        args={"word": {"type": "string", "required": True, "pattern": r"^[a-z]+$"}},
        tier="read",
    )
    assert definition.render({"word": "hello"}) == ["/bin/echo", "hello"]
    with pytest.raises(DefinitionError):  # pattern
        definition.render({"word": "HELLO"})
    with pytest.raises(DefinitionError):  # shell metacharacters
        definition.render({"word": "a;b"})
    with pytest.raises(DefinitionError):  # unknown arg
        definition.render({"word": "a", "extra": "b"})
    with pytest.raises(DefinitionError):  # missing required
        definition.render({})


def test_pipeline_module_imports_without_agent_stack():
    """pipeline.py must not import levi.agent at module top level."""
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, 'core');"
            "import levi.oath.pipeline;"
            "mods = [m for m in sys.modules if m == 'levi.agent' or m.startswith('levi.agent.')];"
            "assert not mods, mods; print('clean')",
        ],
        cwd=str(Path(__file__).resolve().parents[1]),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr.decode()[-500:]
    assert b"clean" in proc.stdout


# ---------------------------------------------------------------------------
# pipelines
# ---------------------------------------------------------------------------


def test_pipeline_parse(hermetic_home):
    from levi.oath.pipeline import parse

    pipeline = parse('cmd:say word=hello | ai:"repeat {stdin}" | reply:body="done"')
    assert [s.kind for s in pipeline.stages] == ["cmd", "ai", "reply"]
    assert pipeline.stages[0].args == {"word": "hello"}
    assert pipeline.stages[1].args == {"prompt": "repeat {stdin}"}


@needs_gpg
def test_pipeline_chains_stdout_with_mocked_ai(oath_env, no_network, monkeypatch):
    from levi.oath import pipeline as pipe_mod
    from levi.oath.commands import CommandRegistry
    from levi.oath.pipeline import parse, run

    _owner_json(oath_env["fingerprint"])
    _define_and_sign(
        "say",
        ["/bin/echo", "{word}"],
        {"word": {"type": "string", "required": True}},
        "read",
        signer=oath_env["fingerprint"],
    )
    contact = _add_alice({"say": ["r"], "ai": ["x"]}, tier_ceiling="execute")

    seen = {}

    def fake_ai(prompt, stdin_text="", **kw):
        seen["prompt"] = prompt
        seen["stdin"] = stdin_text
        return f"MOCKED-AI got: {stdin_text.strip()}", "mocked"

    monkeypatch.setattr(pipe_mod, "ai_reason", fake_ai)
    pipeline = parse('cmd:say word=hello | ai:"repeat {stdin}"')
    run(pipeline, contact, registry=CommandRegistry())
    assert len(pipeline.results) == 2
    assert all(r.ok for r in pipeline.results)
    assert seen["stdin"].strip() == "hello"
    assert pipeline.results[1].stdout == "MOCKED-AI got: hello"


@needs_gpg
def test_pipeline_denies_ungranted_stage_before_execution(
    oath_env, no_network, tmp_path
):
    from levi.oath.commands import CommandRegistry
    from levi.oath.pipeline import parse, run

    _owner_json(oath_env["fingerprint"])
    marker = tmp_path / "should-not-exist"
    _define_and_sign(
        "mark", MARK_ARGV, MARK_ARGS, "write", signer=oath_env["fingerprint"]
    )
    contact = _add_alice({})  # deny-closed: no grants at all
    pipeline = parse(f"cmd:mark flag={marker}")
    run(pipeline, contact, registry=CommandRegistry())
    assert len(pipeline.results) == 1
    assert not pipeline.results[0].ok
    assert pipeline.results[0].decision is not None
    assert not pipeline.results[0].decision.allowed
    assert not marker.exists()


@needs_gpg
def test_pipeline_dry_run_executes_nothing(oath_env, no_network, tmp_path):
    from levi.oath.commands import CommandRegistry
    from levi.oath.pipeline import parse, run

    _owner_json(oath_env["fingerprint"])
    marker = tmp_path / "dry-run-marker"
    _define_and_sign(
        "mark", MARK_ARGV, MARK_ARGS, "write", signer=oath_env["fingerprint"]
    )
    contact = _add_alice({"mark": ["w"]}, tier_ceiling="write")
    pipeline = parse(f'cmd:mark flag={marker} | reply:body="done {{stdin}}"')
    # reply needs a grant too
    contact.grants["reply"] = ["w"]
    from levi.oath.contacts import load_book

    load_book().update(contact)
    run(pipeline, contact, registry=CommandRegistry(), dry_run=True)
    assert all(r.ok for r in pipeline.results)
    assert not marker.exists()  # nothing executed
    assert "would run" in pipeline.results[0].note
    assert "would reply" in pipeline.results[1].note


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------


def test_audit_chain_verifies(hermetic_home):
    from levi.oath.audit import AuditLog

    log = AuditLog()
    log.append({"event": "a"})
    log.append({"event": "b"})
    result = log.verify()
    assert result["ok"] and result["entries"] == 2


def test_audit_tamper_is_detected(hermetic_home):
    from levi.oath.audit import AuditError, AuditLog
    from levi.oath import AUDIT_FILE

    log = AuditLog()
    log.append({"event": "a"})
    log.append({"event": "b"})
    lines = AUDIT_FILE().read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[1])
    entry["payload"]["event"] = "EVIL"
    lines[1] = json.dumps(entry, sort_keys=True)
    AUDIT_FILE().write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(AuditError, match="tampered"):
        log.verify()


@needs_gpg
def test_audit_checkpoint_roundtrip(oath_env, no_network):
    from levi.oath.audit import AuditError, AuditLog
    from levi.oath import AUDIT_FILE

    log = AuditLog()
    log.append({"event": "a"})
    path = log.checkpoint()
    assert path.exists()
    summary = log.verify_checkpoints(oath_env["fingerprint"])
    assert summary == {"ok": True, "checkpoints": 1}
    # Tamper the checkpointed entry itself -> checkpoint verification fails.
    log.append({"event": "b"})
    lines = AUDIT_FILE().read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[0])
    entry["payload"]["event"] = "EVIL"
    lines[0] = json.dumps(entry, sort_keys=True)
    AUDIT_FILE().write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(AuditError):
        log.verify_checkpoints(oath_env["fingerprint"])


# ---------------------------------------------------------------------------
# inbox
# ---------------------------------------------------------------------------


@needs_gpg
def test_inbox_builds_trusted_mission(oath_env, no_network):
    from levi.oath.contacts import load_book
    from levi.oath.inbox import build_mission
    from levi.oath.trust import TRUSTED

    _add_alice({}, fingerprints=[oath_env["fingerprint"]])
    raw = _clearsigned_email(
        "alice@example.com", "mission", 'cmd:say word=hi | ai:"shout {stdin}"\n'
    )
    mission = build_mission(raw, load_book())
    assert mission.trust == TRUSTED
    assert mission.contact_name == "alice"
    assert mission.pipeline_text.strip() == 'cmd:say word=hi | ai:"shout {stdin}"'
    assert [s["kind"] for s in mission.stages] == ["cmd", "ai"]
    assert mission.parse_error == ""


@needs_gpg
def test_inbox_unsigned_mail_has_no_pipeline(oath_env, no_network):
    from levi.oath.contacts import load_book
    from levi.oath.inbox import build_mission
    from levi.oath.trust import UNVERIFIED

    _add_alice({})
    raw = b"From: alice@example.com\r\nSubject: hi\r\n\r\ncmd:say word=hi\n"
    mission = build_mission(raw, load_book())
    assert mission.trust == UNVERIFIED
    assert mission.stages == [] and mission.pipeline_text == ""


@needs_gpg
def test_inbox_maildir_poll(oath_env, no_network):
    from levi.oath.contacts import load_book
    from levi.oath.inbox import poll

    _add_alice({}, fingerprints=[oath_env["fingerprint"]])
    _drop_mail(_clearsigned_email("alice@example.com", "m", "cmd:say word=hi\n"))
    missions = poll(load_book(), use_imap=False, use_maildir=True)
    assert len(missions) == 1
    key, mission = missions[0]
    assert key.startswith("new/")
    assert mission.contact_name == "alice"


# ---------------------------------------------------------------------------
# daemon
# ---------------------------------------------------------------------------


@needs_gpg
def test_daemon_denies_untrusted_mail(oath_env, no_network):
    from levi.oath.audit import AuditLog
    from levi.oath.daemon import Daemon

    _add_alice({})
    _drop_mail(b"From: alice@example.com\r\nSubject: x\r\n\r\ncmd:say word=hi\n")
    daemon = Daemon(dry_run=True)
    summary = daemon.run_once(use_imap=False, use_maildir=True)
    assert summary == {"missions": 1, "ran": 0, "denied": 1, "errors": 0}
    events = [e["payload"]["event"] for e in AuditLog().entries()]
    assert "mission.denied" in events
    # mail was marked seen (moved out of new/)
    assert list((MAILDIR() / "new").iterdir()) == []


@needs_gpg
def test_daemon_runs_signed_mission(oath_env, no_network, tmp_path):
    from levi.oath.audit import AuditLog
    from levi.oath.daemon import Daemon

    _owner_json(oath_env["fingerprint"])
    marker = tmp_path / "mission-ran"
    _define_and_sign(
        "mark", MARK_ARGV, MARK_ARGS, "write", signer=oath_env["fingerprint"]
    )
    _add_alice(
        {"mark": ["w"]}, fingerprints=[oath_env["fingerprint"]], tier_ceiling="write"
    )
    _drop_mail(
        _clearsigned_email("alice@example.com", "go", f"cmd:mark flag={marker}\n")
    )
    daemon = Daemon()
    summary = daemon.run_once(use_imap=False, use_maildir=True)
    assert summary["ran"] == 1 and summary["denied"] == 0
    assert marker.exists()
    events = [e["payload"] for e in AuditLog().entries()]
    assert any(p["event"] == "mission.accepted" for p in events)
    completed = next(p for p in events if p["event"] == "mission.completed")
    assert completed["ok"] is True


@needs_gpg
def test_daemon_dry_run_sends_no_mail(oath_env, no_network, tmp_path):
    from levi.oath.audit import AuditLog
    from levi.oath.daemon import Daemon

    _owner_json(oath_env["fingerprint"])
    marker = tmp_path / "dry-marker"
    _define_and_sign(
        "mark", MARK_ARGV, MARK_ARGS, "write", signer=oath_env["fingerprint"]
    )
    contact = _add_alice(
        {"mark": ["w"], "reply": ["w"]},
        fingerprints=[oath_env["fingerprint"]],
        tier_ceiling="write",
    )
    body = f'cmd:mark flag={marker} | reply:body="done {{stdin}}"\n'
    _drop_mail(_clearsigned_email("alice@example.com", "go", body))
    daemon = Daemon(dry_run=True)
    summary = daemon.run_once(use_imap=False, use_maildir=True)
    assert summary["ran"] == 1
    assert not marker.exists()  # dry-run executed nothing
    events = [e["payload"]["event"] for e in AuditLog().entries()]
    assert "mission.reply_preview" in events  # reply staged, not sent


@needs_gpg
def test_daemon_rate_limit_denies(oath_env, no_network):
    from levi.oath.daemon import Daemon, record_mission_use

    _add_alice({}, max_missions_per_hour=1)
    from levi.oath.contacts import load_book

    contact = load_book().get("alice")
    assert contact is not None
    record_mission_use(contact)
    _drop_mail(_clearsigned_email("alice@example.com", "go", "cmd:say word=hi\n"))
    daemon = Daemon(dry_run=True)
    summary = daemon.run_once(use_imap=False, use_maildir=True)
    assert summary["denied"] == 1 and summary["ran"] == 0


def test_cli_init_and_doctor(hermetic_home, no_network):
    from levi.oath.__main__ import main

    assert main(["init", "--email", "owner@example.com"]) == 0
    assert (oath_home() / "maildir" / "new").is_dir()
    assert OWNER_FILE().exists()
    # doctor fails without a pinned owner key, but must not crash
    rc = main(["doctor"])
    assert rc in (0, 1)
