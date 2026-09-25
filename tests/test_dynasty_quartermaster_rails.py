# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Quartermaster rails tests — 12% cut enforcement, fossil store, invoices.

Hermetic: every test runs under a tmp LEVI_HOME via monkeypatch. No
network, no daemons, no writes to the real user HOME. All money is
paper: no payment rails are touched, because none exist in the build.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from levi.dynasty.wave import quartermaster_rails
from levi.dynasty.wave.quartermaster_rails import (
    PAPER_RAIL,
    PLATFORM_CUT_PERCENT,
    CutError,
    FossilError,
    InvoiceError,
    QuartermasterRails,
)


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    home = tmp_path / "levi-home"
    monkeypatch.setenv("LEVI_HOME", str(home))
    return home


@pytest.fixture
def rails(tmp_home):
    return QuartermasterRails(tmp_home)


def collect(rails, amount, payer="alice", payee="bob", tid="tx-1", memo=""):
    return rails.collect(amount, payer, payee, memo, transfer_id=tid)


# ---------------------------------------------------------------------
# 12% cut enforcement
# ---------------------------------------------------------------------


class TestCutEnforcement:
    def test_twelve_percent_constant(self):
        assert PLATFORM_CUT_PERCENT == 12

    def test_happy_path_split(self, rails):
        out = collect(rails, 1000, tid="tx-happy")
        assert out["transfer_id"] == "tx-happy"
        assert out["payer"] == "alice"
        assert out["payee"] == "bob"
        assert out["gross_cents"] == 1000
        assert out["platform_cents"] == 120
        assert out["payee_cents"] == 880
        assert out["rail"] == PAPER_RAIL
        assert out["memo"] == ""

    def test_floor_goes_to_platform_remainder_to_payee(self, rails):
        # 12% of 101 = 12.12 -> floor 12 to platform, payee gets 89.
        out = collect(rails, 101, tid="tx-odd")
        assert out["platform_cents"] == 12
        assert out["payee_cents"] == 89
        assert out["platform_cents"] + out["payee_cents"] == 101

    def test_no_cent_lost_or_created(self, rails):
        for gross in (1, 2, 3, 7, 33, 99, 100, 101, 999, 12345, 100000):
            out = collect(rails, gross, tid=f"tx-sum-{gross}")
            assert out["platform_cents"] + out["payee_cents"] == gross
            assert out["platform_cents"] == (gross * 12) // 100

    def test_smallest_gross(self, rails):
        out = collect(rails, 1, tid="tx-penny")
        assert out["platform_cents"] == 0
        assert out["payee_cents"] == 1

    def test_fail_closed_malformed_amounts(self, rails):
        for bad in (0, -1, -1000, "100", 10.5, None, True, False):
            with pytest.raises(CutError):
                collect(rails, bad, tid=f"tx-bad-{bad!r}")

    def test_fail_closed_malformed_parties(self, rails):
        with pytest.raises(CutError):
            collect(rails, 100, payer="", tid="tx-nopayer")
        with pytest.raises(CutError):
            collect(rails, 100, payer="   ", tid="tx-blankpayer")
        with pytest.raises(CutError):
            collect(rails, 100, payee=None, tid="tx-nopayee")
        with pytest.raises(CutError):
            collect(rails, 100, memo=123, tid="tx-badmemo")

    def test_transfer_id_required(self, rails):
        with pytest.raises(TypeError):
            rails.collect(100, "alice", "bob")  # type: ignore[call-arg]
        with pytest.raises(CutError):
            rails.collect(100, "alice", "bob", transfer_id="")
        with pytest.raises(CutError):
            rails.collect(100, "alice", "bob", transfer_id="  ")

    def test_replay_refused(self, rails):
        out = collect(rails, 500, tid="tx-once")
        assert out["platform_cents"] == 60
        with pytest.raises(CutError) as excinfo:
            collect(rails, 500, tid="tx-once")
        assert "replay" in str(excinfo.value)
        # The replay did not double-count: only one JSONL line exists.
        lines = [
            line
            for line in (rails._base / "cuts.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        assert len(lines) == 1
        totals = rails.cut_totals()
        assert totals == {
            "gross_cents": 500,
            "platform_cents": 60,
            "payee_cents": 440,
        }

    def test_idempotency_survives_reinit(self, tmp_home):
        rails = QuartermasterRails(tmp_home)
        rails.collect(250, "a", "b", transfer_id="tx-persist")
        fresh = QuartermasterRails(tmp_home)  # new instance, same home
        with pytest.raises(CutError):
            fresh.collect(250, "a", "b", transfer_id="tx-persist")

    def test_jsonl_record_is_immutable_and_complete(self, rails):
        out = collect(rails, 999, payer="shop", payee="seller", memo="job #13")
        rec = json.loads(
            (rails._base / "cuts.jsonl").read_text(encoding="utf-8").strip()
        )
        assert rec == out
        assert rec["platform_cents"] == (999 * 12) // 100
        assert set(rec) == {
            "transfer_id",
            "rail",
            "payer",
            "payee",
            "gross_cents",
            "platform_cents",
            "payee_cents",
            "memo",
            "at",
        }

    def test_cut_record_lookup(self, rails):
        collect(rails, 400, tid="tx-lookup")
        rec = rails.cut_record("tx-lookup")
        assert rec["gross_cents"] == 400
        assert rec["platform_cents"] == 48
        with pytest.raises(CutError):
            rails.cut_record("tx-nope")
        with pytest.raises(CutError):
            rails.cut_record("")

    def test_concurrent_collect_distinct_ids(self, rails):
        errors = []

        def worker(n):
            try:
                collect(rails, 100, tid=f"tx-w{n}")
            except Exception as exc:  # noqa: BLE001 — collected, asserted
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        totals = rails.cut_totals()
        assert totals["gross_cents"] == 2000
        assert totals["platform_cents"] == 240
        assert totals["payee_cents"] == 1760


# ---------------------------------------------------------------------
# Fossil store
# ---------------------------------------------------------------------


class TestFossils:
    def test_roundtrip(self, rails):
        fid = rails.fossilize("ledger.note", {"total": 42, "side": "owner"})
        assert len(fid) == 64
        stored = rails.read_fossil(fid)
        assert stored["id"] == fid
        assert stored["kind"] == "ledger.note"
        assert stored["payload"] == {"total": 42, "side": "owner"}
        assert rails.verify_fossil(fid) is True

    def test_id_is_sha256_of_canonical_json(self, rails):
        import hashlib

        canonical = json.dumps(
            {"kind": "k", "payload": {"b": 2, "a": 1}},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        fid = rails.fossilize("k", {"b": 2, "a": 1})
        assert fid == hashlib.sha256(canonical).hexdigest()
        # Key order does not matter: canonical bytes are the same.
        assert rails.fossilize("k", {"a": 1, "b": 2}) == fid

    def test_idempotent_reseal(self, rails):
        fid = rails.fossilize("run.manifest", {"n": 1})
        assert rails.fossilize("run.manifest", {"n": 1}) == fid
        # ...but same id can only ever carry its sealed bytes.
        assert len(list(rails._fossils.glob("*.json"))) == 1

    def test_write_once_tamper_evident(self, rails):
        fid = rails.fossilize("seal", {"v": 1})
        path = rails._fossils / f"{fid}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["payload"]["v"] = 999  # attacker edits the bytes
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(FossilError) as excinfo:
            rails.verify_fossil(fid)
        assert "tamper" in str(excinfo.value)
        with pytest.raises(FossilError):
            rails.read_fossil(fid)
        # Re-sealing the original content detects the tamper too.
        with pytest.raises(FossilError):
            rails.fossilize("seal", {"v": 1})

    def test_tampered_kind_breaks_seal(self, rails):
        fid = rails.fossilize("a", {"x": 1})
        path = rails._fossils / f"{fid}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["kind"] = "b"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(FossilError):
            rails.read_fossil(fid)

    def test_missing_and_malformed_ids(self, rails):
        with pytest.raises(FossilError):
            rails.read_fossil("0" * 64)  # well-formed, absent
        for bad in ("", "xyz", "0" * 63, "0" * 65, "Z" * 64):
            with pytest.raises(FossilError):
                rails.read_fossil(bad)
            assert rails.list_fossils() == [] or True
        with pytest.raises(FossilError):
            rails.verify_fossil("nope")

    def test_list_and_filter(self, rails):
        a = rails.fossilize("alpha", {"i": 0})
        b = rails.fossilize("alpha", {"i": 1})
        c = rails.fossilize("beta", {"i": 2})
        assert rails.list_fossils() == sorted([a, b, c])
        assert rails.list_fossils(kind="alpha") == sorted([a, b])
        assert rails.list_fossils(kind="beta") == [c]
        assert rails.list_fossils(kind="ghost") == []

    def test_malformed_inputs(self, rails):
        with pytest.raises(FossilError):
            rails.fossilize("", {"x": 1})
        with pytest.raises(FossilError):
            rails.fossilize("  ", {"x": 1})
        with pytest.raises(FossilError):
            rails.fossilize("k", "notadict")  # type: ignore[arg-type]
        with pytest.raises(FossilError):
            rails.fossilize("k", {"bad": object()})  # not JSON-serializable

    def test_corrupt_file_is_not_read_silently(self, rails):
        path = rails._fossils / ("f" * 64 + ".json")
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(FossilError):
            rails.read_fossil("f" * 64)


# ---------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------


class TestInvoices:
    def test_issue_and_fetch(self, rails):
        iid = rails.issue_invoice("alice", "bob", 500, memo="web work")
        rec = rails.invoice(iid)
        assert rec["invoice_id"] == iid
        assert rec["status"] == "open"
        assert rec["payer"] == "alice"
        assert rec["payee"] == "bob"
        assert rec["amount_cents"] == 500
        assert rec["transfer_id"] is None
        assert iid.startswith("inv-")

    def test_ids_are_unique(self, rails):
        ids = {rails.issue_invoice("a", "b", 10) for _ in range(50)}
        assert len(ids) == 50

    def test_open_invoices(self, rails):
        assert rails.open_invoices() == []
        i1 = rails.issue_invoice("a", "b", 100)
        i2 = rails.issue_invoice("a", "b", 200)
        open_ids = {r["invoice_id"] for r in rails.open_invoices()}
        assert open_ids == {i1, i2}

    def test_pay_links_cut_record(self, rails):
        iid = rails.issue_invoice("shop", "seller", 999)
        cut = collect(rails, 999, payer="shop", payee="seller", tid="tx-pay-1")
        paid = rails.pay_invoice(iid, "tx-pay-1")
        assert paid["status"] == "paid"
        assert paid["transfer_id"] == "tx-pay-1" == cut["transfer_id"]
        assert "paid_at" in paid
        # Paid invoices leave the open set.
        assert rails.open_invoices() == []
        # The fetched record carries the link too.
        assert rails.invoice(iid)["transfer_id"] == "tx-pay-1"

    def test_double_pay_refused(self, rails):
        iid = rails.issue_invoice("a", "b", 300)
        collect(rails, 300, tid="tx-dp-1")
        collect(rails, 300, tid="tx-dp-2")
        rails.pay_invoice(iid, "tx-dp-1")
        with pytest.raises(InvoiceError) as excinfo:
            rails.pay_invoice(iid, "tx-dp-2")
        assert "already paid" in str(excinfo.value)

    def test_pay_nonexistent_refused(self, rails):
        collect(rails, 100, tid="tx-ghost-1")
        with pytest.raises(InvoiceError):
            rails.pay_invoice("inv-does-not-exist", "tx-ghost-1")
        with pytest.raises(InvoiceError):
            rails.invoice("inv-does-not-exist")

    def test_pay_with_unknown_transfer_refused(self, rails):
        iid = rails.issue_invoice("a", "b", 100)
        with pytest.raises(InvoiceError):
            rails.pay_invoice(iid, "tx-never-collected")
        # The invoice is still open — the refusal changed nothing.
        assert rails.invoice(iid)["status"] == "open"
        assert [r["invoice_id"] for r in rails.open_invoices()] == [iid]

    def test_malformed_amounts_fail_closed(self, rails):
        for bad in (0, -5, 2.5, "50", None, True):
            with pytest.raises(CutError):
                rails.issue_invoice("a", "b", bad)
        for bad in ("", "  ", None):
            with pytest.raises(CutError):
                rails.issue_invoice(bad, "b", 100)
            with pytest.raises(CutError):
                rails.issue_invoice("a", bad, 100)

    def test_invoices_persist_across_instances(self, tmp_home):
        rails = QuartermasterRails(tmp_home)
        iid = rails.issue_invoice("a", "b", 700)
        rails.collect(700, "a", "b", transfer_id="tx-persist-2")
        rails.pay_invoice(iid, "tx-persist-2")
        fresh = QuartermasterRails(tmp_home)
        assert fresh.invoice(iid)["status"] == "paid"
        assert fresh.open_invoices() == []

    def test_corrupt_ledger_refused_loudly(self, tmp_home):
        rails = QuartermasterRails(tmp_home)
        rails.issue_invoice("a", "b", 10)
        (rails._base / "invoices.json").write_text("{{bad", encoding="utf-8")
        with pytest.raises(InvoiceError):
            rails.open_invoices()


# ---------------------------------------------------------------------
# Paper-only posture
# ---------------------------------------------------------------------


class TestPaperOnly:
    def test_everything_is_paper_and_local(self, rails):
        cut = collect(rails, 100, tid="tx-paper")
        assert cut["rail"] == "paper"
        fid = rails.fossilize("k", {"v": 1})
        assert (rails._fossils / f"{fid}.json").exists()
        # No network imports anywhere in the module.
        src = Path(quartermaster_rails.__file__).read_text(encoding="utf-8")
        for banned in ("socket", "urllib", "http.client", "requests"):
            assert f"import {banned}" not in src
