"""LEVI-native ``.docx`` read/create — stdlib only (``zipfile`` + ``xml.etree``).

A ``.docx`` file is a zip archive of XML parts (OOXML). This module
builds a *minimal valid* ``word/document.xml`` plus the required
``[Content_Types].xml`` and relationship parts, and reads back the same
structure: paragraphs (in document order) and tables (rows × cells).

Honest limits
-------------
* Reading: paragraph text + table cell text only. No styles beyond the
  paragraph style name, no images, no headers/footers, no tracked
  changes, no embedded objects.
* Writing: plain paragraphs, one title (``Title`` style), simple tables.
  Documents open in Word/LibreOffice/Google Docs.

Everything here is written from the OOXML structure itself; no other
product's code or branding is involved.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Union
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
DOC_REL = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
)

PathLike = Union[str, Path]


def _w(tag: str) -> str:
    return f"{{{W_NS}}}{tag}"


@dataclass
class DocxDocument:
    """Text content of a ``.docx`` file."""

    paragraphs: List[str] = field(default_factory=list)
    tables: List[List[List[str]]] = field(default_factory=list)

    def text(self) -> str:
        """All text as one string: paragraphs then tables."""
        parts = list(self.paragraphs)
        for table in self.tables:
            for row in table:
                parts.append(" | ".join(row))
        return "\n".join(parts)


def _paragraph_xml(text: str, style: Optional[str] = None) -> str:
    style_xml = f'<w:pPr><w:pStyle w:val="{escape(style)}"/></w:pPr>' if style else ""
    return (
        f"<w:p>{style_xml}"
        f'<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r>'
        "</w:p>"
    )


def _table_xml(table: Sequence[Sequence[object]]) -> str:
    rows = []
    for row in table:
        cells = "".join(
            f"<w:tc>{_paragraph_xml('' if c is None else str(c))}</w:tc>" for c in row
        )
        rows.append(f"<w:tr>{cells}</w:tr>")
    cols = max((len(r) for r in table), default=0)
    grid = "".join("<w:gridCol/>" for _ in range(cols))
    return (
        "<w:tbl>"
        '<w:tblPr><w:tblW w:w="0" w:type="auto"/></w:tblPr>'
        f"<w:tblGrid>{grid}</w:tblGrid>"
        f"{''.join(rows)}"
        "</w:tbl>"
    )


def _document_xml(
    title: Optional[str],
    paragraphs: Sequence[object],
    tables: Sequence[Sequence[Sequence[object]]],
) -> str:
    body: List[str] = []
    if title:
        body.append(_paragraph_xml(str(title), style="Title"))
    for para in paragraphs:
        body.append(_paragraph_xml("" if para is None else str(para)))
    for table in tables:
        body.append(_table_xml(table))
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<w:document xmlns:w="{W_NS}">'
        f"<w:body>{''.join(body)}</w:body>"
        "</w:document>"
    )


_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<Types xmlns="{CT_NS}">'
    '<Default Extension="rels" '
    'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.'
    'wordprocessingml.document.main+xml"/>'
    "</Types>"
)

_ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<Relationships xmlns="{RELS_NS}">'
    f'<Relationship Id="rId1" Type="{DOC_REL}" Target="word/document.xml"/>'
    "</Relationships>"
)

_DOC_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<Relationships xmlns="{RELS_NS}"></Relationships>'
)


def write_docx(
    path: PathLike,
    title: Optional[str] = None,
    paragraphs: Sequence[object] = (),
    tables: Sequence[Sequence[Sequence[object]]] = (),
) -> Path:
    """Create a minimal valid ``.docx`` file.

    ``paragraphs`` is the body text in order; ``tables`` is a sequence of
    tables, each a sequence of rows, each a row of cell values.
    Returns the written path.
    """
    out = Path(path)
    doc_xml = _document_xml(title, paragraphs, tables)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _ROOT_RELS)
        zf.writestr("word/document.xml", doc_xml)
        zf.writestr("word/_rels/document.xml.rels", _DOC_RELS)
    return out


def _para_text(p_elem: ET.Element) -> str:
    return "".join(t.text or "" for t in p_elem.iter(_w("t")))


def read_docx(path: PathLike) -> DocxDocument:
    """Read paragraphs and tables from a ``.docx`` file.

    Raises :class:`ValueError` when the file is not a readable ``.docx``.
    """
    src = Path(path)
    try:
        with zipfile.ZipFile(src, "r") as zf:
            try:
                raw = zf.read("word/document.xml")
            except KeyError as exc:
                raise ValueError(
                    f"{src} is not a .docx file (no word/document.xml)"
                ) from exc
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{src} is not a zip-based .docx file: {exc}") from exc
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError(f"{src}: word/document.xml is not valid XML: {exc}") from exc

    body = root.find(_w("body"))
    doc = DocxDocument()
    if body is None:
        return doc
    for child in body:
        if child.tag == _w("p"):
            doc.paragraphs.append(_para_text(child))
        elif child.tag == _w("tbl"):
            table: List[List[str]] = []
            for tr in child.findall(_w("tr")):
                row = [
                    " ".join(_para_text(p) for p in tc.findall(_w("p"))).strip()
                    for tc in tr.findall(_w("tc"))
                ]
                table.append(row)
            doc.tables.append(table)
    return doc
