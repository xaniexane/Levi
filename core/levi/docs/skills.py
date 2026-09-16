"""LEVI document skills: registration pack for :mod:`levi.skill.registry`.

``DOC_SKILLS`` is consumed by ``SkillRegistry`` (import + extend), the
same pattern as the other skill packs (cyber, courses, academy, jobs…).
Category is ``"documents"``; every skill is LOW risk with
``requires_confirmation=False`` because they only read files the user
names or write new files the user names — no exfiltration, no network,
no destructive acts.

Skill ids
---------
* ``doc_read`` — read text from ``.docx`` / ``.xlsx`` / ``.pptx`` /
  ``.pdf`` (PDF is best-effort; see :mod:`levi.docs.pdf`).
* ``docx_create`` — create a ``.docx`` from title + paragraphs + tables.
* ``xlsx_create`` — create an ``.xlsx`` from headers + rows.
* ``pptx_create`` — create a ``.pptx`` deck from title + slides.
* ``pdf_extract`` — best-effort text extraction from a PDF.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from levi.docs import docx as _docx
from levi.docs import pdf as _pdf
from levi.docs import pptx as _pptx
from levi.docs import xlsx as _xlsx

_MAX_TEXT_CHARS = 4000


def _as_str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [line for line in value.splitlines() if line.strip()]
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]


def _truncate(text: str) -> str:
    if len(text) > _MAX_TEXT_CHARS:
        return text[:_MAX_TEXT_CHARS] + f"\n…[truncated, {len(text)} chars total]"
    return text


def _require_path(args: Dict[str, Any]) -> Path:
    path = args.get("path") or args.get("file")
    if not path:
        raise ValueError("provide 'path' to the document file")
    return Path(str(path))


def _skill_doc_read(args: Dict[str, Any]) -> str:
    """Read text from any supported document format."""
    try:
        path = _require_path(args)
    except ValueError as exc:
        return str(exc)
    suffix = path.suffix.lower()
    try:
        if suffix == ".docx":
            text = _docx.read_docx(path).text()
        elif suffix == ".xlsx":
            text = _xlsx.read_xlsx(path).text()
        elif suffix == ".pptx":
            text = _pptx.read_pptx(path).text()
        elif suffix == ".pdf":
            text = _pdf.extract_text(path)
        else:
            return (
                f"unsupported format {suffix!r}; supported: .docx, .xlsx, .pptx, .pdf"
            )
    except ValueError as exc:
        return f"document read failed: {exc}"
    if suffix == ".pdf" and not text.strip():
        return (
            f"{path}: no extractable text found "
            "(best-effort extractor; scanned-image PDFs yield nothing)"
        )
    return f"{path} ({suffix}):\n{_truncate(text)}"


def _skill_docx_create(args: Dict[str, Any]) -> str:
    """Create a .docx from title + paragraphs (+ optional tables)."""
    try:
        path = _require_path(args)
    except ValueError as exc:
        return str(exc)
    title = args.get("title")
    paragraphs = _as_str_list(args.get("paragraphs"))
    tables = args.get("tables") or []
    table_rows = [
        [[str(c) for c in row] for row in table]
        for table in tables
        if isinstance(table, (list, tuple))
    ]
    try:
        out = _docx.write_docx(
            path,
            title=str(title) if title else None,
            paragraphs=paragraphs,
            tables=table_rows,
        )
    except (OSError, ValueError) as exc:
        return f"docx create failed: {exc}"
    return f"created {out} ({len(paragraphs)} paragraphs, {len(table_rows)} tables)"


def _skill_xlsx_create(args: Dict[str, Any]) -> str:
    """Create an .xlsx from headers + rows."""
    try:
        path = _require_path(args)
    except ValueError as exc:
        return str(exc)
    headers = _as_str_list(args.get("headers") or args.get("header"))
    rows = args.get("rows") or []
    clean_rows = [
        [str(c) for c in row] for row in rows if isinstance(row, (list, tuple))
    ]
    try:
        out = _xlsx.write_xlsx(path, headers=headers, rows=clean_rows)
    except (OSError, ValueError) as exc:
        return f"xlsx create failed: {exc}"
    return f"created {out} ({len(headers)} columns, {len(clean_rows)} rows)"


def _skill_pptx_create(args: Dict[str, Any]) -> str:
    """Create a .pptx deck from title + slides."""
    try:
        path = _require_path(args)
    except ValueError as exc:
        return str(exc)
    title = args.get("title")
    slides_in = args.get("slides") or []
    slides = []
    for item in slides_in:
        if isinstance(item, dict):
            slides.append(item)
        elif isinstance(item, str):
            slides.append({"title": item, "bullets": []})
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            slides.append({"title": item[0], "bullets": list(item[1])})
    if not slides:
        bullets = _as_str_list(args.get("bullets"))
        if title or bullets:
            slides = [{"title": title, "bullets": bullets}]
    try:
        out = _pptx.write_pptx(path, title=str(title) if title else None, slides=slides)
    except (OSError, ValueError) as exc:
        return f"pptx create failed: {exc}"
    return f"created {out} ({len(slides) or 1} slides)"


def _skill_pdf_extract(args: Dict[str, Any]) -> str:
    """Best-effort text extraction from a PDF (honest limits apply)."""
    try:
        path = _require_path(args)
    except ValueError as exc:
        return str(exc)
    try:
        fragments, chars = _pdf.extract_info(path)
        text = _pdf.extract_text(path)
    except ValueError as exc:
        return f"pdf extract failed: {exc}"
    if not text.strip():
        return (
            f"{path}: no extractable text found — this best-effort "
            "extractor does not OCR scanned images and skips unsupported "
            "encodings (never invents text)"
        )
    return (
        f"{path}: {fragments} text fragments, {chars} chars "
        "(best-effort, no layout fidelity):\n"
        f"{_truncate(text)}"
    )


def _build_doc_skills() -> List[Any]:
    from levi.skill.registry import Skill, SkillRisk

    return [
        Skill(
            id="doc_read",
            name="Document Read",
            description=(
                "Read text from a document file (.docx, .xlsx, .pptx; "
                ".pdf best-effort). Returns paragraphs, tables, sheet "
                "values, or slide text as plain text."
            ),
            category="documents",
            risk_level=SkillRisk.LOW,
            permissions=["documents.read"],
            handler=_skill_doc_read,
            tags=["documents", "read", "docx", "xlsx", "pptx", "pdf"],
            version="1.0.0",
        ),
        Skill(
            id="docx_create",
            name="DOCX Create",
            description=(
                "Create a .docx document from a title, paragraphs, and "
                "optional tables (stdlib-only OOXML writer)."
            ),
            category="documents",
            risk_level=SkillRisk.LOW,
            permissions=["documents.write"],
            handler=_skill_docx_create,
            tags=["documents", "write", "docx"],
            version="1.0.0",
        ),
        Skill(
            id="xlsx_create",
            name="XLSX Create",
            description=(
                "Create an .xlsx spreadsheet from headers and data rows "
                "(stdlib-only OOXML writer)."
            ),
            category="documents",
            risk_level=SkillRisk.LOW,
            permissions=["documents.write"],
            handler=_skill_xlsx_create,
            tags=["documents", "write", "xlsx", "spreadsheet"],
            version="1.0.0",
        ),
        Skill(
            id="pptx_create",
            name="PPTX Create",
            description=(
                "Create a .pptx slide deck from a title and slides "
                "(title + bullets; stdlib-only OOXML writer)."
            ),
            category="documents",
            risk_level=SkillRisk.LOW,
            permissions=["documents.write"],
            handler=_skill_pptx_create,
            tags=["documents", "write", "pptx", "slides"],
            version="1.0.0",
        ),
        Skill(
            id="pdf_extract",
            name="PDF Extract",
            description=(
                "Best-effort text extraction from a PDF (content-stream "
                "Tj/TJ operators, FlateDecode only). No layout fidelity, "
                "no OCR of scanned images, encrypted PDFs refused."
            ),
            category="documents",
            risk_level=SkillRisk.LOW,
            permissions=["documents.read"],
            handler=_skill_pdf_extract,
            tags=["documents", "read", "pdf", "extract"],
            version="1.0.0",
        ),
    ]


# Registration list consumed by SkillRegistry (import + extend).
DOC_SKILLS: List[Any] = _build_doc_skills()
