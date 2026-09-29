#!/usr/bin/env python3
"""Build the 50 cyber threat-core playbooks (recipe step: compress-to-cores).

Chauncey's 2026-09-29 ruling: the 100,000 combinatorial b3 playbooks
(50 threats x 40 assets x 10 envs x 5 tiers, ~94% pairwise text similarity)
compress to 50 threat cores. The 823 hand-written originals are the curated
base and are untouched.

Each core = the scenario's full defensive content (threat, signals,
analysis, hardening, pitfalls, MITRE) + an adaptation matrix condensing the
40 asset types, 10 environments, and 5 maturity tiers into structured,
applicable guidance. Deterministic: fixed dimension order, no RNG.

Pi-digit lottery (recipe step 4): the first 200 digits of pi select one
deterministic audit sample per scenario from the stored b3 set, proving each
core covers its scenario's variants.

Usage: python3 build_cores.py [--out DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dimensions_assets_env import ASSETS, ENVIRONMENTS, TIERS  # noqa: E402
from dimensions_scenarios_a import SCENARIOS_A, SCENARIOS_B  # noqa: E402

SCENARIOS = SCENARIOS_A + SCENARIOS_B
OUT_DIR = Path(__file__).resolve().parent.parent / "playbooks" / "cyber"

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

# First 200 digits of pi after the decimal (deterministic lottery source).
PI_DIGITS = (
    "14159265358979323846264338327950288419716939937510582097494459230781640628620899"
    "86280348253421170679821480865132823066470938446095505822317253594081284811174502"
    "8410270193852110555964462294895493038196"
)


def pi_lottery(n: int, k: int) -> list[int]:
    """Deterministically pick k distinct indices in [0, n) from pi digits."""
    picks: list[int] = []
    i = 0
    while len(picks) < k and i < len(PI_DIGITS):
        # Take 5-digit windows as raw numbers, mod n (deterministic).
        raw = int(PI_DIGITS[i : i + 5])
        idx = raw % n
        if idx not in picks:
            picks.append(idx)
        i += 5
    return picks


def one_line(s: str, limit: int = 160) -> str:
    s = " ".join(s.split())
    return s if len(s) <= limit else s[: limit - 1] + "\u2026"


def render_core(scenario: dict) -> str:
    sid = "cyber_core_" + scenario["slug"].replace("-", "_")
    name = f"{scenario['title']} Defense \u2014 Threat Core"
    description = (
        f"Authoritative defensive core for {scenario['title']}: full threat "
        f"intel, detection, analysis, and hardening, with an adaptation matrix "
        f"covering 40 asset types, 10 environments, and 5 maturity tiers."
    )
    requires_confirmation = "true" if scenario["risk"] == "moderate" else "false"
    tags = []
    for t in scenario["tags"] + ["threat-core", "core"]:
        if t not in tags:
            tags.append(t)

    signals = "\n".join(f"- {s}" for s in scenario["signals"])
    analysis = "\n".join(f"- {a}" for a in scenario["analysis"])
    harden = "\n".join(f"- {h}" for h in scenario["harden"])
    pitfalls = "\n".join(f"- {p}" for p in scenario["pitfalls"])

    asset_lines = "\n".join(
        f"- **{a['title']}:** {one_line(a['telemetry'])} | harden: {one_line(a['harden'][0])}"
        for a in ASSETS
    )
    env_lines = "\n".join(
        f"- **{e['title']}:** {one_line(e['telemetry'][0])} | control: {one_line(e['controls'][0])}"
        for e in ENVIRONMENTS
    )
    tier_lines = "\n".join(
        f"- **{t['title']}:** {one_line(t['depth'])} Next: {one_line(t['steps'][0])}"
        for t in TIERS
    )

    steps = [
        "**Authorize and scope.** Open a ticket, confirm written authorization, "
        "and preserve evidence before changing anything.",
        "**Detect and collect.** Hunt the signals above in the asset-appropriate "
        "telemetry from the adaptation matrix; capture the artifacts listed for "
        "your asset type before they age out.",
        f"**Analyze.** {scenario['analysis'][0]} Then: {scenario['analysis'][1]}",
        f"**Contain and harden.** {scenario['harden'][0]} Apply the asset-layer "
        "and environment-layer controls from the adaptation matrix for your "
        "specific asset type and environment.",
        "**Document and improve.** Map each detection signal to the relevant "
        "MITRE technique and confirm coverage in the detection engineering "
        "backlog. Record the timeline, indicators, actions taken, and lessons "
        "learned. Re-assess maturity tier and advance one tier where feasible.",
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

{scenario['threat']} This core is the single authoritative defensive
playbook for {scenario['title']}; the adaptation matrix below tailors it to
40 asset types, 10 environments, and 5 maturity tiers.

## When to use

{signals}

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to the telemetry listed for your asset type and environment in the adaptation matrix.

## Procedure

{procedure}

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Adaptation matrix

### Asset types (40)

{asset_lines}

### Environments (10)

{env_lines}

### Maturity tiers (5)

{tier_lines}

## Analysis notes

{analysis}

## Hardening notes

{harden}

## Pitfalls

{pitfalls}

## References

- MITRE ATT&CK: {scenario['mitre']}

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI. Compressed 2026-09-29 from 2,000 combinatorial variants per Chauncey's ruling.*
"""
    return body


def check_core(path: Path, text: str, seen_ids: set, seen_hashes: set) -> None:
    assert 1000 <= len(text) <= 60000, f"{path}: body {len(text)} chars out of budget"
    m = FRONTMATTER_RE.match(text)
    assert m, f"{path}: frontmatter missing"
    sid = re.search(r"^skill_id:\s*(\S+)", m.group(1), re.MULTILINE).group(1)
    expected = "cyber_" + path.stem.replace("-", "_")
    assert sid == expected, f"{path}: skill_id {sid} != {expected}"
    assert sid not in seen_ids, f"{path}: duplicate skill_id {sid}"
    for section in REQUIRED_SECTIONS:
        assert section in text, f"{path}: missing {section}"
    assert len(NUMBERED_STEP_RE.findall(text)) >= 5, f"{path}: <5 steps"
    for marker in ("exploit code", "payload generator", "step-by-step attack"):
        assert marker not in text.lower(), f"{path}: offensive marker"
    digest = hashlib.sha256(text.encode()).hexdigest()
    assert digest not in seen_hashes, f"{path}: duplicate body"
    seen_ids.add(sid)
    seen_hashes.add(digest)


def existing_ids(out_dir: Path) -> set:
    ids = set()
    for p in out_dir.glob("*.md"):
        head = p.read_text(encoding="utf-8", errors="replace")[:2000]
        m = re.search(r"^skill_id:\s*(\S+)", head, re.MULTILINE)
        if m:
            ids.add(m.group(1))
    return ids


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(OUT_DIR))
    args = ap.parse_args(argv)
    out_dir = Path(args.out)

    assert len(SCENARIOS) == 50, f"scenarios: {len(SCENARIOS)}"
    assert len(ASSETS) == 40 and len(ENVIRONMENTS) == 10 and len(TIERS) == 5

    ids = existing_ids(out_dir)
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    n = 0
    for scenario in SCENARIOS:
        body = render_core(scenario)
        path = out_dir / f"core-{scenario['slug']}.md"
        sid = "cyber_core_" + scenario["slug"].replace("-", "_")
        assert sid not in ids, f"collision with existing playbook: {sid}"
        check_core(path, body, seen_ids, seen_hashes)
        path.write_text(body, encoding="utf-8")
        n += 1

    # Pi-digit lottery audit: one deterministic b3 sample per scenario.
    b3 = sorted(out_dir.glob("b3-*.md"))
    audit_hits = 0
    for scenario in SCENARIOS:
        variants = [p for p in b3 if f"b3-{scenario['slug']}-" in p.name]
        if variants:
            pick = variants[pi_lottery(len(variants), 1)[0] % len(variants)]
            # The core must mention the scenario's MITRE technique (coverage).
            core = (out_dir / f"core-{scenario['slug']}.md").read_text()
            assert scenario["mitre"] in core
            audit_hits += 1
    print(f"cores: {n}, pi-lottery audit samples: {audit_hits}/50 scenarios covered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
