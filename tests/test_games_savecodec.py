"""Hermetic tests for the save codec (password-save revival)."""

import pytest

from levi.games import savecodec
from levi.games.savecodec import SaveCodecError, decode, describe, encode


def test_round_trip_milestones():
    ms = {"bosses": ["cutman", "gutsman"], "etanks": 2, "stage": "wily1"}
    code = encode("megaman", ms)
    env = decode(code)
    assert env["game"] == "megaman"
    assert env["schema"] == savecodec.SCHEMA
    assert env["milestones"] == ms


def test_code_is_printable_grouped_string():
    code = encode("mancala", {"wins": 12})
    assert code
    assert all(c.isupper() or c.isdigit() or c == "-" for c in code)
    assert "-" in code  # chunked for readability
    # no confusing lowercase, no padding
    assert "=" not in code


def test_typo_is_caught_not_decoded():
    code = encode("mancala", {"wins": 12})
    # flip one character to a different valid one
    bad = ("Z" if code[0] != "Z" else "Y") + code[1:]
    with pytest.raises(SaveCodecError) as ei:
        decode(bad)
    assert "checksum" in str(ei.value).lower() or "mistyped" in str(ei.value).lower()


def test_garbage_is_refused():
    for junk in ["", "hello world", "!!!!", "MANC", "a" * 3]:
        with pytest.raises(SaveCodecError):
            decode(junk)


def test_wrong_game_refused_with_expected():
    code = encode("mancala", {"wins": 1})
    with pytest.raises(SaveCodecError) as ei:
        decode(code, expected_game="bagatelle")
    assert "mancala" in str(ei.value)


def test_case_and_separator_insensitive():
    code = encode("mancala", {"wins": 3})
    assert decode(code.lower().replace("-", " "))["milestones"] == {"wins": 3}


def test_empty_milestones_ok():
    env = decode(encode("nim", {}))
    assert env["milestones"] == {}


def test_bad_game_id_rejected():
    with pytest.raises(SaveCodecError):
        encode("../../etc", {"x": 1})
    with pytest.raises(SaveCodecError):
        encode("", {"x": 1})


def test_non_serializable_rejected():
    with pytest.raises(SaveCodecError):
        encode("nim", {"x": object()})


def test_describe_honest_on_corrupt():
    out = describe("ZZZZ-ZZZZ")
    assert out.startswith("unreadable:")


def test_describe_reports_checksum_ok():
    code = encode("mancala", {"a": 1, "b": 2})
    out = describe(code)
    assert "checksum OK" in out and "mancala" in out


def test_forged_code_is_decodable_by_design():
    # Forgery is a feature (like the Game Genie era): a valid checksum
    # with invented milestones decodes fine. Corruption is caught;
    # intent is not policed.
    ms = {"bosses": ["everyone"], "etanks": 99}
    assert decode(encode("megaman", ms))["milestones"] == ms
