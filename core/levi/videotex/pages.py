"""Videotex pages: the 40-column page model and the content tree.

A Page is title + wrapped body lines + numbered choices. Choice targets
are *page ids* (strings) — never callables with side effects. This is the
passive-terminal law, enforced structurally: the navigator can only ever
resolve a target to another page, so browsing can never execute
anything.

Content adapters read the filesystem only (``docs/``, the warehouse
table in ``docs/WAREHOUSES.md``) and degrade honestly when a source is
missing. They never import sibling LEVI packages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import CHOICES_PER_SCREEN, PAGE_WIDTH
from .keys import guide_lines


@dataclass
class Choice:
    number: int  # 1-based within the visible chunk
    label: str
    target: str  # page id — never a callable


@dataclass
class Page:
    id: str
    title: str
    lines: list[str] = field(default_factory=list)
    choices: list[Choice] = field(default_factory=list)  # full list; chunked at render
    chunk: int = 0  # which chunk of choices is visible


def wrap(text: str, width: int = PAGE_WIDTH) -> list[str]:
    """Word-wrap to the Minitel 40-column homage. Never emits > width."""
    out: list[str] = []
    for para in text.split("\n"):
        words = para.split()
        if not words:
            out.append("")
            continue
        line = ""
        for word in words:
            # Hard-split pathological long tokens (URLs, hashes, code).
            while len(word) > width:
                if line:
                    out.append(line)
                    line = ""
                out.append(word[:width])
                word = word[width:]
            if not word:
                continue
            if not line:
                line = word
            elif len(line) + 1 + len(word) <= width:
                line += " " + word
            else:
                out.append(line)
                line = word
        if line:
            out.append(line)
    return out


def render(page: Page, breadcrumb: list[str]) -> str:
    """Render a page to plain text, 40 columns, numbered choices."""
    bar = "=" * PAGE_WIDTH
    parts = [bar, page.title[:PAGE_WIDTH].center(PAGE_WIDTH), bar]
    for line in page.lines:
        parts.extend(wrap(line))
    total = len(page.choices)
    if total:
        pages = max(1, (total + CHOICES_PER_SCREEN - 1) // CHOICES_PER_SCREEN)
        chunk = min(page.chunk, pages - 1)
        start = chunk * CHOICES_PER_SCREEN
        visible = page.choices[start : start + CHOICES_PER_SCREEN]
        parts.append("-" * PAGE_WIDTH)
        for i, choice in enumerate(visible, start=1):
            label = "%d. %s" % (i, choice.label)
            parts.extend(wrap(label))
        if pages > 1:
            parts.append("page %d/%d — 'suite' pour la suite" % (chunk + 1, pages))
    parts.append("-" * PAGE_WIDTH)
    trail = " > ".join(breadcrumb[-3:])
    parts.append(("S:" + trail)[-PAGE_WIDTH:])
    parts.append("choix, *, sommaire, suite, guide")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Content tree — filesystem adapters, honest degradation
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _warehouse_rows(root: Path) -> list[tuple[str, str]]:
    """Parse the warehouse table out of docs/WAREHOUSES.md."""
    rows: list[tuple[str, str]] = []
    try:
        text = (root / "docs" / "WAREHOUSES.md").read_text(encoding="utf-8")
    except OSError:
        return rows
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("| `"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 3 and not cells[0].startswith("`Warehouse"):
            name = cells[0].strip("`")
            rows.append((name, cells[2][:160]))
    return rows


def _doc_files(root: Path) -> list[Path]:
    docs = root / "docs"
    try:
        return sorted(docs.glob("*.md"))
    except OSError:
        return []


def _doc_excerpt(path: Path, max_lines: int = 14) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ["(illisible — fichier inaccessible)"]
    body = [ln for ln in lines if ln.strip() and not ln.startswith("<!--")]
    return body[:max_lines] if body else ["(document vide)"]


def build_tree(root: Path | None = None) -> dict[str, Page]:
    """Build the whole navigable tree. Keys are page ids."""
    root = root or _repo_root()
    pages: dict[str, Page] = {}

    guide = Page(id="guide", title="3615 LEVI — GUIDE", lines=guide_lines())
    pages["guide"] = guide

    # --- warehouses -----------------------------------------------------
    rows = _warehouse_rows(root)
    wh_page = Page(
        id="warehouses",
        title="3615 LEVI — ENTREPOTS",
        lines=[
            "Pas une ceinture a outils : des entrepots.",
            "Chaque entrepot a son inventaire.",
        ]
        if rows
        else ["Inventaire indisponible.", "docs/WAREHOUSES.md introuvable."],
    )
    for i, (name, desc) in enumerate(rows):
        pid = "warehouse-%d" % i
        wh_page.choices.append(Choice(number=0, label=name, target=pid))
        pages[pid] = Page(
            id=pid,
            title=("ENTREPOT: " + name)[:PAGE_WIDTH],
            lines=[desc, "", "(inventaire complet : voir docs/)"],
        )
    pages["warehouses"] = wh_page

    # --- docs ------------------------------------------------------------
    doc_files = _doc_files(root)
    docs_page = Page(
        id="docs",
        title="3615 LEVI — DOCUMENTATION",
        lines=["%d documents. Lecture seule." % len(doc_files)]
        if doc_files
        else ["Aucun document trouve."],
    )
    for i, path in enumerate(doc_files):
        pid = "doc-%d" % i
        docs_page.choices.append(Choice(number=0, label=path.stem, target=pid))
        pages[pid] = Page(
            id=pid,
            title=("DOC: " + path.stem)[:PAGE_WIDTH],
            lines=_doc_excerpt(path),
        )
    pages["docs"] = docs_page

    # --- root ------------------------------------------------------------
    home = Page(
        id="home",
        title="3615 LEVI",
        lines=[
            "Bienvenue sur le service videotex",
            "de LEVI. Terminal passif :",
            "il montre, il n'execute rien.",
            "",
            "Choisissez un service :",
        ],
        choices=[
            Choice(number=0, label="Entrepots (inventaire)", target="warehouses"),
            Choice(number=0, label="Documentation (lecture)", target="docs"),
            Choice(number=0, label="Guide des touches", target="guide"),
        ],
    )
    pages["home"] = home
    return pages
