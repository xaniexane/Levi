"""Tests for the FairPlay connector plugin (levi.plugins.fairplay).

- Importing the module registers the connector (deny-closed wiring).
- ``audit`` runs the real sly-trade detector; non-mapping offers are
  refused with invalid_params, never guessed.
- ``catalog`` lists the seven sly-trade patterns.
- Catalog/detector sync: every pattern id the detector can emit for the
  seven docstring patterns appears in the catalog.
"""

import pytest

from levi.plugins import fairplay as fairplay_module
from levi.plugins.registry import list_connectors

# Battery: one offer per docstring pattern.
PATTERN_BATTERY = {
    "opaque-odds": {"paid_random_draws": True},
    "no-worst-case": {"paid_random_draws": True, "odds_published": True},
    "time-fenced-grind": {"progress_expiry": "season"},
    "revocable-license": {"sale_is_license": True, "license_revocable": True},
    "pay-to-win": {"paid_power": True},
    "vanishing-inventory": {"server_only_inventory": True},
    "euphemism": {"marketing_language": ["surprise mechanics"]},
}


def _connector():
    return fairplay_module.FairPlayConnector()


def test_connector_registered_on_import():
    ids = [c.id for c in list_connectors()]
    assert "fairplay" in ids


def test_credentialless_public_sentinel():
    assert _connector().credential() == "public"


def test_audit_sly_offer():
    result = _connector().execute("audit", {"offer": PATTERN_BATTERY["opaque-odds"]})
    assert result.ok, result.message
    assert result.data["verdict"] == "predatory"
    assert result.data["sly_count"] >= 1
    patterns = [f["pattern"] for f in result.data["findings"]]
    assert "opaque-odds" in patterns
    for finding in result.data["findings"]:
        assert finding["honest_alternative"]


def test_audit_refuses_non_mapping_offer():
    result = _connector().execute("audit", {"offer": "just trust us"})
    assert not result.ok
    assert result.status == "invalid_params"


def test_audit_refuses_missing_offer():
    result = _connector().execute("audit", {})
    assert not result.ok
    assert result.status == "invalid_params"


def test_catalog_lists_seven_patterns():
    result = _connector().execute("catalog")
    assert result.ok, result.message
    patterns = result.data["patterns"]
    assert len(patterns) == 7
    ids = {p["pattern"] for p in patterns}
    assert ids == set(PATTERN_BATTERY)
    for entry in patterns:
        assert entry["tell"] and entry["honest_alternative"] and entry["source"]


def test_unknown_operation():
    result = _connector().execute("funnel")
    assert not result.ok
    assert result.status == "unknown_operation"


def test_catalog_detector_sync():
    """Every pattern id the detector emits for the battery is cataloged."""
    catalog_ids = {
        p["pattern"] for p in _connector().execute("catalog").data["patterns"]
    }
    for expected, offer in PATTERN_BATTERY.items():
        result = _connector().execute("audit", {"offer": offer})
        assert result.ok, result.message
        emitted = {f["pattern"] for f in result.data["findings"]}
        assert expected in emitted, f"{expected} not emitted for {offer}"
        assert emitted <= catalog_ids, f"uncataloged patterns: {emitted - catalog_ids}"


@pytest.mark.parametrize("bad", [None, 42, ["x"]])
def test_audit_refuses_non_dict_params_shape(bad):
    result = _connector().execute("audit", bad)
    assert not result.ok
