"""Tests for levi.fairplay — honest games, machine-checked laws.

Covers: honestdraw (transparent seeded draws), ownedtrack
(never-expiring progression), library (unrevocable ownership), and the
package law that no till-vocabulary exists anywhere in the modules.
"""

import random
import json as _stdlib_json
import re

import pytest

from levi.fairplay import honestdraw, library, ownedtrack
from levi.fairplay.honestdraw import Drop, DropTable, FairDraw, replay
from levi.fairplay.library import OwnedLibrary
from levi.fairplay.ownedtrack import COSMETIC_KINDS, OwnedTrack, Reward, TrackShelf


def json_loads(text):
    return _stdlib_json.loads(text)


def _table() -> DropTable:
    return DropTable(
        [
            Drop("stick", "common", 70.0),
            Drop("hat", "uncommon", 20.0),
            Drop("cloak", "rare", 8.0),
            Drop("crown", "epic", 1.9),
            Drop("star", "legendary", 0.1),
        ]
    )


# ---------------------------------------------------------------- honestdraw


def test_odds_are_public_and_exact():
    published = _table().publish()
    total = sum(row["probability"] for row in published)
    assert abs(total - 1.0) < 1e-12
    by_name = {row["name"]: row for row in published}
    assert by_name["star"]["probability"] == pytest.approx(0.001)
    assert by_name["stick"]["probability"] == pytest.approx(0.70)


def test_table_rejects_bad_rows():
    with pytest.raises(ValueError):
        Drop("x", "mythic", 1.0)
    with pytest.raises(ValueError):
        Drop("x", "common", 0.0)
    with pytest.raises(ValueError):
        DropTable([])


def test_draws_are_deterministic_from_seed():
    a, b = FairDraw(_table(), 42), FairDraw(_table(), 42)
    a.play_earned = b.play_earned = 50
    seq_a = [(e.item, e.rarity) for e in (a.draw() for _ in range(50))]
    seq_b = [(e.item, e.rarity) for e in (b.draw() for _ in range(50))]
    assert seq_a == seq_b
    # ...and a different seed diverges (overwhelmingly likely)
    c = FairDraw(_table(), 43)
    c.play_earned = 50
    seq_c = [(e.item, e.rarity) for e in (c.draw() for _ in range(50))]
    assert seq_c != seq_a


def test_replay_regenerates_the_log():
    engine = FairDraw(_table(), 7, pity_ceiling=25)
    engine.play_earned = 60
    live = [engine.draw() for _ in range(60)]
    again = replay(_table(), 7, 25, "rare", 60)
    assert [(e.item, e.rarity, e.pity_triggered) for e in live] == [
        (e.item, e.rarity, e.pity_triggered) for e in again
    ]


def test_pity_is_a_guarantee_not_a_hope():
    ceiling = 10
    engine = FairDraw(_table(), 1234, pity_ceiling=ceiling, pity_rarity="rare")
    engine.play_earned = 500
    gap = 0
    max_gap = 0
    for _ in range(500):
        entry = engine.draw()
        rare_enough = honestdraw.RARITIES.index(entry.rarity) >= honestdraw.RARITIES.index("rare")
        if rare_enough:
            gap = 0
        else:
            gap += 1
            max_gap = max(max_gap, gap)
    assert max_gap < ceiling


def test_log_verifies_and_detects_tampering():
    engine = FairDraw(_table(), 99, pity_ceiling=20)
    engine.play_earned = 30
    for _ in range(30):
        engine.draw()
    ok, _ = engine.verify_log()
    assert ok
    engine._log.pop(5)  # tamper: remove an entry
    ok, why = engine.verify_log()
    assert not ok


def test_draw_requires_earned_play():
    engine = FairDraw(_table(), 1)
    with pytest.raises(RuntimeError):
        engine.draw()
    engine.earn_play(3)
    engine.draw()
    assert engine.play_earned == 2
    with pytest.raises(ValueError):
        engine.earn_play(-1)


# ---------------------------------------------------------------- ownedtrack


def test_track_has_no_expiry_anywhere():
    track = OwnedTrack("season-one", [Reward(1, "blue cloak", "skin")])
    for attr in ("expires", "expiry", "deadline", "ends_at", "season_end", "decay"):
        assert not hasattr(track, attr), attr
    assert "expir" not in OwnedTrack.__init__.__code__.co_varnames


def test_power_rewards_are_refused():
    with pytest.raises(ValueError):
        Reward(1, "sword of +10", "weapon")
    with pytest.raises(ValueError):
        OwnedTrack("x", [Reward(1, "xp boost", "boost")])


def test_progress_only_moves_forward_and_claims_are_permanent():
    track = OwnedTrack(
        "s1",
        [Reward(1, "hat", "avatar"), Reward(2, "dance", "emote")],
        xp_per_tier=10,
    )
    assert track.add_play(15) == 1
    with pytest.raises(ValueError):
        track.add_play(-5)
    assert track.xp == 15  # negative play did not land
    assert track.claim() == ["hat"]
    track.add_play(10)
    assert track.claim() == ["dance"]
    assert track.claim() == []  # claimed stays claimed
    assert set(track.claimed) == {"hat", "dance"}


def test_shelf_switching_preserves_every_track():
    shelf = TrackShelf()
    a = OwnedTrack("alpha", [Reward(1, "banner-a", "banner")], xp_per_tier=10)
    b = OwnedTrack("beta", [Reward(1, "banner-b", "banner")], xp_per_tier=10)
    shelf.add(a)
    shelf.add(b)
    shelf.active.add_play(35)
    before = shelf.progress_snapshot()
    shelf.switch("beta")
    shelf.active.add_play(5)
    shelf.switch("alpha")
    assert shelf.progress_snapshot()["alpha"] == before["alpha"]
    assert shelf.active.xp == 35
    with pytest.raises(KeyError):
        shelf.switch("nope")


def test_track_state_survives_export_roundtrip():
    track = OwnedTrack("s1", [Reward(1, "hat", "avatar")], xp_per_tier=10)
    track.add_play(25)
    track.claim()
    twin = OwnedTrack.import_state(track.export_state())
    assert (twin.xp, twin.claimed, twin.name) == (25, ["hat"], "s1")


# ---------------------------------------------------------------- library


def test_ownership_receipts_chain_and_verify():
    lib = OwnedLibrary()
    lib.register("asteroids-clone", "sha256:abc", "local-build")
    lib.register("rogue-clone", "sha256:def", "drm-free")
    ok, _ = lib.verify_chain()
    assert ok
    assert lib.titles == ["asteroids-clone", "rogue-clone"]
    with pytest.raises(ValueError):
        lib.register("asteroids-clone", "sha256:zzz", "drm-free")


def test_tampered_receipt_breaks_the_chain():
    lib = OwnedLibrary()
    lib.register("a", "h1", "local-build")
    lib.register("b", "h2", "local-build")
    lib._receipts[0] = library.OwnershipReceipt(
        title="a (forged)", build_hash="h1", source="local-build",
        registered_at=lib._receipts[0].registered_at,
        prev_hash=lib._receipts[0].prev_hash,
    )
    ok, _ = lib.verify_chain()
    assert not ok


def test_there_is_no_revocation_primitive():
    lib = OwnedLibrary()
    for attr in ("revoke", "remove", "unregister", "delete", "delist", "retire"):
        assert not hasattr(lib, attr), attr


def test_saves_export_import_roundtrip_with_checksum():
    lib = OwnedLibrary()
    lib.register("rogue-clone", "sha256:def", "drm-free")
    envelope = lib.export_save("rogue-clone", "slot-1", b"\x00\x01hero-data")
    game, slot, raw = lib.import_save(envelope)
    assert (game, slot, raw) == ("rogue-clone", "slot-1", b"\x00\x01hero-data")
    # Corrupt one byte of the payload: the checksum must refuse it.
    import base64, hashlib, json
    doc = json.loads(envelope)
    raw2 = base64.b64decode(doc["data"])
    doc["data"] = base64.b64encode(b"X" + raw2[1:]).decode("ascii")
    with pytest.raises(ValueError, match="checksum"):
        lib.import_save(json.dumps(doc))


def test_shelf_export_survives_a_dead_seller():
    lib = OwnedLibrary()
    lib.register("a", "h1", "drm-free")
    lib.export_save("a", "slot-1", b"progress")
    document = lib.export_shelf()
    # "The seller" is gone: rebuild from the document alone, no network.
    reborn = OwnedLibrary.import_shelf(document)
    ok, _ = reborn.verify_chain()
    assert ok and reborn.titles == ["a"]
    game, slot, raw = reborn.import_save(json_loads(document)["saves"][0])
    assert raw == b"progress"


# ---------------------------------------------------------------- package law


TILL_WORDS = re.compile(
    r"\b(price|prices|purchase|purchased|purchases|payment|payments|wallet|wallets|"
    r"premium|stripe|paypal|billing|subscription|subscriptions|monetiz\w*|"
    r"whale|whales|money|cost|costs)\b",
    re.IGNORECASE,
)


def test_no_till_vocabulary_in_fairplay_sources():
    import pathlib
    pkg = pathlib.Path(honestdraw.__file__).parent
    offenders = []
    for path in sorted(pkg.glob("*.py")):
        text = path.read_text()
        for i, line in enumerate(text.splitlines(), 1):
            if TILL_WORDS.search(line):
                offenders.append(f"{path.name}:{i}: {line.strip()}")
    assert not offenders, "till vocabulary found:\n" + "\n".join(offenders)
