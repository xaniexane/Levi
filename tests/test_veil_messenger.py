"""Tests for Veil Messenger (PL-05 KFX2 Milestone 1).

Both tracks: ternary delivery (queued/delivered/synced), membership
enforced on every send and read, closed chats readable but silent,
attested bundle export/import, attachment grants with metadata-only
listings, and track isolation. SI side: adult gate on every entry,
per-message sealed envelopes, tamper-evidence. No explicit content
anywhere in this file.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from levi.creator import seal as seal_mod
from levi.creator.ai import chats as ai_chats
from levi.creator.ai.rules import RulesError
from levi.creator.seal import open_bytes, open_record, seal_record
from levi.creator.si import chats as si_chats
from levi.creator.veil import (
    ATTEST_ALG,
    ATTACH_TIERS,
    DELIVERED,
    QUEUED,
    SYNCED,
    AttestationError,
    DeliveryDeniedError,
    MessengerError,
)
from levi.creator.veil import ai as vai
from levi.creator.veil import si as vsi
from levi.plaiground.gate import (
    CONFIRMATION_PHRASE,
    GateLockedError,
    enable_adult_mode,
    set_pin,
)


@pytest.fixture
def home(tmp_path):
    return tmp_path / "home"


def _enable(home):
    set_pin("test-pin-1234", home=home)
    enable_adult_mode(CONFIRMATION_PHRASE, "test-pin-1234", home=home)
    return home


@pytest.fixture
def enabled(home):
    return _enable(home)


def _si_dm(home, a="alice", b="bob"):
    return si_chats.create_chat(a, b, home)


def _si_group(home, owner="alice", members=("bob", "carol"), name="test group"):
    return si_chats.create_group(owner, name, list(members), home)


def _ai_group(home, owner="alice", members=("bob", "carol"), name="test group"):
    return ai_chats.create_group(owner, name, list(members), home)


# -- Gate law: every SI entry is locked by default --------------------------


def test_si_gate_locked_by_default(home):
    with pytest.raises(GateLockedError):
        vsi.queue_message("nope", "alice", "hello", home)
    with pytest.raises(GateLockedError):
        vsi.send_message("nope", "alice", "hello", home)
    with pytest.raises(GateLockedError):
        vsi.read_thread("nope", "alice", home)
    with pytest.raises(GateLockedError):
        vsi.export_bundle("nope", "alice", home)
    with pytest.raises(GateLockedError):
        vsi.import_bundle({}, "alice", home)
    with pytest.raises(GateLockedError):
        vsi.seal_attachment("nope", "alice", "n", "image/png", b"x", home=home)
    with pytest.raises(GateLockedError):
        vsi.list_attachments("nope", "alice", home)
    with pytest.raises(GateLockedError):
        vsi.get_attachment("nope", "alice", home)
    with pytest.raises(GateLockedError):
        vsi.flush_outbox(home)


# -- SI ternary delivery -----------------------------------------------------


def test_si_ternary_queued_delivered_synced(enabled):
    home = enabled
    chat = _si_dm(home)
    q = vsi.queue_message(chat["id"], "alice", "first hello", home)
    assert q["state"] == QUEUED
    # Explicit sync: nothing ambient delivers it.
    listed = vsi.outbox(home, chat_id=chat["id"])
    assert len(listed) == 1 and listed[0]["state"] == QUEUED
    assert "envelope" not in listed[0]  # metadata-only outbox view
    assert vsi.read_thread(chat["id"], "alice", home) == []
    delivered = vsi.flush_outbox(home, chat_id=chat["id"])
    assert len(delivered) == 1
    thread = vsi.read_thread(chat["id"], "bob", home)
    assert [m["body"] for m in thread] == ["first hello"]
    receipts = vsi.delivery_receipts(home, chat_id=chat["id"])
    assert len(receipts) == 1 and receipts[0]["state"] == DELIVERED
    doc = vsi.export_bundle(chat["id"], "alice", home)
    listed = vsi.outbox(home, chat_id=chat["id"])
    assert listed[0]["state"] == SYNCED
    assert vsi.delivery_receipts(home, chat_id=chat["id"])[0]["state"] == SYNCED
    assert doc["attestation"]["alg"] == ATTEST_ALG


def test_si_send_message_is_instant_local_delivery(enabled):
    home = enabled
    chat = _si_dm(home)
    res = vsi.send_message(chat["id"], "alice", "instant", home)
    assert res["state"] == DELIVERED
    assert [m["body"] for m in vsi.read_thread(chat["id"], "bob", home)] == ["instant"]


def test_si_closed_chat_readable_but_silent(enabled):
    home = enabled
    chat = _si_dm(home)
    vsi.send_message(chat["id"], "alice", "before close", home)
    si_chats.close_chat(chat["id"], "alice", home)
    assert [m["body"] for m in vsi.read_thread(chat["id"], "alice", home)] == [
        "before close"
    ]
    with pytest.raises(MessengerError):
        vsi.send_message(chat["id"], "alice", "after close", home)
    with pytest.raises(MessengerError):
        vsi.queue_message(chat["id"], "alice", "after close", home)


def test_si_flush_refuses_closed_chat_stays_queued(enabled):
    home = enabled
    chat = _si_dm(home)
    vsi.queue_message(chat["id"], "alice", "queued first", home)
    si_chats.close_chat(chat["id"], "alice", home)
    assert vsi.flush_outbox(home, chat_id=chat["id"]) == []
    assert vsi.outbox(home, chat_id=chat["id"])[0]["state"] == QUEUED


# -- SI membership enforcement ------------------------------------------------


def test_si_membership_enforced_on_send_and_read(enabled):
    home = enabled
    chat = _si_dm(home)
    with pytest.raises(DeliveryDeniedError):
        vsi.send_message(chat["id"], "mallory", "intruder", home)
    vsi.send_message(chat["id"], "alice", "legit", home)
    with pytest.raises(DeliveryDeniedError):
        vsi.read_thread(chat["id"], "mallory", home)
    assert [c["id"] for c in si_chats.list_chats("mallory", home)] == []


def test_si_removed_member_cannot_send(enabled):
    home = enabled
    chat = _si_group(home)
    si_chats.remove_member(chat["id"], "alice", "bob", home)
    with pytest.raises(DeliveryDeniedError):
        vsi.send_message(chat["id"], "bob", "i was removed", home)


# -- SI tamper-evidence --------------------------------------------------------


def test_si_tampered_envelope_fails_loudly(enabled):
    home = enabled
    chat = _si_dm(home)
    vsi.send_message(chat["id"], "alice", "untouched", home)
    path = home / ".levi" / "creator" / "si" / "veil_si_messages.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    outer = json.loads(lines[0])
    record = open_record(outer, home=home, context="creator/si/veil_si_messages")
    inner = record["envelope"]
    # Tamper with the inner ciphertext, then re-seal the outer the way a
    # store-level attacker would. The inner MAC must still fail.
    ct = inner["ct"]
    inner["ct"] = ("A" if ct[0] != "A" else "B") + ct[1:]
    tampered_outer = seal_record(
        record, home=home, context="creator/si/veil_si_messages"
    )
    path.write_text(json.dumps(tampered_outer, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(seal_mod.SealError):
        vsi.read_thread(chat["id"], "alice", home)


def test_si_envelope_cannot_be_transplanted_between_chats(enabled):
    home = enabled
    chat_a = _si_dm(home, "alice", "bob")
    chat_b = _si_group(home, owner="alice", members=("dave",), name="other")
    vsi.send_message(chat_a["id"], "alice", "for chat a only", home)
    thread = vsi.read_thread(chat_a["id"], "alice", home)
    assert len(thread) == 1
    # Grab the raw inner envelope and try it against chat B's context.
    path = home / ".levi" / "creator" / "si" / "veil_si_messages.jsonl"
    record = open_record(
        json.loads(path.read_text(encoding="utf-8").splitlines()[0]),
        home=home,
        context="creator/si/veil_si_messages",
    )
    key = seal_mod.keeper_key(home)
    with pytest.raises(seal_mod.SealError):
        open_bytes(record["envelope"], key, "veil1/si/msg/" + chat_b["id"])
    # And it opens fine under its own context.
    assert open_bytes(record["envelope"], key, "veil1/si/msg/" + chat_a["id"])


# -- SI export/import ----------------------------------------------------------


def _copy_keeper(src_home: Path, dst_home: Path) -> None:
    src = src_home / ".levi" / "creator" / "keeper.key"
    dst = dst_home / ".levi" / "creator" / "keeper.key"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def test_si_export_import_round_trip(tmp_path, enabled):
    src = enabled
    chat = _si_group(src)
    vsi.send_message(chat["id"], "alice", "one", src)
    vsi.send_message(chat["id"], "bob", "two", src)
    doc = vsi.export_bundle(chat["id"], "alice", src)
    dst = _enable(tmp_path / "home2")
    _copy_keeper(src, dst)
    res = vsi.import_bundle(doc, "alice", dst)
    thread = vsi.read_thread(res["chat_id"], "bob", dst)
    assert [m["body"] for m in thread] == ["one", "two"]
    assert [m["sender_id"] for m in thread] == ["alice", "bob"]
    # Idempotent re-import.
    res2 = vsi.import_bundle(doc, "alice", dst)
    assert res2["imported"] == 0
    assert len(vsi.read_thread(res["chat_id"], "bob", dst)) == 2


def test_si_import_rejects_tampered_attestation(tmp_path, enabled):
    src = enabled
    chat = _si_dm(src)
    vsi.send_message(chat["id"], "alice", "secret", src)
    doc = vsi.export_bundle(chat["id"], "alice", src)
    doc["bundle"]["messages"][0]["body"] = "forged"
    dst = _enable(tmp_path / "home2")
    _copy_keeper(src, dst)
    with pytest.raises(AttestationError):
        vsi.import_bundle(doc, "alice", dst)


def test_si_import_recomputes_trust_against_importer(tmp_path, enabled):
    src = enabled
    chat = _si_dm(src)
    vsi.send_message(chat["id"], "alice", "real", src)
    doc = vsi.export_bundle(chat["id"], "alice", src)
    # Attest a bundle that claims a message from a non-member.
    doc["bundle"]["messages"].append(
        {
            "id": "fake",
            "chat_id": chat["id"],
            "sender_id": "stranger",
            "body": "smuggled",
            "queued_at": "t",
            "delivered_at": "t",
        }
    )
    import hashlib
    import hmac as _hmac

    key = _hmac.new(seal_mod.keeper_key(src), b"veil1-attest", hashlib.sha256).digest()
    canon = json.dumps(doc["bundle"], sort_keys=True, separators=(",", ":")).encode()
    doc["attestation"]["mac"] = _hmac.new(key, canon, hashlib.sha256).hexdigest()
    dst = _enable(tmp_path / "home2")
    _copy_keeper(src, dst)
    with pytest.raises(MessengerError):
        vsi.import_bundle(doc, "alice", dst)


def test_si_import_rejects_wrong_track(tmp_path, enabled):
    src = enabled
    chat = _ai_group(src)  # AI-track chat, no gate needed
    vai.send_message(chat["id"], "alice", "ai hello", src)
    doc = vai.export_bundle(chat["id"], "alice", src)
    with pytest.raises(AttestationError):
        vsi.import_bundle(doc, "alice", src)


def test_si_import_rejects_different_owner(tmp_path, enabled):
    src = enabled
    chat = _si_dm(src)
    vsi.send_message(chat["id"], "alice", "mine", src)
    doc = vsi.export_bundle(chat["id"], "alice", src)
    dst = _enable(tmp_path / "home2")
    _copy_keeper(src, dst)
    with pytest.raises(AttestationError):
        vsi.import_bundle(doc, "mallory", dst)


# -- SI attachments ------------------------------------------------------------


def test_si_attachments_metadata_only_and_grants(enabled):
    home = enabled
    chat = _si_group(home)
    meta = vsi.seal_attachment(
        chat["id"],
        "alice",
        "photo",
        "image/png",
        b"\x89PNG-fake-bytes",
        tier="entry",
        home=home,
    )
    assert meta["tier"] == "entry" and meta["size"] > 0
    listed = vsi.list_attachments(chat["id"], "bob", home)
    assert len(listed) == 1
    assert "envelope" not in listed[0]
    assert "payload" not in listed[0] and "payload_hex" not in listed[0]
    assert listed[0]["tier"] == "entry"
    got = vsi.get_attachment(meta["id"], "bob", home)
    assert got["payload"] == b"\x89PNG-fake-bytes"
    # Outsider gets nothing.
    with pytest.raises(DeliveryDeniedError):
        vsi.get_attachment(meta["id"], "mallory", home)
    # Owner narrows the grant; bob loses access; owner widens it back.
    vsi.grant_attachment(meta["id"], "alice", ["alice", "carol"], home=home)
    with pytest.raises(DeliveryDeniedError):
        vsi.get_attachment(meta["id"], "bob", home)
    vsi.grant_attachment(
        meta["id"], "alice", ["alice", "bob", "carol"], tier="flagship", home=home
    )
    assert vsi.get_attachment(meta["id"], "bob", home)["tier"] == "flagship"
    # Non-owner cannot change grants; grant can't cover non-members.
    with pytest.raises(DeliveryDeniedError):
        vsi.grant_attachment(meta["id"], "bob", ["bob"], home=home)
    with pytest.raises(MessengerError):
        vsi.grant_attachment(meta["id"], "alice", ["mallory"], home=home)
    with pytest.raises(MessengerError):
        vsi.seal_attachment(
            chat["id"], "alice", "x", "image/png", b"y", tier="diamond", home=home
        )
    # Tiers are the ladder, not binary locked/unlocked.
    assert set(ATTACH_TIERS) == {"open", "entry", "standard", "flagship"}


# -- AI track ------------------------------------------------------------------


def test_ai_no_gate_needed_and_sfw_enforced(home):
    chat = _ai_group(home)
    res = vai.send_message(chat["id"], "alice", "hello sunshine", home)
    assert res["state"] == DELIVERED
    assert [m["body"] for m in vai.read_thread(chat["id"], "bob", home)] == [
        "hello sunshine"
    ]
    with pytest.raises(RulesError):
        vai.send_message(chat["id"], "alice", "bringing a weapon to the meetup", home)


def test_ai_ternary_delivery_and_bundle(home):
    chat = _ai_group(home)
    vai.queue_message(chat["id"], "alice", "queued ai", home)
    assert vai.outbox(home, chat_id=chat["id"])[0]["state"] == QUEUED
    assert vai.read_thread(chat["id"], "alice", home) == []
    assert vai.flush_outbox(home, chat_id=chat["id"])
    assert vai.delivery_receipts(home, chat_id=chat["id"])[0]["state"] == DELIVERED
    doc = vai.export_bundle(chat["id"], "alice", home)
    assert vai.outbox(home, chat_id=chat["id"])[0]["state"] == SYNCED
    assert doc["attestation"]["alg"] == ATTEST_ALG


def test_ai_membership_and_closed_chat(home):
    chat = _ai_group(home)
    with pytest.raises(DeliveryDeniedError):
        vai.send_message(chat["id"], "mallory", "nope", home)
    with pytest.raises(DeliveryDeniedError):
        vai.read_thread(chat["id"], "mallory", home)
    ai_chats.close_chat(chat["id"], "alice", home)
    assert vai.read_thread(chat["id"], "alice", home) == []
    with pytest.raises(MessengerError):
        vai.send_message(chat["id"], "alice", "nope", home)


def test_ai_import_round_trip(tmp_path, home):
    chat = _ai_group(home)
    vai.send_message(chat["id"], "alice", "ai one", home)
    doc = vai.export_bundle(chat["id"], "alice", home)
    dst = tmp_path / "home2"
    key_src = home / ".levi" / "creator" / "ai" / "attest.key"
    key_dst = dst / ".levi" / "creator" / "ai" / "attest.key"
    key_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(key_src, key_dst)
    res = vai.import_bundle(doc, "alice", dst)
    assert [m["body"] for m in vai.read_thread(res["chat_id"], "bob", dst)] == [
        "ai one"
    ]
    doc["attestation"]["mac"] = "0" * 64
    with pytest.raises(AttestationError):
        vai.import_bundle(doc, "alice", dst)


def test_ai_attachments_metadata_only_and_grants(home):
    chat = _ai_group(home)
    meta = vai.seal_attachment(
        chat["id"],
        "alice",
        "pic",
        "image/png",
        b"fake-png-bytes",
        tier="standard",
        home=home,
    )
    listed = vai.list_attachments(chat["id"], "carol", home)
    assert len(listed) == 1
    assert "payload_hex" not in listed[0] and "payload" not in listed[0]
    assert vai.get_attachment(meta["id"], "carol", home)["payload"] == b"fake-png-bytes"
    with pytest.raises(DeliveryDeniedError):
        vai.get_attachment(meta["id"], "mallory", home)
    vai.grant_attachment(meta["id"], "alice", ["alice"], home=home)
    with pytest.raises(DeliveryDeniedError):
        vai.get_attachment(meta["id"], "carol", home)


# -- Track isolation -------------------------------------------------------------


def test_tracks_never_merge(enabled):
    home = enabled
    si_chat = _si_dm(home)
    ai_chat = _ai_group(home)
    vsi.send_message(si_chat["id"], "alice", "si secret", home)
    vai.send_message(ai_chat["id"], "alice", "ai hello", home)
    # SI messages are invisible to every AI read path and vice versa.
    assert vai.read_thread(ai_chat["id"], "alice", home)[0]["body"] == "ai hello"
    assert vsi.read_thread(si_chat["id"], "alice", home)[0]["body"] == "si secret"
    ai_bodies = [m["body"] for m in vai.read_thread(ai_chat["id"], "alice", home)]
    si_bodies = [m["body"] for m in vsi.read_thread(si_chat["id"], "alice", home)]
    assert "si secret" not in ai_bodies and "ai hello" not in si_bodies


def test_track_modules_do_not_cross_import():
    veil_dir = Path(vsi.__file__).parent
    si_src = (veil_dir / "si.py").read_text(encoding="utf-8")
    ai_src = (veil_dir / "ai.py").read_text(encoding="utf-8")
    # No cross-track imports: the SI module must not reach into the AI
    # package, and the AI module must not reach into SI, the sealing
    # module, or the Plaiground gate.
    assert "levi.creator.ai" not in si_src
    assert "levi.creator.si" not in ai_src
    assert "levi.creator.seal" not in ai_src
    assert "levi.plaiground" not in ai_src
    assert "require_adult" not in ai_src


def test_sealing_named_honestly():
    assert seal_mod.ALG == "VEIL1-HMAC-XOR"
    veil_dir = Path(vsi.__file__).parent
    negations = ("not", "never", "nothing", "banned")
    for name in ("__init__.py", "si.py", "ai.py", "threat_model.py"):
        src = (veil_dir / name).read_text(encoding="utf-8")
        low = src.lower()
        assert "end-to-end encrypted" not in low, name
        assert "end to end encryption" not in low, name
        for term in ("aes-gcm", "military-grade", "unbreakable"):
            idx = 0
            while True:
                idx = low.find(term, idx)
                if idx < 0:
                    break
                # May only appear inside an explicit "never claim" passage.
                window = low[max(0, idx - 200) : idx + 200]
                assert any(n in window for n in negations), (name, term)
                idx += len(term)
