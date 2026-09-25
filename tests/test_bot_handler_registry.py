"""Tests for the public custom-handler registry in levi.bot.services.

register_handler(name, fn) is the services API for type=custom services:
fail-closed validation, built-in names are not overridable, and registered
names win over the honest _handle_custom refusal.
"""

import pytest

from levi.bot import services
from levi.bot.services import (
    ServiceDefinition,
    ServiceResult,
    get_handler,
    get_handler_for,
    register_handler,
)

# A unique name per test function keeps the module-level registry clean.
# Each test pops its own registration in a finally block so one process's
# pytest run can't leak registrations into another test.


def _ok_handler(params):
    return ServiceResult(ok=True, report="CUSTOM RAN: %s" % params.get("ping"))


def _registered(name, fn):
    """register, return a cleanup closure."""
    register_handler(name, fn)

    def _cleanup():
        services._HANDLERS.pop(name, None)

    return _cleanup


def test_register_then_get_handler_executes():
    cleanup = _registered("zz-test-custom", _ok_handler)
    try:
        handler = get_handler("zz-test-custom")
        assert handler is _ok_handler
        result = handler({"ping": "pong"})
        assert result.ok is True
        assert "CUSTOM RAN" in result.report
    finally:
        cleanup()


def test_registered_name_wins_over_custom_stub_via_get_handler_for():
    svc = ServiceDefinition(
        name="zz-test-svc", description="d", service_type="custom", schedule="daily"
    )
    cleanup = _registered("zz-test-svc", _ok_handler)
    try:
        handler = get_handler_for(svc)
        assert handler is _ok_handler
        assert get_handler_for(svc)({"ping": "x"}).ok is True
    finally:
        cleanup()


@pytest.mark.parametrize(
    "builtin", ["morning-briefing", "bounty-watch", "backup-status", "research-brief"]
)
def test_builtin_names_cannot_be_overridden(builtin):
    with pytest.raises(ValueError, match="built-in"):
        register_handler(builtin, _ok_handler)


@pytest.mark.parametrize("bad_name", ["", None, 123, b"name", []])
def test_bad_name_raises(bad_name):
    with pytest.raises(ValueError, match="name"):
        register_handler(bad_name, _ok_handler)


@pytest.mark.parametrize("bad_fn", [None, "not-callable", 42])
def test_bad_fn_raises(bad_fn):
    with pytest.raises(ValueError, match="callable"):
        register_handler("zz-test-badfn", bad_fn)


def test_unregistered_name_still_gets_honest_refusal():
    handler = get_handler("zz-never-registered-123")
    result = handler({"name": "zz-never-registered-123"})
    assert result.ok is False
    assert "register_handler" in result.report
