"""Proof for core/levi/custody/exhibit.py laws.

Law 1: integrity is not truth — the exhibit never vouches for the claim.
Law 2: sealing is fail-closed — all sealed bytes are digested at seal time.
Law 3: the handling log is append-only and hash-chained.
Law 4: INTACT means the bytes are exactly what was sealed.
Law 5: every exhibit states what it is NOT (honesty footer).
"""

import pytest

from levi.custody.exhibit import (
    HONESTY_FOOTER,
    INTACT,
    TAMPERED,
    ExhibitError,
    inspect_exhibit,
    log_handling,
    render_exhibit,
    seal_exhibit,
)


def test_seal_and_inspect_intact():
    ex = seal_exhibit(
        "account posts from Germany",
        metadata={"source": "x-account-query", "account_id": "12345"},
        attachments={"screenshot.png": b"\x89PNGfakepng"},
        label="case-001",
    )
    assert inspect_exhibit(ex) == INTACT


def test_empty_claim_fails_closed():
    with pytest.raises(ExhibitError):
        seal_exhibit("   ")


def test_non_string_metadata_fails_closed():
    with pytest.raises(ExhibitError):
        seal_exhibit("a claim", metadata={"n": 42})


def test_non_bytes_attachment_fails_closed():
    with pytest.raises(ExhibitError):
        seal_exhibit("a claim", attachments={"f": "not-bytes"})


def test_tampered_claim_detected():
    ex = seal_exhibit("the original claim")
    from dataclasses import replace

    forged = replace(ex, claim="the altered claim")
    assert inspect_exhibit(forged) == TAMPERED


def test_tampered_attachment_detected():
    ex = seal_exhibit("a claim", attachments={"doc.bin": b"original-bytes"})
    from dataclasses import replace

    forged = replace(ex, attachments=(("doc.bin", b"swapped-bytes"),))
    assert inspect_exhibit(forged) == TAMPERED


def test_handling_log_is_append_only_and_chained():
    ex = seal_exhibit("a claim")
    ex1 = log_handling(ex, "rexx", "sealed into vault")
    ex2 = log_handling(ex1, "chauncey", "reviewed")
    # input exhibits are unchanged — no mutation
    assert len(ex.log) == 0
    assert len(ex1.log) == 1
    assert len(ex2.log) == 2
    assert inspect_exhibit(ex2) == INTACT
    # chain links: each entry commits to the previous digest
    assert ex2.log[0].entry_digest != ex2.log[1].entry_digest


def test_broken_chain_detected():
    ex = seal_exhibit("a claim")
    ex1 = log_handling(ex, "rexx", "sealed")
    from dataclasses import replace

    forged_entry = replace(ex1.log[0], action="stolen")
    forged = replace(ex1, log=(forged_entry,))
    assert inspect_exhibit(forged) == TAMPERED


def test_log_requires_handler_and_action():
    ex = seal_exhibit("a claim")
    with pytest.raises(ExhibitError):
        log_handling(ex, "", "did a thing")
    with pytest.raises(ExhibitError):
        log_handling(ex, "rexx", "  ")


def test_honesty_footer_present_and_law1():
    ex = seal_exhibit("the moon is made of cheese")
    card = render_exhibit(ex)
    assert "INTEGRITY IS NOT TRUTH" in card
    assert HONESTY_FOOTER in card
    # Law 1: a sealed false claim still inspects INTACT — the exhibit
    # vouches for custody, never for truth.
    assert inspect_exhibit(ex) == INTACT


def test_verbatim_claim_preserved():
    claim = "  oddly   spaced CLAIM — quoted exactly!  "
    ex = seal_exhibit(claim)
    assert ex.claim == claim
    assert claim in render_exhibit(ex)
