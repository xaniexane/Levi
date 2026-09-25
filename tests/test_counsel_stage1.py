"""Stage 1 tests: offline document intake -> local vault -> clause retrieval.

All fixtures are synthetic (no real documents, no real parties). Nothing in
this file touches the network; one test proves it by blocking sockets.
"""

import json
import socket
import stat
import zlib

import pytest

from levi.counsel import (
    CounselIndex,
    CounselVault,
    EncryptedPDFError,
    OCRUnavailableError,
    UnsupportedTypeError,
    check,
    handoff_seed,
    propose_intake,
    require_attorney,
    verify_proposal,
)
from levi.counsel.gates import ACTIONS, VERDICTS
from levi.counsel.intake import IntakeError, extract_text
from levi.counsel.notices import (
    NOTICE_STATUS,
    NOT_LEGAL_ADVICE_DRAFT,
    not_assessed_list,
)
from levi.counsel.vault import DIR_MODE, FILE_MODE

CONTRACT_TEXT = """\
SAMPLE SERVICES AGREEMENT (synthetic fixture — not a real contract)

1. PARTIES. This agreement is between Fictional Client Co. and Example
   Services LLC.

2. PAYMENT. Client shall pay $500 per month, due on the first day of each
   month.

3. TERMINATION. Either party may terminate this agreement with thirty (30)
   days written notice to the other party.

4. CONFIDENTIALITY. Both parties agree to keep shared materials
   confidential for two (2) years after termination.
"""


def _make_pdf_bytes(body_text: str, encrypted: bool = False) -> bytes:
    stream = b"BT /F1 12 Tf 72 720 Td (" + body_text.encode("latin-1") + b") Tj ET"
    comp = zlib.compress(stream)
    objs = []
    objs.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objs.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    objs.append(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R >>\nendobj\n"
    )
    objs.append(
        b"4 0 obj\n<< /Length "
        + str(len(comp)).encode()
        + b" /Filter /FlateDecode >>\nstream\n"
        + comp
        + b"\nendstream\nendobj\n"
    )
    trailer = b"trailer\n<< /Root 1 0 R"
    if encrypted:
        trailer += b" /Encrypt 5 0 R"
    trailer += b" >>\n"
    return b"%PDF-1.4\n" + b"".join(objs) + trailer + b"%%EOF"


@pytest.fixture()
def vault(tmp_path):
    return CounselVault(tmp_path / "vault")


@pytest.fixture()
def contract_file(tmp_path):
    p = tmp_path / "sample_agreement.txt"
    p.write_text(CONTRACT_TEXT, encoding="utf-8")
    return p


def _full_pipeline(vault, path):
    proposal = propose_intake(path)
    verification = verify_proposal(proposal)
    doc = vault.store(proposal, verification)
    if verification.verdict == "accept":
        index = CounselIndex(vault.root)
        text = vault.stored_text(doc.doc_id)
        assert text is not None
        index.add(doc.doc_id, doc.source_name, text)
    return doc, verification


# -- intake / extraction -------------------------------------------------


def test_txt_intake_extracts_text(contract_file):
    result = extract_text(contract_file)
    assert result.quality == "text"
    assert "TERMINATION" in result.text
    assert len(result.sha256) == 64
    assert result.warnings == []


def test_markdown_strips_markup(tmp_path):
    p = tmp_path / "notes.md"
    p.write_text("# Title\n\n**Bold** clause with [a link](https://x.example).\n")
    result = extract_text(p)
    assert result.quality == "markdown"
    assert "#" not in result.text
    assert "Bold" in result.text and "a link" in result.text


def test_pdf_best_effort_extraction(tmp_path):
    p = tmp_path / "doc.pdf"
    p.write_bytes(_make_pdf_bytes("Termination. Thirty days written notice."))
    result = extract_text(p)
    assert result.quality == "pdf-best-effort"
    assert "Termination" in result.text
    assert "best-effort" in result.warnings[0]


def test_encrypted_pdf_refused_not_guessed(tmp_path):
    p = tmp_path / "locked.pdf"
    p.write_bytes(_make_pdf_bytes("Secret terms.", encrypted=True))
    with pytest.raises(EncryptedPDFError):
        extract_text(p)


def test_unsupported_type_rejected(tmp_path):
    p = tmp_path / "data.xlsx"
    p.write_bytes(b"PK\x03\x04")
    with pytest.raises(UnsupportedTypeError):
        extract_text(p)


def test_missing_file_rejected(tmp_path):
    with pytest.raises(IntakeError):
        extract_text(tmp_path / "nope.txt")


def test_latin1_fallback_labeled(tmp_path):
    p = tmp_path / "odd.txt"
    p.write_bytes("caf\xe9 terms".encode("latin-1"))  # invalid utf-8
    result = extract_text(p)
    assert result.quality == "text-fallback"
    assert any("latin-1" in w for w in result.warnings)


def test_ocr_unavailable_raises_honestly(tmp_path, monkeypatch):
    import levi.counsel.intake as intake_mod

    monkeypatch.setattr(intake_mod.shutil, "which", lambda _name: None)
    p = tmp_path / "scan.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    with pytest.raises(OCRUnavailableError) as excinfo:
        extract_text(p)
    assert "cloud OCR is never used" in str(excinfo.value)


# -- verifier (paired mind) ----------------------------------------------


def test_verifier_accepts_clean(contract_file):
    v = verify_proposal(propose_intake(contract_file))
    assert v.verdict == "accept"


def test_verifier_rejects_symlink(tmp_path, contract_file):
    link = tmp_path / "link.txt"
    link.symlink_to(contract_file)
    proposal = propose_intake(link)  # reads through the link fine
    v = verify_proposal(proposal)
    assert v.verdict == "reject"
    assert "symlink" in v.reason


def test_verifier_rejects_hash_drift(tmp_path, contract_file):
    proposal = propose_intake(contract_file)
    with open(contract_file, "a", encoding="utf-8") as fh:
        fh.write("\nappended after proposal")
    v = verify_proposal(proposal)
    assert v.verdict == "reject"
    assert "hash drift" in v.reason


def test_verifier_quarantines_empty_extraction(tmp_path, monkeypatch):
    import levi.counsel.intake as intake_mod

    monkeypatch.setattr(intake_mod, "_ocr_available", lambda: False)
    p = tmp_path / "blank.pdf"
    p.write_bytes(_make_pdf_bytes(""))  # valid PDF, no text fragments
    v = verify_proposal(propose_intake(p))
    assert v.verdict == "quarantine"
    assert v.quarantine_causes == ["empty-extraction"]


# -- vault ----------------------------------------------------------------


def test_vault_permissions(vault, contract_file):
    _full_pipeline(vault, contract_file)
    assert vault.assert_permissions() == []
    for d in (vault.root, vault.root / "docs", vault.root / "quarantine"):
        assert stat.S_IMODE(d.stat().st_mode) == DIR_MODE
    for f in vault.root.rglob("*.orig"):
        assert stat.S_IMODE(f.stat().st_mode) == FILE_MODE


def test_quarantined_doc_stored_not_retrievable(vault, tmp_path):
    p = tmp_path / "empty.pdf"
    p.write_bytes(_make_pdf_bytes(""))
    doc, verification = _full_pipeline(vault, p)
    assert verification.verdict == "quarantine"
    assert vault.has(doc.doc_id)
    assert vault.stored_text(doc.doc_id) is None  # not indexed, not readable
    index = CounselIndex(vault.root)
    assert index.doc_count() == 0
    assert index.search("anything", vault) == []


def test_rejected_doc_stores_nothing(vault, contract_file):
    proposal = propose_intake(contract_file)
    with open(contract_file, "a", encoding="utf-8") as fh:
        fh.write("drift")
    verification = verify_proposal(proposal)
    assert verification.verdict == "reject"
    doc = vault.store(proposal, verification)
    assert not vault.has(doc.doc_id)
    # the rejection itself is recorded in the manifest
    assert any(d.verdict == "reject" for d in vault.manifest())


def test_duplicate_intake_is_idempotent(vault, contract_file):
    doc1, _ = _full_pipeline(vault, contract_file)
    doc2, _ = _full_pipeline(vault, contract_file)
    assert doc1.doc_id == doc2.doc_id
    assert vault.has(doc1.doc_id)


# -- retrieval ------------------------------------------------------------


def test_clause_retrieval_by_query(vault, contract_file):
    doc, _ = _full_pipeline(vault, contract_file)
    index = CounselIndex(vault.root)
    hits = index.search("termination thirty days written notice", vault)
    assert len(hits) >= 1
    hit = hits[0]
    assert hit.doc_id == doc.doc_id
    assert hit.source_name == "sample_agreement.txt"
    assert hit.snippet.startswith('"') and hit.snippet.endswith('"')
    assert "terminate" in hit.snippet.lower()
    assert set(hit.matched_terms) <= {
        "termination",
        "thirty",
        "days",
        "written",
        "notice",
    }
    assert hit.notice_status == NOTICE_STATUS


def test_search_no_match_returns_empty(vault, contract_file):
    _full_pipeline(vault, contract_file)
    index = CounselIndex(vault.root)
    assert index.search("zebra arbitration mars", vault) == []


def test_search_empty_query(vault, contract_file):
    _full_pipeline(vault, contract_file)
    index = CounselIndex(vault.root)
    assert index.search("the and of", vault) == []


def test_retrieval_deterministic(vault, contract_file, tmp_path):
    _full_pipeline(vault, contract_file)
    other = tmp_path / "other.txt"
    other.write_text("Termination clauses matter. Notice periods vary widely.")
    _full_pipeline(vault, other)
    index = CounselIndex(vault.root)
    first = [h.doc_id for h in index.search("termination notice", vault)]
    second = [h.doc_id for h in index.search("termination notice", vault)]
    assert first == second and len(first) == 2


# -- gates ----------------------------------------------------------------


def test_gate_registry_complete():
    assert set(VERDICTS) == {"accept", "quarantine", "reject"}
    for action in (
        "intake_document",
        "retrieve",
        "run_ocr",
        "export_handoff_packet",
        "mark_workflow_complete",
    ):
        assert action in ACTIONS


def test_terminal_gate_requires_named_attorney():
    allowed, missing = check("mark_workflow_complete", {})
    assert not allowed and missing == ["named_attorney"]
    allowed, _ = check(
        "mark_workflow_complete", {"named_attorney": "Jane Counsel, Esq."}
    )
    assert allowed


def test_cloud_ocr_permanently_denied():
    allowed, missing = check("enable_cloud_ocr", {"owner_consent": True})
    assert not allowed and missing == ["forbidden"]


def test_external_source_needs_chauncey():
    allowed, missing = check("use_external_source", {"owner_consent": True})
    assert not allowed and missing == ["chauncey_approval"]


def test_unknown_action_fails_closed():
    allowed, missing = check("mint_legal_nft", {"owner_consent": True})
    assert not allowed and missing == ["unregistered-action"]


def test_require_attorney_rejects_blank():
    with pytest.raises(ValueError):
        require_attorney(handoff_seed("x", [], "done"), "  ")


def test_handoff_seed_is_incomplete_without_attorney():
    packet = handoff_seed("abc123", [{"span": "quoted text"}], "intake")
    assert packet["named_attorney"] is None
    assert packet["workflow_complete"] is False
    assert packet["not_assessed"]
    filled = require_attorney(packet, "Jane Counsel, Esq.")
    assert filled["named_attorney"] == "Jane Counsel, Esq."
    assert packet["named_attorney"] is None  # original untouched


# -- notices (draft, gated) -----------------------------------------------


def test_notice_is_labeled_draft():
    assert "DRAFT" in NOTICE_STATUS
    assert "gated on Chauncey" in NOTICE_STATUS
    assert "NOT LEGAL ADVICE" in NOT_LEGAL_ADVICE_DRAFT
    assert "licensed attorney" in NOT_LEGAL_ADVICE_DRAFT


def test_notice_makes_no_advice_claims():
    text = NOT_LEGAL_ADVICE_DRAFT.lower()
    assert "does not advise" in text
    for claim in ("you should", "we recommend", "likely outcome"):
        assert claim not in text
    assert len(not_assessed_list()) >= 5


# -- offline physics -------------------------------------------------------


def test_zero_network_calls_during_full_run(vault, contract_file, monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("network call attempted during offline run")

    monkeypatch.setattr(socket, "socket", _blocked)
    doc, verification = _full_pipeline(vault, contract_file)
    assert verification.verdict == "accept"
    index = CounselIndex(vault.root)
    hits = index.search("payment 500 per month", vault)
    assert hits and hits[0].doc_id == doc.doc_id


def test_manifest_is_jsonl_and_complete(vault, contract_file):
    doc, _ = _full_pipeline(vault, contract_file)
    lines = (vault.root / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["doc_id"] == doc.doc_id
    assert record["verdict"] == "accept"


def test_cli_intake_and_search(tmp_path, contract_file, capsys):
    from levi.counsel.__main__ import main

    vroot = tmp_path / "vault"
    assert main(["--vault", str(vroot), "intake", str(contract_file)]) == 0
    out = capsys.readouterr().out
    assert '"verdict": "accept"' in out
    assert main(["--vault", str(vroot), "search", "termination notice"]) == 0
    out = capsys.readouterr().out
    assert "sample_agreement.txt" in out
    assert main(["--vault", str(vroot), "gates"]) == 0
    assert "mark_workflow_complete" in capsys.readouterr().out
