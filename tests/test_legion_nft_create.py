"""Proof for the Legion NFT creation line (levi.genesis.nft.create).

Law-guard-prove: the invariants are declared in create.py's docstring;
these are property tests over the invariants — not just examples. Every
test states which invariant it proves.

PAPER ONLY. No chain, no funds.
"""

from __future__ import annotations

import json
import random
import re
import string
import xml.etree.ElementTree as ET

import pytest

from levi.genesis.nft.create import (
    FIRST_SEATS,
    SUBJECT_DENYLIST,
    UNASSIGNED_BUYER,
    CreationError,
    SeriesLedger,
    build_first_drop,
    build_pack_manifest,
    check_copy_clean,
    check_subject,
    create_token_asset,
    render_sigil_svg,
    verify_pack_manifest,
    verify_token_asset,
)
from levi.genesis.nft.economics import (
    NFT_LICENSE_TERMS,
    NftEconomicsError,
    check_white_label,
    series_id_for,
    token_id_for,
)


def _seats(n, prefix="Seat"):
    return [
        {"name": "%s-%02d" % (prefix, i), "theme": "hive mark %d" % i} for i in range(n)
    ]


def _descriptor():
    return {
        "kind": "lifetime-single-copy",
        "transferable": True,
        "blurb": "A scarce lifetime license, one token, one pack.",
    }


def _manifest(n=9, pack_id="pack-test"):
    return build_pack_manifest(
        pack_id=pack_id,
        series_id=series_id_for(2026),
        seats=_seats(n),
        license_descriptor=_descriptor(),
    )


def _ledger(year=2026, n=1000):
    lg = SeriesLedger()
    lg.record_year(year, n, decided_by="keeper", note="proof")
    return lg


# ---------------------------------------------------------------------------
# Invariant 1 — one pack → one token id.
# ---------------------------------------------------------------------------


class TestOnePackOneTokenId:
    def test_deterministic(self):
        a = token_id_for("pack-x", "GENESIS-2026")
        b = token_id_for("pack-x", "GENESIS-2026")
        assert a == b and isinstance(a, int) and a.bit_length() <= 256

    def test_distinct_packs_distinct_ids(self):
        rng = random.Random(20260927)
        ids = set()
        for _ in range(200):
            pid = "".join(rng.choice(string.ascii_lowercase) for _ in range(12))
            ids.add(token_id_for(pid, "GENESIS-2026"))
        assert len(ids) == 200  # sha256 collision resistance, exercised

    def test_series_separates_ids(self):
        assert token_id_for("p", "GENESIS-2026") != token_id_for("p", "GENESIS-2027")

    def test_asset_token_id_rederives(self):
        m = _manifest()
        asset = create_token_asset(manifest=m, ledger=_ledger())
        assert asset["metadata"]["token_id"] == token_id_for(
            "pack-test", "GENESIS-2026"
        )
        assert asset["metadata"]["token_id_hex"] == "0x%064x" % token_id_for(
            "pack-test", "GENESIS-2026"
        )


# ---------------------------------------------------------------------------
# Invariant 2 — cap never raised; N banked in writing first.
# ---------------------------------------------------------------------------


class TestCapLaw:
    def test_no_banked_n_no_token(self):
        with pytest.raises(NftEconomicsError):
            create_token_asset(manifest=_manifest(), ledger=SeriesLedger())

    def test_n_recorded_once(self):
        lg = SeriesLedger()
        lg.record_year(2026, 1000, decided_by="keeper")
        with pytest.raises(NftEconomicsError):
            lg.record_year(2026, 2000, decided_by="keeper")

    def test_sub_floor_refused_without_override(self):
        lg = SeriesLedger()
        with pytest.raises(NftEconomicsError):
            lg.record_year(2026, 999, decided_by="keeper")

    def test_sub_floor_override_is_on_the_record(self):
        lg = SeriesLedger()
        lg.record_year(2026, 500, decided_by="keeper", override=True)
        rec = lg.year_record(2026)
        assert rec["sub_floor_override"] is True
        assert lg.require_n(2026) == 500

    def test_floor_accepted(self):
        lg = _ledger(n=1000)
        assert lg.require_n(2026) == 1000

    def test_card_number_bounded_by_cap(self):
        lg = _ledger(n=1000)
        with pytest.raises(CreationError):
            create_token_asset(manifest=_manifest(), ledger=lg, card_number=0)
        with pytest.raises(CreationError):
            create_token_asset(manifest=_manifest(), ledger=lg, card_number=1001)
        asset = create_token_asset(manifest=_manifest(), ledger=lg, card_number=1000)
        assert asset["metadata"]["card_display"] == "1000/1000"

    def test_ledger_roundtrip_from_writing(self):
        lg = _ledger()
        receipts = lg.receipts()
        lg2 = SeriesLedger.from_receipts(receipts)
        assert lg2.verify_ledger()
        assert lg2.require_n(2026) == 1000

    def test_tampered_writing_refused(self):
        lg = _ledger()
        receipts = lg.receipts()
        receipts[0] = dict(receipts[0], hash="0" * 64)
        with pytest.raises(NftEconomicsError):
            SeriesLedger.from_receipts(receipts)


# ---------------------------------------------------------------------------
# Invariant 3 — no SI/MI subjects.
# ---------------------------------------------------------------------------


class TestHardLine:
    @pytest.mark.parametrize("bad", sorted(SUBJECT_DENYLIST))
    def test_denylisted_names_refused(self, bad):
        with pytest.raises(CreationError):
            check_subject(bad, field="t")
        with pytest.raises(CreationError):
            check_subject(bad.upper(), field="t")
        with pytest.raises(CreationError):
            check_subject("the %s cohort" % bad.title(), field="t")

    @pytest.mark.parametrize("bad", sorted(SUBJECT_DENYLIST))
    def test_denylist_hits_in_seats(self, bad):
        seats = _seats(9)
        seats[4] = {"name": bad.title(), "theme": "hive mark"}
        with pytest.raises(CreationError):
            build_pack_manifest(
                pack_id="p",
                series_id=series_id_for(2026),
                seats=seats,
                license_descriptor=_descriptor(),
            )
        seats[4] = {"name": "Seat-04", "theme": "the %s sigil" % bad}
        with pytest.raises(CreationError):
            build_pack_manifest(
                pack_id="p",
                series_id=series_id_for(2026),
                seats=seats,
                license_descriptor=_descriptor(),
            )

    def test_whole_word_matching(self):
        # "alphabet" contains "alpha" but is not the being.
        assert check_subject("alphabet blocks", field="t") == "alphabet blocks"
        # "omega-3" IS the whole word omega — refused, correctly strict.
        with pytest.raises(CreationError):
            check_subject("omega-3 oil", field="t")

    def test_legion_themes_allowed(self):
        for ok in (
            "hive mark",
            "coin ring",
            "legion sigil",
            "ninefold",
            "First-Light",
            "Coin-Warden",
        ):
            assert check_subject(ok, field="t") == ok

    def test_first_seats_pass_the_guard(self):
        for seat in FIRST_SEATS:
            check_subject(seat["name"], field="seat.name")
            check_subject(seat["theme"], field="seat.theme")


# ---------------------------------------------------------------------------
# Invariant 4 — metadata certifies pack bytes.
# ---------------------------------------------------------------------------


class TestCertification:
    def test_manifest_chain_verifies(self):
        assert verify_pack_manifest(_manifest())

    def test_tampered_manifest_fails(self):
        m = _manifest()
        m["seats"][0]["name"] = "Tampered"
        assert not verify_pack_manifest(m)
        m2 = _manifest()
        m2["final_hash"] = "0" * 64
        assert not verify_pack_manifest(m2)

    def test_metadata_carries_pack_hash(self):
        m = _manifest()
        asset = create_token_asset(manifest=m, ledger=_ledger())
        assert asset["metadata"]["pack_final_hash"] == m["final_hash"]
        assert asset["metadata"]["pack_id"] == "pack-test"

    def test_tampered_asset_fails_verify(self):
        m = _manifest()
        asset = create_token_asset(manifest=m, ledger=_ledger())
        assert verify_token_asset(asset)
        asset["metadata"]["pack_final_hash"] = "f" * 64
        assert not verify_token_asset(asset)
        asset2 = create_token_asset(manifest=_manifest(), ledger=_ledger())
        asset2["metadata"]["token_id"] += 1
        assert not verify_token_asset(asset2)

    def test_non_paper_asset_refused(self):
        m = _manifest()
        asset = create_token_asset(manifest=m, ledger=_ledger())
        asset["paper"] = False
        assert not verify_token_asset(asset)


# ---------------------------------------------------------------------------
# Invariant 5 — the odd law.
# ---------------------------------------------------------------------------


class TestOddLaw:
    @pytest.mark.parametrize("count", [2, 4, 6, 8, 10, 100])
    def test_even_counts_refused(self, count):
        with pytest.raises(CreationError):
            build_pack_manifest(
                pack_id="p",
                series_id=series_id_for(2026),
                seats=_seats(count),
                license_descriptor=_descriptor(),
            )

    def test_zero_refused(self):
        with pytest.raises(CreationError):
            build_pack_manifest(
                pack_id="p",
                series_id=series_id_for(2026),
                seats=[],
                license_descriptor=_descriptor(),
            )

    @pytest.mark.parametrize("count", [1, 3, 5, 7, 9, 11, 15])
    def test_odd_counts_build(self, count):
        m = build_pack_manifest(
            pack_id="p",
            series_id=series_id_for(2026),
            seats=_seats(count),
            license_descriptor=_descriptor(),
        )
        assert verify_pack_manifest(m)
        assert m["header"]["agent_count"] == count


# ---------------------------------------------------------------------------
# Invariant 6 — license, not investment.
# ---------------------------------------------------------------------------


class TestLicenseNotInvestment:
    @pytest.mark.parametrize(
        "phrase",
        [
            "will increase in value",
            "guaranteed returns",
            "earn yield while you hold",
            "passive income stream",
            "an investment opportunity",
        ],
    )
    def test_promises_refused(self, phrase):
        with pytest.raises(CreationError):
            check_copy_clean("Hold and " + phrase, field="t")

    def test_canon_copy_is_clean(self):
        for line in NFT_LICENSE_TERMS["no_profit_promises"]:
            check_copy_clean(line, field="terms")
        check_copy_clean(
            "A scarce lifetime license: one token, one genesis pack. "
            "Sold as a license, not an investment: the company promises "
            "no profit and no rising value.",
            field="description",
        )

    def test_asset_carries_terms_ref(self):
        asset = create_token_asset(manifest=_manifest(), ledger=_ledger())
        assert asset["metadata"]["license_terms_ref"] == NFT_LICENSE_TERMS["version"]
        assert "transferable" in NFT_LICENSE_TERMS["transfer"].lower()
        assert asset["license"]["version"] == NFT_LICENSE_TERMS["version"]

    def test_unassigned_placeholder_passes_white_label(self):
        assert check_white_label(UNASSIGNED_BUYER) == UNASSIGNED_BUYER
        with pytest.raises(NftEconomicsError):
            check_white_label("   ")
        with pytest.raises(NftEconomicsError):
            check_white_label("Levi Holdings")


# ---------------------------------------------------------------------------
# Art — deterministic, geometry only.
# ---------------------------------------------------------------------------


class TestSigilArt:
    def test_deterministic(self):
        tid = token_id_for("pack-test", "GENESIS-2026")
        a = render_sigil_svg(
            token_id=tid, series_id="GENESIS-2026", card_display="1/1000"
        )
        b = render_sigil_svg(
            token_id=tid, series_id="GENESIS-2026", card_display="1/1000"
        )
        assert a == b

    def test_distinct_tokens_distinct_art(self):
        a = render_sigil_svg(
            token_id=1, series_id="GENESIS-2026", card_display="1/1000"
        )
        b = render_sigil_svg(
            token_id=2, series_id="GENESIS-2026", card_display="1/1000"
        )
        assert a != b

    def test_valid_xml_no_subjects(self):
        tid = token_id_for("pack-test", "GENESIS-2026")
        svg = render_sigil_svg(
            token_id=tid, series_id="GENESIS-2026", card_display="1/1000"
        )
        ET.fromstring(svg)  # raises if not well-formed XML
        lowered = svg.lower()
        words = set(re.findall(r"[a-z0-9]+", lowered))
        for bad in SUBJECT_DENYLIST:
            assert bad not in words

    def test_asset_art_matches_token(self):
        m = _manifest()
        asset = create_token_asset(manifest=m, ledger=_ledger())
        assert asset["art"]["format"] == "svg"
        assert asset["art"]["svg"].startswith("<svg")
        assert asset["metadata"]["token_id_hex"][:18] in asset["art"]["svg"]


# ---------------------------------------------------------------------------
# The first drop — end to end, paper.
# ---------------------------------------------------------------------------


class TestFirstDrop:
    def test_first_drop_builds_and_verifies(self, tmp_path):
        result = build_first_drop(
            tmp_path / "GENESIS-2026",
            bank_note="Chauncey ruling 2026-09-27: start creating the Legion NFTs",
        )
        asset = result["asset"]
        assert verify_token_asset(asset)
        drop = tmp_path / "GENESIS-2026"
        for name in (
            "series-ledger.json",
            "pack-manifest.json",
            "token-metadata.json",
            "art.svg",
            "README.md",
        ):
            assert (drop / name).exists(), name
        ledger_doc = json.loads((drop / "series-ledger.json").read_text())
        assert ledger_doc["banked_n"] == 1000
        assert ledger_doc["decided_by"] == "keeper"
        assert ledger_doc["ledger_valid"] is True
        lg2 = SeriesLedger.from_receipts(ledger_doc["receipts"])
        assert lg2.require_n(2026) == 1000
        md = json.loads((drop / "token-metadata.json").read_text())
        assert md["card_display"] == "1/1000"
        assert md["buyer_business"] == UNASSIGNED_BUYER
        assert md["agent_count"] == 9
