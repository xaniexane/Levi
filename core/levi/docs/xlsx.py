"""LEVI-native ``.xlsx`` read/create — stdlib only (``zipfile`` + ``xml.etree``).

An ``.xlsx`` file is a zip archive of XML parts (OOXML SpreadsheetML).
This module builds a minimal valid workbook (one sheet, shared-string
table) and reads it back: headers (first row) + data rows.

Honest limits
-------------
* Reading: cell values only — strings via the shared-string table,
  numbers as numbers, sparse cells reconstructed from cell references.
  No formulas (values are read as stored), no formatting, no merged
  cells, no charts, no multiple-sheet fidelity beyond reading the first
  sheet (helpers read any single sheet by index).
* Writing: single sheet, header row + data rows, strings deduplicated in
  the shared-string table, ints/floats stored as numbers.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Sequence, Union
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

S_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
DOC_REL = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
)
WS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"

PathLike = Union[str, Path]


def _s(tag: str) -> str:
    return f"{{{S_NS}}}{tag}"


def _col_letter(index: int) -> str:
    """0-based column index → Excel column letters (0→A, 27→AB)."""
    letters = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _col_index(ref: str) -> int:
    """Cell reference (``B12``) → 0-based column index."""
    letters = "".join(ch for ch in ref if ch.isalpha()).upper()
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch) - 64)
    return index - 1


@dataclass
class XlsxSheet:
    """One worksheet: name, headers (first row), and data rows."""

    name: str
    headers: List[object] = field(default_factory=list)
    rows: List[List[object]] = field(default_factory=list)

    def text(self) -> str:
        """All values as tab-separated text."""
        lines = []
        if self.headers:
            lines.append("\t".join(str(h) for h in self.headers))
        for row in self.rows:
            lines.append("\t".join("" if v is None else str(v) for v in row))
        return "\n".join(lines)


def _cell_xml(ref: str, value: object, strings: List[str], string_idx: dict) -> str:
    if value is None:
        return f'<c r="{ref}"/>'
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"><v>{"1" if value else "0"}</v></c>'
    if isinstance(value, (int, float)):
        return f'<c r="{ref}"><v>{value}</v></c>'
    text = str(value)
    idx = string_idx.get(text)
    if idx is None:
        idx = len(strings)
        strings.append(text)
        string_idx[text] = idx
    return f'<c r="{ref}" t="s"><v>{idx}</v></c>'


def _sheet_xml(
    headers: Sequence[object],
    rows: Sequence[Sequence[object]],
    strings: List[str],
    string_idx: dict,
) -> str:
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    out.append(f'<worksheet xmlns="{S_NS}"><sheetData>')
    row_num = 0
    all_rows: List[Sequence[object]] = []
    if headers:
        all_rows.append(headers)
    all_rows.extend(rows)
    for values in all_rows:
        row_num += 1
        out.append(f'<row r="{row_num}">')
        for col, value in enumerate(values):
            out.append(
                _cell_xml(f"{_col_letter(col)}{row_num}", value, strings, string_idx)
            )
        out.append("</row>")
    out.append("</sheetData></worksheet>")
    return "".join(out)


_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<Types xmlns="{CT_NS}">'
    '<Default Extension="rels" '
    'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.'
    'spreadsheetml.sheet.main+xml"/>'
    '<Override PartName="/xl/worksheets/sheet1.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.'
    'spreadsheetml.worksheet+xml"/>'
    '<Override PartName="/xl/sharedStrings.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.'
    'spreadsheetml.sharedStrings+xml"/>'
    "</Types>"
)

_ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<Relationships xmlns="{RELS_NS}">'
    f'<Relationship Id="rId1" Type="{DOC_REL}" Target="xl/workbook.xml"/>'
    "</Relationships>"
)


def _workbook_xml(sheet_name: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<workbook xmlns="{S_NS}" xmlns:r="{RELS_NS}">'
        "<sheets>"
        f'<sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/>'
        "</sheets>"
        "</workbook>"
    )


_WB_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<Relationships xmlns="{RELS_NS}">'
    f'<Relationship Id="rId1" Type="{WS_REL}" Target="worksheets/sheet1.xml"/>'
    "</Relationships>"
)


def write_xlsx(
    path: PathLike,
    headers: Sequence[object] = (),
    rows: Sequence[Sequence[object]] = (),
    sheet_name: str = "Sheet1",
) -> Path:
    """Create a minimal valid ``.xlsx`` file with one sheet.

    ``headers`` is the first row; ``rows`` are data rows. Values may be
    ``None``/``bool``/``int``/``float``/``str``. Returns the written path.
    """
    out = Path(path)
    strings: List[str] = []
    string_idx: dict = {}
    sheet_xml = _sheet_xml(headers, rows, strings, string_idx)
    si_parts = []
    for text in strings:
        si_parts.append(f'<si><t xml:space="preserve">{escape(text)}</t></si>')
    shared = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<sst xmlns="{S_NS}" count="{len(strings)}" uniqueCount="{len(strings)}">'
        f"{''.join(si_parts)}</sst>"
    )
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _ROOT_RELS)
        zf.writestr("xl/workbook.xml", _workbook_xml(sheet_name))
        zf.writestr("xl/_rels/workbook.xml.rels", _WB_RELS)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        zf.writestr("xl/sharedStrings.xml", shared)
    return out


def _parse_number(raw: str) -> object:
    try:
        if "." in raw or "e" in raw.lower():
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def read_xlsx_sheet(path: PathLike, sheet_index: int = 0) -> XlsxSheet:
    """Read one worksheet (default: the first) from an ``.xlsx`` file.

    Returns :class:`XlsxSheet` with headers (first row) and data rows.
    Raises :class:`ValueError` when the file is not a readable ``.xlsx``.
    """
    src = Path(path)
    try:
        zf = zipfile.ZipFile(src, "r")
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{src} is not a zip-based .xlsx file: {exc}") from exc
    with zf:
        try:
            wb_raw = zf.read("xl/workbook.xml")
        except KeyError as exc:
            raise ValueError(
                f"{src} is not an .xlsx file (no xl/workbook.xml)"
            ) from exc
        # Resolve the sheet part name from the workbook's sheet order.
        try:
            wb_root = ET.fromstring(wb_raw)
        except ET.ParseError as exc:
            raise ValueError(f"{src}: xl/workbook.xml is not valid XML") from exc
        sheets = wb_root.findall(f"{_s('sheets')}/{_s('sheet')}")
        names = [s.get("name") or f"Sheet{i + 1}" for i, s in enumerate(sheets)]
        if not names:
            names = ["Sheet1"]
        if sheet_index < 0 or sheet_index >= len(names):
            raise ValueError(
                f"{src}: sheet index {sheet_index} out of range ({len(names)} sheets)"
            )
        part = f"xl/worksheets/sheet{sheet_index + 1}.xml"
        try:
            sheet_raw = zf.read(part)
        except KeyError as exc:
            raise ValueError(f"{src}: missing worksheet part {part}") from exc
        try:
            shared_raw = zf.read("xl/sharedStrings.xml")
        except KeyError:
            shared_raw = None

    shared: List[str] = []
    if shared_raw is not None:
        try:
            sst = ET.fromstring(shared_raw)
        except ET.ParseError as exc:
            raise ValueError(f"{src}: sharedStrings.xml is not valid XML") from exc
        for si in sst.findall(_s("si")):
            shared.append("".join(t.text or "" for t in si.iter(_s("t"))))

    try:
        sheet_root = ET.fromstring(sheet_raw)
    except ET.ParseError as exc:
        raise ValueError(f"{src}: {part} is not valid XML: {exc}") from exc

    grid: dict = {}
    max_col = 0
    max_row = 0
    for row_el in sheet_root.iter(_s("row")):
        try:
            r = int(row_el.get("r", "0"))
        except ValueError:
            continue
        max_row = max(max_row, r)
        for c in row_el.findall(_s("c")):
            ref = c.get("r") or ""
            col = _col_index(ref)
            max_col = max(max_col, col)
            v_el = c.find(_s("v"))
            raw_v = v_el.text if v_el is not None else None
            if raw_v is None:
                value: object = None
            elif c.get("t") == "s":
                try:
                    value = shared[int(raw_v)]
                except (ValueError, IndexError):
                    value = raw_v
            elif c.get("t") == "b":
                value = raw_v == "1"
            else:
                value = _parse_number(raw_v)
            grid[(r, col)] = value

    rows: List[List[object]] = []
    for r in range(1, max_row + 1):
        rows.append([grid.get((r, c)) for c in range(max_col + 1)])
    headers = rows.pop(0) if rows else []
    return XlsxSheet(name=names[sheet_index], headers=headers, rows=rows)


def read_xlsx(path: PathLike) -> XlsxSheet:
    """Read the first worksheet of an ``.xlsx`` file."""
    return read_xlsx_sheet(path, 0)
