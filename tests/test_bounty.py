"""Hermetic tests for the bounty recon pipeline.

No network, no real HOME writes: ScopeStore/FindingStore are constructed
with tmp_path, network boundaries are monkeypatched, and the CLI smoke
test runs in a subprocess with an isolated HOME. Real network is NEVER
touched.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from levi.bounty import content as content_mod
from levi.bounty import enum as enum_mod
from levi.bounty import probe as probe_mod
from levi.bounty.pipeline import run_recon
from levi.bounty.scope import ScopeError, ScopeStore, normalize_domain
from levi.bounty.store import FindingStore, finding_id


@pytest.fixture
def scoped(tmp_path):
    store = ScopeStore(path=tmp_path / "scope.json")
    store.add("example.com")
    return store


@pytest.fixture
def fstore(tmp_path):
    return FindingStore(path=tmp_path / "findings.json")


# -- scope normalization -------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("example.com", "example.com"),
        ("EXAMPLE.COM", "example.com"),
        ("https://example.com/", "example.com"),
        ("http://app.example.com:8080/path?q=1", "app.example.com"),
        ("example.com.", "example.com"),
        ("  www.example.com  ", "www.example.com"),
        ("user@example.com", "example.com"),
    ],
)
def test_normalize_domain(raw, expected):
    assert normalize_domain(raw) == expected


@pytest.mark.parametrize("raw", ["", "not a domain", "1.2.3.4", "http://", "-bad-.com"])
def test_normalize_domain_rejects(raw):
    with pytest.raises(ValueError):
        normalize_domain(raw)


# -- scope add/remove/list/check -----------------------------------------


def test_scope_add_list_remove(tmp_path):
    s = ScopeStore(path=tmp_path / "s.json")
    assert s.list() == []
    s.add("Example.COM")
    s.add("https://sub.example.com/")
    assert s.list() == ["example.com", "sub.example.com"]
    assert s.remove("example.com") is True
    assert s.list() == ["sub.example.com"]
    assert s.remove("nope.com") is False


def test_scope_persists(tmp_path):
    p = tmp_path / "s.json"
    ScopeStore(path=p).add("example.com")
    assert ScopeStore(path=p).list() == ["example.com"]


def test_check_allows_enrolled_and_subdomains(scoped):
    assert scoped.check("example.com") == "example.com"
    assert scoped.check("https://deep.app.example.com/x") == "example.com"


@pytest.mark.parametrize(
    "target",
    ["other.com", "evilexample.com", "example.com.evil.com", "sub.other.com"],
)
def test_check_refuses_out_of_scope(scoped, target):
    with pytest.raises(ScopeError):
        scoped.check(target)


def test_check_refuses_with_empty_store(tmp_path):
    with pytest.raises(ScopeError):
        ScopeStore(path=tmp_path / "s.json").check("example.com")


# -- the gate runs before any network -------------------------------------


def test_enum_gate_fires_before_network(scoped, monkeypatch):
    called = []

    def _boom(*a, **k):
        called.append(a)
        raise AssertionError("network touched before scope gate")

    monkeypatch.setattr(enum_mod, "_fetch_text", _boom)
    monkeypatch.setattr(enum_mod, "_resolve", _boom)
    with pytest.raises(ScopeError):
        enum_mod.enumerate_subdomains("evil.com", store=scoped)
    assert called == []


def test_probe_gate_fires_before_network(scoped, monkeypatch):
    called = []

    def _boom(*a, **k):
        called.append(a)
        raise AssertionError("network touched before scope gate")

    monkeypatch.setattr(probe_mod, "_tcp_open", _boom)
    with pytest.raises(ScopeError):
        probe_mod.probe_host("evil.com", store=scoped)
    assert called == []


def test_content_gate_fires_before_network(scoped, monkeypatch):
    called = []

    def _boom(*a, **k):
        called.append(a)
        raise AssertionError("network touched before scope gate")

    monkeypatch.setattr(content_mod, "_fetch_text", _boom)
    with pytest.raises(ScopeError):
        content_mod.collect_content("evil.com", store=scoped)
    assert called == []


# -- enum dedup -----------------------------------------------------------


def test_enumerate_dedups_and_sorts(scoped, monkeypatch):
    monkeypatch.setattr(
        enum_mod,
        "_crtsh_subdomains",
        lambda domain: {
            "www.example.com",
            "WWW.EXAMPLE.COM.",
            "*.example.com",
            "api.example.com",
            "other.net",  # filtered: not within domain
        },
    )
    monkeypatch.setattr(enum_mod, "_resolve", lambda host: ["93.184.216.34"])
    subs = enum_mod.enumerate_subdomains(
        "example.com", store=scoped, use_wordlist=False, delay=0
    )
    names = [s["subdomain"] for s in subs]
    assert names == ["api.example.com", "www.example.com"]
    assert all(s["source"] == "crt.sh" for s in subs)


# -- probe facts ----------------------------------------------------------


def test_probe_host_records_facts(scoped, monkeypatch):
    monkeypatch.setattr(probe_mod, "_tcp_open", lambda h, p, timeout=8: p in (80, 443))
    monkeypatch.setattr(
        probe_mod,
        "_http_get",
        lambda h, p, use_tls, timeout=8: {
            "status": 200,
            "title": "Example",
            "tech": ["server: nginx"],
        },
    )
    monkeypatch.setattr(
        probe_mod,
        "_tls_cert",
        lambda h, port=443, timeout=8: {"subject": "CN=example.com"},
    )
    facts = probe_mod.probe_host("app.example.com", store=scoped, delay=0)
    assert facts["open_ports"] == [80, 443]
    assert "http:80" in facts["http"]
    assert facts["tls"]["subject"] == "CN=example.com"


# -- finding dedup --------------------------------------------------------


def test_finding_dedup_refreshes_last_seen(fstore):
    f1, new1 = fstore.add("h.example.com", "example.com", "open_port", "tcp/80 open")
    assert new1 is True
    first = f1.first_seen
    f2, new2 = fstore.add("h.example.com", "example.com", "open_port", "tcp/80 open")
    assert new2 is False
    assert f2.id == f1.id
    assert f2.first_seen == first  # first_seen never moves
    assert f2.last_seen >= first


def test_finding_id_stable():
    assert finding_id("a", "k", "d") == finding_id("a", "k", "d")
    assert finding_id("a", "k", "d") != finding_id("a", "k", "e")


# -- change detection ------------------------------------------------------


def test_new_since_last_run(fstore):
    # backdate directly: dataclass default_factory binds _now at import,
    # so control timestamps by mutating the stored objects
    old, _ = fstore.add("h.example.com", "example.com", "open_port", "tcp/80 open")
    old.first_seen = old.last_seen = "2026-01-01T00:00:01+00:00"
    fstore.record_run("example.com", "2026-01-01T00:00:00+00:00", [old.id])
    new, _ = fstore.add("h.example.com", "example.com", "open_port", "tcp/443 open")
    new.first_seen = new.last_seen = "2026-01-01T00:00:03+00:00"
    fstore.record_run("example.com", "2026-01-01T00:00:02+00:00", [old.id, new.id])
    fresh = fstore.new_since_last_run()
    assert [f.id for f in fresh] == [new.id]


def test_new_since_last_run_first_run_returns_all(fstore):
    fstore.add("h.example.com", "example.com", "open_port", "tcp/80 open")
    fstore.record_run("example.com", "2026-01-01T00:00:00+00:00", [])
    assert len(fstore.new_since_last_run()) == 1


# -- pipeline orchestration (stages mocked) --------------------------------


def test_run_recon_orchestrates_and_gates(scoped, fstore, monkeypatch):
    monkeypatch.setattr(
        enum_mod,
        "enumerate_subdomains",
        lambda domain, store=None, delay=0.5, **k: [
            {"subdomain": "api.example.com", "ips": ["1.2.3.4"], "source": "crt.sh"}
        ],
    )
    monkeypatch.setattr(
        probe_mod,
        "probe_host",
        lambda host, store=None, ports=None, delay=0.5: {
            "host": host,
            "open_ports": [443],
            "http": {"https:443": {"status": 200, "title": "API", "tech": []}},
            "tls": {"subject": "CN=api.example.com", "not_after": "2027-01-01"},
        },
    )
    monkeypatch.setattr(
        content_mod,
        "collect_content",
        lambda domain, store=None, page_bodies=None: {
            "domain": domain,
            "archived_urls": ["https://web.archive.org/x"],
            "archived_count": 1,
            "js_files": [
                {
                    "js_url": "https://api.example.com/app.js",
                    "endpoints": ["/api/v1/users"],
                    "possible_exposures": ["generic_api_key_assign"],
                }
            ],
        },
    )
    report = run_recon("example.com", store=scoped, findings=fstore, delay=0)
    assert report["domain"] == "example.com"
    assert report["scope"] == "example.com"
    kinds = {f.kind for f in fstore.list()}
    assert {
        "subdomain",
        "open_port",
        "http_service",
        "tls_cert",
        "archived_url",
        "js_endpoint",
        "possible_exposure",
    } <= kinds
    assert all(f.scope == "example.com" for f in fstore.list())
    assert report["errors"] == []


def test_run_recon_refuses_out_of_scope_at_entry(tmp_path, monkeypatch):
    called = []

    def _boom(*a, **k):
        called.append(a)
        raise AssertionError("stage ran despite scope refusal")

    monkeypatch.setattr(enum_mod, "enumerate_subdomains", _boom)
    with pytest.raises(ScopeError):
        run_recon(
            "evil.com",
            store=ScopeStore(path=tmp_path / "s.json"),
            findings=FindingStore(path=tmp_path / "f.json"),
        )
    assert called == []


# -- content: wayback + js parsing (fetch mocked) ---------------------------


def test_wayback_parses_cdx(scoped, monkeypatch):
    body = json.dumps(
        [
            ["urlkey", "timestamp", "original"],
            ["k1", "20260101", "https://example.com/old"],
            ["k1", "20260101", "https://example.com/old"],  # dupe
        ]
    )
    monkeypatch.setattr(content_mod, "_fetch_text", lambda url, timeout=10: body)
    urls = content_mod.wayback_urls("example.com", delay=0)
    assert urls == ["https://example.com/old"]


def test_js_harvest_extracts_endpoints_and_exposures(monkeypatch):
    html = '<script src="/static/app.js"></script>'
    js = 'fetch("/api/v1/users"); const api_key = "AKIAIOSFODNN7EXAMPLE";'
    monkeypatch.setattr(
        content_mod, "_fetch_text", lambda url, timeout=10: js
    )
    out = content_mod.harvest_js(
        "example.com", {"https://example.com/": html}, delay=0
    )
    assert len(out) == 1
    assert "/api/v1/users" in out[0]["endpoints"]
    assert "aws_access_key" in out[0]["possible_exposures"]


# -- CLI smoke (subprocess, isolated HOME, no network) -----------------------


def _cli(home: Path, *argv: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "core")
    return subprocess.run(
        [sys.executable, "-m", "levi.cli.main", "bounty", *argv],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def test_cli_scope_and_findings(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    r = _cli(home, "scope", "add", "example.com")
    assert r.returncode == 0, r.stderr
    assert "Scope enrolled: example.com" in r.stdout
    r = _cli(home, "scope", "list")
    assert "example.com" in r.stdout
    r = _cli(home, "scope", "add", "not a domain!!")
    assert "refused" in r.stdout
    r = _cli(home, "findings")
    assert "No findings stored yet" in r.stdout
    # out-of-scope recon refused without touching network
    r = _cli(home, "recon", "evil.com")
    assert "SCOPE REFUSED" in r.stdout
    assert r.returncode == 0
    # scope files landed under the isolated HOME only
    assert (home / ".levi" / "bounty" / "scope.json").exists()
