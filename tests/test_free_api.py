"""Proof tests for the free-API catalog (zero-paid-key web-API registry).

Laws: no paid keys ever, confidence labeled on every entry,
deterministic queries, registry self-validates clean.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from levi.integrations.free_api import (  # noqa: E402
    FreeAPI,
    by_auth,
    by_category,
    categories,
    get,
    keyless,
    validate,
    REGISTRY,
)


def test_registry_self_validates_clean():
    assert validate() == []


def test_registry_is_not_empty_and_not_free_lattice():
    assert len(REGISTRY) >= 8
    ids = {a.id for a in REGISTRY}
    assert "open-meteo" in ids  # a web API, not an engine


def test_no_paid_keys_ever():
    for api in REGISTRY:
        assert api.auth in ("none", "free-key"), api.id
        assert "credit card" not in api.free_limits.lower()


def test_confidence_labeled_everywhere():
    for api in REGISTRY:
        assert api.confidence in ("verified", "hearsay"), api.id


def test_get_unknown_id_is_keyerror_not_guess():
    with pytest.raises(KeyError):
        get("definitely-not-an-api")


def test_by_category_deterministic():
    assert [a.id for a in by_category("weather")] == ["open-meteo"]
    assert by_category("weather") == by_category("weather")


def test_by_auth_rejects_garbage():
    with pytest.raises(ValueError):
        by_auth("oauth2-enterprise")


def test_keyless_is_subset_with_no_key():
    for api in keyless():
        assert api.auth == "none"
    assert len(keyless()) >= 1


def test_categories_first_seen_order():
    cats = categories()
    assert cats[0] == "weather"
    assert len(cats) == len(set(cats))


def test_entry_rejects_bad_auth_and_blank_fields():
    with pytest.raises(ValueError):
        FreeAPI("x", "X", "fun", "https://x.test", "paid", "n/a", "n/a")
    with pytest.raises(ValueError):
        FreeAPI("x", "", "fun", "https://x.test", "none", "n/a", "n/a")
