# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Herald rites tooling tests — diffs, upgrade plans, vocab lint, templates.

Hermetic: pure logic, no I/O at all. No network.
"""

from __future__ import annotations

import pytest

from levi.dynasty.wave.herald_rites import (
    EditionError,
    diff_manifests,
    lint_vocab,
    plan_upgrade,
    template,
    validate_skeleton,
)


def _manifest(version="1.0.0", rites=None, vocab=None, wares=None, name="X"):
    return {
        "name": name,
        "version": version,
        "rites": list(rites or []),
        "vocabulary": dict(vocab or {}),
        "wares": list(wares or []),
    }


# ---------------------------------------------------------------------
# diff_manifests
# ---------------------------------------------------------------------


class TestDiff:
    def test_identical_is_empty(self):
        old = _manifest(rites=["a", "b"], vocab={"x": "1"})
        new = _manifest(rites=["a", "b"], vocab={"x": "1"})
        diff = diff_manifests(old, new)
        assert diff["added_rites"] == []
        assert diff["removed_rites"] == []
        assert diff["changed_rites"] == []
        assert diff["added_vocab"] == {}
        assert diff["removed_vocab"] == {}
        assert diff["changed_vocab"] == {}
        assert diff["version_bump"] == "none"

    def test_rite_add_remove(self):
        old = _manifest(rites=["a"])
        new = _manifest(rites=["a", "b", "c"])
        diff = diff_manifests(old, new)
        assert diff["added_rites"] == ["b", "c"]
        assert diff["removed_rites"] == []
        diff = diff_manifests(new, old)
        assert diff["removed_rites"] == ["b", "c"]
        assert diff["added_rites"] == []

    def test_rite_changed_positionally(self):
        old = _manifest(rites=["a", "b"])
        new = _manifest(rites=["a", "B2"])
        diff = diff_manifests(old, new)
        assert diff["changed_rites"] == [{"index": 1, "from": "b", "to": "B2"}]
        assert diff["added_rites"] == []
        assert diff["removed_rites"] == []

    def test_vocab_diff(self):
        old = _manifest(vocab={"keep": "1", "drop": "2", "edit": "3"})
        new = _manifest(vocab={"keep": "1", "edit": "3b", "fresh": "4"})
        diff = diff_manifests(old, new)
        assert diff["added_vocab"] == {"fresh": "4"}
        assert diff["removed_vocab"] == {"drop": "2"}
        assert diff["changed_vocab"] == {"edit": {"from": "3", "to": "3b"}}

    def test_version_bumps(self):
        base = _manifest(version="1.2.3")
        assert (
            diff_manifests(base, _manifest(version="2.0.0"))["version_bump"] == "major"
        )
        assert (
            diff_manifests(base, _manifest(version="1.3.0"))["version_bump"] == "minor"
        )
        assert (
            diff_manifests(base, _manifest(version="1.2.4"))["version_bump"] == "patch"
        )
        assert (
            diff_manifests(base, _manifest(version="1.2.3"))["version_bump"] == "none"
        )
        assert (
            diff_manifests(base, _manifest(version="1.2.2"))["version_bump"]
            == "downgrade"
        )
        assert (
            diff_manifests(base, _manifest(version="soon"))["version_bump"] == "invalid"
        )
        assert (
            diff_manifests(_manifest(version="soon"), base)["version_bump"] == "invalid"
        )

    def test_missing_keys_tolerated(self):
        diff = diff_manifests({}, {})
        assert diff["added_rites"] == []
        assert diff["version_bump"] == "invalid"

    def test_bad_inputs(self):
        with pytest.raises(EditionError):
            diff_manifests("nope", {})
        with pytest.raises(EditionError):
            diff_manifests({}, None)
        bad_rites = _manifest()
        bad_rites["rites"] = "notalist"
        with pytest.raises(EditionError):
            diff_manifests(bad_rites, _manifest())
        bad_vocab = _manifest()
        bad_vocab["vocabulary"] = {"k": 5}
        with pytest.raises(EditionError):
            diff_manifests(bad_vocab, _manifest())


# ---------------------------------------------------------------------
# plan_upgrade
# ---------------------------------------------------------------------


class TestPlanUpgrade:
    def _pair(self):
        old = _manifest(
            version="1.0.0",
            rites=["keep", "old-rite", "drop-rite"],
            vocab={"keep": "1", "drop": "2", "edit": "3"},
        )
        new = _manifest(
            version="1.1.0",
            rites=["keep", "new-rite", "added-rite", "extra-rite"],
            vocab={"keep": "1", "edit": "3b", "fresh": "4"},
        )
        return old, new

    def test_order_remove_change_add_vocab_before_rites(self):
        old, new = self._pair()
        steps = plan_upgrade(old, new)
        actions = [s["action"] for s in steps]
        assert actions == [
            "remove_vocab",
            "change_vocab",
            "add_vocab",
            "change_rite",
            "change_rite",
            "add_rite",
            "set_version",
        ]
        assert [s["order"] for s in steps] == list(range(len(steps)))

    def test_step_details(self):
        old, new = self._pair()
        steps = plan_upgrade(old, new)
        by_action = {}
        for s in steps:
            by_action.setdefault(s["action"], []).append(s["detail"])
        assert by_action["remove_vocab"] == [{"term": "drop"}]
        assert by_action["change_vocab"] == [{"term": "edit", "from": "3", "to": "3b"}]
        assert by_action["add_vocab"] == [{"term": "fresh", "meaning": "4"}]
        assert by_action["change_rite"] == [
            {"index": 1, "from": "old-rite", "to": "new-rite"},
            {"index": 2, "from": "drop-rite", "to": "added-rite"},
        ]
        assert by_action["add_rite"] == [{"rite": "extra-rite"}]
        assert by_action["set_version"] == [
            {"from": "1.0.0", "to": "1.1.0", "bump": "minor"}
        ]

    def test_removed_rites(self):
        old = _manifest(rites=["keep", "gone-rite", "stale-rite"])
        new = _manifest(rites=["keep", "gone-rite"])
        diff = diff_manifests(old, new)
        assert diff["removed_rites"] == ["stale-rite"]
        assert diff["added_rites"] == []
        steps = plan_upgrade(old, new)
        assert [s["action"] for s in steps] == ["remove_rite"]

    def test_no_diff_no_steps(self):
        m = _manifest()
        assert plan_upgrade(m, _manifest()) == []

    def test_same_version_no_version_step(self):
        old = _manifest(version="1.0.0", rites=["a"])
        new = _manifest(version="1.0.0", rites=["a", "b"])
        actions = [s["action"] for s in plan_upgrade(old, new)]
        assert actions == ["add_rite"]

    def test_downgrade_still_planned(self):
        old = _manifest(version="2.0.0")
        new = _manifest(version="1.0.0")
        steps = plan_upgrade(old, new)
        assert steps[-1]["action"] == "set_version"
        assert steps[-1]["detail"]["bump"] == "downgrade"


# ---------------------------------------------------------------------
# lint_vocab — true names stay untranslated
# ---------------------------------------------------------------------


class TestLintVocab:
    PROTECTED = {"Omega", "Alpha", "Leviathan"}

    def test_exact_canon_passes(self):
        vocab = {"Omega": "the last word", "Alpha": "the first", "other": "x"}
        assert lint_vocab(vocab, self.PROTECTED) == []

    def test_case_variants_flagged(self):
        vocab = {"omega": "renamed", "OMEGA": "shouted", "Omega ": "spaced"}
        violations = lint_vocab(vocab, self.PROTECTED)
        assert {v["term"] for v in violations} == {"Omega"}
        assert {v["mapping"] for v in violations} == {"omega", "OMEGA", "Omega "}

    def test_punctuation_variant_flagged(self):
        assert lint_vocab({"O-m-e-g-a": "x"}, self.PROTECTED) == [
            {"term": "Omega", "mapping": "O-m-e-g-a"}
        ]

    def test_unrelated_keys_pass(self):
        assert lint_vocab({"wound": "x", "rite": "y"}, self.PROTECTED) == []

    def test_empty_protected_passes(self):
        assert lint_vocab({"omega": "x"}, set()) == []

    def test_protected_as_list(self):
        assert lint_vocab({"alpha": "x"}, ["Alpha"]) == [
            {"term": "Alpha", "mapping": "alpha"}
        ]

    def test_semantic_translation_is_invisible(self):
        # Documented limit: meaning-level renames are not spelling
        # variants, so the linter cannot see them.
        assert lint_vocab({"the-end": "x"}, {"Omega"}) == []

    def test_violation_shape(self):
        violations = lint_vocab({"leviathan": "x"}, self.PROTECTED)
        assert violations == [{"term": "Leviathan", "mapping": "leviathan"}]
        for v in violations:
            assert set(v) == {"term", "mapping"}

    def test_bad_inputs(self):
        with pytest.raises(EditionError):
            lint_vocab("notadict", self.PROTECTED)
        with pytest.raises(EditionError):
            lint_vocab({}, "notaset")
        with pytest.raises(EditionError):
            lint_vocab({}, {""})


# ---------------------------------------------------------------------
# template / validate_skeleton
# ---------------------------------------------------------------------


class TestTemplate:
    def test_all_sectors(self):
        for sector in ("research", "crime", "custom"):
            manifest = template(sector)
            assert validate_skeleton(manifest) == []
            assert set(manifest) >= {"name", "version", "rites", "vocabulary", "wares"}
            assert manifest["version"] == "0.1.0"

    def test_sector_flavor_differs(self):
        assert template("research")["name"] != template("crime")["name"]

    def test_mutating_template_does_not_leak(self):
        manifest = template("custom")
        manifest["rites"].append("sneaky")
        manifest["vocabulary"]["evil"] = "x"
        fresh = template("custom")
        assert "sneaky" not in fresh["rites"]
        assert "evil" not in fresh["vocabulary"]

    def test_bad_sector(self):
        for bad in ("", "RESEARCH", "finance", None, 42):
            with pytest.raises(EditionError):
                template(bad)


class TestValidateSkeleton:
    def test_valid(self):
        assert validate_skeleton(template("research")) == []

    def test_missing_fields(self):
        violations = validate_skeleton({"name": "x"})
        assert {v["field"] for v in violations} == {
            "version",
            "rites",
            "vocabulary",
            "wares",
        }
        assert all(v["problem"] == "missing" for v in violations)

    def test_empty_fields(self):
        manifest = _manifest(rites=[], vocab={}, wares=[], name="  ", version="")
        violations = validate_skeleton(manifest)
        assert {v["field"] for v in violations} == {
            "name",
            "version",
            "rites",
            "vocabulary",
            "wares",
        }
        assert all(v["problem"] == "empty" for v in violations)

    def test_wrong_types(self):
        manifest = {
            "name": 5,
            "version": "1.0.0",
            "rites": "notalist",
            "vocabulary": ["notadict"],
            "wares": {"notalist": True},
        }
        violations = validate_skeleton(manifest)
        assert {v["field"] for v in violations} == {
            "name",
            "rites",
            "vocabulary",
            "wares",
        }
        assert all(v["problem"] == "wrong_type" for v in violations)

    def test_non_dict(self):
        with pytest.raises(EditionError):
            validate_skeleton("manifest")
        with pytest.raises(EditionError):
            validate_skeleton(None)

    def test_violation_shape(self):
        violations = validate_skeleton({})
        assert violations and all(set(v) == {"field", "problem"} for v in violations)
