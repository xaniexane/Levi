"""Source converters: approved corpora -> corpus_manager Docs.

Each converter produces :class:`~levi.brain.train.v2.corpus_manager.Doc`
records with honest ``source`` / ``tags`` / ``meta`` provenance. Every
converter runs the news policy gate (``check_policy``) before returning;
a news-tagged or news-path corpus raises ``PolicyError`` and never reaches
a manifest.

Approved sources:

* ``courses`` — chunked full texts from
  ``core/levi/knowledge/courses/raw/<subject>/*.txt`` (the awesome-courses
  ingestion). Chunks carry a ``[subject · file]`` header so a sequence is
  never context-free.
* ``academy`` — records from ``core/levi/brain/train/corpus_academy.jsonl``.
* ``growth`` — redacted growth learnings via
  ``levi.growth.corpus_export.collect_corpus_records``. The kind
  (fact/preference/procedural/correction) is prefixed to the text.
* ``seed`` — the growth seed curriculum
  (``levi.growth.curriculum.lessons.LESSONS``): founder-level direction
  and distilled operational technique.

Hygiene: :func:`sanitize_text` masks email addresses (course syllabi ship
with instructor/TA addresses; they are noise for training and privacy
debt) and collapses whitespace. Converters never fetch from the network.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Iterable

from levi.brain.train.v2.corpus_manager import (
    Doc,
    check_policy,
    doc_sha256,
    normalize_text,
)

__all__ = [
    "SOURCES",
    "repo_root",
    "sanitize_text",
    "courses_docs",
    "academy_docs",
    "growth_docs",
    "seed_docs",
    "collect",
]

SOURCES = ("courses", "academy", "growth", "seed")

# Tags per source; all pass the news policy gate.
SOURCE_TAGS: dict[str, tuple[str, ...]] = {
    "courses": ("courses", "seed-knowledge"),
    "academy": ("academy",),
    "growth": ("growth",),
    "seed": ("seed-curriculum",),
}

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-][\w.-]*\.[a-zA-Z]{2,}")

#: Chunking defaults for course texts (words).
COURSE_CHUNK_WORDS = 400
COURSE_CHUNK_OVERLAP = 40
MIN_CHUNK_WORDS = 20


def repo_root() -> Path:
    """Locate the LEVI repo root.

    ``core/levi/teach/converters.py`` sits four levels deep
    (teach -> levi -> core -> repo). ``LEVI_REPO`` overrides detection.
    """
    override = os.environ.get("LEVI_REPO", "").strip()
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[3]


def sanitize_text(text: str) -> str:
    """Mask emails, collapse whitespace. Returns "" for non-str input."""
    if not isinstance(text, str):
        return ""
    text = _EMAIL_RE.sub("[email redacted]", text)
    return normalize_text(text)


def _chunk_words(words: list[str], size: int, overlap: int) -> Iterable[list[str]]:
    step = max(1, size - overlap)
    for start in range(0, len(words), step):
        chunk = words[start : start + size]
        if len(chunk) >= MIN_CHUNK_WORDS:
            yield chunk
        if start + size >= len(words):
            break


def _courses_repo_dir(root: Path) -> Path:
    return root / "core" / "levi" / "knowledge" / "courses" / "raw"


def courses_docs(
    root: Path | None = None,
    *,
    chunk_words: int = COURSE_CHUNK_WORDS,
    overlap: int = COURSE_CHUNK_OVERLAP,
    subjects: Iterable[str] | None = None,
) -> list[Doc]:
    """Chunk course full-texts into Docs. Never reads outside the repo."""
    root = root or repo_root()
    raw_dir = _courses_repo_dir(root)
    check_policy(SOURCE_TAGS["courses"], str(raw_dir))
    if not raw_dir.is_dir():
        return []
    wanted = {s.strip() for s in subjects} if subjects else None
    docs: list[Doc] = []
    for subject_dir in sorted(raw_dir.iterdir()):
        if not subject_dir.is_dir():
            continue
        if wanted and subject_dir.name not in wanted:
            continue
        for path in sorted(subject_dir.glob("*.txt")):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            clean = sanitize_text(text)
            words = clean.split()
            for i, chunk in enumerate(_chunk_words(words, chunk_words, overlap)):
                chunk_text = (
                    f"[courses · {subject_dir.name} · {path.stem}] " + " ".join(chunk)
                )
                docs.append(
                    Doc(
                        id=doc_sha256(chunk_text),
                        text=chunk_text,
                        source=f"courses:{subject_dir.name}/{path.name}#c{i}",
                        tags=SOURCE_TAGS["courses"],
                        meta={"subject": subject_dir.name, "file": path.name},
                    )
                )
    return docs


def _academy_corpus_path(root: Path) -> Path:
    return root / "core" / "levi" / "brain" / "train" / "corpus_academy.jsonl"


def academy_docs(root: Path | None = None) -> list[Doc]:
    """Academy lesson records -> Docs."""
    root = root or repo_root()
    path = _academy_corpus_path(root)
    check_policy(SOURCE_TAGS["academy"], str(path))
    if not path.is_file():
        return []
    docs: list[Doc] = []
    for lineno, line in enumerate(
        path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
    ):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        text = sanitize_text(obj.get("text", ""))
        if len(text.split()) < MIN_CHUNK_WORDS:
            continue
        docs.append(
            Doc(
                id=doc_sha256(text),
                text=text,
                source=f"academy:corpus_academy.jsonl:{lineno}",
                tags=SOURCE_TAGS["academy"],
                meta={
                    k: v
                    for k, v in obj.items()
                    if k != "text" and isinstance(v, (str, int, float, bool))
                },
            )
        )
    return docs


def growth_docs(
    *, min_confidence: float = 0.0, store: object | None = None
) -> list[Doc]:
    """Redacted growth learnings -> Docs (kind-prefixed)."""
    from levi.growth.corpus_export import collect_corpus_records

    check_policy(SOURCE_TAGS["growth"])
    records = collect_corpus_records(store, min_confidence=min_confidence)
    docs: list[Doc] = []
    for rec in records:
        text = sanitize_text(rec.get("text", ""))
        if len(text.split()) < 8:
            continue
        prefixed = f"[growth · {rec.get('kind', 'fact')}] {text}"
        docs.append(
            Doc(
                id=doc_sha256(prefixed),
                text=prefixed,
                source=f"growth:{rec.get('memory_id', '')}",
                tags=SOURCE_TAGS["growth"],
                meta={
                    "kind": str(rec.get("kind", "")),
                    "confidence": rec.get("confidence"),
                    "corroborated_count": rec.get("corroborated_count", 0),
                    "status": str(rec.get("status", "")),
                    "cycle_id": str(rec.get("cycle_id", "")),
                },
            )
        )
    return docs


def seed_docs() -> list[Doc]:
    """Growth seed curriculum lessons -> Docs."""
    from levi.growth.curriculum.lessons import LESSONS

    check_policy(SOURCE_TAGS["seed"])
    docs: list[Doc] = []
    for lesson in LESSONS:
        if not isinstance(lesson, dict):
            continue
        text = sanitize_text(lesson.get("text", ""))
        if len(text.split()) < 8:
            continue
        lesson_id = str(lesson.get("id", ""))
        topic = str(lesson.get("topic", ""))
        prefixed = f"[seed · {topic} · {lesson.get('taught_by', '')}] {text}"
        docs.append(
            Doc(
                id=doc_sha256(prefixed),
                text=prefixed,
                source=f"seed:{lesson_id}",
                tags=SOURCE_TAGS["seed"],
                meta={
                    "lesson_id": lesson_id,
                    "topic": topic,
                    "kind": str(lesson.get("kind", "")),
                    "taught_by": str(lesson.get("taught_by", "")),
                },
            )
        )
    return docs


_CONVERTERS = {
    "courses": courses_docs,
    "academy": academy_docs,
    "growth": growth_docs,
    "seed": seed_docs,
}


def collect(
    sources: Iterable[str] = SOURCES,
    *,
    root: Path | None = None,
    min_confidence: float = 0.0,
) -> dict[str, list[Doc]]:
    """Run converters for ``sources``. Unknown names raise ValueError."""
    chosen = list(sources)
    unknown = [s for s in chosen if s not in _CONVERTERS]
    if unknown:
        raise ValueError(f"teach: unknown source(s): {', '.join(unknown)}")
    out: dict[str, list[Doc]] = {}
    for name in chosen:
        if name == "growth":
            out[name] = growth_docs(min_confidence=min_confidence)
        elif name in ("courses", "academy"):
            out[name] = _CONVERTERS[name](root)
        else:
            out[name] = _CONVERTERS[name]()
    return out
