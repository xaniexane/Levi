"""Hermetic tests for per-item audience grants (Google+ ACL revival)."""

import pytest

from levi.circles.audience import AudienceStore
from levi.circles.model import CircleError, CircleStore


@pytest.fixture()
def circles(tmp_path):
    store = CircleStore(home=tmp_path)
    store.add("amy", layer="inner")
    store.add("bo", layer="close")
    store.add("cy", layer="friends")
    store.add("dee", layer="tribe")
    return store


@pytest.fixture()
def audience(tmp_path):
    return AudienceStore(home=tmp_path)


def test_grant_resolves_layers_and_individuals(circles, audience):
    grant = audience.grant(
        "post-1", circles, layers=["inner"], individuals=["cy"]
    )
    assert grant.member_ids == ["amy", "cy"]
    assert audience.can_see("post-1", "amy")
    assert audience.can_see("post-1", "cy")
    assert not audience.can_see("post-1", "bo")  # close layer not granted
    assert not audience.can_see("post-1", "dee")


def test_unknown_post_is_visible_to_no_one(circles, audience):
    assert not audience.can_see("nope", "amy")


def test_revoke_is_explicit_and_permanent(circles, audience):
    audience.grant("post-1", circles, layers=["inner"])
    audience.revoke("post-1")
    assert not audience.can_see("post-1", "amy")
    audit = audience.audience_of("post-1")
    assert audit["revoked"] is True
    assert audit["revoked_at"]
    assert audit["member_ids"] == ["amy"]  # the record stays


def test_revoke_unknown_raises(audience):
    with pytest.raises(CircleError):
        audience.revoke("nope")


def test_grant_to_phantom_individual_raises(circles, audience):
    with pytest.raises(CircleError):
        audience.grant("post-1", circles, individuals=["ghost"])


def test_empty_audience_refused(circles, audience):
    with pytest.raises(CircleError):
        audience.grant("post-1", circles)


def test_unknown_layer_raises(circles, audience):
    with pytest.raises(CircleError):
        audience.grant("post-1", circles, layers=["strangers"])


def test_double_grant_requires_revoke_first(circles, audience):
    audience.grant("post-1", circles, layers=["inner"])
    with pytest.raises(CircleError):
        audience.grant("post-1", circles, layers=["close"])
    audience.revoke("post-1")
    # A fresh grant after revoke is allowed (a new audience decision).
    audience.grant("post-1", circles, layers=["close"])
    assert audience.can_see("post-1", "bo")


def test_snapshot_semantics(circles, audience):
    audience.grant("post-1", circles, layers=["friends"])
    circles.remove("cy")  # leaves the circle later
    # The grant's receipt is stable: the audit shows who could see it.
    assert audience.can_see("post-1", "cy")
    assert audience.audience_of("post-1")["member_ids"] == ["cy"]


def test_audience_of_unknown_raises(audience):
    with pytest.raises(CircleError):
        audience.audience_of("nope")


def test_grants_persist(tmp_path, circles):
    first = AudienceStore(home=tmp_path)
    first.grant("post-1", circles, layers=["inner"], individuals=["dee"])
    second = AudienceStore(home=tmp_path)
    assert second.can_see("post-1", "amy")
    assert second.can_see("post-1", "dee")
    assert not second.can_see("post-1", "bo")
