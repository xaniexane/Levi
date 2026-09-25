"""Tests for the Agent Workshop: inventory, blueprints, fail-closed
validation, and honestly-labeled local dry-runs."""

import json

import pytest

from levi.workshop import (
    ValidationError,
    compose_blueprint,
    dry_run,
    inventory,
    load_blueprint,
    save_blueprint,
    validate_blueprint,
)
from levi.workshop.dryrun import DRY_RUN_LABEL
from levi.workshop.inventory import (
    agent_ids,
    legion_role_names,
    organ_names,
    substrate_ids,
)


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def _good_kwargs():
    return dict(
        name="test-blue",
        agent=agent_ids()[0],
        specialist="reasoning",
        substrate="rules",
        organ="mandella",
        legion_role="receptionist",
        claims=["local-only", "reason"],
        twin_note="twin semantics unresolved",
    )


# ---------------------------------------------------------------------------
# inventory: derived from the real registries, never invented
# ---------------------------------------------------------------------------


def test_inventory_counts_positive():
    inv = inventory()
    counts = inv["counts"]
    assert counts["agents"] == 471
    assert counts["specialists"] == 9
    assert counts["substrates"] == 7
    assert counts["organs"] == 4
    assert counts["legion_roles"] == 7
    for key in ("agents", "specialists", "substrates", "organs", "legion_roles"):
        assert counts[key] > 0, key


def test_inventory_agents_are_registry_ids():
    ids = agent_ids()
    assert len(ids) == len(set(ids)) == 471
    assert ids[0] == "productivity-email-digest-01"


def test_inventory_substrates_carry_honest_status():
    from levi.packaging.roster_matrix import MODEL_TYPES

    assert MODEL_TYPES["own-cloud"].status == "planned"
    assert MODEL_TYPES["rules"].status == "real"
    assert MODEL_TYPES["local-brain"].status == "real-weak"
    for gated in ("groq", "gemini", "openai", "xai"):
        assert MODEL_TYPES[gated].status == "auth-gated"
    assert set(substrate_ids()) == set(MODEL_TYPES)


def test_inventory_organs_are_deny_closed_four():
    assert organ_names() == ["echoverse", "mandella", "reim", "riem"]


def test_inventory_legion_roles_derive_from_crew():
    from levi.legion.team import NEED_ROLE

    assert set(legion_role_names()) == set(NEED_ROLE.values())


# ---------------------------------------------------------------------------
# blueprints: deterministic, save/load round-trip with integrity check
# ---------------------------------------------------------------------------


def test_compose_is_deterministic():
    a = compose_blueprint(**_good_kwargs()).seal()
    b = compose_blueprint(**_good_kwargs()).seal()
    assert a.fingerprint == b.fingerprint
    assert len(a.fingerprint) == 64


def test_save_load_round_trip(home):
    bp = compose_blueprint(**_good_kwargs())
    path = save_blueprint(bp)
    assert path.exists()
    loaded = load_blueprint("test-blue")
    assert loaded.to_dict() == bp.to_dict()


def test_load_refuses_tampered_record(home):
    save_blueprint(compose_blueprint(**_good_kwargs()))
    path = home / "workshop" / "blueprints" / "test-blue.json"
    raw = json.loads(path.read_text())
    raw["substrate"] = "own-cloud"  # tamper with the spec
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="integrity check"):
        load_blueprint("test-blue")


def test_load_refuses_missing(home):
    with pytest.raises(FileNotFoundError):
        load_blueprint("no-such-blueprint")


# ---------------------------------------------------------------------------
# validation: fail closed
# ---------------------------------------------------------------------------


def test_validate_accepts_good_blueprint():
    bp = compose_blueprint(**_good_kwargs())
    checks = validate_blueprint(bp)
    assert len(checks) >= 6


def test_validate_refuses_unknown_agent():
    kw = _good_kwargs()
    kw["agent"] = "not-a-real-agent"
    with pytest.raises(ValidationError, match="unknown agent"):
        validate_blueprint(compose_blueprint(**kw))


def test_validate_refuses_unknown_specialist():
    kw = _good_kwargs()
    kw["specialist"] = "necromancer"
    with pytest.raises(ValidationError, match="unknown specialist"):
        validate_blueprint(compose_blueprint(**kw))


def test_validate_refuses_unknown_substrate():
    kw = _good_kwargs()
    kw["substrate"] = "skynet"
    with pytest.raises(ValidationError, match="unknown substrate"):
        validate_blueprint(compose_blueprint(**kw))


def test_validate_refuses_planned_own_cloud():
    kw = _good_kwargs()
    kw["substrate"] = "own-cloud"
    with pytest.raises(ValidationError, match="planned"):
        validate_blueprint(compose_blueprint(**kw))


def test_validate_refuses_unauthorized_cloud_provider():
    kw = _good_kwargs()
    kw["substrate"] = "groq"
    with pytest.raises(ValidationError, match="auth-gated"):
        validate_blueprint(compose_blueprint(**kw))


def test_validate_accepts_authorized_cloud_provider():
    kw = _good_kwargs()
    kw["substrate"] = "groq"
    bp = compose_blueprint(**kw)
    checks = validate_blueprint(bp, {"groq"})
    assert any("groq" in c for c in checks)


def test_validate_refuses_unknown_organ():
    kw = _good_kwargs()
    kw["organ"] = "stomach"
    with pytest.raises(ValidationError, match="unknown organ"):
        validate_blueprint(compose_blueprint(**kw))


def test_validate_refuses_unknown_legion_role():
    kw = _good_kwargs()
    kw["legion_role"] = "overlord"
    with pytest.raises(ValidationError, match="unknown Legion role"):
        validate_blueprint(compose_blueprint(**kw))


def test_validate_refuses_unsupported_capability_claim():
    kw = _good_kwargs()
    kw["claims"] = ["live-trading"]
    with pytest.raises(ValidationError, match="unsupported claim"):
        validate_blueprint(compose_blueprint(**kw))


def test_validate_refuses_claim_outside_specialist():
    # "delegate" is a supervisor capability, not reasoning's.
    kw = _good_kwargs()
    kw["claims"] = ["delegate"]
    with pytest.raises(ValidationError, match="unsupported claim"):
        validate_blueprint(compose_blueprint(**kw))


def test_validate_accepts_honest_labels():
    kw = _good_kwargs()
    kw["claims"] = ["local-only", "paper-only", "no-live-execution", "advisory"]
    validate_blueprint(compose_blueprint(**kw))


# ---------------------------------------------------------------------------
# dry-run: honestly labeled, no live effects
# ---------------------------------------------------------------------------


def test_dry_run_is_honestly_labeled():
    report = dry_run(compose_blueprint(**_good_kwargs()))
    assert report["label"] == DRY_RUN_LABEL
    assert "LOCAL-ONLY DRY RUN" in report["label"]
    assert report["live_effects"].startswith("none")
    assert report["would_assemble"]["agent"] == agent_ids()[0]


def test_dry_run_fails_closed_on_bad_blueprint():
    kw = _good_kwargs()
    kw["substrate"] = "own-cloud"
    with pytest.raises(ValidationError):
        dry_run(compose_blueprint(**kw))


def test_dry_run_marks_auth_gated_substrate():
    kw = _good_kwargs()
    kw["substrate"] = "gemini"
    report = dry_run(compose_blueprint(**kw), {"gemini"})
    assert (
        "authorization" in report["would_assemble"]["substrate_status"]
        or report["would_assemble"]["substrate_status"] == "auth-gated"
    )
    assert any("authorization" in s for s in report["simulated_steps"])


# ---------------------------------------------------------------------------
# nanobit + originals: Chauncey's order — the chain's micro-companion
# format and the eleven originals are workshop parts too
# ---------------------------------------------------------------------------


def test_inventory_nanobit_is_the_one_canonical_format():
    from levi.workshop.inventory import nanobit_ids

    inv = inventory()
    assert inv["counts"]["nanobit"] == 1
    assert nanobit_ids() == ["nano-bit"]
    part = inv["nanobit"][0]
    # minimal entry: id/name only
    assert set(part) <= {"id", "name", "note"}
    assert part["name"] == "NanoBitOperator"


def test_inventory_originals_are_the_eleven():
    from levi.dynasty.wave import __all__ as ELEVEN
    from levi.workshop.inventory import original_ids

    inv = inventory()
    assert inv["counts"]["originals"] == 11
    assert original_ids() == sorted(n.lower() for n in ELEVEN)
    # minimal entries: id/name only — no capabilities, no IP detail
    for part in inv["originals"]:
        assert set(part) == {"id", "name"}
    names = {p["name"] for p in inv["originals"]}
    assert names == set(ELEVEN)


def test_compose_deterministic_with_nanobit_and_original():
    kw = _good_kwargs()
    kw.update(nanobit="nano-bit", original="shellwright")
    a = compose_blueprint(**kw).seal()
    b = compose_blueprint(**kw).seal()
    assert a.fingerprint == b.fingerprint
    # the new fields are part of the seal, not decoration
    plain = compose_blueprint(**_good_kwargs()).seal()
    assert a.fingerprint != plain.fingerprint


def test_validate_accepts_nanobit_and_original():
    kw = _good_kwargs()
    kw.update(nanobit="nano-bit", original="shellwright")
    checks = validate_blueprint(compose_blueprint(**kw))
    assert any("nano-bit" in c for c in checks)
    assert any("shellwright" in c for c in checks)


def test_validate_extras_are_optional():
    # empty nanobit/original means absent — old blueprints still validate
    validate_blueprint(compose_blueprint(**_good_kwargs()))


def test_validate_refuses_unknown_nanobit():
    kw = _good_kwargs()
    kw["nanobit"] = "megabit"
    with pytest.raises(ValidationError, match="unknown nanobit"):
        validate_blueprint(compose_blueprint(**kw))


def test_validate_refuses_unknown_original():
    kw = _good_kwargs()
    kw["original"] = "not-an-original"
    with pytest.raises(ValidationError, match="unknown original"):
        validate_blueprint(compose_blueprint(**kw))


def test_save_load_round_trip_with_lineage(home):
    kw = _good_kwargs()
    kw.update(name="lineage-blue", nanobit="nano-bit", original="herald")
    bp = compose_blueprint(**kw)
    save_blueprint(bp)
    loaded = load_blueprint("lineage-blue")
    assert loaded.to_dict() == bp.to_dict()
    assert loaded.nanobit == "nano-bit"
    assert loaded.original == "herald"


def test_dry_run_reports_nanobit_and_original():
    kw = _good_kwargs()
    kw.update(nanobit="nano-bit", original="herald")
    report = dry_run(compose_blueprint(**kw))
    assert report["label"] == DRY_RUN_LABEL
    assert report["would_assemble"]["nanobit"] == "nano-bit"
    assert report["would_assemble"]["original"] == "herald"
    assert any("nanobit" in s for s in report["simulated_steps"])
    assert any("herald" in s for s in report["simulated_steps"])
