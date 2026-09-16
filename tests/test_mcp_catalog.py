"""MCP catalog tests — hermetic (never touches the real ~/.levi).

The catalog is data (plain dicts in levi.mcp.catalog); these tests pin
the entry shape, the third-party reference label, the no-secrets rule,
and the `levi mcp add --catalog` / `levi mcp catalog` CLI paths.
"""

import json
from types import SimpleNamespace

import pytest

from levi.mcp import catalog
from levi.mcp import client as mc
from levi.mcp.cli import _cmd_mcp_client
from levi.plugins import references as refs


def _args(**kw):
    base = dict(
        mcp_action="add",
        name=None,
        url=None,
        cmd=None,
        client_transport="",
        header=[],
        timeout=None,
        reference=None,
        catalog=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _isolate_home(monkeypatch, tmp_path):
    """Redirect both the MCP client and reference registry to tmp_path."""
    monkeypatch.setattr(mc, "_home", lambda: tmp_path)
    monkeypatch.setattr(refs, "_home", lambda: tmp_path)


class _FakeProbe:
    def list_tools(self):
        return [{"name": "t", "description": "stub", "inputSchema": {}}]

    def close(self):
        pass


# ---------------------------------------------------------------------------
# Catalog shape
# ---------------------------------------------------------------------------


def test_catalog_loads_with_unique_names():
    entries = catalog.load_catalog()
    assert len(entries) >= 7
    names = [e["name"] for e in entries]
    assert len(set(names)) == len(names)
    assert catalog.catalog_names() == names


def test_every_entry_has_required_fields_and_reference_label():
    for e in catalog.load_catalog():
        for key in ("name", "description", "transport", "provider", "reference"):
            assert key in e, f"{e.get('name')}: missing {key}"
        assert e["reference"] is True, f"{e['name']}: reference label must be True"
        assert isinstance(e["provider"], str) and e["provider"].strip()
        assert isinstance(e["description"], str) and e["description"].strip()
        assert "\n" not in e["description"]
        assert e["transport"] in ("stdio", "http")
        if e["transport"] == "stdio":
            assert e["command"] and all(
                isinstance(c, str) and c.strip() for c in e["command"]
            )
            assert "url" not in e
        else:
            assert e["url"].startswith(("http://", "https://"))
            assert "command" not in e


def test_no_secrets_in_transport_specs():
    """No API keys / secrets may hide in a catalog command or URL."""
    needles = ("api_key", "apikey", "api-key", "secret", "password", "token=")
    for e in catalog.load_catalog():
        blob = json.dumps({k: e[k] for k in ("command", "url") if k in e}).lower()
        for n in needles:
            assert n not in blob, f"{e['name']}: transport spec looks secret-bearing"


def test_get_entry_unknown_errors_cleanly():
    with pytest.raises(catalog.CatalogError) as exc:
        catalog.get_entry("no-such-server")
    msg = str(exc.value)
    assert "no-such-server" in msg
    assert "context7" in msg  # available names are listed


def test_install_spec_maps_to_add_server_kwargs():
    spec = catalog.install_spec(catalog.get_entry("context7"))
    assert spec["transport"] == "stdio"
    assert spec["command"] == ["npx", "-y", "@upstash/context7-mcp"]
    assert spec["reference"] == "Context7"  # provider → reference label


def test_validate_rejects_bad_entries():
    good = dict(catalog.get_entry("fetch"))
    bad = dict(good, reference=False)
    with pytest.raises(catalog.CatalogError):
        catalog._validate_entry(bad, 0)
    bad = dict(good)
    del bad["provider"]
    with pytest.raises(catalog.CatalogError):
        catalog._validate_entry(bad, 0)
    bad = dict(good, bogus_key=1)
    with pytest.raises(catalog.CatalogError):
        catalog._validate_entry(bad, 0)


# ---------------------------------------------------------------------------
# Config writes (isolated home)
# ---------------------------------------------------------------------------


def test_add_catalog_writes_correct_isolated_config(tmp_path):
    home = tmp_path / "home"
    entry = catalog.get_entry("context7")
    cfg = mc.add_server("context7", home=home, **catalog.install_spec(entry))
    assert cfg["transport"] == "stdio"
    assert cfg["command"] == ["npx", "-y", "@upstash/context7-mcp"]
    assert cfg["reference"] == "Context7"

    stored = json.loads((home / ".levi" / "mcp" / "servers.json").read_text())
    assert stored["servers"]["context7"]["reference"] == "Context7"

    # The provider lands in the universal reference registry, isolated too.
    found = [
        r
        for r in refs.list_references(home=home).values()
        if r.kind == "mcp-server" and r.detail.get("mcp_server") == "context7"
    ]
    assert len(found) == 1
    assert found[0].provider == "Context7"

    # Everything landed under the isolated home, nowhere else: the store
    # functions take home explicitly, so the real ~/.levi is untouched.
    assert (home / ".levi" / "mcp" / "servers.json").exists()
    assert (home / ".levi" / "references.json").exists()


def test_existing_url_and_cmd_add_still_work(tmp_path):
    home = tmp_path / "home"
    http_cfg = mc.add_server(
        "via-url", transport="http", url="http://127.0.0.1:9/mcp", home=home
    )
    assert http_cfg == {"transport": "http", "url": "http://127.0.0.1:9/mcp"}
    stdio_cfg = mc.add_server(
        "via-cmd",
        transport="stdio",
        command=["npx", "-y", "some-mcp-server"],
        home=home,
    )
    assert stdio_cfg["command"] == ["npx", "-y", "some-mcp-server"]
    assert set(mc.list_servers(home)) == {"via-url", "via-cmd"}


# ---------------------------------------------------------------------------
# CLI paths
# ---------------------------------------------------------------------------


def test_cli_catalog_lists_entries_with_reference_labels(capsys):
    _cmd_mcp_client(_args(mcp_action="catalog"), "catalog")
    out = capsys.readouterr().out
    assert "context7" in out
    assert "sequential-thinking" in out
    assert "third-party reference" in out
    assert "reference: Context7" in out


def test_cli_add_catalog_unknown_name_exits_1(capsys):
    with pytest.raises(SystemExit) as exc:
        _cmd_mcp_client(_args(catalog="no-such-server"), "add")
    assert exc.value.code == 1
    assert "no-such-server" in capsys.readouterr().out


def test_cli_add_catalog_conflicts_with_url(capsys):
    with pytest.raises(SystemExit) as exc:
        _cmd_mcp_client(_args(catalog="context7", url="http://x/mcp"), "add")
    assert exc.value.code == 2


def test_cli_add_catalog_full_flow_isolated(monkeypatch, tmp_path, capsys):
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    monkeypatch.setattr(mc, "connect_server", lambda name, cfg: _FakeProbe())

    _cmd_mcp_client(_args(catalog="context7"), "add")
    out = capsys.readouterr().out
    assert "Added MCP server 'context7'" in out
    assert "[reference: Context7]" in out

    stored = json.loads((home / ".levi" / "mcp" / "servers.json").read_text())
    cfg = stored["servers"]["context7"]
    assert cfg["command"] == ["npx", "-y", "@upstash/context7-mcp"]
    assert cfg["reference"] == "Context7"


def test_cli_add_catalog_custom_name(monkeypatch, tmp_path):
    home = tmp_path / "home"
    _isolate_home(monkeypatch, home)
    monkeypatch.setattr(mc, "connect_server", lambda name, cfg: _FakeProbe())

    _cmd_mcp_client(_args(catalog="fetch", name="webfetch"), "add")
    stored = json.loads((home / ".levi" / "mcp" / "servers.json").read_text())
    assert set(stored["servers"]) == {"webfetch"}
    assert stored["servers"]["webfetch"]["command"] == ["uvx", "mcp-server-fetch"]
