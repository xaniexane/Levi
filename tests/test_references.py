"""Universal provider references — hermetic tests.

Never touches the real ~/.levi: every store function takes a home param.
"""

import stat

import pytest

from levi.plugins import references as refs
from levi.mcp import client as mc


@pytest.fixture()
def home(tmp_path):
    return tmp_path / "home"


# ---------------------------------------------------------------------------
# Identity guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    ["LEVI", "levi", "Levi", "levi_care", "levi-care", "LeviCare", "LEVI CARE"],
)
def test_identity_guard_rejects_levi_names(bad):
    with pytest.raises(refs.ReferenceError):
        refs.validate_provider_name(bad)
    with pytest.raises(refs.ReferenceError):
        refs.assert_not_levi_identity(bad)


@pytest.mark.parametrize("good", ["KAI-9000", "Qwen", "Pollinations", "LLaMA", "Acme Models"])
def test_identity_guard_accepts_providers(good):
    assert refs.validate_provider_name(good) == good.strip()


def test_identity_guard_rejects_blank():
    with pytest.raises(refs.ReferenceError):
        refs.validate_provider_name("   ")


def test_connector_references_validated_at_definition():
    from levi.plugins.registry import Connector

    with pytest.raises(refs.ReferenceError):

        class _Bad(Connector):
            id = "bad"
            display_name = "Bad"
            credential_env_var = "BAD_TOKEN"
            references = ("levi_care",)

            def perform(self, operation, params, token, transport):
                raise AssertionError


def test_connector_references_shown_as_references():
    from levi.plugins.registry import Connector, describe

    class _Ok(Connector):
        id = "ok"
        display_name = "Ok"
        credential_env_var = "OK_TOKEN"
        references = ("KAI-9000",)

        def perform(self, operation, params, token, transport):
            raise AssertionError

    text = describe(_Ok())
    assert "KAI-9000" in text
    assert "reference" in text.lower()


# ---------------------------------------------------------------------------
# Store round-trip
# ---------------------------------------------------------------------------


def test_add_list_remove_round_trip(home):
    r = refs.add_reference("KAI-9000", kind="plugin", detail={"note": "x"}, home=home)
    assert r.id == "ref-kai-9000"
    assert r.provider == "KAI-9000"
    assert r.kind == "plugin"
    got = refs.list_references(home=home)
    assert set(got) == {"ref-kai-9000"}
    refs.remove_reference("ref-kai-9000", home=home)
    assert refs.list_references(home=home) == {}
    with pytest.raises(refs.ReferenceError):
        refs.remove_reference("ref-kai-9000", home=home)


def test_store_is_owner_only(home):
    refs.add_reference("Qwen", home=home)
    path = home / ".levi" / "references.json"
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600


def test_duplicate_provider_gets_unique_id(home):
    a = refs.add_reference("Qwen", home=home)
    b = refs.add_reference("Qwen", home=home)
    assert a.id != b.id
    assert b.id == "ref-qwen-2"


def test_bad_kind_rejected(home):
    with pytest.raises(refs.ReferenceError):
        refs.add_reference("Qwen", kind="brain", home=home)


def test_describe_labels_reference(home):
    r = refs.add_reference("Pollinations", kind="media", home=home)
    text = refs.describe(r)
    assert "reference" in text
    assert "Pollinations" in text
    assert "never a LEVI source" in text


# ---------------------------------------------------------------------------
# MCP integration
# ---------------------------------------------------------------------------


def test_mcp_add_with_reference_records_universally(home):
    cfg = mc.add_server(
        "kai_9000",
        transport="http",
        url="http://127.0.0.1:9/mcp",
        reference="KAI-9000",
        home=home,
    )
    assert cfg["reference"] == "KAI-9000"
    all_refs = refs.list_references(home=home)
    linked = [r for r in all_refs.values() if r.detail.get("mcp_server") == "kai_9000"]
    assert len(linked) == 1
    assert linked[0].provider == "KAI-9000"
    assert linked[0].kind == "mcp-server"


def test_mcp_add_without_reference_records_nothing(home):
    mc.add_server("plain", transport="http", url="http://127.0.0.1:9/mcp", home=home)
    assert refs.list_references(home=home) == {}


def test_mcp_remove_cleans_up_reference(home):
    mc.add_server(
        "kai_9000",
        transport="http",
        url="http://127.0.0.1:9/mcp",
        reference="KAI-9000",
        home=home,
    )
    mc.remove_server("kai_9000", home=home)
    assert refs.list_references(home=home) == {}


def test_mcp_replace_updates_reference(home):
    mc.add_server(
        "srv", transport="http", url="http://127.0.0.1:9/mcp",
        reference="KAI-9000", home=home,
    )
    mc.add_server(
        "srv", transport="http", url="http://127.0.0.1:9/mcp",
        reference="Qwen", home=home,
    )
    providers = {r.provider for r in refs.list_references(home=home).values()}
    assert providers == {"Qwen"}


def test_mcp_reference_rejecting_levi_identity(home):
    with pytest.raises(refs.ReferenceError):
        mc.add_server(
            "srv",
            transport="http",
            url="http://127.0.0.1:9/mcp",
            reference="LEVI",
            home=home,
        )
    # Failed add must not leave a half-written server or reference behind.
    assert mc.list_servers(home=home) == {}
    assert refs.list_references(home=home) == {}
