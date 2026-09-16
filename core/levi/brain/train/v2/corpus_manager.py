"""v2 corpus management: dedupe, versioned manifests, seeded splits.

Standing policy (hard gate, non-negotiable): the NEWS corpus stays OUT of
training weights. Any corpus tagged ``news`` — or living under a known news
corpus path — is rejected by :func:`check_policy` with :class:`PolicyError`
before it can reach a training manifest. See docs/BRAIN_TRAINING.md §6.

Manifest schema (JSON)::

    {"name": "courses", "version": "2026-09-15",
     "tags": ["courses", "seed-knowledge"],
     "files": [{"path": "corpus.jsonl", "sha256": "...",
                "n_docs": 1234, "n_chars": 847990}],
     "n_docs": 1234, "n_chars": 847990,
     "created_at": "2026-09-15T21:00:00Z",
     "policy": "news-excluded"}

Corpus files are JSONL with one ``{"text": ...}`` object per line; extra
keys (``kind``, ``register``, ``tags``, ``source``) are preserved as doc
metadata when present.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


class PolicyError(ValueError):
    """A corpus violates the training-data policy (news exclusion)."""


class CorpusError(RuntimeError):
    """A corpus file is missing or unreadable."""


# ---------------------------------------------------------------------------
# Policy: news stays out of the weights. Never weaken this without the user.


FORBIDDEN_TRAIN_TAGS = frozenset({"news"})
# Path fragments that mark a corpus as news-derived, even if untagged.
FORBIDDEN_PATH_HINTS = ("news", "headlines", "press")


def check_policy(tags: Iterable[str], source_path: str = "") -> None:
    """Raise PolicyError if tags/path mark this corpus as news-derived."""
    lowered = {str(t).strip().lower() for t in tags}
    hit = lowered & FORBIDDEN_TRAIN_TAGS
    if hit:
        raise PolicyError(
            f"corpus tagged {sorted(hit)}: news corpora are excluded from "
            "training weights by standing policy (docs/BRAIN_TRAINING.md §6)"
        )
    path_hit = source_path.strip().lower()
    if any(hint in path_hit for hint in FORBIDDEN_PATH_HINTS):
        raise PolicyError(
            f"corpus path '{source_path}' looks news-derived: news corpora "
            "are excluded from training weights by standing policy"
        )


# ---------------------------------------------------------------------------
# Docs + dedupe


@dataclass
class Doc:
    id: str  # sha256 of normalized text — stable across runs
    text: str
    source: str = ""
    tags: tuple = field(default_factory=tuple)
    meta: dict = field(default_factory=dict)


def normalize_text(text: str) -> str:
    """Collapse whitespace; dedupe is on the normalized form."""
    return " ".join(text.split())


def doc_sha256(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def dedupe(docs: Iterable[Doc]) -> tuple[list[Doc], int]:
    """Drop exact (normalized-text) duplicates, keeping first occurrence.

    Dedup key is always the normalized text hash — never the ``id`` field —
    so two Docs with the same text collapse even if their ids differ.

    Returns ``(unique_docs, n_removed)``.
    """
    seen: set[str] = set()
    unique: list[Doc] = []
    removed = 0
    for doc in docs:
        key = doc_sha256(doc.text)
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        unique.append(doc)
    return unique, removed


def load_jsonl_docs(path: str | Path) -> list[Doc]:
    """Load ``{"text": ...}`` JSONL into Docs. Skips blank/malformed lines."""
    path = Path(path)
    if not path.is_file():
        raise CorpusError(f"corpus file not found: {path}")
    docs: list[Doc] = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = obj.get("text", "") if isinstance(obj, dict) else ""
            if not isinstance(text, str) or not text.strip():
                continue
            tags = obj.get("tags", []) if isinstance(obj, dict) else []
            tags = tuple(str(t) for t in tags) if isinstance(tags, list) else ()
            meta = (
                {k: v for k, v in obj.items() if k not in ("text", "tags")}
                if isinstance(obj, dict)
                else {}
            )
            docs.append(
                Doc(
                    id=doc_sha256(text),
                    text=text,
                    source=f"{path.name}:{lineno}",
                    tags=tags,
                    meta=meta,
                )
            )
    return docs


# ---------------------------------------------------------------------------
# Versioned manifests


@dataclass
class FileEntry:
    path: str  # relative to the manifest's base dir
    sha256: str
    n_docs: int
    n_chars: int


@dataclass
class CorpusManifest:
    name: str
    version: str
    tags: tuple
    files: list[FileEntry]
    n_docs: int
    n_chars: int
    created_at: str
    policy: str = "news-excluded"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_manifest(
    name: str,
    version: str,
    corpus_files: Iterable[str | Path],
    *,
    tags: Iterable[str] = (),
    base_dir: str | Path = ".",
) -> CorpusManifest:
    """Hash corpus files and record doc/char counts. Enforces news policy."""
    tags = tuple(str(t) for t in tags)
    files = [Path(f) for f in corpus_files]
    for f in files:
        check_policy(tags, str(f))
    base = Path(base_dir)
    entries: list[FileEntry] = []
    total_docs = 0
    total_chars = 0
    for f in files:
        docs = load_jsonl_docs(f)
        n_chars = sum(len(d.text) for d in docs)
        h = hashlib.sha256()
        with open(f, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        try:
            rel = str(f.relative_to(base))
        except ValueError:
            rel = str(f)
        entries.append(
            FileEntry(path=rel, sha256=h.hexdigest(), n_docs=len(docs), n_chars=n_chars)
        )
        total_docs += len(docs)
        total_chars += n_chars
    return CorpusManifest(
        name=name,
        version=version,
        tags=tags,
        files=entries,
        n_docs=total_docs,
        n_chars=total_chars,
        created_at=_utcnow(),
    )


def manifest_to_dict(m: CorpusManifest) -> dict:
    d = asdict(m)
    d["tags"] = list(d["tags"])
    return d


def manifest_from_dict(d: dict) -> CorpusManifest:
    return CorpusManifest(
        name=d["name"],
        version=d["version"],
        tags=tuple(d.get("tags", [])),
        files=[FileEntry(**f) for f in d.get("files", [])],
        n_docs=d["n_docs"],
        n_chars=d["n_chars"],
        created_at=d["created_at"],
        policy=d.get("policy", "news-excluded"),
    )


def save_manifest(manifest: CorpusManifest, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest_to_dict(manifest), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def load_manifest(path: str | Path) -> CorpusManifest:
    path = Path(path)
    if not path.is_file():
        raise CorpusError(f"manifest not found: {path}")
    return manifest_from_dict(json.loads(path.read_text(encoding="utf-8")))


def verify_manifest(manifest: CorpusManifest, base_dir: str | Path = ".") -> list[str]:
    """Re-hash every file; return a list of problems (empty = verified)."""
    base = Path(base_dir)
    problems: list[str] = []
    for entry in manifest.files:
        f = base / entry.path
        if not f.is_file():
            problems.append(f"missing file: {entry.path}")
            continue
        h = hashlib.sha256()
        with open(f, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest() != entry.sha256:
            problems.append(f"hash mismatch (modified?): {entry.path}")
    try:
        check_policy(manifest.tags)
    except PolicyError as exc:
        problems.append(f"policy violation: {exc}")
    return problems


# ---------------------------------------------------------------------------
# Seeded train/val/test splits


def split_docs(
    docs: list[Doc],
    *,
    train: float = 0.9,
    val: float = 0.05,
    test: float = 0.05,
    seed: int = 1337,
) -> dict[str, list[Doc]]:
    """Deterministic split. Fractions must sum to 1. Same seed => same split."""
    total = train + val + test
    if abs(total - 1.0) > 1e-9:
        raise CorpusError(
            f"split fractions must sum to 1.0, got {train}+{val}+{test}={total}"
        )
    for name, frac in (("train", train), ("val", val), ("test", test)):
        if frac < 0:
            raise CorpusError(f"split fraction '{name}' is negative: {frac}")
    rng = random.Random(seed)
    order = list(docs)
    rng.shuffle(order)
    n = len(order)
    n_train = int(n * train)
    n_val = int(n * val)
    return {
        "train": order[:n_train],
        "val": order[n_train : n_train + n_val],
        "test": order[n_train + n_val :],
    }


def write_split_jsonl(docs: list[Doc], path: str | Path) -> Path:
    """Write a doc split as JSONL (text + id + tags + meta preserved)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for d in docs:
            fh.write(
                json.dumps(
                    {"id": d.id, "text": d.text, "tags": list(d.tags), "meta": d.meta},
                    ensure_ascii=False,
                )
                + "\n"
            )
    return path
