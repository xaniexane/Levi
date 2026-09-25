"""Proof/guard script for the full Cybrus build laws.

Laws -> implementation -> proof. This script proves, against a throwaway
``LEVI_HOME``, that the laws hold in the shipped code:

- FL1 AUTHENTICATED-FOUNDER-PATH: every provisioning transition requires a
  live FounderSession; founder-tier sessions are refused at creation;
  expired sessions fail closed; cross-identity containment holds.
- FL6 OPERATOR-CHANNEL-BINDING: the unbound production channel fails
  closed; only a bound executor can drive it.
- FL7 PLAN-REGISTRY-FIDELITY: PayPal is registered beside Cash App under
  the same checkpoint laws; unknown platforms are refused.
- FL8 CLI-COVERAGE: the founder CLI commands are wired and the read side
  runs without secrets.
- NO-SECRETS-IN-STORES: ``scan_for_secrets()`` sweeps a Cybrus home for a
  set of known plaintext values (minted passwords, contacts, codes,
  passphrases) across every JSON store, the audit trail, and the raw
  vault bytes. During the real rotation run, Chauncey feeds it the three
  fresh secrets and the decrypted Cash App credential; any hit aborts
  the rotation.

Run: ``python3 core/levi/cybrus/proof_full_build.py`` from a checkout.
Exit 0 means every law held. Nothing here touches the real ``~/.levi``.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for _rel in ("core", "delivery/megazord"):
    _p = str(ROOT / _rel)
    if _p not in sys.path:
        sys.path.insert(0, _p)

TMP = tempfile.mkdtemp(prefix="cybrus-proof-")
os.environ["LEVI_HOME"] = TMP

from levi.cybrus import (  # noqa: E402
    SIGNUP_PLANS,
    BrowserTaskChannel,
    FounderBroker,
    FounderBrokerError,
    FounderSession,
    FounderSessionError,
    OperatorChannelError,
    ScriptedChannel,
)
from levi.cybrus.approval import ApprovalEngine  # noqa: E402
from levi.cybrus.audit import AuditEngine  # noqa: E402
from levi.cybrus.broker_founder import CHECKPOINT_KINDS  # noqa: E402
from levi.cybrus.factory import generate_password, hash_password  # noqa: E402
from levi.cybrus.gateway import CybrusGateway  # noqa: E402
from levi.cybrus.identity import IdentityStore  # noqa: E402
from levi.cybrus import BrokerApprovalRequired  # noqa: E402
from levi.cybrus import rate_limits  # noqa: E402

PASS = []
FAIL = []


def check(name, fn):
    try:
        fn()
    except AssertionError as exc:
        FAIL.append(f"{name}: {exc}")
        print(f"  FAIL {name}: {exc}")
    except Exception as exc:  # noqa: BLE001
        FAIL.append(f"{name}: unexpected {type(exc).__name__}: {exc}")
        print(f"  FAIL {name}: unexpected {type(exc).__name__}: {exc}")
    else:
        PASS.append(name)
        print(f"  ok   {name}")


def _session(name, tier="pro"):
    store = IdentityStore()
    if not store.exists(name):
        store.create(name, tier=tier)
    pw = generate_password(20)
    store.set_credential(name, hash_password(pw))
    rate_limits.set_tier(name, tier)
    gw = CybrusGateway()
    return FounderSession.authenticate(name, pw, gateway=gw), gw


def _gated(fn):
    try:
        return fn()
    except BrokerApprovalRequired as exc:
        ApprovalEngine().approve(exc.approval_id, by="proof")
        return fn()


def cybrus_home() -> Path:
    """The live Cybrus data dir for the current ``LEVI_HOME``."""
    from levi.cybrus._paths import cybrus_dir

    return cybrus_dir()


def scan_for_secrets(cybrus_dir: Path, secrets: list[str]) -> list[str]:
    """Sweep a Cybrus data dir for plaintext occurrences of *secrets*.

    Scans every file under it (JSON stores, audit trail, raw vault
    bytes) for any of the given plaintext values. Returns the list of
    hits as ``"<file>: <which-secret-index>"``. A hit is a proof-of-leak:
    secret values must live encrypted in the vault only.
    """
    hits = []
    if not cybrus_dir.is_dir():
        return [f"<missing cybrus dir {cybrus_dir}>"]
    for path in sorted(cybrus_dir.rglob("*")):
        if not path.is_file():
            continue
        try:
            blob = path.read_bytes().decode("utf-8", "replace")
        except OSError:
            continue
        for i, secret in enumerate(secrets):
            if secret and secret in blob:
                hits.append(f"{path}: secret[{i}]")
    return hits


def prove_fl1():
    print("FL1 authenticated-founder-path")
    b = FounderBroker("proof-pass")

    def no_session():
        try:
            b.provision_plan("cashapp", contact="555-0100")
        except FounderBrokerError as exc:
            assert "authenticated founder session" in str(exc), exc
        else:
            raise AssertionError("provision without session succeeded")

    check("provision without session refused", no_session)

    def wrong_type():
        try:
            b.mint_credential("x" * 32, session="svc")
        except FounderBrokerError as exc:
            assert "must be a FounderSession" in str(exc), exc
        else:
            raise AssertionError("wrong session type accepted")

    check("wrong session type refused", wrong_type)

    def founder_refused():
        store = IdentityStore()
        if not store.exists("chauncey"):
            store.create("chauncey", tier="founder")
        pw = generate_password(20)
        store.set_credential("chauncey", hash_password(pw))
        try:
            FounderSession.authenticate("chauncey", pw, gateway=CybrusGateway())
        except FounderSessionError as exc:
            assert "founder identity" in str(exc), exc
        else:
            raise AssertionError("founder identity session created")

    check("founder-tier session refused at creation", founder_refused)

    def expiry_closed():
        s, gw = _session("proof-a")
        plan = _gated(lambda: b.provision_plan("cashapp", session=s, contact="555-0100"))
        gw._sessions.clear()
        try:
            b.mint_credential(plan["plan_id"], session=s)
        except FounderSessionError as exc:
            assert "not live" in str(exc), exc
        else:
            raise AssertionError("expired session honored")

    check("expired session fails closed", expiry_closed)

    def containment():
        sa, _ = _session("proof-a")
        sb, _ = _session("proof-b")
        plan = _gated(lambda: b.provision_plan("paypal", session=sa, contact="555-0100"))
        try:
            b.mint_credential(plan["plan_id"], session=sb)
        except FounderBrokerError as exc:
            assert "containment" in str(exc), exc
        else:
            raise AssertionError("cross-identity mint succeeded")

    check("cross-identity containment", containment)

    def service_ok():
        s, _ = _session("proof-a2")
        plan = _gated(lambda: b.provision_plan("cashapp", session=s, contact="555-0100"))
        assert plan["identity"] == "proof-a2", plan
        assert b.list_plans(identity="proof-a2"), "read side must see own plans"

    check("service identity session drives a plan", service_ok)


def prove_fl6():
    print("FL6 operator-channel-binding")

    def unbound_refuses():
        ch = BrowserTaskChannel()
        assert ch.bound is False
        try:
            ch.perform({"plan_id": "x"}, {"id": "open_signup", "kind": "action"}, {})
        except OperatorChannelError as exc:
            assert "no browser-task executor bound" in str(exc), exc
        else:
            raise AssertionError("unbound channel performed a step")

    check("unbound channel fails closed", unbound_refuses)

    def bound_drives():
        ch = BrowserTaskChannel(lambda p, s, c: {"ok": True, "note": "did it"})
        assert ch.bound is True
        out = ch.perform({"plan_id": "x"}, {"id": "open_signup", "kind": "action"}, {})
        assert out["ok"] is True, out

    check("bound executor drives the channel", bound_drives)

    def scripted_honest():
        b = FounderBroker("proof-pass")
        s, _ = _session("proof-c")
        plan = _gated(lambda: b.provision_plan("cashapp", session=s, contact="555-0100"))
        _gated(lambda: b.mint_credential(plan["plan_id"], session=s))
        _gated(lambda: b.begin_execution(plan["plan_id"], session=s))
        from levi.cybrus import FounderPlanFailed

        try:
            b.run_to_checkpoint(plan["plan_id"], ScriptedChannel({}), session=s)
        except FounderPlanFailed:
            pass
        else:
            raise AssertionError("undeclared step did not fail the plan")
        assert b.get_plan(plan["plan_id"], identity="proof-c")["status"] == "failed"

    check("scripted channel cannot improvise steps", scripted_honest)


def prove_fl7():
    print("FL7 plan-registry-fidelity")

    def registry():
        assert set(SIGNUP_PLANS) == {"cashapp", "paypal"}, sorted(SIGNUP_PLANS)
        pp = SIGNUP_PLANS["paypal"]
        assert pp["signup_url"].startswith("https://www.paypal.com/"), pp["signup_url"]
        kinds = {s.get("checkpoint") for s in pp["steps"] if s["kind"] == "checkpoint"}
        assert kinds <= set(CHECKPOINT_KINDS), kinds
        assert {"verification_code", "terms_acceptance"} <= kinds, kinds

    check("paypal registered beside cashapp under the same checkpoint laws", registry)

    def unknown_refused():
        b = FounderBroker("proof-pass")
        s, _ = _session("proof-d")
        try:
            b.provision_plan("venmo", session=s, contact="555-0100")
        except FounderBrokerError as exc:
            assert "unknown platform" in str(exc), exc
        else:
            raise AssertionError("unknown platform accepted")

    check("unknown platform refused", unknown_refused)


def prove_fl8():
    print("FL8 cli-coverage")
    from levi.cybrus.__main__ import main

    def status_cmd():
        assert main(["founder", "status"]) == 0

    check("founder status runs", status_cmd)

    def plans_cmd():
        assert main(["founder", "plans"]) == 0

    check("founder plans runs", plans_cmd)

    def bad_platform():
        try:
            main(["founder", "provision", "--platform", "venmo", "--identity", "proof-d"])
        except SystemExit as exc:
            assert exc.code == 2, exc.code
        else:
            raise AssertionError("bad platform choice not rejected by the parser")

    check("provision parser rejects unknown platform", bad_platform)


def prove_no_secrets_scan():
    print("NO-SECRETS-IN-STORES")

    def full_run_then_scan():
        b = FounderBroker("proof-pass")
        s, _ = _session("proof-e")
        plan = _gated(lambda: b.provision_plan("cashapp", session=s, contact="555-0199"))
        pid = plan["plan_id"]
        _, password = _gated(lambda: b.mint_credential(pid, session=s))
        _gated(lambda: b.begin_execution(pid, session=s))
        contact = b.issue_contact(pid, session=s)
        ch = ScriptedChannel(
            {
                "open_signup": {"ok": True, "note": "form visible"},
                "enter_contact": {"ok": True, "note": "contact accepted"},
                "submit_code": {"ok": True, "note": "verified"},
                "confirm_created": {"ok": True, "note": "dashboard"},
            }
        )
        b.run_to_checkpoint(pid, ch, session=s)
        _gated(lambda: b.human_input(pid, "checkpoint_sms", {"code": "424242"}, session=s))
        code = b.issue_checkpoint_secret(pid, session=s)
        b.run_to_checkpoint(pid, ch, session=s)
        _gated(lambda: b.human_input(pid, "checkpoint_identity", {"provided": True}, session=s))
        b.run_to_checkpoint(pid, ch, session=s)
        _gated(
            lambda: b.human_input(
                pid, "checkpoint_terms", {"accepted": True}, session=s, human_attestation=True
            )
        )
        b.run_to_checkpoint(pid, ch, session=s)
        _gated(lambda: b.human_input(pid, "link_card", {"skipped": True}, session=s))
        done = b.run_to_checkpoint(pid, ch, session=s)
        assert done["done"] is True, done
        _gated(lambda: b.complete_execution(pid, session=s))
        ok, _ = AuditEngine().verify()
        assert ok, "audit chain must verify"
        hits = scan_for_secrets(cybrus_home(), [password, contact, code])
        assert not hits, f"secret leaked into stores/audit: {hits}"

    check("full run leaves no plaintext secret in stores/audit/vault bytes", full_run_then_scan)

    def scanner_finds_known_hit():
        # The scanner itself is honest: plant a known value, it must report it.
        probe = cybrus_home() / "probe.txt"
        probe.write_text("canary-SECRET-xyz")
        hits = scan_for_secrets(cybrus_home(), ["canary-SECRET-xyz"])
        probe.unlink()
        assert hits and hits[0].endswith("secret[0]"), hits

    check("scanner reports a planted plaintext hit", scanner_finds_known_hit)


def main() -> int:
    print(f"cybrus full-build proof — LEVI_HOME={TMP}")
    prove_fl1()
    prove_fl6()
    prove_fl7()
    prove_fl8()
    prove_no_secrets_scan()
    print(f"\n{PASS.__len__()} passed, {FAIL.__len__()} failed")
    for f in FAIL:
        print("FAILED:", f)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
