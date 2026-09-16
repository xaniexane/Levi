"""Tests for levi.boards (charter-governed local message areas).

Hermetic: every test runs with an isolated LEVI_HOME in tmp_path.
"""

from __future__ import annotations

import json

import pytest

from levi.boards import areas
from levi.boards.__main__ import main as boards_main


@pytest.fixture()
def home(tmp_path, monkeypatch):
    h = tmp_path / "levi-home"
    h.mkdir()
    monkeypatch.setenv("LEVI_HOME", str(h))
    return h


# ------------------------------------------------------------------- create


def test_create_requires_charter(home):
    with pytest.raises(ValueError):
        areas.create_area("town-hall", "", "chauncey")
    with pytest.raises(ValueError):
        areas.create_area("town-hall", "   ", "chauncey")
    assert not (home / "boards" / "town-hall").exists()


def test_create_and_charter_roundtrip(home):
    cfg = areas.create_area("town-hall", "Be kind, stay local.", "chauncey")
    assert cfg["name"] == "town-hall"
    assert cfg["moderator"] == "chauncey"
    assert len(cfg["charter_sha256"]) == 64
    assert areas.charter("town-hall") == "Be kind, stay local."


def test_create_duplicate_raises(home):
    areas.create_area("town-hall", "charter one", "chauncey")
    with pytest.raises(ValueError):
        areas.create_area("town-hall", "charter two", "chauncey")


def test_create_bad_names_raise(home):
    for bad in ["", "has space", "a/b", "..", "x" * 41]:
        with pytest.raises(ValueError):
            areas.create_area(bad, "some charter", "chauncey")


def test_charter_unknown_area_raises(home):
    with pytest.raises(KeyError):
        areas.charter("ghost")


# -------------------------------------------------------------- post/queue


def test_post_then_queue_shows_it(home):
    areas.create_area("town-hall", "Be kind.", "chauncey")
    pid = areas.post("town-hall", "ana", "Hello", "first post")
    q = areas.queue("town-hall")
    assert len(q) == 1
    assert q[0]["id"] == pid
    assert q[0]["author"] == "ana"
    assert q[0]["subject"] == "Hello"
    assert "ts" in q[0]


def test_post_ids_monotonic_counter(home):
    areas.create_area("town-hall", "Be kind.", "chauncey")
    ids = [areas.post("town-hall", "ana", "s%d" % i, "b%d" % i) for i in range(3)]
    counters = [i.split("-")[0] for i in ids]
    assert counters == ["0001", "0002", "0003"]


# ------------------------------------------------------- approve/read/seen


def test_approve_then_read_once_second_read_empty(home):
    areas.create_area("town-hall", "Be kind.", "chauncey")
    pid = areas.post("town-hall", "ana", "Hello", "first post")
    msg = areas.approve("town-hall", pid, "chauncey")
    assert msg["approved_by"] == "chauncey"
    assert "approved_at" in msg
    assert areas.queue("town-hall") == []

    first = areas.read("town-hall", "bea")
    assert [m["id"] for m in first] == [pid]
    second = areas.read("town-hall", "bea")
    assert second == []

    # A different reader still sees it once.
    other = areas.read("town-hall", "cai")
    assert [m["id"] for m in other] == [pid]


def test_read_rejects_bad_reader_names(home):
    areas.create_area("town-hall", "Be kind.", "chauncey")
    with pytest.raises(ValueError):
        areas.read("town-hall", "../evil")
    with pytest.raises(ValueError):
        areas.read("town-hall", "")
    with pytest.raises(ValueError):
        areas.read("town-hall", "x" * 41)


def test_approve_unknown_id_raises(home):
    areas.create_area("town-hall", "Be kind.", "chauncey")
    with pytest.raises(KeyError):
        areas.approve("town-hall", "9999-zzzz", "chauncey")


def test_approve_unknown_area_raises(home):
    with pytest.raises(KeyError):
        areas.approve("ghost", "0001-ab12", "chauncey")


# ------------------------------------------------------------------- reject


def test_reject_requires_reason_and_moves_to_rejected(home):
    areas.create_area("town-hall", "Be kind.", "chauncey")
    pid = areas.post("town-hall", "spammer", "BUY NOW", "spam body")
    with pytest.raises(ValueError):
        areas.reject("town-hall", pid, "chauncey", "")
    with pytest.raises(ValueError):
        areas.reject("town-hall", pid, "chauncey", "   ")
    # Still pending after the refused rejections.
    assert len(areas.queue("town-hall")) == 1

    rec = areas.reject("town-hall", pid, "chauncey", "off-topic spam")
    assert rec["rejected_by"] == "chauncey"
    assert rec["reason"] == "off-topic spam"
    assert areas.queue("town-hall") == []
    assert areas.read("town-hall", "bea") == []  # rejected posts never publish
    assert [r["id"] for r in areas.rejected("town-hall")] == [pid]


def test_reject_unknown_id_raises(home):
    areas.create_area("town-hall", "Be kind.", "chauncey")
    with pytest.raises(KeyError):
        areas.reject("town-hall", "9999-zzzz", "chauncey", "spam")


# --------------------------------------------------------------- packets


def test_export_import_roundtrip_preserves_messages_and_charter_hash(
    tmp_path, monkeypatch
):
    h1 = tmp_path / "home1"
    h1.mkdir()
    monkeypatch.setenv("LEVI_HOME", str(h1))
    areas.create_area("town-hall", "Be kind, stay local.", "chauncey")
    pid = areas.post("town-hall", "ana", "Hello", "first post")
    areas.approve("town-hall", pid, "chauncey")
    h1_hash = areas.charter_hash("town-hall")

    packet = str(tmp_path / "town-hall.packet.json")
    dest = areas.export_packet("town-hall", packet)
    raw = json.loads((tmp_path / "town-hall.packet.json").read_text(encoding="utf-8"))
    assert raw["format"] == "levi-board-packet/1"
    assert raw["area"] == "town-hall"
    assert raw["charter_sha256"] == h1_hash
    assert dest == packet

    # Import into a SECOND LEVI_HOME: area created from the supplied charter.
    h2 = tmp_path / "home2"
    h2.mkdir()
    monkeypatch.setenv("LEVI_HOME", str(h2))
    n = areas.import_packet(packet, "town-hall", "Be kind, stay local.")
    assert n == 1
    assert areas.charter("town-hall") == "Be kind, stay local."
    assert areas.charter_hash("town-hall") == h1_hash
    msgs = areas.messages("town-hall")
    assert len(msgs) == 1
    assert msgs[0]["id"] == pid
    assert msgs[0]["body"] == "first post"


def test_import_skips_duplicates(home):
    areas.create_area("town-hall", "Be kind.", "chauncey")
    pid = areas.post("town-hall", "ana", "Hello", "first post")
    areas.approve("town-hall", pid, "chauncey")
    packet = str(home / "packet.json")
    areas.export_packet("town-hall", packet)
    assert areas.import_packet(packet, "town-hall", "Be kind.") == 0
    assert len(areas.messages("town-hall")) == 1


def test_import_bad_packet_format_raises(home, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"format": "QWK/1", "messages": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        areas.import_packet(str(bad), "town-hall", "Be kind.")


def test_import_empty_charter_raises(home, tmp_path):
    areas.create_area("town-hall", "Be kind.", "chauncey")
    packet = str(tmp_path / "packet.json")
    areas.export_packet("town-hall", packet)
    with pytest.raises(ValueError):
        areas.import_packet(packet, "new-area", "")


# ------------------------------------------------------------------- CLI


def test_cli_create_charter_post_queue_approve_read_roundtrip(home, capsys):
    create = ["create", "--name", "club", "--charter", "C.", "--moderator", "m"]
    assert boards_main(create) == 0
    assert boards_main(["charter", "--name", "club"]) == 0
    assert capsys.readouterr().out.strip().endswith("C.")
    post = [
        "post",
        "--name",
        "club",
        "--author",
        "ana",
        "--subject",
        "hi",
        "--body",
        "hello",
    ]
    assert boards_main(post) == 0
    pid = capsys.readouterr().out.split()[-1]
    assert boards_main(["queue", "--name", "club"]) == 0
    out = capsys.readouterr().out
    assert pid in out
    assert (
        boards_main(["approve", "--name", "club", "--id", pid, "--moderator", "m"]) == 0
    )
    assert boards_main(["read", "--name", "club", "--reader", "bea"]) == 0
    out = capsys.readouterr().out
    assert "hello" in out
    assert boards_main(["read", "--name", "club", "--reader", "bea"]) == 0
    assert capsys.readouterr().out.strip() == "nothing new"


def test_cli_errors_return_1(home, capsys):
    assert boards_main(["charter", "--name", "ghost"]) == 1
    assert (
        boards_main(["create", "--name", "club", "--charter", "", "--moderator", "m"])
        == 1
    )
    create = ["create", "--name", "club", "--charter", "C.", "--moderator", "m"]
    assert boards_main(create) == 0
    reject = [
        "reject",
        "--name",
        "club",
        "--id",
        "0001-ffff",
        "--moderator",
        "m",
        "--reason",
        "nope",
    ]
    assert boards_main(reject) == 1
