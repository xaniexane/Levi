"""Tests for the Story Table (levi.games.table): dice-first protocol,
hash-chained receipts, swappable roles, portable world packs."""

import sqlite3

import pytest

from levi.games import table
from levi.games.charter import is_fair


PACK = str(table._shipped_packs_dir() / "emberfall")


def _table(tmp_path, **kw):
    kw.setdefault("quiet", True)
    kw.setdefault("seed", 1234)
    return table.Table.new("emberfall", root=tmp_path, **kw)


# ---------------------------------------------------------------------------
# Dice spec parsing
# ---------------------------------------------------------------------------


def test_parse_spec_ok():
    assert str(table.parse_spec("2d6+3")) == "2d6+3"
    assert str(table.parse_spec("d20")) == "1d20"
    assert str(table.parse_spec("4d6-2")) == "4d6-2"
    assert str(table.parse_spec(" 3D8 + 1 ")) == "3d8+1"


def test_parse_spec_bad():
    for bad in ("", "d", "2d", "d1", "0d6", "2d6++3", "abc", "2d6+3d4"):
        with pytest.raises(ValueError):
            table.parse_spec(bad)


# ---------------------------------------------------------------------------
# Dice-first protocol: roll seals BEFORE narration can run
# ---------------------------------------------------------------------------


def test_check_seals_receipt_before_narration(tmp_path):
    t = _table(tmp_path)
    receipt, success = t.check("d20", vs=10, label="pick the lock")
    # the ledger already holds the sealed receipt
    sealed = t.receipts()
    assert len(sealed) == 1
    assert sealed[0].hash == receipt.hash
    assert sealed[0].total == receipt.total
    # narration receives the frozen receipt and cannot change the outcome
    story = t.narrate(receipt)
    assert ("SUCCESS" in receipt.format()) == success
    assert len(t.receipts()) == 1  # narration added nothing
    assert ("cleared by" in story) == success
    t.close()


def test_receipt_is_frozen(tmp_path):
    t = _table(tmp_path)
    receipt, _ = t.check("d20", vs=10, label="x")
    with pytest.raises(AttributeError):  # FrozenInstanceError subclasses it
        receipt.total = 99  # frozen dataclass — narration cannot edit it
    t.close()


def test_chain_verify_ok(tmp_path):
    t = _table(tmp_path)
    for _ in range(5):
        t.roll("2d6+3", label="s")
    ok, bad = t.verify()
    assert ok and bad is None
    t.close()


def test_chain_detects_tamper(tmp_path):
    t = _table(tmp_path)
    t.roll("d20", label="a")
    t.roll("d20", label="b")
    # tamper with a stored receipt directly in sqlite (the retcon attempt)
    conn = sqlite3.connect(str(tmp_path / "ledger.db"))
    conn.execute("UPDATE receipts SET total=20 WHERE slot=? AND seq=1", (t.slot,))
    conn.commit()
    conn.close()
    ok, bad = t.verify()
    assert not ok and bad == 1
    t.close()


def test_seeded_determinism(tmp_path):
    a = _table(tmp_path, slot="a", seed=99)
    b = _table(tmp_path, slot="b", seed=99)
    ra = [a.roll("d20").total for _ in range(10)]
    rb = [b.roll("d20").total for _ in range(10)]
    assert ra == rb
    a.close()
    b.close()


# ---------------------------------------------------------------------------
# Swappable roles
# ---------------------------------------------------------------------------


def test_role_swap_changes_voice(tmp_path):
    class GrimNarrator(table.Role):
        name = "grim"

        def narrate(self, ctx):
            rc = ctx["receipt"]
            return f"grim tidings: {rc.total} (sealed #{rc.seq:04d})"

    table.register_role("grim-test", GrimNarrator)
    t = _table(tmp_path)
    before = t.narrate(t.roll("d20"))
    old = t.swap_role("narrator", "grim-test")
    assert old == "hearth"
    receipt, _ = t.check("d20", vs=10, label="y")
    after = t.narrate(receipt)
    assert after != before
    assert "grim tidings" in after
    t.close()


def test_swap_rejects_unknown(tmp_path):
    t = _table(tmp_path)
    with pytest.raises(ValueError):
        t.swap_role("narrator", "nope")
    with pytest.raises(ValueError):
        t.swap_role("nope", "hearth")
    t.close()


def test_npc_and_scene_and_create(tmp_path):
    t = _table(tmp_path)
    assert "Mira Salt" in t.npc("mira", "good evening")
    assert "Harbor" in t.scene("harbor")
    assert "Emberfall" in t.lore()
    chartering = t.create_character("Ash", "drifter")
    assert "Ash" in chartering
    t.close()


# ---------------------------------------------------------------------------
# World packs: portable, round-trippable
# ---------------------------------------------------------------------------


def test_pack_roundtrip(tmp_path):
    dest = tmp_path / "emberfall.zip"
    out = table.export_pack(PACK, dest)
    assert out.is_file()
    installed = table.import_pack(out, root=tmp_path / "home", name="emberfall2")
    pack = table.load_pack(installed)
    assert pack["meta"]["name"] == "emberfall"
    assert len(pack["cast"]) == 4
    assert set(pack["scenes"]) == {"harbor", "lighthouse", "market"}
    assert set(pack["quests"]) == {"first-light", "glassfish"}


def test_pack_validation(tmp_path):
    with pytest.raises(ValueError):
        table.load_pack(tmp_path)  # empty dir
    with pytest.raises(ValueError):
        table.import_pack(tmp_path / "nope.zip", root=tmp_path)


def test_list_packs_includes_shipped(tmp_path):
    names = dict(table.list_packs(tmp_path))
    assert "emberfall" in names


# ---------------------------------------------------------------------------
# Charter + odds audit
# ---------------------------------------------------------------------------


def test_charter_fair():
    assert is_fair(table.manifest())


def test_prove_reports_honest():
    report = table.prove(trials=6000, seed=7)
    assert "ODDS HONEST" in report


def test_save_load_roundtrip(tmp_path):
    t = _table(tmp_path, slot="s1")
    t.swap_role("cast", "cast-director")
    t.roll("d20", label="z")
    t.save()
    t.close()
    t2 = table.Table.load("s1", root=tmp_path, quiet=True)
    assert t2.roles["cast"] == "cast-director"
    assert len(t2.receipts()) == 1  # ledger persists per slot
    t2.close()
