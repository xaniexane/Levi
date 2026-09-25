"""Document intake (the PROPOSER half of the paired mind).

``propose_intake`` reads a document and proposes a candidate for the vault:
extracted text, an honest quality label, a sha256 fingerprint, and warnings.
It never stores anything and never indexes anything. The verifier
(``levi.counsel.verify``) decides the fate of the proposal.

Supported inputs (stdlib only):
* ``.txt`` — plain text, decoded as UTF-8 with a latin-1 fallback (labeled).
* ``.md`` / ``.markdown`` — markdown with light markup stripping.
* ``.pdf`` — best-effort text extraction via ``levi.docs.pdf`` (its honest
  contract applies: encrypted PDFs are REFUSED, not guessed; scanned-image
  PDFs yield no text and say so).
* image files (``.png`` ``.jpg`` ``.jpeg`` ``.tif`` ``.tiff``) — ONLY via a
  local system OCR tool (tesseract) if present. Cloud OCR is never used;
  the gate registry denies it permanently.

Quality labels (honest, machine-readable):
* ``text``            — clean plain-text read.
* ``text-fallback``   — decoded with a fallback encoding; bytes may be off.
* ``markdown``        — markup stripped, prose kept.
* ``pdf-best-effort`` — fragment stream from the PDF structure; layout,
  reading order, and glyph encodings are NOT reconstructed. Encrypted PDFs
  are REFUSED with ``EncryptedPDFError`` — never stored, never guessed.
* ``ocr-local``       — produced by a local OCR tool; error-prone by nature.
* ``ocr-unavailable`` — no text layer and no local OCR tool present.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Union

PathLike = Union[str, Path]

TEXT_SUFFIXES = {".txt"}
MARKDOWN_SUFFIXES = {".md", ".markdown"}
PDF_SUFFIXES = {".pdf"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}

OCR_TOOL = "tesseract"
OCR_TIMEOUT_SECONDS = 120

_PDF_ENCRYPT_RE = re.compile(rb"/Encrypt\b")


class IntakeError(Exception):
    """Base class for intake failures."""


class UnsupportedTypeError(IntakeError):
    """The file type is not in the intake set."""


class EncryptedPDFError(IntakeError):
    """The PDF is encrypted; extraction is refused, not guessed."""


class OCRUnavailableError(IntakeError):
    """No text layer and no local OCR tool present. Cloud OCR is not a
    fallback — it is permanently denied by the gate registry."""


@dataclass
class ExtractionResult:
    text: str
    quality: str
    sha256: str
    size_bytes: int
    warnings: List[str] = field(default_factory=list)
    fragments: int = 0  # extraction fragments (pdf) or line count (text)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_text_bytes(raw: bytes) -> tuple[str, str, List[str]]:
    warnings: List[str] = []
    try:
        return raw.decode("utf-8"), "text", warnings
    except UnicodeDecodeError:
        warnings.append(
            "input was not valid UTF-8; decoded with latin-1 fallback — "
            "some characters may be wrong"
        )
        return raw.decode("latin-1"), "text-fallback", warnings


_MD_STRIP_PATTERNS = [
    (re.compile(r"```.*?```", re.DOTALL), ""),  # fenced code blocks
    (re.compile(r"`([^`]*)`"), r"\1"),  # inline code
    (re.compile(r"^#{1,6}\s+", re.MULTILINE), ""),  # headings
    (re.compile(r"!\[([^\]]*)\]\([^)]*\)"), r"\1"),  # images
    (re.compile(r"\[([^\]]*)\]\([^)]*\)"), r"\1"),  # links keep label
    (re.compile(r"^[>\s]*[-*+]\s+", re.MULTILINE), ""),  # list bullets
    (re.compile(r"\*\*([^*]+)\*\*"), r"\1"),  # bold
    (re.compile(r"__([^_]+)__"), r"\1"),
    (re.compile(r"\*([^*]+)\*"), r"\1"),  # italic
    (re.compile(r"_([^_]+)_"), r"\1"),
]


def _strip_markdown(text: str) -> str:
    for pattern, repl in _MD_STRIP_PATTERNS:
        text = pattern.sub(repl, text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_pdf(path: Path) -> ExtractionResult:
    raw = path.read_bytes()
    if _PDF_ENCRYPT_RE.search(raw):
        raise EncryptedPDFError(
            f"{path.name}: PDF is encrypted — extraction refused; nothing was guessed"
        )
    from levi.docs.pdf import extract_fragments

    fragments = extract_fragments(path)
    text = "\n".join(fragments).strip()
    warnings = [
        "best-effort extraction: layout, reading order, and glyph encodings "
        "are NOT reconstructed; use for search/indexing only"
    ]
    quality = "pdf-best-effort"
    if not text:
        warnings.append(
            "no text fragments found — this PDF likely contains scanned "
            "page images; text extraction is impossible without OCR"
        )
    return ExtractionResult(
        text=text,
        quality=quality,
        sha256=sha256_file(path),
        size_bytes=len(raw),
        warnings=warnings,
        fragments=len(fragments),
    )


def _ocr_available() -> bool:
    return shutil.which(OCR_TOOL) is not None


def _extract_ocr(path: Path) -> ExtractionResult:
    if not _ocr_available():
        raise OCRUnavailableError(
            f"{path.name}: no text layer and no local OCR tool "
            f"({OCR_TOOL}) present; cloud OCR is never used"
        )
    try:
        completed = subprocess.run(
            [OCR_TOOL, str(path), "stdout", "--psm", "6"],
            capture_output=True,
            timeout=OCR_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OCRUnavailableError(f"{path.name}: local OCR failed: {exc}") from exc
    if completed.returncode != 0:
        raise OCRUnavailableError(
            f"{path.name}: local OCR exited {completed.returncode}: "
            f"{completed.stderr.decode('utf-8', 'replace')[:200]}"
        )
    text = completed.stdout.decode("utf-8", "replace").strip()
    return ExtractionResult(
        text=text,
        quality="ocr-local",
        sha256=sha256_file(path),
        size_bytes=path.stat().st_size,
        warnings=[
            f"text produced by local OCR ({OCR_TOOL}); OCR output is "
            "error-prone — verify against the original image"
        ],
    )


def extract_text(path: PathLike) -> ExtractionResult:
    """Extract text from a supported document. Pure function: no storage,
    no network, no side effects beyond reading the file."""
    p = Path(path)
    if not p.is_file():
        raise IntakeError(f"not a file: {p}")
    suffix = p.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        text, quality, warnings = _read_text_bytes(p.read_bytes())
        return ExtractionResult(
            text=text.strip(),
            quality=quality,
            sha256=sha256_file(p),
            size_bytes=p.stat().st_size,
            warnings=warnings,
            fragments=len(text.splitlines()),
        )
    if suffix in MARKDOWN_SUFFIXES:
        text, _quality, warnings = _read_text_bytes(p.read_bytes())
        stripped = _strip_markdown(text)
        warnings.append("markdown markup stripped; prose kept")
        return ExtractionResult(
            text=stripped,
            quality="markdown",
            sha256=sha256_file(p),
            size_bytes=p.stat().st_size,
            warnings=warnings,
            fragments=len(stripped.splitlines()),
        )
    if suffix in PDF_SUFFIXES:
        return _extract_pdf(p)
    if suffix in IMAGE_SUFFIXES:
        return _extract_ocr(p)
    raise UnsupportedTypeError(
        f"{p.name}: unsupported type {suffix!r}; intake accepts "
        f"{sorted(TEXT_SUFFIXES | MARKDOWN_SUFFIXES | PDF_SUFFIXES | IMAGE_SUFFIXES)}"
    )


@dataclass
class IntakeProposal:
    """What the proposer hands to the verifier."""

    source_path: str
    doc_id: str  # sha256 of the source bytes — content-addressed
    extraction: ExtractionResult
    proposed_at: str  # ISO-8601 UTC


def propose_intake(path: PathLike) -> IntakeProposal:
    """Propose a document for the vault. Reads and fingerprints the file;
    stores nothing, indexes nothing, calls nothing over the network."""
    from datetime import datetime, timezone

    p = Path(path)
    extraction = extract_text(p)
    return IntakeProposal(
        source_path=str(p),
        doc_id=extraction.sha256,
        extraction=extraction,
        proposed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
