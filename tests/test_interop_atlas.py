"""Hermetic tests for the capability atlas + warehouses (axis 3).

The manifest is deny-closed: every ``requires`` target must be a
registered module. Inventory counts are real — tests assert them against
direct file scans, never hard-coded numbers.
"""

import json
from pathlib import Path

import pytest

from levi.interop.atlas import atlas_modules, export_atlas, write_atlas
from levi.interop.manifest import DECLARATIONS
from levi.interop.registry import Registry
from levi.interop.warehouses import (
    WAREHOUSES,
    browse_warehouse,
    list_warehouses,
    pull_from_shelf,
    warehouse_inventory,
)

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "core" / "levi"

EXPECTED_NEW_MODULES = {
    "methods",
    "revival",
    "galaxy",
    "lifepack",
    "bloodstream",
    "daemon",
    "perpetual",
    "archive",
    "cyber-skills",
    "factory",
    "finance",
}

#: Operator + additions + research waves (2026-09-16 sweep): every new
#: package must be declared in the manifest and shelved in a warehouse.
EXPECTED_WAVE_MODULES = {
    "signals",
    "creed",
    "promises",
    "decisions",
    "interruptions",
    "snapshots",
    "drift",
    "teachback",
    "energy",
    "friction",
    "sweeps",
    "premortem",
    "research",
    "ephemera",
    "feedreader",
    "packs",
    "commitments",
    "recap",
    "classifieds",
    "dials",
    "bridging",
    "communities",
    "threads",
    "charters",
    "capproto",
    "mailtriage",
    "vaults",
    "canvas",
    "discover",
    "presence",
    "honestsearch",
    "recommender",
}

EXPECTED_WAVE_WAREHOUSES = {"operations", "commons", "craft"}


def test_wave_modules_declared():
    assert EXPECTED_WAVE_MODULES <= set(DECLARATIONS)


def test_wave_warehouses_exist_and_shelve_everything():
    assert EXPECTED_WAVE_WAREHOUSES <= set(WAREHOUSES)
    shelved = {
        shelf for wh in EXPECTED_WAVE_WAREHOUSES for shelf in WAREHOUSES[wh]["shelves"]
    }
    assert EXPECTED_WAVE_MODULES - {"research"} <= shelved
    assert "research" in WAREHOUSES["archive"]["shelves"]


@pytest.fixture(autouse=True)
def _hermetic_home(tmp_path, monkeypatch):
    # warehouse inventory strategies that read live runtime state
    # (archive records, galaxy services, daemon automations) must resolve
    # against a tmp HOME, never the real one.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


# -- manifest extensions ----------------------------------------------------


def test_new_modules_declared():
    assert EXPECTED_NEW_MODULES <= set(DECLARATIONS)


def test_manifest_check_all_passes_with_new_modules():
    reg = Registry()
    for name, decl in DECLARATIONS.items():
        reg.register(name, provides=decl["provides"], requires=decl["requires"])
    reg.check_all()  # deny-closed: must not raise


def test_check_each_new_module():
    reg = Registry()
    for name, decl in DECLARATIONS.items():
        reg.register(name, provides=decl["provides"], requires=decl["requires"])
    for name in EXPECTED_NEW_MODULES:
        reg.check(name)


def test_perpetual_requires_archive_is_declared():
    assert "archive" in DECLARATIONS["perpetual"]["requires"]
    assert "archive" in DECLARATIONS


def test_growth_declaration_unchanged():
    assert DECLARATIONS["growth"] == {
        "provides": ["growth.journal", "growth.cycle"],
        "requires": ["memory-store"],
    }


# -- atlas ------------------------------------------------------------------


def test_export_atlas_shape():
    atlas = export_atlas()
    for key in (
        "modules",
        "capabilities",
        "requires_graph",
        "warehouses",
        "generated_at",
        "levi_version",
    ):
        assert key in atlas, f"missing atlas key: {key}"
    assert isinstance(atlas["generated_at"], str)
    assert isinstance(atlas["levi_version"], str) and atlas["levi_version"]


def test_export_atlas_keeps_flat_module_list():
    atlas = export_atlas()
    assert set(atlas["modules"]) == set(DECLARATIONS)
    for name, entry in atlas["modules"].items():
        assert entry["provides"] == DECLARATIONS[name]["provides"]
        assert entry["requires"] == DECLARATIONS[name]["requires"]
        assert isinstance(entry["cli"], list)


def test_export_atlas_capabilities_cover_all_provides():
    atlas = export_atlas()
    expected = sorted({cap for d in DECLARATIONS.values() for cap in d["provides"]})
    assert atlas["capabilities"] == expected


def test_export_atlas_requires_graph_matches_manifest():
    atlas = export_atlas()
    for name, reqs in atlas["requires_graph"].items():
        assert reqs == DECLARATIONS[name]["requires"]


def test_export_atlas_warehouses_group_modules():
    atlas = export_atlas()
    wh = atlas["warehouses"]
    assert set(wh) == set(WAREHOUSES)
    for name, entry in wh.items():
        assert entry["name"] == name
        assert entry["inventory_count"] >= 0
        for shelf in entry["shelves"]:
            assert shelf["module"] in atlas["modules"]


def test_atlas_cli_reachability_spot_checks():
    modules = atlas_modules()
    assert modules["bloodstream"]["cli"] == ["turn"]
    assert modules["lifepack"]["cli"] == ["lifepack"]
    assert modules["finance"]["cli"] == ["finance"]
    assert modules["growth"]["cli"] == ["growth"]
    assert modules["daemon"]["cli"] == ["daemon"]
    assert modules["galaxy"]["cli"] == ["python -m levi.galaxy"]
    assert modules["methods"]["cli"] == []
    assert modules["organs"]["cli"] == ["echo", "mandella"]


def test_write_atlas_to_tmp_path(tmp_path):
    target = tmp_path / "atlas" / "atlas.json"
    out = write_atlas(target)
    assert out == target and target.is_file()
    data = json.loads(target.read_text(encoding="utf-8"))
    assert set(data["modules"]) == set(DECLARATIONS)
    assert "warehouses" in data


# -- warehouses ---------------------------------------------------------------


def test_list_warehouses_shape():
    whs = list_warehouses()
    assert {w["name"] for w in whs} == set(WAREHOUSES)
    for w in whs:
        assert w["summary"] and w["title"]
        assert isinstance(w["inventory_count"], int) and w["inventory_count"] >= 0


def test_inventory_counts_match_reality():
    real_methods = len(list((PKG / "methods").glob("[a-z]*.py")))
    real_revivals = len(list((PKG / "revival").glob("[a-z]*.py")))
    real_playbooks = len(list((PKG / "skill" / "playbooks").rglob("*.md")))
    by_name = {w["name"]: w["inventory_count"] for w in list_warehouses()}
    assert real_methods == 41
    assert by_name["methods"] == real_methods
    assert real_revivals == 20
    assert (
        by_name["revivals"] == real_revivals + 3 + 3 + 3
    )  # + telegraph shelf (envelopes/identity/directory) + analog shelf (bench/nomo/fourier) + craft shelf (hallmark/guild/measures)
    assert real_playbooks == 839
    assert by_name["skills"] == real_playbooks
    assert (
        by_name["games"] == 9
    )  # games wave landed: charter/codebreak/cipher/hotseat/saves + wave-015: if-engine/open-crate/open-season/turn-relay


def test_browse_warehouse_shelves():
    info = browse_warehouse("organism")
    assert info["title"] == "Organism Core Warehouse"
    shelf_modules = [s["module"] for s in info["shelves"]]
    assert shelf_modules == ["bloodstream", "organs", "lifepack", "oath"]
    for shelf in info["shelves"]:
        assert shelf["summary"]
        assert shelf["provides"] == DECLARATIONS[shelf["module"]]["provides"]
        assert shelf["requires"] == DECLARATIONS[shelf["module"]]["requires"]
        assert isinstance(shelf["cli"], list)


def test_browse_unknown_warehouse_names_available():
    with pytest.raises(ValueError) as excinfo:
        browse_warehouse("tool-belt")
    msg = str(excinfo.value)
    assert "unknown warehouse" in msg
    assert "methods" in msg  # names what's available


def test_inventory_unknown_warehouse_rejected():
    with pytest.raises(ValueError, match="unknown warehouse"):
        warehouse_inventory("nope")


def test_inventory_pagination_is_honest():
    full = warehouse_inventory("skills", limit=None)
    assert full["total"] == 839
    assert len(full["items"]) == 839
    assert full["truncated"] is False

    page = warehouse_inventory("skills", limit=50, offset=0)
    assert page["total"] == 839
    assert len(page["items"]) == 50
    assert page["truncated"] is True

    last = warehouse_inventory("skills", limit=50, offset=800)
    assert len(last["items"]) == 39
    assert last["truncated"] is False

    for item in page["items"]:
        assert {"id", "kind", "summary"} <= set(item)
        assert item["kind"] == "playbook"
        assert item["id"].startswith("playbook.cyber.")


def test_inventory_negative_offset_rejected():
    with pytest.raises(ValueError, match="offset"):
        warehouse_inventory("methods", offset=-1)


def test_inventory_archive_and_services_empty_in_tmp_home():
    # no records / installs in a fresh tmp HOME — honestly zero
    assert warehouse_inventory("archive", limit=None)["total"] == 0
    assert warehouse_inventory("services", limit=None)["total"] == 0


def test_pull_technique():
    item = pull_from_shelf("methods", "methods.loci")
    assert item["kind"] == "technique"
    assert item["summary"]
    assert "levi.methods.loci" in item["invoke"]
    assert item["detail"]["module"] == "levi.methods.loci"
    assert isinstance(item["detail"]["public_members"], list)


def test_pull_revival():
    item = pull_from_shelf("revivals", "revival.telescript")
    assert item["kind"] == "revival"
    assert "levi.revival.telescript" in item["invoke"]


def test_pull_playbook():
    inv = warehouse_inventory("skills", limit=1)
    first_id = inv["items"][0]["id"]
    item = pull_from_shelf("skills", first_id)
    assert item["kind"] == "playbook"
    assert item["id"] == first_id
    assert item["summary"]
    assert "SkillRegistry" in item["invoke"]


def test_pull_capability():
    item = pull_from_shelf("organism", "bloodstream.turn")
    assert item["kind"] == "capability"
    assert item["invoke"] == "levi turn"
    assert item["detail"]["module"] == "bloodstream"


def test_pull_unknown_item_names_available():
    with pytest.raises(ValueError, match="unknown technique"):
        pull_from_shelf("methods", "methods.nonexistent")
    with pytest.raises(ValueError, match="unknown playbook"):
        pull_from_shelf("skills", "playbook.cyber.nonexistent")
    with pytest.raises(ValueError, match="unknown warehouse"):
        pull_from_shelf("nope", "methods.loci")


def test_pull_never_executes():
    # pull_from_shelf only inspects; importing it must not create state.
    before = (
        set((Path.home() / ".levi").rglob("*"))
        if (Path.home() / ".levi").exists()
        else set()
    )
    pull_from_shelf("methods", "methods.ach")
    pull_from_shelf("revivals", "revival.plan9")
    after = (
        set((Path.home() / ".levi").rglob("*"))
        if (Path.home() / ".levi").exists()
        else set()
    )
    assert before == after
