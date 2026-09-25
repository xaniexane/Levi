"""Hermetic tests for the LEVI document skills (``levi.docs``).

All fixtures are synthetic and generated in ``tmp_path`` — no real user
files are ever touched. Round-trips: write -> read for docx/xlsx/pptx.
PDF tests construct a minimal synthetic PDF in-memory (FlateDecode
content stream + Tj/TJ operators), never a real document.
"""

import os
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

from levi.docs import docx, pdf, pptx, xlsx

ROOT = Path(__file__).resolve().parents[1]


# ── synthetic minimal PDF builder (test-only) ─────────────────────


def _make_pdf(content_streams, trailer_extra=b"") -> bytes:
    """Build a minimal one-page PDF whose content streams are FlateDecode.

    ``content_streams`` is a list of raw (uncompressed) content bytes.
    """
    data = b"%PDF-1.4\n"
    offsets = []

    def add(chunk: bytes) -> None:
        offsets.append(len(data))
        data_chunks.append(chunk)

    data_chunks = [data]
    catalog = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    pages = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    page = (
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R "
        + b"/Contents ["
        + b" ".join(f"{4 + i} 0 R".encode() for i in range(len(content_streams)))
        + b"] >>\nendobj\n"
    )
    data_chunks.extend([catalog, pages, page])
    for i, raw in enumerate(content_streams):
        comp = zlib.compress(raw)
        obj = (
            f"{4 + i} 0 obj\n".encode()
            + b"<< /Length "
            + str(len(comp)).encode()
            + b" /Filter /FlateDecode >>\nstream\n"
            + comp
            + b"\nendstream\nendobj\n"
        )
        data_chunks.append(obj)
    body = b"".join(data_chunks)
    xref_at = len(body)
    out = [body, b"xref\n0 %d\n" % (4 + len(content_streams))]
    out.append(b"0000000000 65535 f \n")
    for off in [len(b"%PDF-1.4\n")] + [
        len(b"".join(data_chunks[: k + 1])) for k in range(len(data_chunks) - 1)
    ]:
        out.append(b"%010d 00000 n \n" % off)
    out.append(
        b"trailer\n<< /Size %d /Root 1 0 R %s>>\nstartxref\n%d\n%%%%EOF"
        % (4 + len(content_streams), trailer_extra, xref_at)
    )
    return b"".join(out)


def _write_pdf(tmp_path: Path, name: str, streams, trailer_extra=b"") -> Path:
    path = tmp_path / name
    path.write_bytes(_make_pdf(streams, trailer_extra))
    return path


# ── docx ──────────────────────────────────────────────────────────


def test_docx_roundtrip(tmp_path):
    path = tmp_path / "report.docx"
    docx.write_docx(
        path,
        title="Q3 Summary",
        paragraphs=["Revenue grew 12%.", 'Costs flat; <escaped> & "quoted".'],
        tables=[[["Item", "Qty"], ["Bolts", "400"]]],
    )
    doc = docx.read_docx(path)
    assert doc.paragraphs[0] == "Q3 Summary"
    assert doc.paragraphs[1] == "Revenue grew 12%."
    assert doc.paragraphs[2] == 'Costs flat; <escaped> & "quoted".'
    assert doc.tables == [[["Item", "Qty"], ["Bolts", "400"]]]
    assert "Bolts" in doc.text()


def test_docx_read_invalid(tmp_path):
    bad = tmp_path / "bad.docx"
    bad.write_text("not a zip", encoding="utf-8")
    with pytest.raises(ValueError):
        docx.read_docx(bad)


def test_docx_is_valid_zip_of_xml(tmp_path):
    import zipfile

    path = tmp_path / "x.docx"
    docx.write_docx(path, paragraphs=["hi"])
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
    assert {"[Content_Types].xml", "_rels/.rels", "word/document.xml"} <= names


# ── xlsx ──────────────────────────────────────────────────────────


def test_xlsx_roundtrip(tmp_path):
    path = tmp_path / "data.xlsx"
    xlsx.write_xlsx(
        path,
        headers=["Name", "Qty", "Price", "Active", "Note"],
        rows=[
            ["Bolts", 400, 1.5, True, None],
            ["Nuts", 900, 0.25, False, "restock soon"],
        ],
    )
    sheet = xlsx.read_xlsx(path)
    assert sheet.name == "Sheet1"
    assert sheet.headers == ["Name", "Qty", "Price", "Active", "Note"]
    assert sheet.rows[0] == ["Bolts", 400, 1.5, True, None]
    assert sheet.rows[1] == ["Nuts", 900, 0.25, False, "restock soon"]
    assert "Bolts" in sheet.text()


def test_xlsx_headers_only(tmp_path):
    path = tmp_path / "h.xlsx"
    xlsx.write_xlsx(path, headers=["A", "B"])
    sheet = xlsx.read_xlsx(path)
    assert sheet.headers == ["A", "B"]
    assert sheet.rows == []


def test_xlsx_read_invalid(tmp_path):
    bad = tmp_path / "bad.xlsx"
    bad.write_text("nope", encoding="utf-8")
    with pytest.raises(ValueError):
        xlsx.read_xlsx(bad)


# ── pptx ──────────────────────────────────────────────────────────


def test_pptx_roundtrip(tmp_path):
    path = tmp_path / "deck.pptx"
    pptx.write_pptx(
        path,
        title="Kickoff",
        slides=[
            ("Goals", ["Ship the release", "Learn from users"]),
            ("Risks", ["Scope creep"]),
        ],
    )
    deck = pptx.read_pptx(path)
    assert len(deck.slides) == 2
    assert deck.slides[0].shapes[0] == ["Goals"]
    assert deck.slides[0].shapes[1] == ["Ship the release", "Learn from users"]
    assert deck.slides[1].shapes[0] == ["Risks"]
    assert deck.slides[1].shapes[1] == ["Scope creep"]
    assert "Scope creep" in deck.text()


def test_pptx_title_only_deck(tmp_path):
    path = tmp_path / "title.pptx"
    pptx.write_pptx(path, title="Solo")
    deck = pptx.read_pptx(path)
    assert len(deck.slides) == 1
    assert deck.slides[0].shapes[0] == ["Solo"]


def test_pptx_read_invalid(tmp_path):
    bad = tmp_path / "bad.pptx"
    bad.write_text("nope", encoding="utf-8")
    with pytest.raises(ValueError):
        pptx.read_pptx(bad)


# ── pdf (best-effort) ─────────────────────────────────────────────


def test_pdf_extract_tj_and_tj_array(tmp_path):
    path = _write_pdf(
        tmp_path,
        "a.pdf",
        [
            b"BT /F1 12 Tf 72 720 Td (Hello LEVI) Tj ET",
            b"BT /F1 12 Tf 72 700 Td [(Second) 120 (line)] TJ ET",
        ],
    )
    frags = pdf.extract_fragments(path)
    assert "Hello LEVI" in frags
    assert "Secondline" in frags  # TJ arrays join with no layout fidelity
    assert "Hello LEVI" in pdf.extract_text(path)


def test_pdf_extract_hex_and_escapes(tmp_path):
    path = _write_pdf(
        tmp_path,
        "b.pdf",
        [b"BT <48656c6c6f> Tj (a\\(b\\)) Tj ET"],
    )
    frags = pdf.extract_fragments(path)
    assert "Hello" in frags
    assert "a(b)" in frags


def test_pdf_no_text_yields_empty(tmp_path):
    # A content stream with no text operators: honest empty, never invented.
    path = _write_pdf(tmp_path, "empty.pdf", [b"1 0 0 1 0 0 cm"])
    assert pdf.extract_text(path) == ""


def test_pdf_encrypted_refused(tmp_path):
    path = _write_pdf(
        tmp_path,
        "enc.pdf",
        [b"BT (secret) Tj ET"],
        trailer_extra=b"/Encrypt 9 0 R ",
    )
    with pytest.raises(ValueError, match="encrypted"):
        pdf.extract_fragments(path)


def test_pdf_not_a_pdf(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError, match="not a PDF"):
        pdf.extract_fragments(bad)


# ── skill registration ────────────────────────────────────────────


def test_doc_skills_registered():
    from levi.skill.registry import SkillRegistry, SkillRisk

    reg = SkillRegistry()
    docs = reg.list(category="documents")
    ids = {s.id for s in docs}
    assert {
        "doc_read",
        "docx_create",
        "xlsx_create",
        "pptx_create",
        "pdf_extract",
    } <= ids
    for skill in docs:
        assert skill.risk_level == SkillRisk.LOW
        assert skill.requires_confirmation is False


def test_doc_skill_handlers_roundtrip(tmp_path):
    from levi.skill.registry import SkillRegistry

    reg = SkillRegistry()
    out = tmp_path / "via_skill.docx"
    created = reg.invoke(
        "docx_create",
        {"path": str(out), "title": "Skill Report", "paragraphs": ["first", "second"]},
    )
    assert "created" in created
    read_back = reg.invoke("doc_read", {"path": str(out)})
    assert "Skill Report" in read_back
    assert "first" in read_back


def test_pdf_extract_skill_honest_empty(tmp_path):
    from levi.skill.registry import SkillRegistry

    reg = SkillRegistry()
    path = _write_pdf(tmp_path, "img.pdf", [b"1 0 0 1 0 0 cm"])
    result = reg.invoke("pdf_extract", {"path": str(path)})
    assert "no extractable text" in result


# ── CLI surface ───────────────────────────────────────────────────


def _cli_env(home: str):
    env = dict(os.environ)
    env["HOME"] = home
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "core"), *sys.path])
    return env


def _run(home: str, *argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "levi.cli.main", *argv],
        cwd=ROOT,
        env=_cli_env(home),
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_cli_doc_write_read_docx(tmp_path):
    home = str(tmp_path / "home")
    out = str(tmp_path / "cli.docx")
    w = _run(
        home,
        "doc",
        "write",
        "docx",
        out,
        "--title",
        "CLI Report",
        "--paragraph",
        "alpha",
        "--paragraph",
        "beta",
        "--table",
        "a,b;c,d",
    )
    assert w.returncode == 0, w.stderr
    r = _run(home, "doc", "read", out)
    assert r.returncode == 0, r.stderr
    assert "CLI Report" in r.stdout and "alpha" in r.stdout and "c" in r.stdout


def test_cli_doc_write_read_xlsx_pptx(tmp_path):
    home = str(tmp_path / "home")
    xs = str(tmp_path / "cli.xlsx")
    w = _run(
        home,
        "doc",
        "write",
        "xlsx",
        xs,
        "--header",
        "Name",
        "--header",
        "Qty",
        "--row",
        "Bolts,400",
    )
    assert w.returncode == 0, w.stderr
    r = _run(home, "doc", "read", xs)
    assert r.returncode == 0, r.stderr
    assert "Bolts" in r.stdout and "400" in r.stdout

    pz = str(tmp_path / "cli.pptx")
    w = _run(
        home,
        "doc",
        "write",
        "pptx",
        pz,
        "--title",
        "Kickoff",
        "--slide",
        "Goals|Ship;Learn",
    )
    assert w.returncode == 0, w.stderr
    r = _run(home, "doc", "read", pz)
    assert r.returncode == 0, r.stderr
    assert "Goals" in r.stdout and "Ship" in r.stdout


def test_cli_doc_read_pdf(tmp_path):
    home = str(tmp_path / "home")
    path = _write_pdf(tmp_path, "cli.pdf", [b"BT (CLI PDF text) Tj ET"])
    r = _run(home, "doc", "read", str(path))
    assert r.returncode == 0, r.stderr
    assert "CLI PDF text" in r.stdout
