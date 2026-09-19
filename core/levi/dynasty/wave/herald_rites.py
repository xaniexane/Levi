# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Herald rites tooling — edition diffs, upgrade plans, vocabulary lint, rite templates.

Companion machinery for the Herald wave agent
(core/levi/dynasty/wave/herald.py), which owns "editions expansion":
sector editions as declared, versioned, auditable manifests. This module
is the upgrade path between editions — what changed, what the migration
order is, and the guardrail that keeps true names untranslated.

Pure logic: no I/O, no network, stdlib only.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Union

from levi.dynasty.dna import AgentError

__all__ = [
    "EditionError",
    "diff_manifests",
    "plan_upgrade",
    "lint_vocab",
    "template",
    "validate_skeleton",
]


class EditionError(AgentError):
    """An edition diff, lint, template, or skeleton check was refused."""


_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
_SECTORS = ("research", "crime", "custom")
_REQUIRED_FIELDS = ("name", "version", "rites", "vocabulary", "wares")


# ---------------------------------------------------------------------
# edition diffs
# ---------------------------------------------------------------------


def _check_manifest(manifest: Any, which: str) -> Dict[str, Any]:
    if not isinstance(manifest, dict):
        raise EditionError(f"{which} manifest must be a dict")
    return manifest


def _rite_list(manifest: Dict[str, Any], which: str) -> List[str]:
    rites = manifest.get("rites") or []
    if not isinstance(rites, list) or any(not isinstance(r, str) for r in rites):
        raise EditionError(f"{which} manifest: rites must be a list of strings")
    return rites


def _vocab_map(manifest: Dict[str, Any], which: str) -> Dict[str, str]:
    vocab = manifest.get("vocabulary") or {}
    if not isinstance(vocab, dict) or any(
        not isinstance(k, str) or not isinstance(v, str) for k, v in vocab.items()
    ):
        raise EditionError(f"{which} manifest: vocabulary must be a dict of str->str")
    return vocab


def _version_bump(old_version: Any, new_version: Any) -> str:
    """Classify the version step: major/minor/patch/none/downgrade/invalid."""
    old = str(old_version or "")
    new = str(new_version or "")
    if not _VERSION_RE.match(old) or not _VERSION_RE.match(new):
        return "invalid"
    old_t = tuple(int(p) for p in old.split("."))
    new_t = tuple(int(p) for p in new.split("."))
    if new_t == old_t:
        return "none"
    if new_t < old_t:
        return "downgrade"
    if new_t[0] != old_t[0]:
        return "major"
    if new_t[1] != old_t[1]:
        return "minor"
    return "patch"


def diff_manifests(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """Diff two edition manifests.

    Rites are compared positionally: entries at the same index that
    differ are changed_rites ({index, from, to}); the longer list's
    tail is added_rites/removed_rites. Vocabulary diffs by key:
    added_vocab/removed_vocab carry {term: meaning}, changed_vocab
    carries {term: {from, to}}. version_bump classifies the version
    step (major/minor/patch/none/downgrade/invalid).
    """
    old_m = _check_manifest(old, "old")
    new_m = _check_manifest(new, "new")
    old_rites = _rite_list(old_m, "old")
    new_rites = _rite_list(new_m, "new")
    shared = min(len(old_rites), len(new_rites))
    changed_rites = [
        {"index": i, "from": old_rites[i], "to": new_rites[i]}
        for i in range(shared)
        if old_rites[i] != new_rites[i]
    ]
    old_vocab = _vocab_map(old_m, "old")
    new_vocab = _vocab_map(new_m, "new")
    added_vocab = {k: v for k, v in new_vocab.items() if k not in old_vocab}
    removed_vocab = {k: v for k, v in old_vocab.items() if k not in new_vocab}
    changed_vocab = {
        k: {"from": old_vocab[k], "to": new_vocab[k]}
        for k in old_vocab
        if k in new_vocab and old_vocab[k] != new_vocab[k]
    }
    return {
        "added_rites": new_rites[shared:],
        "removed_rites": old_rites[shared:],
        "changed_rites": changed_rites,
        "added_vocab": added_vocab,
        "removed_vocab": removed_vocab,
        "changed_vocab": changed_vocab,
        "version_bump": _version_bump(old_m.get("version"), new_m.get("version")),
    }


# ---------------------------------------------------------------------
# upgrade planner
# ---------------------------------------------------------------------


def plan_upgrade(old: Dict[str, Any], new: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Ordered migration steps from the old manifest to the new one.

    Order is load-bearing: removals before changes before additions,
    and vocabulary before rites (a rite may cite a term that must
    already exist). A set_version step closes the plan when the
    version actually moves.
    """
    diff = diff_manifests(old, new)
    steps: List[Dict[str, Any]] = []

    def add(action: str, detail: Dict[str, Any]) -> None:
        steps.append({"order": len(steps), "action": action, "detail": detail})

    for term in sorted(diff["removed_vocab"]):
        add("remove_vocab", {"term": term})
    for term in sorted(diff["changed_vocab"]):
        change = diff["changed_vocab"][term]
        add("change_vocab", {"term": term, "from": change["from"], "to": change["to"]})
    for term in sorted(diff["added_vocab"]):
        add("add_vocab", {"term": term, "meaning": diff["added_vocab"][term]})
    for rite in diff["removed_rites"]:
        add("remove_rite", {"rite": rite})
    for change in diff["changed_rites"]:
        add(
            "change_rite",
            {"index": change["index"], "from": change["from"], "to": change["to"]},
        )
    for rite in diff["added_rites"]:
        add("add_rite", {"rite": rite})
    if diff["version_bump"] not in ("none", "invalid"):
        add(
            "set_version",
            {
                "from": str(old.get("version")),
                "to": str(new.get("version")),
                "bump": diff["version_bump"],
            },
        )
    return steps


# ---------------------------------------------------------------------
# vocabulary linter — true names stay untranslated
# ---------------------------------------------------------------------


def _fold(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def lint_vocab(
    vocab: Dict[str, str], protected: Union[Set[str], List[str]]
) -> List[Dict[str, str]]:
    """Flag protected canon names that appear renamed as vocabulary keys.

    The guardrail: a true name must appear as a key spelled EXACTLY as
    the canon. Any key that matches a protected name case-insensitively
    (ignoring punctuation/spacing) but is not the exact canon spelling
    is a rename violation -> {term, mapping}.

    DOCUMENTED LIMIT: this catches spelling variants ("omega", "OMEGA",
    "O-m-e-g-a"), never semantic translations. "Omega" mistranslated to
    "the-end" is invisible to this linter — meaning-level policing is
    a human call, not a regex.
    """
    if not isinstance(vocab, dict):
        raise EditionError("vocab must be a dict")
    if isinstance(protected, (set, list, tuple)):
        canon_names = list(protected)
    else:
        raise EditionError("protected must be a set/list of canon names")
    for term in canon_names:
        if not isinstance(term, str) or not term.strip():
            raise EditionError("protected canon names must be non-empty strings")
    violations = []
    for canon in canon_names:
        folded = _fold(canon)
        for key in vocab:
            if not isinstance(key, str):
                continue
            if key != canon and _fold(key) == folded:
                violations.append({"term": canon, "mapping": key})
    return violations


# ---------------------------------------------------------------------
# rite templates
# ---------------------------------------------------------------------

_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "research": {
        "name": "LEVI Research Edition",
        "rites": [
            "preregister the hypothesis before the first run",
            "publish the method with the result, not after it",
        ],
        "vocabulary": {
            "hypothesis": "a falsifiable claim, stated before the run",
            "provenance": "the chain of custody for every number",
        },
        "wares": ["experiment ledger", "replication queue"],
    },
    "crime": {
        "name": "LEVI Crime Edition",
        "rites": [
            "name the victim before the method",
            "every claim of harm cites its record",
        ],
        "vocabulary": {
            "record": "the sealed account of what happened",
            "restitution": "what is owed, named before it is paid",
        },
        "wares": ["case ledger", "restitution queue"],
    },
    "custom": {
        "name": "LEVI Custom Edition",
        "rites": ["declare the sector before the first rite"],
        "vocabulary": {"sector": "the ground this edition stands on"},
        "wares": ["sector ledger"],
    },
}


def template(sector: str) -> Dict[str, Any]:
    """A skeleton manifest for a sector edition. sector is one of
    research/crime/custom; anything else raises EditionError."""
    if sector not in _SECTORS:
        raise EditionError(f"sector must be one of {', '.join(_SECTORS)}")
    spec = _TEMPLATES[sector]
    return {
        "name": spec["name"],
        "version": "0.1.0",
        "rites": list(spec["rites"]),
        "vocabulary": dict(spec["vocabulary"]),
        "wares": list(spec["wares"]),
    }


def validate_skeleton(manifest: Any) -> List[Dict[str, str]]:
    """Check a manifest against the required skeleton fields
    [name, version, rites, vocabulary, wares]. Returns a list of
    {field, problem} violations; an empty list means the skeleton holds."""
    if not isinstance(manifest, dict):
        raise EditionError("manifest must be a dict")
    violations = []
    for field in _REQUIRED_FIELDS:
        if field not in manifest:
            violations.append({"field": field, "problem": "missing"})
            continue
        value = manifest[field]
        if field in ("rites", "wares"):
            if not isinstance(value, list):
                violations.append({"field": field, "problem": "wrong_type"})
            elif not value:
                violations.append({"field": field, "problem": "empty"})
        elif field == "vocabulary":
            if not isinstance(value, dict):
                violations.append({"field": field, "problem": "wrong_type"})
            elif not value:
                violations.append({"field": field, "problem": "empty"})
        else:  # name, version
            if not isinstance(value, str):
                violations.append({"field": field, "problem": "wrong_type"})
            elif not value.strip():
                violations.append({"field": field, "problem": "empty"})
    return violations
