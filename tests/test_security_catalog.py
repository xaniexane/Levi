"""Tests for the LEVI offline security knowledge index.

Covers: catalog shape (81 domains from the Awesome-Hacking meta-list's
category names), schema completeness, unique kebab-case ids, the defensive
framing structural guarantee (detection_notes + hardening_notes non-empty on
every entry), and the attack-profile guarantee (attack_relevant entries carry
a non-empty attack_profile; knowledge of attacks, never instructions).
"""

from __future__ import annotations

import json
import re
from pathlib import Path


SECURITY = (
    Path(__file__).resolve().parent.parent / "core" / "levi" / "knowledge" / "security"
)

BASE_KEYS = {
    "id",
    "name",
    "defensive_summary",
    "detection_notes",
    "hardening_notes",
    "key_concepts",
    "reference",
    "attack_relevant",
}


def _catalog() -> dict:
    return json.loads((SECURITY / "catalog.json").read_text(encoding="utf-8"))


def test_catalog_has_81_domains():
    catalog = _catalog()
    entries = catalog["entries"]
    assert len(entries) == 81, f"expected 81 domains, got {len(entries)}"


def test_schema_complete_and_ids_unique_kebab():
    entries = _catalog()["entries"]
    ids = []
    for e in entries:
        assert BASE_KEYS <= set(e.keys()), f"{e.get('id')}: missing keys"
        assert e["id"] and re.fullmatch(r"[a-z0-9-]+", e["id"]), f"bad id: {e['id']!r}"
        assert e["name"], f"{e['id']}: empty name"
        assert len(e["defensive_summary"]) >= 100, f"{e['id']}: summary too short"
        assert 3 <= len(e["key_concepts"]) <= 8, f"{e['id']}: key_concepts size"
        assert e["reference"].startswith("Hack-with-Github/Awesome-Hacking -> "), (
            f"{e['id']}: bad reference pointer"
        )
        assert isinstance(e["attack_relevant"], bool), f"{e['id']}: attack_relevant not bool"
        ids.append(e["id"])
    assert len(set(ids)) == len(ids), "duplicate ids"


def test_defensive_framing_structural_guarantee():
    # Every entry — including offensive-leaning domains — must carry
    # defender-actionable detection and hardening notes. Nothing blocked.
    for e in _catalog()["entries"]:
        assert e["detection_notes"].strip(), f"{e['id']}: empty detection_notes"
        assert e["hardening_notes"].strip(), f"{e['id']}: empty hardening_notes"


def test_attack_profile_breadth_and_presence():
    # "Even the attacks": a broad set of attack-relevant domains must carry
    # ATT&CK-style technique knowledge (what/how/targets/footprints),
    # and non-relevant entries must not carry a stray profile.
    entries = _catalog()["entries"]
    relevant = [e for e in entries if e["attack_relevant"]]
    assert len(relevant) >= 40, f"expected broad attack coverage, got {len(relevant)}"
    for e in relevant:
        prof = e.get("attack_profile", "")
        assert prof and len(prof.strip()) >= 200, (
            f"{e['id']}: attack_profile missing or too thin"
        )
    stray = [e["id"] for e in entries if not e["attack_relevant"] and "attack_profile" in e]
    assert not stray, f"stray attack_profile on non-relevant entries: {stray}"


def test_known_attack_domains_covered():
    ids = {e["id"] for e in _catalog()["entries"]}
    for must in (
        "password-cracking",
        "payloads",
        "payloadsallthethings",
        "social-engineering",
        "linux-kernel-exploitation",
        "gtfobins",
        "red-teaming-toolkit",
        "red-team-physical-tools",
        "cve-poc",
        "prompt-injection",
    ):
        assert must in ids, f"blocked/omitted domain: {must}"
        entry = next(e for e in _catalog()["entries"] if e["id"] == must)
        assert entry["attack_relevant"] and entry["attack_profile"].strip()


def test_security_cli_wires_up():
    import subprocess
    import sys

    repo = Path(__file__).resolve().parent.parent
    r = subprocess.run(
        [sys.executable, "-m", "levi.cli.main", "security", "list"],
        capture_output=True,
        text=True,
        cwd=repo / "core",
        timeout=60,
    )
    assert r.returncode == 0, r.stderr[-500:]
    assert "password-cracking" in r.stdout and "81 security domains" in r.stdout
    r = subprocess.run(
        [sys.executable, "-m", "levi.cli.main", "security", "show", "yara"],
        capture_output=True,
        text=True,
        cwd=repo / "core",
        timeout=60,
    )
    assert r.returncode == 0, r.stderr[-500:]
    assert "YARA" in r.stdout and "-- detection --" in r.stdout
    r = subprocess.run(
        [sys.executable, "-m", "levi.cli.main", "security", "search", "phishing"],
        capture_output=True,
        text=True,
        cwd=repo / "core",
        timeout=60,
    )
    assert r.returncode == 0, r.stderr[-500:]
    assert "social-engineering" in r.stdout
