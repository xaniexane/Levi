"""Hermetic tests for the RIEM organ (compost -> genome).

No network, no HOME writes, deterministic. RIEM emits proposals as data;
it must never write anything or auto-apply anything.
"""

import pytest

from levi.organs.reim import compost_failure
from levi.organs.riem import promote, format_proposals


def _compost(**overrides):
    base = compost_failure({
        "source": "deploy-pipeline",
        "what": "deployment timed out while waiting on the test step",
        "context": "runner queue was full during release window",
        "ts": "2026-09-15T19:00:00Z",
        "severity": "high",
    })
    base.update(overrides)
    return base


class TestPromotionThresholds:
    def test_high_severity_promotes_at_corroboration_1(self):
        proposals = promote([_compost()])
        assert len(proposals) == 1

    def test_corroborated_medium_promotes(self):
        c = _compost(severity="medium")
        c["corroboration"] = 2
        proposals = promote([c])
        assert len(proposals) == 1

    def test_single_medium_does_not_promote(self):
        c = _compost(severity="medium")  # corroboration 1
        assert promote([c]) == []

    def test_non_reusable_never_promotes(self):
        c = _compost(severity="high", reusable=False, compost_class="unknown")
        c["corroboration"] = 5
        assert promote([c]) == []

    def test_empty_input_empty_output(self):
        assert promote([]) == []


class TestProposalShape:
    def test_kind_mapping(self):
        cases = [
            ("resource-exhaustion", "guard-rule"),
            ("flaky-input", "guard-rule"),
            ("missing-guard", "guard-rule"),
            ("wrong-assumption", "checklist-item"),
        ]
        for cls, kind in cases:
            c = _compost(severity="high", compost_class=cls, reusable=True)
            (p,) = promote([c])
            assert p["kind"] == kind

    def test_proposal_fields(self):
        (p,) = promote([_compost()])
        assert p["kind"] == "guard-rule"
        assert isinstance(p["content"], str) and p["content"].strip()
        assert p["confidence"] == "high" or p["confidence"] in (
            "high", "medium", "low",
        )
        assert p["applied"] is False
        assert p["provenance"]["organ"] == "riem"
        assert p["provenance"]["compost_fingerprint"] == _compost()["fingerprint"]

    def test_confidence_ladder(self):
        high = _compost(severity="high")
        high["corroboration"] = 2
        (p,) = promote([high])
        assert p["confidence"] == "high"

        med = _compost(severity="medium")
        med["corroboration"] = 2
        (p,) = promote([med])
        assert p["confidence"] == "low"

    def test_determinism(self):
        c = _compost()
        assert promote([c]) == promote([c])

    def test_json_serializable(self):
        import json

        json.dumps(promote([_compost()]))


class TestProposalsAreDataNotWrites:
    def test_no_writes_to_home(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        promote([_compost()])
        assert list(tmp_path.iterdir()) == []

    def test_input_not_mutated(self):
        c = _compost()
        snapshot = dict(c)
        promote([c])
        assert c == snapshot

    def test_applied_always_false(self):
        for c_kwargs in (
            {"severity": "high"},
            dict(severity="medium", compost_class="wrong-assumption"),
        ):
            c = _compost(**c_kwargs)
            c["corroboration"] = 2
            c["reusable"] = True
            proposals = promote([c])
            assert all(p["applied"] is False for p in proposals)


class TestValidation:
    def test_non_list_rejected(self):
        with pytest.raises(ValueError):
            promote({"organ": "reim"})

    def test_malformed_compost_rejected(self):
        with pytest.raises(ValueError):
            promote([{"organ": "reim", "lesson": "x"}])

    def test_non_reim_organ_rejected(self):
        c = _compost()
        c["organ"] = "echo"
        with pytest.raises(ValueError):
            promote([c])

    def test_unknown_kind_rejected(self):
        c = _compost()
        c["compost_class"] = "mysterious-failure"
        with pytest.raises(ValueError):
            promote([c])

    def test_bad_corroboration_rejected(self):
        c = _compost()
        c["corroboration"] = 0
        with pytest.raises(ValueError):
            promote([c])


class TestFormat:
    def test_format_proposals(self):
        text = format_proposals(promote([_compost()]))
        assert "RIEM" in text
        assert "not writes" in text

    def test_format_rejects_malformed(self):
        with pytest.raises(ValueError):
            format_proposals([{"kind": "guard-rule"}])
        with pytest.raises(ValueError):
            format_proposals("nope")
