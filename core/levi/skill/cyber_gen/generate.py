#!/usr/bin/env python3
"""Batch-3 combinatorial cyber playbook generator for LEVI.

Product: 50 threat scenarios x 40 asset types x 10 environments x 5
maturity tiers = 100,000 unique defensive playbooks.

Disk reality (2026-09-25): the shared volume holds ~354MB free, so each
playbook is rendered dense (target <= 2700 bytes, floor 1000). Every byte
is real content: genuine threat intel, detection signals, artifacts,
commands, and hardening per dimension. No filler, no lorem ipsum.

LAWS (from cyber_gen/LAWS.md), enforced by assertions in this file:
  L1  Exactly 100,000 files are produced (50*40*10*5), each unique.
  L2  Every file parses as an existing-format playbook (frontmatter,
      required sections, >=5 numbered procedure steps, >=1000 chars).
  L3  skill_id is unique across the batch and never collides with the
      823 pre-existing playbooks; skill_id == "cyber_" + filename stem
      with hyphens -> underscores (loader invariant).
  L4  Nothing pre-existing is modified or deleted.
  L5  All content is original defensive blue-team material. No offensive
      instructions. No contact with any external skill repository.
  L6  Generation is resumable and disk-aware: aborts instead of filling
      the filesystem.

Usage:
    python3 generate.py [--out DIR] [--chunk N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dimensions_assets_env import ASSETS, ENVIRONMENTS, TIERS  # noqa: E402
from dimensions_scenarios_a import SCENARIOS_A, SCENARIOS_B  # noqa: E402

SCENARIOS = SCENARIOS_A + SCENARIOS_B

OUT_DIR = Path(__file__).resolve().parent.parent / "playbooks" / "cyber"

# Disk budget: stop generation while enough headroom remains for the
# follow-up git commit batches (see commit plan in the final report).
MIN_FREE_BYTES = 40_000_000

REQUIRED_SECTIONS = [
    "## Purpose",
    "## When to use",
    "## Prerequisites",
    "## Procedure",
    "## Expected outputs",
    "## Pitfalls",
    "## References",
]

NUMBERED_STEP_RE = re.compile(r"^(\d+)\.\s+\S", re.MULTILINE)
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)

# Must match tests/test_cyber_skills.py::test_no_attack_howto_markers.
OFFENSIVE_MARKERS = [
    "exploit code",
    "payload generator",
    "step-by-step attack",
    "zero-day exploit",
]


def slug_filename(scenario, asset, env, tier) -> str:
    return (
        f"b3-{scenario['slug']}-{asset['slug']}-{env['slug']}-{tier['slug']}.md"
    )


def skill_id(scenario, asset, env, tier) -> str:
    stem = slug_filename(scenario, asset, env, tier)[: -len(".md")]
    return "cyber_" + stem.replace("-", "_")


def render(scenario, asset, env, tier) -> str:
    sid = skill_id(scenario, asset, env, tier)
    name = (
        f"{scenario['title']} Defense for {asset['title']} "
        f"in {env['title']} ({tier['title']} Maturity)"
    )
    description = (
        f"{scenario['title']} defense playbook for {asset['title']} "
        f"in {env['title']} at {tier['title']} maturity."
    )
    requires_confirmation = "true" if scenario["risk"] == "moderate" else "false"
    tags = []
    for t in scenario["tags"] + asset["tags"] + env["tags"] + tier["tags"]:
        if t not in tags:
            tags.append(t)

    steps = [
        "**Authorize and scope.** Open a ticket, confirm written authorization, "
        "and preserve evidence before changing anything.",
        f"**Detect and collect.** Hunt the signals above in {asset['artifacts'][0]} "
        f"and {asset['artifacts'][1]}; run `{asset['commands'][0]}` then "
        f"`{asset['commands'][1]}`.",
        f"**Analyze.** {scenario['analysis'][0]} Then: {scenario['analysis'][1]}",
        f"**Contain and harden.** {scenario['harden'][0]} "
        f"Asset layer: {asset['harden'][0]} Environment layer: {env['controls'][0]}",
        f"**Document and improve.** {tier['steps'][1]} Record the timeline, "
        "indicators, actions taken, and lessons learned.",
    ]
    procedure = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps))

    body = f"""---
skill_id: {sid}
name: {name}
description: "{description}"
risk: {scenario['risk']}
permissions: []
requires_confirmation: {requires_confirmation}
tags: [{", ".join(tags)}]
version: 1.0.0
---
# {name}

## Purpose

{scenario['threat']} Applies to {asset['title']} in {env['title']} at {tier['title']} maturity.

## When to use

- {scenario['signals'][0]}
- {scenario['signals'][1]}
- {scenario['signals'][2]}
- Lens: {asset['telemetry']} {env['telemetry'][0]}

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to {env['telemetry'][1]}

## Procedure

{procedure}

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- {scenario['pitfalls'][0]}
- {scenario['pitfalls'][1]}

## References

- MITRE ATT&CK: {scenario['mitre']}
- Vendor logging and hardening baselines for {asset['title']}; {env['controls'][0]}

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
"""
    return body


def check_laws(path: Path, text: str, seen_ids: set, seen_hashes: set) -> None:
    """L2/L5 guard: structural invariants on one rendered playbook."""
    assert 1000 <= len(text) <= 5000, f"{path}: body {len(text)} chars out of budget"
    m = FRONTMATTER_RE.match(text)
    assert m, f"{path}: frontmatter missing"
    fm = m.group(1)
    sid_m = re.search(r"^skill_id:\s*(\S+)", fm, re.MULTILINE)
    assert sid_m, f"{path}: skill_id missing"
    sid = sid_m.group(1)
    # L3: id scheme locked to filename (loader + test invariant).
    expected = "cyber_" + path.stem.replace("-", "_")
    assert sid == expected, f"{path}: skill_id {sid} != {expected}"
    assert sid not in seen_ids, f"{path}: duplicate skill_id {sid}"
    assert re.search(r"^version:\s*1\.0\.0", fm, re.MULTILINE), f"{path}: version"
    assert re.search(r"^risk:\s*(info|low|moderate)", fm, re.MULTILINE), (
        f"{path}: risk"
    )
    for section in REQUIRED_SECTIONS:
        assert section in text, f"{path}: missing {section}"
    steps = NUMBERED_STEP_RE.findall(text)
    assert len(steps) >= 5, f"{path}: only {len(steps)} numbered steps"
    lowered = text.lower()
    for marker in OFFENSIVE_MARKERS:
        assert marker not in lowered, f"{path}: offensive marker {marker!r}"
    digest = hashlib.sha256(text.encode()).hexdigest()
    assert digest not in seen_hashes, f"{path}: duplicate body hash"
    seen_ids.add(sid)
    seen_hashes.add(digest)


def existing_ids(out_dir: Path) -> set:
    """L3: skill_ids of pre-existing (non-b3) playbooks, for collision check."""
    ids = set()
    for p in out_dir.glob("*.md"):
        if p.name.startswith("b3-"):
            continue
        head = p.read_text(encoding="utf-8", errors="replace")[:2000]
        m = re.search(r"^skill_id:\s*(\S+)", head, re.MULTILINE)
        if m:
            ids.add(m.group(1))
    return ids


def generate(out_dir: Path, chunk: int = 10000) -> dict:
    assert len(SCENARIOS) == 50, f"scenarios: {len(SCENARIOS)}"
    assert len(ASSETS) == 40, f"assets: {len(ASSETS)}"
    assert len(ENVIRONMENTS) == 10, f"environments: {len(ENVIRONMENTS)}"
    assert len(TIERS) == 5, f"tiers: {len(TIERS)}"
    for dim, want_key in (
        (SCENARIOS, "threat"),
        (ASSETS, "artifacts"),
        (ENVIRONMENTS, "telemetry"),
        (TIERS, "depth"),
    ):
        slugs = [d["slug"] for d in dim]
        assert len(set(slugs)) == len(slugs), "duplicate slugs in a dimension"
        for d in dim:
            assert d["slug"] and d["title"] and d[want_key], f"empty field in {d}"

    out_dir.mkdir(parents=True, exist_ok=True)
    pre_existing = existing_ids(out_dir)
    print(f"pre-existing non-b3 playbooks: {len(pre_existing)}", flush=True)

    combos = [
        (s, a, e, t)
        for s in SCENARIOS
        for a in ASSETS
        for e in ENVIRONMENTS
        for t in TIERS
    ]
    assert len(combos) == 100_000, f"combo count {len(combos)}"

    # Disk budget projection from a 500-file sample (L6).
    sample_bytes = sum(len(render(*c).encode()) for c in combos[:500])
    projected = sample_bytes / 500 * len(combos)
    free = shutil.disk_usage(out_dir).free
    print(
        f"sample avg bytes/file: {sample_bytes / 500:.0f}; "
        f"projected total: {projected / 1e9:.2f}GB; free: {free / 1e9:.2f}GB",
        flush=True,
    )
    assert projected + MIN_FREE_BYTES < free, (
        f"disk budget exceeded: need {projected / 1e9:.2f}GB + "
        f"{MIN_FREE_BYTES / 1e9:.2f}GB headroom, have {free / 1e9:.2f}GB"
    )

    seen_ids: set = set()
    seen_hashes: set = set()
    written = 0
    skipped_present = 0
    t0 = time.time()

    for i, (s, a, e, t) in enumerate(combos):
        fname = slug_filename(s, a, e, t)
        path = out_dir / fname
        sid = skill_id(s, a, e, t)
        assert sid not in pre_existing, f"collision with existing: {sid}"
        if path.exists():
            text = path.read_text(encoding="utf-8")
            check_laws(path, text, seen_ids, seen_hashes)
            skipped_present += 1
        else:
            text = render(s, a, e, t)
            check_laws(path, text, seen_ids, seen_hashes)
            path.write_text(text, encoding="utf-8")
            written += 1
        if (i + 1) % chunk == 0:
            free = shutil.disk_usage(out_dir).free
            elapsed = time.time() - t0
            print(
                f"[{i + 1}/{len(combos)}] written={written} "
                f"reused={skipped_present} free={free / 1e9:.2f}GB "
                f"elapsed={elapsed:.0f}s",
                flush=True,
            )
            assert free > MIN_FREE_BYTES, "disk headroom breached — aborting (L6)"

    assert written + skipped_present == 100_000, (
        f"total mismatch: {written + skipped_present}"
    )
    assert len(seen_ids) == 100_000, f"unique ids: {len(seen_ids)}"
    assert len(seen_hashes) == 100_000, f"unique bodies: {len(seen_hashes)}"
    elapsed = time.time() - t0
    report = {
        "total": len(combos),
        "written": written,
        "reused_present": skipped_present,
        "unique_skill_ids": len(seen_ids),
        "unique_bodies": len(seen_hashes),
        "elapsed_s": round(elapsed, 1),
        "pre_existing_non_b3": len(pre_existing),
        "projected_bytes": round(projected),
    }
    print("DONE", report, flush=True)
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--chunk", type=int, default=10000)
    args = ap.parse_args()
    report = generate(Path(args.out), chunk=args.chunk)
    rep_path = Path(__file__).resolve().parent / "generation_report.json"
    rep_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"report: {rep_path}")


if __name__ == "__main__":
    main()
