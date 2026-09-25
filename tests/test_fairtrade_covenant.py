"""Tests for the free-tier covenant (fairtrade/covenant.py).

The covenant is the honest inversion of the three rug-pull patterns:
bait-and-rug-free-tier (Google Photos), cap-the-habit (IFTTT),
frozen-generosity (iCloud). It must catch the giants' shapes and pass
LEVI's own.
"""

import pytest

from levi.fairtrade import FreeTierCovenant, audit_covenant
from levi.fairtrade.covenant import BAIT_WORDS


def _honest():
    return FreeTierCovenant(
        feature="media vault",
        free_offers=[
            "photo storage up to your own 500 GB disk",
            "10,000 local automation rules",
        ],
        never=[
            "shrink the free tier under existing users",
            "charge for export",
            "narrow 'free' after a dependency forms",
        ],
        grandfather_clause=(
            "Existing users keep their signup terms forever; any future "
            "narrowing applies to new signups only."
        ),
        export_path="levi vault export --format zip",
        grows_with_medium=True,
        mandates_own_paid_path=False,
    )


class TestHonestCovenant:
    def test_fully_honest_covenant_scores_100(self):
        report = audit_covenant(_honest())
        assert report["score"] == 100
        assert report["verdict"] == "honest"

    def test_covenant_exports_public_api(self):
        import levi.fairtrade as ft

        assert "FreeTierCovenant" in ft.__all__
        assert "audit_covenant" in ft.__all__

    def test_related_patterns_are_the_rugpull_trio(self):
        report = audit_covenant(_honest())
        assert report["related_patterns"] == [
            "bait-and-rug-free-tier",
            "cap-the-habit",
            "frozen-generosity",
        ]


class TestBaitAndRugShape:
    def test_google_photos_shape_fails(self):
        # "free unlimited photo backup forever" + mandated paid path
        covenant = FreeTierCovenant(
            feature="photos",
            free_offers=["free unlimited photo backup forever"],
            mandates_own_paid_path=False,
        )
        report = audit_covenant(covenant)
        assert report["verdict"] == "rugpull-risk"
        failed = {f["check"] for f in report["findings"] if f["result"] == "fail"}
        assert "plain-numbers" in failed
        assert "bait-words" in failed

    def test_bait_words_flagged(self):
        for word in ("unlimited", "free forever", "no limits"):
            covenant = FreeTierCovenant(
                feature="x", free_offers=["%s storage" % word]
            )
            report = audit_covenant(covenant)
            failed = {f["check"] for f in report["findings"] if f["result"] == "fail"}
            assert "bait-words" in failed, word

    def test_bait_words_with_numbers_are_plain_numbers(self):
        # "unlimited in count, 500 GB of your disk" states a number.
        covenant = _honest()
        report = audit_covenant(covenant)
        failed = {f["check"] for f in report["findings"] if f["result"] == "fail"}
        assert "bait-words" not in failed


class TestCapTheHabitShape:
    def test_ifttt_shape_fails_without_never_list(self):
        # Shrinking the free tier under existing users: no never-list,
        # no grandfather clause — exactly IFTTT's 3-applet move.
        covenant = FreeTierCovenant(
            feature="automation",
            free_offers=["3 applets for free"],
            export_path="download your applets",
            grows_with_medium=False,
        )
        report = audit_covenant(covenant)
        failed = {f["check"] for f in report["findings"] if f["result"] == "fail"}
        assert "never-list" in failed
        assert "grandfather" in failed
        assert report["verdict"] in ("weak", "rugpull-risk")


class TestFrozenGenerosityShape:
    def test_icloud_shape_fails_mandated_toll(self):
        covenant = FreeTierCovenant(
            feature="backup",
            free_offers=["5 GB of cloud storage"],
            never=["reduce the free tier"],
            grandfather_clause="Nothing changes for existing users.",
            export_path="takeout export",
            grows_with_medium=False,
            mandates_own_paid_path=True,  # full backup only via our paid service
        )
        report = audit_covenant(covenant)
        failed = {f["check"] for f in report["findings"] if f["result"] == "fail"}
        assert "no-mandated-toll" in failed
        assert "grows-with-medium" in failed

    def test_frozen_floor_alone_is_weak(self):
        covenant = FreeTierCovenant(
            feature="storage",
            free_offers=["5 GB free"],
            never=["remove the free tier"],
            grandfather_clause="Kept for existing users.",
            export_path="export tool",
            grows_with_medium=False,
        )
        report = audit_covenant(covenant)
        failed = {f["check"] for f in report["findings"] if f["result"] == "fail"}
        assert "grows-with-medium" in failed
        assert report["verdict"] != "honest"


class TestHonestGaps:
    def test_empty_feature_rejected(self):
        with pytest.raises(ValueError):
            audit_covenant(FreeTierCovenant(feature="  "))

    def test_wrong_type_rejected(self):
        with pytest.raises(ValueError):
            audit_covenant({"feature": "x"})

    def test_bait_words_list_is_nonempty(self):
        assert "unlimited" in BAIT_WORDS

    def test_score_never_negative(self):
        covenant = FreeTierCovenant(feature="x")
        report = audit_covenant(covenant)
        assert report["score"] >= 0
        assert report["verdict"] == "rugpull-risk"
