"""Genesis package tests — hermetic, fast, stdlib only."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from levi.genesis import assemble, license as genesis_license, money, parts, remix


# --- parts catalog ---------------------------------------------------------

def test_parts_catalog_has_eleven_sources_no_heavy_import():
    caps = parts.list_capabilities()
    assert len(caps) == 11
    for c in caps:
        assert c["lineage_hash"] and len(c["lineage_hash"]) == 64
        assert c["source_files"]


def test_catalog_receipt_stable():
    assert parts.catalog_receipt()["catalog_hash"] == parts.catalog_receipt()["catalog_hash"]


# --- forge determinism ------------------------------------------------------

def _spec(entries):
    return [{"source": s, "mode": m, "seed": sd} for s, m, sd in entries]


def test_forge_determinism_same_spec_seed_same_variant():
    a = remix.forge_variant("quartermaster", "remix", 7)
    b = remix.forge_variant("quartermaster", "remix", 7)
    assert a == b
    c = remix.forge_variant("quartermaster", "remix", 8)
    assert c["variant_id"] != a["variant_id"]


def test_forge_all_modes_deterministic():
    for mode in remix.MODES:
        a = remix.forge_variant("herald", mode, 42)
        b = remix.forge_variant("herald", mode, 42)
        assert a == b, mode


def test_roster_forge_deterministic():
    spec = _spec([("keystone", "rename", 1), ("vaultkeeper", "mutate", 3)])
    assert remix.forge_roster(spec) == remix.forge_roster(spec)


def test_forge_rejects_bad_mode_and_unknown_source():
    with pytest.raises(remix.ForgeError):
        remix.forge_variant("keystone", "teleport", 1)
    with pytest.raises((remix.ForgeError, KeyError)):
        remix.forge_variant("nosuchagent", "rename", 1)


# --- no leaks: raw originals never surface ----------------------------------

RAW = set(parts.BASE_AGENTS) | {
    "forgehand", "gamemaster", "herald", "keystone", "quartermaster",
    "schoolmaster", "shellwright", "starmaker", "threadweaver",
    "vaultkeeper", "veilwright", "dynasty", "legion", "section 0",
}
# Note: "cybrus" is deliberately NOT in RAW — it is the keeper's payment
# gateway (money doctrine), correctly named in quote.json's paper receipt.


def test_no_raw_names_in_any_forged_output():
    for agent in parts.BASE_AGENTS:
        for mode in remix.MODES:
            for seed in (0, 1, 99):
                v = remix.forge_variant(agent, mode, seed)
                blob = (v["name"] + "\n" + v["description"] + "\n" + "\n".join(v["traits"])).lower()
                for raw in RAW:
                    assert raw not in blob, (agent, mode, seed, raw)


def test_no_mask_violations_in_forged_output():
    from levi.bot.persona import check_no_mask

    for agent in parts.BASE_AGENTS:
        for mode in remix.MODES:
            v = remix.forge_variant(agent, mode, 5)
            text = v["name"] + "\n" + v["description"]
            assert check_no_mask(text) == [], (agent, mode, text)


def test_variant_identity_is_new():
    v = remix.forge_variant("starmaker", "rename", 2)
    assert v["name"].lower() not in RAW
    assert v["variant_id"].startswith("gen-")
    # lineage travels as hash, never as a name
    assert len(v["lineage"]["lineage_hash"]) == 64


# --- assembly + hash-chain --------------------------------------------------

def _demo_spec():
    return {
        "name": "Test Genesis Pack",
        "variants": [
            {"source": "forgehand", "mode": "rename", "seed": 11},
            {"source": "gamemaster", "mode": "remix", "seed": 12},
            {"source": "quartermaster", "mode": "mutate", "seed": 13},
        ],
    }


def test_assemble_end_to_end(tmp_path):
    summary = assemble.assemble(_demo_spec(), root=tmp_path)
    pack_dir = Path(summary["pack_dir"])
    assert pack_dir.is_dir()
    manifest = json.loads((pack_dir / "manifest.json").read_text())
    assert manifest["license_terms"] == "lifetime single-copy"
    assert len(manifest["variants"]) == 3
    assert all(len(v["lineage_hash"]) == 64 for v in manifest["variants"])
    # no raw names anywhere in the buyer-facing files
    for f in ("README.md", "manifest.json", "license.json", "quote.json"):
        blob = (pack_dir / f).read_text(encoding="utf-8").lower()
        for raw in RAW:
            assert raw not in blob, (f, raw)
    for mod in (pack_dir / "variants").glob("*.py"):
        blob = mod.read_text(encoding="utf-8").lower()
        for raw in RAW:
            assert raw not in blob, (mod.name, raw)
    # hash-chain verifies
    result = assemble.verify_pack(pack_dir)
    assert result["ok"], result
    # tamper breaks the chain
    (pack_dir / "README.md").write_text("tampered", encoding="utf-8")
    assert not assemble.verify_pack(pack_dir)["ok"]


def test_assemble_is_deterministic(tmp_path):
    s1 = assemble.assemble(_demo_spec(), root=tmp_path / "a")
    s2 = assemble.assemble(_demo_spec(), root=tmp_path / "b")
    # Pack id and roster are spec-derived (deterministic); the final hash
    # binds the real build timestamp, so it legitimately differs per run.
    assert s1["pack_id"] == s2["pack_id"]
    assert s1["variants"] == s2["variants"]
    m1 = json.loads((Path(s1["pack_dir"]) / "manifest.json").read_text())
    m2 = json.loads((Path(s2["pack_dir"]) / "manifest.json").read_text())
    assert m1["spec_hash"] == m2["spec_hash"]
    assert m1["variants"] == m2["variants"]
    assert assemble.verify_pack(Path(s1["pack_dir"]))["ok"]
    assert assemble.verify_pack(Path(s2["pack_dir"]))["ok"]


def test_operator_integration_registered_not_fatal(tmp_path):
    summary = assemble.assemble(_demo_spec(), root=tmp_path)
    manifest = json.loads((Path(summary["pack_dir"]) / "manifest.json").read_text())
    integration = manifest["operator_integration"]
    assert integration["status"] == "registered"
    assert integration["detail"]
    assert all(
        d["status"] == "registered" and d["kind"] == "si"
        for d in integration["detail"]
    )


# --- install routine --------------------------------------------------------

def test_install_dry_run(tmp_path):
    summary = assemble.assemble(_demo_spec(), root=tmp_path / "packs")
    pack_dir = Path(summary["pack_dir"])
    target = tmp_path / "home"
    r = subprocess.run(
        [sys.executable, str(pack_dir / "install.py"),
         "--target", str(target), "--dry-run"],
        capture_output=True, text=True, timeout=60,
    )
    assert r.returncode == 0, r.stderr
    assert "dry-run" in r.stdout
    assert not (target / "genesis").exists()


def test_install_real_run(tmp_path):
    summary = assemble.assemble(_demo_spec(), root=tmp_path / "packs")
    pack_dir = Path(summary["pack_dir"])
    target = tmp_path / "home"
    r = subprocess.run(
        [sys.executable, str(pack_dir / "install.py"), "--target", str(target)],
        capture_output=True, text=True, timeout=60,
    )
    assert r.returncode == 0, r.stderr
    dest = target / "genesis" / summary["pack_id"]
    assert (dest / "installed.json").is_file()
    assert (dest / "manifest.json").is_file()


def test_install_refuses_tampered_pack(tmp_path):
    summary = assemble.assemble(_demo_spec(), root=tmp_path / "packs")
    pack_dir = Path(summary["pack_dir"])
    (pack_dir / "README.md").write_text("tampered", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(pack_dir / "install.py"),
         "--target", str(tmp_path / "home")],
        capture_output=True, text=True, timeout=60,
    )
    assert r.returncode == 2
    assert "VERIFY FAILED" in r.stdout


# --- license ----------------------------------------------------------------

def test_license_mint_blank_buyer_and_terms():
    rec = genesis_license.mint_license("gen-pack-abc", "deadbeef")
    assert rec["buyer"] == "UNASSIGNED"
    assert rec["terms"]["sale"].startswith("one-time purchase")
    assert rec["terms"]["copy"].startswith("1 copy")
    assert genesis_license.validate_license(rec)
    assert not genesis_license.validate_license({"license_id": "x"})


# --- money seam: paper only --------------------------------------------------

def test_quote_deterministic_and_split_7030():
    q1 = money.quote_pack(3)
    q2 = money.quote_pack(3)
    assert q1 == q2
    split = q1["split_projection"]
    total = split["keeper_70"] + split["pool_30"]
    assert abs(total - q1["recommended_lifetime_price"]) < 0.02
    assert abs(split["keeper_70"] / q1["recommended_lifetime_price"] - 0.7) < 0.01


def test_checkout_paper_only_never_records_income(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))  # isolate cybrus data dir
    receipt = money.price_receipt(2)
    assert receipt["checkout"]["status"].startswith("paper-only")
    assert receipt["checkout"]["gateway"] == "cybrus"
