"""Docs index tests: every doc shipped by the Builder C sweep exists and
is non-empty, and no docs/*.md file in the repo is an empty stub."""

from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"

NEW_DOCS = [
    "DEMAND.md",
    "MEMORY.md",
    "SIM.md",
    "KNOWLEDGE.md",
    "VAULT.md",
    "INTEGRATIONS.md",
]


def test_new_docs_exist_and_nonempty():
    missing = [n for n in NEW_DOCS if not (DOCS / n).is_file()]
    assert not missing, f"missing docs: {missing}"
    empty = [n for n in NEW_DOCS if (DOCS / n).stat().st_size == 0]
    assert not empty, f"empty docs: {empty}"


def test_new_docs_have_required_sections():
    for name in NEW_DOCS:
        text = (DOCS / name).read_text(encoding="utf-8")
        for section in ("Purpose", "Key APIs", "CLI usage", "Honest limits"):
            assert section in text, f"{name} is missing section {section!r}"


def test_no_empty_doc_stubs():
    empties = [p.name for p in DOCS.glob("*.md") if p.stat().st_size == 0]
    assert not empties, f"empty doc stubs: {empties}"
