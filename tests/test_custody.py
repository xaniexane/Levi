"""Tests for levi.custody — the paper chain of custody, revived (proof artifact).

Guards the module laws (see core/levi/custody/__init__.py):
  1. A tally half never discloses the statement to a stranger -- digests only.
  2. A tally closes only when both halves reunite with matching digests.
  3. Slip blocks are append-only; a slip states what it is NOT (honesty footer).
  4. INTACT means the payload bytes are exactly what was sealed; it never
     claims identity beyond the bound signet.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from levi.custody import closure as C
from levi.custody import slip as S
from levi.custody import tally as T

NOW = datetime(2026, 9, 28, 10, 0, 0, tzinfo=timezone.utc)
STMT = "Chauncey will review the veil migration plan before October 3, 2026."


# ---------------------------------------------------------------------------
# tally.py — the split stick
# ---------------------------------------------------------------------------


class TestTally:
    def test_cut_produces_stock_and_foil(self):
        stock, foil = T.cut_tally(
            STMT, "keeper", "omega", tally_id="t1", nonce="n1", now=NOW
        )
        assert stock.role == T.STOCK and foil.role == T.FOIL
        assert stock.tally_id == foil.tally_id == "t1"
        assert stock.party == "keeper" and foil.party == "omega"
        assert stock.statement_digest == foil.statement_digest

    def test_half_never_contains_statement(self):
        # Law 1: a stranger holding one half cannot read the agreement.
        stock, foil = T.cut_tally(
            STMT, "keeper", "omega", tally_id="t1", nonce="n1", now=NOW
        )
        for half in (stock, foil):
            for value in half.to_dict().values():
                assert STMT not in str(value), "statement leaked into a tally half"

    def test_matching_halves_close(self):
        stock, foil = T.cut_tally(
            STMT, "keeper", "omega", tally_id="t1", nonce="n1", now=NOW
        )
        verdict = T.close_tally(stock, foil)
        assert verdict["verdict"] == T.CLOSE_MATCH
        assert "agreement, not truth" in verdict["note"]

    def test_altered_half_breaks_the_fit(self):
        # Law 2: altering one half is detectable on reunion.
        stock, foil = T.cut_tally(
            STMT, "keeper", "omega", tally_id="t1", nonce="n1", now=NOW
        )
        bad = T.TallyHalf(
            tally_id="t1",
            role=T.FOIL,
            party="omega",
            counterparty="keeper",
            statement_digest="0" * 64,
            cut_at=foil.cut_at,
            nonce=foil.nonce,
        )
        verdict = T.close_tally(stock, bad)
        assert verdict["verdict"] == T.CLOSE_MISMATCH

    def test_halves_from_different_sticks_do_not_fit(self):
        stock_a, _ = T.cut_tally(
            STMT, "keeper", "omega", tally_id="ta", nonce="n", now=NOW
        )
        _, foil_b = T.cut_tally(
            STMT, "keeper", "omega", tally_id="tb", nonce="n", now=NOW
        )
        assert T.close_tally(stock_a, foil_b)["verdict"] == T.CLOSE_WRONG_PAIR

    def test_empty_statement_refused(self):
        with pytest.raises(T.TallyError):
            T.cut_tally("  ", "keeper", "omega")

    def test_json_roundtrip_preserves_fit(self):
        stock, foil = T.cut_tally(
            STMT, "keeper", "omega", tally_id="t1", nonce="n1", now=NOW
        )
        s2, f2 = T.halves_from_json(T.halves_to_json(stock, foil))
        assert T.close_tally(s2, f2)["verdict"] == T.CLOSE_MATCH

    def test_bad_format_refused(self):
        with pytest.raises(T.TallyError):
            T.TallyHalf.from_dict({"format": "not-a-tally"})


# ---------------------------------------------------------------------------
# slip.py — the traveling card
# ---------------------------------------------------------------------------


class TestSlip:
    def _slip(self):
        return S.issue_slip(
            "veil-migration-plan", ["omega", "keeper"], slip_id="s1", now=NOW
        )

    def test_sign_two_blocks_chain_intact(self):
        slip = self._slip()
        S.sign_slip(slip, "omega", "OM", "comment", remark="looks honest", now=NOW)
        S.sign_slip(slip, "keeper", "CL", "signature", now=NOW)
        assert len(slip.blocks) == 2
        assert slip.blocks[0]["prev_hash"] == "GENESIS"
        assert slip.blocks[1]["prev_hash"] == slip.blocks[0]["block_hash"]
        verdict = S.verify_slip(slip)
        assert verdict["verdict"] == "INTACT"

    def test_chain_is_hash_linked(self):
        slip = self._slip()
        S.sign_slip(slip, "omega", "OM", "comment", now=NOW)
        assert len(slip.blocks[0]["block_hash"]) == 64

    def test_tampered_block_detected(self):
        # Law 3: blocks are append-only; tampering shows.
        slip = self._slip()
        S.sign_slip(slip, "omega", "OM", "comment", now=NOW)
        slip.blocks[0]["remark"] = "rewritten history"
        verdict = S.verify_slip(slip)
        assert verdict["verdict"] == "TAMPERED"
        assert verdict["at_seq"] == 1

    def test_honesty_footer_present(self):
        slip = self._slip()
        S.sign_slip(slip, "omega", "OM", "comment", now=NOW)
        note = S.verify_slip(slip)["note"]
        assert "NOT a record of approvals" in note

    def test_unknown_action_refused(self):
        slip = self._slip()
        with pytest.raises(S.SlipError):
            S.sign_slip(slip, "omega", "OM", "teleport", now=NOW)

    def test_closed_slip_refuses_signing(self):
        slip = S.close_slip(self._slip())
        with pytest.raises(S.SlipError):
            S.sign_slip(slip, "omega", "OM", "comment", now=NOW)

    def test_issue_requires_recipients(self):
        with pytest.raises(S.SlipError):
            S.issue_slip("item", [])

    def test_of41_actions_present(self):
        for code in (
            "CIRCULATE",
            "FOR_CLEARANCE",
            "SEE_ME",
            "SIGNATURE",
            "NOTE_AND_RETURN",
        ):
            assert code in S.ACTIONS

    def test_json_roundtrip(self):
        slip = self._slip()
        S.sign_slip(slip, "omega", "OM", "comment", now=NOW)
        s2 = S.slip_from_json(S.slip_to_json(slip))
        assert S.verify_slip(s2)["verdict"] == "INTACT"


# ---------------------------------------------------------------------------
# closure.py — the wax dollop
# ---------------------------------------------------------------------------


class TestClosure:
    def test_seal_then_inspect_intact(self):
        payload = b"veil migration plan, revision 3"
        c = C.seal_payload(payload, "chauncey-signet", salt="salt1", now=NOW)
        verdict = C.inspect_closure(c, payload)
        assert verdict["verdict"] == C.INTACT
        assert verdict["signet"] == "chauncey-signet"

    def test_altered_payload_tampered(self):
        # Law 4: any mutation breaks the wax.
        c = C.seal_payload(b"original", "chauncey-signet", salt="salt1", now=NOW)
        verdict = C.inspect_closure(c, b"altered")
        assert verdict["verdict"] == C.TAMPERED

    def test_missing_closure_unsigned(self):
        verdict = C.inspect_closure(None, b"anything")
        assert verdict["verdict"] == C.UNSIGNED

    def test_empty_payload_refused(self):
        with pytest.raises(C.ClosureError):
            C.seal_payload(b"", "signet")

    def test_json_roundtrip(self):
        payload = b"traveling artifact"
        c = C.seal_payload(payload, "signet", salt="s", now=NOW)
        c2 = C.closure_from_json(C.closure_to_json(c))
        assert C.inspect_closure(c2, payload)["verdict"] == C.INTACT
