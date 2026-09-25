"""Hermetic tests for the REIM organ (failure composting).

No network, no HOME writes, deterministic.
"""

import pytest

from levi.organs.reim import compost_failure, format_compost


def _record(**overrides):
    base = {
        "source": "deploy-pipeline",
        "what": "deployment timed out while waiting on the test step",
        "context": "runner queue was full during release window",
        "ts": "2026-09-15T19:00:00Z",
        "severity": "high",
    }
    base.update(overrides)
    return base


class TestCompostClasses:
    def test_resource_exhaustion(self):
        c = compost_failure(_record())
        assert c["compost_class"] == "resource-exhaustion"
        assert c["reusable"] is True

    def test_flaky_input(self):
        c = compost_failure(
            _record(
                what="job failed: malformed CSV in upload payload", severity="medium"
            )
        )
        assert c["compost_class"] == "flaky-input"
        assert c["reusable"] is True

    def test_wrong_assumption(self):
        c = compost_failure(
            _record(
                what="we assumed the staging URL in production config",
                severity="medium",
            )
        )
        assert c["compost_class"] == "wrong-assumption"
        assert c["reusable"] is True

    def test_missing_guard(self):
        c = compost_failure(
            _record(what="crash: unvalidated token passed to parser", severity="high")
        )
        assert c["compost_class"] == "missing-guard"
        assert c["reusable"] is True

    def test_unknown_not_reusable(self):
        c = compost_failure(
            _record(
                what="it just stopped working, no logs captured",
                context="nothing in the logs",
                severity="high",
            )
        )
        assert c["compost_class"] == "unknown"
        assert c["reusable"] is False

    def test_low_severity_not_reusable(self):
        c = compost_failure(
            _record(what="timed out once on a flaky network", severity="low")
        )
        assert c["compost_class"] == "resource-exhaustion"
        assert c["reusable"] is False


class TestRecordShape:
    def test_all_keys_present(self):
        c = compost_failure(_record())
        for key in (
            "organ",
            "source",
            "what",
            "context",
            "ts",
            "severity",
            "compost_class",
            "lesson",
            "inverse_map",
            "reusable",
            "corroboration",
            "fingerprint",
            "provenance",
        ):
            assert key in c, key
        assert c["organ"] == "reim"
        assert c["corroboration"] == 1
        assert isinstance(c["lesson"], str) and c["lesson"].strip()
        assert isinstance(c["inverse_map"], str) and c["inverse_map"].strip()
        assert c["provenance"]["source"] == "deploy-pipeline"

    def test_determinism(self):
        assert compost_failure(_record()) == compost_failure(_record())

    def test_json_serializable(self):
        import json

        json.dumps(compost_failure(_record()))


class TestMalformedRecords:
    @pytest.mark.parametrize(
        "bad",
        [
            None,
            "not-a-dict",
            [],
            42,
        ],
    )
    def test_non_dict_rejected(self, bad):
        with pytest.raises(ValueError):
            compost_failure(bad)

    def test_missing_keys_rejected(self):
        r = _record()
        del r["what"]
        with pytest.raises(ValueError):
            compost_failure(r)

    @pytest.mark.parametrize("key", ["source", "what", "context", "ts"])
    def test_empty_string_rejected(self, key):
        with pytest.raises(ValueError):
            compost_failure(_record(**{key: "   "}))

    def test_non_string_rejected(self):
        with pytest.raises(ValueError):
            compost_failure(_record(what=123))

    def test_bad_severity_rejected(self):
        with pytest.raises(ValueError):
            compost_failure(_record(severity="catastrophic"))


class TestFormat:
    def test_format_compost(self):
        text = format_compost(compost_failure(_record()))
        assert "REIM" in text
        assert "resource-exhaustion" in text
        assert "yes" in text  # reusable

    def test_format_rejects_malformed(self):
        with pytest.raises(ValueError):
            format_compost({"lesson": "x"})
        with pytest.raises(ValueError):
            format_compost("nope")
