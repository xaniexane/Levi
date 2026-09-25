"""Teach planning and preparation.

``plan_teaching`` is the dry run behind ``levi teach plan``: collect,
policy-check, dedupe, order via the v2 curriculum builder, and report
what *would* be taught (corpus stats, curriculum stages, sequence counts,
data mix) without writing anything.

``prepare`` does the same work and writes a v2-trainer-consumable bundle:

    <out>/
      corpora/train.jsonl  val.jsonl  test.jsonl   (seeded splits)
      corpora/train.manifest.json | val | test     (corpus_manager manifests)
      corpora/source_<name>.manifest.json          (per-source, for the `mix:`)
      sequences_train.jsonl | _val | _test         (fixed windows, curriculum
                                                   order, stage-tagged)
      curriculum.json                             (CurriculumManifest)
      train.yaml                                  (v2 TrainConfig, rel paths)
      teach.manifest.json                         (versioned teach manifest)

The prepared teach manifest is also copied into
``~/.levi/teach/manifests/`` so ``levi teach stats`` can report what has
been taught across runs.

Assumptions about SCAFFOLD's modules (v2 harness):

* ``corpus_manager``: ``Doc``, ``check_policy``, ``dedupe``,
  ``write_split_jsonl``, ``build_manifest``, ``save_manifest``,
  ``split_docs``, ``PolicyError``.
* ``curriculum``: ``build_curriculum``, ``save_curriculum``,
  ``describe_stages`` (contiguous stages over the simple->complex order).
* ``config``: YAML ``train.yaml`` validated by ``load_config``; model
  builder ``levi.brain.train.model_v2:build_model`` (tokenizer "" = the
  builder provides its own tokenizer).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from levi.brain.train.v2.corpus_manager import (
    CorpusManifest,
    Doc,
    FileEntry,
    build_manifest,
    check_policy,
    dedupe,
    save_manifest,
    split_docs,
    write_split_jsonl,
)
from levi.brain.train.v2.curriculum import (
    build_curriculum,
    describe_stages,
    save_curriculum,
)
from levi.teach import TEACH_VERSION, registry_dir
from levi.teach.converters import SOURCES, collect
from levi.teach.probes import PROBES
from levi.teach.teachback import coverage as teachback_coverage

__all__ = [
    "TeachError",
    "TeachSummary",
    "plan_teaching",
    "make_sequences",
    "prepare",
    "today_version",
]

#: Tail windows shorter than half max_seq_len are dropped (noise control).
TAIL_KEEP_FRACTION = 0.5


class TeachError(RuntimeError):
    """Teach planning/preparation failed."""


def today_version() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@dataclass
class TeachSummary:
    """Everything ``levi teach plan`` reports."""

    name: str
    version: str
    sources: tuple[str, ...]
    seed: int
    n_stages: int
    max_seq_len: int
    per_source: dict = field(default_factory=dict)  # name -> {n_docs, n_chars}
    n_docs_raw: int = 0
    n_docs_unique: int = 0
    n_dedup_removed: int = 0
    stages: list = field(default_factory=list)  # describe_stages rows
    split_counts: dict = field(default_factory=dict)  # train/val/test -> n docs
    sequence_counts: dict = field(default_factory=dict)  # split -> n sequences
    mix: dict = field(default_factory=dict)  # source -> weight fraction
    teachback: dict = field(default_factory=dict)


def _teachback_for_sources(texts: list[str], sources: tuple[str, ...]) -> dict:
    """Teachback over probes matching the chosen sources.

    When no probe covers a chosen source, the check is skipped (recorded,
    not faked): scoring e.g. cyber probes against a courses-only bundle
    would be noise.
    """
    probes = [p for p in PROBES if p.source in sources]
    if not probes:
        return {"skipped": f"no probes for sources: {', '.join(sources)}"}
    return teachback_coverage(texts, probes)


def _check_teachback_gate(teachback: dict, fail_under: float | None) -> None:
    if fail_under is None or teachback.get("skipped"):
        return
    if not 0.0 <= fail_under <= 1.0:
        raise TeachError(f"teachback_fail_under must be within 0..1, got {fail_under}")
    coverage = teachback.get("coverage", 0.0)
    if coverage < fail_under:
        raise TeachError(
            f"teachback gate: coverage {coverage:.0%} below --teachback-fail-under "
            f"{fail_under:.0%} ({teachback.get('n_covered')}/"
            f"{teachback.get('n_probes')} probes). Data-side only: the prepared "
            "texts are missing expected probe vocabulary."
        )


def _collect_unique(
    sources: Iterable[str],
    *,
    root: Path | None,
    min_confidence: float,
) -> tuple[dict[str, list[Doc]], list[Doc], int]:
    per_source = collect(sources, root=root, min_confidence=min_confidence)
    all_docs = [d for docs in per_source.values() for d in docs]
    if not all_docs:
        raise TeachError(
            "no teaching material collected from sources: "
            + ", ".join(per_source.keys())
        )
    # Belt-and-braces: policy check over the union of source tags too.
    tags = {t for docs in per_source.values() for d in docs for t in d.tags}
    check_policy(tags)
    unique, removed = dedupe(all_docs)
    return per_source, unique, removed


def plan_teaching(
    sources: Iterable[str] = SOURCES,
    *,
    name: str = "teach",
    root: Path | None = None,
    seed: int = 1337,
    n_stages: int = 4,
    max_seq_len: int = 128,
    train_frac: float = 0.9,
    val_frac: float = 0.05,
    test_frac: float = 0.05,
    min_confidence: float = 0.0,
    run_teachback: bool = True,
    teachback_fail_under: float | None = None,
) -> TeachSummary:
    """Dry run: compute everything ``prepare`` would do, write nothing."""
    if n_stages < 1:
        raise TeachError(f"n_stages must be >= 1, got {n_stages}")
    if max_seq_len < 8:
        raise TeachError(f"max_seq_len must be >= 8, got {max_seq_len}")
    chosen = tuple(sources)
    unknown = [s for s in chosen if s not in SOURCES]
    if unknown:
        raise TeachError(f"unknown source(s): {', '.join(unknown)}")
    per_source, unique, removed = _collect_unique(
        chosen, root=root, min_confidence=min_confidence
    )

    curriculum = build_curriculum(
        unique,
        name=f"{name}-curriculum",
        source_manifests=[f"teach:{s}" for s in chosen],
        n_stages=n_stages,
        seed=seed,
    )
    stages = describe_stages(curriculum)

    splits = split_docs(
        unique, train=train_frac, val=val_frac, test=test_frac, seed=seed
    )
    split_counts = {k: len(v) for k, v in splits.items()}

    order_index = {doc_id: i for i, doc_id in enumerate(curriculum.order)}
    seq_counts: dict[str, int] = {}
    for split_name, docs in splits.items():
        ordered = sorted(docs, key=lambda d: order_index.get(d.id, len(order_index)))
        seq_counts[split_name] = _count_sequences(ordered, max_seq_len)

    total = sum(split_counts.values())
    mix = {s: round(len(docs) / max(total, 1), 4) for s, docs in per_source.items()}

    teachback: dict = {}
    if run_teachback:
        teachback = _teachback_for_sources([d.text for d in unique], chosen)
        teachback.pop("probes", None)  # plan stays readable; detail in prepare
    _check_teachback_gate(teachback, teachback_fail_under)

    per_src_stats = {
        s: {
            "n_docs": len(docs),
            "n_chars": sum(len(d.text) for d in docs),
        }
        for s, docs in per_source.items()
    }
    return TeachSummary(
        name=name,
        version=today_version(),
        sources=chosen,
        seed=seed,
        n_stages=n_stages,
        max_seq_len=max_seq_len,
        per_source=per_src_stats,
        n_docs_raw=sum(len(d) for d in per_source.values()),
        n_docs_unique=len(unique),
        n_dedup_removed=removed,
        stages=stages,
        split_counts=split_counts,
        sequence_counts=seq_counts,
        mix=mix,
        teachback=teachback,
    )


def _count_sequences(docs: list[Doc], max_seq_len: int) -> int:
    return sum(len(_windows(d.text, max_seq_len)) for d in docs)


def _windows(text: str, max_seq_len: int) -> list[list[str]]:
    words = text.split()
    out: list[list[str]] = []
    for start in range(0, len(words), max_seq_len):
        win = words[start : start + max_seq_len]
        if not win:
            continue
        # Drop a runt tail (< half window) unless it is the only window.
        if len(win) < max_seq_len * TAIL_KEEP_FRACTION and start > 0:
            continue
        out.append(win)
    return out


def make_sequences(
    docs: list[Doc],
    *,
    order: list[str],
    stage_of: dict[str, int],
    max_seq_len: int,
) -> list[dict]:
    """Fixed word windows in curriculum order, stage-tagged.

    ``order``/``stage_of`` come from the curriculum manifest. Each record
    is ``{"seq_id", "doc_id", "stage", "source", "text"}``.
    """
    by_id = {d.id: d for d in docs}
    ordered = [by_id[i] for i in order if i in by_id]
    # Docs missing from the manifest (shouldn't happen) go last.
    missing = [d for d in docs if d.id not in by_id or d.id not in set(order)]
    seqs: list[dict] = []
    n = 0
    for doc in ordered + missing:
        for win in _windows(doc.text, max_seq_len):
            seqs.append(
                {
                    "seq_id": f"s{n:06d}",
                    "doc_id": doc.id,
                    "stage": stage_of.get(doc.id, 0),
                    "source": doc.source,
                    "tags": list(doc.tags),
                    "text": " ".join(win),
                }
            )
            n += 1
    return seqs


def _write_jsonl(records: list[dict], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


def _render_train_yaml(
    *,
    name: str,
    seed: int,
    out_dir: Path,
    source_weights: dict[str, float],
) -> str:
    """A v2 TrainConfig YAML pointing at the prepared bundle (rel paths)."""
    mix_lines = "".join(
        f"      - {{manifest: corpora/source_{s}.manifest.json, weight: {w}}}\n"
        for s, w in sorted(source_weights.items())
    )
    return f"""# Generated by `levi teach prepare` (teach {TEACH_VERSION}).
# Consumed by the v2 trainer: levi.brain.train.v2.config.load_config.
name: {name}
seed: {seed}
model:
  builder: "levi.brain.train.model_v2:build_model"
  tokenizer: ""
  vocab_size: 256
  n_layer: 4
  n_head: 4
  n_embd: 128
  block_size: 128
  dropout: 0.0
data:
  train_manifest: corpora/train.manifest.json
  val_manifest: corpora/val.manifest.json
  test_manifest: corpora/test.manifest.json
  batch_size: 32
  max_seq_len: 128
  shuffle_seed: {seed}
  mix:
{mix_lines}schedule:
  steps: 2000
  learning_rate: 3.0e-4
  warmup_steps: 100
  lr_min: 3.0e-5
  weight_decay: 0.01
  grad_clip: 1.0
  log_every: 25
eval:
  every_steps: 250
  probes_path: ""
  baseline_checkpoint: ""
  max_val_batches: 50
checkpointing:
  dir: weights/v2
  save_every: 250
  keep_last: 5
"""


def prepare(
    out_dir: str | Path,
    *,
    name: str = "teach",
    sources: Iterable[str] = SOURCES,
    root: Path | None = None,
    seed: int = 1337,
    n_stages: int = 4,
    max_seq_len: int = 128,
    train_frac: float = 0.9,
    val_frac: float = 0.05,
    test_frac: float = 0.05,
    min_confidence: float = 0.0,
    run_teachback: bool = True,
    teachback_fail_under: float | None = None,
    register: bool = True,
) -> Path:
    """Prepare a trainer-consumable bundle in ``out_dir``.

    Returns the path of the written ``teach.manifest.json``. Raises
    ``TeachError`` / ``PolicyError`` on any problem; never half-writes
    (artifacts are staged under ``out_dir/.tmp`` then moved into place).
    """
    out = Path(out_dir).expanduser()
    if not str(out).strip():
        raise TeachError("out_dir must be a non-empty path")
    if out.exists() and not out.is_dir():
        raise TeachError(f"out_dir exists and is not a directory: {out}")
    chosen = tuple(sources)
    if n_stages < 1:
        raise TeachError(f"n_stages must be >= 1, got {n_stages}")
    if max_seq_len < 8:
        raise TeachError(f"max_seq_len must be >= 8, got {max_seq_len}")

    per_source, unique, removed = _collect_unique(
        chosen, root=root, min_confidence=min_confidence
    )
    version = today_version()

    # Curriculum: simple -> complex, contiguous stages.
    curriculum = build_curriculum(
        unique,
        name=f"{name}-curriculum",
        source_manifests=[f"teach:{s}@{version}" for s in chosen],
        n_stages=n_stages,
        seed=seed,
    )

    # Seeded splits.
    splits = split_docs(
        unique, train=train_frac, val=val_frac, test=test_frac, seed=seed
    )

    # Sequences per split, in curriculum order.
    order_index = {doc_id: i for i, doc_id in enumerate(curriculum.order)}
    seqs: dict[str, list[dict]] = {}
    for split_name, docs in splits.items():
        ordered = sorted(docs, key=lambda d: order_index.get(d.id, len(order_index)))
        seqs[split_name] = make_sequences(
            ordered,
            order=curriculum.order,
            stage_of=curriculum.stage_of,
            max_seq_len=max_seq_len,
        )

    teachback: dict = {}
    if run_teachback:
        teachback = _teachback_for_sources([d.text for d in unique], chosen)
    _check_teachback_gate(teachback, teachback_fail_under)

    # Stage into out/.tmp, then promote atomically-ish.
    tmp = out / ".tmp"
    if tmp.exists():
        import shutil

        shutil.rmtree(tmp)
    corpora = tmp / "corpora"
    corpora.mkdir(parents=True)

    manifest_names: dict[str, str] = {}
    for split_name, docs in splits.items():
        jsonl = write_split_jsonl(docs, corpora / f"{split_name}.jsonl")
        # NOTE: entry paths are relative to the manifest's own directory
        # (corpora/), matching how the v2 trainer resolves them via
        # manifest_path.parent — NOT relative to the bundle root.
        m = build_manifest(
            f"{name}-{split_name}",
            version,
            [jsonl],
            tags=("teach", split_name, "news-excluded"),
            base_dir=corpora,
        )
        manifest_names[split_name] = f"corpora/{split_name}.manifest.json"
        save_manifest(m, corpora / f"{split_name}.manifest.json")
        _write_jsonl(seqs[split_name], tmp / f"sequences_{split_name}.jsonl")

    source_weights: dict[str, float] = {}
    total_docs = len(unique)
    for src_name, src_docs_all in per_source.items():
        src_tags = ("teach", f"source-{src_name}", "news-excluded")
        check_policy(src_tags)
        entries = []
        for s in splits:
            f = corpora / f"{s}.jsonl"
            h = hashlib.sha256()
            with open(f, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            in_split = [d for d in splits[s] if d.source.split(":")[0] == src_name]
            # Path relative to the manifest's own directory (corpora/):
            # the v2 trainer resolves entry paths via manifest_path.parent.
            entries.append(
                FileEntry(
                    path=f"{s}.jsonl",
                    sha256=h.hexdigest(),
                    n_docs=len(in_split),
                    n_chars=sum(len(d.text) for d in in_split),
                )
            )
        m = CorpusManifest(
            name=f"{name}-source-{src_name}",
            version=version,
            tags=src_tags,
            files=entries,
            n_docs=sum(e.n_docs for e in entries),
            n_chars=sum(e.n_chars for e in entries),
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            policy="news-excluded",
        )
        save_manifest(m, corpora / f"source_{src_name}.manifest.json")
        source_weights[src_name] = len(src_docs_all) / max(total_docs, 1)

    save_curriculum(curriculum, tmp / "curriculum.json")
    (tmp / "train.yaml").write_text(
        _render_train_yaml(
            name=name, seed=seed, out_dir=tmp, source_weights=source_weights
        ),
        encoding="utf-8",
    )

    teach_manifest = {
        "name": name,
        "version": version,
        "teach_version": TEACH_VERSION,
        "sources": list(chosen),
        "seed": seed,
        "n_stages": n_stages,
        "max_seq_len": max_seq_len,
        "per_source": {
            s: {
                "n_docs": len(docs),
                "n_chars": sum(len(d.text) for d in docs),
            }
            for s, docs in per_source.items()
        },
        "n_docs_raw": sum(len(d) for d in per_source.values()),
        "n_docs_unique": len(unique),
        "n_dedup_removed": removed,
        "stages": describe_stages(curriculum),
        "split_counts": {k: len(v) for k, v in splits.items()},
        "sequence_counts": {k: len(v) for k, v in seqs.items()},
        "mix": {s: round(w, 4) for s, w in source_weights.items()},
        "teachback": {k: v for k, v in teachback.items() if k != "probes"},
        "policy": "news-excluded",
        "artifacts": [
            "corpora/train.jsonl",
            "corpora/val.jsonl",
            "corpora/test.jsonl",
            "corpora/train.manifest.json",
            "corpora/val.manifest.json",
            "corpora/test.manifest.json",
            "sequences_train.jsonl",
            "sequences_val.jsonl",
            "sequences_test.jsonl",
            "curriculum.json",
            "train.yaml",
            "teach.manifest.json",
        ],
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (tmp / "teach.manifest.json").write_text(
        json.dumps(teach_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # Promote: move tmp contents into out (out may exist; merge).
    out.mkdir(parents=True, exist_ok=True)
    for child in tmp.iterdir():
        target = out / child.name
        if target.exists():
            if target.is_dir():
                import shutil

                shutil.rmtree(target)
            else:
                target.unlink()
        child.rename(target)
    tmp.rmdir()

    if register:
        reg = registry_dir()
        reg.mkdir(parents=True, exist_ok=True)
        reg_path = reg / f"{name}@{version}.json"
        reg_path.write_text(
            json.dumps(teach_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return out / "teach.manifest.json"
