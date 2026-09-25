"""Change-scoped refinement: conversational iteration without amnesia.

The giants regenerate the whole project on every edit and drift it into
code the user never wrote. Refinement here is the opposite: a change
request produces a diff, the diff touches only what changed, untouched
files stay byte-identical, nothing is ever deleted, and the iteration is
appended to the project's provenance — the same iteration history the
competitors keep only in a chat thread we can see, but as data.

Deterministic in the change request: the same request against the same
project produces the same diff. The iteration record is time-bound history,
not build bytes.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List

from levi.builders.actions import apply_actions, plan_actions
from levi.builders.scaffold import ScaffoldEngine
from levi.builders.verify import BuildOutcome, CheckResult, VerifyLoop

_PROVENANCE = ".provenance.json"


@dataclass
class RefineReport:
    outcome: BuildOutcome
    files_added: List[str] = field(default_factory=list)
    files_changed: List[str] = field(default_factory=list)
    files_untouched: List[str] = field(default_factory=list)
    checks: List[CheckResult] = field(default_factory=list)
    diagnostics: str = ""
    target_dir: str = ""


def _read_tree(root: str) -> Dict[str, str]:
    tree: Dict[str, str] = {}
    for dirpath, _dirs, names in os.walk(root):
        for name in sorted(names):
            if name.endswith(".pyc") or name == "__pycache__":
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            try:
                with open(full, "r", encoding="utf-8") as fh:
                    tree[rel] = fh.read()
            except (OSError, UnicodeDecodeError):
                continue
    return tree


def refine(workdir: str, change_request: str, _fault_hook=None) -> RefineReport:
    """Apply a change request to an existing built project.

    Returns a RefineReport. The project's files are only ever added to or
    changed in place — never deleted — and the iteration is recorded in
    .provenance.json. The merged result is verified before return.
    """
    if not change_request or not change_request.strip():
        raise ValueError("change_request must not be empty")
    target_dir = os.path.abspath(workdir)
    if not os.path.isdir(target_dir):
        raise FileNotFoundError("no built project at %s" % target_dir)

    prov_path = os.path.join(target_dir, _PROVENANCE)
    try:
        with open(prov_path, encoding="utf-8") as fh:
            old_prov = json.load(fh)
    except (OSError, ValueError):
        old_prov = {}
    original_prompt = old_prov.get("prompt") or old_prov.get("builder", {}).get(
        "prompt", ""
    )
    combined = (
        "%s\nRefinement: %s" % (original_prompt, change_request.strip())
        if original_prompt
        else change_request.strip()
    )

    engine = ScaffoldEngine(combined, _fault_hook=_fault_hook)
    new_files = engine.generate()
    old_files = _read_tree(target_dir)

    files_added: List[str] = []
    files_changed: List[str] = []
    files_untouched: List[str] = []
    overlay: Dict[str, str] = {}
    for path, content in sorted(new_files.items()):
        if path not in old_files:
            files_added.append(path)
            overlay[path] = content
        elif old_files[path] != content:
            files_changed.append(path)
            overlay[path] = content
        else:
            files_untouched.append(path)

    # Provenance: keep the original record, append the iteration.
    iterations = list(old_prov.get("iterations", []))
    new_prov = dict(old_prov)
    new_prov["prompt"] = combined
    new_prov["entities"] = engine.entities
    new_prov["provenance"] = "builder"
    iterations.append(
        {
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "change": change_request.strip(),
            "files_added": files_added,
            "files_changed": files_changed,
            "outcome": None,  # filled after verification
        }
    )
    new_prov["iterations"] = iterations
    prov_text = json.dumps(new_prov, indent=2, sort_keys=True) + "\n"
    if old_files.get(_PROVENANCE) != prov_text:
        overlay[_PROVENANCE] = prov_text
        if _PROVENANCE in files_untouched:
            files_untouched.remove(_PROVENANCE)
        if _PROVENANCE not in files_changed and _PROVENANCE not in files_added:
            files_changed.append(_PROVENANCE)

    # Write only what changed — the disk is never wholesale regenerated.
    action_plan = plan_actions(engine.build_plan, overlay)
    apply_actions(action_plan, target_dir, overlay)

    # Verify the merged whole, not just the diff.
    merged = dict(old_files)
    merged.update(overlay)
    loop = VerifyLoop()
    verdict = loop.verify_files(engine.build_plan, merged, target_dir)
    iterations[-1]["outcome"] = verdict.outcome.value
    final_prov = dict(new_prov)
    final_prov["iterations"] = iterations
    with open(prov_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(final_prov, indent=2, sort_keys=True) + "\n")

    return RefineReport(
        outcome=verdict.outcome,
        files_added=sorted(files_added),
        files_changed=sorted(files_changed),
        files_untouched=sorted(files_untouched),
        checks=verdict.checks,
        diagnostics=verdict.diagnostics,
        target_dir=target_dir,
    )
