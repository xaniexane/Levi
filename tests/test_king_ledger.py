"""King continuity ledger: rank ladder, harvest aggregation, persistence."""
import json
import os
import stat

from levi.king.ledger import ContinuityLedger


def _ledger(tmp_path):
    return ContinuityLedger(data_dir=tmp_path / "king")


def test_fresh_ledger_is_d2(tmp_path):
    led = _ledger(tmp_path)
    assert led.rank() == "D2"
    assert led.total_words == 0
    assert led.total_banks == 0


def test_rank_advances_on_words(tmp_path):
    led = _ledger(tmp_path)
    led.harvest("model_engine", 6_000, 0, "expand")
    assert led.rank() == "D3"


def test_rank_advances_on_banks_not_words_alone(tmp_path):
    # The blueprint's key point: banks alone must move the ladder.
    led = _ledger(tmp_path)
    led.harvest("story_fabric", 0, 12, "twelve beats, zero counted words")
    assert led.total_words == 0
    assert led.rank() == "D3"


def test_rank_d4_via_banks(tmp_path):
    led = _ledger(tmp_path)
    led.harvest("story_fabric", 100, 35, "beats")
    assert led.rank() == "D4"


def test_rank_d4_via_words(tmp_path):
    led = _ledger(tmp_path)
    led.harvest("model_engine", 25_000, 0, "expand")
    assert led.rank() == "D4"


def test_rank_d5_gold_path(tmp_path):
    led = _ledger(tmp_path)
    led.harvest("model_engine", 80_000, 40, "gold push")
    assert led.rank() == "D5"


def test_negative_harvest_floors_total_at_zero(tmp_path):
    led = _ledger(tmp_path)
    led.harvest("model_engine", -500, 0, "deny more than banked")
    assert led.total_words == 0


def test_entities_and_edges_roundtrip(tmp_path):
    led = _ledger(tmp_path)
    led.register_entity("story.abc", "story", "Test Tale", {"genre": "noir"})
    led.add_edge("story.abc", "story.abc:beat:1", "advances", "hook")
    led2 = ContinuityLedger(data_dir=tmp_path / "king")
    assert led2.entities["story.abc"]["name"] == "Test Tale"
    assert led2.entities["story.abc"]["meta"]["genre"] == "noir"
    assert led2.edges[-1]["relation"] == "advances"


def test_fingerprint_stable_and_sensitive(tmp_path):
    led = _ledger(tmp_path)
    fp1 = led.fingerprint()
    led2 = ContinuityLedger(data_dir=tmp_path / "king")
    assert led2.fingerprint() == fp1
    led.harvest("king", 10, 1, "event")
    assert led.fingerprint() != fp1


def test_promote_d5_and_reset(tmp_path):
    led = _ledger(tmp_path)
    led.promote_d5()
    assert led.rank() == "D5"
    assert led.promoted["demo"] is True
    led2 = ContinuityLedger(data_dir=tmp_path / "king")
    assert led2.rank() == "D5"  # persists
    assert led2.reset_promotion() is True
    assert led2.rank() == "D2"


def test_ledger_file_is_owner_only(tmp_path):
    led = _ledger(tmp_path)
    led.harvest("king", 1, 1, "x")
    mode = stat.S_IMODE(os.stat(led.path).st_mode)
    assert mode == 0o600, f"ledger.json mode is {oct(mode)}, expected 0o600"


def test_corrupt_ledger_starts_clean(tmp_path):
    d = tmp_path / "king"
    d.mkdir()
    (d / "ledger.json").write_text("{not json", encoding="utf-8")
    led = ContinuityLedger(data_dir=d)
    assert led.rank() == "D2"
    assert led.total_words == 0


def test_summary_shape(tmp_path):
    led = _ledger(tmp_path)
    led.harvest("story_fabric", 100, 2, "pulse")
    s = led.summary()
    assert s["rank"] == "D2"
    assert s["total_words"] == 100
    assert s["total_banks"] == 2
    assert s["harvests"] == 1
    assert len(s["fingerprint"]) == 16
    # raw file is valid JSON with expected keys
    raw = json.loads(led.path.read_text(encoding="utf-8"))
    assert {"entities", "edges", "harvests"} <= set(raw)
