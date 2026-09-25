"""Hermetic tests for the LEVI Galaxy packaging + namespacing layer.

No network, no HOME writes (all manifests live in tmp_path), no randomness:
every assertion is deterministic.
"""

import json

import pytest

from levi.galaxy import (
    Collision,
    Manifest,
    NamespaceError,
    PackageError,
    RegistryEntry,
    Resolution,
    check_collision,
    load_manifest,
    parse_namespaced,
    parse_version,
    resolve,
    to_namespaced,
    validate_manifest,
)


def _manifest(**over):
    base = {
        "name": "cleaner",
        "version": "1.2.3",
        "kind": "skill",
        "description": "Cleans up disk clutter.",
        "author": "com.acme",
        "entry_points": {"clean": "run.py"},
        "capabilities": ["fs.clean.*"],
        "permissions": {
            "network": False,
            "fs": ["data"],
            "subprocess": False,
        },
        "min_levi_version": "0.9.0",
    }
    base.update(over)
    return base


def _write_manifest(tmp_path, data, script="run.py"):
    (tmp_path / "levi-skill.json").write_text(json.dumps(data), encoding="utf-8")
    if script is not None:
        (tmp_path / script).write_text("# entry\n", encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------- load_manifest


def test_load_valid_manifest(tmp_path):
    d = _write_manifest(tmp_path, _manifest())
    m = load_manifest(d)
    assert isinstance(m, Manifest)
    assert m.name == "cleaner"
    assert m.version == "1.2.3"
    assert m.kind == "skill"
    assert m.namespaced_id == "com.acme.cleaner"
    assert m.entry_points == {"clean": "run.py"}
    assert m.capabilities == ("fs.clean.*",)
    assert m.permissions == {"network": False, "fs": ["data"], "subprocess": False}
    assert m.entry_path("clean") == d / "run.py"


def test_load_manifest_module_target(tmp_path):
    data = _manifest(entry_points={"clean": "acme.cleaner:run"})
    _write_manifest(tmp_path, data, script=None)
    m = load_manifest(tmp_path)
    assert m.entry_points == {"clean": "acme.cleaner:run"}
    with pytest.raises(PackageError):
        m.entry_path("clean")  # module targets have no filesystem path


def test_load_manifest_missing_file(tmp_path):
    with pytest.raises(PackageError, match="not found"):
        load_manifest(tmp_path)


def test_load_manifest_invalid_json(tmp_path):
    (tmp_path / "levi-skill.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(PackageError, match="not valid JSON"):
        load_manifest(tmp_path)


def test_load_manifest_refuses_missing_script(tmp_path):
    data = _manifest(entry_points={"clean": "missing.py"})
    _write_manifest(tmp_path, data, script=None)
    with pytest.raises(PackageError, match="does not exist"):
        load_manifest(tmp_path)


# ------------------------------------------------------- validate_manifest


def test_validate_valid_manifest_has_no_errors():
    assert validate_manifest(_manifest()) == []


@pytest.mark.parametrize(
    "field",
    [
        "name",
        "version",
        "kind",
        "description",
        "author",
        "entry_points",
        "capabilities",
        "permissions",
        "min_levi_version",
    ],
)
def test_missing_required_field_refused(field):
    data = _manifest()
    del data[field]
    errors = validate_manifest(data)
    assert any(field in e for e in errors), errors


@pytest.mark.parametrize(
    "bad",
    ["latest", "v1", "1.0.0.0", "", "1..0", "one.two.three", 123, None],
)
def test_bad_version_refused(bad):
    errors = validate_manifest(_manifest(version=bad))
    assert any("version" in e for e in errors), errors


@pytest.mark.parametrize(
    "good", ["1", "1.0", "1.0.0", "2.3.4-alpha.1", "1.0.0+build.7"]
)
def test_lenient_versions_accepted(good):
    assert validate_manifest(_manifest(version=good)) == []


def test_unknown_kind_refused():
    errors = validate_manifest(_manifest(kind="plugin"))
    assert any("kind" in e for e in errors), errors


def test_unknown_field_refused():
    errors = validate_manifest(_manifest(extra="nope"))
    assert any("unknown field" in e for e in errors), errors


@pytest.mark.parametrize("bad", ["UPPER", "has space", "bad!char", "", 42])
def test_bad_name_refused(bad):
    errors = validate_manifest(_manifest(name=bad))
    assert any("name" in e for e in errors), errors


@pytest.mark.parametrize(
    "bad",
    [
        "no-dot-and-unregistered",
        "UPPER.com",
        "bad char.com",
        ".leading.com",
        "trailing.com.",
        "double..dot",
        "",
        42,
    ],
)
def test_bad_author_refused(bad):
    errors = validate_manifest(_manifest(author=bad))
    assert any("author" in e for e in errors), errors


def test_registered_handle_author_accepted():
    data = _manifest(author="chauncey")
    assert validate_manifest(data, registered_handles={"chauncey"}) == []
    # ...but refused when the handle is not registered
    assert validate_manifest(data) != []


def test_empty_description_refused():
    assert validate_manifest(_manifest(description="   ")) != []


@pytest.mark.parametrize(
    "eps",
    [
        {"BadVerb": "run.py"},  # verb must be lowercase-led
        {"clean": ""},  # empty target
        {"clean": "not a module: also bad"},  # malformed module:function
        {"clean": "/abs/path.py"},  # absolute path escapes package
        {"clean": "../escape.py"},  # parent traversal
        {"clean": "~/home.py"},  # home expansion
        {"clean": 42},
        {},  # at least one verb required
    ],
)
def test_bad_entry_points_refused(eps):
    errors = validate_manifest(_manifest(entry_points=eps))
    assert any("entry_points" in e for e in errors), errors


def test_bad_capabilities_refused():
    assert validate_manifest(_manifest(capabilities="not-a-list")) != []
    assert validate_manifest(_manifest(capabilities=["ok.*", "bad cap"])) != []
    assert validate_manifest(_manifest(capabilities=[""])) != []


def test_permissions_shape_refused():
    assert validate_manifest(_manifest(permissions={})) != []  # missing keys
    bad = {"network": "yes", "fs": [], "subprocess": False}
    assert any("network" in e for e in validate_manifest(_manifest(permissions=bad)))
    bad = {"network": False, "fs": ["/abs"], "subprocess": False}
    assert any("fs" in e for e in validate_manifest(_manifest(permissions=bad)))
    bad = {"network": False, "fs": ["../x"], "subprocess": False}
    assert any("fs" in e for e in validate_manifest(_manifest(permissions=bad)))
    bad = {"network": False, "fs": [], "subprocess": False, "root": True}
    assert any(
        "unknown key" in e for e in validate_manifest(_manifest(permissions=bad))
    )


def test_bad_min_levi_version_refused():
    errors = validate_manifest(_manifest(min_levi_version="soon"))
    assert any("min_levi_version" in e for e in errors), errors


def test_validate_non_dict_refused():
    assert validate_manifest(["not", "a", "dict"]) != []


def test_parse_version_ordering():
    assert parse_version("1.0")[0] == (1, 0, 0)
    assert parse_version("2.0.0")[0] > parse_version("1.9.9")[0]
    with pytest.raises(PackageError):
        parse_version("nope")


# ------------------------------------------------------------- namespacing


def test_to_namespaced_roundtrip():
    nid = to_namespaced("com.acme", "cleaner")
    assert nid == "com.acme.cleaner"
    assert parse_namespaced(nid) == ("com.acme", "cleaner")


def test_to_namespaced_last_dot_convention():
    # Reverse-DNS authors are dotted; the name is the trailing segment.
    assert parse_namespaced("org.example.deep.cleaner") == (
        "org.example.deep",
        "cleaner",
    )


def test_to_namespaced_registered_handle():
    assert to_namespaced("chauncey", "cleaner", {"chauncey"}) == "chauncey.cleaner"


@pytest.mark.parametrize(
    "author,name",
    [
        ("UPPER.com", "cleaner"),
        ("com.acme", "UPPER"),
        ("bad char.com", "cleaner"),
        ("", "cleaner"),
        ("com.acme", ""),
        ("unregistered", "cleaner"),
    ],
)
def test_to_namespaced_refuses_bad_parts(author, name):
    with pytest.raises(NamespaceError):
        to_namespaced(author, name)


@pytest.mark.parametrize(
    "bad",
    ["nodot", "", ".leading", "trailing.", "BAD.CHARS!"],
)
def test_parse_namespaced_refuses(bad):
    with pytest.raises(NamespaceError):
        parse_namespaced(bad)


# ------------------------------------------------------ collision detection


def _registry():
    return {
        "com.acme.cleaner": RegistryEntry("com.acme.cleaner", "com.acme", "1.2.3"),
        "org.beta.tool": {"author": "org.beta", "version": "0.1.0"},
        "io.gamma.svc": ("io.gamma", "2.0.0"),
    }


def test_no_collision_for_fresh_id():
    assert check_collision(_registry(), "com.new.thing") is None


def test_same_id_same_author_same_version_no_collision():
    got = check_collision(
        _registry(),
        "com.acme.cleaner",
        candidate_author="com.acme",
        candidate_version="1.2.3",
    )
    assert got is None


def test_author_mismatch_collision():
    # Candidate manifest claims author "evil.com" but registers the id that
    # belongs to com.acme — classic impersonation attempt.
    got = check_collision(
        _registry(),
        "com.acme.cleaner",
        candidate_author="evil.com",
        candidate_version="9.9.9",
    )
    assert isinstance(got, Collision)
    assert got.kind == "author_mismatch"
    assert got.existing_author == "com.acme"
    assert got.candidate_author == "evil.com"
    assert "already claimed" in got.describe()


def test_version_conflict_collision():
    got = check_collision(
        _registry(),
        "org.beta.tool",
        candidate_author="org.beta",
        candidate_version="0.2.0",
    )
    assert isinstance(got, Collision)
    assert got.kind == "version_conflict"
    assert got.existing_version == "0.1.0"
    assert got.candidate_version == "0.2.0"
    assert "already registered" in got.describe()


def test_registry_accepts_list_of_entries():
    entries = [RegistryEntry("com.acme.cleaner", "com.acme", "1.2.3")]
    assert check_collision(entries, "com.other.x") is None
    got = check_collision(entries, "com.acme.cleaner", candidate_version="2.0.0")
    assert got is not None and got.kind == "version_conflict"


# ------------------------------------------------------------------ resolve


def test_resolve_fresh_install():
    cand = RegistryEntry("com.new.thing", "com.new", "1.0.0")
    r = resolve(None, cand)
    assert isinstance(r, Resolution)
    assert r.allowed and r.action == "install"


def test_resolve_author_mismatch_refused():
    existing = RegistryEntry("com.acme.cleaner", "com.acme", "1.2.3")
    cand = RegistryEntry("com.acme.cleaner", "evil.com", "1.2.3")
    r = resolve(existing, cand)
    assert not r.allowed and r.action == "refuse"
    assert "evil.com" in r.reason


def test_resolve_semver_upgrade_allowed():
    existing = RegistryEntry("com.acme.cleaner", "com.acme", "1.2.3")
    for newer in ("1.2.4", "1.3.0", "2.0.0"):
        cand = RegistryEntry("com.acme.cleaner", "com.acme", newer)
        r = resolve(existing, cand)
        assert r.allowed and r.action == "upgrade", newer


def test_resolve_prerelease_upgrade_allowed():
    existing = RegistryEntry("com.acme.cleaner", "com.acme", "1.2.3-alpha")
    cand = RegistryEntry("com.acme.cleaner", "com.acme", "1.2.3")
    r = resolve(existing, cand)
    assert r.allowed and r.action == "upgrade"


def test_resolve_equal_version_refused():
    existing = RegistryEntry("com.acme.cleaner", "com.acme", "1.2.3")
    cand = RegistryEntry("com.acme.cleaner", "com.acme", "1.2.3")
    r = resolve(existing, cand)
    assert not r.allowed and r.action == "refuse"
    assert "already installed" in r.reason


def test_resolve_downgrade_refused():
    existing = RegistryEntry("com.acme.cleaner", "com.acme", "2.0.0")
    cand = RegistryEntry("com.acme.cleaner", "com.acme", "1.9.9")
    r = resolve(existing, cand)
    assert not r.allowed and r.action == "refuse"
    assert "downgrade" in r.reason


def test_resolve_release_does_not_lose_to_prerelease():
    existing = RegistryEntry("com.acme.cleaner", "com.acme", "1.2.3")
    cand = RegistryEntry("com.acme.cleaner", "com.acme", "1.2.4-beta")
    r = resolve(existing, cand)
    # candidate is numerically higher (1.2.4 > 1.2.3): still an upgrade
    assert r.allowed and r.action == "upgrade"
    cand2 = RegistryEntry("com.acme.cleaner", "com.acme", "1.2.3-beta")
    r2 = resolve(existing, cand2)
    assert not r2.allowed  # same numbers, pre-release < release


def test_resolve_mismatched_ids_refused():
    existing = RegistryEntry("com.acme.cleaner", "com.acme", "1.2.3")
    cand = RegistryEntry("com.acme.other", "com.acme", "1.2.3")
    r = resolve(existing, cand)
    assert not r.allowed and r.action == "refuse"


def test_resolve_unknown_policy_refused():
    cand = RegistryEntry("com.new.thing", "com.new", "1.0.0")
    with pytest.raises(NamespaceError):
        resolve(None, cand, policy="yolo")


def test_resolve_bad_version_refused():
    existing = RegistryEntry("com.acme.cleaner", "com.acme", "garbage")
    cand = RegistryEntry("com.acme.cleaner", "com.acme", "1.0.0")
    with pytest.raises(NamespaceError):
        resolve(existing, cand)
