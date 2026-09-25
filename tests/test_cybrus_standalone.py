"""Tests for the Cybrus standalone product surface.

Hermetic: CYBRUS_HOME is monkeypatched to a tmp dir and the master
password comes from a throwaway env value — no real HOME writes, no
network, no installation. The broker hookup test adapts: it asserts the
wired path when levi.cybrus.broker has landed, and the clean pending
path while it is still in flight.
"""

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from levi.cybrus import product, quickstart

ROOT = Path(__file__).resolve().parents[1]
TEST_MASTER = "throwaway-test-passphrase-not-a-secret"


@pytest.fixture()
def iso(tmp_path, monkeypatch):
    home = tmp_path / "cybrus-home"
    monkeypatch.setenv(quickstart.ENV_HOME, str(home))
    # Route the engine's LEVI_HOME convention at the isolated home too, so
    # quickstart and the broker open the SAME vault in tests.
    monkeypatch.setenv("LEVI_HOME", str(home))
    monkeypatch.setenv(quickstart.ENV_MASTER, TEST_MASTER)
    return home


def test_shim_importable():
    import cybrus

    assert callable(cybrus.generate_password)
    assert len(cybrus.generate_password(16)) == 16
    assert cybrus.product.PRODUCT_NAME == "Cybrus"


def test_quickstart_receipt_shape(iso):
    receipt = quickstart.quickstart("github", "octocat")
    assert receipt["product"] == "Cybrus"
    assert receipt["version"] == product.PRODUCT_VERSION
    assert receipt["home"] == str(iso)
    assert receipt["elapsed_s"] >= 0
    assert [s["name"] for s in receipt["steps"]] == [
        "layout",
        "vault-init",
        "generate",
        "store",
        "verify",
    ]
    cred = receipt["credential"]
    assert cred["service"] == "github"
    assert cred["username"] == "octocat"
    assert len(cred["password"]) == 24
    assert "Chauncey" in receipt["price"]  # pricing flagged, not invented
    assert product.PRICE_MONTHLY is None


def test_quickstart_round_trip_and_delete(iso):
    from levi.cybrus.vault import CredentialVault

    receipt = quickstart.quickstart("example.com", "user1")
    # Engine-default vault (LEVI_HOME is routed at the isolated home).
    vault = CredentialVault(TEST_MASTER)
    assert vault.get("example.com", "user1") == receipt["credential"]["password"]
    assert "example.com" in vault.list_services()
    vault.delete("example.com", "user1")
    with pytest.raises(Exception):
        vault.get("example.com", "user1")


def test_quickstart_rejects_empty_service(iso):
    with pytest.raises(ValueError):
        quickstart.quickstart("", "user1")


def test_status_reports_home_and_vault(iso):
    before = quickstart.status()
    assert before["home_exists"] is False
    assert before["ok"] is False

    quickstart.quickstart("svc", "u")
    after = quickstart.status()
    assert after["home_exists"] is True
    assert after["vault_unlocked"] is True
    assert after["vault_backend"] in ("fernet", "stdlib-fallback")
    assert "svc" in after["stored_services"]
    assert after["ok"] is True


def test_product_sheet_and_price_line():
    sheet = product.product_sheet()
    assert "Cybrus" in sheet
    assert "Encrypted at rest" in sheet
    assert "approval" in sheet.lower()
    line = product.price_line()
    assert "Chauncey" in line
    assert "not set in this build" in line
    assert product.PRICE_MONTHLY is None  # never invent pricing


def test_packaging_manifest_valid():
    manifest = ROOT / "packaging" / "cybrus" / "pyproject.toml"
    assert manifest.is_file()
    with open(manifest, "rb") as fh:
        data = tomllib.load(fh)
    proj = data["project"]
    assert proj["name"] == "cybrus"
    assert proj["version"] == product.PRODUCT_VERSION
    assert proj["dependencies"] == []  # stdlib-only core, by law
    assert data["project"]["scripts"]["cybrus"] == "cybrus.__main__:main"


def _run_cybrus_cli(*argv, iso_home):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "core") + os.pathsep + env.get("PYTHONPATH", "")
    env[quickstart.ENV_HOME] = str(iso_home)
    # Same routing as the test fixture: broker + quickstart share one vault.
    env["LEVI_HOME"] = str(iso_home)
    env[quickstart.ENV_MASTER] = TEST_MASTER
    return subprocess.run(
        [sys.executable, "-m", "cybrus", *argv],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_cli_sheet(tmp_path):
    proc = _run_cybrus_cli("sheet", iso_home=tmp_path / "h1")
    assert proc.returncode == 0
    assert "Cybrus" in proc.stdout


def test_cli_price_flagged(tmp_path):
    proc = _run_cybrus_cli("price", iso_home=tmp_path / "h2")
    assert proc.returncode == 0
    assert "Chauncey" in proc.stdout


def test_cli_quickstart_end_to_end(tmp_path):
    home = tmp_path / "h3"
    proc = _run_cybrus_cli(
        "quickstart", "--service", "demo", "--username", "d1", iso_home=home
    )
    assert proc.returncode == 0
    assert "shown once" in proc.stdout

    status_proc = _run_cybrus_cli("status", iso_home=home)
    assert status_proc.returncode == 0
    report = json.loads(status_proc.stdout)
    assert report["vault_unlocked"] is True
    assert "demo" in report["stored_services"]


def test_cli_broker_hookup(tmp_path):
    """Broker wired: read-only product commands delegate to the engine.

    ``accounts`` needs no approval and touches no secrets — safe to run
    against the isolated home.
    """
    try:
        import levi.cybrus.broker  # noqa: F401

        landed = True
    except ImportError:
        landed = False

    proc = _run_cybrus_cli("broker", "--identity", "tester", "accounts",
                           iso_home=tmp_path / "h4")
    if landed:
        assert proc.returncode == 0, proc.stderr
    else:
        assert proc.returncode == 3
        assert "not landed yet" in proc.stdout


def test_cli_limits(tmp_path):
    proc = _run_cybrus_cli("limits", iso_home=tmp_path / "h5")
    assert proc.returncode == 0
    assert "FREE" in proc.stdout
    assert "STARTER" in proc.stdout
    assert "Chauncey" in proc.stdout  # pricing provisional flag


def test_gate_import_resolves_to_installed_wheel():
    """R2G-4 wheel binding: in release-gate runs the ``levi.cybrus`` under
    test MUST come from the installed wheel (site-packages), never a repo
    shadow on sys.path. Without this, a gate run with the repo's core/
    shadowing the path goes green while the wheel — the actual ship
    artifact — could differ. Opt-in via CYBRUS_GATE_REQUIRE_WHEEL=1 so
    ordinary dev runs against the repo checkout keep working; the
    release gate always sets it."""
    if os.environ.get("CYBRUS_GATE_REQUIRE_WHEEL") != "1":
        pytest.skip("wheel binding enforced only in release-gate runs")
    import importlib.metadata
    import importlib.util

    # The distribution must be installed, and its version must match the
    # product under test — a stale wheel is as bad as a repo shadow.
    assert importlib.metadata.version("cybrus") == product.PRODUCT_VERSION
    spec = importlib.util.find_spec("levi.cybrus.vault")
    assert spec is not None and spec.origin, "levi.cybrus.vault not importable"
    origin = Path(spec.origin).resolve()
    # Installed wheel == inside the distribution's own site-packages dir;
    # a repo checkout shadow resolves elsewhere and fails here.
    dist_info = Path(importlib.metadata.distribution("cybrus").locate_file(""))
    site_dir = dist_info.resolve().parent
    assert origin.is_relative_to(site_dir), (
        f"levi.cybrus resolves to {origin}, not the installed wheel "
        f"under {site_dir}: repo shadow suspected"
    )
