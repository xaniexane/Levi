"""Wiring tests: REIM corroboration merging + failure-to-genome pipeline.

No network, no HOME writes, deterministic.

Covers ONLY the wiring between the organs — ``corroborate``,
``compost_batch``, and ``failure_to_genome``. Unit coverage of
``compost_failure`` and ``promote`` (classes, lessons, thresholds,
validation) lives in test_organs_reim.py and test_organs_riem.py and is
not duplicated here.
"""

import pytest

from levi.organs.reim import compost_failure, compost_batch, corroborate
from levi.organs.riem import failure_to_genome, promote


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


class TestCorroborate:
    def test_increments_and_takes_newer_ts(self):
        first = compost_failure(_record(ts="2026-09-15T19:00:00Z"))
        second = compost_failure(_record(ts="2026-09-16T08:30:00Z"))
        merged = corroborate(first, second)
        assert merged["corroboration"] == 2
        assert merged["fingerprint"] == first["fingerprint"] == second["fingerprint"]
        assert merged["ts"] == "2026-09-16T08:30:00Z"
        assert merged["provenance"]["merged_from"] == 2

    def test_reversed_order_still_takes_newer_ts(self):
        older = compost_failure(_record(ts="2026-09-15T19:00:00Z"))
        newer = compost_failure(_record(ts="2026-09-16T08:30:00Z"))
        merged = corroborate(newer, older)
        assert merged["ts"] == "2026-09-16T08:30:00Z"

    def test_repeated_merges_accumulate(self):
        acc = compost_failure(_record())
        for _ in range(2):
            acc = corroborate(acc, compost_failure(_record()))
        assert acc["corroboration"] == 3
        assert acc["provenance"]["merged_from"] == 3

    def test_inputs_are_not_mutated(self):
        first = compost_failure(_record(ts="2026-09-15T19:00:00Z"))
        second = compost_failure(_record(ts="2026-09-16T08:30:00Z"))
        corroborate(first, second)
        assert first["corroboration"] == 1
        assert first["ts"] == "2026-09-15T19:00:00Z"
        assert "merged_from" not in first["provenance"]

    def test_fingerprint_mismatch_raises(self):
        first = compost_failure(_record())
        other = compost_failure(_record(what="something completely different happened"))
        assert first["fingerprint"] != other["fingerprint"]
        with pytest.raises(ValueError):
            corroborate(first, other)

    def test_malformed_inputs_raise(self):
        good = compost_failure(_record())
        with pytest.raises(ValueError):
            corroborate({"organ": "reim"}, good)
        with pytest.raises(ValueError):
            corroborate(good, None)
        with pytest.raises(ValueError):
            corroborate(good, dict(good, organ="echo"))


class TestCompostBatch:
    def test_merges_three_identical_into_corroboration_3(self):
        batch = compost_batch([_record() for _ in range(3)])
        assert len(batch) == 1
        assert batch[0]["corroboration"] == 3
        assert batch[0]["provenance"]["merged_from"] == 3

    def test_merged_corroboration_unlocks_promotion(self):
        # Medium severity at corroboration 1 is ineligible; three repeats
        # merged to corroboration 3 cross the 'corroboration >= 2' path.
        batch = compost_batch([_record(severity="medium") for _ in range(3)])
        assert batch[0]["corroboration"] == 3
        proposals = promote(batch)
        assert len(proposals) == 1
        assert proposals[0]["applied"] is False
        assert proposals[0]["provenance"]["corroboration"] == 3

    def test_distinct_failures_stay_separate(self):
        batch = compost_batch(
            [
                _record(),
                _record(what="malformed CSV in upload payload", severity="medium"),
            ]
        )
        assert len(batch) == 2
        assert batch[0]["corroboration"] == 1
        assert batch[1]["corroboration"] == 1

    def test_first_occurrence_order_preserved(self):
        alt = _record(
            source="ingest-service",
            what="malformed CSV in upload payload",
            severity="medium",
        )
        batch = compost_batch([alt, _record(), alt])
        assert [b["source"] for b in batch] == ["ingest-service", "deploy-pipeline"]
        assert batch[0]["corroboration"] == 2
        assert batch[1]["corroboration"] == 1

    def test_malformed_record_raises(self):
        good = _record()
        bad = dict(good)
        del bad["ts"]
        with pytest.raises(ValueError):
            compost_batch([good, bad])

    def test_non_list_raises(self):
        with pytest.raises(ValueError):
            compost_batch("not a list")

    def test_empty_batch(self):
        assert compost_batch([]) == []


class TestFailureToGenome:
    def test_end_to_end_with_prior_merges_and_promotes(self):
        prior = compost_failure(_record(ts="2026-09-15T19:00:00Z"))
        result = failure_to_genome(_record(ts="2026-09-16T08:30:00Z"), prior=prior)
        compost = result["compost"]
        proposals = result["proposals"]
        assert set(result.keys()) == {"compost", "proposals"}
        assert compost["corroboration"] == 2
        assert compost["ts"] == "2026-09-16T08:30:00Z"
        assert len(proposals) == 1
        proposal = proposals[0]
        assert proposal["applied"] is False
        assert proposal["provenance"]["compost_fingerprint"] == compost["fingerprint"]
        assert proposal["provenance"]["corroboration"] == 2

    def test_end_to_end_without_prior_composts_then_promotes(self):
        result = failure_to_genome(_record())
        assert result["compost"]["corroboration"] == 1
        assert len(result["proposals"]) == 1
        proposal = result["proposals"][0]
        assert proposal["applied"] is False
        assert (
            proposal["provenance"]["compost_fingerprint"]
            == result["compost"]["fingerprint"]
        )

    def test_ineligible_compost_yields_empty_proposals(self):
        result = failure_to_genome(_record(severity="low"))
        assert result["compost"]["reusable"] is False
        assert result["proposals"] == []

    def test_provenance_chain_intact(self):
        result = failure_to_genome(_record())
        compost = result["compost"]
        proposal = result["proposals"][0]
        assert proposal["provenance"]["source"] == compost["source"]
        assert proposal["provenance"]["ts"] == compost["ts"]
        assert proposal["provenance"]["organ"] == "riem"

    def test_malformed_record_raises(self):
        with pytest.raises(ValueError):
            failure_to_genome({"what": "missing every other key"})

    def test_mismatched_prior_raises(self):
        prior = compost_failure(_record(what="an unrelated failure mode"))
        with pytest.raises(ValueError):
            failure_to_genome(_record(), prior=prior)
