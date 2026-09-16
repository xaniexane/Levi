"""Bundle verification: is a ``teach prepare`` output intact and consumable?

``check_bundle`` re-validates everything the v2 trainer will touch:

* ``teach.manifest.json`` parses and names real artifacts
* every ``corpora/*.manifest.json`` re-hashes clean
  (:func:`corpus_manager.verify_manifest`)
* ``curriculum.json`` loads with a non-empty, fully-staged order
* ``train.yaml`` validates with ``v2.config.load_config`` and its
  manifests resolve relative to the bundle dir
* every ``sequences_<split>.jsonl`` record carries the required keys and
  references a doc id present in the matching split corpus, with a stage
  inside the curriculum's stage range

Returns a report dict; ``ok`` is False when any problem is found.
Problems are strings a human can act on. Never raises on a malformed
bundle — a broken bundle is a report, not an exception.
"""

from __future__ import annotations

import json
from pathlib import Path

from levi.brain.train.v2.config import ConfigError, load_config
from levi.brain.train.v2.corpus_manager import (
    CorpusError,
    load_manifest,
    verify_manifest,
)
from levi.brain.train.v2.curriculum import load_curriculum

__all__ = ["check_bundle"]

_REQUIRED_SEQ_KEYS = {"seq_id", "doc_id", "stage", "source", "text"}
_SPLITS = ("train", "val", "test")


def _read_json(path: Path, problems: list[str], what: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        problems.append(f"{what}: unreadable ({exc})")
        return None


def check_bundle(bundle_dir: str | Path) -> dict:
    """Verify a prepared bundle. Returns ``{"ok", "problems", "stats"}``."""
    root = Path(bundle_dir).expanduser()
    problems: list[str] = []
    stats: dict = {}

    if not root.is_dir():
        return {
            "ok": False,
            "problems": [f"bundle dir missing: {root}"],
            "stats": stats,
        }

    # Teach manifest.
    tm_path = root / "teach.manifest.json"
    teach_manifest = _read_json(tm_path, problems, "teach.manifest.json")
    if teach_manifest is not None:
        missing = [
            a for a in teach_manifest.get("artifacts", []) if not (root / a).exists()
        ]
        for a in missing:
            problems.append(f"teach.manifest.json lists missing artifact: {a}")
        stats["manifest"] = (
            f"{teach_manifest.get('name', '?')}@{teach_manifest.get('version', '?')}"
        )

    # Split corpora + their manifests (hash-verified).
    split_ids: dict[str, set[str]] = {}
    corpora = root / "corpora"
    for split in _SPLITS:
        jsonl = corpora / f"{split}.jsonl"
        manifest_p = corpora / f"{split}.manifest.json"
        if not jsonl.is_file():
            problems.append(f"missing corpus file: corpora/{split}.jsonl")
            continue
        if not manifest_p.is_file():
            problems.append(f"missing manifest: corpora/{split}.manifest.json")
            continue
        try:
            manifest = load_manifest(manifest_p)
        except (CorpusError, KeyError, ValueError) as exc:
            problems.append(f"corpora/{split}.manifest.json: {exc}")
            continue
        for p in verify_manifest(manifest, base_dir=root):
            problems.append(f"corpora/{split}.manifest.json: {p}")
        ids: set[str] = set()
        try:
            with open(jsonl, encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line:
                        continue
                    obj = _read_json_line(line, lineno, split, problems)
                    if obj is None:
                        continue
                    if not isinstance(obj.get("text"), str):
                        problems.append(
                            f"corpora/{split}.jsonl:{lineno}: record has no text"
                        )
                        continue
                    ids.add(str(obj.get("id", "")))
        except OSError as exc:
            problems.append(f"corpora/{split}.jsonl: unreadable ({exc})")
        split_ids[split] = ids
        stats[f"{split}_docs"] = len(ids)

    # Per-source manifests: must at least load + verify.
    if corpora.is_dir():
        for mp in sorted(corpora.glob("source_*.manifest.json")):
            try:
                m = load_manifest(mp)
            except (CorpusError, KeyError, ValueError) as exc:
                problems.append(f"{mp.name}: {exc}")
                continue
            for p in verify_manifest(m, base_dir=root):
                problems.append(f"{mp.name}: {p}")

    # Curriculum.
    n_stages = 0
    order_ids: set[str] = set()
    curr_path = root / "curriculum.json"
    if curr_path.is_file():
        try:
            curr = load_curriculum(curr_path)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            problems.append(f"curriculum.json: {exc}")
        else:
            order_ids = set(curr.order)
            n_stages = curr.n_stages
            if not curr.order:
                problems.append("curriculum.json: empty order")
            unstaged = [i for i in curr.order if i not in curr.stage_of]
            if unstaged:
                problems.append(
                    f"curriculum.json: {len(unstaged)} ordered docs lack a stage"
                )
            bad_stage = {
                curr.stage_of[i]
                for i in curr.order
                if i in curr.stage_of and not (0 <= curr.stage_of[i] < curr.n_stages)
            }
            if bad_stage:
                problems.append(
                    f"curriculum.json: stage ids out of range: {sorted(bad_stage)}"
                )
            stats["curriculum_stages"] = n_stages
    else:
        problems.append("missing curriculum.json")

    # train.yaml: validates and its manifests resolve.
    yaml_path = root / "train.yaml"
    if yaml_path.is_file():
        try:
            cfg = load_config(yaml_path)
        except ConfigError as exc:
            problems.append(f"train.yaml: {exc}")
        else:
            for label, rel in (
                ("train_manifest", cfg.data.train_manifest),
                ("val_manifest", cfg.data.val_manifest),
            ):
                if not (root / rel).is_file():
                    problems.append(f"train.yaml: {label} missing: {rel}")
            for entry in cfg.data.mix:
                if not (root / entry["manifest"]).is_file():
                    problems.append(
                        f"train.yaml: mix manifest missing: {entry['manifest']}"
                    )
            stats["config"] = cfg.name
    else:
        problems.append("missing train.yaml")

    # Sequences: schema + doc-id + stage-range checks.
    all_seq_doc_ids: set[str] = set()
    for split in _SPLITS:
        sp = root / f"sequences_{split}.jsonl"
        if not sp.is_file():
            problems.append(f"missing sequences_{split}.jsonl")
            continue
        n = 0
        try:
            with open(sp, encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line:
                        continue
                    obj = _read_json_line(line, lineno, f"sequences_{split}", problems)
                    if obj is None:
                        continue
                    missing_keys = _REQUIRED_SEQ_KEYS - set(obj)
                    if missing_keys:
                        problems.append(
                            f"sequences_{split}.jsonl:{lineno}: missing keys "
                            f"{sorted(missing_keys)}"
                        )
                        continue
                    n += 1
                    all_seq_doc_ids.add(str(obj["doc_id"]))
                    if split in split_ids and obj["doc_id"] not in split_ids[split]:
                        problems.append(
                            f"sequences_{split}.jsonl:{lineno}: doc_id "
                            f"{obj['doc_id'][:12]}… not in corpora/{split}.jsonl"
                        )
                    stage = obj.get("stage")
                    if not isinstance(stage, int) or not (
                        0 <= stage < max(n_stages, 1)
                    ):
                        problems.append(
                            f"sequences_{split}.jsonl:{lineno}: stage {stage!r} "
                            f"out of range (0..{max(n_stages - 1, 0)})"
                        )
                    if n > 200000:  # sanity cap on error volume, not on data
                        break
        except OSError as exc:
            problems.append(f"sequences_{split}.jsonl: unreadable ({exc})")
        stats[f"{split}_sequences"] = n

    if order_ids:
        orphan = all_seq_doc_ids - order_ids
        if orphan:
            problems.append(
                f"{len(orphan)} sequence doc_ids are not in curriculum.json order"
            )

    return {"ok": not problems, "problems": problems, "stats": stats}


def _read_json_line(line: str, lineno: int, what: str, problems: list[str]):
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        problems.append(f"{what}:{lineno}: malformed JSON, skipped")
        return None
    if not isinstance(obj, dict):
        problems.append(f"{what}:{lineno}: record is not an object, skipped")
        return None
    return obj
