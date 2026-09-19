"""Tests for levi.fairtrade — the honest-trade module."""

from __future__ import annotations

import json
import os

import pytest

from levi.fairtrade import (
    PATTERNS,
    audit_offer,
    declare_trade,
    get_pattern,
    pattern_ids,
    read_ledger,
)


class TestCatalog:
    def test_four_patterns(self):
        assert len(PATTERNS) == 4
        assert set(pattern_ids()) == {
            "walled-garden-generosity",
            "asymmetric-rules",
            "roach-motel-funnel",
            "manufactured-social-debt",
        }

    def test_each_pattern_has_inversion_and_refusal(self):
        for p in PATTERNS:
            for key in (
                "the_generosity",
                "the_capture",
                "what_they_refuse",
                "inversion",
                "exemplar",
                "signals",
            ):
                assert p[key], p["id"]

    def test_get_pattern(self):
        p = get_pattern("asymmetric-rules")
        assert p is not None and p["name"].startswith("Asymmetric")
        assert get_pattern("nope") is None


class TestAudit:
    def _free_vpn(self):
        return {
            "name": "Free VPN",
            "gives": ["private browsing", "no account needed"],
            "asks": [],
            "hidden": ["sells aggregate traffic logs"],
            "entry_steps": 1,
            "exit_steps": 8,
            "rule_binds_maker": None,
            "manufactures_obligation": False,
        }

    def test_hidden_costs_fail_hard(self):
        report = audit_offer(self._free_vpn())
        assert report["score"] <= 45
        assert report["verdict"] in ("sly", "predatory")
        checks = {f["check"]: f["result"] for f in report["findings"]}
        assert checks["hidden-cost"] == "fail"
        assert checks["symmetric-friction"] == "fail"

    def test_nothing_asked_is_the_biggest_tell(self):
        offer = {
            "name": "Free Photos",
            "gives": ["unlimited backup"],
            "asks": [],
            "hidden": [],
            "entry_steps": 1,
            "exit_steps": 1,
            "rule_binds_maker": True,
        }
        report = audit_offer(offer)
        checks = {f["check"]: f["result"] for f in report["findings"]}
        assert checks["disclosed-cost"] == "fail"
        assert report["score"] < 100

    def test_honest_offer_scores_high(self):
        offer = {
            "name": "LEVI Fair Trade catalog",
            "gives": ["sly-generosity pattern catalog"],
            "asks": ["nothing; pure archive entry"],
            "hidden": [],
            "entry_steps": 1,
            "exit_steps": 1,
            "rule_binds_maker": True,
            "manufactures_obligation": False,
        }
        report = audit_offer(offer)
        assert report["verdict"] == "honest"
        assert report["score"] == 100

    def test_asymmetric_rule_penalized(self):
        offer = {
            "name": "Privacy Shield",
            "gives": ["tracking protection"],
            "asks": ["install our browser"],
            "entry_steps": 2,
            "exit_steps": 2,
            "rule_binds_maker": False,
        }
        report = audit_offer(offer)
        checks = {f["check"]: f["result"] for f in report["findings"]}
        assert checks["rule-binds-maker"] == "fail"
        assert report["score"] == 80  # one serious flaw: sly, not damning

    def test_manufactured_obligation_penalized(self):
        offer = {
            "name": "Friend Score",
            "gives": ["daily friendship points"],
            "asks": ["daily check-in"],
            "entry_steps": 1,
            "exit_steps": 1,
            "rule_binds_maker": True,
            "manufactures_obligation": True,
        }
        report = audit_offer(offer)
        checks = {f["check"]: f["result"] for f in report["findings"]}
        assert checks["obligation-free"] == "fail"

    def test_missing_steps_are_unknown_not_clean(self):
        offer = {"name": "Mystery Box", "gives": ["a box"], "asks": ["your email"]}
        report = audit_offer(offer)
        checks = {f["check"]: f["result"] for f in report["findings"]}
        assert checks["symmetric-friction"] == "unknown"
        assert report["score"] < 100

    def test_bad_offer_rejected(self):
        with pytest.raises(ValueError):
            audit_offer({})
        with pytest.raises(ValueError):
            audit_offer({"name": "  "})

    def test_pattern_matching_finds_streaks(self):
        offer = {
            "name": "SnapScore Pro",
            "gives": ["daily streak score with friends"],
            "asks": ["message every day"],
            "entry_steps": 1,
            "exit_steps": 1,
            "rule_binds_maker": True,
            "manufactures_obligation": True,
        }
        report = audit_offer(offer)
        ids = [m["pattern_id"] for m in report["patterns"]]
        assert "manufactured-social-debt" in ids


class TestLedger:
    def test_declare_and_read(self, tmp_path):
        home = tmp_path / "home"
        rec = declare_trade(
            name="Test generosity",
            gives=["a pattern catalog"],
            asks=["nothing"],
            note="pure archive entry",
            home=home,
        )
        assert rec["name"] == "Test generosity"
        entries = read_ledger(home=home)
        assert len(entries) == 1
        assert entries[0]["asks"] == ["nothing"]

    def test_owner_only_permissions(self, tmp_path):
        home = tmp_path / "home"
        declare_trade("T", ["g"], [], home=home)
        d = home / ".levi" / "fairtrade"
        assert oct(os.stat(d).st_mode & 0o777) == "0o700"
        assert oct(os.stat(d / "ledger.jsonl").st_mode & 0o777) == "0o600"

    def test_empty_ledger(self, tmp_path):
        assert read_ledger(home=tmp_path / "nope") == []

    def test_rejects_empty_name_and_gives(self, tmp_path):
        with pytest.raises(ValueError):
            declare_trade("", ["g"], [], home=tmp_path)
        with pytest.raises(ValueError):
            declare_trade("N", [], [], home=tmp_path)

    def test_append_only(self, tmp_path):
        home = tmp_path / "home"
        declare_trade("One", ["a"], [], home=home)
        declare_trade("Two", ["b"], [], home=home)
        entries = read_ledger(home=home)
        assert [e["name"] for e in entries] == ["One", "Two"]
