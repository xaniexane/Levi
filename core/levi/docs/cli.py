"""``levi doc`` CLI: read/create document files (docx, xlsx, pptx; pdf read).

This module owns the command logic; ``levi.cli.main`` registers the
``doc`` subparser and dispatches here via a thin ``cmd_doc`` wrapper.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from levi.docs import docx as _docx
from levi.docs import pdf as _pdf
from levi.docs import pptx as _pptx
from levi.docs import xlsx as _xlsx


def _read_summary(path: Path) -> Dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        doc = _docx.read_docx(path)
        return {
            "format": "docx",
            "paragraphs": len(doc.paragraphs),
            "tables": len(doc.tables),
            "text": doc.text(),
        }
    if suffix == ".xlsx":
        sheet = _xlsx.read_xlsx(path)
        return {
            "format": "xlsx",
            "sheet": sheet.name,
            "headers": sheet.headers,
            "rows": sheet.rows,
        }
    if suffix == ".pptx":
        deck = _pptx.read_pptx(path)
        return {
            "format": "pptx",
            "slides": len(deck.slides),
            "text": deck.text(),
        }
    if suffix == ".pdf":
        fragments, chars = _pdf.extract_info(path)
        return {
            "format": "pdf",
            "fragments": fragments,
            "chars": chars,
            "text": _pdf.extract_text(path),
            "note": "best-effort extraction: no layout fidelity, no OCR",
        }
    raise ValueError(
        f"unsupported format {suffix!r}; supported: .docx, .xlsx, .pptx, .pdf"
    )


def _split_csv(value: str) -> List[str]:
    return [cell.strip() for cell in value.split(",")]


def cmd_doc(args: Any) -> None:
    action = getattr(args, "doc_action", None) or "read"
    as_json = bool(getattr(args, "json", False))

    if action == "read":
        file = getattr(args, "file", None)
        if not file:
            print("usage: levi doc read <file>")
            raise SystemExit(2)
        path = Path(file)
        try:
            summary = _read_summary(path)
        except (ValueError, OSError) as exc:
            print(f"doc read failed: {exc}")
            raise SystemExit(1) from None
        summary["file"] = str(path)
        if as_json:
            print(json.dumps(summary, indent=2, default=str))
            return
        print(f"── {path} ({summary['format']}) ──")
        if summary["format"] == "docx":
            print(f"{summary['paragraphs']} paragraphs, {summary['tables']} tables\n")
            print(summary["text"])
        elif summary["format"] == "xlsx":
            print(f"sheet: {summary['sheet']}")
            print("\t".join(str(h) for h in summary["headers"]))
            for row in summary["rows"]:
                print("\t".join("" if v is None else str(v) for v in row))
        elif summary["format"] == "pptx":
            print(f"{summary['slides']} slides\n")
            print(summary["text"])
        else:
            print(
                f"{summary['fragments']} fragments, {summary['chars']} chars "
                f"({summary['note']})"
            )
            print(summary["text"] or "(no extractable text)")
        return

    if action == "write":
        fmt = getattr(args, "format", None)
        file = getattr(args, "file", None)
        if fmt not in ("docx", "xlsx", "pptx") or not file:
            print("usage: levi doc write <docx|xlsx|pptx> <file> [options]")
            raise SystemExit(2)
        path = Path(file)
        title = getattr(args, "title", None)
        try:
            if fmt == "docx":
                paragraphs = getattr(args, "paragraph", None) or []
                tables = [
                    [_split_csv(r) for r in t.split(";")]
                    for t in (getattr(args, "table", None) or [])
                ]
                _docx.write_docx(
                    path, title=title, paragraphs=paragraphs, tables=tables
                )
            elif fmt == "xlsx":
                headers = getattr(args, "header", None) or []
                rows = [_split_csv(r) for r in (getattr(args, "row", None) or [])]
                _xlsx.write_xlsx(path, headers=headers, rows=rows)
            else:  # pptx
                slides = []
                for spec in getattr(args, "slide", None) or []:
                    s_title, _, rest = spec.partition("|")
                    bullets = [b for b in rest.split(";") if b.strip()]
                    slides.append({"title": s_title.strip(), "bullets": bullets})
                _pptx.write_pptx(path, title=title, slides=slides)
        except (ValueError, OSError) as exc:
            print(f"doc write failed: {exc}")
            raise SystemExit(1) from None
        print(f"created {path} ({fmt})")
        return

    print(f"unknown doc action {action!r}; expected read|write")
    raise SystemExit(2)
